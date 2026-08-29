from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .capability import CapabilityResult, parse_capability_datetime
from .errors import ModelProviderValidationError
from .events import JsonValue
from .integration_hashing import HASH_PATTERN, canonicalize_json, sha256_hash


MODEL_EXECUTION_FORMAT_VERSION = 2
MODEL_USAGE_FORMAT_VERSION = 1
REAL_PROVIDER_USAGE_DEFERRED = "DEFERRED_TO_P22"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelProviderValidationError(f"{name} must be a non-empty string")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name)
    if _ID_PATTERN.fullmatch(value) is None:
        raise ModelProviderValidationError(f"{name} contains unsafe characters")
    return value


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ModelProviderValidationError(
            f"{name} must be an integer greater than or equal to {minimum}"
        )
    return value


def _utc(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ModelProviderValidationError(f"{name} must be an RFC 3339 UTC string")
    try:
        parse_capability_datetime(value)
    except Exception as exc:
        raise ModelProviderValidationError(
            f"{name} must be an RFC 3339 UTC timestamp ending in uppercase Z"
        ) from exc
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
        raise ModelProviderValidationError(
            f"{name} must use sha256: followed by 64 lowercase hexadecimal digits"
        )
    return value


def _object(value: Any, name: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ModelProviderValidationError(f"{name} has an invalid shape")
    return value


class ProviderExecutionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    GENERATION_FAILED = "GENERATION_FAILED"
    NETWORK_FAILED = "NETWORK_FAILED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    @property
    def is_success(self) -> bool:
        return self is ProviderExecutionStatus.SUCCEEDED


class ProviderQueryStatus(str, Enum):
    FOUND = "FOUND"
    NOT_EXECUTED = "NOT_EXECUTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderModelProfile:
    profile_id: str
    profile_version: int
    provider_id: str
    model_name: str
    enabled: bool
    per_execution_token_limit: int
    daily_token_limit: int
    success_test_credit: int
    fallback_enabled: bool = False

    def __post_init__(self) -> None:
        _id(self.profile_id, "profileId")
        _integer(self.profile_version, "profileVersion", minimum=1)
        _text(self.provider_id, "providerId")
        _text(self.model_name, "modelName")
        if not isinstance(self.enabled, bool) or not isinstance(
            self.fallback_enabled, bool
        ):
            raise ModelProviderValidationError(
                "enabled and fallbackEnabled must be booleans"
            )
        _integer(
            self.per_execution_token_limit,
            "perExecutionTokenLimit",
            minimum=1,
        )
        _integer(self.daily_token_limit, "dailyTokenLimit", minimum=1)
        if self.daily_token_limit < self.per_execution_token_limit:
            raise ModelProviderValidationError(
                "dailyTokenLimit cannot be lower than perExecutionTokenLimit"
            )
        _integer(self.success_test_credit, "successTestCredit", minimum=1)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "providerId": self.provider_id,
            "modelName": self.model_name,
            "enabled": self.enabled,
            "perExecutionTokenLimit": self.per_execution_token_limit,
            "dailyTokenLimit": self.daily_token_limit,
            "successTestCredit": self.success_test_credit,
            "fallbackEnabled": self.fallback_enabled,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProviderModelProfile:
        data = _object(
            value,
            "ProviderModelProfile",
            {
                "profileId",
                "profileVersion",
                "providerId",
                "modelName",
                "enabled",
                "perExecutionTokenLimit",
                "dailyTokenLimit",
                "successTestCredit",
                "fallbackEnabled",
            },
        )
        return cls(
            profile_id=data["profileId"],
            profile_version=data["profileVersion"],
            provider_id=data["providerId"],
            model_name=data["modelName"],
            enabled=data["enabled"],
            per_execution_token_limit=data["perExecutionTokenLimit"],
            daily_token_limit=data["dailyTokenLimit"],
            success_test_credit=data["successTestCredit"],
            fallback_enabled=data["fallbackEnabled"],
        )


@dataclass(frozen=True, slots=True)
class ModelExecutionRequest:
    execution_id: str
    attempt_id: str
    capability_request_id: str
    operation_id: str
    request_id: str
    idempotency_key: str
    input_hash: str
    instruction: str
    message_content: str
    profile: ProviderModelProfile
    maximum_tokens: int
    created_at: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.execution_id, "executionId"),
            (self.attempt_id, "attemptId"),
            (self.capability_request_id, "capabilityRequestId"),
            (self.operation_id, "operationId"),
            (self.request_id, "requestId"),
        ):
            _id(value, name)
        _hash(self.idempotency_key, "idempotencyKey")
        _hash(self.input_hash, "inputHash")
        _text(self.instruction, "instruction")
        if not isinstance(self.message_content, str):
            raise ModelProviderValidationError("messageContent must be a string")
        if not isinstance(self.profile, ProviderModelProfile):
            raise ModelProviderValidationError("profile must be a ProviderModelProfile")
        _integer(self.maximum_tokens, "maximumTokens")
        if self.maximum_tokens > self.profile.per_execution_token_limit:
            raise ModelProviderValidationError(
                "maximumTokens exceeds the selected profile limit"
            )
        _utc(self.created_at, "createdAt")

    @property
    def request_fingerprint(self) -> str:
        return sha256_hash(canonicalize_json(self.to_dict()))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "executionId": self.execution_id,
            "attemptId": self.attempt_id,
            "capabilityRequestId": self.capability_request_id,
            "operationId": self.operation_id,
            "requestId": self.request_id,
            "idempotencyKey": self.idempotency_key,
            "inputHash": self.input_hash,
            "instruction": self.instruction,
            "messageContent": self.message_content,
            "profile": self.profile.to_dict(),
            "maximumTokens": self.maximum_tokens,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ModelExecutionRequest:
        data = _object(
            value,
            "ModelExecutionRequest",
            {
                "executionId",
                "attemptId",
                "capabilityRequestId",
                "operationId",
                "requestId",
                "idempotencyKey",
                "inputHash",
                "instruction",
                "messageContent",
                "profile",
                "maximumTokens",
                "createdAt",
            },
        )
        return cls(
            execution_id=data["executionId"],
            attempt_id=data["attemptId"],
            capability_request_id=data["capabilityRequestId"],
            operation_id=data["operationId"],
            request_id=data["requestId"],
            idempotency_key=data["idempotencyKey"],
            input_hash=data["inputHash"],
            instruction=data["instruction"],
            message_content=data["messageContent"],
            profile=ProviderModelProfile.from_dict(data["profile"]),
            maximum_tokens=data["maximumTokens"],
            created_at=data["createdAt"],
        )


@dataclass(frozen=True, slots=True)
class ProviderExecutionFact:
    execution_id: str
    attempt_id: str
    request_fingerprint: str
    provider_id: str
    model_name: str
    status: ProviderExecutionStatus
    response_candidate: str | None
    input_tokens: int
    output_tokens: int
    finish_reason: str | None
    error_code: str | None
    retry_class: str | None
    started_at: str
    completed_at: str
    execution_occurred: bool
    synthetic: bool = True

    def __post_init__(self) -> None:
        _id(self.execution_id, "executionId")
        _id(self.attempt_id, "attemptId")
        _hash(self.request_fingerprint, "requestFingerprint")
        _text(self.provider_id, "providerId")
        _text(self.model_name, "modelName")
        if not isinstance(self.status, ProviderExecutionStatus):
            raise ModelProviderValidationError("provider status is invalid")
        input_tokens = _integer(self.input_tokens, "inputTokens")
        output_tokens = _integer(self.output_tokens, "outputTokens")
        _utc(self.started_at, "startedAt")
        _utc(self.completed_at, "completedAt")
        if parse_capability_datetime(self.completed_at) < parse_capability_datetime(
            self.started_at
        ):
            raise ModelProviderValidationError("completedAt cannot precede startedAt")
        if self.execution_occurred is not True and self.execution_occurred is not False:
            raise ModelProviderValidationError("executionOccurred must be a boolean")
        if self.synthetic is not True:
            raise ModelProviderValidationError("P02 execution facts must be synthetic")
        if self.status.is_success:
            if not isinstance(self.response_candidate, str) or not self.response_candidate.strip():
                raise ModelProviderValidationError(
                    "a successful provider fact requires a non-blank candidate"
                )
            _text(self.finish_reason, "finishReason")
            if self.error_code is not None or self.retry_class is not None:
                raise ModelProviderValidationError(
                    "a successful provider fact cannot contain failure fields"
                )
            if not self.execution_occurred:
                raise ModelProviderValidationError(
                    "a successful provider fact requires executionOccurred=true"
                )
        else:
            if self.response_candidate is not None or self.finish_reason is not None:
                raise ModelProviderValidationError(
                    "a failed provider fact cannot contain an output candidate"
                )
            _text(self.error_code, "errorCode")
            if self.retry_class not in {"retry", "query", "never"}:
                raise ModelProviderValidationError("retryClass is invalid")
        if not self.execution_occurred and (input_tokens or output_tokens):
            raise ModelProviderValidationError(
                "a non-executed provider fact cannot report token usage"
            )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "executionId": self.execution_id,
            "attemptId": self.attempt_id,
            "requestFingerprint": self.request_fingerprint,
            "providerId": self.provider_id,
            "modelName": self.model_name,
            "status": self.status.value,
            "responseCandidate": self.response_candidate,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "finishReason": self.finish_reason,
            "errorCode": self.error_code,
            "retryClass": self.retry_class,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "executionOccurred": self.execution_occurred,
            "synthetic": self.synthetic,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProviderExecutionFact:
        data = _object(
            value,
            "ProviderExecutionFact",
            {
                "executionId",
                "attemptId",
                "requestFingerprint",
                "providerId",
                "modelName",
                "status",
                "responseCandidate",
                "inputTokens",
                "outputTokens",
                "finishReason",
                "errorCode",
                "retryClass",
                "startedAt",
                "completedAt",
                "executionOccurred",
                "synthetic",
            },
        )
        try:
            status = ProviderExecutionStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise ModelProviderValidationError("provider status is invalid") from exc
        return cls(
            execution_id=data["executionId"],
            attempt_id=data["attemptId"],
            request_fingerprint=data["requestFingerprint"],
            provider_id=data["providerId"],
            model_name=data["modelName"],
            status=status,
            response_candidate=data["responseCandidate"],
            input_tokens=data["inputTokens"],
            output_tokens=data["outputTokens"],
            finish_reason=data["finishReason"],
            error_code=data["errorCode"],
            retry_class=data["retryClass"],
            started_at=data["startedAt"],
            completed_at=data["completedAt"],
            execution_occurred=data["executionOccurred"],
            synthetic=data["synthetic"],
        )


@dataclass(frozen=True, slots=True)
class ProviderQueryResult:
    status: ProviderQueryStatus
    fact: ProviderExecutionFact | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProviderQueryStatus):
            raise ModelProviderValidationError("query status is invalid")
        if (self.status is ProviderQueryStatus.FOUND) != (self.fact is not None):
            raise ModelProviderValidationError(
                "FOUND requires exactly one provider execution fact"
            )


@dataclass(frozen=True, slots=True)
class ProviderQueryResolution:
    """Durable, monotonic resolution of one ambiguous Provider attempt."""

    status: ProviderQueryStatus
    resolved_at: str
    fact: ProviderExecutionFact | None = None

    def __post_init__(self) -> None:
        if self.status not in {
            ProviderQueryStatus.FOUND,
            ProviderQueryStatus.NOT_EXECUTED,
        }:
            raise ModelProviderValidationError(
                "only a conclusive Provider query may be persisted"
            )
        _utc(self.resolved_at, "resolvedAt")
        if (self.status is ProviderQueryStatus.FOUND) != (self.fact is not None):
            raise ModelProviderValidationError(
                "a FOUND resolution requires exactly one Provider fact"
            )
        if self.fact is not None and self.fact.status in {
            ProviderExecutionStatus.TIMEOUT,
            ProviderExecutionStatus.UNKNOWN,
        }:
            raise ModelProviderValidationError(
                "an ambiguous Provider fact is not a conclusive resolution"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": self.status.value,
            "resolvedAt": self.resolved_at,
            "fact": self.fact.to_dict() if self.fact is not None else None,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProviderQueryResolution:
        data = _object(
            value,
            "ProviderQueryResolution",
            {"status", "resolvedAt", "fact"},
        )
        try:
            status = ProviderQueryStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise ModelProviderValidationError(
                "Provider query resolution status is invalid"
            ) from exc
        return cls(
            status=status,
            resolved_at=data["resolvedAt"],
            fact=(
                ProviderExecutionFact.from_dict(data["fact"])
                if data["fact"] is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ProviderDispatchAttempt:
    request: ModelExecutionRequest
    fact: ProviderExecutionFact | None = None
    query_resolutions: tuple[ProviderQueryResolution, ...] = ()
    delivery_error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ModelExecutionRequest):
            raise ModelProviderValidationError("attempt request is invalid")
        if self.fact is not None and any(
            (
                self.fact.execution_id != self.request.execution_id,
                self.fact.attempt_id != self.request.attempt_id,
                self.fact.request_fingerprint != self.request.request_fingerprint,
                self.fact.provider_id != self.request.profile.provider_id,
                self.fact.model_name != self.request.profile.model_name,
            )
        ):
            raise ModelProviderValidationError(
                "provider fact does not match its dispatched request"
            )

        if len(self.query_resolutions) > 1:
            raise ModelProviderValidationError(
                "one Provider attempt can have at most one conclusive query resolution"
            )
        for resolution in self.query_resolutions:
            if self.fact is None or self.fact.status not in {
                ProviderExecutionStatus.TIMEOUT,
                ProviderExecutionStatus.UNKNOWN,
            }:
                raise ModelProviderValidationError(
                    "only an ambiguous persisted fact can receive a query resolution"
                )
            if parse_capability_datetime(resolution.resolved_at) < parse_capability_datetime(
                self.fact.completed_at
            ):
                raise ModelProviderValidationError(
                    "Provider query resolution cannot precede the ambiguous fact"
                )
            if resolution.fact is not None and any(
                (
                    resolution.fact.execution_id != self.request.execution_id,
                    resolution.fact.attempt_id != self.request.attempt_id,
                    resolution.fact.request_fingerprint
                    != self.request.request_fingerprint,
                    resolution.fact.provider_id != self.request.profile.provider_id,
                    resolution.fact.model_name != self.request.profile.model_name,
                )
            ):
                raise ModelProviderValidationError(
                    "resolved Provider fact does not match its dispatched request"
                )

        if self.delivery_error_code is not None:
            if self.delivery_error_code != "RESOURCE_EXHAUSTED":
                raise ModelProviderValidationError(
                    "Provider delivery error code is unsupported"
                )
            if self.effective_fact is None or not self.effective_fact.status.is_success:
                raise ModelProviderValidationError(
                    "a delivery rejection requires one successful Provider fact"
                )

    @property
    def effective_fact(self) -> ProviderExecutionFact | None:
        if self.query_resolutions and self.query_resolutions[-1].fact is not None:
            return self.query_resolutions[-1].fact
        return self.fact

    @property
    def proven_not_executed(self) -> bool:
        return bool(
            self.query_resolutions
            and self.query_resolutions[-1].status is ProviderQueryStatus.NOT_EXECUTED
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request": self.request.to_dict(),
            "fact": self.fact.to_dict() if self.fact is not None else None,
            "queryResolutions": [item.to_dict() for item in self.query_resolutions],
            "deliveryErrorCode": self.delivery_error_code,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProviderDispatchAttempt:
        if not isinstance(value, dict) or set(value) not in (
            {"request", "fact"},
            {"request", "fact", "queryResolutions", "deliveryErrorCode"},
        ):
            raise ModelProviderValidationError(
                "ProviderDispatchAttempt has an invalid shape"
            )
        data = value
        resolutions = data.get("queryResolutions", [])
        if not isinstance(resolutions, list):
            raise ModelProviderValidationError(
                "Provider query resolutions must be an array"
            )
        return cls(
            request=ModelExecutionRequest.from_dict(data["request"]),
            fact=(
                ProviderExecutionFact.from_dict(data["fact"])
                if data["fact"] is not None
                else None
            ),
            query_resolutions=tuple(
                ProviderQueryResolution.from_dict(item) for item in resolutions
            ),
            delivery_error_code=data.get("deliveryErrorCode"),
        )


@dataclass(frozen=True, slots=True)
class ModelExecutionRecord:
    execution_id: str
    capability_request_id: str
    operation_id: str
    request_id: str
    idempotency_key: str
    input_hash: str
    profile: ProviderModelProfile
    created_at: str
    updated_at: str
    attempts: tuple[ProviderDispatchAttempt, ...] = ()
    capability_results: tuple[CapabilityResult, ...] = ()
    delivered_result_ids: tuple[str, ...] = ()
    completed_response_id: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.execution_id, "executionId"),
            (self.capability_request_id, "capabilityRequestId"),
            (self.operation_id, "operationId"),
            (self.request_id, "requestId"),
        ):
            _id(value, name)
        _hash(self.idempotency_key, "idempotencyKey")
        _hash(self.input_hash, "inputHash")
        if not isinstance(self.profile, ProviderModelProfile):
            raise ModelProviderValidationError("record profile is invalid")
        _utc(self.created_at, "createdAt")
        _utc(self.updated_at, "updatedAt")
        if self.completed_response_id is not None:
            _id(self.completed_response_id, "completedResponseId")
        attempt_ids: set[str] = set()
        for attempt in self.attempts:
            if attempt.request.attempt_id in attempt_ids:
                raise ModelProviderValidationError("attemptId must be unique")
            attempt_ids.add(attempt.request.attempt_id)
            if any(
                (
                    attempt.request.execution_id != self.execution_id,
                    attempt.request.capability_request_id != self.capability_request_id,
                    attempt.request.operation_id != self.operation_id,
                    attempt.request.request_id != self.request_id,
                    attempt.request.idempotency_key != self.idempotency_key,
                    attempt.request.input_hash != self.input_hash,
                    attempt.request.profile != self.profile,
                )
            ):
                raise ModelProviderValidationError(
                    "dispatch attempt conflicts with its model execution record"
                )
        result_ids: set[str] = set()
        for result in self.capability_results:
            if result.capability_result_id in result_ids:
                raise ModelProviderValidationError(
                    "capabilityResultId must be unique in a model execution"
                )
            result_ids.add(result.capability_result_id)
            if any(
                (
                    result.capability_request_id != self.capability_request_id,
                    result.operation_id != self.operation_id,
                    result.request_id != self.request_id,
                )
            ):
                raise ModelProviderValidationError(
                    "CapabilityResult conflicts with model execution identity"
                )
        if len(set(self.delivered_result_ids)) != len(self.delivered_result_ids):
            raise ModelProviderValidationError("delivered result ids must be unique")
        if not set(self.delivered_result_ids).issubset(result_ids):
            raise ModelProviderValidationError(
                "delivered result ids must reference persisted CapabilityResults"
            )
        successful_facts = [
            item.effective_fact
            for item in self.attempts
            if item.effective_fact is not None
            and item.effective_fact.status.is_success
        ]
        if len(successful_facts) > 1:
            raise ModelProviderValidationError(
                "one capability request can have at most one successful provider fact"
            )

    @property
    def provider_execution_count(self) -> int:
        return sum(
            1
            for attempt in self.attempts
            if not attempt.proven_not_executed
            and attempt.effective_fact is not None
            and attempt.effective_fact.execution_occurred
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "executionId": self.execution_id,
            "capabilityRequestId": self.capability_request_id,
            "operationId": self.operation_id,
            "requestId": self.request_id,
            "idempotencyKey": self.idempotency_key,
            "inputHash": self.input_hash,
            "profile": self.profile.to_dict(),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "attempts": [item.to_dict() for item in self.attempts],
            "capabilityResults": [item.to_dict() for item in self.capability_results],
            "deliveredResultIds": list(self.delivered_result_ids),
            "completedResponseId": self.completed_response_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ModelExecutionRecord:
        data = _object(
            value,
            "ModelExecutionRecord",
            {
                "executionId",
                "capabilityRequestId",
                "operationId",
                "requestId",
                "idempotencyKey",
                "inputHash",
                "profile",
                "createdAt",
                "updatedAt",
                "attempts",
                "capabilityResults",
                "deliveredResultIds",
                "completedResponseId",
            },
        )
        if not isinstance(data["attempts"], list) or not isinstance(
            data["capabilityResults"], list
        ) or not isinstance(data["deliveredResultIds"], list):
            raise ModelProviderValidationError("model execution arrays are invalid")
        return cls(
            execution_id=data["executionId"],
            capability_request_id=data["capabilityRequestId"],
            operation_id=data["operationId"],
            request_id=data["requestId"],
            idempotency_key=data["idempotencyKey"],
            input_hash=data["inputHash"],
            profile=ProviderModelProfile.from_dict(data["profile"]),
            created_at=data["createdAt"],
            updated_at=data["updatedAt"],
            attempts=tuple(
                ProviderDispatchAttempt.from_dict(item) for item in data["attempts"]
            ),
            capability_results=tuple(
                CapabilityResult.from_dict(item) for item in data["capabilityResults"]
            ),
            delivered_result_ids=tuple(data["deliveredResultIds"]),
            completed_response_id=data["completedResponseId"],
        )


@dataclass(frozen=True, slots=True)
class ModelUsageEntry:
    usage_id: str
    execution_id: str
    attempt_id: str
    capability_request_id: str
    provider_id: str
    model_name: str
    usage_day: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    test_credits: int
    recorded_at: str
    synthetic: bool = True
    real_provider_usage: str = REAL_PROVIDER_USAGE_DEFERRED
    real_provider_cost: str = REAL_PROVIDER_USAGE_DEFERRED

    def __post_init__(self) -> None:
        for value, name in (
            (self.usage_id, "usageId"),
            (self.execution_id, "executionId"),
            (self.attempt_id, "attemptId"),
            (self.capability_request_id, "capabilityRequestId"),
        ):
            _id(value, name)
        _text(self.provider_id, "providerId")
        _text(self.model_name, "modelName")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.usage_day):
            raise ModelProviderValidationError("usageDay must be YYYY-MM-DD")
        _integer(self.input_tokens, "inputTokens")
        _integer(self.output_tokens, "outputTokens")
        _integer(self.total_tokens, "totalTokens")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ModelProviderValidationError(
                "totalTokens must equal inputTokens plus outputTokens"
            )
        _integer(self.test_credits, "testCredits", minimum=1)
        _utc(self.recorded_at, "recordedAt")
        if self.synthetic is not True:
            raise ModelProviderValidationError("P02 usage must be synthetic")
        if (
            self.real_provider_usage != REAL_PROVIDER_USAGE_DEFERRED
            or self.real_provider_cost != REAL_PROVIDER_USAGE_DEFERRED
        ):
            raise ModelProviderValidationError(
                "real provider usage and cost must remain deferred to P22"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "usageId": self.usage_id,
            "executionId": self.execution_id,
            "attemptId": self.attempt_id,
            "capabilityRequestId": self.capability_request_id,
            "providerId": self.provider_id,
            "modelName": self.model_name,
            "usageDay": self.usage_day,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "testCredits": self.test_credits,
            "recordedAt": self.recorded_at,
            "synthetic": self.synthetic,
            "realProviderUsage": self.real_provider_usage,
            "realProviderCost": self.real_provider_cost,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ModelUsageEntry:
        data = _object(
            value,
            "ModelUsageEntry",
            {
                "usageId",
                "executionId",
                "attemptId",
                "capabilityRequestId",
                "providerId",
                "modelName",
                "usageDay",
                "inputTokens",
                "outputTokens",
                "totalTokens",
                "testCredits",
                "recordedAt",
                "synthetic",
                "realProviderUsage",
                "realProviderCost",
            },
        )
        return cls(
            usage_id=data["usageId"],
            execution_id=data["executionId"],
            attempt_id=data["attemptId"],
            capability_request_id=data["capabilityRequestId"],
            provider_id=data["providerId"],
            model_name=data["modelName"],
            usage_day=data["usageDay"],
            input_tokens=data["inputTokens"],
            output_tokens=data["outputTokens"],
            total_tokens=data["totalTokens"],
            test_credits=data["testCredits"],
            recorded_at=data["recordedAt"],
            synthetic=data["synthetic"],
            real_provider_usage=data["realProviderUsage"],
            real_provider_cost=data["realProviderCost"],
        )
