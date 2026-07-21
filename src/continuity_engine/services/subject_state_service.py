from collections.abc import Callable
from datetime import datetime

from continuity_engine.domain.errors import StateAlreadyExistsError, StateEvolutionError
from continuity_engine.domain.events import Event, StateSection, StateUpdateRecord
from continuity_engine.domain.evolution import StateEvolutionResult, SubjectStateEvolver
from continuity_engine.domain.models import SubjectState, utc_now
from continuity_engine.storage.base import ContinuityRepository


class SubjectStateService:
    """Application service for the minimum SubjectState lifecycle."""

    def __init__(
        self,
        repository: ContinuityRepository,
        clock: Callable[[], datetime] = utc_now,
        evolver: SubjectStateEvolver | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._evolver = evolver or SubjectStateEvolver()

    def create(self, subject_id: str) -> SubjectState:
        if self._repository.exists(subject_id):
            raise StateAlreadyExistsError(f"subject state already exists: {subject_id}")
        state = SubjectState.create(subject_id, now=self._clock())
        self._repository.save(state)
        return state

    def load(self, subject_id: str) -> SubjectState:
        return self._repository.load(subject_id)

    def save(self, state: SubjectState) -> SubjectState:
        """Persist direct edits retained for first-stage compatibility.

        New state changes should normally use apply_event so their causes and
        before/after differences are recorded.
        """
        state.mark_updated(self._clock())
        self._repository.save(state)
        return state

    def apply_event(
        self,
        subject_id: str,
        event: Event,
        *,
        expected_revision: int | None = None,
    ) -> StateEvolutionResult:
        state = self.load(subject_id)
        if expected_revision is not None and state.revision != expected_revision:
            raise StateEvolutionError(
                f"stale SubjectState revision: expected {expected_revision}, "
                f"found {state.revision}"
            )
        result = self._evolver.evolve(state, event, applied_at=self._clock())
        self._repository.save_transition(result.state, result.update)
        return result

    def get_update_history(self, subject_id: str) -> list[StateUpdateRecord]:
        return self._repository.list_update_records(subject_id)

    def record_interaction(self, subject_id: str) -> SubjectState:
        interaction_time = self._clock()
        event = Event.create(
            occurred_at=interaction_time,
            source="continuity_engine.service",
            event_type="interaction",
            content="An interaction with the subject was recorded.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Keep the subject's temporal continuity current.",
        )
        return self.apply_event(subject_id, event).state
