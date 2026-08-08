from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from continuity_engine.domain.action import ResourceLimits
from continuity_engine.domain.integration_results import (
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationOperationRecord,
)
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.continuity_interaction_service import (
    ContinuityInteractionService,
    _operation_id,
    _response_id,
    _utc_now,
)
from continuity_engine.services.integration_contract_validation import MachineContractValidator
from continuity_engine.services.integration_ports import IntegrationReplyComposer
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.base import (
    IntegrationResultLedger,
    SubjectBindingFixtureRepository,
)


class _FixtureBindingReader:
    """Compatibility bridge from the immutable E3 fixture to the runtime port."""

    def __init__(self, repository: SubjectBindingFixtureRepository, cycle_id: str) -> None:
        self._repository = repository
        self._cycle_id = cycle_id

    def initialize(self, binding: SubjectBinding) -> None:
        raise RuntimeError("the E3 fixture reader is read-only")

    def load_active(self) -> SubjectBinding:
        fixture, fixture_hash = self._repository.load_fixed()
        return SubjectBinding.from_fixture(
            fixture,
            cycle_id=self._cycle_id,
            binding_fixture_hash=fixture_hash,
        )


class ContractTestAdapter:
    """Thin E3 compatibility adapter over the formal interaction service."""

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
        reply_composer: IntegrationReplyComposer,
        cycle_id: str,
        available_permissions: Iterable[str] = (),
        resource_limits: ResourceLimits | None = None,
        clock: Callable[[], datetime] = _utc_now,
        operation_id_factory: Callable[[], str] = _operation_id,
        response_id_factory: Callable[[], str] = _response_id,
        trace: Callable[[str], None] | None = None,
        fault_injector: Callable[[str, IntegrationOperationRecord], None] | None = None,
    ) -> None:
        self._service = ContinuityInteractionService(
            validator=validator,
            bindings=_FixtureBindingReader(bindings, cycle_id),
            ledger=ledger,
            subject_states=subject_states,
            awakening=awakening,
            perception=perception,
            thinking=thinking,
            action=action,
            action_evolution=action_evolution,
            reply_composer=reply_composer,
            available_permissions=available_permissions,
            resource_limits=resource_limits,
            clock=clock,
            operation_id_factory=operation_id_factory,
            response_id_factory=response_id_factory,
            trace=trace,
            fault_injector=fault_injector,
        )

    @property
    def service(self) -> ContinuityInteractionService:
        return self._service

    @property
    def last_call_log(self) -> list[str]:
        return self._service.last_call_log

    def submit(self, payload: Any) -> FirstRoundSuccessResult | FirstRoundErrorEnvelope:
        return self._service.submit(payload)
