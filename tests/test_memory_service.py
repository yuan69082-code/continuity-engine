import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.errors import MemoryInfluenceError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.evolution import SubjectStateEvolver
from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryRetrievalRequest,
    MemoryRetrievalResult,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.services.memory_service import MemoryService


class StubMemoryRetriever:
    def __init__(self, candidates: list[MemoryCandidate]) -> None:
        self.candidates = candidates
        self.requests: list[MemoryRetrievalRequest] = []

    def retrieve(self, request: MemoryRetrievalRequest) -> list[MemoryCandidate]:
        self.requests.append(request)
        return list(self.candidates)


class SpyInfluenceRecorder:
    def __init__(self) -> None:
        self.records = []

    def record_influence(self, record) -> None:
        self.records.append(record)


class MemoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        self.request = MemoryRetrievalRequest.create(
            request_id="request-1",
            subject_id="subject-1",
            query="What unfinished project work should continue?",
            requested_at=self.now,
            desired_scope=[StateSection.CONTINUITY],
            limit=1,
            minimum_relevance=0.6,
            context={"current_phase": 3},
        )

    def candidate(
        self,
        memory_id: str,
        score: float,
        *,
        subject_id: str = "subject-1",
        scope: StateSection = StateSection.CONTINUITY,
        occurred_at: datetime | None = None,
    ) -> MemoryCandidate:
        return MemoryCandidate(
            memory_id=memory_id,
            subject_id=subject_id,
            content=f"Content for {memory_id}",
            source="external-test-adapter",
            occurred_at=occurred_at or self.now - timedelta(days=1),
            provider_relevance=score,
            related_scope=[scope],
        )

    def test_retrieval_filters_ranks_and_serializes_decisions(self) -> None:
        retriever = StubMemoryRetriever(
            [
                self.candidate("selected", 0.90),
                self.candidate("limited-out", 0.80),
                self.candidate("wrong-subject", 0.99, subject_id="subject-2"),
                self.candidate("wrong-scope", 0.95, scope=StateSection.IDENTITY),
                self.candidate("low-score", 0.40),
                self.candidate(
                    "future-memory",
                    0.92,
                    occurred_at=self.now + timedelta(minutes=1),
                ),
            ]
        )
        recorder = SpyInfluenceRecorder()
        service = MemoryService(retriever, recorder, clock=lambda: self.now)

        result = service.retrieve(self.request)

        self.assertEqual([item.memory_id for item in result.selected_memories], ["selected"])
        self.assertEqual(retriever.requests, [self.request])
        decisions = {decision.candidate.memory_id: decision for decision in result.decisions}
        self.assertTrue(decisions["limited-out"].relevant)
        self.assertFalse(decisions["limited-out"].selected)
        self.assertFalse(decisions["wrong-subject"].relevant)
        self.assertFalse(decisions["wrong-scope"].relevant)
        self.assertFalse(decisions["low-score"].relevant)
        self.assertFalse(decisions["future-memory"].relevant)
        self.assertEqual(
            MemoryRetrievalResult.from_dict(result.to_dict()).to_dict(),
            result.to_dict(),
        )

    def test_influence_record_links_selected_memory_to_state_update(self) -> None:
        retriever = StubMemoryRetriever([self.candidate("selected", 0.90)])
        recorder = SpyInfluenceRecorder()
        service = MemoryService(retriever, recorder, clock=lambda: self.now)
        result = service.retrieve(self.request)

        state = SubjectState.create("subject-1", now=self.now - timedelta(minutes=5))
        event = Event.create(
            event_id="event-from-memory",
            occurred_at=self.now,
            source="memory-manager",
            event_type="state_update",
            content="A selected memory restored an unfinished focus.",
            impact_scope=[StateSection.CONTINUITY],
            mutations=[
                StateMutation(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    value="continue the project",
                    reason="The selected memory showed that the project was unfinished.",
                )
            ],
            reason="Let the relevant memory affect the current subject state.",
        )
        update = SubjectStateEvolver().evolve(state, event, applied_at=self.now).update

        influence = service.record_influence(
            result,
            memory_id="selected",
            influence_type="state_change",
            summary="Restored the unfinished project focus.",
            reason="The selected memory was directly relevant to continuity.",
            state_update=update,
            metadata={"adapter": "future-mcp-compatible"},
        )

        self.assertEqual(recorder.records, [influence])
        self.assertEqual(influence.related_event_id, "event-from-memory")
        self.assertEqual(influence.related_update_id, update.update_id)
        self.assertIn("continuity.current_focus", influence.affected_fields)

    def test_influence_cannot_reference_unselected_memory(self) -> None:
        retriever = StubMemoryRetriever(
            [
                self.candidate("selected", 0.90),
                self.candidate("not-selected", 0.80),
            ]
        )
        service = MemoryService(retriever, SpyInfluenceRecorder(), clock=lambda: self.now)
        result = service.retrieve(self.request)

        with self.assertRaises(MemoryInfluenceError):
            service.record_influence(
                result,
                memory_id="not-selected",
                influence_type="judgment",
                summary="Should not be recorded.",
                reason="The candidate was not selected under the request limit.",
            )


if __name__ == "__main__":
    unittest.main()
