from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from uuid import uuid4

from continuity_engine.domain.errors import MachineContractValidationError
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import (
    calculate_projection_content_hash,
    calculate_state_hash,
)
from continuity_engine.domain.integration_results import (
    FIRST_ROUND_BINDING_VERSION,
    FirstRoundSubjectResponse,
    FirstRoundSuccessResult,
    SubjectStateProjection,
    SubjectStateProjectionSnapshot,
    format_contract_datetime,
)
from continuity_engine.domain.models import SubjectState

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _operation_id() -> str:
    return f"operation-{uuid4()}"


def _response_id() -> str:
    return f"response-{uuid4()}"


class FirstRoundResultFactory:
    """Build immutable first-round results without running the engine workflow."""

    def __init__(
        self,
        *,
        clock: Clock = _utc_now,
        operation_id_factory: IdFactory = _operation_id,
        response_id_factory: IdFactory = _response_id,
    ) -> None:
        self._clock = clock
        self._operation_id_factory = operation_id_factory
        self._response_id_factory = response_id_factory

    def create_completed_result(
        self,
        *,
        request_id: str,
        request_hash: str,
        binding: SubjectBindingFixture,
        response_content: str,
        subject_state: SubjectState,
        previous_revision: int,
        engine_update_id: str | None,
        consumed_observation_ids: Sequence[str],
        operation_id: str | None = None,
        response_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> FirstRoundSuccessResult:
        if binding != SubjectBindingFixture.first_round():
            raise MachineContractValidationError(
                "E2 result construction accepts only the fixed first-round binding"
            )
        if binding.binding_version != FIRST_ROUND_BINDING_VERSION:
            raise MachineContractValidationError(
                "the first-round binding version must be 1"
            )
        if subject_state.subject_id != binding.subject_id:
            raise MachineContractValidationError(
                "SubjectState subject_id must match the fixed binding"
            )

        state_hash = calculate_state_hash(subject_state)
        snapshot = SubjectStateProjectionSnapshot(
            subject_id=subject_state.subject_id,
            revision=subject_state.revision,
            state_hash=state_hash,
        )
        projection = SubjectStateProjection(
            subject_id=subject_state.subject_id,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            previous_revision=previous_revision,
            current_revision=subject_state.revision,
            changed=subject_state.revision != previous_revision,
            engine_update_id=engine_update_id,
            snapshot=snapshot,
            content_hash=calculate_projection_content_hash(snapshot),
        )
        return FirstRoundSuccessResult(
            request_id=request_id,
            request_hash=request_hash,
            operation_id=operation_id or self._operation_id_factory(),
            subject_id=subject_state.subject_id,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            response=FirstRoundSubjectResponse(
                response_id=response_id or self._response_id_factory(),
                content=response_content,
            ),
            state_projection=projection,
            consumed_observation_ids=tuple(consumed_observation_ids),
            completed_at=format_contract_datetime(completed_at or self._clock()),
        )
