"""W04-1 internal attachment and history contracts; never Subject authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .action_planning import digest, exact, identifier
from .capability import parse_capability_datetime
from .errors import CapabilityValidationError


class EnvironmentAccessError(CapabilityValidationError):
    """Only stable codes cross an external attachment boundary."""


class AttachmentKind(str, Enum):
    MESSAGE_INGRESS = "MESSAGE_INGRESS"
    TOOL_EGRESS = "TOOL_EGRESS"
    MODEL_API = "MODEL_API"
    ENGINE_INTEGRATION = "ENGINE_INTEGRATION"
    BODY = "BODY"


class DiscoveryState(str, Enum):
    HEARD_OF = "HEARD_OF"
    DISCOVERED = "DISCOVERED"
    CONNECTED = "CONNECTED"


class BodyKind(str, Enum):
    NONE = "NONE"
    SIMULATED = "SIMULATED"
    REAL = "REAL"


class SensationSource(str, Enum):
    BODY_OBSERVATION = "BODY_OBSERVATION"
    INTERNAL_SOMATIC = "INTERNAL_SOMATIC"
    DREAM_SIMULATION = "DREAM_SIMULATION"


def _optional_id(value: str | None) -> None:
    if value is not None:
        identifier(value)


@dataclass(frozen=True)
class Ability:
    name: str
    direction: str
    unit: str | None
    coordinate: str | None
    lower: float | None
    upper: float | None
    sampled_at: str | None
    valid_until: str | None
    value: float | None = None

    def __post_init__(self):
        identifier(self.name)
        if self.direction not in {"INPUT", "OUTPUT"}:
            raise EnvironmentAccessError("W04_ABILITY_DIRECTION")
        for item in (self.unit, self.coordinate):
            _optional_id(item)
        for item in (self.lower, self.upper, self.value):
            if item is not None and (type(item) not in (int, float) or not __import__("math").isfinite(item)):
                raise EnvironmentAccessError("W04_ABILITY_VALUE")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise EnvironmentAccessError("W04_ABILITY_RANGE")
        if self.value is not None and ((self.lower is not None and self.value < self.lower)
                                       or (self.upper is not None and self.value > self.upper)):
            raise EnvironmentAccessError("W04_ABILITY_VALUE")
        if (self.sampled_at is None) != (self.valid_until is None):
            raise EnvironmentAccessError("W04_ABILITY_TIME")
        if self.sampled_at is not None:
            if parse_capability_datetime(self.valid_until) <= parse_capability_datetime(self.sampled_at):
                raise EnvironmentAccessError("W04_ABILITY_TIME")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**exact(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class Attachment:
    attachment_id: str
    subject_id: str
    environment: str
    kind: AttachmentKind
    state: DiscoveryState
    host_id: str
    channel_id: str
    software_id: str | None
    device_id: str | None
    account_id: str | None
    session_id: str | None
    body_kind: BodyKind
    generation: int
    purposes: tuple[str, ...]
    read_scopes: tuple[str, ...]
    abilities: tuple[Ability, ...]
    valid_from: str
    expires_at: str
    permission_ref: str | None
    enabled: bool = True

    def __post_init__(self):
        for value in (self.attachment_id, self.subject_id, self.host_id, self.channel_id):
            identifier(value)
        for value in (self.software_id, self.device_id, self.account_id, self.session_id, self.permission_ref):
            _optional_id(value)
        if self.environment not in {"TEST", "RESEARCH"}:
            raise EnvironmentAccessError("W04_ENVIRONMENT_UNSUPPORTED")
        if not isinstance(self.kind, AttachmentKind) or not isinstance(self.state, DiscoveryState):
            raise EnvironmentAccessError("W04_ATTACHMENT_KIND")
        if not isinstance(self.body_kind, BodyKind) or (self.kind is AttachmentKind.BODY) != (self.body_kind is not BodyKind.NONE):
            raise EnvironmentAccessError("W04_BODY_KIND")
        if self.kind is AttachmentKind.BODY and self.device_id is None:
            raise EnvironmentAccessError("W04_BODY_ID_REQUIRED")
        if self.kind in {AttachmentKind.MESSAGE_INGRESS, AttachmentKind.ENGINE_INTEGRATION} and self.session_id is None:
            raise EnvironmentAccessError("W04_SESSION_REQUIRED")
        if type(self.generation) is not int or self.generation < 1 or type(self.enabled) is not bool:
            raise EnvironmentAccessError("W04_GENERATION_INVALID")
        for group in (self.purposes, self.read_scopes):
            if not isinstance(group, tuple) or len(group) > 32 or len(group) != len(set(group)):
                raise EnvironmentAccessError("W04_SCOPE_INVALID")
            for value in group:
                identifier(value)
        if len(self.abilities) > 64 or len({a.name for a in self.abilities}) != len(self.abilities):
            raise EnvironmentAccessError("W04_ABILITY_DUPLICATE")
        if any(not isinstance(a, Ability) for a in self.abilities):
            raise EnvironmentAccessError("W04_ABILITY_INVALID")
        if parse_capability_datetime(self.expires_at) <= parse_capability_datetime(self.valid_from):
            raise EnvironmentAccessError("W04_ATTACHMENT_TIME")
        if self.state is DiscoveryState.CONNECTED and self.permission_ref is None:
            raise EnvironmentAccessError("W04_PERMISSION_REFERENCE_REQUIRED")

    def to_dict(self):
        return {**asdict(self), "kind": self.kind.value, "state": self.state.value,
                "body_kind": self.body_kind.value, "purposes": list(self.purposes),
                "read_scopes": list(self.read_scopes), "abilities": [a.to_dict() for a in self.abilities]}

    @classmethod
    def from_dict(cls, value):
        data = exact(value, set(cls.__dataclass_fields__))
        try:
            return cls(**{**data, "kind": AttachmentKind(data["kind"]),
                          "state": DiscoveryState(data["state"]), "body_kind": BodyKind(data["body_kind"]),
                          "purposes": tuple(data["purposes"]), "read_scopes": tuple(data["read_scopes"]),
                          "abilities": tuple(Ability.from_dict(a) for a in data["abilities"])})
        except (TypeError, ValueError, KeyError):
            raise EnvironmentAccessError("W04_ATTACHMENT_CORRUPT") from None

    @property
    def fingerprint(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class AttachmentUse:
    attachment_id: str
    subject_id: str
    environment: str
    generation: int
    host_id: str
    channel_id: str
    software_id: str | None
    device_id: str | None
    account_id: str | None
    session_id: str | None
    purpose: str
    scope: str | None = None

    def __post_init__(self):
        for value in (self.attachment_id, self.subject_id, self.host_id, self.channel_id, self.purpose):
            identifier(value)
        for value in (self.software_id, self.device_id, self.account_id, self.session_id, self.scope):
            _optional_id(value)
        if self.environment not in {"TEST", "RESEARCH"} or type(self.generation) is not int or self.generation < 1:
            raise EnvironmentAccessError("W04_USE_INVALID")


@dataclass(frozen=True)
class HistoryScope:
    query_id: str
    subject_id: str
    environment: str
    object_id: str
    software_id: str | None
    device_id: str | None
    session_id: str | None
    from_at: str | None
    until_at: str | None
    source_ids: tuple[str, ...]
    permission_ref: str
    mode: str
    subject_willing: bool
    user_requested: bool
    limit: int = 8

    def __post_init__(self):
        for value in (self.query_id, self.subject_id, self.object_id, self.permission_ref):
            identifier(value)
        for value in (self.software_id, self.device_id, self.session_id):
            _optional_id(value)
        if self.environment not in {"TEST", "RESEARCH"} or self.mode not in {"LOCAL", "DEEP_ARCHIVE", "EXTERNAL"}:
            raise EnvironmentAccessError("W04_HISTORY_SCOPE")
        if self.mode != "LOCAL" and not (self.subject_willing or self.user_requested):
            raise EnvironmentAccessError("W04_HISTORY_INTENT_REQUIRED")
        if type(self.subject_willing) is not bool or type(self.user_requested) is not bool:
            raise EnvironmentAccessError("W04_HISTORY_INTENT_INVALID")
        if type(self.limit) is not int or not 1 <= self.limit <= 16:
            raise EnvironmentAccessError("W04_HISTORY_LIMIT")
        if len(self.source_ids) != len(set(self.source_ids)) or len(self.source_ids) > 16:
            raise EnvironmentAccessError("W04_HISTORY_SOURCES")
        for value in self.source_ids:
            identifier(value)
        if self.from_at is not None:
            parse_capability_datetime(self.from_at)
        if self.until_at is not None:
            parse_capability_datetime(self.until_at)
        if self.from_at and self.until_at and parse_capability_datetime(self.until_at) < parse_capability_datetime(self.from_at):
            raise EnvironmentAccessError("W04_HISTORY_TIME")


@dataclass(frozen=True)
class MigrationPreparation:
    kind: str
    subject_id: str
    environment: str
    source_host: str | None
    target_host: str
    source_time_ref: str | None
    available: tuple[str, ...]
    required: tuple[str, ...]
    missing: tuple[str, ...]
    source_generation: int | None
    status: str

    def __post_init__(self):
        if self.kind not in {"FIRST_IMPORT", "SAME_SUBJECT_TRANSFER", "NEW_SUBJECT", "ENTRY_SWITCH"}:
            raise EnvironmentAccessError("W04_MIGRATION_KIND")
        identifier(self.subject_id); identifier(self.target_host)
        _optional_id(self.source_host); _optional_id(self.source_time_ref)
        if self.environment not in {"TEST", "RESEARCH"}:
            raise EnvironmentAccessError("W04_MIGRATION_ENVIRONMENT")
        if set(self.missing) != set(self.required) - set(self.available):
            raise EnvironmentAccessError("W04_MIGRATION_INVENTORY")
        if self.status not in {"READY_FOR_ISOLATED_HANDOFF", "DEPENDENCY_MISSING", "NOT_READY_PRODUCTION", "ENTRY_ONLY"}:
            raise EnvironmentAccessError("W04_MIGRATION_STATUS")
        if self.kind == "SAME_SUBJECT_TRANSFER" and (self.source_host is None or self.source_generation is None):
            raise EnvironmentAccessError("W04_MIGRATION_SOURCE_REQUIRED")
        expected = ("DEPENDENCY_MISSING" if self.missing else
                    "READY_FOR_ISOLATED_HANDOFF" if self.kind == "SAME_SUBJECT_TRANSFER" else
                    "ENTRY_ONLY" if self.kind == "ENTRY_SWITCH" else "NOT_READY_PRODUCTION")
        if self.status != expected or (self.kind != "SAME_SUBJECT_TRANSFER" and self.source_generation is not None):
            raise EnvironmentAccessError("W04_MIGRATION_STATUS")

    def to_dict(self):
        return {**asdict(self), "available": list(self.available), "required": list(self.required), "missing": list(self.missing)}
