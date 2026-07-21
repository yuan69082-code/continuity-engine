import tempfile
import unittest
from datetime import datetime, timezone

from continuity_engine.domain.events import Event, StateSection
from continuity_engine.domain.learning import LearningContext
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
from continuity_engine.domain.resources import (
    ResourceRequest,
    ResourceSessionType,
    RuntimeMode,
)
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    ThinkingResult,
    TokenBudget,
    TokenBudgetRequest,
)
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.resource_aware_wake_scheduler import (
    ResourceAwareWakeScheduler,
)
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


class EmptyMemoryRetriever:
    def retrieve(self, request):
        return []


class DiscardingInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class BudgetAwareThinkingProvider:
    provider_id = "deterministic-resource-test-provider"

    def __init__(self) -> None:
        self.calls = 0

    def think(self, perception, budget):
        self.calls += 1
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary="The resource-bounded thought completed.",
            rationale_summary="The provider used only the approved depth and budget.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=True,
            suggest_future_user_contact=False,
            token_budget=budget,
        )


class TokenAndResourceManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = temporary.name
        self.resources = ResourceManager(
            JsonResourceRepository(self.directory),
            clock=lambda: self.now,
        )

    def create_resources(
        self,
        subject_id="subject-1",
        *,
        tokens=10_000,
        compute=10,
        mode=RuntimeMode.LOW_FREQUENCY,
    ):
        return self.resources.create_resource_state(
            subject_id,
            token_budget=tokens,
            compute_budget=compute,
            current_mode=mode,
            resource_id=f"resources-{subject_id}",
        )

    def perception(self, subject_id="subject-1", revision=0):
        return PerceptionResult(
            perception_id=f"perception-{subject_id}",
            subject_id=subject_id,
            source_revision=revision,
            wake_session_id=f"wake-{subject_id}",
            wake_context_id=f"wake-context-{subject_id}",
            perceived_at=self.now,
            current_focus=CurrentFocus([], [], "No current focus."),
            temporal_perception=TemporalPerception(
                TemporalMeaning.UNKNOWN,
                InteractionFrequencyTrend.UNKNOWN,
                False,
                [],
                "No temporal pressure.",
            ),
            relationship_perception=RelationshipPerception(
                RelationshipDirection.UNCLEAR,
                False,
                [],
                False,
                [],
                "No relationship pressure.",
            ),
            memory_influence=MemoryInfluence([], "No memory influence."),
            observation=Observation(StateStability.STABLE, False, False, [], []),
            internal_drives=[],
            summary="The state is stable.",
            memory_request_id=f"memory-request-{subject_id}",
        )

    def thinking_result(self):
        return ThinkingResult.create(
            provider_id="context-provider",
            result_summary="No direct update is proposed.",
            rationale_summary="Learning remains resource gated.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=True,
            suggest_future_user_contact=False,
            token_budget=TokenBudget(100, 100, 10, ThinkingDepth.LOW),
        )

    def test_create_resource_state(self) -> None:
        created = self.create_resources(
            tokens=5_000,
            compute=12,
            mode=RuntimeMode.SCHEDULED,
        )
        restored = self.resources.get_resource_state("subject-1")

        self.assertEqual(created.to_dict(), restored.to_dict())
        self.assertEqual(restored.token_used, 0)
        self.assertEqual(restored.token_remaining, 5_000)
        self.assertEqual(restored.compute_remaining, 12)
        self.assertEqual(restored.current_mode, RuntimeMode.SCHEDULED)

    def test_token_budget_calculation_usage_and_actual_reconciliation(self) -> None:
        self.create_resources(tokens=2_000, compute=5)

        allocation = self.resources.request_memory(
            "subject-1",
            "memory-session-1",
            reason="Estimate a bounded memory operation.",
            estimated_tokens=128,
            estimated_compute=1,
        )
        estimated_state = self.resources.get_resource_state("subject-1")
        actual = self.resources.record_actual_usage(
            "subject-1", "memory-session-1", 64
        )
        reconciled = self.resources.get_resource_state("subject-1")

        self.assertTrue(allocation.decision.allowed)
        self.assertEqual(estimated_state.token_used, 128)
        self.assertEqual(estimated_state.token_remaining, 1_872)
        self.assertIsNone(allocation.usage.actual_tokens)
        self.assertEqual(actual.actual_tokens, 64)
        self.assertEqual(reconciled.token_used, 64)
        self.assertEqual(reconciled.token_remaining, 1_936)
        self.assertEqual(len(self.resources.get_usage_history("subject-1")), 1)

    def test_over_budget_request_is_deferred_without_consumption(self) -> None:
        initial = self.create_resources(tokens=1_000, compute=2)
        request = ResourceRequest.create(
            subject_id="subject-1",
            session_id="expensive-session",
            session_type=ResourceSessionType.OTHER,
            estimated_tokens=950,
            estimated_compute=2,
            model_name="not-applicable",
            reason="Attempt a high-cost bounded task.",
            requested_at=self.now,
        )

        allocation = self.resources.request_resources(request)
        restored = self.resources.get_resource_state("subject-1")

        self.assertFalse(allocation.decision.allowed)
        self.assertTrue(allocation.decision.defer)
        self.assertTrue(allocation.decision.lower_frequency)
        self.assertIsNone(allocation.usage)
        self.assertEqual(restored.to_dict(), initial.to_dict())
        self.assertEqual(self.resources.get_usage_history("subject-1"), [])
        self.assertEqual(len(self.resources.get_decision_history("subject-1")), 1)

    def test_runtime_modes_switch_and_cap_thinking_depth(self) -> None:
        self.create_resources(mode=RuntimeMode.LOW_FREQUENCY)

        def preview(session_id):
            return self.resources.preview(
                ResourceRequest.create(
                    subject_id="subject-1",
                    session_id=session_id,
                    session_type=ResourceSessionType.THINKING,
                    estimated_tokens=4_096,
                    estimated_compute=4,
                    model_name="future-model",
                    reason="Preview a deep thinking request.",
                    requested_at=self.now,
                    requested_depth=ThinkingDepth.DEEP,
                )
            )

        self.assertEqual(preview("low").approved_depth, ThinkingDepth.LOW)
        scheduled = self.resources.set_runtime_mode(
            "subject-1", RuntimeMode.SCHEDULED, expected_revision=0
        )
        self.assertEqual(preview("scheduled").approved_depth, ThinkingDepth.NORMAL)
        continuous = self.resources.set_runtime_mode(
            "subject-1", RuntimeMode.CONTINUOUS, expected_revision=scheduled.revision
        )
        self.assertEqual(preview("continuous").approved_depth, ThinkingDepth.NORMAL)
        deep = self.resources.set_runtime_mode(
            "subject-1", RuntimeMode.DEEP_THINKING, expected_revision=continuous.revision
        )
        self.assertEqual(preview("deep").approved_depth, ThinkingDepth.DEEP)
        self.assertEqual(deep.revision, 3)

    def test_thinking_uses_resource_manager_and_accepts_depth_downgrade(self) -> None:
        self.create_resources(tokens=1_000, compute=5, mode=RuntimeMode.LOW_FREQUENCY)
        states = SubjectStateService(
            JsonSubjectStateRepository(self.directory), clock=lambda: self.now
        )
        states.create("subject-1")
        provider = BudgetAwareThinkingProvider()
        thinking = ThinkingService(
            provider,
            self.resources,
            states,
            JsonThinkingRepository(self.directory),
            clock=lambda: self.now,
        )

        execution = thinking.handle_perception(
            self.perception(), depth=ThinkingDepth.NORMAL
        )
        usage = self.resources.get_usage_history("subject-1")

        self.assertEqual(provider.calls, 1)
        self.assertEqual(execution.session.token_budget.depth, ThinkingDepth.LOW)
        self.assertEqual(execution.session.token_budget.session_tokens, 256)
        self.assertEqual(usage[0].session_id, execution.session.think_id)
        self.assertEqual(usage[0].session_type, ResourceSessionType.THINKING)
        self.assertEqual(usage[0].model_name, provider.provider_id)

    def test_low_remaining_resources_downgrade_normal_to_low(self) -> None:
        self.create_resources(
            tokens=1_000,
            compute=5,
            mode=RuntimeMode.DEEP_THINKING,
        )
        self.resources.request_resources(
            ResourceRequest.create(
                subject_id="subject-1",
                session_id="prior-work",
                session_type=ResourceSessionType.OTHER,
                estimated_tokens=600,
                estimated_compute=2,
                model_name="not-applicable",
                reason="Consume part of the current resource window.",
                requested_at=self.now,
            )
        )

        allocation = self.resources.request_thinking(
            "subject-1",
            "constrained-thinking",
            depth=ThinkingDepth.NORMAL,
            model_name="future-model",
            reason="Attempt normal thinking with constrained resources.",
        )

        self.assertTrue(allocation.decision.allowed)
        self.assertEqual(allocation.decision.approved_depth, ThinkingDepth.LOW)
        self.assertEqual(allocation.decision.allocated_tokens, 256)

    def test_thinking_waits_when_low_depth_cannot_be_afforded(self) -> None:
        self.create_resources(tokens=200, compute=1, mode=RuntimeMode.DEEP_THINKING)
        states = SubjectStateService(
            JsonSubjectStateRepository(self.directory), clock=lambda: self.now
        )
        states.create("subject-1")
        provider = BudgetAwareThinkingProvider()
        thinking = ThinkingService(
            provider,
            self.resources,
            states,
            JsonThinkingRepository(self.directory),
            clock=lambda: self.now,
        )

        execution = thinking.handle_perception(
            self.perception(), depth=ThinkingDepth.DEEP
        )

        self.assertEqual(provider.calls, 0)
        self.assertTrue(execution.session.completed_successfully)
        self.assertTrue(execution.session.result.should_wait)
        self.assertEqual(execution.session.token_budget.session_tokens, 0)
        self.assertEqual(self.resources.get_usage_history("subject-1"), [])
        self.assertTrue(self.resources.get_decision_history("subject-1")[0].defer)

    def test_learning_is_deferred_before_candidate_extraction(self) -> None:
        self.create_resources(tokens=100, compute=1)
        state = SubjectState.create("subject-1", self.now)
        explicit = Event.create(
            event_id="learning-source",
            occurred_at=self.now,
            source="explicit_evaluation",
            event_type="learning_evidence",
            content="Structured learning evidence was supplied.",
            impact_scope=[StateSection.IDENTITY],
            mutations=[],
            reason="Provide reviewed learning evidence.",
            metadata={
                "learning_observation": "A concise response preserved clarity.",
                "learning_hypothesis": "Concise expression may be durable.",
                "learning_field_path": "identity.expression_preferences",
                "learning_value": "prefers concise responses",
                "learning_confidence": 0.6,
            },
        )
        context = LearningContext.create(
            context_id="learning-context-resource-check",
            subject_state=state,
            recent_events=[explicit],
            memory_influences=[],
            perception_result=self.perception(),
            thinking_result=self.thinking_result(),
            created_at=self.now,
        )
        learning = LearningService(
            JsonLearningRepository(self.directory),
            resource_manager=self.resources,
            clock=lambda: self.now,
        )

        result = learning.extract_candidates(context)

        self.assertTrue(result.deferred)
        self.assertEqual(result.candidates, [])
        self.assertEqual(learning.list_learning_events("subject-1"), [])
        self.assertEqual(self.resources.get_usage_history("subject-1"), [])

    def test_wake_scheduler_checks_resources_before_starting(self) -> None:
        states = SubjectStateService(
            JsonSubjectStateRepository(self.directory), clock=lambda: self.now
        )
        states.create("wake-blocked")
        states.create("wake-allowed")
        memory = MemoryService(
            EmptyMemoryRetriever(),
            DiscardingInfluenceRecorder(),
            clock=lambda: self.now,
        )
        awakening = AwakeningService(
            states,
            memory,
            JsonAwakeningRepository(self.directory),
            clock=lambda: self.now,
        )
        blocked_cycle = awakening.create_manual_cycle("wake-blocked")
        allowed_cycle = awakening.create_manual_cycle("wake-allowed")
        self.create_resources("wake-blocked", tokens=0, compute=0)
        self.create_resources("wake-allowed", tokens=1_000, compute=5)
        scheduler = ResourceAwareWakeScheduler(
            awakening, self.resources, clock=lambda: self.now
        )

        blocked = scheduler.wake_manual(blocked_cycle.cycle_id, detail="Try wake.")
        allowed = scheduler.wake_manual(allowed_cycle.cycle_id, detail="Run wake.")

        self.assertTrue(blocked.deferred)
        self.assertIsNone(blocked.awakening)
        self.assertEqual(awakening.get_sessions("wake-blocked"), [])
        self.assertFalse(allowed.deferred)
        self.assertIsNotNone(allowed.awakening)
        self.assertEqual(
            allowed.resources.usage.session_id,
            allowed.awakening.session.session_id,
        )
        self.assertEqual(len(awakening.get_sessions("wake-allowed")), 1)

    def test_resource_state_and_history_survive_restart(self) -> None:
        self.create_resources(tokens=2_000, compute=5, mode=RuntimeMode.SCHEDULED)
        self.resources.request_memory(
            "subject-1",
            "restart-memory-session",
            reason="Persist estimated memory resource use.",
        )
        before = self.resources.set_runtime_mode(
            "subject-1", RuntimeMode.DEEP_THINKING, expected_revision=1
        )

        restarted = ResourceManager(
            JsonResourceRepository(self.directory), clock=lambda: self.now
        )

        self.assertEqual(restarted.get_resource_state("subject-1").to_dict(), before.to_dict())
        self.assertEqual(len(restarted.get_usage_history("subject-1")), 1)
        self.assertEqual(len(restarted.get_decision_history("subject-1")), 1)
        self.assertEqual(
            restarted.get_usage_history("subject-1")[0].session_type,
            ResourceSessionType.MEMORY,
        )


if __name__ == "__main__":
    unittest.main()
