from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .errors import PermissionValidationError
from .events import Event, JsonValue


class PermissionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    LIMITED = "LIMITED"
    EXPIRED = "EXPIRED"


class PermissionChangeType(str, Enum):
    GRANTED = "GRANTED"
    STATUS_CHANGED = "STATUS_CHANGED"
    LIMITED = "LIMITED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SCOPE_CHANGED = "SCOPE_CHANGED"
    CAPABILITIES_CHANGED = "CAPABILITIES_CHANGED"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PermissionValidationError(f"{field_name} must be a non-empty string")
    return value


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PermissionValidationError(
            f"{field_name} must be a list of non-empty strings"
        )
    return list(dict.fromkeys(value))


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise PermissionValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(
    value: Any,
    field_name: str,
    *,
    optional: bool = False,
) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise PermissionValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PermissionValidationError(f"{field_name} is not a valid datetime") from exc
    if parsed.tzinfo is None:
        raise PermissionValidationError(f"{field_name} must include a timezone")
    return parsed


def _json_snapshot(value: Any, field_name: str, *, optional: bool = False):
    if value is None and optional:
        return None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise PermissionValidationError(f"{field_name} must be an object")
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise PermissionValidationError(
            f"{field_name} must contain JSON-compatible values"
        ) from exc
    return dict(value)


@dataclass(slots=True)
class PermissionState:
    permission_id: str
    subject_id: str
    permission_type: str
    name: str
    description: str
    scope: list[str]
    capabilities: list[str]
    status: PermissionStatus
    granted_at: datetime
    revoked_at: datetime | None
    source: str
    revision: int = 0

    def __post_init__(self) -> None:
        for value, name in (
            (self.permission_id, "permission_id"),
            (self.subject_id, "permission subject_id"),
            (self.permission_type, "permission_type"),
            (self.name, "permission name"),
            (self.description, "permission description"),
            (self.source, "permission source"),
        ):
            _require_text(value, name)
        self.scope = _text_list(self.scope, "permission scope")
        self.capabilities = _text_list(
            self.capabilities, "permission capabilities"
        )
        try:
            self.status = (
                self.status
                if isinstance(self.status, PermissionStatus)
                else PermissionStatus(self.status)
            )
        except ValueError as exc:
            raise PermissionValidationError("unsupported permission status") from exc
        if self.granted_at.tzinfo is None:
            raise PermissionValidationError("granted_at must include a timezone")
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            raise PermissionValidationError("revoked_at must include a timezone")
        if self.status is PermissionStatus.REVOKED and self.revoked_at is None:
            raise PermissionValidationError("revoked permission requires revoked_at")
        if self.status is not PermissionStatus.REVOKED and self.revoked_at is not None:
            raise PermissionValidationError(
                "revoked_at is only valid while permission status is REVOKED"
            )
        if not isinstance(self.revision, int) or self.revision < 0:
            raise PermissionValidationError("permission revision must be non-negative")

    @property
    def is_available(self) -> bool:
        return self.status in (PermissionStatus.ACTIVE, PermissionStatus.LIMITED)

    def allows(self, capability: str, scope: str | None = None) -> bool:
        _require_text(capability, "capability")
        if not self.is_available or capability not in self.capabilities:
            return False
        if scope is None:
            return True
        _require_text(scope, "capability scope")
        return "*" in self.scope or scope in self.scope

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "permission_id": self.permission_id,
            "subject_id": self.subject_id,
            "permission_type": self.permission_type,
            "name": self.name,
            "description": self.description,
            "scope": list(self.scope),
            "capabilities": list(self.capabilities),
            "status": self.status.value,
            "granted_at": _format_datetime(self.granted_at),
            "revoked_at": _format_datetime(self.revoked_at),
            "source": self.source,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, value: Any) -> PermissionState:
        if not isinstance(value, dict):
            raise PermissionValidationError("permission state must be an object")
        granted_at = _parse_datetime(value.get("granted_at"), "granted_at")
        assert granted_at is not None
        return cls(
            permission_id=value.get("permission_id"),
            subject_id=value.get("subject_id"),
            permission_type=value.get("permission_type"),
            name=value.get("name"),
            description=value.get("description"),
            scope=_text_list(value.get("scope", []), "permission scope"),
            capabilities=_text_list(
                value.get("capabilities", []), "permission capabilities"
            ),
            status=value.get("status"),
            granted_at=granted_at,
            revoked_at=_parse_datetime(
                value.get("revoked_at"), "revoked_at", optional=True
            ),
            source=value.get("source"),
            revision=value.get("revision", 0),
        )


@dataclass(slots=True)
class PermissionChangeRecord:
    record_id: str
    permission_id: str
    change_type: PermissionChangeType
    before_state: dict[str, JsonValue] | None
    after_state: dict[str, JsonValue]
    reason: str
    source: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.record_id, "permission record_id")
        _require_text(self.permission_id, "record permission_id")
        try:
            self.change_type = (
                self.change_type
                if isinstance(self.change_type, PermissionChangeType)
                else PermissionChangeType(self.change_type)
            )
        except ValueError as exc:
            raise PermissionValidationError("unsupported permission change type") from exc
        self.before_state = _json_snapshot(
            self.before_state, "before_state", optional=True
        )
        self.after_state = _json_snapshot(self.after_state, "after_state")
        _require_text(self.reason, "permission change reason")
        _require_text(self.source, "permission change source")
        if self.created_at.tzinfo is None:
            raise PermissionValidationError("change created_at must include a timezone")
        if self.after_state.get("permission_id") != self.permission_id:
            raise PermissionValidationError(
                "permission history snapshot does not match permission_id"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "record_id": self.record_id,
            "permission_id": self.permission_id,
            "change_type": self.change_type.value,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "reason": self.reason,
            "source": self.source,
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> PermissionChangeRecord:
        if not isinstance(value, dict):
            raise PermissionValidationError("permission change record must be an object")
        created_at = _parse_datetime(value.get("created_at"), "change created_at")
        assert created_at is not None
        return cls(
            record_id=value.get("record_id"),
            permission_id=value.get("permission_id"),
            change_type=value.get("change_type"),
            before_state=_json_snapshot(
                value.get("before_state"), "before_state", optional=True
            ),
            after_state=_json_snapshot(value.get("after_state"), "after_state"),
            reason=value.get("reason"),
            source=value.get("source"),
            created_at=created_at,
        )


@dataclass(slots=True)
class PermissionContext:
    subject_id: str
    current_permissions: list[PermissionState]
    available_capabilities: list[str]
    restrictions: list[str]
    recent_changes: list[PermissionChangeRecord]
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.subject_id, "permission context subject_id")
        if any(
            not isinstance(item, PermissionState)
            or item.subject_id != self.subject_id
            or not item.is_available
            for item in self.current_permissions
        ):
            raise PermissionValidationError(
                "PermissionContext contains invalid current permissions"
            )
        self.available_capabilities = _text_list(
            self.available_capabilities, "available capabilities"
        )
        self.restrictions = _text_list(self.restrictions, "permission restrictions")
        if any(
            not isinstance(item, PermissionChangeRecord)
            for item in self.recent_changes
        ):
            raise PermissionValidationError("recent permission changes are invalid")
        if self.created_at.tzinfo is None:
            raise PermissionValidationError("context created_at must include a timezone")

    def has_capability(self, capability: str, scope: str | None = None) -> bool:
        return any(
            permission.allows(capability, scope)
            for permission in self.current_permissions
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "subject_id": self.subject_id,
            "current_permissions": [item.to_dict() for item in self.current_permissions],
            "available_capabilities": list(self.available_capabilities),
            "restrictions": list(self.restrictions),
            "recent_changes": [item.to_dict() for item in self.recent_changes],
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> PermissionContext:
        if not isinstance(value, dict) or not isinstance(
            value.get("current_permissions"), list
        ) or not isinstance(value.get("recent_changes"), list):
            raise PermissionValidationError("permission context has invalid collections")
        created_at = _parse_datetime(value.get("created_at"), "context created_at")
        assert created_at is not None
        return cls(
            subject_id=value.get("subject_id"),
            current_permissions=[
                PermissionState.from_dict(item)
                for item in value["current_permissions"]
            ],
            available_capabilities=_text_list(
                value.get("available_capabilities", []), "available capabilities"
            ),
            restrictions=_text_list(
                value.get("restrictions", []), "permission restrictions"
            ),
            recent_changes=[
                PermissionChangeRecord.from_dict(item)
                for item in value["recent_changes"]
            ],
            created_at=created_at,
        )


@dataclass(slots=True)
class PermissionChangeResult:
    permission: PermissionState
    record: PermissionChangeRecord
    event: Event
