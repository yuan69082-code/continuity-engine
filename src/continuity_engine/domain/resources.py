from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .errors import ResourceValidationError
from .events import JsonValue
from .thinking import ThinkingDepth


class RuntimeMode(str, Enum):
    LOW_FREQUENCY = "LOW_FREQUENCY"
    SCHEDULED = "SCHEDULED"
    CONTINUOUS = "CONTINUOUS"
    DEEP_THINKING = "DEEP_THINKING"


class ResourceSessionType(str, Enum):
    THINKING = "THINKING"
    MEMORY = "MEMORY"
    LEARNING = "LEARNING"
    OTHER = "OTHER"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResourceValidationError(f"{field_name} must be a non-empty string")
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResourceValidationError(f"{field_name} must be a non-negative integer")
    return value


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ResourceValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ResourceValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResourceValidationError(f"{field_name} is not a valid datetime") from exc
    if parsed.tzinfo is None:
        raise ResourceValidationError(f"{field_name} must include a timezone")
    return parsed


def _runtime_mode(value: Any) -> RuntimeMode:
    try:
        return value if isinstance(value, RuntimeMode) else RuntimeMode(value)
    except ValueError as exc:
        raise ResourceValidationError("unsupported runtime mode") from exc


def _session_type(value: Any) -> ResourceSessionType:
    try:
        return (
            value
            if isinstance(value, ResourceSessionType)
            else ResourceSessionType(value)
        )
    except ValueError as exc:
        raise ResourceValidationError("unsupported resource session type") from exc


def _thinking_depth(value: Any, *, optional: bool = False) -> ThinkingDepth | None:
    if value is None and optional:
        return None
    try:
        return value if isinstance(value, ThinkingDepth) else ThinkingDepth(value)
    except ValueError as exc:
        raise ResourceValidationError("unsupported thinking depth") from exc


@dataclass(slots=True)
class ResourceState:
    resource_id: str
    subject_id: str
    token_budget: int
    token_used: int
    token_remaining: int
    compute_budget: int
    current_mode: RuntimeMode
    updated_at: datetime
    compute_used: int = 0
    compute_remaining: int | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        _require_text(self.resource_id, "resource_id")
        _require_text(self.subject_id, "resource subject_id")
        self.token_budget = _non_negative_int(self.token_budget, "token_budget")
        self.token_used = _non_negative_int(self.token_used, "token_used")
        self.token_remaining = _non_negative_int(
            self.token_remaining, "token_remaining"
        )
        self.compute_budget = _non_negative_int(
            self.compute_budget, "compute_budget"
        )
        self.compute_used = _non_negative_int(self.compute_used, "compute_used")
        if self.compute_remaining is None:
            self.compute_remaining = max(0, self.compute_budget - self.compute_used)
        self.compute_remaining = _non_negative_int(
            self.compute_remaining, "compute_remaining"
        )
        if self.token_remaining != max(0, self.token_budget - self.token_used):
            raise ResourceValidationError(
                "token_remaining must match token budget and usage"
            )
        if self.compute_remaining != max(0, self.compute_budget - self.compute_used):
            raise ResourceValidationError(
                "compute_remaining must match compute budget and usage"
            )
        self.current_mode = _runtime_mode(self.current_mode)
        if self.updated_at.tzinfo is None:
            raise ResourceValidationError("resource updated_at must include a timezone")
        self.revision = _non_negative_int(self.revision, "resource revision")

    @classmethod
    def create(
        cls,
        *,
        subject_id: str,
        token_budget: int,
        compute_budget: int,
        current_mode: RuntimeMode,
        updated_at: datetime,
        resource_id: str | None = None,
    ) -> ResourceState:
        return cls(
            resource_id=resource_id or str(uuid4()),
            subject_id=subject_id,
            token_budget=token_budget,
            token_used=0,
            token_remaining=token_budget,
            compute_budget=compute_budget,
            compute_used=0,
            compute_remaining=compute_budget,
            current_mode=current_mode,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "resource_id": self.resource_id,
            "subject_id": self.subject_id,
            "token_budget": self.token_budget,
            "token_used": self.token_used,
            "token_remaining": self.token_remaining,
            "compute_budget": self.compute_budget,
            "compute_used": self.compute_used,
            "compute_remaining": self.compute_remaining,
            "current_mode": self.current_mode.value,
            "updated_at": _format_datetime(self.updated_at),
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceState:
        if not isinstance(value, dict):
            raise ResourceValidationError("resource state must be an object")
        return cls(
            resource_id=value.get("resource_id"),
            subject_id=value.get("subject_id"),
            token_budget=value.get("token_budget"),
            token_used=value.get("token_used"),
            token_remaining=value.get("token_remaining"),
            compute_budget=value.get("compute_budget"),
            compute_used=value.get("compute_used", 0),
            compute_remaining=value.get("compute_remaining"),
            current_mode=value.get("current_mode"),
            updated_at=_parse_datetime(value.get("updated_at"), "resource updated_at"),
            revision=value.get("revision", 0),
        )


@dataclass(slots=True)
class TokenUsageRecord:
    usage_id: str
    subject_id: str
    session_id: str
    session_type: ResourceSessionType
    estimated_tokens: int
    actual_tokens: int | None
    model_name: str
    reason: str
    created_at: datetime
    estimated_compute: int = 0

    def __post_init__(self) -> None:
        for value, name in (
            (self.usage_id, "usage_id"),
            (self.subject_id, "usage subject_id"),
            (self.session_id, "usage session_id"),
            (self.model_name, "usage model_name"),
            (self.reason, "usage reason"),
        ):
            _require_text(value, name)
        self.session_type = _session_type(self.session_type)
        self.estimated_tokens = _non_negative_int(
            self.estimated_tokens, "estimated_tokens"
        )
        if self.actual_tokens is not None:
            self.actual_tokens = _non_negative_int(self.actual_tokens, "actual_tokens")
        self.estimated_compute = _non_negative_int(
            self.estimated_compute, "estimated_compute"
        )
        if self.created_at.tzinfo is None:
            raise ResourceValidationError("usage created_at must include a timezone")

    @property
    def accounted_tokens(self) -> int:
        return self.actual_tokens if self.actual_tokens is not None else self.estimated_tokens

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "usage_id": self.usage_id,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "session_type": self.session_type.value,
            "estimated_tokens": self.estimated_tokens,
            "actual_tokens": self.actual_tokens,
            "model_name": self.model_name,
            "reason": self.reason,
            "created_at": _format_datetime(self.created_at),
            "estimated_compute": self.estimated_compute,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TokenUsageRecord:
        if not isinstance(value, dict):
            raise ResourceValidationError("token usage record must be an object")
        return cls(
            usage_id=value.get("usage_id"),
            subject_id=value.get("subject_id"),
            session_id=value.get("session_id"),
            session_type=value.get("session_type"),
            estimated_tokens=value.get("estimated_tokens"),
            actual_tokens=value.get("actual_tokens"),
            model_name=value.get("model_name"),
            reason=value.get("reason"),
            created_at=_parse_datetime(value.get("created_at"), "usage created_at"),
            estimated_compute=value.get("estimated_compute", 0),
        )


@dataclass(slots=True)
class ResourceRequest:
    request_id: str
    subject_id: str
    session_id: str
    session_type: ResourceSessionType
    estimated_tokens: int
    estimated_compute: int
    model_name: str
    reason: str
    requested_at: datetime
    requested_depth: ThinkingDepth | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "resource request_id"),
            (self.subject_id, "request subject_id"),
            (self.session_id, "request session_id"),
            (self.model_name, "request model_name"),
            (self.reason, "request reason"),
        ):
            _require_text(value, name)
        self.session_type = _session_type(self.session_type)
        self.estimated_tokens = _non_negative_int(
            self.estimated_tokens, "request estimated_tokens"
        )
        self.estimated_compute = _non_negative_int(
            self.estimated_compute, "request estimated_compute"
        )
        self.requested_depth = _thinking_depth(
            self.requested_depth, optional=True
        )
        if (
            self.session_type is ResourceSessionType.THINKING
            and self.requested_depth is None
        ):
            raise ResourceValidationError("thinking requests require requested_depth")
        if (
            self.session_type is not ResourceSessionType.THINKING
            and self.requested_depth is not None
        ):
            raise ResourceValidationError(
                "requested_depth is only valid for thinking requests"
            )
        if self.requested_at.tzinfo is None:
            raise ResourceValidationError("request time must include a timezone")

    @classmethod
    def create(
        cls,
        *,
        subject_id: str,
        session_id: str,
        session_type: ResourceSessionType,
        estimated_tokens: int,
        estimated_compute: int,
        model_name: str,
        reason: str,
        requested_at: datetime,
        requested_depth: ThinkingDepth | None = None,
        request_id: str | None = None,
    ) -> ResourceRequest:
        return cls(
            request_id=request_id or str(uuid4()),
            subject_id=subject_id,
            session_id=session_id,
            session_type=session_type,
            estimated_tokens=estimated_tokens,
            estimated_compute=estimated_compute,
            model_name=model_name,
            reason=reason,
            requested_at=requested_at,
            requested_depth=requested_depth,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "session_type": self.session_type.value,
            "estimated_tokens": self.estimated_tokens,
            "estimated_compute": self.estimated_compute,
            "model_name": self.model_name,
            "reason": self.reason,
            "requested_at": _format_datetime(self.requested_at),
            "requested_depth": (
                self.requested_depth.value if self.requested_depth is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceRequest:
        if not isinstance(value, dict):
            raise ResourceValidationError("resource request must be an object")
        return cls(
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            session_id=value.get("session_id"),
            session_type=value.get("session_type"),
            estimated_tokens=value.get("estimated_tokens"),
            estimated_compute=value.get("estimated_compute"),
            model_name=value.get("model_name"),
            reason=value.get("reason"),
            requested_at=_parse_datetime(value.get("requested_at"), "requested_at"),
            requested_depth=_thinking_depth(
                value.get("requested_depth"), optional=True
            ),
        )


@dataclass(slots=True)
class ResourceDecision:
    decision_id: str
    request_id: str
    subject_id: str
    session_id: str
    allowed: bool
    approved_depth: ThinkingDepth | None
    allocated_tokens: int
    allocated_compute: int
    lower_frequency: bool
    defer: bool
    reason: str
    recommended_mode: RuntimeMode
    decided_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.decision_id, "resource decision_id"),
            (self.request_id, "decision request_id"),
            (self.subject_id, "decision subject_id"),
            (self.session_id, "decision session_id"),
            (self.reason, "resource decision reason"),
        ):
            _require_text(value, name)
        if not isinstance(self.allowed, bool) or not isinstance(
            self.lower_frequency, bool
        ) or not isinstance(self.defer, bool):
            raise ResourceValidationError("resource decision flags must be booleans")
        self.approved_depth = _thinking_depth(self.approved_depth, optional=True)
        self.allocated_tokens = _non_negative_int(
            self.allocated_tokens, "allocated_tokens"
        )
        self.allocated_compute = _non_negative_int(
            self.allocated_compute, "allocated_compute"
        )
        if self.allowed and self.defer:
            raise ResourceValidationError("an allowed request cannot also be deferred")
        if not self.allowed and (self.allocated_tokens or self.allocated_compute):
            raise ResourceValidationError("a blocked request cannot allocate resources")
        self.recommended_mode = _runtime_mode(self.recommended_mode)
        if self.decided_at.tzinfo is None:
            raise ResourceValidationError("decision time must include a timezone")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "allowed": self.allowed,
            "approved_depth": (
                self.approved_depth.value if self.approved_depth is not None else None
            ),
            "allocated_tokens": self.allocated_tokens,
            "allocated_compute": self.allocated_compute,
            "lower_frequency": self.lower_frequency,
            "defer": self.defer,
            "reason": self.reason,
            "recommended_mode": self.recommended_mode.value,
            "decided_at": _format_datetime(self.decided_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceDecision:
        if not isinstance(value, dict):
            raise ResourceValidationError("resource decision must be an object")
        return cls(
            decision_id=value.get("decision_id"),
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            session_id=value.get("session_id"),
            allowed=value.get("allowed"),
            approved_depth=_thinking_depth(
                value.get("approved_depth"), optional=True
            ),
            allocated_tokens=value.get("allocated_tokens"),
            allocated_compute=value.get("allocated_compute"),
            lower_frequency=value.get("lower_frequency"),
            defer=value.get("defer"),
            reason=value.get("reason"),
            recommended_mode=value.get("recommended_mode"),
            decided_at=_parse_datetime(value.get("decided_at"), "decided_at"),
        )


@dataclass(slots=True)
class ResourceAllocation:
    state: ResourceState
    request: ResourceRequest
    decision: ResourceDecision
    usage: TokenUsageRecord | None = None

    def __post_init__(self) -> None:
        if (
            self.state.subject_id != self.request.subject_id
            or self.decision.subject_id != self.request.subject_id
            or self.decision.request_id != self.request.request_id
        ):
            raise ResourceValidationError("resource allocation references do not match")
        if self.decision.allowed != (self.usage is not None):
            raise ResourceValidationError(
                "allowed resource allocations require exactly one usage record"
            )
        if self.usage is not None and (
            self.usage.subject_id != self.request.subject_id
            or self.usage.session_id != self.request.session_id
        ):
            raise ResourceValidationError("usage record does not match allocation")
