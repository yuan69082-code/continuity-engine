import tempfile
import unittest
from datetime import datetime, timezone

from continuity_engine.domain.action import (
    ActionContext,
    PerceptionActionSummary,
    ResourceLimits,
)
from continuity_engine.domain.memory import MemoryCandidate
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
from continuity_engine.domain.resources import ResourceSessionType, RuntimeMode
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    ThinkingResult,
    TokenBudget,
)
from continuity_engine.interfaces import (
    APIBackedSkillAdapter,
    APIService,
    ActionPlanAPIRequest,
    ContinuityMCPAdapter,
    InterfaceAccessGuard,
    InterfaceCapability,
    MemoryAPIRequest,
    PerceptionAPIRequest,
    SkillAdapter,
    SubjectStateAPIRequest,
    ThinkingAPIRequest,
    WakeAPIRequest,
)
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_awakening_repository import (
    JsonAwakeningRepository,
)
from continuity_engine.storage.json_permission_repository import (
    JsonPermissionRepository,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


class TrackingMemoryRetriever:
    def __init__(self, now):
        self.now = now
        self.requests = []

    def retrieve(self, request):
        self.requests.append(request)
        return [
            MemoryCandidate(
                memory_id="memory-1",
                subject_id=request.subject_id,
                content="A relevant continuity memory.",
                source="interface-test",
                occurred_at=self.now,
                provider_relevance=0.9,
            )
        ]


class DiscardingInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class StaticPerceptionProvider:
    def __init__(self, perception):
        self.perception = perception
        self.calls = 0

    def get_current_perception(self, subject_id):
        self.calls += 1
        return PerceptionResult.from_dict(self.perception.to_dict())


class RepositoryActionSessionProvider:
    def __init__(self, repository):
        self.repository = repository

    def get_latest_action_session(self, subject_id):
        sessions = self.repository.list_action_sessions(subject_id, limit=1)
        return sessions[0] if sessions else None


class DeterministicThinkingProvider:
    provider_id = "interface-test-provider"

    def __init__(self):
        self.calls = 0

    def think(self, perception, budget):
        self.calls += 1
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary="The current perception remains stable.",
            rationale_summary="A deterministic interface test completed.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=True,
            suggest_future_user_contact=False,
            token_budget=budget,
        )


class InterfaceLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 26, 9, 0, tzinfo=timezone.utc)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = temporary.name
        self.subject_id = "subject-interface"

        self.subject_states = SubjectStateService(
            JsonSubjectStateRepository(self.directory),
            clock=lambda: self.now,
        )
        self.subject_states.create(self.subject_id)

        self.permissions = PermissionService(
            JsonPermissionRepository(self.directory),
            clock=lambda: self.now,
        )
        self.resources = ResourceManager(
            JsonResourceRepository(self.directory),
            clock=lambda: self.now,
        )
        self.resources.create_resource_state(
            self.subject_id,
            token_budget=50_000,
            compute_budget=100,
            current_mode=RuntimeMode.DEEP_THINKING,
            resource_id="resources-interface",
        )

        self.memory_retriever = TrackingMemoryRetriever(self.now)
        self.memory = MemoryService(
            self.memory_retriever,
            DiscardingInfluenceRecorder(),
            clock=lambda: self.now,
        )
        self.perceptions = StaticPerceptionProvider(self._perception())
        self.thinking_provider = DeterministicThinkingProvider()
        self.thinking = ThinkingService(
            self.thinking_provider,
            self.resources,
            self.subject_states,
            JsonThinkingRepository(self.directory),
            clock=lambda: self.now,
        )
        self.actions = InMemoryActionRepository()
        self.awakening = AwakeningService(
            self.subject_states,
            self.memory,
            JsonAwakeningRepository(self.directory),
            clock=lambda: self.now,
        )
        self.manual_cycle = self.awakening.create_manual_cycle(self.subject_id)
        self.api = APIService(
            subject_states=self.subject_states,
            memory=self.memory,
            perceptions=self.perceptions,
            thinking=self.thinking,
            actions=RepositoryActionSessionProvider(self.actions),
            awakening=self.awakening,
            access_guard=InterfaceAccessGuard(
                self.permissions,
                self.resources,
                clock=lambda: self.now,
            ),
            clock=lambda: self.now,
        )

    def _perception(self):
        return PerceptionResult(
            perception_id="perception-interface",
            subject_id=self.subject_id,
            source_revision=0,
            wake_session_id="wake-interface",
            wake_context_id="wake-context-interface",
            perceived_at=self.now,
            current_focus=CurrentFocus([], [], "No urgent focus."),
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
            memory_influence=MemoryInfluence([], "No current memory influence."),
            observation=Observation(StateStability.STABLE, False, False, [], []),
            internal_drives=[],
            summary="The current state is stable.",
            memory_request_id="memory-request-interface",
        )

    def grant(self, *capabilities):
        return self.permissions.create_permission(
            self.subject_id,
            permission_id=f"permission-{len(self.permissions.list_permissions(self.subject_id))}",
            permission_type="interface_access",
            name="Continuity interface access",
            description="Allows selected interface operations.",
            scope=["*"],
            capabilities=[
                item.value if isinstance(item, InterfaceCapability) else item
                for item in capabilities
            ],
            source="test-user",
            reason="The test grants this bounded interface capability.",
        )

    def test_api_get_subject_state_returns_unified_response(self) -> None:
        self.grant(InterfaceCapability.READ_SUBJECT_STATE)
        response = self.api.get_subject_state(
            SubjectStateAPIRequest(
                request_id="request-state",
                subject_id=self.subject_id,
            )
        )

        self.assertTrue(response.successful)
        self.assertEqual(response.current_revision, 0)
        self.assertEqual(response.result["revision"], 0)
        self.assertEqual(
            set(response.to_dict()),
            {
                "request_id",
                "subject_id",
                "timestamp",
                "current_revision",
                "result",
                "error",
            },
        )

    def test_external_request_cannot_bypass_permission_context(self) -> None:
        response = self.api.get_subject_state(
            SubjectStateAPIRequest(
                request_id="request-denied",
                subject_id=self.subject_id,
            )
        )

        self.assertFalse(response.successful)
        self.assertEqual(response.error.code, "PERMISSION_DENIED")
        self.assertEqual(self.resources.get_usage_history(self.subject_id), [])

    def test_api_returns_snapshot_and_has_no_direct_state_write_endpoint(self) -> None:
        self.grant(InterfaceCapability.READ_SUBJECT_STATE)
        response = self.api.get_subject_state(
            SubjectStateAPIRequest(
                request_id="request-snapshot",
                subject_id=self.subject_id,
            )
        )
        response.result["subject_state"]["identity"]["stable_traits"].append(
            "external mutation"
        )

        restored = self.subject_states.load(self.subject_id)
        self.assertEqual(restored.identity.stable_traits, [])
        self.assertEqual(restored.revision, 0)
        for method in ("save_subject_state", "update_subject_state", "apply_event"):
            self.assertFalse(hasattr(self.api, method))

    def test_resource_manager_participates_in_external_calls(self) -> None:
        self.grant(InterfaceCapability.QUERY_MEMORY)
        response = self.api.query_memory(
            MemoryAPIRequest(
                request_id="request-memory",
                subject_id=self.subject_id,
                query="What remains relevant?",
            )
        )

        self.assertTrue(response.successful)
        usage = self.resources.get_usage_history(self.subject_id)
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].session_id, "request-memory")
        self.assertEqual(usage[0].session_type, ResourceSessionType.MEMORY)
        self.assertEqual(len(self.memory_retriever.requests), 1)

    def test_perception_and_thinking_are_available_through_api(self) -> None:
        self.grant(
            InterfaceCapability.READ_PERCEPTION,
            InterfaceCapability.REQUEST_THINKING,
        )
        perception = self.api.get_perception(
            PerceptionAPIRequest(
                request_id="request-perception",
                subject_id=self.subject_id,
            )
        )
        thinking = self.api.request_thinking(
            ThinkingAPIRequest(
                request_id="request-thinking",
                subject_id=self.subject_id,
                depth=ThinkingDepth.LOW,
            )
        )

        self.assertTrue(perception.successful)
        self.assertTrue(thinking.successful)
        self.assertEqual(self.thinking_provider.calls, 1)
        self.assertIsNone(thinking.result["state_update"])
        self.assertEqual(self.subject_states.load(self.subject_id).revision, 0)

    def test_action_query_is_read_only_and_explicit_when_no_plan_exists(self) -> None:
        self.grant(InterfaceCapability.READ_ACTION_PLAN)
        response = self.api.get_action_plan(
            ActionPlanAPIRequest(
                request_id="request-action",
                subject_id=self.subject_id,
            )
        )

        self.assertFalse(response.successful)
        self.assertEqual(response.error.code, "ACTION_PLAN_NOT_FOUND")
        self.assertEqual(self.subject_states.load(self.subject_id).revision, 0)

    def test_api_returns_latest_audited_action_decision_and_plan(self) -> None:
        thought = ThinkingResult.create(
            provider_id="action-interface-test",
            result_summary="No action is currently needed.",
            rationale_summary="The current perception is stable.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=TokenBudget(500, 500, 100, ThinkingDepth.LOW),
        )
        ActionService(
            InMemoryPermissionProvider(),
            self.actions,
        ).decide(
            ActionContext(
                context_id="action-context-interface",
                subject_id=self.subject_id,
                wake_session_id="wake-interface",
                think_session_id="think-interface",
                subject_state_revision=0,
                thinking_result=thought,
                perception_summary=PerceptionActionSummary(
                    perception_id="perception-interface",
                    wake_session_id="wake-interface",
                    source_revision=0,
                    summary="The current state is stable.",
                    current_focus="No urgent focus.",
                    temporal_meaning="No temporal pressure.",
                    relationship_meaning="No relationship pressure.",
                    memory_influence="No memory influence.",
                    observation_notes=[],
                    internal_drives=[],
                ),
                current_time=self.now,
                available_permissions=[],
                resource_limits=ResourceLimits(),
            )
        )
        self.grant(InterfaceCapability.READ_ACTION_PLAN)

        response = self.api.get_action_plan(
            ActionPlanAPIRequest(
                request_id="request-action-success",
                subject_id=self.subject_id,
            )
        )

        self.assertTrue(response.successful)
        self.assertEqual(response.result["decision"]["selected_action"]["action_type"], "NO_ACTION")
        self.assertEqual(response.result["plan"]["status"], "PLANNED")
        self.assertEqual(self.subject_states.load(self.subject_id).revision, 0)

    def test_manual_wake_requires_confirmation_and_remains_read_only(self) -> None:
        self.grant(InterfaceCapability.TRIGGER_WAKE)
        denied = self.api.trigger_manual_wake(
            WakeAPIRequest(
                request_id="request-wake-unconfirmed",
                subject_id=self.subject_id,
                cycle_id=self.manual_cycle.cycle_id,
                detail="External manual wake request.",
            )
        )
        allowed = self.api.trigger_manual_wake(
            WakeAPIRequest(
                request_id="request-wake-confirmed",
                subject_id=self.subject_id,
                cycle_id=self.manual_cycle.cycle_id,
                detail="External manual wake request.",
                confirmed=True,
            )
        )

        self.assertEqual(denied.error.code, "CONFIRMATION_REQUIRED")
        self.assertTrue(allowed.successful)
        self.assertEqual(
            allowed.result["wake_session"]["session_id"],
            "request-wake-confirmed",
        )
        self.assertEqual(self.subject_states.load(self.subject_id).revision, 0)

    def test_mcp_adapter_exposes_only_declared_tool_facade(self) -> None:
        adapter = ContinuityMCPAdapter(self.api)

        self.assertEqual(
            set(adapter.TOOL_NAMES),
            {
                "get_subject_state",
                "query_memory",
                "get_perception",
                "request_thinking",
                "get_action_plan",
            },
        )
        response = adapter.get_subject_state(
            SubjectStateAPIRequest(
                request_id="request-mcp-denied",
                subject_id=self.subject_id,
            )
        )
        self.assertEqual(response.error.code, "PERMISSION_DENIED")
        self.assertFalse(hasattr(adapter, "apply_event"))

    def test_skill_adapter_contract_delegates_to_secured_api(self) -> None:
        adapter = APIBackedSkillAdapter("future-agent-platform", self.api)

        self.assertIsInstance(adapter, SkillAdapter)
        response = adapter.get_subject_state(
            SubjectStateAPIRequest(
                request_id="request-skill-denied",
                subject_id=self.subject_id,
            )
        )
        self.assertEqual(response.error.code, "PERMISSION_DENIED")
        self.assertEqual(adapter.platform_id, "future-agent-platform")


if __name__ == "__main__":
    unittest.main()
