from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from continuity_engine.domain.scheduling import (
    NotificationStatus,
    QuietHours,
    SchedulerAdmissionStatus,
    SchedulerIdentityConflictError,
    SchedulerPersistenceError,
    SchedulerTask,
    SchedulerTaskState,
    SchedulerTickStatus,
    SchedulerValidationError,
    SchedulerWakeReason,
)
from continuity_engine.storage.json_scheduler_repository import JsonSchedulerRepository
from continuity_engine.testing.p11_scheduler_fixture import P11SchedulerFixture
from continuity_engine.testing.models import SandboxOperationError


UTC = timezone.utc
START = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


class P11SchedulerDomainTests(unittest.TestCase):
    def test_task_requires_trusted_utc_time_and_event_source(self) -> None:
        with self.assertRaises(SchedulerValidationError):
            SchedulerTask.create(
                task_id="task-naive",
                subject_id="subject-a",
                environment="TEST",
                priority=5,
                due_at=START.replace(tzinfo=None),
                wake_reason=SchedulerWakeReason.INTERNAL,
                cycle_id="cycle-a",
                created_at=START,
            )
        with self.assertRaises(SchedulerValidationError):
            SchedulerTask.create(
                task_id="task-event",
                subject_id="subject-a",
                environment="TEST",
                priority=5,
                due_at=START,
                wake_reason=SchedulerWakeReason.EVENT,
                cycle_id="cycle-a",
                created_at=START,
            )

    def test_task_round_trip_preserves_identity_hash(self) -> None:
        task = SchedulerTask.create(
            task_id="task-roundtrip",
            subject_id="subject-a",
            environment="TEST",
            priority=42,
            due_at=START,
            wake_reason=SchedulerWakeReason.EVENT,
            cycle_id="cycle-a",
            source_event_id="event-a",
            created_at=START,
            max_attempts=4,
        )
        self.assertEqual(SchedulerTask.from_dict(task.to_dict()), task)
        self.assertEqual(task.identity_hash, SchedulerTask.from_dict(task.to_dict()).identity_hash)

    def test_tampered_identity_hash_fails_closed(self) -> None:
        task = SchedulerTask.create(
            task_id="task-tamper",
            subject_id="subject-a",
            environment="TEST",
            priority=3,
            due_at=START,
            wake_reason=SchedulerWakeReason.INTERNAL,
            cycle_id="cycle-a",
            created_at=START,
        )
        value = task.to_dict()
        value["priority"] = 99
        with self.assertRaises(SchedulerValidationError):
            SchedulerTask.from_dict(value)

    def test_quiet_hours_supports_midnight_crossing(self) -> None:
        hours = QuietHours(start=time(22, 0), end=time(7, 0))
        self.assertTrue(hours.contains(datetime(2026, 9, 5, 23, 0, tzinfo=UTC)))
        self.assertTrue(hours.contains(datetime(2026, 9, 6, 6, 59, tzinfo=UTC)))
        self.assertFalse(hours.contains(datetime(2026, 9, 6, 7, 0, tzinfo=UTC)))


class P11SchedulerQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = P11SchedulerFixture.create(self.root, frozen_at=START)

    def test_submit_persists_stable_identity_and_binding(self) -> None:
        task = self.fixture.create_task(task_id="task-a", priority=10)
        admitted = self.fixture.service.submit(task)
        self.assertEqual(admitted.status, SchedulerAdmissionStatus.ACCEPTED)
        loaded = self.fixture.restart().service.get(
            "task-a", subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual(loaded.identity_hash, task.identity_hash)
        self.assertEqual(loaded.state, SchedulerTaskState.QUEUED)
        self.assertEqual(loaded.sequence, 1)

    def test_duplicate_submit_is_idempotent_but_conflict_is_rejected(self) -> None:
        task = self.fixture.create_task(task_id="task-duplicate", priority=10)
        first = self.fixture.service.submit(task)
        before = self.fixture.repository.path.read_bytes()
        second = self.fixture.service.submit(task)
        self.assertEqual(first.task.identity_hash, second.task.identity_hash)
        self.assertEqual(second.status, SchedulerAdmissionStatus.DUPLICATE)
        self.assertEqual(self.fixture.repository.path.read_bytes(), before)
        conflict = self.fixture.create_task(task_id="task-duplicate", priority=11)
        with self.assertRaises(SchedulerIdentityConflictError):
            self.fixture.service.submit(conflict)

    def test_backpressure_has_explicit_result_and_zero_queue_write(self) -> None:
        fixture = P11SchedulerFixture.create(self.root / "bounded", frozen_at=START, capacity=1)
        fixture.service.submit(fixture.create_task(task_id="task-one"))
        before = fixture.repository.path.read_bytes()
        rejected = fixture.service.submit(fixture.create_task(task_id="task-two"))
        self.assertEqual(rejected.status, SchedulerAdmissionStatus.BACKPRESSURE)
        self.assertEqual(fixture.repository.path.read_bytes(), before)
        self.assertEqual(len(fixture.service.list_tasks(subject_id=fixture.subject_id, environment="TEST")), 1)

    def test_priority_due_time_and_sequence_are_deterministic(self) -> None:
        for task_id, priority, offset in (
            ("later-high", 100, 30),
            ("same-b", 20, 0),
            ("same-a", 20, 0),
            ("low", 1, 0),
        ):
            self.fixture.service.submit(
                self.fixture.create_task(
                    task_id=task_id,
                    priority=priority,
                    due_at=START + timedelta(seconds=offset),
                )
            )
        ordered = self.fixture.service.ready_tasks(
            subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual([task.task_id for task in ordered], ["same-b", "same-a", "low"])
        self.assertEqual(self.fixture.service.tick(self.fixture.subject_id, "TEST").task.task_id, "same-b")

    def test_not_due_and_out_of_order_input_do_not_dispatch(self) -> None:
        self.fixture.service.submit(
            self.fixture.create_task(task_id="future", due_at=START + timedelta(minutes=5))
        )
        result = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(result.status, SchedulerTickStatus.NOT_DUE)
        self.assertEqual(self.fixture.adapter.dispatch_count, 0)
        self.fixture.clock.advance(timedelta(minutes=5))
        self.assertEqual(
            self.fixture.service.tick(self.fixture.subject_id, "TEST").status,
            SchedulerTickStatus.COMPLETED,
        )

    def test_quiet_hours_defer_without_attempt_or_write(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "quiet",
            frozen_at=datetime(2026, 9, 5, 23, 0, tzinfo=UTC),
            quiet_hours=QuietHours(start=time(22), end=time(7)),
        )
        fixture.service.submit(fixture.create_task(task_id="quiet-task"))
        before = fixture.repository.path.read_bytes()
        result = fixture.service.tick(fixture.subject_id, "TEST")
        self.assertEqual(result.status, SchedulerTickStatus.QUIET_HOURS)
        self.assertEqual(result.task.attempt_count, 0)
        self.assertEqual(fixture.adapter.dispatch_count, 0)
        self.assertEqual(fixture.repository.path.read_bytes(), before)

    def test_resource_shortage_defers_without_attempt_wake_or_resource_write(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "resources", frozen_at=START, token_budget=0, compute_budget=0
        )
        fixture.service.submit(fixture.create_task(task_id="resource-task"))
        resource_path = fixture.resource_repository.path_for_test(fixture.subject_id)
        resource_before = resource_path.read_bytes()
        queue_before = fixture.repository.path.read_bytes()
        result = fixture.service.tick(fixture.subject_id, "TEST")
        self.assertEqual(result.status, SchedulerTickStatus.RESOURCE_DEFERRED)
        self.assertEqual(result.task.attempt_count, 0)
        self.assertEqual(fixture.adapter.dispatch_count, 0)
        self.assertEqual(fixture.wake_count, 0)
        self.assertEqual(resource_path.read_bytes(), resource_before)
        self.assertEqual(fixture.repository.path.read_bytes(), queue_before)

    def test_aging_prevents_starvation_under_continuous_high_priority_arrivals(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "aging", frozen_at=START, aging_interval_seconds=1
        )
        fixture.service.submit(fixture.create_task(task_id="low", priority=0))
        fixture.clock.advance(timedelta(seconds=101))
        fixture.service.submit(fixture.create_task(task_id="new-high", priority=100))
        ordered = fixture.service.ready_tasks(subject_id=fixture.subject_id, environment="TEST")
        self.assertEqual(ordered[0].task_id, "low")
        self.assertGreater(ordered[0].effective_priority(fixture.clock.now(), 1), 100)

    def test_bounded_long_run_gives_low_priority_task_an_opportunity(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "bounded-long", frozen_at=START, aging_interval_seconds=1, capacity=256
        )
        fixture.service.submit(fixture.create_task(task_id="long-low", priority=0))
        completed_at_tick: int | None = None
        for tick in range(1, 103):
            fixture.clock.advance(timedelta(seconds=1))
            fixture.service.submit(
                fixture.create_task(task_id=f"stream-high-{tick:03d}", priority=100)
            )
            result = fixture.service.tick(fixture.subject_id, "TEST")
            if result.task is not None and result.task.task_id == "long-low":
                completed_at_tick = tick
                break
        self.assertIsNotNone(completed_at_tick)
        self.assertLessEqual(completed_at_tick, 101)
        self.assertEqual(
            len({call.attempt_id for call in fixture.adapter.dispatch_requests}),
            fixture.adapter.dispatch_count,
        )

    def test_subject_and_environment_are_fail_closed(self) -> None:
        self.fixture.service.submit(self.fixture.create_task(task_id="bound"))
        with self.assertRaises(SchedulerIdentityConflictError):
            self.fixture.service.get("bound", subject_id="other", environment="TEST")
        with self.assertRaises(SchedulerIdentityConflictError):
            self.fixture.service.get("bound", subject_id=self.fixture.subject_id, environment="PROD")
        self.assertEqual(self.fixture.adapter.dispatch_count, 0)

    def test_corrupt_queue_and_unknown_fields_fail_closed(self) -> None:
        self.fixture.service.submit(self.fixture.create_task(task_id="corrupt"))
        self.fixture.repository.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(SchedulerPersistenceError):
            self.fixture.service.list_tasks(subject_id=self.fixture.subject_id, environment="TEST")

        other = P11SchedulerFixture.create(self.root / "unknown", frozen_at=START)
        other.service.submit(other.create_task(task_id="unknown-field"))
        value = json.loads(other.repository.path.read_text(encoding="utf-8"))
        value["authority"] = "subject-state"
        other.repository.path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(SchedulerPersistenceError):
            other.repository.load_queue()

        changed = P11SchedulerFixture.create(self.root / "changed-order", frozen_at=START)
        changed.service.submit(changed.create_task(task_id="order-a"))
        changed.service.submit(changed.create_task(task_id="order-b"))
        value = json.loads(changed.repository.path.read_text(encoding="utf-8"))
        value["tasks"][0]["sequence"] = 99
        changed.repository.path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(SchedulerPersistenceError):
            changed.repository.load_queue()

    def test_repository_revision_rejects_stale_writer(self) -> None:
        repo_a = JsonSchedulerRepository(self.root / "revision")
        repo_b = JsonSchedulerRepository(self.root / "revision")
        first = repo_a.load_queue()
        stale = repo_b.load_queue()
        first.revision = 1
        repo_a.save_queue(first, expected_revision=0)
        stale.revision = 1
        with self.assertRaises(SchedulerPersistenceError):
            repo_b.save_queue(stale, expected_revision=0)

    def test_scheduler_records_no_psychological_or_action_payload(self) -> None:
        self.fixture.service.submit(self.fixture.create_task(task_id="minimal-record"))
        document = self.fixture.repository.path.read_text(encoding="utf-8").lower()
        for forbidden in ("thought", "emotion", "desire", "will", "decision", "action_intent"):
            self.assertNotIn(forbidden, document)

    def test_fixture_rejects_protected_overlap_before_any_write(self) -> None:
        protected = self.root / "protected"
        protected.mkdir()
        marker = protected / "marker.txt"
        marker.write_text("unchanged", encoding="utf-8")
        before = {p.relative_to(protected).as_posix(): p.read_bytes() for p in protected.rglob("*") if p.is_file()}
        with self.assertRaises(SandboxOperationError):
            P11SchedulerFixture.create(
                protected / "nested",
                frozen_at=START,
                protected_paths=(protected,),
            )
        after = {p.relative_to(protected).as_posix(): p.read_bytes() for p in protected.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        self.assertFalse((protected / "nested").exists())


class P11SchedulerAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = P11SchedulerFixture.create(self.root, frozen_at=START)

    def _files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }

    def _assert_rejected_without_io(self, task: SchedulerTask) -> None:
        before = self._files()
        validation_error = None
        with ExitStack() as stack:
            load = stack.enter_context(patch.object(
                self.fixture.repository, "load_queue", wraps=self.fixture.repository.load_queue
            ))
            save = stack.enter_context(patch.object(
                self.fixture.repository, "save_queue", wraps=self.fixture.repository.save_queue
            ))
            notification = Mock(wraps=self.fixture.adapter)
            resources = Mock(wraps=self.fixture.resource_manager)
            stack.enter_context(patch.object(self.fixture.service, "_notification", notification))
            stack.enter_context(patch.object(self.fixture.service, "_resources", resources))
            try:
                self.fixture.service.submit(task)
            except SchedulerValidationError as exc:
                validation_error = exc
        self.assertEqual(
            {
                "validation_error": validation_error is not None,
                "queue_reads": load.call_count,
                "queue_writes": save.call_count,
                "notification_calls": len(notification.mock_calls),
                "resource_calls": len(resources.mock_calls),
                "files_unchanged": self._files() == before,
            },
            {
                "validation_error": True,
                "queue_reads": 0,
                "queue_writes": 0,
                "notification_calls": 0,
                "resource_calls": 0,
                "files_unchanged": True,
            },
        )
        self.assertIn("new task", str(validation_error))

    def _history_variants(self) -> dict[str, object]:
        return {
            "attempt_count": 1,
            "next_attempt_at": START + timedelta(seconds=30),
            "last_attempt_id": "forged-attempt",
            "last_receipt_id": "forged-receipt",
            "last_receipt_hash": "sha256:" + "a" * 64,
            "last_receipt_status": NotificationStatus.DELIVERED,
            "cancel_requested_at": START,
            "completed_at": START,
            "reason_codes": ("FORGED_HISTORY",),
        }

    def test_initial_history_rejected_before_io_without_queue(self) -> None:
        self.assertFalse(self.fixture.repository.path.exists())
        for field_name, value in self._history_variants().items():
            with self.subTest(field=field_name):
                task = self.fixture.create_task(task_id="forged-" + field_name)
                setattr(task, field_name, value)
                self._assert_rejected_without_io(task)
                self.assertFalse(self.fixture.repository.path.exists())

    def test_initial_history_rejected_before_io_with_existing_queue(self) -> None:
        self.fixture.service.submit(self.fixture.create_task(task_id="existing"))
        for field_name, value in self._history_variants().items():
            with self.subTest(field=field_name):
                task = self.fixture.create_task(task_id="forged-" + field_name)
                setattr(task, field_name, value)
                self._assert_rejected_without_io(task)

    def test_combined_attempt_receipt_cancel_history_rejected_before_io(self) -> None:
        task = self.fixture.create_task(task_id="forged-combined")
        for field_name, value in self._history_variants().items():
            if field_name != "completed_at":
                setattr(task, field_name, value)
        # This is a valid recovery-shaped object; only new admission must reject it.
        task.__post_init__()
        self._assert_rejected_without_io(task)

    def test_exhausted_initial_attempt_rejected_before_enqueue(self) -> None:
        task = self.fixture.create_task(task_id="poisoned", max_attempts=1)
        task.attempt_count = task.max_attempts
        task.last_attempt_id = "forged-attempt"
        task.__post_init__()
        self._assert_rejected_without_io(task)
        self.assertFalse(self.fixture.repository.path.exists())
        self.assertEqual(
            self.fixture.service.tick(self.fixture.subject_id, "TEST").status,
            SchedulerTickStatus.IDLE,
        )
        self.assertEqual(self.fixture.adapter.dispatch_count, 0)

    def test_noninitial_state_sequence_revision_rejected_before_io(self) -> None:
        for field_name, value in (
            ("state", SchedulerTaskState.CANCELLED), ("sequence", 1), ("revision", 1)
        ):
            with self.subTest(field=field_name):
                task = self.fixture.create_task(task_id="noninitial-" + field_name)
                setattr(task, field_name, value)
                self._assert_rejected_without_io(task)

    def test_created_task_and_persisted_retry_completion_remain_compatible(self) -> None:
        task = self.fixture.create_task(task_id="legitimate")
        self.assertEqual(self.fixture.service.submit(task).status, SchedulerAdmissionStatus.ACCEPTED)
        self.fixture.adapter.queue_dispatch(NotificationStatus.FAILED)
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        restarted = self.fixture.restart()
        loaded = restarted.service.get(task.task_id, subject_id=task.subject_id, environment="TEST")
        self.assertEqual(loaded.state, SchedulerTaskState.RETRY_WAIT)
        self.assertEqual(loaded.attempt_count, 1)
        self.assertEqual(loaded.last_receipt_status, NotificationStatus.FAILED)
        before = restarted.repository.path.read_bytes()
        duplicate = restarted.service.submit(task)
        self.assertEqual(duplicate.status, SchedulerAdmissionStatus.DUPLICATE)
        self.assertEqual(duplicate.task, loaded)
        self.assertEqual(restarted.repository.path.read_bytes(), before)
        restarted.clock.advance(timedelta(seconds=30))
        self.assertEqual(
            restarted.service.tick(task.subject_id, "TEST").status,
            SchedulerTickStatus.COMPLETED,
        )
        completed = restarted.restart().service.get(
            task.task_id, subject_id=task.subject_id, environment="TEST"
        )
        self.assertEqual(completed.state, SchedulerTaskState.COMPLETED)
        self.assertEqual(completed.attempt_count, 2)
        self.assertIsNotNone(completed.completed_at)
        self.assertEqual(completed.last_receipt_status, NotificationStatus.DELIVERED)


if __name__ == "__main__":
    unittest.main()
