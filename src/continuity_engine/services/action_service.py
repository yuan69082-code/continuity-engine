from __future__ import annotations

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from continuity_engine.domain.action import (
    ActionContext,
    ActionDecision,
    ActionExecutionResult,
    ActionIntent,
    ActionPlan,
    ActionPlanStatus,
    ActionSession,
    ActionStep,
    ActionType,
    FailurePolicy,
    PermissionCheck,
    RiskLevel,
)
from continuity_engine.storage.base import ActionRepository

from .action_evaluators import ResourceEvaluator, RiskEvaluator
from .action_ports import PermissionProvider


_ACTION_PRIORITY = {
    ActionType.UPDATE_STATE: 0,
    ActionType.REQUEST_MEMORY: 1,
    ActionType.REQUEST_MORE_THINKING: 2,
    ActionType.CONTACT_USER: 3,
    ActionType.USE_TOOL: 4,
    ActionType.DEFER: 5,
    ActionType.NO_ACTION: 6,
}


class ActionService:
    """Create deterministic, auditable action decisions without executing them."""

    def __init__(
        self,
        permissions: PermissionProvider,
        repository: ActionRepository,
        *,
        risk_evaluator: RiskEvaluator | None = None,
        resource_evaluator: ResourceEvaluator | None = None,
    ) -> None:
        self._permissions = permissions
        self._repository = repository
        self._risk_evaluator = risk_evaluator or RiskEvaluator()
        self._resource_evaluator = resource_evaluator or ResourceEvaluator()

    def decide(self, context: ActionContext) -> ActionExecutionResult:
        intents = self._extract_intents(context)
        selected = min(intents, key=lambda item: _ACTION_PRIORITY[item.action_type])
        permission_checks = self._check_permissions(context, selected)
        risk = self._risk_evaluator.evaluate(selected, permission_checks)
        resources = self._resource_evaluator.evaluate(
            selected,
            context.resource_limits,
        )
        revision_matches = (
            context.subject_state_revision
            == context.perception_summary.source_revision
        )
        invalid_permissions = [item for item in permission_checks if not item.valid]
        requires_confirmation = (
            any(item.requires_confirmation for item in permission_checks)
            or selected.action_type is ActionType.CONTACT_USER
            or risk.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        )

        rejection_reason: str | None = None
        approved = True
        if not revision_matches:
            approved = False
            rejection_reason = (
                "The current SubjectState revision does not match the perception source revision."
            )
        elif invalid_permissions:
            approved = False
            rejection_reason = " ".join(item.reason for item in invalid_permissions)
        elif not resources.within_limits:
            approved = False
            rejection_reason = "The action exceeds the current resource limits."
        elif risk.risk_level is RiskLevel.CRITICAL:
            approved = False
            rejection_reason = "Critical-risk actions cannot be approved automatically."
        elif risk.risk_level is RiskLevel.HIGH:
            approved = False
            rejection_reason = "High-risk actions require explicit approval outside this stage."

        can_execute_automatically = (
            approved
            and not requires_confirmation
            and risk.automatic_approval_allowed
            and selected.action_type not in (ActionType.NO_ACTION, ActionType.DEFER)
        )
        decision_id = self._id(
            "decision",
            context.context_id,
            selected.intent_id,
            str(approved),
        )
        decision = ActionDecision(
            decision_id=decision_id,
            selected_action=selected,
            approved=approved,
            rejection_reason=rejection_reason,
            requires_confirmation=requires_confirmation,
            can_execute_automatically=can_execute_automatically,
            evaluated_permissions=permission_checks,
            evaluated_risks=risk,
            evaluated_resources=resources,
            created_at=context.current_time,
        )
        plan = self._build_plan(context, decision)
        session = ActionSession(
            action_session_id=self._id(
                "session", context.context_id, context.think_session_id
            ),
            subject_id=context.subject_id,
            wake_session_id=context.wake_session_id,
            think_session_id=context.think_session_id,
            input_state_revision=context.subject_state_revision,
            intents=intents,
            permission_checks=permission_checks,
            risk_assessment=risk,
            resource_assessment=resources,
            final_decision=decision,
            action_plan=plan,
            created_at=context.current_time,
        )
        self._repository.save_action_session(session)
        return ActionExecutionResult(context=context, session=session)

    def get_sessions(self, subject_id: str, limit: int | None = None) -> list[ActionSession]:
        return self._repository.list_action_sessions(subject_id, limit)

    def _extract_intents(self, context: ActionContext) -> list[ActionIntent]:
        result = context.thinking_result
        specifications: list[
            tuple[ActionType, str, str, RiskLevel, list[str], float, float]
        ] = []
        if result.update_subject_state:
            specifications.append(
                (
                    ActionType.UPDATE_STATE,
                    "subject_state",
                    "Submit the proposed mutations to Event and Evolution.",
                    RiskLevel.LOW,
                    ["subject_state:update"],
                    float(max(1, len(result.proposed_mutations))),
                    0.95,
                )
            )
        if result.request_more_memory:
            specifications.append(
                (
                    ActionType.REQUEST_MEMORY,
                    "memory_manager",
                    "Prepare a request for additional relevant memory.",
                    RiskLevel.LOW,
                    ["memory:request"],
                    2.0,
                    0.9,
                )
            )
        if result.request_more_thinking:
            specifications.append(
                (
                    ActionType.REQUEST_MORE_THINKING,
                    "thinking_engine",
                    "Prepare another bounded thinking pass.",
                    RiskLevel.LOW,
                    ["thinking:request"],
                    5.0,
                    0.8,
                )
            )
        if result.suggest_future_user_contact:
            specifications.append(
                (
                    ActionType.CONTACT_USER,
                    "user",
                    "Prepare a contact plan without sending a message.",
                    RiskLevel.MEDIUM,
                    ["user:contact"],
                    3.0,
                    0.75,
                )
            )
        if result.suggest_tool_use:
            assert result.tool_target is not None
            specifications.append(
                (
                    ActionType.USE_TOOL,
                    result.tool_target,
                    "Prepare a tool-use plan without invoking the tool.",
                    RiskLevel.HIGH,
                    [f"tool:use:{result.tool_target}"],
                    10.0,
                    0.7,
                )
            )
        if result.should_wait:
            specifications.append(
                (
                    ActionType.DEFER,
                    "action_review",
                    "Delay action and re-evaluate after more context becomes available.",
                    RiskLevel.LOW,
                    [],
                    0.0,
                    0.9,
                )
            )
        if not specifications:
            specifications.append(
                (
                    ActionType.NO_ACTION,
                    "continuity_engine",
                    "Explicitly retain the current state without an action plan.",
                    RiskLevel.LOW,
                    [],
                    0.0,
                    1.0,
                )
            )

        intents: list[ActionIntent] = []
        for index, (
            action_type,
            target,
            effect,
            risk,
            permissions,
            cost,
            confidence,
        ) in enumerate(specifications):
            intents.append(
                ActionIntent(
                    intent_id=self._id(
                        "intent",
                        result.result_id,
                        action_type.value,
                        str(index),
                    ),
                    action_type=action_type,
                    source_thought=result.result_summary,
                    reason=result.rationale_summary,
                    target=target,
                    expected_effect=effect,
                    confidence=confidence,
                    risk_level=risk,
                    required_permissions=permissions,
                    estimated_resource_cost=cost,
                    created_at=context.current_time,
                )
            )
        return intents

    def _check_permissions(
        self,
        context: ActionContext,
        intent: ActionIntent,
    ) -> list[PermissionCheck]:
        checks: list[PermissionCheck] = []
        for permission in intent.required_permissions:
            if permission not in context.effective_permissions:
                checks.append(
                    PermissionCheck.missing(
                        permission,
                        "The required permission is not in the currently available permission set.",
                    )
                )
                continue
            checks.append(
                self._permissions.check(
                    permission,
                    subject_id=context.subject_id,
                    action_type=intent.action_type,
                    target=intent.target,
                    at=context.current_time,
                )
            )
        return checks

    def _build_plan(
        self,
        context: ActionContext,
        decision: ActionDecision,
    ) -> ActionPlan:
        selected = decision.selected_action
        if selected.action_type is ActionType.DEFER:
            status = ActionPlanStatus.DEFERRED
        elif not decision.approved:
            invalid = [
                item
                for item in decision.evaluated_permissions
                if item.revoked or item.expired or (item.exists and not item.within_scope)
            ]
            status = (
                ActionPlanStatus.REJECTED
                if invalid
                or decision.evaluated_risks.risk_level is RiskLevel.CRITICAL
                or "revision" in (decision.rejection_reason or "").lower()
                else ActionPlanStatus.BLOCKED
            )
        elif decision.requires_confirmation:
            status = ActionPlanStatus.BLOCKED
        else:
            status = ActionPlanStatus.PLANNED

        parameters = self._step_parameters(context, selected.action_type)
        step = ActionStep(
            step_id=self._id("step", decision.decision_id, "1"),
            sequence=1,
            action_type=selected.action_type,
            target=selected.target,
            parameters=parameters,
            required_permission=(
                selected.required_permissions[0]
                if selected.required_permissions
                else None
            ),
            failure_policy=(
                FailurePolicy.DEFER
                if selected.action_type is ActionType.DEFER
                else FailurePolicy.ABORT
            ),
        )
        expiry = context.current_time + (
            timedelta(days=7)
            if selected.action_type is ActionType.DEFER
            else timedelta(days=1)
        )
        return ActionPlan(
            plan_id=self._id("plan", decision.decision_id),
            decision_id=decision.decision_id,
            steps=[step],
            expected_outcome=selected.expected_effect,
            requires_user_confirmation=decision.requires_confirmation,
            expires_at=expiry,
            status=status,
        )

    @staticmethod
    def _step_parameters(
        context: ActionContext,
        action_type: ActionType,
    ) -> dict:
        result = context.thinking_result
        if action_type is ActionType.UPDATE_STATE:
            return {
                "expected_revision": context.subject_state_revision,
                "mutations": [item.to_dict() for item in result.proposed_mutations],
            }
        if action_type is ActionType.REQUEST_MEMORY:
            return {"query": result.additional_memory_query}
        if action_type is ActionType.CONTACT_USER:
            return {
                "contact_intent": result.result_summary,
                "send_message": False,
            }
        if action_type is ActionType.USE_TOOL:
            return {
                "tool_target": result.tool_target,
                "invoke_tool": False,
            }
        if action_type is ActionType.DEFER:
            return {
                "reason": result.rationale_summary,
                "suggested_reevaluation_at": (
                    context.current_time + timedelta(days=1)
                ).isoformat(),
            }
        if action_type is ActionType.REQUEST_MORE_THINKING:
            return {"reason": result.rationale_summary, "start_thinking": False}
        return {"reason": "No action tendency was produced by thinking."}

    @staticmethod
    def _id(*parts: str) -> str:
        return str(uuid5(NAMESPACE_URL, "|".join(parts)))
