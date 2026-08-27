from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from continuity_engine.domain.action import ActionContext, ApprovedStateAction, ResourceLimits
from continuity_engine.domain.awakening import AwakeningResult
from continuity_engine.domain.capability import (
    CapabilityFailedEnvelope,
    CapabilityRequiredEnvelope,
    CapabilityResult,
    CapabilityStatus,
    IntegrationThinkingMode,
)
from continuity_engine.domain.errors import (
    CapabilityConflictError,
    CapabilityNotFoundError,
    CapabilityValidationError,
    IntegrationExecutionError,
    IntegrationPersistenceError,
    MachineContractCallError,
    MachineContractSchemaError,
    MachineContractValidationError,
    StateNotFoundError,
)
from continuity_engine.domain.integration_contract import ContinuityInteractionRequest
from continuity_engine.domain.integration_results import (
    FirstRoundErrorCode,
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationDomainCheckpoint,
    IntegrationDomainProgress,
    IntegrationDomainProgressStage,
    IntegrationEvolutionCheckpoint,
    IntegrationCapabilityCheckpoint,
    IntegrationOperationRecord,
    IntegrationOperationStage,
    IntegrationRequestQueryResult,
    IntegrationRequestQueryStatus,
    LedgerLookupStatus,
    format_contract_datetime,
)
from continuity_engine.domain.perception import (
    PerceivedPlatformFact,
    PerceptionContext,
    PerceptionResult,
)
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.domain.thinking import (
    ThinkSession,
    ThinkSessionStatus,
    ThinkingDepth,
    ThinkingExecutionResult,
)
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.capability_coordination_service import (
    CapabilityCoordinationService,
)
from continuity_engine.services.capability_result_interpreter import (
    CapabilityResultInterpreter,
)
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from continuity_engine.services.integration_contract_validation import MachineContractValidator
from continuity_engine.services.integration_ports import (
    IntegrationReplyComposer,
    SubjectBindingRepository,
)
from continuity_engine.services.integration_result_factory import FirstRoundResultFactory
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.base import IntegrationResultLedger


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]
TraceSink = Callable[[str], None]
FaultInjector = Callable[[str, IntegrationOperationRecord], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _operation_id() -> str:
    return f"operation-{uuid4()}"


def _response_id() -> str:
    return f"response-{uuid4()}"


def _contract_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


class ContinuityInteractionService:
    """The single formal first-round interaction and recovery pipeline."""

    def __init__(
        self,
        *,
        validator: MachineContractValidator,
        bindings: SubjectBindingRepository,
        ledger: IntegrationResultLedger,
        subject_states: SubjectStateService,
        awakening: AwakeningService,
        perception: PerceptionService,
        thinking: ThinkingService,
        action: ActionService,
        action_evolution: ActionEvolutionService,
        reply_composer: IntegrationReplyComposer,
        available_permissions: Iterable[str] = (),
        resource_limits: ResourceLimits | None = None,
        clock: Clock = _utc_now,
        operation_id_factory: IdFactory = _operation_id,
        response_id_factory: IdFactory = _response_id,
        trace: TraceSink | None = None,
        fault_injector: FaultInjector | None = None,
        thinking_mode: IntegrationThinkingMode = IntegrationThinkingMode.DETERMINISTIC,
        capabilities: CapabilityCoordinationService | None = None,
        capability_interpreter: CapabilityResultInterpreter | None = None,
        result_factory: FirstRoundResultFactory | None = None,
    ) -> None:
        self._validator = validator
        self._bindings = bindings
        self._ledger = ledger
        self._subject_states = subject_states
        self._awakening = awakening
        self._perception = perception
        self._thinking = thinking
        self._action = action
        self._action_evolution = action_evolution
        self._reply_composer = reply_composer
        self._available_permissions = list(available_permissions)
        self._resource_limits = resource_limits or ResourceLimits()
        self._clock = clock
        self._operation_id_factory = operation_id_factory
        self._response_id_factory = response_id_factory
        self._trace_sink = trace
        self._fault_injector = fault_injector
        if not isinstance(thinking_mode, IntegrationThinkingMode):
            raise ValueError("thinking_mode is invalid")
        if thinking_mode is IntegrationThinkingMode.CAPABILITY and capabilities is None:
            raise ValueError("capability thinking mode requires capability coordination")
        self._thinking_mode = thinking_mode
        self._capabilities = capabilities
        self._capability_interpreter = (
            capability_interpreter or CapabilityResultInterpreter()
        )
        self._result_factory = result_factory
        self.last_call_log: list[str] = []

    @property
    def thinking_mode(self) -> IntegrationThinkingMode:
        return self._thinking_mode

    def submit(
        self,
        payload: Any,
    ) -> (
        FirstRoundSuccessResult
        | FirstRoundErrorEnvelope
        | CapabilityRequiredEnvelope
        | CapabilityFailedEnvelope
    ):
        request_id = self.safe_request_id(payload)
        self.last_call_log = []
        operation: IntegrationOperationRecord | None = None
        stage = "schema"
        try:
            self._record("schema")
            try:
                request = self._validator.validate_request(payload)
            except (MachineContractSchemaError, MachineContractValidationError):
                if self._is_binding_version_only_mismatch(payload):
                    return self._error(request_id, FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH)
                return self._error(request_id, FirstRoundErrorCode.SCHEMA_INVALID)

            stage = "binding"
            self._record("binding")
            binding = self._validated_binding(request)
            if binding is None:
                return self._error(request_id, FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH)

            stage = "ledger"
            self._record("ledger")
            lookup = self._ledger.lookup(request.request_id, request.request_hash)
            if lookup.status is LedgerLookupStatus.COMPLETED:
                assert lookup.result is not None
                completed_operation = self._ledger.load_operation(request.request_id)
                if (
                    completed_operation is not None
                    and completed_operation.stage is not IntegrationOperationStage.COMPLETED
                ):
                    self._ledger.save_operation(
                        replace(
                            completed_operation,
                            stage=IntegrationOperationStage.COMPLETED,
                            updated_at=lookup.result.completed_at,
                        )
                    )
                self._record("replay")
                return lookup.result
            if lookup.status is LedgerLookupStatus.HASH_CONFLICT:
                return self._error(request_id, FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED)

            operation = self._ledger.load_operation(request.request_id)
            if operation is None:
                stage = "revision"
                self._record("revision")
                state = self._subject_states.load(binding.subject_id)
                if request.expected_engine_revision != state.revision:
                    return self._error(
                        request_id,
                        FirstRoundErrorCode.REVISION_CONFLICT,
                        current_engine_revision=state.revision,
                    )
                stage = "operation"
                self._record("operation")
                now = format_contract_datetime(self._clock())
                operation = IntegrationOperationRecord(
                    request_id=request.request_id,
                    request_hash=request.request_hash,
                    operation_id=self._operation_id_factory(),
                    subject_id=binding.subject_id,
                    binding_id=binding.binding_id,
                    binding_version=binding.binding_version,
                    input_revision=state.revision,
                    consumed_observation_ids=(request.observations[0].observation_id,),
                    stage=IntegrationOperationStage.RESERVED,
                    reserved_at=now,
                    updated_at=now,
                )
                self._ledger.save_operation(operation)
                self._fault("after_operation_reserved", operation)
            else:
                self._record("operation_recovery")

            if operation.domain is None:
                stage = "domain"
                operation, thinking_execution = self._run_domain(request, operation, binding)
                if thinking_execution is None:
                    return self._capability_status_envelope(operation)
                self._ledger.save_operation(operation)
                self._fault("after_domain_completed", operation)
            else:
                thinking_execution = self._restore_domain_thinking(operation)
            stage = "completion"
            return self._finish_operation(binding, operation, thinking_execution)
        except IntegrationExecutionError:
            raise
        except Exception as exc:
            raise IntegrationExecutionError(
                request_id=request_id,
                operation_id=operation.operation_id if operation is not None else None,
                stage=stage,
                message=f"Local integration encountered an unexpected execution fault during {stage}.",
            ) from exc

    def submit_capability_result(
        self,
        payload: Any,
    ) -> FirstRoundSuccessResult | CapabilityRequiredEnvelope | CapabilityFailedEnvelope:
        if self._thinking_mode is not IntegrationThinkingMode.CAPABILITY:
            raise CapabilityValidationError(
                "CapabilityResult submission requires capability thinking mode"
            )
        assert self._capabilities is not None
        self.last_call_log = []
        self._record("capability_result_validation")
        validated_result = self._capabilities.validator.validate_result(payload)
        request_id = validated_result.request_id
        operation = self._ledger.load_operation(request_id)
        if operation is None:
            raise CapabilityNotFoundError(
                "CapabilityResult requestId does not identify an operation"
            )
        try:
            self._fault("after_capability_result_received", operation)
            attempt = self._capabilities.accept_result(
                payload,
                operation,
                received_at=self._clock(),
            )
            self._fault("after_capability_result_persisted", operation)
            result = attempt.result
            completed = self._ledger.load_completed(request_id)
            if completed is not None:
                if operation.stage is not IntegrationOperationStage.COMPLETED:
                    self._ledger.save_operation(
                        replace(
                            operation,
                            stage=IntegrationOperationStage.COMPLETED,
                            updated_at=completed.completed_at,
                        )
                    )
                return completed
            if operation.domain is not None:
                binding = self._bindings.load_active()
                thinking = self._restore_domain_thinking(operation)
                return self._finish_operation(binding, operation, thinking)
            checkpoint = IntegrationCapabilityCheckpoint(
                capability_request_id=result.capability_request_id,
                status=result.status,
                accepted_result_id=result.capability_result_id,
                accepted_result_hash=attempt.result_hash,
                updated_at=attempt.received_at,
            )
            operation = replace(
                operation,
                stage=(
                    operation.stage
                    if operation.stage is IntegrationOperationStage.COMPLETED
                    else IntegrationOperationStage.WAITING_CAPABILITY
                ),
                updated_at=attempt.received_at,
                capability=checkpoint,
            )
            if operation.stage is not IntegrationOperationStage.COMPLETED:
                self._ledger.save_operation(operation)
            self._fault("after_capability_result_checkpoint_saved", operation)

            if result.status.requires_capability:
                request = self._capability_request_for_operation(operation)
                assert request is not None
                return self._capability_required(operation, request)
            if result.status.failed_terminally:
                return self._capability_failed(operation, result)

            binding = self._bindings.load_active()
            operation, thinking = self._resume_capability_domain(
                operation,
                binding,
                result,
            )
            self._ledger.save_operation(operation)
            self._fault("after_domain_completed", operation)
            return self._finish_operation(binding, operation, thinking)
        except (
            CapabilityConflictError,
            CapabilityValidationError,
            CapabilityNotFoundError,
        ):
            raise
        except IntegrationExecutionError:
            raise
        except Exception as exc:
            raise IntegrationExecutionError(
                request_id=request_id,
                operation_id=operation.operation_id,
                stage="capability_result",
                message=(
                    "Local integration encountered an unexpected execution fault "
                    "during capability_result."
                ),
            ) from exc

    def query_request(
        self,
        request_id: str,
    ) -> (
        IntegrationRequestQueryResult
        | CapabilityRequiredEnvelope
        | CapabilityFailedEnvelope
        | None
    ):
        if not isinstance(request_id, str) or not request_id.strip():
            raise MachineContractCallError("requestId must be a safe non-empty string")
        completed = self._ledger.load_completed(request_id)
        operation = self._ledger.load_operation(request_id)
        if completed is not None:
            if operation is None:
                raise IntegrationPersistenceError(
                    "completed result is missing its operation journal record"
                )
            return IntegrationRequestQueryResult(
                request_id=completed.request_id,
                request_hash=completed.request_hash,
                operation_id=completed.operation_id,
                status=IntegrationRequestQueryStatus.COMPLETED,
                result=completed,
            )
        if operation is None:
            return None
        if self._thinking_mode is IntegrationThinkingMode.CAPABILITY:
            request = self._capability_request_for_operation(operation)
            if request is not None:
                latest = self._capabilities.latest_attempt(
                    request.capability_request_id
                )
                if latest is None or latest.result.status.requires_capability:
                    return self._capability_required(operation, request)
                if latest.result.status.failed_terminally:
                    return self._capability_failed(operation, latest.result)
        return IntegrationRequestQueryResult(
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            operation_id=operation.operation_id,
            status=IntegrationRequestQueryStatus.RECOVERY_REQUIRED,
            result=None,
        )

    def _finish_operation(
        self,
        binding: SubjectBinding,
        operation: IntegrationOperationRecord,
        thinking: ThinkingExecutionResult | None,
    ) -> FirstRoundSuccessResult:
        assert operation.domain is not None
        if operation.domain.approved_state_action is not None and operation.evolution is None:
            operation = self._complete_evolution(operation, thinking)
        result = self._build_result(binding, operation)
        self._record("result")
        existing = self._ledger.load_completed(result.request_id)
        if existing is None:
            self._ledger.save_completed(result)
            self._fault("after_completed_result_saved", operation)
        elif existing != result:
            raise IntegrationPersistenceError(
                "completed interaction result cannot be replaced"
            )
        else:
            result = existing
        self._ledger.save_operation(
            replace(
                operation,
                stage=IntegrationOperationStage.COMPLETED,
                updated_at=result.completed_at,
            )
        )
        self._record("completed")
        return result

    @staticmethod
    def safe_request_id(payload: Any) -> str:
        if not isinstance(payload, Mapping):
            raise MachineContractCallError(
                "a local contract call requires an object with a non-empty requestId"
            )
        request_id = payload.get("requestId")
        if not isinstance(request_id, str) or not request_id.strip():
            raise MachineContractCallError(
                "a local contract call requires a safe non-empty requestId"
            )
        return request_id

    def _validated_binding(self, request: ContinuityInteractionRequest) -> SubjectBinding | None:
        try:
            binding = self._bindings.load_active()
            self._validator.validate_fixed_subject_binding(
                binding.to_fixture().to_dict(),
                binding_fixture_hash=binding.binding_fixture_hash,
            )
        except (IntegrationPersistenceError, MachineContractValidationError):
            return None
        identity = request.identity
        if (
            binding.status != "active"
            or identity.user_id != binding.user_id
            or identity.assistant_id != binding.assistant_id
            or identity.subject_id != binding.subject_id
            or identity.binding_id != binding.binding_id
            or identity.binding_version != binding.binding_version
        ):
            return None
        return binding

    def _is_binding_version_only_mismatch(self, payload: Any) -> bool:
        try:
            identities = (
                payload["identity"],
                payload["observations"][0]["identity"],
                payload["platformFactPackage"]["facts"][0]["identity"],
            )
            versions = [item["bindingVersion"] for item in identities]
            if (
                any(isinstance(item, bool) or not isinstance(item, int) for item in versions)
                or len(set(versions)) != 1
                or versions[0] == 1
                or payload.get("requestHash") != calculate_request_hash(payload)
            ):
                return False
            normalized = copy.deepcopy(payload)
            normalized["identity"]["bindingVersion"] = 1
            normalized["observations"][0]["identity"]["bindingVersion"] = 1
            normalized["platformFactPackage"]["facts"][0]["identity"]["bindingVersion"] = 1
            normalized["requestHash"] = calculate_request_hash(normalized)
            self._validator.validate_request(normalized)
            return True
        except (
            KeyError,
            IndexError,
            TypeError,
            MachineContractSchemaError,
            MachineContractValidationError,
        ):
            return False

    def _run_domain(
        self,
        request: ContinuityInteractionRequest,
        operation: IntegrationOperationRecord,
        binding: SubjectBinding,
    ) -> tuple[IntegrationOperationRecord, ThinkingExecutionResult | None]:
        observation = request.observations[0]
        fact = request.platform_fact_package.facts[0]
        perceived_fact = PerceivedPlatformFact(
            observation_id=observation.observation_id,
            source_event_id=observation.source_event_id,
            observation_type=observation.observation_type,
            fact_id=fact.fact_id,
            conversation_id=fact.conversation_id,
            message_id=fact.message_id,
            message_version_id=fact.message_version_id,
            content=fact.content,
            occurred_at=_contract_datetime(observation.occurred_at),
            observed_at=_contract_datetime(observation.observed_at),
        )
        operation = self._prepare_domain_progress(operation)
        assert operation.domain_progress is not None
        progress = operation.domain_progress

        self._record("wake")
        if progress.wake_context is None:
            legacy_thinking = self._load_think_session_if_present(
                operation.subject_id,
                progress.think_session_id,
            )
            try:
                wake_session = self._awakening.get_session(
                    operation.subject_id,
                    progress.wake_session_id,
                )
            except StateNotFoundError:
                awakening = self._awakening.wake_manual(
                    binding.cycle_id,
                    detail="Process one validated first-round PlatformObservation.",
                    session_id=progress.wake_session_id,
                    context_id=progress.wake_context_id,
                    preserve_recovery_context=True,
                )
            else:
                self._validate_wake_session(
                    wake_session,
                    operation=operation,
                    cycle_id=binding.cycle_id,
                    progress=progress,
                )
                awakening = self._awakening.recover_completed(
                    wake_session,
                    context_id=progress.wake_context_id,
                    legacy_context_time=(
                        legacy_thinking.started_at
                        if legacy_thinking is not None
                        else None
                    ),
                )
            self._fault("after_wake_completed", operation)
            perception_at = (
                legacy_thinking.perception_snapshot.perceived_at
                if (
                    legacy_thinking is not None
                    and legacy_thinking.perception_snapshot is not None
                )
                else (
                    legacy_thinking.started_at
                    if legacy_thinking is not None
                    else self._clock()
                )
            )
            progress = replace(
                progress,
                stage=IntegrationDomainProgressStage.WAKE_COMPLETED,
                wake_context=awakening.context,
                perception_at=format_contract_datetime(perception_at),
            )
            operation = self._save_domain_progress(operation, progress)
            self._fault("after_wake_checkpoint_saved", operation)
        else:
            wake_session = self._awakening.get_session(
                operation.subject_id,
                progress.wake_session_id,
            )
            self._validate_wake_session(
                wake_session,
                operation=operation,
                cycle_id=binding.cycle_id,
                progress=progress,
            )
            awakening = AwakeningResult(
                context=progress.wake_context,
                session=wake_session,
            )

        assert progress.perception_at is not None
        self._record("perception")
        if progress.perception is None:
            existing_thinking = self._load_think_session_if_present(
                operation.subject_id,
                progress.think_session_id,
            )
            if (
                existing_thinking is not None
                and existing_thinking.perception_snapshot is not None
            ):
                perception = PerceptionResult.from_dict(
                    existing_thinking.perception_snapshot.to_dict()
                )
            else:
                context = PerceptionContext.from_awakening(
                    awakening,
                    current_time=_contract_datetime(progress.perception_at),
                    context_id=progress.perception_context_id,
                    external_facts=(perceived_fact,),
                )
                perception = self._perception.perceive(
                    context,
                    perception_id=progress.perception_id,
                )
            self._validate_perception(
                perception,
                operation=operation,
                progress=progress,
                perceived_fact=perceived_fact,
            )
            if existing_thinking is not None:
                self._validate_thinking_observation(existing_thinking, perception)
            progress = replace(
                progress,
                stage=IntegrationDomainProgressStage.PERCEPTION_COMPLETED,
                perception=perception,
            )
            operation = self._save_domain_progress(operation, progress)
            self._fault("after_perception_checkpoint_saved", operation)
        else:
            perception = progress.perception
            self._validate_perception(
                perception,
                operation=operation,
                progress=progress,
                perceived_fact=perceived_fact,
            )

        if self._thinking_mode is IntegrationThinkingMode.CAPABILITY:
            return self._run_capability_domain(
                operation,
                binding,
                awakening,
                perception,
            )

        self._record("thinking")
        existing_thinking = self._load_think_session_if_present(
            operation.subject_id,
            progress.think_session_id,
        )
        if existing_thinking is None:
            thinking = self._thinking.handle_perception(
                perception,
                depth=ThinkingDepth.NORMAL,
                think_id=progress.think_session_id,
                result_id=progress.thinking_result_id,
                preserve_perception_snapshot=True,
            )
        else:
            self._validate_completed_thinking(
                existing_thinking,
                operation=operation,
                progress=progress,
                perception=perception,
            )
            thinking = ThinkingExecutionResult(
                perception=perception,
                session=existing_thinking,
                state_update=None,
            )
        self._fault("after_thinking_completed", operation)
        if progress.stage not in {
            IntegrationDomainProgressStage.THINKING_COMPLETED,
            IntegrationDomainProgressStage.ACTION_COMPLETED,
        }:
            action_at = format_contract_datetime(self._clock())
            progress = replace(
                progress,
                stage=IntegrationDomainProgressStage.THINKING_COMPLETED,
                action_at=action_at,
                response_completed_at=action_at,
            )
            operation = self._save_domain_progress(operation, progress)
            self._fault("after_thinking_checkpoint_saved", operation)

        return self._complete_domain_after_thinking(
            operation,
            awakening,
            perception,
            thinking,
        )

    def _run_capability_domain(
        self,
        operation: IntegrationOperationRecord,
        binding: SubjectBinding,
        awakening: AwakeningResult,
        perception: PerceptionResult,
    ) -> tuple[IntegrationOperationRecord, ThinkingExecutionResult | None]:
        assert self._capabilities is not None
        assert operation.domain_progress is not None
        progress = operation.domain_progress
        self._record("capability_request")
        self._fault("before_capability_request_created", operation)
        request = self._capabilities.ensure_request(
            operation,
            binding,
            perception,
            created_at=self._clock(),
        )
        self._fault("after_capability_request_saved", operation)

        existing = self._load_think_session_if_present(
            operation.subject_id,
            progress.think_session_id,
        )
        if existing is None:
            self._thinking.begin_capability_wait(
                perception,
                capability_request_id=request.capability_request_id,
                depth=ThinkingDepth.NORMAL,
                think_id=progress.think_session_id,
                preserve_perception_snapshot=True,
                started_at=_contract_datetime(request.created_at),
            )
        else:
            self._validate_capability_thinking(
                existing,
                operation=operation,
                progress=progress,
                perception=perception,
                capability_request_id=request.capability_request_id,
            )

        latest = self._capabilities.latest_attempt(request.capability_request_id)
        checkpoint = IntegrationCapabilityCheckpoint(
            capability_request_id=request.capability_request_id,
            status=(latest.result.status if latest is not None else CapabilityStatus.PROPOSED),
            accepted_result_id=(
                latest.result.capability_result_id if latest is not None else None
            ),
            accepted_result_hash=(latest.result_hash if latest is not None else None),
            updated_at=(latest.received_at if latest is not None else request.created_at),
        )
        if operation.capability != checkpoint or (
            operation.stage is IntegrationOperationStage.RESERVED
        ):
            operation = replace(
                operation,
                stage=IntegrationOperationStage.WAITING_CAPABILITY,
                updated_at=checkpoint.updated_at,
                capability=checkpoint,
            )
            self._ledger.save_operation(operation)
        self._fault("after_capability_request_checkpoint_saved", operation)

        if latest is None or latest.result.status.requires_capability:
            return operation, None
        if latest.result.status.failed_terminally:
            return operation, None
        return self._resume_capability_domain(
            operation,
            binding,
            latest.result,
            awakening=awakening,
        )

    def _resume_capability_domain(
        self,
        operation: IntegrationOperationRecord,
        binding: SubjectBinding,
        result: CapabilityResult,
        *,
        awakening: AwakeningResult | None = None,
    ) -> tuple[IntegrationOperationRecord, ThinkingExecutionResult]:
        assert self._capabilities is not None
        progress = operation.domain_progress
        if progress is None or progress.perception is None:
            raise CapabilityValidationError(
                "capability recovery requires durable Perception progress"
            )
        perception = progress.perception
        request = self._capability_request_for_operation(operation)
        if request is None or request.capability_request_id != result.capability_request_id:
            raise CapabilityValidationError(
                "CapabilityResult does not match the operation request"
            )
        session = self._load_think_session_if_present(
            operation.subject_id,
            progress.think_session_id,
        )
        if session is None:
            session = self._thinking.begin_capability_wait(
                perception,
                capability_request_id=request.capability_request_id,
                depth=ThinkingDepth.NORMAL,
                think_id=progress.think_session_id,
                preserve_perception_snapshot=True,
                started_at=_contract_datetime(request.created_at),
            )
        self._validate_capability_thinking(
            session,
            operation=operation,
            progress=progress,
            perception=perception,
            capability_request_id=request.capability_request_id,
        )
        self._record("thinking_resume")
        if session.status in {
            ThinkSessionStatus.WAITING_CAPABILITY,
            ThinkSessionStatus.RUNNING,
        }:
            thinking_result = self._capability_interpreter.interpret(
                result,
                session,
                thinking_result_id=progress.thinking_result_id,
            )
            thinking = self._thinking.complete_capability_wait(
                perception,
                think_id=progress.think_session_id,
                result=thinking_result,
                ended_at=_contract_datetime(result.completed_at),
            )
        else:
            self._validate_completed_thinking(
                session,
                operation=operation,
                progress=progress,
                perception=perception,
            )
            thinking = ThinkingExecutionResult(
                perception=perception,
                session=session,
                state_update=None,
            )
        self._fault("after_capability_thinking_completed", operation)
        if progress.stage not in {
            IntegrationDomainProgressStage.THINKING_COMPLETED,
            IntegrationDomainProgressStage.ACTION_COMPLETED,
        }:
            progress = replace(
                progress,
                stage=IntegrationDomainProgressStage.THINKING_COMPLETED,
                action_at=result.completed_at,
                response_completed_at=result.completed_at,
            )
            operation = self._save_domain_progress(operation, progress)
            self._fault("after_capability_thinking_checkpoint_saved", operation)
        if awakening is None:
            wake_session = self._awakening.get_session(
                operation.subject_id,
                progress.wake_session_id,
            )
            self._validate_wake_session(
                wake_session,
                operation=operation,
                cycle_id=binding.cycle_id,
                progress=progress,
            )
            awakening = AwakeningResult(
                context=progress.wake_context,
                session=wake_session,
            )
        return self._complete_domain_after_thinking(
            operation,
            awakening,
            perception,
            thinking,
        )

    def _complete_domain_after_thinking(
        self,
        operation: IntegrationOperationRecord,
        awakening: AwakeningResult,
        perception: PerceptionResult,
        thinking: ThinkingExecutionResult,
    ) -> tuple[IntegrationOperationRecord, ThinkingExecutionResult]:
        progress = operation.domain_progress
        assert progress is not None
        assert progress.action_at is not None
        assert progress.response_completed_at is not None
        if progress.action is None:
            self._record("action")
            action_context = ActionContext.from_results(
                subject_id=operation.subject_id,
                subject_state_revision=operation.input_revision,
                thinking=thinking,
                perception=perception,
                current_time=_contract_datetime(progress.action_at),
                available_permissions=self._available_permissions,
                resource_limits=self._resource_limits,
                context_id=progress.action_context_id,
            )
            action = self._action.decide(action_context)
            progress = replace(
                progress,
                stage=IntegrationDomainProgressStage.ACTION_COMPLETED,
                action=action,
            )
            operation = self._save_domain_progress(operation, progress)
        else:
            self._record("action_reused")
            action = progress.action
        self._fault("after_action_completed", operation)
        response_content = self._reply_composer.compose(thinking, action)
        approved = ApprovedStateAction.from_execution(action)
        checkpoint = IntegrationDomainCheckpoint(
            response_id=progress.response_id,
            response_content=response_content,
            response_completed_at=progress.response_completed_at,
            wake_session_id=awakening.session.session_id,
            perception_id=perception.perception_id,
            think_session_id=thinking.session.think_id,
            thinking_result_id=action.context.thinking_result.result_id,
            action_session_id=action.session.action_session_id,
            action_decision_id=action.decision.decision_id,
            action_plan_id=action.plan.plan_id,
            selected_action=action.decision.selected_action.action_type.value,
            action_approved=action.decision.approved,
            action_requires_confirmation=action.decision.requires_confirmation,
            action_plan_status=action.plan.status.value,
            approved_state_action=approved,
        )
        return (
            replace(
                operation,
                stage=IntegrationOperationStage.DOMAIN_COMPLETED,
                updated_at=progress.response_completed_at,
                domain=checkpoint,
            ),
            thinking,
        )

    def _capability_request_for_operation(self, operation: IntegrationOperationRecord):
        if self._capabilities is None:
            return None
        return self._capabilities.find_request_by_operation(operation.operation_id)

    def _capability_status_envelope(
        self,
        operation: IntegrationOperationRecord,
    ) -> CapabilityRequiredEnvelope | CapabilityFailedEnvelope:
        assert self._capabilities is not None
        request = self._capability_request_for_operation(operation)
        if request is None:
            raise CapabilityValidationError(
                "waiting operation is missing its CapabilityRequest"
            )
        latest = self._capabilities.latest_attempt(request.capability_request_id)
        if latest is not None and latest.result.status.failed_terminally:
            return self._capability_failed(operation, latest.result)
        return self._capability_required(operation, request)

    @staticmethod
    def _capability_required(operation, request) -> CapabilityRequiredEnvelope:
        return CapabilityRequiredEnvelope(
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            operation_id=operation.operation_id,
            subject_id=operation.subject_id,
            capability_request=request,
            updated_at=(
                operation.capability.updated_at
                if operation.capability is not None
                else request.created_at
            ),
        )

    @staticmethod
    def _capability_failed(
        operation: IntegrationOperationRecord,
        result: CapabilityResult,
    ) -> CapabilityFailedEnvelope:
        assert result.error_code is not None
        assert result.retry_class is not None
        return CapabilityFailedEnvelope(
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            operation_id=operation.operation_id,
            subject_id=operation.subject_id,
            capability_request_id=result.capability_request_id,
            failure_status=result.status,
            error_code=result.error_code,
            retry_class=result.retry_class,
            updated_at=(
                operation.capability.updated_at
                if operation.capability is not None
                else result.completed_at
            ),
        )

    def _validate_capability_thinking(
        self,
        session: ThinkSession,
        *,
        operation: IntegrationOperationRecord,
        progress: IntegrationDomainProgress,
        perception: PerceptionResult,
        capability_request_id: str,
    ) -> None:
        if (
            session.think_id != progress.think_session_id
            or session.wake_session_id != progress.wake_session_id
            or session.subject_id != operation.subject_id
            or session.provider_id != self._thinking.provider_id
            or session.capability_request_id != capability_request_id
            or session.status
            not in {
                ThinkSessionStatus.RUNNING,
                ThinkSessionStatus.WAITING_CAPABILITY,
                ThinkSessionStatus.COMPLETED,
            }
        ):
            raise CapabilityValidationError(
                "persisted capability ThinkSession does not match operation identity"
            )
        self._validate_thinking_observation(session, perception)

    def _prepare_domain_progress(
        self,
        operation: IntegrationOperationRecord,
    ) -> IntegrationOperationRecord:
        if operation.domain_progress is not None:
            return operation
        wake_session_id = str(
            uuid5(NAMESPACE_URL, f"first-round-wake|{operation.operation_id}")
        )
        candidates = [
            session
            for session in self._thinking.get_sessions(operation.subject_id)
            if session.wake_session_id == wake_session_id
            and session.provider_id == self._thinking.provider_id
        ]
        if len(candidates) > 1:
            raise RuntimeError(
                "legacy recovery found multiple ThinkSessions for one operation"
            )
        existing = candidates[0] if candidates else None
        if existing is not None:
            if not existing.completed_successfully or existing.result is None:
                raise RuntimeError(
                    "legacy recovery found a non-completed ThinkSession"
                )
            if (
                existing.subject_id != operation.subject_id
                or existing.observation.state_revision != operation.input_revision
                or existing.observation.perception_id is None
            ):
                raise RuntimeError(
                    "legacy ThinkSession does not match the operation identity"
                )
            wake_context_id = existing.observation.wake_context_id
            perception_id = existing.observation.perception_id
            think_session_id = existing.think_id
            thinking_result_id = existing.result.result_id
        else:
            wake_context_id = str(
                uuid5(NAMESPACE_URL, f"first-round-wake-context|{operation.operation_id}")
            )
            perception_id = str(
                uuid5(NAMESPACE_URL, f"first-round-perception-result|{operation.operation_id}")
            )
            think_session_id = str(
                uuid5(NAMESPACE_URL, f"first-round-thinking|{operation.operation_id}")
            )
            thinking_result_id = str(
                uuid5(NAMESPACE_URL, f"first-round-thinking-result|{operation.operation_id}")
            )
        progress = IntegrationDomainProgress(
            stage=IntegrationDomainProgressStage.PREPARED,
            wake_session_id=wake_session_id,
            wake_context_id=wake_context_id,
            perception_context_id=str(
                uuid5(NAMESPACE_URL, f"first-round-perception|{operation.operation_id}")
            ),
            perception_id=perception_id,
            think_session_id=think_session_id,
            thinking_result_id=thinking_result_id,
            action_context_id=str(
                uuid5(NAMESPACE_URL, f"first-round-action|{operation.operation_id}")
            ),
            response_id=self._response_id_factory(),
        )
        prepared = self._save_domain_progress(operation, progress)
        self._fault("after_domain_progress_prepared", prepared)
        return prepared

    def _save_domain_progress(
        self,
        operation: IntegrationOperationRecord,
        progress: IntegrationDomainProgress,
    ) -> IntegrationOperationRecord:
        updated = replace(
            operation,
            updated_at=format_contract_datetime(self._clock()),
            domain_progress=progress,
        )
        self._ledger.save_operation(updated)
        return updated

    def _load_think_session_if_present(
        self,
        subject_id: str,
        think_session_id: str,
    ) -> ThinkSession | None:
        try:
            return self._thinking.get_session(subject_id, think_session_id)
        except StateNotFoundError:
            return None

    @staticmethod
    def _validate_wake_session(
        session,
        *,
        operation: IntegrationOperationRecord,
        cycle_id: str,
        progress: IntegrationDomainProgress,
    ) -> None:
        if (
            session.session_id != progress.wake_session_id
            or session.cycle_id != cycle_id
            or session.subject_id != operation.subject_id
            or session.subject_revision != operation.input_revision
            or not session.completed_successfully
            or session.decision is None
            or session.observation.context_id != progress.wake_context_id
        ):
            raise RuntimeError(
                "persisted WakeSession does not match the recoverable operation"
            )

    @staticmethod
    def _validate_perception(
        perception: PerceptionResult,
        *,
        operation: IntegrationOperationRecord,
        progress: IntegrationDomainProgress,
        perceived_fact: PerceivedPlatformFact,
    ) -> None:
        if (
            perception.perception_id != progress.perception_id
            or perception.subject_id != operation.subject_id
            or perception.source_revision != operation.input_revision
            or perception.wake_session_id != progress.wake_session_id
            or perception.wake_context_id != progress.wake_context_id
            or perception.perceived_at != _contract_datetime(progress.perception_at or "")
            or perception.external_facts != (perceived_fact,)
        ):
            raise RuntimeError(
                "persisted PerceptionResult does not match the recoverable operation"
            )

    @staticmethod
    def _validate_thinking_observation(
        session: ThinkSession,
        perception: PerceptionResult,
    ) -> None:
        observation = session.observation
        if (
            observation.perception_id != perception.perception_id
            or observation.perception_summary != perception.summary
            or observation.wake_context_id != perception.wake_context_id
            or observation.state_revision != perception.source_revision
            or observation.event_ids != perception.recent_event_ids
            or observation.update_ids != perception.recent_update_ids
            or observation.viewed_memory_ids != perception.viewed_memory_ids
            or observation.selected_memory_ids != perception.selected_memory_ids
            or observation.perceived_external_fact_ids
            != [item.fact_id for item in perception.external_facts]
        ):
            raise RuntimeError(
                "persisted ThinkSession observation does not match PerceptionResult"
            )

    def _validate_completed_thinking(
        self,
        session: ThinkSession,
        *,
        operation: IntegrationOperationRecord,
        progress: IntegrationDomainProgress,
        perception: PerceptionResult,
    ) -> None:
        if (
            session.think_id != progress.think_session_id
            or session.wake_session_id != progress.wake_session_id
            or session.subject_id != operation.subject_id
            or session.provider_id != self._thinking.provider_id
            or not session.completed_successfully
            or session.result is None
            or session.result.result_id != progress.thinking_result_id
        ):
            raise RuntimeError(
                "persisted ThinkSession does not match the recoverable operation"
            )
        self._validate_thinking_observation(session, perception)

    def _restore_domain_thinking(
        self,
        operation: IntegrationOperationRecord,
    ) -> ThinkingExecutionResult | None:
        progress = operation.domain_progress
        if progress is None:
            return None
        if (
            progress.stage
            not in {
                IntegrationDomainProgressStage.THINKING_COMPLETED,
                IntegrationDomainProgressStage.ACTION_COMPLETED,
            }
            or progress.perception is None
        ):
            raise RuntimeError(
                "domain checkpoint has incomplete durable Thinking progress"
            )
        session = self._thinking.get_session(
            operation.subject_id,
            progress.think_session_id,
        )
        self._validate_completed_thinking(
            session,
            operation=operation,
            progress=progress,
            perception=progress.perception,
        )
        return ThinkingExecutionResult(
            perception=progress.perception,
            session=session,
            state_update=None,
        )

    def _complete_evolution(
        self,
        operation: IntegrationOperationRecord,
        thinking: ThinkingExecutionResult | None,
    ) -> IntegrationOperationRecord:
        assert operation.domain is not None
        approved = operation.domain.approved_state_action
        assert approved is not None
        event_id = str(uuid5(NAMESPACE_URL, f"first-round-event|{operation.request_id}|{operation.operation_id}"))
        update = self._action_evolution.find_update_by_event_id(operation.subject_id, event_id)
        if update is None:
            self._record("evolution")
            update = self._action_evolution.evolve(
                approved,
                event_id=event_id,
                occurred_at=_contract_datetime(operation.domain.response_completed_at),
                metadata={
                    "integration_request_id": operation.request_id,
                    "integration_operation_id": operation.operation_id,
                },
            )
            assert update is not None
            self._fault("after_evolution_committed", operation)
        if (
            update.before_revision != operation.input_revision
            or update.after_revision != operation.input_revision + 1
            or update.event.event_id != event_id
            or update.event.metadata.get("integration_request_id") != operation.request_id
            or update.event.metadata.get("integration_operation_id") != operation.operation_id
        ):
            raise RuntimeError("recovered Evolution record does not match the operation")
        if thinking is not None:
            session = thinking.session
            if session.state_update_id not in (None, update.update_id):
                raise RuntimeError(
                    "ThinkSession references a different recovered state update"
                )
            if (
                session.state_update_id != update.update_id
                or session.state_event_id != update.event.event_id
                or not session.state_written_back
            ):
                self._thinking.record_evolution_result(thinking, update)
        evolved = replace(
            operation,
            stage=IntegrationOperationStage.EVOLUTION_COMMITTED,
            updated_at=format_contract_datetime(self._clock()),
            evolution=IntegrationEvolutionCheckpoint(
                event_id=event_id,
                update_id=update.update_id,
                output_revision=update.after_revision,
            ),
        )
        self._ledger.save_operation(evolved)
        self._fault("after_evolution_checkpoint_saved", evolved)
        return evolved

    def _build_result(
        self,
        binding: SubjectBinding,
        operation: IntegrationOperationRecord,
    ) -> FirstRoundSuccessResult:
        assert operation.domain is not None
        state = self._subject_states.load(operation.subject_id)
        expected_revision = (
            operation.evolution.output_revision
            if operation.evolution is not None
            else operation.input_revision
        )
        if state.revision != expected_revision:
            raise RuntimeError("authoritative SubjectState no longer matches the operation checkpoint")
        result_factory = self._result_factory or FirstRoundResultFactory(
            clock=self._clock,
            operation_id_factory=self._operation_id_factory,
            response_id_factory=self._response_id_factory,
        )
        return result_factory.create_completed_result(
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            binding=binding.to_fixture(),
            response_content=operation.domain.response_content,
            subject_state=state,
            previous_revision=operation.input_revision,
            engine_update_id=(
                operation.evolution.update_id if operation.evolution is not None else None
            ),
            consumed_observation_ids=operation.consumed_observation_ids,
            operation_id=operation.operation_id,
            response_id=operation.domain.response_id,
            completed_at=_contract_datetime(operation.domain.response_completed_at),
        )

    @staticmethod
    def _error(
        request_id: str,
        code: FirstRoundErrorCode,
        *,
        current_engine_revision: int | None = None,
    ) -> FirstRoundErrorEnvelope:
        return FirstRoundErrorEnvelope.create(
            request_id,
            code,
            current_engine_revision=current_engine_revision,
        )

    def _record(self, name: str) -> None:
        self.last_call_log.append(name)
        if self._trace_sink is not None:
            self._trace_sink(name)

    def _fault(self, stage: str, operation: IntegrationOperationRecord) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage, operation)
