import tempfile
import unittest
from datetime import datetime, timezone

from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.domain.events import ChangeOperation, Event, StateMutation, StateSection
from continuity_engine.domain.learning import (
    LearningContext,
    LearningRecordType,
    LearningValidationStatus,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.perception import (
    CurrentFocus,
    InteractionFrequencyTrend,
    MemoryInfluence,
    Observation,
    PerceptionResult,
    RelationshipDirection,
    RelationshipPerception,
    StateStability,
    TemporalMeaning,
    TemporalPerception,
)
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    ThinkingResult,
    TokenBudget,
)
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class PersonalityLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = temporary.name
        self.learning = LearningService(
            JsonLearningRepository(self.directory),
            clock=lambda: self.now,
        )
        self.states = SubjectStateService(
            JsonSubjectStateRepository(self.directory),
            clock=lambda: self.now,
        )
        self.states.create("subject-1")

    def candidate(self, source_event_id: str, confidence: float = 0.55):
        return self.learning.create_candidate(
            "subject-1",
            source_event_id=source_event_id,
            source_memory_id=None,
            related_state_revision=0,
            observation="Concise responses repeatedly preserved clarity.",
            hypothesis="A concise expression preference is useful over time.",
            proposed_change=StateMutation(
                field_path="identity.expression_preferences",
                operation=ChangeOperation.APPEND,
                value="prefers concise responses",
                reason=f"Evidence from {source_event_id} supports this preference.",
            ),
            confidence=confidence,
            original_experience={
                "event_id": source_event_id,
                "content": "A concise response was explicitly evaluated as useful.",
            },
            reason="The structured experience may have long-term learning value.",
            source="explicit_evaluation",
        )

    def validated_learning(self):
        first = self.candidate("event-1")
        second = self.candidate("event-2")
        third = self.candidate("event-3")
        validated = self.learning.validate_learning(
            "subject-1",
            first.learning_event.learning_id,
            [second.learning_event.learning_id, third.learning_event.learning_id],
            reason="Three independent experiences support the same hypothesis.",
            source="learning_review",
        )
        return validated

    def consolidated_learning(self):
        validated = self.validated_learning()
        state = self.states.load("subject-1")
        result = self.learning.solidify_learning(
            "subject-1",
            validated.learning_event.learning_id,
            state,
            trait_name="Concise expression",
            trait_description="Prefer concise replies when they preserve clarity.",
            reason="The explicitly reviewed evidence met the consolidation threshold.",
            source="confirmed_learning_review",
            confirmed=True,
            expected_revision=state.revision,
        )
        return result

    def test_single_experience_only_creates_candidate(self) -> None:
        before = self.states.load("subject-1").to_dict()

        result = self.candidate("event-only")

        after = self.states.load("subject-1").to_dict()
        self.assertEqual(result.learning_event.validation_status, LearningValidationStatus.PENDING)
        self.assertEqual(before, after)
        self.assertEqual(self.learning.list_traits("subject-1"), [])
        self.assertIsNone(result.record.state_event_id)

    def test_consistent_experiences_raise_confidence_and_validate(self) -> None:
        validated = self.validated_learning()

        self.assertEqual(
            validated.learning_event.validation_status,
            LearningValidationStatus.VALIDATED,
        )
        self.assertGreaterEqual(validated.learning_event.confidence, 0.75)
        self.assertEqual(len(validated.learning_event.evidence_learning_ids), 3)
        self.assertEqual(validated.record.record_type, LearningRecordType.VALIDATED)
        self.assertEqual(self.states.load("subject-1").revision, 0)

    def test_confidence_can_be_raised_or_lowered_without_state_change(self) -> None:
        candidate = self.candidate("event-confidence", confidence=0.5)

        raised = self.learning.adjust_confidence(
            "subject-1",
            candidate.learning_event.learning_id,
            0.2,
            reason="A review supported the hypothesis.",
            source="learning_review",
        )
        lowered = self.learning.adjust_confidence(
            "subject-1",
            candidate.learning_event.learning_id,
            -0.4,
            reason="Contradictory evidence weakened the hypothesis.",
            source="learning_review",
        )

        self.assertEqual(raised.learning_event.confidence, 0.7)
        self.assertAlmostEqual(lowered.learning_event.confidence, 0.3)
        self.assertEqual(lowered.learning_event.validation_status, LearningValidationStatus.PENDING)
        self.assertEqual(self.states.load("subject-1").revision, 0)

    def test_unvalidated_learning_cannot_be_consolidated(self) -> None:
        candidate = self.candidate("event-pending")
        state = self.states.load("subject-1")

        with self.assertRaises(LearningValidationError):
            self.learning.solidify_learning(
                "subject-1",
                candidate.learning_event.learning_id,
                state,
                trait_name="Premature trait",
                trait_description="This must never be consolidated from one event.",
                reason="Attempt premature consolidation.",
                source="test",
                confirmed=True,
                expected_revision=state.revision,
            )

        self.assertEqual(self.learning.list_traits("subject-1"), [])

    def test_consolidation_requires_confirmation_and_evolution(self) -> None:
        validated = self.validated_learning()
        state = self.states.load("subject-1")
        with self.assertRaises(LearningValidationError):
            self.learning.solidify_learning(
                "subject-1",
                validated.learning_event.learning_id,
                state,
                trait_name="Concise expression",
                trait_description="Prefer concise replies.",
                reason="No explicit confirmation was supplied.",
                source="test",
                confirmed=False,
                expected_revision=state.revision,
            )

        consolidated = self.learning.solidify_learning(
            "subject-1",
            validated.learning_event.learning_id,
            state,
            trait_name="Concise expression",
            trait_description="Prefer concise replies when clarity is preserved.",
            reason="The user explicitly confirmed consolidation.",
            source="confirmed_learning_review",
            confirmed=True,
            expected_revision=state.revision,
        )

        unchanged = self.states.load("subject-1")
        self.assertEqual(unchanged.revision, 0)
        self.assertEqual(unchanged.identity.expression_preferences, [])
        self.assertIsNotNone(consolidated.event)
        applied = self.states.apply_event(
            "subject-1",
            consolidated.event,
            expected_revision=0,
        )
        self.assertEqual(applied.state.revision, 1)
        self.assertEqual(
            applied.state.identity.expression_preferences,
            ["prefers concise responses"],
        )
        self.assertEqual(
            consolidated.record.state_event_id,
            applied.update.event.event_id,
        )

    def test_wrong_learning_can_be_rolled_back_through_evolution(self) -> None:
        consolidated = self.consolidated_learning()
        first_update = self.states.apply_event(
            "subject-1",
            consolidated.event,
            expected_revision=0,
        )

        rollback = self.learning.rollback_learning(
            "subject-1",
            consolidated.learning_event.learning_id,
            consolidated.trait.trait_id,
            first_update.state,
            reason="Later review showed that the generalization was incorrect.",
            source="confirmed_learning_review",
            confirmed=True,
            expected_revision=1,
        )

        still_present = self.states.load("subject-1")
        self.assertEqual(
            still_present.identity.expression_preferences,
            ["prefers concise responses"],
        )
        rolled_back = self.states.apply_event(
            "subject-1",
            rollback.event,
            expected_revision=1,
        )
        self.assertEqual(rolled_back.state.identity.expression_preferences, [])
        self.assertFalse(rollback.trait.active)
        self.assertEqual(
            rollback.learning_event.validation_status,
            LearningValidationStatus.REVOKED,
        )
        self.assertEqual(rollback.record.record_type, LearningRecordType.ROLLED_BACK)

    def test_learning_history_preserves_experience_reason_and_diff(self) -> None:
        consolidated = self.consolidated_learning()
        history = self.learning.get_history(
            "subject-1", consolidated.learning_event.learning_id
        )

        self.assertEqual(
            [item.record_type for item in history],
            [
                LearningRecordType.CANDIDATE_CREATED,
                LearningRecordType.VALIDATED,
                LearningRecordType.CONSOLIDATED,
            ],
        )
        origin = history[0]
        self.assertEqual(origin.original_experience["event_id"], "event-1")
        self.assertIn("Concise responses", origin.observation)
        self.assertIn("preference", origin.hypothesis)
        consolidated_record = history[-1]
        self.assertEqual(consolidated_record.before_value, [])
        self.assertEqual(
            consolidated_record.after_value,
            ["prefers concise responses"],
        )
        self.assertTrue(consolidated_record.permanently_consolidated)
        self.assertEqual(consolidated_record.trait_id, consolidated.trait.trait_id)

    def test_learning_state_recovers_after_restart(self) -> None:
        consolidated = self.consolidated_learning()

        restarted = LearningService(
            JsonLearningRepository(self.directory),
            clock=lambda: self.now,
        )
        restored_event = restarted.get_learning_event(
            "subject-1", consolidated.learning_event.learning_id
        )
        restored_trait = restarted.get_trait(
            "subject-1", consolidated.trait.trait_id
        )
        restored_history = restarted.get_history(
            "subject-1", consolidated.learning_event.learning_id
        )

        self.assertEqual(restored_event.to_dict(), consolidated.learning_event.to_dict())
        self.assertEqual(restored_trait.to_dict(), consolidated.trait.to_dict())
        self.assertEqual(len(restored_history), 3)

    def test_context_extracts_only_explicit_structured_learning_evidence(self) -> None:
        state = self.states.load("subject-1")
        ordinary = Event.create(
            event_id="ordinary-event",
            occurred_at=self.now,
            source="user",
            event_type="interaction",
            content="An ordinary interaction is not behavior-analysis evidence.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Record an interaction without inferring personality.",
        )
        explicit = Event.create(
            event_id="explicit-learning-event",
            occurred_at=self.now,
            source="explicit_evaluation",
            event_type="learning_evidence",
            content="An explicit evaluation supplied structured learning evidence.",
            impact_scope=[StateSection.IDENTITY],
            mutations=[],
            reason="Make reviewed evidence available to LearningService.",
            metadata={
                "learning_observation": "A concise format preserved clarity.",
                "learning_hypothesis": "Concise expression may be a durable preference.",
                "learning_field_path": "identity.expression_preferences",
                "learning_value": "prefers concise responses",
                "learning_confidence": 0.55,
                "learning_reason": "The evidence was explicitly annotated.",
            },
        )
        perception = PerceptionResult(
            perception_id="perception-1",
            subject_id="subject-1",
            source_revision=0,
            wake_session_id="wake-1",
            wake_context_id="wake-context-1",
            perceived_at=self.now,
            current_focus=CurrentFocus([], [], "No current focus."),
            temporal_perception=TemporalPerception(
                TemporalMeaning.UNKNOWN,
                InteractionFrequencyTrend.UNKNOWN,
                False,
                [],
                "No temporal learning signal.",
            ),
            relationship_perception=RelationshipPerception(
                RelationshipDirection.UNCLEAR,
                False,
                [],
                False,
                [],
                "No relationship learning signal.",
            ),
            memory_influence=MemoryInfluence([], "No memory influence."),
            observation=Observation(StateStability.STABLE, False, False, [], []),
            internal_drives=[],
            summary="The current state is stable.",
            memory_request_id="memory-request-1",
        )
        thinking = ThinkingResult.create(
            provider_id="deterministic-test-provider",
            result_summary="No direct state mutation is proposed.",
            rationale_summary="Learning remains a separate candidate process.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=True,
            suggest_future_user_contact=False,
            token_budget=TokenBudget(100, 100, 10, ThinkingDepth.LOW),
        )
        context = LearningContext.create(
            context_id="learning-context-1",
            subject_state=state,
            recent_events=[ordinary, explicit],
            memory_influences=[],
            perception_result=perception,
            thinking_result=thinking,
            created_at=self.now,
        )

        result = self.learning.extract_candidates(context)
        restored_context = LearningContext.from_dict(context.to_dict())

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].source_event_id, "explicit-learning-event")
        self.assertEqual(restored_context.to_dict(), context.to_dict())
        self.assertEqual(self.states.load("subject-1").revision, 0)


if __name__ == "__main__":
    unittest.main()
