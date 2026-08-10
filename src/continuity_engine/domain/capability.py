from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .errors import CapabilityValidationError
from .events import JsonValue
from .integration_hashing import canonicalize_json, sha256_hash


CAPABILITY_CONTRACT_VERSION = "continuity-capability/v1"
CAPABILITY_REQUEST_SCHEMA_VERSION = "continuity-capability-request/v1"
CAPABILITY_RESULT_SCHEMA_VERSION = "continuity-capability-result/v1"
MODEL_OUTPUT_SCHEMA_VERSION = "continuity-model-output/v1"
CAPABILITY_REQUIRED_SCHEMA_VERSION = "continuity-capability-required/v1"
CAPABILITY_FAILED_SCHEMA_VERSION = "continuity-capability-failed/v1"

_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


def _exact_object(value: Any, name: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CapabilityValidationError(f"{name} must be an object")
    actual = set(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise CapabilityValidationError(
            f"{name} has an invalid shape ({'; '.join(details)})"
        )
    return value


def _text(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise CapabilityValidationError(f"{name} must be a non-empty string")
    return value


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CapabilityValidationError(f"{name} must be a non-negative integer")
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise CapabilityValidationError(
            f"{name} must use sha256: followed by 64 lowercase hexadecimal digits"
        )
    return value


def _utc(value: Any, name: str) -> str:
    if not isinstance(value, str) or _UTC_PATTERN.fullmatch(value) is None:
        raise CapabilityValidationError(
            f"{name} must be an RFC 3339 UTC timestamp ending in uppercase Z"
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CapabilityValidationError(f"{name} is not a valid timestamp") from exc
    return value


class CapabilityStatus(str, Enum):
    PROPOSED = "PROPOSED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    SUCCEEDED = "SUCCEEDED"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"

    @property
    def requires_capability(self) -> bool:
        return self in {
            CapabilityStatus.PROPOSED,
            CapabilityStatus.FAILED_RETRYABLE,
            CapabilityStatus.UNKNOWN,
        }

    @property
    def failed_terminally(self) -> bool:
        return self in {
            CapabilityStatus.FAILED_TERMINAL,
            CapabilityStatus.CANCELLED,
            CapabilityStatus.EXPIRED,
        }


class IntegrationThinkingMode(str, Enum):
    DETERMINISTIC = "deterministic"
    CAPABILITY = "capability"


@dataclass(frozen=True, slots=True)
class CapabilityModelInput:
    instruction: str
    message_fact_id: str
    observation_id: str
    message_content: str
    perception_id: str
    perception_summary: str
    current_focus: str
    source_revision: int
    output_schema_version: str
    maximum_output_characters: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.instruction, "input.instruction"),
            (self.message_fact_id, "input.messageFactId"),
            (self.observation_id, "input.observationId"),
            (self.perception_id, "input.perceptionId"),
            (self.perception_summary, "input.perceptionSummary"),
            (self.current_focus, "input.currentFocus"),
        ):
            _text(value, name)
        _text(self.message_content, "input.messageContent", allow_empty=True)
        _integer(self.source_revision, "input.sourceRevision")
        if self.output_schema_version != MODEL_OUTPUT_SCHEMA_VERSION:
            raise CapabilityValidationError(
                "input.outputSchemaVersion must be continuity-model-output/v1"
            )
        if (
            isinstance(self.maximum_output_characters, bool)
            or not isinstance(self.maximum_output_characters, int)
            or not 1 <= self.maximum_output_characters <= 16384
        ):
            raise CapabilityValidationError(
                "input.maximumOutputCharacters must be between 1 and 16384"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "instruction": self.instruction,
            "messageFactId": self.message_fact_id,
            "observationId": self.observation_id,
            "messageContent": self.message_content,
            "perceptionId": self.perception_id,
            "perceptionSummary": self.perception_summary,
            "currentFocus": self.current_focus,
            "sourceRevision": self.source_revision,
            "outputSchemaVersion": self.output_schema_version,
            "maximumOutputCharacters": self.maximum_output_characters,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityModelInput:
        data = _exact_object(
            value,
            "capability input",
            {
                "instruction",
                "messageFactId",
                "observationId",
                "messageContent",
                "perceptionId",
                "perceptionSummary",
                "currentFocus",
                "sourceRevision",
                "outputSchemaVersion",
                "maximumOutputCharacters",
            },
        )
        return cls(
            instruction=data["instruction"],
            message_fact_id=data["messageFactId"],
            observation_id=data["observationId"],
            message_content=data["messageContent"],
            perception_id=data["perceptionId"],
            perception_summary=data["perceptionSummary"],
            current_focus=data["currentFocus"],
            source_revision=data["sourceRevision"],
            output_schema_version=data["outputSchemaVersion"],
            maximum_output_characters=data["maximumOutputCharacters"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    capability_request_id: str
    operation_id: str
    request_id: str
    request_hash: str
    subject_id: str
    binding_id: str
    binding_version: int
    originating_session_id: str
    input: CapabilityModelInput
    input_hash: str
    permission_ref: str
    resource_ref: str
    risk_level: str
    deadline_at: str
    idempotency_key: str
    created_at: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.capability_request_id, "capabilityRequestId"),
            (self.operation_id, "operationId"),
            (self.request_id, "requestId"),
            (self.subject_id, "subjectId"),
            (self.binding_id, "bindingId"),
            (self.originating_session_id, "originatingSessionId"),
            (self.permission_ref, "permissionRef"),
            (self.resource_ref, "resourceRef"),
        ):
            _text(value, name)
        _hash(self.request_hash, "requestHash")
        _hash(self.input_hash, "inputHash")
        _hash(self.idempotency_key, "idempotencyKey")
        if self.binding_version != 1 or isinstance(self.binding_version, bool):
            raise CapabilityValidationError("bindingVersion must be 1")
        if self.risk_level not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise CapabilityValidationError("riskLevel is invalid")
        _utc(self.deadline_at, "deadlineAt")
        _utc(self.created_at, "createdAt")
        if parse_capability_datetime(self.deadline_at) <= parse_capability_datetime(
            self.created_at
        ):
            raise CapabilityValidationError("deadlineAt must be later than createdAt")
        expected_input_hash = calculate_capability_content_hash(self.input)
        if self.input_hash != expected_input_hash:
            raise CapabilityValidationError("inputHash does not match input")

    @property
    def contract_version(self) -> str:
        return CAPABILITY_CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return CAPABILITY_REQUEST_SCHEMA_VERSION

    @property
    def originating_session_type(self) -> str:
        return "thinking"

    @property
    def capability_type(self) -> str:
        return "model.generate"

    @property
    def task_type(self) -> str:
        return "conversation_response"

    @property
    def input_schema_version(self) -> str:
        return "continuity-model-input/v1"

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "schemaVersion": self.schema_version,
            "capabilityRequestId": self.capability_request_id,
            "operationId": self.operation_id,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "bindingVersion": self.binding_version,
            "originatingSessionType": self.originating_session_type,
            "originatingSessionId": self.originating_session_id,
            "capabilityType": self.capability_type,
            "taskType": self.task_type,
            "inputSchemaVersion": self.input_schema_version,
            "input": self.input.to_dict(),
            "inputHash": self.input_hash,
            "permissionRef": self.permission_ref,
            "resourceRef": self.resource_ref,
            "riskLevel": self.risk_level,
            "deadlineAt": self.deadline_at,
            "idempotencyKey": self.idempotency_key,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityRequest:
        fields = {
            "contractVersion", "schemaVersion", "capabilityRequestId",
            "operationId", "requestId", "requestHash", "subjectId",
            "bindingId", "bindingVersion", "originatingSessionType",
            "originatingSessionId", "capabilityType", "taskType",
            "inputSchemaVersion", "input", "inputHash", "permissionRef",
            "resourceRef", "riskLevel", "deadlineAt", "idempotencyKey",
            "createdAt",
        }
        data = _exact_object(value, "CapabilityRequest", fields)
        fixed = {
            "contractVersion": CAPABILITY_CONTRACT_VERSION,
            "schemaVersion": CAPABILITY_REQUEST_SCHEMA_VERSION,
            "originatingSessionType": "thinking",
            "capabilityType": "model.generate",
            "taskType": "conversation_response",
            "inputSchemaVersion": "continuity-model-input/v1",
        }
        for name, expected in fixed.items():
            if data[name] != expected:
                raise CapabilityValidationError(f"{name} is unsupported")
        return cls(
            capability_request_id=data["capabilityRequestId"],
            operation_id=data["operationId"],
            request_id=data["requestId"],
            request_hash=data["requestHash"],
            subject_id=data["subjectId"],
            binding_id=data["bindingId"],
            binding_version=data["bindingVersion"],
            originating_session_id=data["originatingSessionId"],
            input=CapabilityModelInput.from_dict(data["input"]),
            input_hash=data["inputHash"],
            permission_ref=data["permissionRef"],
            resource_ref=data["resourceRef"],
            risk_level=data["riskLevel"],
            deadline_at=data["deadlineAt"],
            idempotency_key=data["idempotencyKey"],
            created_at=data["createdAt"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityProvider:
    provider_type: str
    provider_id: str
    model_name: str

    def __post_init__(self) -> None:
        if self.provider_type != "model":
            raise CapabilityValidationError("provider.providerType must be model")
        _text(self.provider_id, "provider.providerId")
        _text(self.model_name, "provider.modelName")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "providerType": self.provider_type,
            "providerId": self.provider_id,
            "modelName": self.model_name,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityProvider:
        data = _exact_object(
            value, "provider", {"providerType", "providerId", "modelName"}
        )
        return cls(data["providerType"], data["providerId"], data["modelName"])


@dataclass(frozen=True, slots=True)
class CapabilityActualUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def __post_init__(self) -> None:
        _integer(self.input_tokens, "actualUsage.inputTokens")
        _integer(self.output_tokens, "actualUsage.outputTokens")
        _integer(self.total_tokens, "actualUsage.totalTokens")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise CapabilityValidationError(
                "actualUsage.totalTokens must equal inputTokens plus outputTokens"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityActualUsage:
        data = _exact_object(
            value, "actualUsage", {"inputTokens", "outputTokens", "totalTokens"}
        )
        return cls(data["inputTokens"], data["outputTokens"], data["totalTokens"])


@dataclass(frozen=True, slots=True)
class CapabilityModelOutput:
    response_candidate: str
    finish_reason: str

    def __post_init__(self) -> None:
        _text(self.response_candidate, "output.responseCandidate")
        _text(self.finish_reason, "output.metadata.finishReason")

    @property
    def schema_version(self) -> str:
        return MODEL_OUTPUT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "responseCandidate": self.response_candidate,
            "metadata": {"finishReason": self.finish_reason},
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityModelOutput:
        data = _exact_object(
            value, "output", {"schemaVersion", "responseCandidate", "metadata"}
        )
        if data["schemaVersion"] != MODEL_OUTPUT_SCHEMA_VERSION:
            raise CapabilityValidationError("output.schemaVersion is unsupported")
        metadata = _exact_object(
            data["metadata"], "output.metadata", {"finishReason"}
        )
        return cls(data["responseCandidate"], metadata["finishReason"])


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    capability_result_id: str
    capability_request_id: str
    operation_id: str
    request_id: str
    request_hash: str
    subject_id: str
    binding_id: str
    binding_version: int
    status: CapabilityStatus
    provider: CapabilityProvider
    output: CapabilityModelOutput | None
    content_hash: str
    started_at: str
    completed_at: str
    actual_usage: CapabilityActualUsage
    vio_ledger_entry_id: str
    error_code: str | None
    retry_class: str | None
    audit_ref: str
    execution_fact: bool

    def __post_init__(self) -> None:
        for value, name in (
            (self.capability_result_id, "capabilityResultId"),
            (self.capability_request_id, "capabilityRequestId"),
            (self.operation_id, "operationId"),
            (self.request_id, "requestId"),
            (self.subject_id, "subjectId"),
            (self.binding_id, "bindingId"),
            (self.vio_ledger_entry_id, "vioLedgerEntryId"),
            (self.audit_ref, "auditRef"),
        ):
            _text(value, name)
        _hash(self.request_hash, "requestHash")
        if self.binding_version != 1 or isinstance(self.binding_version, bool):
            raise CapabilityValidationError("bindingVersion must be 1")
        _hash(self.content_hash, "contentHash")
        if not isinstance(self.status, CapabilityStatus) or self.status is CapabilityStatus.PROPOSED:
            raise CapabilityValidationError("CapabilityResult status is invalid")
        _utc(self.started_at, "startedAt")
        _utc(self.completed_at, "completedAt")
        if parse_capability_datetime(self.completed_at) < parse_capability_datetime(
            self.started_at
        ):
            raise CapabilityValidationError(
                "completedAt cannot be earlier than startedAt"
            )
        if self.execution_fact is not True:
            raise CapabilityValidationError("executionFact must be true")
        expected_hash = calculate_capability_content_hash(
            self.output.to_dict() if self.output is not None else None
        )
        if self.content_hash != expected_hash:
            raise CapabilityValidationError("contentHash does not match output")
        if self.status is CapabilityStatus.SUCCEEDED:
            if self.output is None:
                raise CapabilityValidationError("SUCCEEDED requires output")
            if self.error_code is not None or self.retry_class is not None:
                raise CapabilityValidationError(
                    "SUCCEEDED requires null errorCode and retryClass"
                )
        else:
            if self.output is not None:
                raise CapabilityValidationError("non-success result requires null output")
            _text(self.error_code, "errorCode")
            expected_retry = (
                "retry"
                if self.status is CapabilityStatus.FAILED_RETRYABLE
                else "query"
                if self.status is CapabilityStatus.UNKNOWN
                else "never"
            )
            if self.retry_class != expected_retry:
                raise CapabilityValidationError(
                    f"{self.status.value} requires retryClass={expected_retry}"
                )

    @property
    def contract_version(self) -> str:
        return CAPABILITY_CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return CAPABILITY_RESULT_SCHEMA_VERSION

    @property
    def capability_type(self) -> str:
        return "model.generate"

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "schemaVersion": self.schema_version,
            "capabilityResultId": self.capability_result_id,
            "capabilityRequestId": self.capability_request_id,
            "operationId": self.operation_id,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "bindingVersion": self.binding_version,
            "status": self.status.value,
            "capabilityType": self.capability_type,
            "provider": self.provider.to_dict(),
            "output": self.output.to_dict() if self.output is not None else None,
            "contentHash": self.content_hash,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "actualUsage": self.actual_usage.to_dict(),
            "vioLedgerEntryId": self.vio_ledger_entry_id,
            "errorCode": self.error_code,
            "retryClass": self.retry_class,
            "auditRef": self.audit_ref,
            "executionFact": self.execution_fact,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityResult:
        fields = {
            "contractVersion", "schemaVersion", "capabilityResultId",
            "capabilityRequestId", "operationId", "requestId", "requestHash",
            "subjectId", "bindingId", "bindingVersion",
            "status", "capabilityType", "provider", "output", "contentHash",
            "startedAt", "completedAt", "actualUsage", "vioLedgerEntryId",
            "errorCode", "retryClass", "auditRef", "executionFact",
        }
        data = _exact_object(value, "CapabilityResult", fields)
        if data["contractVersion"] != CAPABILITY_CONTRACT_VERSION:
            raise CapabilityValidationError("contractVersion is unsupported")
        if data["schemaVersion"] != CAPABILITY_RESULT_SCHEMA_VERSION:
            raise CapabilityValidationError("schemaVersion is unsupported")
        if data["capabilityType"] != "model.generate":
            raise CapabilityValidationError("capabilityType is unsupported")
        try:
            status = CapabilityStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise CapabilityValidationError("CapabilityResult status is invalid") from exc
        return cls(
            capability_result_id=data["capabilityResultId"],
            capability_request_id=data["capabilityRequestId"],
            operation_id=data["operationId"],
            request_id=data["requestId"],
            request_hash=data["requestHash"],
            subject_id=data["subjectId"],
            binding_id=data["bindingId"],
            binding_version=data["bindingVersion"],
            status=status,
            provider=CapabilityProvider.from_dict(data["provider"]),
            output=(
                CapabilityModelOutput.from_dict(data["output"])
                if data["output"] is not None else None
            ),
            content_hash=data["contentHash"],
            started_at=data["startedAt"],
            completed_at=data["completedAt"],
            actual_usage=CapabilityActualUsage.from_dict(data["actualUsage"]),
            vio_ledger_entry_id=data["vioLedgerEntryId"],
            error_code=_optional_text(data["errorCode"], "errorCode"),
            retry_class=_optional_text(data["retryClass"], "retryClass"),
            audit_ref=data["auditRef"],
            execution_fact=data["executionFact"],
        )


@dataclass(frozen=True, slots=True)
class CapabilityAttempt:
    result_hash: str
    received_at: str
    result: CapabilityResult

    def __post_init__(self) -> None:
        _hash(self.result_hash, "resultHash")
        _utc(self.received_at, "receivedAt")
        if self.result_hash != calculate_capability_result_hash(self.result):
            raise CapabilityValidationError("resultHash does not match CapabilityResult")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "resultHash": self.result_hash,
            "receivedAt": self.received_at,
            "result": self.result.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> CapabilityAttempt:
        data = _exact_object(
            value, "CapabilityAttempt", {"resultHash", "receivedAt", "result"}
        )
        return cls(
            result_hash=data["resultHash"],
            received_at=data["receivedAt"],
            result=CapabilityResult.from_dict(data["result"]),
        )


@dataclass(frozen=True, slots=True)
class CapabilityRequiredEnvelope:
    request_id: str
    request_hash: str
    operation_id: str
    subject_id: str
    capability_request: CapabilityRequest
    updated_at: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "requestId"),
            (self.operation_id, "operationId"),
            (self.subject_id, "subjectId"),
        ):
            _text(value, name)
        _hash(self.request_hash, "requestHash")
        _utc(self.updated_at, "updatedAt")
        if any(
            (
                self.capability_request.request_id != self.request_id,
                self.capability_request.request_hash != self.request_hash,
                self.capability_request.operation_id != self.operation_id,
                self.capability_request.subject_id != self.subject_id,
            )
        ):
            raise CapabilityValidationError(
                "capability_required identity does not match CapabilityRequest"
            )

    @property
    def contract_version(self) -> str:
        return CAPABILITY_CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return CAPABILITY_REQUIRED_SCHEMA_VERSION

    @property
    def status(self) -> str:
        return "capability_required"

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "schemaVersion": self.schema_version,
            "status": self.status,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "subjectId": self.subject_id,
            "capabilityRequest": self.capability_request.to_dict(),
            "updatedAt": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class CapabilityFailedEnvelope:
    request_id: str
    request_hash: str
    operation_id: str
    subject_id: str
    capability_request_id: str
    failure_status: CapabilityStatus
    error_code: str
    retry_class: str
    updated_at: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "requestId"),
            (self.operation_id, "operationId"),
            (self.subject_id, "subjectId"),
            (self.capability_request_id, "capabilityRequestId"),
            (self.error_code, "errorCode"),
            (self.retry_class, "retryClass"),
        ):
            _text(value, name)
        _hash(self.request_hash, "requestHash")
        _utc(self.updated_at, "updatedAt")
        if not self.failure_status.failed_terminally:
            raise CapabilityValidationError(
                "capability_failed requires a terminal capability status"
            )

    @property
    def contract_version(self) -> str:
        return CAPABILITY_CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return CAPABILITY_FAILED_SCHEMA_VERSION

    @property
    def status(self) -> str:
        return "capability_failed"

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "schemaVersion": self.schema_version,
            "status": self.status,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "subjectId": self.subject_id,
            "capabilityRequestId": self.capability_request_id,
            "failureStatus": self.failure_status.value,
            "errorCode": self.error_code,
            "retryClass": self.retry_class,
            "updatedAt": self.updated_at,
        }


def calculate_capability_content_hash(value: Any) -> str:
    return sha256_hash(canonicalize_json(value))


def parse_capability_datetime(value: str) -> datetime:
    _utc(value, "capability timestamp")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def calculate_capability_result_hash(result: CapabilityResult | dict[str, Any]) -> str:
    value = result.to_dict() if isinstance(result, CapabilityResult) else result
    return sha256_hash(canonicalize_json(value))
