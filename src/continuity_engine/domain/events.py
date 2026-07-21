from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .errors import StateValidationError


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class StateSection(str, Enum):
    IDENTITY = "identity"
    RELATIONSHIP = "relationship"
    CONTINUITY = "continuity"
    TEMPORAL = "temporal"
    INTENTIONS = "intentions"
    EMOTION_STATE = "emotion_state"


class ChangeOperation(str, Enum):
    SET = "set"
    APPEND = "append"
    REMOVE = "remove"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateValidationError(f"{field_name} must be a non-empty string")
    return value


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise StateValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateValidationError(f"{field_name} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise StateValidationError(f"{field_name} must include a timezone")
    return parsed


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise StateValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_json_value(value: Any, field_name: str) -> JsonValue:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise StateValidationError(f"{field_name} must contain JSON-compatible data") from exc
    return value


@dataclass(slots=True)
class StateMutation:
    field_path: str
    operation: ChangeOperation
    value: JsonValue
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.field_path, "mutation.field_path")
        if "." not in self.field_path:
            raise StateValidationError("mutation.field_path must include a state section")
        if not isinstance(self.operation, ChangeOperation):
            try:
                self.operation = ChangeOperation(self.operation)
            except ValueError as exc:
                raise StateValidationError("mutation.operation is not supported") from exc
        _validate_json_value(self.value, "mutation.value")
        _require_text(self.reason, "mutation.reason")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "field_path": self.field_path,
            "operation": self.operation.value,
            "value": self.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> StateMutation:
        if not isinstance(value, dict):
            raise StateValidationError("mutation must be an object")
        return cls(
            field_path=value.get("field_path"),
            operation=value.get("operation"),
            value=value.get("value"),
            reason=value.get("reason"),
        )


@dataclass(slots=True)
class Event:
    event_id: str
    occurred_at: datetime
    source: str
    event_type: str
    content: str
    impact_scope: list[StateSection]
    mutations: list[StateMutation]
    reason: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        if self.occurred_at.tzinfo is None:
            raise StateValidationError("occurred_at must include a timezone")
        _require_text(self.source, "source")
        _require_text(self.event_type, "event_type")
        _require_text(self.content, "content")
        _require_text(self.reason, "reason")
        if not self.impact_scope:
            raise StateValidationError("impact_scope must contain at least one state section")
        normalized_scope: list[StateSection] = []
        for section in self.impact_scope:
            try:
                normalized = section if isinstance(section, StateSection) else StateSection(section)
            except ValueError as exc:
                raise StateValidationError(f"unsupported impact scope: {section}") from exc
            if normalized not in normalized_scope:
                normalized_scope.append(normalized)
        self.impact_scope = normalized_scope
        if any(not isinstance(mutation, StateMutation) for mutation in self.mutations):
            raise StateValidationError("mutations must contain StateMutation values")
        _validate_json_value(self.metadata, "metadata")

    @classmethod
    def create(
        cls,
        *,
        occurred_at: datetime,
        source: str,
        event_type: str,
        content: str,
        impact_scope: Iterable[StateSection],
        mutations: Iterable[StateMutation],
        reason: str,
        metadata: dict[str, JsonValue] | None = None,
        event_id: str | None = None,
    ) -> Event:
        return cls(
            event_id=event_id or str(uuid4()),
            occurred_at=occurred_at,
            source=source,
            event_type=event_type,
            content=content,
            impact_scope=list(impact_scope),
            mutations=list(mutations),
            reason=reason,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "event_id": self.event_id,
            "occurred_at": _format_datetime(self.occurred_at),
            "source": self.source,
            "event_type": self.event_type,
            "content": self.content,
            "impact_scope": [section.value for section in self.impact_scope],
            "mutations": [mutation.to_dict() for mutation in self.mutations],
            "reason": self.reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Any) -> Event:
        if not isinstance(value, dict):
            raise StateValidationError("event must be an object")
        raw_scope = value.get("impact_scope")
        raw_mutations = value.get("mutations")
        if not isinstance(raw_scope, list):
            raise StateValidationError("impact_scope must be a list")
        if not isinstance(raw_mutations, list):
            raise StateValidationError("mutations must be a list")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise StateValidationError("metadata must be an object")
        return cls(
            event_id=value.get("event_id"),
            occurred_at=_parse_datetime(value.get("occurred_at"), "occurred_at"),
            source=value.get("source"),
            event_type=value.get("event_type"),
            content=value.get("content"),
            impact_scope=[StateSection(section) for section in raw_scope],
            mutations=[StateMutation.from_dict(item) for item in raw_mutations],
            reason=value.get("reason"),
            metadata=metadata,
        )


@dataclass(slots=True)
class FieldChange:
    field_path: str
    operation: ChangeOperation
    before: JsonValue
    after: JsonValue
    reason: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "field_path": self.field_path,
            "operation": self.operation.value,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> FieldChange:
        if not isinstance(value, dict):
            raise StateValidationError("field change must be an object")
        return cls(
            field_path=_require_text(value.get("field_path"), "field_change.field_path"),
            operation=ChangeOperation(value.get("operation")),
            before=_validate_json_value(value.get("before"), "field_change.before"),
            after=_validate_json_value(value.get("after"), "field_change.after"),
            reason=_require_text(value.get("reason"), "field_change.reason"),
        )


@dataclass(slots=True)
class StateUpdateRecord:
    update_id: str
    subject_id: str
    event: Event
    applied_at: datetime
    before_revision: int
    after_revision: int
    changes: list[FieldChange]
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.update_id, "update_id")
        _require_text(self.subject_id, "subject_id")
        if self.applied_at.tzinfo is None:
            raise StateValidationError("applied_at must include a timezone")
        if self.before_revision < 0 or self.after_revision < self.before_revision:
            raise StateValidationError("update revisions are invalid")
        _require_text(self.reason, "update.reason")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "update_id": self.update_id,
            "subject_id": self.subject_id,
            "event": self.event.to_dict(),
            "applied_at": _format_datetime(self.applied_at),
            "before_revision": self.before_revision,
            "after_revision": self.after_revision,
            "changes": [change.to_dict() for change in self.changes],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> StateUpdateRecord:
        if not isinstance(value, dict):
            raise StateValidationError("state update record must be an object")
        raw_changes = value.get("changes")
        if not isinstance(raw_changes, list):
            raise StateValidationError("update.changes must be a list")
        before_revision = value.get("before_revision")
        after_revision = value.get("after_revision")
        if not isinstance(before_revision, int) or not isinstance(after_revision, int):
            raise StateValidationError("update revisions must be integers")
        return cls(
            update_id=value.get("update_id"),
            subject_id=value.get("subject_id"),
            event=Event.from_dict(value.get("event")),
            applied_at=_parse_datetime(value.get("applied_at"), "applied_at"),
            before_revision=before_revision,
            after_revision=after_revision,
            changes=[FieldChange.from_dict(item) for item in raw_changes],
            reason=value.get("reason"),
        )

