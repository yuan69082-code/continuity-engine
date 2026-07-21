import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.action import (
    ActionContext,
    ActionPlanStatus,
    ActionSession,
    ActionType,
    PermissionGrant,
    PerceptionActionSummary,
    ResourceLimits,
    RiskLevel,
)
from continuity_engine.domain.events import ChangeOperation, StateMutation, StateSection
from continuity_engine.domain.memory import MemoryCandidate
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.thinking import ThinkingDepth, ThinkingResult, TokenBudget
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.services.wake_perception_thinking_action_service import (
    WakePerceptionThinkingActionService,
)
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


class CandidateRetriever:
    def __init__(self, candidates=()) -> None:
        self.candidates = list(candidates)
        self.calls = 0

    def retrieve(self, request):
        self.calls += 1
        return list(self.candidates)


class DiscardingInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class FixedTokenBudgetManager:
    def allocate(self, request):
        return TokenBudget(10_000, 8_000, 1_000, request.depth)

    def record_usage(self, think_id, actual_tokens):
        raise AssertionError("real token accounting is forbidden in this stage")


class StateUpdateThinkingProvider:
    provider_id = "action-test-thinking-provider"

    def __init__(self) -> None:
        self.calls = []

    def think(self, perception, budget):
        self.calls.append(perception)
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary="Stage seven should be recorded as the current focus.",
            rationale_summary="Perception and memory both point to the Action Engine work.",
            generated_new_thought=True,
            update_subject_state=True,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=budget,
            proposed_mutations=[
                StateMutation(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    value="Action Engine",
                    reason="The approved action records the current implementation focus.",
                )
            ],
        )


class ActionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)

    def result(self, **overrides) -> ThinkingResult:
        values = {
            "provider_id": "unit-thinking-provider",
            "result_summary": "The internal review reached a bounded result.",
            "rationale_summary": "The available perception supports this tendency.",
            "generated_new_thought": False,
            "update_subject_state": False,
            "request_more_memory": False,
            "should_wait": False,
            "suggest_future_user_contact": False,
            "token_budget": TokenBudget(1_000, 1_000, 500, ThinkingDepth.LOW),
            "result_id": "thinking-result-1",
        }
        values.update(overrides)
        return ThinkingResult.create(**values)

    def context(
        self,
        result: ThinkingResult,
        *,
        revision: int = 0,
        source_revision: int = 0,
        permissions=(),
        limits: ResourceLimits | None = None,
    ) -> ActionContext:
        return ActionContext(
            context_id="action-context-1",
            subject_id="subject-1",
            wake_session_id="wake-1",
            think_session_id="think-1",
            subject_state_revision=revision,
            thinking_result=result,
            perception_summary=PerceptionActionSummary(
                perception_id="perception-1",
                wake_session_id="wake-1",
                source_revision=source_revision,
                summary="The subject is stable and the current focus is visible.",
                current_focus="Action Engine is the current focus.",
                temporal_meaning="The interaction remains recent.",
                relationship_meaning="The relationship appears stable.",
                memory_influence="A relevant design memory is present.",
                observation_notes=["No conflict is visible."],
                internal_drives=["Continue the current topic."],
            ),
            current_time=self.now,
            available_permissions=list(permissions),
            resource_limits=limits or ResourceLimits(),
        )

    def grant(
        self,
        permission: str,
        *,
        revoked: bool = False,
        requires_confirmation: bool = False,
        expires_at=None,
        scopes=None,
    ) -> PermissionGrant:
        return PermissionGrant(
            permission=permission,
            subject_id="subject-1",
            valid_from=self.now - timedelta(days=1),
            expires_at=expires_at,
            revoked=revoked,
            requires_confirmation=requires_confirmation,
            scopes=list(scopes or ["*"]),
        )

    def decide(self, context, grants=()):
        repository = InMemoryActionRepository()
        service = ActionService(InMemoryPermissionProvider(grants), repository)
        return service.decide(context), repository, service

    def test_no_action_tendency_returns_explicit_no_action(self) -> None:
        output, _, _ = self.decide(self.context(self.result()))

        self.assertEqual(output.decision.selected_action.action_type, ActionType.NO_ACTION)
        self.assertTrue(output.decision.approved)
        self.assertEqual(output.plan.status, ActionPlanStatus.PLANNED)
        self.assertFalse(output.decision.can_execute_automatically)

    def test_update_state_is_only_planned_inside_action_service(self) -> None:
        state = SubjectState.create("subject-1", self.now)
        before = state.to_dict()
        result = self.result(
            update_subject_state=True,
            proposed_mutations=[
                StateMutation(
                    "continuity.current_focus",
                    ChangeOperation.APPEND,
                    "Action Engine",
                    "Record the approved focus.",
                )
            ],
        )
        permission = "subject_state:update"
        output, _, _ = self.decide(
            self.context(result, permissions=[permission]),
            [self.grant(permission)],
        )

        self.assertEqual(output.decision.selected_action.action_type, ActionType.UPDATE_STATE)
        self.assertTrue(output.decision.approved)
        self.assertEqual(output.plan.status, ActionPlanStatus.PLANNED)
        self.assertEqual(output.plan.steps[0].parameters["expected_revision"], 0)
        self.assertEqual(state.to_dict(), before)

    def test_contact_user_without_permission_is_blocked(self) -> None:
        result = self.result(suggest_future_user_contact=True)
        output, _, _ = self.decide(self.context(result))

        self.assertEqual(output.decision.selected_action.action_type, ActionType.CONTACT_USER)
        self.assertFalse(output.decision.approved)
        self.assertEqual(output.plan.status, ActionPlanStatus.BLOCKED)
        self.assertIn("permission", output.decision.rejection_reason.lower())

    def test_revoked_permission_cannot_pass(self) -> None:
        permission = "user:contact"
        result = self.result(suggest_future_user_contact=True)
        output, _, _ = self.decide(
            self.context(result, permissions=[permission]),
            [self.grant(permission, revoked=True)],
        )

        self.assertFalse(output.decision.approved)
        self.assertTrue(output.session.permission_checks[0].revoked)
        self.assertEqual(output.plan.status, ActionPlanStatus.REJECTED)

    def test_expired_and_out_of_scope_permissions_are_rejected(self) -> None:
        permission = "user:contact"
        result = self.result(suggest_future_user_contact=True)
        grants = (
            self.grant(permission, expires_at=self.now - timedelta(seconds=1)),
            self.grant(permission, scopes=["different-target"]),
        )
        for grant, field in ((grants[0], "expired"), (grants[1], "within_scope")):
            with self.subTest(field=field):
                output, _, _ = self.decide(
                    self.context(result, permissions=[permission]),
                    [grant],
                )
                self.assertFalse(output.decision.approved)
                check = output.session.permission_checks[0]
                if field == "expired":
                    self.assertTrue(check.expired)
                else:
                    self.assertFalse(check.within_scope)
                self.assertEqual(output.plan.status, ActionPlanStatus.REJECTED)

    def test_confirmation_required_action_is_never_automatic(self) -> None:
        permission = "user:contact"
        result = self.result(suggest_future_user_contact=True)
        output, _, _ = self.decide(
            self.context(result, permissions=[permission]),
            [self.grant(permission, requires_confirmation=True)],
        )

        self.assertTrue(output.decision.approved)
        self.assertTrue(output.decision.requires_confirmation)
        self.assertFalse(output.decision.can_execute_automatically)
        self.assertTrue(output.plan.requires_user_confirmation)
        self.assertEqual(output.plan.status, ActionPlanStatus.BLOCKED)

    def test_high_and_critical_risk_actions_are_not_automatically_approved(self) -> None:
        for target, expected_risk in (
            ("filesystem-tool", RiskLevel.HIGH),
            ("critical-admin-tool", RiskLevel.CRITICAL),
        ):
            with self.subTest(target=target):
                permission = f"tool:use:{target}"
                result = self.result(suggest_tool_use=True, tool_target=target)
                output, _, _ = self.decide(
                    self.context(result, permissions=[permission]),
                    [self.grant(permission)],
                )
                self.assertEqual(
                    output.decision.evaluated_risks.risk_level,
                    expected_risk,
                )
                self.assertFalse(output.decision.approved)
                self.assertFalse(output.decision.can_execute_automatically)

    def test_request_memory_only_creates_a_plan(self) -> None:
        permission = "memory:request"
        result = self.result(
            request_more_memory=True,
            additional_memory_query="Retrieve the missing design decision.",
        )
        output, _, _ = self.decide(
            self.context(result, permissions=[permission]),
            [self.grant(permission)],
        )

        self.assertEqual(output.decision.selected_action.action_type, ActionType.REQUEST_MEMORY)
        self.assertEqual(
            output.plan.steps[0].parameters["query"],
            "Retrieve the missing design decision.",
        )
        self.assertEqual(output.plan.status, ActionPlanStatus.PLANNED)

    def test_use_tool_only_creates_a_non_executed_plan(self) -> None:
        target = "calendar-preview"
        permission = f"tool:use:{target}"
        result = self.result(suggest_tool_use=True, tool_target=target)
        output, _, _ = self.decide(
            self.context(result, permissions=[permission]),
            [self.grant(permission)],
        )

        self.assertEqual(output.decision.selected_action.action_type, ActionType.USE_TOOL)
        self.assertFalse(output.plan.steps[0].parameters["invoke_tool"])
        self.assertIn(output.plan.status, (ActionPlanStatus.BLOCKED, ActionPlanStatus.REJECTED))

    def test_defer_and_more_thinking_remain_non_executed_plans(self) -> None:
        deferred, _, _ = self.decide(self.context(self.result(should_wait=True)))
        self.assertEqual(deferred.decision.selected_action.action_type, ActionType.DEFER)
        self.assertEqual(deferred.plan.status, ActionPlanStatus.DEFERRED)
        self.assertIn("suggested_reevaluation_at", deferred.plan.steps[0].parameters)

        permission = "thinking:request"
        more_thinking, _, _ = self.decide(
            self.context(
                self.result(request_more_thinking=True),
                permissions=[permission],
            ),
            [self.grant(permission)],
        )
        self.assertEqual(
            more_thinking.decision.selected_action.action_type,
            ActionType.REQUEST_MORE_THINKING,
        )
        self.assertFalse(more_thinking.plan.steps[0].parameters["start_thinking"])

    def test_revision_mismatch_rejects_action(self) -> None:
        output, _, _ = self.decide(
            self.context(self.result(), revision=2, source_revision=1)
        )

        self.assertFalse(output.decision.approved)
        self.assertEqual(output.plan.status, ActionPlanStatus.REJECTED)
        self.assertIn("revision", output.decision.rejection_reason)

    def test_resource_limit_failure_is_audited_and_blocked(self) -> None:
        permission = "memory:request"
        result = self.result(
            request_more_memory=True,
            additional_memory_query="More memory.",
        )
        limits = ResourceLimits(maximum_estimated_cost=1.0)
        output, _, _ = self.decide(
            self.context(result, permissions=[permission], limits=limits),
            [self.grant(permission)],
        )

        self.assertFalse(output.decision.approved)
        self.assertFalse(output.decision.evaluated_resources.within_limits)
        self.assertEqual(output.plan.status, ActionPlanStatus.BLOCKED)

    def test_action_session_is_deterministic_serializable_and_traceable(self) -> None:
        context = self.context(self.result())
        output, repository, service = self.decide(context)
        repeated = service.decide(context)
        restored = repository.load_action_session(
            "subject-1", output.session.action_session_id
        )

        self.assertEqual(output.session.to_dict(), repeated.session.to_dict())
        self.assertEqual(restored.to_dict(), output.session.to_dict())
        self.assertEqual(
            ActionSession.from_dict(output.session.to_dict()).to_dict(),
            output.session.to_dict(),
        )
        self.assertEqual(output.session.wake_session_id, "wake-1")
        self.assertEqual(output.session.think_session_id, "think-1")

    def test_full_wake_perception_thinking_action_evolution_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: self.now,
            )
            states.create("subject-1")
            retriever = CandidateRetriever(
                [
                    MemoryCandidate(
                        memory_id="action-memory",
                        subject_id="subject-1",
                        content="The Action Engine is the next planned stage.",
                        source="test-memory",
                        occurred_at=self.now - timedelta(days=1),
                        provider_relevance=0.95,
                        related_scope=[StateSection.CONTINUITY],
                    )
                ]
            )
            memory = MemoryService(
                retriever,
                DiscardingInfluenceRecorder(),
                clock=lambda: self.now,
            )
            awakening = AwakeningService(
                states,
                memory,
                JsonAwakeningRepository(directory),
                clock=lambda: self.now,
            )
            provider = StateUpdateThinkingProvider()
            thinking = ThinkingService(
                provider,
                FixedTokenBudgetManager(),
                states,
                JsonThinkingRepository(directory),
                clock=lambda: self.now,
            )
            permission = "subject_state:update"
            action_repository = InMemoryActionRepository()
            action = ActionService(
                InMemoryPermissionProvider([self.grant(permission)]),
                action_repository,
            )
            flow = WakePerceptionThinkingActionService(
                awakening,
                PerceptionService(),
                thinking,
                action,
                states,
                available_permissions=[permission],
                clock=lambda: self.now,
            )
            cycle = awakening.create_manual_cycle("subject-1")

            result = flow.wake_manual(
                cycle.cycle_id,
                detail="Run the stage-seven decision flow.",
            )

            self.assertIsNotNone(result.thinking_result)
            self.assertEqual(result.action_decision.selected_action.action_type, ActionType.UPDATE_STATE)
            self.assertTrue(result.action_decision.approved)
            self.assertEqual(result.action_plan.status, ActionPlanStatus.PLANNED)
            self.assertIsNotNone(result.state_update)
            self.assertEqual(states.load("subject-1").revision, 1)
            self.assertEqual(
                states.load("subject-1").continuity.current_focus,
                ["Action Engine"],
            )
            self.assertEqual(
                result.state_update.event.metadata["action_session_id"],
                result.action.session.action_session_id,
            )
            self.assertTrue(result.thinking.session.state_written_back)
            self.assertEqual(result.thinking.state_update, result.state_update)
            stored = action_repository.load_action_session(
                "subject-1", result.action.session.action_session_id
            )
            self.assertEqual(stored.wake_session_id, result.awakening.session.session_id)
            self.assertEqual(stored.think_session_id, result.thinking.session.think_id)
            self.assertEqual(retriever.calls, 1)


if __name__ == "__main__":
    unittest.main()
