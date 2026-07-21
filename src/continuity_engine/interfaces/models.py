from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from continuity_engine.domain.events import JsonValue, StateSection
from continuity_engine.domain.thinking import ThinkingDepth


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("interface timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ExternalOperation(str, Enum):
    GET_SUBJECT_STATE = "GET_SUBJECT_STATE"
    QUERY_MEMORY = "QUERY_MEMORY"
    GET_PERCEPTION = "GET_PERCEPTION"
    REQUEST_THINKING = "REQUEST_THINKING"
    GET_ACTION_PLAN = "GET_ACTION_PLAN"
    TRIGGER_MANUAL_WAKE = "TRIGGER_MANUAL_WAKE"
    SUBMIT_MESSAGE = "SUBMIT_MESSAGE"


class InterfaceCapability(str, Enum):
    READ_SUBJECT_STATE = "subject_state:read"
    QUERY_MEMORY = "memory:request"
    READ_PERCEPTION = "perception:read"
    REQUEST_THINKING = "thinking:request"
    READ_ACTION_PLAN = "action:read"
    TRIGGER_WAKE = "wake:trigger"
    SUBMIT_INTERACTION = "interaction:submit"


@dataclass(slots=True, kw_only=True)
class APIRequest:
    subject_id: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    confirmed: bool = False

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.subject_id, "subject_id")
        if not isinstance(self.confirmed, bool):
            raise ValueError("confirmed must be a boolean")


@dataclass(slots=True, kw_only=True)
class SubjectStateAPIRequest(APIRequest):
    pass


@dataclass(slots=True, kw_only=True)
class MemoryAPIRequest(APIRequest):
    query: str
    desired_scope: list[StateSection] = field(default_factory=list)
    limit: int = 5
    minimum_relevance: float = 0.5
    context: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super(MemoryAPIRequest, self).__post_init__()
        _require_text(self.query, "memory query")
        try:
            self.desired_scope = [
                item if isinstance(item, StateSection) else StateSection(item)
                for item in self.desired_scope
            ]
        except (TypeError, ValueError) as exc:
            raise ValueError("desired_scope contains an unsupported section") from exc
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not isinstance(self.minimum_relevance, (int, float)) or not 0 <= float(
            self.minimum_relevance
        ) <= 1:
            raise ValueError("minimum_relevance must be between zero and one")
        self.minimum_relevance = float(self.minimum_relevance)
        if not isinstance(self.context, dict) or any(
            not isinstance(key, str) for key in self.context
        ):
            raise ValueError("context must be an object with string keys")
        self.context = dict(self.context)


@dataclass(slots=True, kw_only=True)
class PerceptionAPIRequest(APIRequest):
    pass


@dataclass(slots=True, kw_only=True)
class ThinkingAPIRequest(APIRequest):
    depth: ThinkingDepth = ThinkingDepth.NORMAL

    def __post_init__(self) -> None:
        super(ThinkingAPIRequest, self).__post_init__()
        try:
            self.depth = (
                self.depth
                if isinstance(self.depth, ThinkingDepth)
                else ThinkingDepth(self.depth)
            )
        except ValueError as exc:
            raise ValueError("unsupported thinking depth") from exc


@dataclass(slots=True, kw_only=True)
class ActionPlanAPIRequest(APIRequest):
    pass


@dataclass(slots=True, kw_only=True)
class WakeAPIRequest(APIRequest):
    cycle_id: str
    detail: str

    def __post_init__(self) -> None:
        super(WakeAPIRequest, self).__post_init__()
        _require_text(self.cycle_id, "cycle_id")
        _require_text(self.detail, "wake detail")


@dataclass(slots=True, kw_only=True)
class ChatAPIRequest(APIRequest):
    cycle_id: str
    message: str
    expected_revision: int
    user_id: str | None = None
    depth: ThinkingDepth = ThinkingDepth.NORMAL

    def __post_init__(self) -> None:
        super(ChatAPIRequest, self).__post_init__()
        _require_text(self.cycle_id, "cycle_id")
        _require_text(self.message, "message")
        if len(self.message) > 10_000:
            raise ValueError("message must not exceed 10000 characters")
        if not isinstance(self.expected_revision, int) or self.expected_revision < 0:
            raise ValueError("expected_revision must be non-negative")
        if self.user_id is not None:
            _require_text(self.user_id, "user_id")
        try:
            self.depth = (
                self.depth
                if isinstance(self.depth, ThinkingDepth)
                else ThinkingDepth(self.depth)
            )
        except ValueError as exc:
            raise ValueError("unsupported thinking depth") from exc


@dataclass(frozen=True, slots=True)
class APIError:
    code: str
    message: str
    details: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.code, "error code")
        _require_text(self.message, "error message")
        if not isinstance(self.details, dict) or any(
            not isinstance(key, str) for key in self.details
        ):
            raise ValueError("error details must be an object")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class APIResponse:
    request_id: str
    subject_id: str
    timestamp: datetime
    current_revision: int | None
    result: JsonValue | None
    error: APIError | None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "response request_id")
        _require_text(self.subject_id, "response subject_id")
        if self.timestamp.tzinfo is None:
            raise ValueError("response timestamp must include a timezone")
        if self.current_revision is not None and (
            not isinstance(self.current_revision, int) or self.current_revision < 0
        ):
            raise ValueError("current_revision must be non-negative or null")
        if (self.result is None) == (self.error is None):
            raise ValueError("a response must contain exactly one of result or error")

    @property
    def successful(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "timestamp": _format_datetime(self.timestamp),
            "current_revision": self.current_revision,
            "result": self.result,
            "error": self.error.to_dict() if self.error is not None else None,
        }
