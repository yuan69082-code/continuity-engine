import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.awakening import (
    AwakeCycle,
    AwakeningResult,
    WakeAction,
    WakeContext,
    WakeDecision,
    WakeSession,
    WakeTimeInfo,
    WakeTrigger,
)
from continuity_engine.domain.errors import PerceptionValidationError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    FieldChange,
    StateMutation,
    StateSection,
    StateUpdateRecord,
)
from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryRelevanceDecision,
    MemoryRetrievalRequest,
    MemoryRetrievalResult,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.perception import (
    DriveKind,
    InteractionFrequencyTrend,
    PerceptionContext,
    PerceptionResult,
    RelationshipDirection,
    StateStability,
    TemporalMeaning,
)
from continuity_engine.domain.perception_rules import PerceptionPolicy
from continuity_engine.services.perception_service import PerceptionService


class MutatingPerceptionPolicy:
    def perceive(self, context):
        context.subject_state.continuity.current_focus.append("illegal mutation")
        return PerceptionPolicy().perceive(context)


class PerceptionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)

    def build_awakening(self) -> AwakeningResult:
        state = SubjectState.create("subject-1", self.now - timedelta(days=60))
        state.revision = 2
        state.temporal.updated_at = self.now - timedelta(days=8)
        state.temporal.last_interaction_at = self.now - timedelta(days=8)
        state.continuity.current_focus = ["Perception Engine"]
        state.continuity.unfinished_items = ["complete stage six"]
        state.relationship.current_status = "working together"

        interactions = []
        for index, days in enumerate((20, 15, 8), start=1):
            interactions.append(
                Event.create(
                    event_id=f"interaction-{index}",
                    occurred_at=self.now - timedelta(days=days),
                    source="user",
                    event_type="interaction",
                    content="A prior interaction occurred.",
                    impact_scope=[StateSection.TEMPORAL],
                    mutations=[],
                    reason="Track interaction continuity.",
                )
            )
        relationship_event = Event.create(
            event_id="relationship-event",
            occurred_at=self.now - timedelta(days=2),
            source="user",
            event_type="state_update",
            content="The collaboration became closer while stage six remained unfinished.",
            impact_scope=[StateSection.RELATIONSHIP, StateSection.CONTINUITY],
            mutations=[
                StateMutation(
                    field_path="relationship.current_status",
                    operation=ChangeOperation.SET,
                    value="working together",
                    reason="The collaboration status changed.",
                )
            ],
            reason="Record the relationship and unfinished work.",
            metadata={
                "relationship_direction": "closer",
                "important_at": (self.now + timedelta(days=3)).isoformat(),
                "important_label": "stage-six review",
            },
        )
        update = StateUpdateRecord(
            update_id="update-relationship",
            subject_id=state.subject_id,
            event=relationship_event,
            applied_at=self.now - timedelta(days=2),
            before_revision=1,
            after_revision=2,
            changes=[
                FieldChange(
                    field_path="relationship.current_status",
                    operation=ChangeOperation.SET,
                    before="initial collaboration",
                    after="working together",
                    reason="The collaboration status changed.",
                ),
                FieldChange(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    before=[],
                    after=["Perception Engine"],
                    reason="Stage six became the current focus.",
                ),
            ],
            reason="Record the relationship and unfinished work.",
        )

        request = MemoryRetrievalRequest.create(
            request_id="memory-request",
            subject_id=state.subject_id,
            query="Recall context relevant to the current focus.",
            requested_at=self.now,
            desired_scope=[StateSection.CONTINUITY],
        )
        candidate = MemoryCandidate(
            memory_id="memory-stage-six",
            subject_id=state.subject_id,
            content="A previous design review established that perception must be read-only.",
            source="external-memory-adapter",
            occurred_at=self.now - timedelta(days=30),
            provider_relevance=0.95,
            related_scope=[StateSection.CONTINUITY],
        )
        memory = MemoryRetrievalResult(
            request=request,
            evaluated_at=self.now,
            decisions=[
                MemoryRelevanceDecision(
                    candidate=candidate,
                    relevant=True,
                    relevance_score=0.95,
                    reasons=["The memory overlaps the current continuity focus."],
                    selected=True,
                )
            ],
        )
        context = WakeContext(
            context_id="wake-context",
            subject_state=state,
            recent_events=[*interactions, relationship_event],
            recent_updates=[update],
            memory_result=memory,
            time_info=WakeTimeInfo(
                current_time=self.now,
                last_interaction_at=state.temporal.last_interaction_at,
                seconds_since_last_interaction=8 * 24 * 60 * 60,
            ),
            created_at=self.now,
        )
        cycle = AwakeCycle.manual(
            subject_id=state.subject_id,
            created_at=self.now,
            cycle_id="cycle-1",
        )
        session = WakeSession.start(
            cycle,
            WakeTrigger.manual(triggered_at=self.now, detail="Run perception."),
        )
        session.complete(
            context=context,
            decision=WakeDecision(
                WakeAction.THINK,
                "Relevant state and memory need interpretation.",
                self.now,
                ["A selected memory is available."],
            ),
            completed_at=self.now,
        )
        return AwakeningResult(context=context, session=session)

    def test_perception_interprets_focus_time_relationship_memory_and_drives(self) -> None:
        awakening = self.build_awakening()
        state_before = awakening.context.subject_state.to_dict()
        context = PerceptionContext.from_awakening(
            awakening,
            current_time=self.now,
            context_id="perception-context",
        )

        result = PerceptionService().perceive(context)

        self.assertEqual(result.current_focus.topics, ["Perception Engine"])
        self.assertEqual(
            result.temporal_perception.last_interaction_meaning,
            TemporalMeaning.LONG_SILENCE,
        )
        self.assertEqual(
            result.temporal_perception.interaction_frequency_trend,
            InteractionFrequencyTrend.DECREASING,
        )
        self.assertEqual(
            result.temporal_perception.approaching_important_dates,
            ["stage-six review"],
        )
        self.assertEqual(
            result.relationship_perception.direction,
            RelationshipDirection.CLOSER,
        )
        self.assertTrue(result.relationship_perception.unfinished_exchange)
        self.assertTrue(result.relationship_perception.waiting_signal)
        self.assertEqual(
            result.memory_influence.impacts[0].recalled_experience,
            "A previous design review established that perception must be read-only.",
        )
        self.assertIn("continuity", result.memory_influence.impacts[0].influence_reason)
        self.assertEqual(result.observation.state_stability, StateStability.CHANGED)
        self.assertTrue(result.observation.major_change)
        self.assertIn(
            DriveKind.CONTINUE_TOPIC,
            {drive.kind for drive in result.internal_drives},
        )
        self.assertIn(
            DriveKind.KEEP_WAITING,
            {drive.kind for drive in result.internal_drives},
        )
        self.assertIn(
            DriveKind.INTEGRATE_MEMORY,
            {drive.kind for drive in result.internal_drives},
        )
        self.assertNotIn("found 1", result.memory_influence.summary.lower())
        self.assertFalse(hasattr(result, "subject_state"))
        self.assertEqual(awakening.context.subject_state.to_dict(), state_before)

    def test_perception_result_round_trips_without_raw_wake_or_state(self) -> None:
        awakening = self.build_awakening()
        context = PerceptionContext.from_awakening(
            awakening,
            current_time=self.now,
        )
        restored_context = PerceptionContext.from_dict(context.to_dict())
        result = PerceptionService().perceive(context)

        restored = PerceptionResult.from_dict(result.to_dict())

        self.assertEqual(restored.to_dict(), result.to_dict())
        self.assertEqual(restored_context.to_dict(), context.to_dict())
        self.assertNotIn("subject_state", result.to_dict())
        self.assertNotIn("wake_context", result.to_dict())

    def test_service_rejects_a_policy_that_mutates_subject_state(self) -> None:
        awakening = self.build_awakening()
        original_wake_state = awakening.context.subject_state.to_dict()
        context = PerceptionContext.from_awakening(
            awakening,
            current_time=self.now,
        )
        original_context_state = context.subject_state.to_dict()

        with self.assertRaises(PerceptionValidationError):
            PerceptionService(MutatingPerceptionPolicy()).perceive(context)

        self.assertEqual(
            awakening.context.subject_state.to_dict(),
            original_wake_state,
        )
        self.assertEqual(context.subject_state.to_dict(), original_context_state)


if __name__ == "__main__":
    unittest.main()
