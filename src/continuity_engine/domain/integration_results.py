from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .errors import MachineContractValidationError
from .events import JsonValue
from .integration_hashing import (
    calculate_projection_content_hash,
    verify_declared_hash,
)


CONTRACT_VERSION = "continuity-integration/v1.1"
PROJECTION_SCHEMA_VERSION = "engine-subject-state-projection/first-round-v1"
SNAPSHOT_SCHEMA_VERSION = 1
FIRST_ROUND_BINDING_VERSION = 1
COMPLETED_STATUS = "completed"
FAILED_TERMINAL_STATUS = "failed_terminal"
SUBJECT_ROLE = "subject"

_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_UTC_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


def _object(value: Any, field_name: str, expected_keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MachineContractValidationError(f"{field_name} must be an object")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unknown = sorted(actual_keys - expected_keys)
        details: list[str] = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise MachineContractValidationError(
            f"{field_name} has an invalid shape ({'; '.join(details)})"
        )
    return value


def _text(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = "a string" if allow_empty else "a non-empty string"
        raise MachineContractValidationError(f"{field_name} must be {suffix}")
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MachineContractValidationError(
            f"{field_name} must be a non-negative integer"
        )
    return value


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise MachineContractValidationError(f"{field_name} must be a boolean")
    return value


def _nullable_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _hash(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise MachineContractValidationError(
            f"{field_name} must use sha256: followed by 64 lowercase hexadecimal digits"
        )
    return value


def _utc_datetime(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _UTC_DATETIME_PATTERN.fullmatch(value) is None:
        raise MachineContractValidationError(
            f"{field_name} must be an RFC 3339 UTC timestamp ending in uppercase Z"
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MachineContractValidationError(
            f"{field_name} must be a valid RFC 3339 UTC timestamp"
        ) from exc
    return value


def format_contract_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MachineContractValidationError("contract timestamps must include a timezone")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class FirstRoundSubjectResponse:
    response_id: str
    content: str

    def __post_init__(self) -> None:
        _text(self.response_id, "response.responseId")
        _text(self.content, "response.content", allow_empty=True)

    @property
    def role(self) -> str:
        return SUBJECT_ROLE

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "responseId": self.response_id,
            "role": self.role,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, value: Any) -> FirstRoundSubjectResponse:
        data = _object(
            value,
            "response",
            {"responseId", "role", "content"},
        )
        if data["role"] != SUBJECT_ROLE:
            raise MachineContractValidationError("response.role must be subject")
        return cls(
            response_id=_text(data["responseId"], "response.responseId"),
            content=_text(data["content"], "response.content", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class SubjectStateProjectionSnapshot:
    subject_id: str
    revision: int
    state_hash: str

    def __post_init__(self) -> None:
        _text(self.subject_id, "stateProjection.snapshot.subjectId")
        _integer(self.revision, "stateProjection.snapshot.revision")
        _hash(self.state_hash, "stateProjection.snapshot.stateHash")

    @property
    def schema_version(self) -> int:
        return SNAPSHOT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "subjectId": self.subject_id,
            "revision": self.revision,
            "stateHash": self.state_hash,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SubjectStateProjectionSnapshot:
        data = _object(
            value,
            "stateProjection.snapshot",
            {"schemaVersion", "subjectId", "revision", "stateHash"},
        )
        if data["schemaVersion"] != SNAPSHOT_SCHEMA_VERSION:
            raise MachineContractValidationError(
                "stateProjection.snapshot.schemaVersion must be 1"
            )
        return cls(
            subject_id=_text(
                data["subjectId"], "stateProjection.snapshot.subjectId"
            ),
            revision=_integer(
                data["revision"], "stateProjection.snapshot.revision"
            ),
            state_hash=_hash(
                data["stateHash"], "stateProjection.snapshot.stateHash"
            ),
        )


@dataclass(frozen=True, slots=True)
class SubjectStateProjection:
    subject_id: str
    binding_id: str
    binding_version: int
    previous_revision: int
    current_revision: int
    changed: bool
    engine_update_id: str | None
    snapshot: SubjectStateProjectionSnapshot
    content_hash: str

    def __post_init__(self) -> None:
        _text(self.subject_id, "stateProjection.subjectId")
        _text(self.binding_id, "stateProjection.bindingId")
        if self.binding_version != FIRST_ROUND_BINDING_VERSION:
            raise MachineContractValidationError(
                "stateProjection.bindingVersion must be 1"
            )
        _integer(self.previous_revision, "stateProjection.previousRevision")
        _integer(self.current_revision, "stateProjection.currentRevision")
        _boolean(self.changed, "stateProjection.changed")
        _nullable_text(self.engine_update_id, "stateProjection.engineUpdateId")
        _hash(self.content_hash, "stateProjection.contentHash")
        verify_declared_hash(
            declared=self.content_hash,
            calculated=calculate_projection_content_hash(self.snapshot),
            field_name="stateProjection.contentHash",
        )
        if self.snapshot.subject_id != self.subject_id:
            raise MachineContractValidationError(
                "stateProjection.snapshot.subjectId must match stateProjection.subjectId"
            )
        if self.snapshot.revision != self.current_revision:
            raise MachineContractValidationError(
                "stateProjection.snapshot.revision must match currentRevision"
            )
        if self.changed:
            if self.current_revision != self.previous_revision + 1:
                raise MachineContractValidationError(
                    "a changed projection must advance revision exactly once"
                )
            if self.engine_update_id is None:
                raise MachineContractValidationError(
                    "a changed projection requires engineUpdateId"
                )
        else:
            if self.current_revision != self.previous_revision:
                raise MachineContractValidationError(
                    "an unchanged projection must retain the revision"
                )
            if self.engine_update_id is not None:
                raise MachineContractValidationError(
                    "an unchanged projection requires engineUpdateId to be null"
                )

    @property
    def schema_version(self) -> str:
        return PROJECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "bindingVersion": self.binding_version,
            "previousRevision": self.previous_revision,
            "currentRevision": self.current_revision,
            "changed": self.changed,
            "engineUpdateId": self.engine_update_id,
            "snapshot": self.snapshot.to_dict(),
            "contentHash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SubjectStateProjection:
        data = _object(
            value,
            "stateProjection",
            {
                "schemaVersion",
                "subjectId",
                "bindingId",
                "bindingVersion",
                "previousRevision",
                "currentRevision",
                "changed",
                "engineUpdateId",
                "snapshot",
                "contentHash",
            },
        )
        if data["schemaVersion"] != PROJECTION_SCHEMA_VERSION:
            raise MachineContractValidationError(
                "unsupported stateProjection.schemaVersion"
            )
        return cls(
            subject_id=_text(data["subjectId"], "stateProjection.subjectId"),
            binding_id=_text(data["bindingId"], "stateProjection.bindingId"),
            binding_version=_integer(
                data["bindingVersion"], "stateProjection.bindingVersion"
            ),
            previous_revision=_integer(
                data["previousRevision"], "stateProjection.previousRevision"
            ),
            current_revision=_integer(
                data["currentRevision"], "stateProjection.currentRevision"
            ),
            changed=_boolean(data["changed"], "stateProjection.changed"),
            engine_update_id=_nullable_text(
                data["engineUpdateId"], "stateProjection.engineUpdateId"
            ),
            snapshot=SubjectStateProjectionSnapshot.from_dict(data["snapshot"]),
            content_hash=_hash(
                data["contentHash"], "stateProjection.contentHash"
            ),
        )


@dataclass(frozen=True, slots=True)
class FirstRoundSuccessResult:
    request_id: str
    request_hash: str
    operation_id: str
    subject_id: str
    binding_id: str
    binding_version: int
    response: FirstRoundSubjectResponse
    state_projection: SubjectStateProjection
    consumed_observation_ids: tuple[str, ...]
    completed_at: str

    def __post_init__(self) -> None:
        _text(self.request_id, "requestId")
        _hash(self.request_hash, "requestHash")
        _text(self.operation_id, "operationId")
        _text(self.subject_id, "subjectId")
        _text(self.binding_id, "bindingId")
        if self.binding_version != FIRST_ROUND_BINDING_VERSION:
            raise MachineContractValidationError("bindingVersion must be 1")
        if (
            not isinstance(self.consumed_observation_ids, tuple)
            or len(self.consumed_observation_ids) != 1
        ):
            raise MachineContractValidationError(
                "consumedObservationIds must contain exactly one item"
            )
        _text(self.consumed_observation_ids[0], "consumedObservationIds[0]")
        _utc_datetime(self.completed_at, "completedAt")
        if self.state_projection.subject_id != self.subject_id:
            raise MachineContractValidationError(
                "stateProjection.subjectId must match result subjectId"
            )
        if self.state_projection.binding_id != self.binding_id:
            raise MachineContractValidationError(
                "stateProjection.bindingId must match result bindingId"
            )
        if self.state_projection.binding_version != self.binding_version:
            raise MachineContractValidationError(
                "stateProjection.bindingVersion must match result bindingVersion"
            )

    @property
    def contract_version(self) -> str:
        return CONTRACT_VERSION

    @property
    def status(self) -> str:
        return COMPLETED_STATUS

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "status": self.status,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "bindingVersion": self.binding_version,
            "response": self.response.to_dict(),
            "stateProjection": self.state_projection.to_dict(),
            "consumedObservationIds": list(self.consumed_observation_ids),
            "completedAt": self.completed_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> FirstRoundSuccessResult:
        data = _object(
            value,
            "completed result",
            {
                "contractVersion",
                "requestId",
                "requestHash",
                "operationId",
                "status",
                "subjectId",
                "bindingId",
                "bindingVersion",
                "response",
                "stateProjection",
                "consumedObservationIds",
                "completedAt",
            },
        )
        if data["contractVersion"] != CONTRACT_VERSION:
            raise MachineContractValidationError("unsupported contractVersion")
        if data["status"] != COMPLETED_STATUS:
            raise MachineContractValidationError(
                "persisted success result status must be completed"
            )
        observations = data["consumedObservationIds"]
        if not isinstance(observations, list):
            raise MachineContractValidationError(
                "consumedObservationIds must be an array"
            )
        return cls(
            request_id=_text(data["requestId"], "requestId"),
            request_hash=_hash(data["requestHash"], "requestHash"),
            operation_id=_text(data["operationId"], "operationId"),
            subject_id=_text(data["subjectId"], "subjectId"),
            binding_id=_text(data["bindingId"], "bindingId"),
            binding_version=_integer(data["bindingVersion"], "bindingVersion"),
            response=FirstRoundSubjectResponse.from_dict(data["response"]),
            state_projection=SubjectStateProjection.from_dict(
                data["stateProjection"]
            ),
            consumed_observation_ids=tuple(observations),
            completed_at=_utc_datetime(data["completedAt"], "completedAt"),
        )


class FirstRoundErrorCode(str, Enum):
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SUBJECT_BINDING_MISMATCH = "SUBJECT_BINDING_MISMATCH"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"


class FirstRoundRetryClass(str, Enum):
    NEVER = "never"
    REASSEMBLE = "reassemble"


_ERROR_RULES: dict[FirstRoundErrorCode, tuple[str, FirstRoundRetryClass]] = {
    FirstRoundErrorCode.SCHEMA_INVALID: (
        "Request schema is invalid.",
        FirstRoundRetryClass.NEVER,
    ),
    FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH: (
        "Subject binding does not match.",
        FirstRoundRetryClass.NEVER,
    ),
    FirstRoundErrorCode.REVISION_CONFLICT: (
        "Engine revision does not match.",
        FirstRoundRetryClass.REASSEMBLE,
    ),
    FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED: (
        "requestId is already bound to a different requestHash.",
        FirstRoundRetryClass.NEVER,
    ),
}


@dataclass(frozen=True, slots=True)
class FirstRoundError:
    code: FirstRoundErrorCode
    message: str
    retry_class: FirstRoundRetryClass
    current_engine_revision: int | None
    current_binding_version: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, FirstRoundErrorCode):
            raise MachineContractValidationError(
                "error.code is not a first-round error code"
            )
        if not isinstance(self.retry_class, FirstRoundRetryClass):
            raise MachineContractValidationError("error.retryClass is not valid")
        expected_message, expected_retry = _ERROR_RULES[self.code]
        if self.message != expected_message:
            raise MachineContractValidationError(
                f"error.message is fixed for {self.code.value}"
            )
        if self.retry_class is not expected_retry:
            raise MachineContractValidationError(
                f"error.retryClass is fixed for {self.code.value}"
            )
        if self.code is FirstRoundErrorCode.REVISION_CONFLICT:
            if self.current_engine_revision is None:
                raise MachineContractValidationError(
                    "REVISION_CONFLICT requires currentEngineRevision"
                )
            _integer(self.current_engine_revision, "error.currentEngineRevision")
        elif self.current_engine_revision is not None:
            raise MachineContractValidationError(
                f"{self.code.value} requires currentEngineRevision to be null"
            )
        if self.current_binding_version is not None:
            raise MachineContractValidationError(
                "first-round errors require currentBindingVersion to be null"
            )

    @classmethod
    def create(
        cls,
        code: FirstRoundErrorCode,
        *,
        current_engine_revision: int | None = None,
    ) -> FirstRoundError:
        if not isinstance(code, FirstRoundErrorCode):
            raise MachineContractValidationError(
                "error.code is not a first-round error code"
            )
        message, retry_class = _ERROR_RULES[code]
        return cls(
            code=code,
            message=message,
            retry_class=retry_class,
            current_engine_revision=current_engine_revision,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryClass": self.retry_class.value,
            "currentEngineRevision": self.current_engine_revision,
            "currentBindingVersion": self.current_binding_version,
        }

    @classmethod
    def from_dict(cls, value: Any) -> FirstRoundError:
        data = _object(
            value,
            "error",
            {
                "code",
                "message",
                "retryClass",
                "currentEngineRevision",
                "currentBindingVersion",
            },
        )
        try:
            code = FirstRoundErrorCode(data["code"])
        except (TypeError, ValueError) as exc:
            raise MachineContractValidationError(
                "error.code is not a first-round error code"
            ) from exc
        try:
            retry_class = FirstRoundRetryClass(data["retryClass"])
        except (TypeError, ValueError) as exc:
            raise MachineContractValidationError(
                "error.retryClass is not valid"
            ) from exc
        current_revision = data["currentEngineRevision"]
        if current_revision is not None:
            current_revision = _integer(
                current_revision, "error.currentEngineRevision"
            )
        current_binding_version = data["currentBindingVersion"]
        if current_binding_version is not None:
            current_binding_version = _integer(
                current_binding_version, "error.currentBindingVersion"
            )
        return cls(
            code=code,
            message=_text(data["message"], "error.message"),
            retry_class=retry_class,
            current_engine_revision=current_revision,
            current_binding_version=current_binding_version,
        )


@dataclass(frozen=True, slots=True)
class FirstRoundErrorEnvelope:
    request_id: str
    error: FirstRoundError

    def __post_init__(self) -> None:
        _text(self.request_id, "requestId")

    @property
    def contract_version(self) -> str:
        return CONTRACT_VERSION

    @property
    def status(self) -> str:
        return FAILED_TERMINAL_STATUS

    @classmethod
    def create(
        cls,
        request_id: str,
        code: FirstRoundErrorCode,
        *,
        current_engine_revision: int | None = None,
    ) -> FirstRoundErrorEnvelope:
        return cls(
            request_id=request_id,
            error=FirstRoundError.create(
                code,
                current_engine_revision=current_engine_revision,
            ),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "requestId": self.request_id,
            "operationId": None,
            "status": self.status,
            "error": self.error.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> FirstRoundErrorEnvelope:
        data = _object(
            value,
            "error envelope",
            {"contractVersion", "requestId", "operationId", "status", "error"},
        )
        if data["contractVersion"] != CONTRACT_VERSION:
            raise MachineContractValidationError("unsupported contractVersion")
        if data["operationId"] is not None:
            raise MachineContractValidationError(
                "first-round error operationId must be null"
            )
        if data["status"] != FAILED_TERMINAL_STATUS:
            raise MachineContractValidationError(
                "first-round error status must be failed_terminal"
            )
        return cls(
            request_id=_text(data["requestId"], "requestId"),
            error=FirstRoundError.from_dict(data["error"]),
        )


class LedgerLookupStatus(str, Enum):
    NOT_FOUND = "not_found"
    COMPLETED = "completed"
    HASH_CONFLICT = "hash_conflict"


@dataclass(frozen=True, slots=True)
class LedgerLookupResult:
    status: LedgerLookupStatus
    result: FirstRoundSuccessResult | None = None

    def __post_init__(self) -> None:
        if self.status is LedgerLookupStatus.COMPLETED and self.result is None:
            raise MachineContractValidationError(
                "a completed ledger lookup requires the persisted result"
            )
        if self.status is not LedgerLookupStatus.COMPLETED and self.result is not None:
            raise MachineContractValidationError(
                "non-completed ledger lookups cannot expose a result"
            )
