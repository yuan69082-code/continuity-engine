from continuity_engine.domain.action import (
    ActionIntent,
    ActionType,
    PermissionCheck,
    ResourceAssessment,
    ResourceLimits,
    RiskAssessment,
    RiskLevel,
)


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class RiskEvaluator:
    """Deterministic minimum-risk policy; no model or external service is used."""

    def evaluate(
        self,
        intent: ActionIntent,
        permission_checks: list[PermissionCheck],
    ) -> RiskAssessment:
        minimum = {
            ActionType.NO_ACTION: RiskLevel.LOW,
            ActionType.DEFER: RiskLevel.LOW,
            ActionType.UPDATE_STATE: RiskLevel.LOW,
            ActionType.REQUEST_MEMORY: RiskLevel.LOW,
            ActionType.REQUEST_MORE_THINKING: RiskLevel.LOW,
            ActionType.CONTACT_USER: RiskLevel.MEDIUM,
            ActionType.USE_TOOL: RiskLevel.HIGH,
        }[intent.action_type]
        level = max((intent.risk_level, minimum), key=lambda item: _RISK_ORDER[item])
        reasons = [
            f"{intent.action_type.value} has a deterministic minimum risk of {minimum.value}."
        ]
        if intent.risk_level is not minimum:
            reasons.append(
                f"The intent declared {intent.risk_level.value} risk and the stricter value was retained."
            )
        if intent.action_type is ActionType.USE_TOOL:
            reasons.append(
                "Tool use cannot default to low risk because the target and permission boundary matter."
            )
        if intent.action_type is ActionType.CONTACT_USER:
            reasons.append(
                "Contact planning requires user confirmation in the current stage."
            )
        if any(item.revoked or item.expired or not item.within_scope for item in permission_checks):
            reasons.append("A permission problem increases uncertainty around the action.")
        if "critical" in intent.target.lower():
            level = RiskLevel.CRITICAL
            reasons.append("The target is explicitly marked critical.")
        return RiskAssessment(
            risk_level=level,
            reasons=reasons,
            automatic_approval_allowed=level not in (RiskLevel.HIGH, RiskLevel.CRITICAL),
        )


class ResourceEvaluator:
    """Deterministic plan-cost check; it does not inspect real tokens or billing."""

    def evaluate(
        self,
        intent: ActionIntent,
        limits: ResourceLimits,
    ) -> ResourceAssessment:
        estimated_steps = 1
        action_allowed = intent.action_type in limits.allowed_action_types
        within_cost = intent.estimated_resource_cost <= limits.maximum_estimated_cost
        within_steps = estimated_steps <= limits.maximum_plan_steps
        reasons = [
            (
                "The estimated resource cost is within the configured limit."
                if within_cost
                else "The estimated resource cost exceeds the configured limit."
            ),
            (
                "The planned step count is within the configured limit."
                if within_steps
                else "The planned step count exceeds the configured limit."
            ),
            (
                "The action type is allowed by the current resource limits."
                if action_allowed
                else "The action type is excluded by the current resource limits."
            ),
        ]
        return ResourceAssessment(
            estimated_cost=intent.estimated_resource_cost,
            maximum_cost=limits.maximum_estimated_cost,
            estimated_steps=estimated_steps,
            maximum_steps=limits.maximum_plan_steps,
            within_limits=within_cost and within_steps and action_allowed,
            reasons=reasons,
        )
