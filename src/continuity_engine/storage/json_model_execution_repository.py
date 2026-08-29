from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from continuity_engine.domain.errors import (
    IntegrationPersistenceError,
    ModelProviderConflictError,
    ModelProviderValidationError,
)
from continuity_engine.domain.model_provider import (
    MODEL_EXECUTION_FORMAT_VERSION,
    MODEL_USAGE_FORMAT_VERSION,
    ModelExecutionRecord,
    ModelUsageEntry,
)
from continuity_engine.domain.capability import parse_capability_datetime

from .json_integration_repository import _atomic_write_json, _read_json, _strict_document


_FILE_NAME = "model-execution-ledger.p02-v1.json"


class JsonModelExecutionRepository:
    """One atomic P02 ledger for execution, usage, and synthetic test-credit facts."""

    def __init__(self, root: str | Path) -> None:
        self._path = Path(root) / "integration" / _FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def ensure_initialized(self) -> None:
        if self._path.exists():
            self._load()
            return
        self._write([], [])

    def ensure_execution(self, record: ModelExecutionRecord) -> ModelExecutionRecord:
        if not isinstance(record, ModelExecutionRecord):
            raise IntegrationPersistenceError(
                "model execution ledger accepts ModelExecutionRecord values"
            )
        executions, usage = self._load()
        for existing in executions:
            if existing.capability_request_id != record.capability_request_id:
                continue
            if existing != record:
                raise ModelProviderConflictError(
                    "an immutable model execution identity cannot be changed"
                )
            return existing
        if any(
            existing.execution_id == record.execution_id
            or existing.operation_id == record.operation_id
            or existing.request_id == record.request_id
            for existing in executions
        ):
            raise ModelProviderConflictError(
                "model execution identities must be unique"
            )
        executions.append(record)
        self._write(executions, usage)
        return record

    def load_execution(self, capability_request_id: str) -> ModelExecutionRecord | None:
        executions, _ = self._load()
        return next(
            (
                item
                for item in executions
                if item.capability_request_id == capability_request_id
            ),
            None,
        )

    def save_execution(self, record: ModelExecutionRecord) -> None:
        if not isinstance(record, ModelExecutionRecord):
            raise IntegrationPersistenceError(
                "model execution ledger accepts ModelExecutionRecord values"
            )
        executions, usage = self._load()
        existing = next(
            (
                item
                for item in executions
                if item.capability_request_id == record.capability_request_id
            ),
            None,
        )
        if existing is None:
            raise ModelProviderConflictError(
                "model execution must be reserved before it can advance"
            )
        self._validate_progress(existing, record)
        executions = [
            record if item.capability_request_id == record.capability_request_id else item
            for item in executions
        ]
        self._write(executions, usage)

    def list_executions(self) -> list[ModelExecutionRecord]:
        executions, _ = self._load()
        return list(executions)

    def save_usage(self, entry: ModelUsageEntry) -> None:
        if not isinstance(entry, ModelUsageEntry):
            raise IntegrationPersistenceError(
                "model execution ledger accepts ModelUsageEntry values"
            )
        executions, usage = self._load()
        execution = next(
            (item for item in executions if item.execution_id == entry.execution_id),
            None,
        )
        if execution is None or execution.capability_request_id != entry.capability_request_id:
            raise ModelProviderConflictError(
                "usage must reference a persisted model execution"
            )
        attempt = next(
            (
                item
                for item in execution.attempts
                if item.request.attempt_id == entry.attempt_id
            ),
            None,
        )
        if (
            attempt is None
            or attempt.effective_fact is None
            or not attempt.effective_fact.status.is_success
            or attempt.effective_fact.input_tokens != entry.input_tokens
            or attempt.effective_fact.output_tokens != entry.output_tokens
            or attempt.effective_fact.provider_id != entry.provider_id
            or attempt.effective_fact.model_name != entry.model_name
        ):
            raise ModelProviderConflictError(
                "usage does not match one successful provider execution fact"
            )
        for existing in usage:
            same_identity = (
                existing.usage_id == entry.usage_id
                or existing.attempt_id == entry.attempt_id
                or existing.capability_request_id == entry.capability_request_id
            )
            if not same_identity:
                continue
            if existing != entry:
                raise ModelProviderConflictError(
                    "an immutable model usage/test-credit fact cannot be changed"
                )
            return
        usage.append(entry)
        self._write(executions, usage)

    def list_usage(self) -> list[ModelUsageEntry]:
        _, usage = self._load()
        return list(usage)

    def _load(self) -> tuple[list[ModelExecutionRecord], list[ModelUsageEntry]]:
        if not self._path.exists():
            raise IntegrationPersistenceError(
                "P02 model execution ledger has not been initialized"
            )
        raw = _read_json(self._path, name="P02 model execution ledger")
        document = _strict_document(
            raw,
            name="P02 model execution ledger document",
            expected_keys={
                "executionFormatVersion",
                "usageFormatVersion",
                "executions",
                "usageEntries",
            },
        )
        if (
            document["executionFormatVersion"] not in {1, MODEL_EXECUTION_FORMAT_VERSION}
            or document["usageFormatVersion"] != MODEL_USAGE_FORMAT_VERSION
        ):
            raise IntegrationPersistenceError(
                "unsupported P02 model execution ledger format"
            )
        if not isinstance(document["executions"], list) or not isinstance(
            document["usageEntries"], list
        ):
            raise IntegrationPersistenceError(
                "P02 model execution ledger arrays are invalid"
            )
        try:
            executions = [
                ModelExecutionRecord.from_dict(item)
                for item in document["executions"]
            ]
            usage = [
                ModelUsageEntry.from_dict(item)
                for item in document["usageEntries"]
            ]
        except ModelProviderValidationError as exc:
            raise IntegrationPersistenceError(
                f"persisted P02 model execution fact is invalid: {exc}"
            ) from exc
        self._validate_set(executions, usage)
        return executions, usage

    def _write(
        self,
        executions: list[ModelExecutionRecord],
        usage: list[ModelUsageEntry],
    ) -> None:
        self._validate_set(executions, usage)
        _atomic_write_json(
            self._path,
            {
                "executionFormatVersion": MODEL_EXECUTION_FORMAT_VERSION,
                "usageFormatVersion": MODEL_USAGE_FORMAT_VERSION,
                "executions": [item.to_dict() for item in executions],
                "usageEntries": [item.to_dict() for item in usage],
            },
            name="P02 model execution ledger",
        )

    @staticmethod
    def _validate_set(
        executions: list[ModelExecutionRecord],
        usage: list[ModelUsageEntry],
    ) -> None:
        identities: set[tuple[str, str, str, str]] = set()
        for item in executions:
            identity = (
                item.execution_id,
                item.capability_request_id,
                item.operation_id,
                item.request_id,
            )
            if any(value in {part[index] for part in identities} for index, value in enumerate(identity)):
                raise IntegrationPersistenceError(
                    "P02 model execution identities must be unique"
                )
            identities.add(identity)
        usage_ids: set[str] = set()
        attempts: set[str] = set()
        capability_requests: set[str] = set()
        executions_by_id = {item.execution_id: item for item in executions}
        for entry in usage:
            if (
                entry.usage_id in usage_ids
                or entry.attempt_id in attempts
                or entry.capability_request_id in capability_requests
            ):
                raise IntegrationPersistenceError(
                    "P02 usage/test-credit identities must be unique"
                )
            usage_ids.add(entry.usage_id)
            attempts.add(entry.attempt_id)
            capability_requests.add(entry.capability_request_id)
            execution = executions_by_id.get(entry.execution_id)
            if execution is None or execution.capability_request_id != entry.capability_request_id:
                raise IntegrationPersistenceError(
                    "P02 usage references an unknown model execution"
                )
            attempt = next(
                (
                    item
                    for item in execution.attempts
                    if item.request.attempt_id == entry.attempt_id
                ),
                None,
            )
            fact = attempt.effective_fact if attempt is not None else None
            expected_usage_id = f"p02-usage-{uuid5(NAMESPACE_URL, entry.attempt_id)}"
            if (
                attempt is None
                or fact is None
                or not fact.status.is_success
                or fact.execution_id != entry.execution_id
                or fact.attempt_id != entry.attempt_id
                or entry.usage_id != expected_usage_id
                or fact.provider_id != entry.provider_id
                or fact.model_name != entry.model_name
                or fact.input_tokens != entry.input_tokens
                or fact.output_tokens != entry.output_tokens
                or fact.total_tokens != entry.total_tokens
                or parse_capability_datetime(fact.completed_at).date().isoformat()
                != entry.usage_day
                or entry.recorded_at != fact.completed_at
                or entry.test_credits != execution.profile.success_test_credit
            ):
                raise IntegrationPersistenceError(
                    "P02 usage/test-credit does not match its unique successful Provider fact"
                )

    @staticmethod
    def _validate_progress(
        previous: ModelExecutionRecord,
        current: ModelExecutionRecord,
    ) -> None:
        identity_fields = (
            "execution_id",
            "capability_request_id",
            "operation_id",
            "request_id",
            "idempotency_key",
            "input_hash",
            "profile",
            "created_at",
        )
        if any(
            getattr(previous, name) != getattr(current, name)
            for name in identity_fields
        ):
            raise ModelProviderConflictError(
                "a model execution identity cannot be changed"
            )
        if len(current.attempts) < len(previous.attempts):
            raise ModelProviderConflictError("provider attempts cannot be removed")
        for index, old_attempt in enumerate(previous.attempts):
            new_attempt = current.attempts[index]
            if old_attempt.request != new_attempt.request:
                raise ModelProviderConflictError("a dispatched request cannot be changed")
            if old_attempt.fact is not None and old_attempt.fact != new_attempt.fact:
                raise ModelProviderConflictError(
                    "a persisted provider execution fact cannot be changed"
                )
            if len(new_attempt.query_resolutions) < len(old_attempt.query_resolutions):
                raise ModelProviderConflictError(
                    "Provider query resolutions cannot be removed"
                )
            if (
                new_attempt.query_resolutions[: len(old_attempt.query_resolutions)]
                != old_attempt.query_resolutions
            ):
                raise ModelProviderConflictError(
                    "Provider query resolution history cannot be changed"
                )
            if old_attempt.delivery_error_code is not None and (
                new_attempt.delivery_error_code != old_attempt.delivery_error_code
            ):
                raise ModelProviderConflictError(
                    "a Provider delivery rejection cannot be changed"
                )
        if current.capability_results[: len(previous.capability_results)] != previous.capability_results:
            raise ModelProviderConflictError("CapabilityResults cannot be changed or removed")
        if current.delivered_result_ids[: len(previous.delivered_result_ids)] != previous.delivered_result_ids:
            raise ModelProviderConflictError("delivery facts cannot be changed or removed")
        if previous.completed_response_id is not None and (
            current.completed_response_id != previous.completed_response_id
        ):
            raise ModelProviderConflictError(
                "a completed subject result cannot be changed"
            )
