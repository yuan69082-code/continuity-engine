from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from continuity_engine.domain.capability import (
    CapabilityActualUsage,
    CapabilityFailedEnvelope,
    CapabilityModelOutput,
    CapabilityProvider,
    CapabilityRequiredEnvelope,
    CapabilityResult,
    CapabilityStatus,
    calculate_capability_content_hash,
    parse_capability_datetime,
)
from continuity_engine.domain.errors import (
    ModelProviderConflictError,
    ModelProviderNotFoundError,
    ModelProviderValidationError,
)
from continuity_engine.domain.integration_hashing import canonicalize_json, sha256_hash
from continuity_engine.domain.integration_results import (
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationRequestQueryResult,
    format_contract_datetime,
)
from continuity_engine.domain.model_provider import (
    ModelExecutionRecord,
    ModelExecutionRequest,
    ModelUsageEntry,
    ProviderDispatchAttempt,
    ProviderExecutionFact,
    ProviderExecutionStatus,
    ProviderQueryResolution,
    ProviderQueryStatus,
)
from continuity_engine.interfaces.integration_adapter import IntegrationAdapter

from .model_provider_ports import (
    ModelExecutionRepository,
    ModelProfilePolicy,
    ModelProvider,
)


Clock = Callable[[], datetime]
FaultInjector = Callable[[str, ModelExecutionRecord], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ModelCapabilityService:
    """Drive host-neutral model execution through the existing E5-A state machine."""

    def __init__(
        self,
        *,
        integration: IntegrationAdapter,
        provider: ModelProvider,
        profiles: ModelProfilePolicy,
        repository: ModelExecutionRepository,
        clock: Clock = _utc_now,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self._integration = integration
        self._provider = provider
        self._profiles = profiles
        self._repository = repository
        self._clock = clock
        self._fault_injector = fault_injector
        self._repository.ensure_initialized()

    @property
    def repository(self) -> ModelExecutionRepository:
        return self._repository

    def submit(self, payload: Any):
        """Run one local Engine interaction without any Vio or network dependency."""

        outcome = self._integration.submit(payload)
        if isinstance(outcome, FirstRoundSuccessResult):
            self._mark_completed_from_query(outcome)
            return outcome
        if not isinstance(outcome, CapabilityRequiredEnvelope):
            return outcome
        return self._drive(outcome, allow_new_attempt=True, explicit_retry=False)

    def recover(self, request_id: str):
        """Resume durable P02/E5-A state without authorizing a new retry."""

        outcome = self._integration.query_request(request_id)
        if outcome is None:
            raise ModelProviderNotFoundError("request has no Engine operation")
        if isinstance(outcome, IntegrationRequestQueryResult):
            if outcome.result is not None:
                self._mark_completed_from_query(outcome.result)
                return outcome.result
            return outcome
        if isinstance(outcome, CapabilityRequiredEnvelope):
            return self._drive(outcome, allow_new_attempt=True, explicit_retry=False)
        return outcome

    def retry(self, request_id: str):
        """Explicitly retry only a durable retryable result; UNKNOWN remains query-first."""

        outcome = self._integration.query_request(request_id)
        if not isinstance(outcome, CapabilityRequiredEnvelope):
            if outcome is None:
                raise ModelProviderNotFoundError("request has no Engine operation")
            if isinstance(outcome, IntegrationRequestQueryResult) and outcome.result is not None:
                self._mark_completed_from_query(outcome.result)
                return outcome.result
            return outcome
        record = self._repository.load_execution(
            outcome.capability_request.capability_request_id
        )
        if record is None or not record.capability_results:
            raise ModelProviderValidationError(
                "retry requires one durable P02 result classification"
            )
        latest = record.capability_results[-1]
        if latest.status not in {
            CapabilityStatus.UNKNOWN,
            CapabilityStatus.FAILED_RETRYABLE,
        }:
            raise ModelProviderValidationError(
                "only retryable or proven-not-executed UNKNOWN results may retry"
            )
        return self._drive(outcome, allow_new_attempt=True, explicit_retry=True)

    def _drive(
        self,
        required: CapabilityRequiredEnvelope,
        *,
        allow_new_attempt: bool,
        explicit_retry: bool,
    ):
        request = required.capability_request
        profile = self._profiles.select()
        record = self._ensure_record(required, profile)

        completed = self._integration.query_request(required.request_id)
        if isinstance(completed, IntegrationRequestQueryResult) and completed.result is not None:
            self._mark_completed(record, completed.result)
            return completed.result

        undelivered = next(
            (
                result
                for result in record.capability_results
                if result.capability_result_id not in record.delivered_result_ids
            ),
            None,
        )
        if undelivered is not None:
            return self._deliver(record, undelivered)

        if record.attempts and record.attempts[-1].fact is None:
            attempt = record.attempts[-1]
            queried = self._provider.query(attempt.request)
            self._fault("after_provider_query", record)
            if queried.status is ProviderQueryStatus.FOUND:
                assert queried.fact is not None
                record = self._persist_fact(record, queried.fact)
            elif queried.status is ProviderQueryStatus.UNKNOWN:
                return required
            elif allow_new_attempt:
                fact = self._provider.execute(attempt.request)
                self._fault("after_provider_returned_before_fact", record)
                record = self._persist_fact(record, fact)
            else:
                return required

        if record.attempts and record.attempts[-1].fact is not None:
            latest_attempt = record.attempts[-1]
            effective_fact = latest_attempt.effective_fact
            assert effective_fact is not None
            existing_result = self._result_for_attempt(
                required,
                record,
                latest_attempt,
            )

            if (
                not latest_attempt.proven_not_executed
                and effective_fact.status
                in {ProviderExecutionStatus.TIMEOUT, ProviderExecutionStatus.UNKNOWN}
                and existing_result is not None
            ):
                queried = self._provider.query(latest_attempt.request)
                self._fault("after_provider_query", record)
                if queried.status is ProviderQueryStatus.UNKNOWN:
                    return required
                if queried.status is ProviderQueryStatus.FOUND:
                    assert queried.fact is not None
                    if queried.fact == effective_fact:
                        return required
                    record = self._persist_query_resolution(record, queried)
                else:
                    record = self._persist_query_resolution(record, queried)
                    if not explicit_retry:
                        return required
                latest_attempt = record.attempts[-1]
                effective_fact = latest_attempt.effective_fact

            if latest_attempt.proven_not_executed:
                if not explicit_retry:
                    return required
            elif effective_fact is not None:
                result_for_attempt = self._result_for_attempt(
                    required,
                    record,
                    latest_attempt,
                )
                if result_for_attempt is None:
                    record, result_for_attempt = self._persist_result_for_fact(
                        required,
                        record,
                        latest_attempt,
                    )
                    return self._deliver(record, result_for_attempt)
                if result_for_attempt.capability_result_id not in record.delivered_result_ids:
                    return self._deliver(record, result_for_attempt)
                if effective_fact.status in {
                    ProviderExecutionStatus.TIMEOUT,
                    ProviderExecutionStatus.UNKNOWN,
                }:
                    return required
                if not explicit_retry:
                    return required
                if result_for_attempt.status is not CapabilityStatus.FAILED_RETRYABLE:
                    raise ModelProviderValidationError(
                        "only a retryable or proven-not-executed attempt may retry"
                    )

        if not allow_new_attempt:
            return required
        if record.capability_results and not explicit_retry:
            return required

        ordinal = len(record.attempts) + 1
        now = self._safe_time_after(request.created_at)
        daily_used = self._daily_tokens(format_contract_datetime(now))
        daily_remaining = max(0, profile.daily_token_limit - daily_used)
        maximum_tokens = min(profile.per_execution_token_limit, daily_remaining)
        execution_request = ModelExecutionRequest(
            execution_id=record.execution_id,
            attempt_id=f"{record.execution_id}-attempt-{ordinal}",
            capability_request_id=request.capability_request_id,
            operation_id=request.operation_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            instruction=request.input.instruction,
            message_content=request.input.message_content,
            profile=profile,
            maximum_tokens=maximum_tokens,
            created_at=format_contract_datetime(now),
        )
        record = replace(
            record,
            updated_at=execution_request.created_at,
            attempts=(*record.attempts, ProviderDispatchAttempt(execution_request)),
        )
        self._repository.save_execution(record)
        self._fault("after_provider_dispatch_reserved", record)

        if maximum_tokens == 0:
            completed_at = format_contract_datetime(now + timedelta(microseconds=1))
            fact = ProviderExecutionFact(
                execution_id=record.execution_id,
                attempt_id=execution_request.attempt_id,
                request_fingerprint=execution_request.request_fingerprint,
                provider_id=profile.provider_id,
                model_name=profile.model_name,
                status=ProviderExecutionStatus.RESOURCE_EXHAUSTED,
                response_candidate=None,
                input_tokens=0,
                output_tokens=0,
                finish_reason=None,
                error_code="RESOURCE_EXHAUSTED",
                retry_class="never",
                started_at=execution_request.created_at,
                completed_at=completed_at,
                execution_occurred=False,
            )
        else:
            fact = self._provider.execute(execution_request)
            self._fault("after_provider_returned_before_fact", record)
        record = self._persist_fact(record, fact)
        record, result = self._persist_result_for_fact(
            required,
            record,
            record.attempts[-1],
        )
        return self._deliver(record, result)

    def _ensure_record(self, required, profile) -> ModelExecutionRecord:
        request = required.capability_request
        existing = self._repository.load_execution(request.capability_request_id)
        execution_id = f"p02-execution-{uuid5(NAMESPACE_URL, request.capability_request_id)}"
        created_at = request.created_at
        expected = ModelExecutionRecord(
            execution_id=execution_id,
            capability_request_id=request.capability_request_id,
            operation_id=request.operation_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            profile=profile,
            created_at=created_at,
            updated_at=created_at,
        )
        if existing is None:
            persisted = self._repository.ensure_execution(expected)
            self._fault("after_model_execution_reserved", persisted)
            return persisted
        identity = (
            existing.execution_id == execution_id
            and existing.operation_id == request.operation_id
            and existing.request_id == request.request_id
            and existing.idempotency_key == request.idempotency_key
            and existing.input_hash == request.input_hash
            and existing.profile == profile
        )
        if not identity:
            raise ModelProviderConflictError(
                "persisted model execution conflicts with CapabilityRequest or profile"
            )
        return existing

    def _persist_query_resolution(
        self,
        record: ModelExecutionRecord,
        query,
    ) -> ModelExecutionRecord:
        if not record.attempts:
            raise ModelProviderConflictError(
                "Provider query resolution has no dispatched attempt"
            )
        current = record.attempts[-1]
        if current.fact is None or current.fact.status not in {
            ProviderExecutionStatus.TIMEOUT,
            ProviderExecutionStatus.UNKNOWN,
        }:
            raise ModelProviderConflictError(
                "Provider query resolution requires one ambiguous persisted fact"
            )
        if query.status is ProviderQueryStatus.UNKNOWN:
            raise ModelProviderConflictError(
                "an inconclusive Provider query cannot be persisted as a resolution"
            )
        if current.query_resolutions:
            existing = current.query_resolutions[-1]
            if existing.status is query.status and existing.fact == query.fact:
                return record
            raise ModelProviderConflictError(
                "a conclusive Provider query resolution cannot be changed"
            )
        lower_bound = current.fact.completed_at
        if query.fact is not None and parse_capability_datetime(
            query.fact.completed_at
        ) > parse_capability_datetime(lower_bound):
            lower_bound = query.fact.completed_at
        resolved_at = format_contract_datetime(self._safe_time_after(lower_bound))
        resolution = ProviderQueryResolution(
            status=query.status,
            resolved_at=resolved_at,
            fact=query.fact,
        )
        updated_attempt = replace(
            current,
            query_resolutions=(*current.query_resolutions, resolution),
        )
        record = replace(
            record,
            updated_at=resolved_at,
            attempts=(*record.attempts[:-1], updated_attempt),
        )
        self._repository.save_execution(record)
        self._fault("after_provider_query_resolution_persisted", record)
        return record

    def _persist_fact(
        self,
        record: ModelExecutionRecord,
        fact: ProviderExecutionFact,
    ) -> ModelExecutionRecord:
        if not record.attempts:
            raise ModelProviderConflictError("provider fact has no dispatched attempt")
        current = record.attempts[-1]
        delivery_error_code = None
        if fact.status.is_success and (
            fact.total_tokens > current.request.maximum_tokens
            or self._daily_tokens(fact.completed_at) + fact.total_tokens
            > record.profile.daily_token_limit
        ):
            delivery_error_code = "RESOURCE_EXHAUSTED"
        checked = ProviderDispatchAttempt(
            current.request,
            fact,
            delivery_error_code=delivery_error_code,
        )
        record = replace(
            record,
            updated_at=fact.completed_at,
            attempts=(*record.attempts[:-1], checked),
        )
        self._repository.save_execution(record)
        self._fault("after_provider_fact_persisted", record)
        if fact.status.is_success:
            usage = self._usage_for(record, fact)
            self._repository.save_usage(usage)
            self._fault("after_usage_persisted", record)
        return record

    def _result_for_attempt(
        self,
        required: CapabilityRequiredEnvelope,
        record: ModelExecutionRecord,
        attempt: ProviderDispatchAttempt,
    ) -> CapabilityResult | None:
        fact = attempt.effective_fact
        if fact is None:
            return None
        expected = self._capability_result(
            required,
            fact,
            delivery_error_code=attempt.delivery_error_code,
        )
        existing = next(
            (
                item
                for item in record.capability_results
                if item.capability_result_id == expected.capability_result_id
            ),
            None,
        )
        if existing is not None and existing != expected:
            raise ModelProviderConflictError(
                "a P02 CapabilityResult identity cannot be changed"
            )
        return existing

    def _persist_result_for_fact(
        self,
        required: CapabilityRequiredEnvelope,
        record: ModelExecutionRecord,
        attempt: ProviderDispatchAttempt,
    ) -> tuple[ModelExecutionRecord, CapabilityResult]:
        fact = attempt.effective_fact
        if fact is None:
            raise ModelProviderConflictError("CapabilityResult requires a provider fact")
        if fact.status.is_success:
            self._repository.save_usage(self._usage_for(record, fact))
        result = self._capability_result(
            required,
            fact,
            delivery_error_code=attempt.delivery_error_code,
        )
        existing = next(
            (
                item
                for item in record.capability_results
                if item.capability_result_id == result.capability_result_id
            ),
            None,
        )
        if existing is not None:
            if existing != result:
                raise ModelProviderConflictError(
                    "a P02 CapabilityResult identity cannot be changed"
                )
            return record, existing
        record = replace(
            record,
            updated_at=result.completed_at,
            capability_results=(*record.capability_results, result),
        )
        self._repository.save_execution(record)
        self._fault("after_capability_result_prepared", record)
        return record, result

    def _deliver(
        self,
        record: ModelExecutionRecord,
        result: CapabilityResult,
    ):
        outcome = self._integration.submit_capability_result(result.to_dict())
        self._fault("after_engine_result_before_delivery_checkpoint", record)
        response_id = (
            outcome.response.response_id
            if isinstance(outcome, FirstRoundSuccessResult)
            else None
        )
        record = replace(
            record,
            updated_at=result.completed_at,
            delivered_result_ids=(
                record.delivered_result_ids
                if result.capability_result_id in record.delivered_result_ids
                else (*record.delivered_result_ids, result.capability_result_id)
            ),
            completed_response_id=response_id or record.completed_response_id,
        )
        self._repository.save_execution(record)
        self._fault("after_delivery_checkpoint_saved", record)
        return outcome

    def _mark_completed_from_query(self, result: FirstRoundSuccessResult) -> None:
        record = next(
            (
                item
                for item in self._repository.list_executions()
                if item.request_id == result.request_id
            ),
            None,
        )
        if record is not None:
            self._mark_completed(record, result)

    def _mark_completed(
        self,
        record: ModelExecutionRecord,
        result: FirstRoundSuccessResult,
    ) -> None:
        if record.completed_response_id == result.response.response_id:
            return
        if record.completed_response_id is not None:
            raise ModelProviderConflictError(
                "completed Engine response identity cannot be changed"
            )
        delivered = record.delivered_result_ids
        if record.capability_results:
            last_result_id = record.capability_results[-1].capability_result_id
            if last_result_id not in delivered:
                delivered = (*delivered, last_result_id)
        self._repository.save_execution(
            replace(
                record,
                delivered_result_ids=delivered,
                completed_response_id=result.response.response_id,
            )
        )

    def _usage_for(
        self,
        record: ModelExecutionRecord,
        fact: ProviderExecutionFact,
    ) -> ModelUsageEntry:
        return ModelUsageEntry(
            usage_id=f"p02-usage-{uuid5(NAMESPACE_URL, fact.attempt_id)}",
            execution_id=record.execution_id,
            attempt_id=fact.attempt_id,
            capability_request_id=record.capability_request_id,
            provider_id=fact.provider_id,
            model_name=fact.model_name,
            usage_day=parse_capability_datetime(fact.completed_at).date().isoformat(),
            input_tokens=fact.input_tokens,
            output_tokens=fact.output_tokens,
            total_tokens=fact.total_tokens,
            test_credits=record.profile.success_test_credit,
            recorded_at=fact.completed_at,
        )

    def _daily_tokens(self, timestamp: str) -> int:
        day = parse_capability_datetime(timestamp).date().isoformat()
        return sum(
            item.total_tokens
            for item in self._repository.list_usage()
            if item.usage_day == day
        )

    @staticmethod
    def _audit_ref(attempt_id: str) -> str:
        return f"engine-p02-audit-{uuid5(NAMESPACE_URL, attempt_id)}"

    def _capability_result(
        self,
        required: CapabilityRequiredEnvelope,
        fact: ProviderExecutionFact,
        *,
        delivery_error_code: str | None = None,
    ) -> CapabilityResult:
        request = required.capability_request
        output = (
            CapabilityModelOutput(
                response_candidate=fact.response_candidate,
                finish_reason=fact.finish_reason,
            )
            if fact.status.is_success and delivery_error_code is None
            else None
        )
        if delivery_error_code is None:
            status, error_code, retry_class = self._result_classification(fact)
            result_identity = fact.status.value
        else:
            status = CapabilityStatus.FAILED_TERMINAL
            error_code = delivery_error_code
            retry_class = "never"
            result_identity = f"delivery-rejected:{delivery_error_code}"
        result_id = (
            "p02-result-"
            f"{uuid5(NAMESPACE_URL, fact.attempt_id + '|' + result_identity)}"
        )
        content_value = output.to_dict() if output is not None else None
        return CapabilityResult(
            capability_result_id=result_id,
            capability_request_id=request.capability_request_id,
            operation_id=request.operation_id,
            request_id=request.request_id,
            request_hash=request.request_hash,
            subject_id=request.subject_id,
            binding_id=request.binding_id,
            binding_version=request.binding_version,
            status=status,
            provider=CapabilityProvider(
                provider_type="model",
                provider_id=fact.provider_id,
                model_name=fact.model_name,
            ),
            output=output,
            content_hash=calculate_capability_content_hash(content_value),
            started_at=fact.started_at,
            completed_at=fact.completed_at,
            actual_usage=CapabilityActualUsage(
                input_tokens=fact.input_tokens,
                output_tokens=fact.output_tokens,
                total_tokens=fact.total_tokens,
            ),
            vio_ledger_entry_id=(
                "engine-p02-test-ledger-"
                f"{uuid5(NAMESPACE_URL, fact.attempt_id + '|compat')}"
            ),
            error_code=error_code,
            retry_class=retry_class,
            audit_ref=self._audit_ref(fact.attempt_id),
            execution_fact=True,
        )

    @staticmethod
    def _result_classification(
        fact: ProviderExecutionFact,
    ) -> tuple[CapabilityStatus, str | None, str | None]:
        if fact.status is ProviderExecutionStatus.SUCCEEDED:
            return CapabilityStatus.SUCCEEDED, None, None
        if fact.status in {
            ProviderExecutionStatus.NETWORK_FAILED,
            ProviderExecutionStatus.FAILED_RETRYABLE,
        }:
            return CapabilityStatus.FAILED_RETRYABLE, fact.error_code, "retry"
        if fact.status in {
            ProviderExecutionStatus.TIMEOUT,
            ProviderExecutionStatus.UNKNOWN,
        }:
            return CapabilityStatus.UNKNOWN, fact.error_code, "query"
        status = {
            ProviderExecutionStatus.CANCELLED: CapabilityStatus.CANCELLED,
            ProviderExecutionStatus.EXPIRED: CapabilityStatus.EXPIRED,
        }.get(fact.status, CapabilityStatus.FAILED_TERMINAL)
        return status, fact.error_code, "never"

    def _safe_time_after(self, lower_bound: str) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ModelProviderValidationError("model execution clock must be timezone-aware")
        now = now.astimezone(timezone.utc)
        minimum = parse_capability_datetime(lower_bound) + timedelta(microseconds=1)
        return max(now, minimum)

    def _fault(self, stage: str, record: ModelExecutionRecord) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage, record)
