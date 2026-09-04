from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from continuity_engine.domain.capability import (
    CapabilityAttempt,
    CapabilityModelInput,
    CapabilityRequest,
    CapabilityResult,
    CapabilityStatus,
    calculate_capability_content_hash,
    parse_capability_datetime,
)
from continuity_engine.domain.errors import (
    CapabilityNotFoundError,
    CapabilityValidationError,
)
from continuity_engine.domain.integration_hashing import canonicalize_json, sha256_hash
from continuity_engine.domain.integration_results import (
    IntegrationOperationRecord,
    format_contract_datetime,
)
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.subject_binding import SubjectBinding

from .capability_contract_validation import CapabilityContractValidator
from .capability_ports import CapabilityRepository
from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest, InternalActionResult, ReceiptQuery
from continuity_engine.domain.errors import CapabilityConflictError


class CapabilityCoordinationService:
    """Create immutable requests and accept execution facts without executing them."""

    def __init__(
        self,
        repository: CapabilityRepository,
        validator: CapabilityContractValidator | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator or CapabilityContractValidator()

    @property
    def validator(self) -> CapabilityContractValidator:
        return self._validator

    def ensure_action_request(self, request: InternalActionRequest, *, allow_create: bool = True) -> InternalActionRequest:
        """Internal-only typed dispatch; never sent to the frozen external validator."""
        if not isinstance(request, InternalActionRequest):
            raise CapabilityValidationError("internal action request required")
        existing = self._repository.find_capability_request_by_operation(request.operation_id)
        if existing is not None and existing != request:
            raise CapabilityConflictError("operation recovery identity conflict")
        if existing is not None:
            return existing
        if not allow_create:
            raise CapabilityValidationError("CONTEXT_STALE_OR_UNAUTHORIZED")
        self._repository.save_capability_request(request)
        return request

    def action_attempts(self, request: InternalActionRequest, *, receipt_verifier):
        """Read the existing ledger, then verify execution facts before consumption.

        Repository shape/hash validation is not proof of an Adapter effect. This
        gate applies equally to reloaded history, exact replay and result append.
        It deliberately does not execute, retry, or repair persisted history.
        """
        existing = self._repository.load_capability_request(request.capability_request_id)
        if existing != request:
            raise CapabilityConflictError("internal recovery request mismatch")
        attempts = self._repository.list_capability_attempts(request.capability_request_id)
        for attempt in attempts:
            self._verify_action_result_evidence(attempt.result, receipt_verifier)
        return attempts

    @staticmethod
    def _query_action_fact(request, verifier):
        if verifier.adapter_id != request.adapter_id:
            raise CapabilityValidationError("ADAPTER_RECEIPT_BINDING_MISMATCH")
        try:
            fact = verifier.query(request)
        except Exception as exc:
            raise CapabilityValidationError("EXECUTION_FACT_UNVERIFIABLE") from exc
        if isinstance(fact, ActionReceipt):
            fact.validate_request(request)
        return fact

    @classmethod
    def _verify_action_result_evidence(cls, result, verifier):
        # No public status/reason/hash (including receipt=None) is execution proof.
        checked = InternalActionResult.from_dict(result.to_dict())
        if checked.receipt is not None:
            cls._verify_action_receipt(checked.request, checked.receipt, verifier)
        elif checked.status is CapabilityStatus.EXPIRED:
            fact = cls._query_action_fact(checked.request, verifier)
            if isinstance(fact, ActionReceipt):
                raise CapabilityValidationError("LOCAL_STOP_CONFLICTS_WITH_EXECUTION_FACT")
            if fact is not ReceiptQuery.NOT_EXECUTED:
                raise CapabilityValidationError("LOCAL_STOP_NOT_EXECUTED_UNVERIFIED")

    @classmethod
    def _verify_action_receipt(cls, request, receipt, verifier):
        receipt.validate_request(request)
        verified = cls._query_action_fact(request, verifier)
        if not isinstance(verified, ActionReceipt) or verified != receipt:
            raise CapabilityValidationError("EXECUTION_FACT_UNVERIFIED_OR_DRIFTED")
        verified.validate_request(request)

    def accept_action_result(self, result: InternalActionResult, *, received_at: str, receipt_verifier):
        """Reuse the same attempt/terminal ledger after exact receipt verification."""
        if not isinstance(result, InternalActionResult):
            raise CapabilityValidationError("internal action result required")
        self.action_attempts(result.request, receipt_verifier=receipt_verifier)
        self._verify_action_result_evidence(result, receipt_verifier)
        return self._repository.save_capability_result(result, received_at=received_at)

    def ensure_request(
        self,
        operation: IntegrationOperationRecord,
        binding: SubjectBinding,
        perception: PerceptionResult,
        *,
        created_at: datetime,
    ) -> CapabilityRequest:
        existing = self._repository.find_capability_request_by_operation(
            operation.operation_id
        )
        if existing is not None:
            self._validate_request_association(existing, operation, binding, perception)
            self._validator.validate_request(existing.to_dict())
            return existing
        model_input = self._model_input(perception)
        input_hash = calculate_capability_content_hash(model_input)
        capability_request_id = str(
            uuid5(NAMESPACE_URL, f"capability-request|{operation.operation_id}")
        )
        idempotency_key = sha256_hash(
            canonicalize_json(
                {
                    "capabilityRequestId": capability_request_id,
                    "operationId": operation.operation_id,
                    "requestId": operation.request_id,
                    "requestHash": operation.request_hash,
                    "inputHash": input_hash,
                }
            )
        )
        request = CapabilityRequest(
            capability_request_id=capability_request_id,
            operation_id=operation.operation_id,
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            subject_id=operation.subject_id,
            binding_id=operation.binding_id,
            binding_version=operation.binding_version,
            originating_session_id=operation.domain_progress.think_session_id,
            input=model_input,
            input_hash=input_hash,
            permission_ref=f"engine-permission:model.generate:{operation.subject_id}",
            resource_ref=f"engine-resource:thinking:{operation.operation_id}",
            risk_level="MEDIUM",
            deadline_at=format_contract_datetime(created_at + timedelta(minutes=10)),
            idempotency_key=idempotency_key,
            created_at=format_contract_datetime(created_at),
        )
        self._validator.validate_request(request.to_dict())
        self._repository.save_capability_request(request)
        return request

    def accept_result(
        self,
        payload: Any,
        operation: IntegrationOperationRecord,
        *,
        received_at: datetime,
    ) -> CapabilityAttempt:
        result = self._validator.validate_result(payload)
        request = self._repository.load_capability_request(
            result.capability_request_id
        )
        if request is None:
            raise CapabilityNotFoundError(
                "CapabilityResult references an unknown CapabilityRequest"
            )
        if any(
            (
                result.request_id != operation.request_id,
                result.request_hash != operation.request_hash,
                result.operation_id != operation.operation_id,
                result.subject_id != operation.subject_id,
                result.binding_id != operation.binding_id,
                result.binding_version != operation.binding_version,
                request.capability_request_id != result.capability_request_id,
                request.operation_id != result.operation_id,
                request.request_id != result.request_id,
                request.request_hash != result.request_hash,
                request.subject_id != result.subject_id,
                request.binding_id != result.binding_id,
                request.binding_version != result.binding_version,
                request.capability_type != result.capability_type,
            )
        ):
            raise CapabilityValidationError(
                "CapabilityResult identity does not match the waiting operation"
            )
        if (
            result.output is not None
            and len(result.output.response_candidate)
            > request.input.maximum_output_characters
        ):
            raise CapabilityValidationError(
                "CapabilityResult output exceeds the request output limit"
            )
        request_created_at = parse_capability_datetime(request.created_at)
        if (
            parse_capability_datetime(result.started_at) < request_created_at
            or parse_capability_datetime(result.completed_at) < request_created_at
        ):
            raise CapabilityValidationError(
                "CapabilityResult timestamps cannot precede CapabilityRequest.createdAt"
            )
        return self._repository.save_capability_result(
            result,
            received_at=format_contract_datetime(received_at),
        )

    def latest_attempt(self, capability_request_id: str) -> CapabilityAttempt | None:
        attempts = self._repository.list_capability_attempts(capability_request_id)
        return attempts[-1] if attempts else None

    def find_request_by_operation(
        self,
        operation_id: str,
    ) -> CapabilityRequest | None:
        return self._repository.find_capability_request_by_operation(operation_id)

    @staticmethod
    def _validate_request_association(
        request: CapabilityRequest,
        operation: IntegrationOperationRecord,
        binding: SubjectBinding,
        perception: PerceptionResult,
    ) -> None:
        if operation.domain_progress is None or any(
            (
                request.operation_id != operation.operation_id,
                request.request_id != operation.request_id,
                request.request_hash != operation.request_hash,
                request.subject_id != operation.subject_id,
                request.binding_id != operation.binding_id,
                request.binding_version != operation.binding_version,
                request.originating_session_id
                != operation.domain_progress.think_session_id,
                request.input != CapabilityCoordinationService._model_input(perception),
                binding.subject_id != operation.subject_id,
                binding.binding_id != operation.binding_id,
                request.permission_ref
                != f"engine-permission:model.generate:{operation.subject_id}",
                request.resource_ref
                != f"engine-resource:thinking:{operation.operation_id}",
                request.risk_level != "MEDIUM",
            )
        ):
            raise CapabilityValidationError(
                "persisted CapabilityRequest conflicts with operation identity"
            )

    @staticmethod
    def _model_input(perception: PerceptionResult) -> CapabilityModelInput:
        if len(perception.external_facts) != 1:
            raise CapabilityValidationError(
                "capability input requires exactly one perceived platform fact"
            )
        fact = perception.external_facts[0]
        return CapabilityModelInput(
            instruction=(
                "Produce one bounded subject-expression candidate for the verified "
                "message. Do not propose state mutations, events, revisions, tool calls, "
                "or hidden chain-of-thought."
            ),
            message_fact_id=fact.fact_id,
            observation_id=fact.observation_id,
            message_content=fact.content,
            perception_id=perception.perception_id,
            perception_summary=perception.summary,
            current_focus=perception.current_focus.summary,
            source_revision=perception.source_revision,
            output_schema_version="continuity-model-output/v1",
            maximum_output_characters=4096,
        )
