from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.awakening import WakeReason
from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, StateSection
from continuity_engine.domain.scheduling import (
    NotificationStatus,
    SchedulerCancelStatus,
    SchedulerPersistenceError,
    SchedulerTaskState,
    SchedulerTickStatus,
)
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p11_scheduler_fixture import (
    P11SchedulerFixture,
    SimulatedSchedulerProcessCrash,
    run_p11_golden_scenario,
)
from continuity_engine.testing.p09_core_fixture import P09Fixture


UTC = timezone.utc
START = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


class P11SchedulerRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = P11SchedulerFixture.create(self.root, frozen_at=START)

    def _submit(self, task_id: str = "task-a", *, max_attempts: int = 3) -> None:
        self.fixture.service.submit(
            self.fixture.create_task(task_id=task_id, max_attempts=max_attempts)
        )

    def test_delivered_receipt_completes_once_across_duplicate_ticks(self) -> None:
        self._submit()
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        second = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(second.status, SchedulerTickStatus.IDLE)
        self.assertEqual(self.fixture.adapter.dispatch_count, 1)
        self.assertEqual(first.task.state, SchedulerTaskState.COMPLETED)

    def test_crash_checkpoint_queries_delivered_fact_after_restart_without_redispatch(self) -> None:
        self.fixture = P11SchedulerFixture.create(
            self.root / "crash-awakening", frozen_at=START, enable_awakening=True
        )
        self._submit()
        self.fixture.adapter.crash_after_effect_once = True
        with self.assertRaisesRegex(SimulatedSchedulerProcessCrash, "simulated crash"):
            self.fixture.service.tick(self.fixture.subject_id, "TEST")
        checkpoint = self.fixture.service.get(
            "task-a", subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual(checkpoint.state, SchedulerTaskState.UNKNOWN)
        restarted = self.fixture.restart()
        recovered = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(recovered.status, SchedulerTickStatus.RECONCILED_COMPLETED)
        self.assertEqual(restarted.adapter.query_count, 1)
        self.assertEqual(restarted.adapter.dispatch_count, 0)
        self.assertEqual(restarted.wake_count, 1)

    def test_unknown_is_queried_and_never_blindly_redispatched(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.status, SchedulerTickStatus.VERIFICATION_PENDING)
        restarted = self.fixture.restart()
        restarted.adapter.queue_query(NotificationStatus.UNKNOWN)
        restarted.clock.advance(timedelta(seconds=30))
        second = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(second.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(restarted.adapter.query_count, 1)
        self.assertEqual(restarted.adapter.dispatch_count, 0)

    def test_unknown_then_verified_delivery_opens_one_wake_after_restart(self) -> None:
        self.fixture = P11SchedulerFixture.create(
            self.root / "verified-delivery", frozen_at=START, enable_awakening=True
        )
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(self.fixture.wake_count, 0)
        restarted = self.fixture.restart()
        restarted.adapter.queue_query(NotificationStatus.DELIVERED)
        restarted.clock.advance(timedelta(seconds=30))
        recovered = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(recovered.status, SchedulerTickStatus.RECONCILED_COMPLETED)
        self.assertEqual(restarted.wake_count, 1)
        restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(restarted.wake_count, 1)

    def test_unresolved_unknown_does_not_starve_another_due_task(self) -> None:
        self._submit("unknown-first")
        self._submit("ready-second")
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.task.task_id, "unknown-first")
        second = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(second.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(second.task.task_id, "ready-second")
        self.assertEqual(self.fixture.adapter.dispatch_count, 2)
        self.assertEqual(self.fixture.adapter.query_count, 0)
        self.fixture.clock.advance(timedelta(seconds=30))
        self.fixture.adapter.queue_query(NotificationStatus.UNKNOWN)
        verification = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(verification.task.task_id, "unknown-first")
        self.assertEqual(verification.status, SchedulerTickStatus.VERIFICATION_PENDING)

    def test_query_exception_preserves_unknown_and_attempt_identity(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        attempt_id = first.task.last_attempt_id
        restarted = self.fixture.restart()
        restarted.adapter.raise_on_query = True
        restarted.clock.advance(timedelta(seconds=30))
        second = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(second.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(second.task.last_attempt_id, attempt_id)
        self.assertEqual(second.task.attempt_count, 1)

    def test_failed_attempt_retries_only_after_bounded_backoff(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.FAILED)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.status, SchedulerTickStatus.RETRY_SCHEDULED)
        first_attempt = first.task.last_attempt_id
        self.assertEqual(self.fixture.service.tick(self.fixture.subject_id, "TEST").status, SchedulerTickStatus.NOT_DUE)
        self.fixture.clock.advance(timedelta(seconds=30))
        second = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(second.status, SchedulerTickStatus.COMPLETED)
        self.assertNotEqual(second.task.last_attempt_id, first_attempt)
        self.assertEqual(second.task.attempt_count, 2)

    def test_retry_limit_enters_terminal_state(self) -> None:
        self._submit(max_attempts=2)
        self.fixture.adapter.queue_dispatch(NotificationStatus.FAILED, NotificationStatus.FAILED)
        self.assertEqual(
            self.fixture.service.tick(self.fixture.subject_id, "TEST").status,
            SchedulerTickStatus.RETRY_SCHEDULED,
        )
        self.fixture.clock.advance(timedelta(seconds=30))
        terminal = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(terminal.status, SchedulerTickStatus.RETRY_EXHAUSTED)
        self.assertEqual(terminal.task.state, SchedulerTaskState.RETRY_EXHAUSTED)
        self.assertEqual(self.fixture.adapter.dispatch_count, 2)

    def test_cancel_queued_is_idempotent_and_completed_never_regresses(self) -> None:
        self._submit("queued")
        first = self.fixture.service.cancel(
            "queued", subject_id=self.fixture.subject_id, environment="TEST"
        )
        second = self.fixture.service.cancel(
            "queued", subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual(first.status, SchedulerCancelStatus.CANCELLED)
        self.assertEqual(second.status, SchedulerCancelStatus.ALREADY_CANCELLED)
        self.assertEqual(self.fixture.adapter.dispatch_count, 0)

        self._submit("done")
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        completed = self.fixture.service.cancel(
            "done", subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual(completed.status, SchedulerCancelStatus.ALREADY_COMPLETED)
        self.assertEqual(completed.task.state, SchedulerTaskState.COMPLETED)

    def test_cancel_unknown_waits_for_fact_then_cancels_only_if_not_delivered(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        pending = self.fixture.service.cancel(
            "task-a", subject_id=self.fixture.subject_id, environment="TEST"
        )
        self.assertEqual(pending.status, SchedulerCancelStatus.VERIFICATION_REQUIRED)
        self.assertEqual(pending.task.state, SchedulerTaskState.UNKNOWN)
        restarted = self.fixture.restart()
        restarted.adapter.queue_query(NotificationStatus.NOT_DELIVERED)
        resolved = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(resolved.status, SchedulerTickStatus.CANCELLED)
        self.assertEqual(resolved.task.state, SchedulerTaskState.CANCELLED)

    def test_cancel_unknown_does_not_hide_delivered_fact(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.fixture.service.cancel("task-a", subject_id=self.fixture.subject_id, environment="TEST")
        restarted = self.fixture.restart()
        restarted.adapter.queue_query(NotificationStatus.DELIVERED)
        resolved = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(resolved.status, SchedulerTickStatus.RECONCILED_COMPLETED)
        self.assertEqual(resolved.task.state, SchedulerTaskState.COMPLETED)

    def test_receipt_identity_conflict_fails_closed_in_submit_and_query_paths(self) -> None:
        self._submit("dispatch-conflict")
        self.fixture.adapter.conflict_on_dispatch = True
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        self.assertEqual(first.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(first.task.state, SchedulerTaskState.UNKNOWN)

        restarted = self.fixture.restart()
        restarted.adapter.conflict_on_query = True
        second = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(second.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(second.task.state, SchedulerTaskState.UNKNOWN)
        self.assertEqual(restarted.adapter.dispatch_count, 0)

    def test_plain_status_string_cannot_prove_not_delivered(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        restarted = self.fixture.restart()
        restarted.adapter.query = lambda request: "NOT_DELIVERED"  # type: ignore[method-assign,return-value]
        restarted.clock.advance(timedelta(seconds=30))
        result = restarted.service.tick(restarted.subject_id, "TEST")
        self.assertEqual(result.status, SchedulerTickStatus.VERIFICATION_PENDING)
        self.assertEqual(result.task.state, SchedulerTaskState.UNKNOWN)
        self.assertEqual(restarted.adapter.dispatch_count, 0)

    def test_missing_attempt_binding_in_persistence_fails_closed(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        self.fixture.service.tick(self.fixture.subject_id, "TEST")
        data = json.loads(self.fixture.repository.path.read_text(encoding="utf-8"))
        data["tasks"][0]["last_attempt_id"] = None
        self.fixture.repository.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(SchedulerPersistenceError):
            self.fixture.restart().service.tick(self.fixture.subject_id, "TEST")

    def test_restart_preserves_attempt_number_and_backoff(self) -> None:
        self._submit()
        self.fixture.adapter.queue_dispatch(NotificationStatus.FAILED)
        first = self.fixture.service.tick(self.fixture.subject_id, "TEST")
        restarted = self.fixture.restart()
        loaded = restarted.service.get("task-a", subject_id=restarted.subject_id, environment="TEST")
        self.assertEqual(loaded.attempt_count, 1)
        self.assertEqual(loaded.next_attempt_at, first.task.next_attempt_at)
        self.assertEqual(restarted.service.tick(restarted.subject_id, "TEST").status, SchedulerTickStatus.NOT_DUE)

    def test_actual_awakening_integration_creates_one_wake_session(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "awakening", frozen_at=START, enable_awakening=True
        )
        fixture.service.submit(
            fixture.create_task(
                task_id="event-wake",
                wake_reason="event",
                source_event_id="event-001",
            )
        )
        result = fixture.service.tick(fixture.subject_id, "TEST")
        self.assertEqual(result.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(fixture.wake_count, 1)
        fixture.service.tick(fixture.subject_id, "TEST")
        self.assertEqual(fixture.wake_count, 1)
        session = fixture.awakening_repository.load_session(
            fixture.subject_id, result.task.last_attempt_id
        )
        self.assertEqual(session.source_event_id, "event-001")
        self.assertEqual(session.subject_id, fixture.subject_id)

    def test_successful_wake_reuses_resource_aware_scheduler_allocation(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "resource-aware-wake", frozen_at=START, enable_awakening=True
        )
        before = fixture.resource_manager.get_resource_state(fixture.subject_id)
        fixture.service.submit(fixture.create_task(task_id="resource-aware"))
        result = fixture.service.tick(fixture.subject_id, "TEST")
        after = fixture.resource_manager.get_resource_state(fixture.subject_id)
        usage = fixture.resource_repository.list_usage(fixture.subject_id)
        self.assertEqual(result.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(after.revision, before.revision + 1)
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].session_id, result.task.last_attempt_id)

    def test_scheduled_reason_uses_existing_scheduled_wake_boundary(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "scheduled-wake", frozen_at=START, enable_awakening=True
        )
        fixture.service.submit(
            fixture.create_task(task_id="scheduled", wake_reason="scheduled")
        )
        result = fixture.service.tick(fixture.subject_id, "TEST")
        session = fixture.awakening_repository.load_session(
            fixture.subject_id, result.task.last_attempt_id
        )
        self.assertEqual(result.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(session.wake_reason, WakeReason.SCHEDULED)
        cycle = fixture.awakening_repository.load_cycle(result.task.cycle_id)
        self.assertEqual(cycle.last_wake_at, START)
        self.assertGreater(cycle.next_wake_at, START)

    def test_event_timeline_and_awakening_composition_preserves_objective_fact(self) -> None:
        fixture = P11SchedulerFixture.create(
            self.root / "timeline", frozen_at=START, enable_awakening=True
        )
        repository = JsonSubjectStateRepository(fixture.root)
        states = SubjectStateService(repository, clock=fixture.clock.now)
        event = Event.create(
            event_id="timeline-source",
            occurred_at=START - timedelta(seconds=2),
            observed_at=START - timedelta(seconds=1),
            recorded_at=START,
            source="p11-test",
            source_kind=EventSourceKind.TEST,
            event_type=EventClassification.FACT.value,
            classification=EventClassification.FACT,
            content="Synthetic P11 scheduling fact.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Bind one scheduler opportunity to an existing Event fact.",
        )
        states.apply_event(fixture.subject_id, event)
        timeline = TimelineService(repository)
        before_entry = timeline.load_entry(fixture.subject_id, event.event_id)
        before_revision = states.load(fixture.subject_id).revision
        fixture.service.submit(
            fixture.create_task(
                task_id="timeline-wake",
                wake_reason="event",
                source_event_id=event.event_id,
            )
        )
        result = fixture.service.tick(fixture.subject_id, "TEST")
        after_entry = timeline.load_entry(fixture.subject_id, event.event_id)
        self.assertEqual(result.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(after_entry.event.to_dict(), before_entry.event.to_dict())
        self.assertEqual(after_entry.event.occurred_at, START - timedelta(seconds=2))
        self.assertEqual(states.load(fixture.subject_id).revision, before_revision)

    def test_p09_normal_chain_then_scheduler_opportunity_keeps_authorities_separate(self) -> None:
        c1 = P09Fixture(self.root / "c1")
        c1_result = c1.submit()
        subject_id = c1.runtime.descriptor.subject_id
        revision_before = c1.runtime.subject_states.load(subject_id).revision
        model_calls_before = c1.provider.calls
        action_effects_before = c1.adapter.effect_count
        fixture = P11SchedulerFixture.create(
            c1.runtime.data_root,
            frozen_at=c1.runtime.clock.now(),
            subject_id=subject_id,
            enable_awakening=True,
        )
        wake_count_before = fixture.wake_count
        fixture.service.submit(fixture.create_task(task_id="after-c1", priority=20))
        scheduled = fixture.service.tick(subject_id, "TEST")
        self.assertIsNotNone(c1_result)
        self.assertEqual(scheduled.status, SchedulerTickStatus.COMPLETED)
        self.assertEqual(c1.runtime.subject_states.load(subject_id).revision, revision_before)
        self.assertEqual(c1.provider.calls, model_calls_before)
        self.assertEqual(c1.adapter.effect_count, action_effects_before)
        self.assertEqual(fixture.wake_count, wake_count_before + 1)

    def test_golden_scenario_is_repeatable_and_bounded(self) -> None:
        first = run_p11_golden_scenario(self.root / "golden-a")
        second = run_p11_golden_scenario(self.root / "golden-b")
        self.assertEqual(first.canonical_result_hash, second.canonical_result_hash)
        self.assertEqual(first.completed_task_ids, ("event-priority", "internal-aged"))
        self.assertEqual(first.dispatch_count, 2)
        self.assertEqual(first.wake_session_count, 2)
        self.assertEqual(first.model_call_count, 0)
        self.assertEqual(first.action_call_count, 0)


if __name__ == "__main__":
    unittest.main()
