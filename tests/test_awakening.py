import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.awakening import WakeAction, WakeReason
from continuity_engine.domain.errors import WakeExecutionError, WakeNotDueError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.memory import MemoryCandidate, MemoryRetrievalRequest
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class CandidateRetriever:
    def __init__(self, candidates=None) -> None:
        self.candidates = list(candidates or [])
        self.requests: list[MemoryRetrievalRequest] = []

    def retrieve(self, request: MemoryRetrievalRequest):
        self.requests.append(request)
        return list(self.candidates)


class FailingRetriever:
    def retrieve(self, request: MemoryRetrievalRequest):
        raise RuntimeError("external memory provider unavailable")


class DiscardingInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class AwakeningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)

    def services(self, directory, retriever):
        state_service = SubjectStateService(
            JsonSubjectStateRepository(directory),
            clock=lambda: self.now,
        )
        memory_service = MemoryService(
            retriever,
            DiscardingInfluenceRecorder(),
            clock=lambda: self.now,
        )
        awakening_repository = JsonAwakeningRepository(directory)
        awakening_service = AwakeningService(
            state_service,
            memory_service,
            awakening_repository,
            clock=lambda: self.now,
        )
        return state_service, awakening_service, awakening_repository

    def test_manual_wake_runs_full_pipeline_and_persists_ready_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            retriever = CandidateRetriever()
            states, awakening, repository = self.services(directory, retriever)
            state = states.create("subject-1")
            state.continuity.current_focus.append("continue fourth-stage work")
            states.save(state)
            cycle = awakening.create_manual_cycle("subject-1")

            result = awakening.wake_manual(cycle.cycle_id, detail="Operator requested a wake.")

            self.assertTrue(result.session.completed_successfully)
            self.assertEqual(result.session.wake_reason, WakeReason.MANUAL)
            self.assertEqual(result.session.subject_revision, 0)
            self.assertEqual(result.session.decision.action, WakeAction.READY)
            self.assertEqual(result.context.subject_state.subject_id, "subject-1")
            self.assertEqual(result.context.recent_events, [])
            self.assertEqual(result.context.recent_updates, [])
            self.assertEqual(result.context.memory_result.selected_memories, [])
            self.assertEqual(len(retriever.requests), 1)

            restored = JsonAwakeningRepository(directory).load_session(
                "subject-1", result.session.session_id
            )
            self.assertEqual(restored.to_dict(), result.session.to_dict())
            self.assertEqual(repository.list_sessions("subject-1"), [result.session])

    def test_scheduled_wake_selects_memory_and_advances_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = MemoryCandidate(
                memory_id="memory-1",
                subject_id="subject-1",
                content="The subject previously planned the next implementation step.",
                source="external-memory-adapter",
                occurred_at=self.now - timedelta(days=1),
                provider_relevance=0.9,
                related_scope=[StateSection.CONTINUITY],
            )
            states, awakening, repository = self.services(
                directory, CandidateRetriever([candidate])
            )
            states.create("subject-1")
            cycle = awakening.create_scheduled_cycle(
                "subject-1",
                interval_seconds=300,
                first_wake_at=self.now,
            )

            self.assertEqual([item.cycle_id for item in awakening.list_due_cycles()], [cycle.cycle_id])
            result = awakening.wake_scheduled(cycle.cycle_id)

            self.assertEqual(result.session.wake_reason, WakeReason.SCHEDULED)
            self.assertEqual(result.session.decision.action, WakeAction.THINK)
            self.assertEqual(result.session.observation.viewed_memory_ids, ["memory-1"])
            self.assertEqual(result.session.observation.selected_memory_ids, ["memory-1"])
            restored_cycle = repository.load_cycle(cycle.cycle_id)
            self.assertEqual(restored_cycle.last_wake_at, self.now)
            self.assertEqual(restored_cycle.next_wake_at, self.now + timedelta(seconds=300))

            with self.assertRaises(WakeNotDueError):
                awakening.wake_scheduled(cycle.cycle_id)

    def test_rejected_memory_returns_check_memory_without_executing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = MemoryCandidate(
                memory_id="low-relevance",
                subject_id="subject-1",
                content="An unrelated old detail.",
                source="external-memory-adapter",
                occurred_at=self.now - timedelta(days=1),
                provider_relevance=0.1,
                related_scope=[StateSection.CONTINUITY],
            )
            states, awakening, _ = self.services(directory, CandidateRetriever([candidate]))
            states.create("subject-1")
            cycle = awakening.create_manual_cycle("subject-1")

            result = awakening.wake_manual(cycle.cycle_id, detail="Review current continuity.")

            self.assertEqual(result.session.decision.action, WakeAction.CHECK_MEMORY)
            self.assertEqual(result.context.memory_result.selected_memories, [])

    def test_recent_evolution_is_loaded_into_context_and_returns_think(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states, awakening, _ = self.services(directory, CandidateRetriever())
            states.create("subject-1")
            event = Event.create(
                event_id="recent-event",
                occurred_at=self.now,
                source="user",
                event_type="state_update",
                content="The current project focus changed.",
                impact_scope=[StateSection.CONTINUITY],
                mutations=[
                    StateMutation(
                        field_path="continuity.recent_changes",
                        operation=ChangeOperation.APPEND,
                        value="awakening work started",
                        reason="The project entered its awakening stage.",
                    )
                ],
                reason="Keep the current development stage continuous.",
            )
            update = states.apply_event("subject-1", event).update
            cycle = awakening.create_manual_cycle("subject-1")

            result = awakening.wake_manual(cycle.cycle_id, detail="Review recent evolution.")

            self.assertEqual(result.session.decision.action, WakeAction.THINK)
            self.assertEqual([item.event_id for item in result.context.recent_events], ["recent-event"])
            self.assertEqual(
                [item.update_id for item in result.context.recent_updates],
                [update.update_id],
            )
            self.assertEqual(result.session.observation.event_ids, ["recent-event"])
            self.assertEqual(result.session.observation.update_ids, [update.update_id])

    def test_quiet_wake_returns_sleep_without_executing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states, awakening, _ = self.services(directory, CandidateRetriever())
            states.create("subject-1")
            cycle = awakening.create_manual_cycle("subject-1")

            result = awakening.wake_manual(cycle.cycle_id, detail="Periodic quiet check.")

            self.assertTrue(result.session.completed_successfully)
            self.assertEqual(result.session.decision.action, WakeAction.SLEEP)

    def test_failed_memory_request_is_logged_and_forces_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states, awakening, repository = self.services(directory, FailingRetriever())
            states.create("subject-1")
            cycle = awakening.create_manual_cycle("subject-1")

            with self.assertRaises(WakeExecutionError) as captured:
                awakening.wake_for_event(
                    cycle.cycle_id,
                    source_event_id="event-1",
                    detail="A state event requested a wake.",
                )

            sessions = repository.list_sessions("subject-1")
            self.assertEqual(len(sessions), 1)
            session = sessions[0]
            self.assertEqual(session.session_id, captured.exception.session_id)
            self.assertFalse(session.completed_successfully)
            self.assertEqual(session.wake_reason, WakeReason.EVENT)
            self.assertEqual(session.source_event_id, "event-1")
            self.assertEqual(session.subject_revision, 0)
            self.assertEqual(session.decision.action, WakeAction.SLEEP)
            self.assertIn("external memory provider unavailable", session.error)


if __name__ == "__main__":
    unittest.main()
