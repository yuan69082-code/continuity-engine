from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from continuity_engine.domain.action import (
    ActionContext,
    ApprovedStateAction,
    ResourceLimits,
)
from continuity_engine.domain.errors import (
    ContractTestExecutionError,
    IntegrationPersistenceError,
    MachineContractCallError,
    MachineContractSchemaError,
    MachineContractValidationError,
)
from continuity_engine.domain.integration_contract import (
    ContinuityInteractionRequest,
    SubjectBindingFixture,
)
from continuity_engine.domain.integration_results import (
    FirstRoundErrorCode,
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationDomainCheckpoint,
    IntegrationEvolutionCheckpoint,
    IntegrationOperationRecord,
    IntegrationOperationStage,
    LedgerLookupStatus,
    format_contract_datetime,
)
from continuity_engine.domain.perception import (
    PerceivedPlatformFact,
    PerceptionContext,
)
from continuity_engine.domain.thinking import ThinkingDepth, ThinkingExecutionResult
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.contract_test_doubles import ContractReplyComposer
from continuity_engine.services.integration_contract_validation import (
    MachineContractValidator,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_request_hash,
)
from continuity_engine.services.integration_result_factory import (
    FirstRoundResultFactory,
)
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.base import (
    IntegrationResultLedger,
    SubjectBindingFixtureRepository,
)


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


class ContractTestAdapter:
    """Independent, test-only, in-process first-round contract boundary."""

    def __init__(
        self,
        *,
        validator: MachineContractValidator,
        bindings: SubjectBindingFixtureRepository,
        ledger: IntegrationResultLedger,
        subject_states: SubjectStateService,
        awakening: AwakeningService,
        perception: PerceptionService,
        thinking: ThinkingService,
        action: ActionService,
        action_evolution: ActionEvolutionService,
        reply_composer: ContractReplyComposer,
        cycle_id: str,
        available_permissions: Iterable[str] = (),
        resource_limits: ResourceLimits | None = None,
        clock: Clock = _utc_now,
        operation_id_factory: IdFactory = _operation_id,
        response_id_factory: IdFactory = _response_id,
        trace: TraceSink | None = None,
        fault_injector: FaultInjector | None = None,
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
        self._cycle_id = cycle_id
        self._available_permissions = list(available_permissions)
        self._resource_limits = resource_limits or ResourceLimits()
        self._clock = clock
        self._operation_id_factory = operation_id_factory
        self._response_id_factory = response_id_factory
        self._trace_sink = trace
        self._fault_injector = fault_injector
        self.last_call_log: list[str] = []

    def submit(
        self,
        payload: Any,
    ) -> FirstRoundSuccessResult | FirstRoundErrorEnvelope:
        request_id = self._safe_request_id(payload)
        self.last_call_log = []
        operation: IntegrationOperationRecord | None = None
        stage = "schema"
        try:
            self._record("schema")
            try:
                request = self._validator.validate_request(payload)
            except (MachineContractSchemaError, MachineContractValidationError):
                if self._is_binding_version_only_mismatch(payload):
                    return self._error(
                        request_id,
                        FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
                    )
                return self._error(request_id, FirstRoundErrorCode.SCHEMA_INVALID)

            stage = "binding"
            self._record("binding")
            binding = self._validated_binding(request)
            if binding is None:
                return self._error(
                    request_id,
                    FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
                )

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
                return self._error(
                    request_id,
                    FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED,
                )

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
                operation, thinking_execution = self._run_domain(
                    request,
                    operation,
                )
                self._ledger.save_operation(operation)
                self._fault("after_domain_completed", operation)
            else:
                thinking_execution = None

            if operation.domain.approved_state_action is not None:
                stage = "evolution"
                operation = self._complete_evolution(
                    operation,
                    thinking_execution,
                )

            stage = "result"
            result = self._build_result(binding, operation)
            self._record("result")
            self._ledger.save_completed(result)
            self._fault("after_completed_result_saved", operation)
            completed_operation = replace(
                operation,
                stage=IntegrationOperationStage.COMPLETED,
                updated_at=result.completed_at,
            )
            self._ledger.save_operation(completed_operation)
            self._record("completed")
            return result
        except ContractTestExecutionError:
            raise
        except Exception as exc:
            raise ContractTestExecutionError(
                request_id=request_id,
                operation_id=(operation.operation_id if operation is not None else None),
                stage=stage,
                message=(
                    "ContractTestAdapter encountered an unexpected local execution "
                    f"fault during {stage}."
                ),
            ) from exc

    @staticmethod
    def _safe_request_id(payload: Any) -> str:
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

    def _validated_binding(
        self,
        request: ContinuityInteractionRequest,
    ) -> SubjectBindingFixture | None:
        try:
            fixture, fixture_hash = self._bindings.load_fixed()
            validated = self._validator.validate_fixed_subject_binding(
                fixture.to_dict(),
                binding_fixture_hash=fixture_hash,
            )
        except (IntegrationPersistenceError, MachineContractValidationError):
            return None
        identity = request.identity
        if (
            validated.status != "active"
            or identity.user_id != validated.user_id
            or identity.assistant_id != validated.assistant_id
            or identity.subject_id != validated.subject_id
            or identity.binding_id != validated.binding_id
            or identity.binding_version != validated.binding_version
        ):
            return None
        return validated

    def _is_binding_version_only_mismatch(self, payload: Any) -> bool:
        """Honor the fixed binding error without weakening the strict E1 schema."""
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
            normalized["platformFactPackage"]["facts"][0]["identity"][
                "bindingVersion"
            ] = 1
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
    ) -> tuple[IntegrationOperationRecord, ThinkingExecutionResult]:
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

        self._record("wake")
        awakening = self._awakening.wake_manual(
            self._cycle_id,
            detail="Process one validated first-round PlatformObservation.",
            session_id=str(
                uuid5(NAMESPACE_URL, f"first-round-wake|{operation.operation_id}")
            ),
        )
        context = PerceptionContext.from_awakening(
            awakening,
            current_time=self._clock(),
            context_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"first-round-perception|{operation.operation_id}",
                )
            ),
            external_facts=(perceived_fact,),
        )
        self._record("perception")
        perception = self._perception.perceive(context)

        self._record("thinking")
        thinking = self._thinking.handle_perception(
            perception,
            depth=ThinkingDepth.NORMAL,
        )
        self._record("action")
        action_context = ActionContext.from_results(
            subject_id=operation.subject_id,
            subject_state_revision=operation.input_revision,
            thinking=thinking,
            perception=perception,
            current_time=self._clock(),
            available_permissions=self._available_permissions,
            resource_limits=self._resource_limits,
            context_id=str(
                uuid5(NAMESPACE_URL, f"first-round-action|{operation.operation_id}")
            ),
        )
        action = self._action.decide(action_context)
        response_content = self._reply_composer.compose(thinking, action)
        approved = ApprovedStateAction.from_execution(action)
        completed_at = format_contract_datetime(self._clock())
        checkpoint = IntegrationDomainCheckpoint(
            response_id=self._response_id_factory(),
            response_content=response_content,
            response_completed_at=completed_at,
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
                updated_at=completed_at,
                domain=checkpoint,
            ),
            thinking,
        )

    def _complete_evolution(
        self,
        operation: IntegrationOperationRecord,
        thinking: ThinkingExecutionResult | None,
    ) -> IntegrationOperationRecord:
        assert operation.domain is not None
        approved = operation.domain.approved_state_action
        assert approved is not None
        event_id = str(
            uuid5(
                NAMESPACE_URL,
                f"first-round-event|{operation.request_id}|{operation.operation_id}",
            )
        )
        update = self._action_evolution.find_update_by_event_id(
            operation.subject_id,
            event_id,
        )
        if update is None:
            self._record("evolution")
            update = self._action_evolution.evolve(
                approved,
                event_id=event_id,
                occurred_at=_contract_datetime(
                    operation.domain.response_completed_at
                ),
                metadata={
                    "integration_request_id": operation.request_id,
                    "integration_operation_id": operation.operation_id,
                },
            )
            assert update is not None
            if thinking is not None:
                self._thinking.record_evolution_result(thinking, update)
            self._fault("after_evolution_committed", operation)
        if (
            update.before_revision != operation.input_revision
            or update.after_revision != operation.input_revision + 1
            or update.event.event_id != event_id
            or update.event.metadata.get("integration_request_id")
            != operation.request_id
            or update.event.metadata.get("integration_operation_id")
            != operation.operation_id
        ):
            raise RuntimeError("recovered Evolution record does not match the operation")
        checkpoint = IntegrationEvolutionCheckpoint(
            event_id=event_id,
            update_id=update.update_id,
            output_revision=update.after_revision,
        )
        evolved = replace(
            operation,
            stage=IntegrationOperationStage.EVOLUTION_COMMITTED,
            updated_at=format_contract_datetime(self._clock()),
            evolution=checkpoint,
        )
        self._ledger.save_operation(evolved)
        self._fault("after_evolution_checkpoint_saved", evolved)
        return evolved

    def _build_result(
        self,
        binding: SubjectBindingFixture,
        operation: IntegrationOperationRecord,
    ) -> FirstRoundSuccessResult:
        assert operation.domain is not None
        state = self._subject_states.load(operation.subject_id)
        engine_update_id = (
            operation.evolution.update_id if operation.evolution is not None else None
        )
        expected_revision = (
            operation.evolution.output_revision
            if operation.evolution is not None
            else operation.input_revision
        )
        if state.revision != expected_revision:
            raise RuntimeError(
                "authoritative SubjectState no longer matches the operation checkpoint"
            )
        factory = FirstRoundResultFactory(
            clock=self._clock,
            operation_id_factory=self._operation_id_factory,
            response_id_factory=self._response_id_factory,
        )
        return factory.create_completed_result(
            request_id=operation.request_id,
            request_hash=operation.request_hash,
            binding=binding,
            response_content=operation.domain.response_content,
            subject_state=state,
            previous_revision=operation.input_revision,
            engine_update_id=engine_update_id,
            consumed_observation_ids=operation.consumed_observation_ids,
            operation_id=operation.operation_id,
            response_id=operation.domain.response_id,
            completed_at=_contract_datetime(
                operation.domain.response_completed_at
            ),
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
