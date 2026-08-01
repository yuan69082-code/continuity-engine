from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from continuity_engine.domain.awakening import AwakeCycle
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.models import utc_now
from continuity_engine.storage.base import (
    AwakeningRepository,
    SubjectBindingFixtureRepository,
)

from .integration_contract_hashing import calculate_binding_fixture_hash
from .subject_state_service import SubjectStateService


@dataclass(frozen=True, slots=True)
class FirstRoundContractFixture:
    subject_id: str
    initial_revision: int
    binding: SubjectBindingFixture
    binding_fixture_hash: str
    cycle_id: str


class FirstRoundContractBootstrap:
    """Create the one fresh, fixed E3 test fixture without legacy initialization."""

    SUBJECT_ID = "subject-001"
    CYCLE_ID = "first-round-manual-cycle-001"

    def __init__(
        self,
        subject_states: SubjectStateService,
        bindings: SubjectBindingFixtureRepository,
        awakening_repository: AwakeningRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._subject_states = subject_states
        self._bindings = bindings
        self._awakening_repository = awakening_repository
        self._clock = clock

    def prepare(self) -> FirstRoundContractFixture:
        state = self._subject_states.create(self.SUBJECT_ID)
        if state.revision != 0:
            raise RuntimeError("the first-round subject must start at revision 0")

        binding = SubjectBindingFixture.first_round()
        binding_hash = calculate_binding_fixture_hash(binding)
        self._bindings.save_fixed(binding, binding_hash)

        cycle = AwakeCycle.manual(
            subject_id=state.subject_id,
            created_at=self._clock(),
            cycle_id=self.CYCLE_ID,
        )
        self._awakening_repository.save_cycle(cycle)
        return FirstRoundContractFixture(
            subject_id=state.subject_id,
            initial_revision=state.revision,
            binding=binding,
            binding_fixture_hash=binding_hash,
            cycle_id=cycle.cycle_id,
        )
