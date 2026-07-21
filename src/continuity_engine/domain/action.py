from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from .awakening import AwakeningResult
from .errors import ActionValidationError
from .events import JsonValue, StateUpdateRecord
from .perception import PerceptionResult
from .permissions import PermissionContext
from .thinking import ThinkingExecutionResult, ThinkingResult


class ActionType(str, Enum):
    NO_ACTION = "NO_ACTION"
    UPDATE_STATE = "UPDATE_STATE"
    REQUEST_MEMORY = "REQUEST_MEMORY"
    CONTACT_USER = "CONTACT_USER"
    USE_TOOL = "USE_TOOL"
    DEFER = "DEFER"
    REQUEST_MORE_THINKING = "REQUEST_MORE_THINKING"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionPlanStatus(str, Enum):
    PLANNED = "PLANNED"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


class FailurePolicy(str, Enum):
    ABORT = "ABORT"
    SKIP = "SKIP"
    DEFER = "DEFER"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActionValidationError(f"{field_name} must be a non-empty string")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ActionValidationError(
            f"{field_name} must be a list of non-empty strings"
        )
    return list(value)


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ActionValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ActionValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ActionValidationError(f"{field_name} is not a valid datetime") from exc
    if parsed.tzinfo is None:
        raise ActionValidationError(f"{field_name} must include a timezone")
    return parsed


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        raise ActionValidationError(f"unsupported {field_name}") from exc


def _json_object(value: Any, field_name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ActionValidationError(f"{field_name} must be an object")
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ActionValidationError(
            f"{field_name} must contain JSON-compatible values"
        ) from exc
    return dict(value)


@dataclass(slots=True)
class ResourceLimits:
    maximum_plan_steps: int = 10
    maximum_estimated_cost: float = 100.0
    allowed_action_types: list[ActionType] = field(
        default_factory=lambda: list(ActionType)
    )

    def __post_init__(self) -> None:
        if not isinstance(self.maximum_plan_steps, int) or self.maximum_plan_steps < 1:
            raise ActionValidationError("maximum_plan_steps must be positive")
        if not isinstance(self.maximum_estimated_cost, (int, float)) or float(
            self.maximum_estimated_cost
        ) < 0:
            raise ActionValidationError("maximum_estimated_cost must be non-negative")
        self.maximum_estimated_cost = float(self.maximum_estimated_cost)
        normalized: list[ActionType] = []
        for item in self.allowed_action_types:
            action_type = _enum(item, ActionType, "allowed action type")
            if action_type not in normalized:
                normalized.append(action_type)
        self.allowed_action_types = normalized

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "maximum_plan_steps": self.maximum_plan_steps,
            "maximum_estimated_cost": self.maximum_estimated_cost,
            "allowed_action_types": [item.value for item in self.allowed_action_types],
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceLimits:
        if not isinstance(value, dict) or not isinstance(
            value.get("allowed_action_types", []), list
        ):
            raise ActionValidationError("resource limits must be an object")
        return cls(
            maximum_plan_steps=value.get("maximum_plan_steps", 10),
            maximum_estimated_cost=value.get("maximum_estimated_cost", 100.0),
            allowed_action_types=value.get("allowed_action_types", list(ActionType)),
        )


@dataclass(slots=True)
class PerceptionActionSummary:
    perception_id: str
    wake_session_id: str
    source_revision: int
    summary: str
    current_focus: str
    temporal_meaning: str
    relationship_meaning: str
    memory_influence: str
    observation_notes: list[str]
    internal_drives: list[str]

    def __post_init__(self) -> None:
        _require_text(self.perception_id, "perception_id")
        _require_text(self.wake_session_id, "perception wake_session_id")
        if not isinstance(self.source_revision, int) or self.source_revision < 0:
            raise ActionValidationError("perception source_revision is invalid")
        for value, name in (
            (self.summary, "perception summary"),
            (self.current_focus, "perception current_focus"),
            (self.temporal_meaning, "perception temporal_meaning"),
            (self.relationship_meaning, "perception relationship_meaning"),
            (self.memory_influence, "perception memory_influence"),
        ):
            _require_text(value, name)
        self.observation_notes = _text_list(
            self.observation_notes, "perception observation_notes"
        )
        self.internal_drives = _text_list(
            self.internal_drives, "perception internal_drives"
        )

    @classmethod
    def from_perception(cls, perception: PerceptionResult) -> PerceptionActionSummary:
        return cls(
            perception_id=perception.perception_id,
            wake_session_id=perception.wake_session_id,
            source_revision=perception.source_revision,
            summary=perception.summary,
            current_focus=perception.current_focus.summary,
            temporal_meaning=perception.temporal_perception.meaning,
            relationship_meaning=perception.relationship_perception.summary,
            memory_influence=perception.memory_influence.summary,
            observation_notes=list(perception.observation.notes),
            internal_drives=[item.tendency for item in perception.internal_drives],
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "perception_id": self.perception_id,
            "wake_session_id": self.wake_session_id,
            "source_revision": self.source_revision,
            "summary": self.summary,
            "current_focus": self.current_focus,
            "temporal_meaning": self.temporal_meaning,
            "relationship_meaning": self.relationship_meaning,
            "memory_influence": self.memory_influence,
            "observation_notes": list(self.observation_notes),
            "internal_drives": list(self.internal_drives),
        }

    @classmethod
    def from_dict(cls, value: Any) -> PerceptionActionSummary:
        if not isinstance(value, dict):
            raise ActionValidationError("perception action summary must be an object")
        return cls(
            perception_id=value.get("perception_id"),
            wake_session_id=value.get("wake_session_id"),
            source_revision=value.get("source_revision"),
            summary=value.get("summary"),
            current_focus=value.get("current_focus"),
            temporal_meaning=value.get("temporal_meaning"),
            relationship_meaning=value.get("relationship_meaning"),
            memory_influence=value.get("memory_influence"),
            observation_notes=_text_list(
                value.get("observation_notes", []), "perception observation_notes"
            ),
            internal_drives=_text_list(
                value.get("internal_drives", []), "perception internal_drives"
            ),
        )


@dataclass(slots=True)
class ActionContext:
    context_id: str
    subject_id: str
    wake_session_id: str
    think_session_id: str
    subject_state_revision: int
    thinking_result: ThinkingResult
    perception_summary: PerceptionActionSummary
    current_time: datetime
    available_permissions: list[str]
    resource_limits: ResourceLimits
    permission_context: PermissionContext | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.context_id, "action context_id"),
            (self.subject_id, "action subject_id"),
            (self.wake_session_id, "action wake_session_id"),
            (self.think_session_id, "action think_session_id"),
        ):
            _require_text(value, name)
        if not isinstance(self.subject_state_revision, int) or self.subject_state_revision < 0:
            raise ActionValidationError("subject_state_revision must be non-negative")
        if not isinstance(self.thinking_result, ThinkingResult):
            raise ActionValidationError("ActionContext requires ThinkingResult")
        if not isinstance(self.perception_summary, PerceptionActionSummary):
            raise ActionValidationError("ActionContext requires perception summary")
        if self.wake_session_id != self.perception_summary.wake_session_id:
            raise ActionValidationError("action wake does not match perception")
        if self.current_time.tzinfo is None:
            raise ActionValidationError("action current_time must include a timezone")
        self.available_permissions = _text_list(
            self.available_permissions, "available_permissions"
        )
        if not isinstance(self.resource_limits, ResourceLimits):
            raise ActionValidationError("ActionContext requires ResourceLimits")
        if self.permission_context is not None:
            if not isinstance(self.permission_context, PermissionContext):
                raise ActionValidationError(
                    "permission_context must be a PermissionContext"
                )
            if self.permission_context.subject_id != self.subject_id:
                raise ActionValidationError(
                    "PermissionContext subject does not match ActionContext"
                )

    @property
    def effective_permissions(self) -> list[str]:
        if self.permission_context is not None:
            return list(self.permission_context.available_capabilities)
        return list(self.available_permissions)

    @classmethod
    def from_results(
        cls,
        *,
        subject_id: str,
        subject_state_revision: int,
        thinking: ThinkingExecutionResult,
        perception: PerceptionResult,
        current_time: datetime,
        available_permissions: Iterable[str],
        resource_limits: ResourceLimits,
        context_id: str,
        permission_context: PermissionContext | None = None,
    ) -> ActionContext:
        result = thinking.session.result
        if result is None or not thinking.session.completed_successfully:
            raise ActionValidationError("action requires a completed ThinkingResult")
        if thinking.session.subject_id != subject_id:
            raise ActionValidationError("ThinkSession subject does not match action")
        if thinking.session.wake_session_id != perception.wake_session_id:
            raise ActionValidationError("ThinkSession wake does not match perception")
        if thinking.perception.perception_id != perception.perception_id:
            raise ActionValidationError("Thinking input does not match perception")
        return cls(
            context_id=context_id,
            subject_id=subject_id,
            wake_session_id=perception.wake_session_id,
            think_session_id=thinking.session.think_id,
            subject_state_revision=subject_state_revision,
            thinking_result=result,
            perception_summary=PerceptionActionSummary.from_perception(perception),
            current_time=current_time,
            available_permissions=list(available_permissions),
            resource_limits=resource_limits,
            permission_context=permission_context,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "context_id": self.context_id,
            "subject_id": self.subject_id,
            "wake_session_id": self.wake_session_id,
            "think_session_id": self.think_session_id,
            "subject_state_revision": self.subject_state_revision,
            "thinking_result": self.thinking_result.to_dict(),
            "perception_summary": self.perception_summary.to_dict(),
            "current_time": _format_datetime(self.current_time),
            "available_permissions": list(self.available_permissions),
            "resource_limits": self.resource_limits.to_dict(),
            "permission_context": (
                self.permission_context.to_dict()
                if self.permission_context is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionContext:
        if not isinstance(value, dict):
            raise ActionValidationError("action context must be an object")
        return cls(
            context_id=value.get("context_id"),
            subject_id=value.get("subject_id"),
            wake_session_id=value.get("wake_session_id"),
            think_session_id=value.get("think_session_id"),
            subject_state_revision=value.get("subject_state_revision"),
            thinking_result=ThinkingResult.from_dict(value.get("thinking_result")),
            perception_summary=PerceptionActionSummary.from_dict(
                value.get("perception_summary")
            ),
            current_time=_parse_datetime(value.get("current_time"), "action current_time"),
            available_permissions=_text_list(
                value.get("available_permissions", []), "available_permissions"
            ),
            resource_limits=ResourceLimits.from_dict(value.get("resource_limits")),
            permission_context=(
                PermissionContext.from_dict(value.get("permission_context"))
                if value.get("permission_context") is not None
                else None
            ),
        )


@dataclass(slots=True)
class ActionIntent:
    intent_id: str
    action_type: ActionType
    source_thought: str
    reason: str
    target: str
    expected_effect: str
    confidence: float
    risk_level: RiskLevel
    required_permissions: list[str]
    estimated_resource_cost: float
    created_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.intent_id, "intent_id"),
            (self.source_thought, "source_thought"),
            (self.reason, "intent reason"),
            (self.target, "intent target"),
            (self.expected_effect, "expected_effect"),
        ):
            _require_text(value, name)
        self.action_type = _enum(self.action_type, ActionType, "action type")
        self.risk_level = _enum(self.risk_level, RiskLevel, "risk level")
        if not isinstance(self.confidence, (int, float)) or not 0 <= float(
            self.confidence
        ) <= 1:
            raise ActionValidationError("confidence must be between 0 and 1")
        self.confidence = float(self.confidence)
        self.required_permissions = _text_list(
            self.required_permissions, "required_permissions"
        )
        if not isinstance(self.estimated_resource_cost, (int, float)) or float(
            self.estimated_resource_cost
        ) < 0:
            raise ActionValidationError("estimated_resource_cost must be non-negative")
        self.estimated_resource_cost = float(self.estimated_resource_cost)
        if self.created_at.tzinfo is None:
            raise ActionValidationError("intent created_at must include a timezone")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "intent_id": self.intent_id,
            "action_type": self.action_type.value,
            "source_thought": self.source_thought,
            "reason": self.reason,
            "target": self.target,
            "expected_effect": self.expected_effect,
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "required_permissions": list(self.required_permissions),
            "estimated_resource_cost": self.estimated_resource_cost,
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionIntent:
        if not isinstance(value, dict):
            raise ActionValidationError("action intent must be an object")
        return cls(
            intent_id=value.get("intent_id"),
            action_type=value.get("action_type"),
            source_thought=value.get("source_thought"),
            reason=value.get("reason"),
            target=value.get("target"),
            expected_effect=value.get("expected_effect"),
            confidence=value.get("confidence"),
            risk_level=value.get("risk_level"),
            required_permissions=_text_list(
                value.get("required_permissions", []), "required_permissions"
            ),
            estimated_resource_cost=value.get("estimated_resource_cost"),
            created_at=_parse_datetime(value.get("created_at"), "intent created_at"),
        )


@dataclass(slots=True)
class PermissionGrant:
    permission: str
    subject_id: str
    valid_from: datetime
    expires_at: datetime | None = None
    revoked: bool = False
    requires_confirmation: bool = False
    scopes: list[str] = field(default_factory=lambda: ["*"])

    def __post_init__(self) -> None:
        _require_text(self.permission, "permission")
        _require_text(self.subject_id, "permission subject_id")
        if self.valid_from.tzinfo is None:
            raise ActionValidationError("permission valid_from must include a timezone")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ActionValidationError("permission expires_at must include a timezone")
        if self.expires_at is not None and self.expires_at < self.valid_from:
            raise ActionValidationError("permission expires before it becomes valid")
        if not isinstance(self.revoked, bool) or not isinstance(
            self.requires_confirmation, bool
        ):
            raise ActionValidationError("permission flags must be booleans")
        self.scopes = _text_list(self.scopes, "permission scopes")


@dataclass(slots=True)
class PermissionCheck:
    permission: str
    exists: bool
    valid: bool
    revoked: bool
    expired: bool
    requires_confirmation: bool
    within_scope: bool
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.permission, "checked permission")
        for value, name in (
            (self.exists, "permission exists"),
            (self.valid, "permission valid"),
            (self.revoked, "permission revoked"),
            (self.expired, "permission expired"),
            (self.requires_confirmation, "permission requires_confirmation"),
            (self.within_scope, "permission within_scope"),
        ):
            if not isinstance(value, bool):
                raise ActionValidationError(f"{name} must be a boolean")
        _require_text(self.reason, "permission check reason")
        if self.valid and (
            not self.exists or self.revoked or self.expired or not self.within_scope
        ):
            raise ActionValidationError("a valid permission check is inconsistent")

    @classmethod
    def missing(cls, permission: str, reason: str) -> PermissionCheck:
        return cls(permission, False, False, False, False, False, False, reason)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "permission": self.permission,
            "exists": self.exists,
            "valid": self.valid,
            "revoked": self.revoked,
            "expired": self.expired,
            "requires_confirmation": self.requires_confirmation,
            "within_scope": self.within_scope,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> PermissionCheck:
        if not isinstance(value, dict):
            raise ActionValidationError("permission check must be an object")
        return cls(
            permission=value.get("permission"),
            exists=value.get("exists"),
            valid=value.get("valid"),
            revoked=value.get("revoked"),
            expired=value.get("expired"),
            requires_confirmation=value.get("requires_confirmation"),
            within_scope=value.get("within_scope"),
            reason=value.get("reason"),
        )


@dataclass(slots=True)
class RiskAssessment:
    risk_level: RiskLevel
    reasons: list[str]
    automatic_approval_allowed: bool

    def __post_init__(self) -> None:
        self.risk_level = _enum(self.risk_level, RiskLevel, "risk level")
        self.reasons = _text_list(self.reasons, "risk reasons")
        if not isinstance(self.automatic_approval_allowed, bool):
            raise ActionValidationError("automatic_approval_allowed must be boolean")
        if self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and (
            self.automatic_approval_allowed
        ):
            raise ActionValidationError("high-risk action cannot allow automatic approval")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "risk_level": self.risk_level.value,
            "reasons": list(self.reasons),
            "automatic_approval_allowed": self.automatic_approval_allowed,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RiskAssessment:
        if not isinstance(value, dict):
            raise ActionValidationError("risk assessment must be an object")
        return cls(
            risk_level=value.get("risk_level"),
            reasons=_text_list(value.get("reasons", []), "risk reasons"),
            automatic_approval_allowed=value.get("automatic_approval_allowed"),
        )


@dataclass(slots=True)
class ResourceAssessment:
    estimated_cost: float
    maximum_cost: float
    estimated_steps: int
    maximum_steps: int
    within_limits: bool
    reasons: list[str]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, (int, float)) or float(value) < 0
            for value in (self.estimated_cost, self.maximum_cost)
        ):
            raise ActionValidationError("resource costs must be non-negative")
        if any(
            not isinstance(value, int) or value < 0
            for value in (self.estimated_steps, self.maximum_steps)
        ):
            raise ActionValidationError("resource steps must be non-negative")
        self.estimated_cost = float(self.estimated_cost)
        self.maximum_cost = float(self.maximum_cost)
        if not isinstance(self.within_limits, bool):
            raise ActionValidationError("within_limits must be boolean")
        self.reasons = _text_list(self.reasons, "resource reasons")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "estimated_cost": self.estimated_cost,
            "maximum_cost": self.maximum_cost,
            "estimated_steps": self.estimated_steps,
            "maximum_steps": self.maximum_steps,
            "within_limits": self.within_limits,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceAssessment:
        if not isinstance(value, dict):
            raise ActionValidationError("resource assessment must be an object")
        return cls(
            estimated_cost=value.get("estimated_cost"),
            maximum_cost=value.get("maximum_cost"),
            estimated_steps=value.get("estimated_steps"),
            maximum_steps=value.get("maximum_steps"),
            within_limits=value.get("within_limits"),
            reasons=_text_list(value.get("reasons", []), "resource reasons"),
        )


@dataclass(slots=True)
class ActionDecision:
    decision_id: str
    selected_action: ActionIntent
    approved: bool
    rejection_reason: str | None
    requires_confirmation: bool
    can_execute_automatically: bool
    evaluated_permissions: list[PermissionCheck]
    evaluated_risks: RiskAssessment
    evaluated_resources: ResourceAssessment
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        if not isinstance(self.selected_action, ActionIntent):
            raise ActionValidationError("selected_action must be an ActionIntent")
        for value, name in (
            (self.approved, "action approved"),
            (self.requires_confirmation, "requires_confirmation"),
            (self.can_execute_automatically, "can_execute_automatically"),
        ):
            if not isinstance(value, bool):
                raise ActionValidationError(f"{name} must be a boolean")
        if self.approved:
            if self.rejection_reason is not None:
                raise ActionValidationError("approved decision cannot have rejection_reason")
        else:
            _require_text(self.rejection_reason, "rejection_reason")
        if self.can_execute_automatically and (
            not self.approved or self.requires_confirmation
        ):
            raise ActionValidationError("automatic execution flags are inconsistent")
        if any(
            not isinstance(item, PermissionCheck) for item in self.evaluated_permissions
        ):
            raise ActionValidationError("evaluated_permissions are invalid")
        if not isinstance(self.evaluated_risks, RiskAssessment) or not isinstance(
            self.evaluated_resources, ResourceAssessment
        ):
            raise ActionValidationError("action assessments are invalid")
        if self.created_at.tzinfo is None:
            raise ActionValidationError("decision created_at must include a timezone")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "decision_id": self.decision_id,
            "selected_action": self.selected_action.to_dict(),
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
            "requires_confirmation": self.requires_confirmation,
            "can_execute_automatically": self.can_execute_automatically,
            "evaluated_permissions": [item.to_dict() for item in self.evaluated_permissions],
            "evaluated_risks": self.evaluated_risks.to_dict(),
            "evaluated_resources": self.evaluated_resources.to_dict(),
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionDecision:
        if not isinstance(value, dict) or not isinstance(
            value.get("evaluated_permissions"), list
        ):
            raise ActionValidationError("action decision must contain permissions")
        return cls(
            decision_id=value.get("decision_id"),
            selected_action=ActionIntent.from_dict(value.get("selected_action")),
            approved=value.get("approved"),
            rejection_reason=value.get("rejection_reason"),
            requires_confirmation=value.get("requires_confirmation"),
            can_execute_automatically=value.get("can_execute_automatically"),
            evaluated_permissions=[
                PermissionCheck.from_dict(item)
                for item in value["evaluated_permissions"]
            ],
            evaluated_risks=RiskAssessment.from_dict(value.get("evaluated_risks")),
            evaluated_resources=ResourceAssessment.from_dict(
                value.get("evaluated_resources")
            ),
            created_at=_parse_datetime(value.get("created_at"), "decision created_at"),
        )


@dataclass(slots=True)
class ActionStep:
    step_id: str
    sequence: int
    action_type: ActionType
    target: str
    parameters: dict[str, JsonValue]
    required_permission: str | None
    failure_policy: FailurePolicy

    def __post_init__(self) -> None:
        _require_text(self.step_id, "step_id")
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ActionValidationError("step sequence must be positive")
        self.action_type = _enum(self.action_type, ActionType, "step action type")
        _require_text(self.target, "step target")
        self.parameters = _json_object(self.parameters, "step parameters")
        self.required_permission = _optional_text(
            self.required_permission, "step required_permission"
        )
        self.failure_policy = _enum(
            self.failure_policy, FailurePolicy, "failure policy"
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "step_id": self.step_id,
            "sequence": self.sequence,
            "action_type": self.action_type.value,
            "target": self.target,
            "parameters": self.parameters,
            "required_permission": self.required_permission,
            "failure_policy": self.failure_policy.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionStep:
        if not isinstance(value, dict):
            raise ActionValidationError("action step must be an object")
        return cls(
            step_id=value.get("step_id"),
            sequence=value.get("sequence"),
            action_type=value.get("action_type"),
            target=value.get("target"),
            parameters=_json_object(value.get("parameters", {}), "step parameters"),
            required_permission=value.get("required_permission"),
            failure_policy=value.get("failure_policy"),
        )


@dataclass(slots=True)
class ActionPlan:
    plan_id: str
    decision_id: str
    steps: list[ActionStep]
    expected_outcome: str
    requires_user_confirmation: bool
    expires_at: datetime
    status: ActionPlanStatus

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.decision_id, "plan decision_id")
        if any(not isinstance(item, ActionStep) for item in self.steps):
            raise ActionValidationError("plan steps are invalid")
        sequences = [item.sequence for item in self.steps]
        if sequences != list(range(1, len(self.steps) + 1)):
            raise ActionValidationError("plan step sequence must be contiguous")
        _require_text(self.expected_outcome, "expected_outcome")
        if not isinstance(self.requires_user_confirmation, bool):
            raise ActionValidationError("requires_user_confirmation must be boolean")
        if self.expires_at.tzinfo is None:
            raise ActionValidationError("plan expires_at must include a timezone")
        self.status = _enum(self.status, ActionPlanStatus, "action plan status")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "plan_id": self.plan_id,
            "decision_id": self.decision_id,
            "steps": [item.to_dict() for item in self.steps],
            "expected_outcome": self.expected_outcome,
            "requires_user_confirmation": self.requires_user_confirmation,
            "expires_at": _format_datetime(self.expires_at),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionPlan:
        if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
            raise ActionValidationError("action plan must contain steps")
        return cls(
            plan_id=value.get("plan_id"),
            decision_id=value.get("decision_id"),
            steps=[ActionStep.from_dict(item) for item in value["steps"]],
            expected_outcome=value.get("expected_outcome"),
            requires_user_confirmation=value.get("requires_user_confirmation"),
            expires_at=_parse_datetime(value.get("expires_at"), "plan expires_at"),
            status=value.get("status"),
        )


@dataclass(slots=True)
class ActionSession:
    action_session_id: str
    subject_id: str
    wake_session_id: str
    think_session_id: str
    input_state_revision: int
    intents: list[ActionIntent]
    permission_checks: list[PermissionCheck]
    risk_assessment: RiskAssessment
    resource_assessment: ResourceAssessment
    final_decision: ActionDecision
    action_plan: ActionPlan
    created_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.action_session_id, "action_session_id"),
            (self.subject_id, "action session subject_id"),
            (self.wake_session_id, "action session wake_session_id"),
            (self.think_session_id, "action session think_session_id"),
        ):
            _require_text(value, name)
        if not isinstance(self.input_state_revision, int) or self.input_state_revision < 0:
            raise ActionValidationError("input_state_revision must be non-negative")
        if not self.intents or any(
            not isinstance(item, ActionIntent) for item in self.intents
        ):
            raise ActionValidationError("ActionSession requires intents")
        if any(not isinstance(item, PermissionCheck) for item in self.permission_checks):
            raise ActionValidationError("ActionSession permission checks are invalid")
        if self.final_decision.selected_action.intent_id not in {
            item.intent_id for item in self.intents
        }:
            raise ActionValidationError("selected action is not part of the session")
        if self.action_plan.decision_id != self.final_decision.decision_id:
            raise ActionValidationError("action plan does not match decision")
        if self.created_at.tzinfo is None:
            raise ActionValidationError("action session created_at must include timezone")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "action_session_id": self.action_session_id,
            "subject_id": self.subject_id,
            "wake_session_id": self.wake_session_id,
            "think_session_id": self.think_session_id,
            "input_state_revision": self.input_state_revision,
            "intents": [item.to_dict() for item in self.intents],
            "permission_checks": [item.to_dict() for item in self.permission_checks],
            "risk_assessment": self.risk_assessment.to_dict(),
            "resource_assessment": self.resource_assessment.to_dict(),
            "final_decision": self.final_decision.to_dict(),
            "action_plan": self.action_plan.to_dict(),
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ActionSession:
        if not isinstance(value, dict) or not isinstance(value.get("intents"), list) or not isinstance(
            value.get("permission_checks"), list
        ):
            raise ActionValidationError("action session has invalid collections")
        return cls(
            action_session_id=value.get("action_session_id"),
            subject_id=value.get("subject_id"),
            wake_session_id=value.get("wake_session_id"),
            think_session_id=value.get("think_session_id"),
            input_state_revision=value.get("input_state_revision"),
            intents=[ActionIntent.from_dict(item) for item in value["intents"]],
            permission_checks=[
                PermissionCheck.from_dict(item) for item in value["permission_checks"]
            ],
            risk_assessment=RiskAssessment.from_dict(value.get("risk_assessment")),
            resource_assessment=ResourceAssessment.from_dict(
                value.get("resource_assessment")
            ),
            final_decision=ActionDecision.from_dict(value.get("final_decision")),
            action_plan=ActionPlan.from_dict(value.get("action_plan")),
            created_at=_parse_datetime(value.get("created_at"), "session created_at"),
        )


@dataclass(slots=True)
class ActionExecutionResult:
    context: ActionContext
    session: ActionSession

    @property
    def decision(self) -> ActionDecision:
        return self.session.final_decision

    @property
    def plan(self) -> ActionPlan:
        return self.session.action_plan


@dataclass(slots=True)
class WakePerceptionThinkingActionResult:
    awakening: AwakeningResult
    perception: PerceptionResult
    thinking: ThinkingExecutionResult | None
    action: ActionExecutionResult | None
    state_update: StateUpdateRecord | None = None

    @property
    def thinking_result(self) -> ThinkingResult | None:
        return self.thinking.session.result if self.thinking is not None else None

    @property
    def action_decision(self) -> ActionDecision | None:
        return self.action.decision if self.action is not None else None

    @property
    def action_plan(self) -> ActionPlan | None:
        return self.action.plan if self.action is not None else None
