from collections.abc import Callable
from datetime import datetime, timezone

from continuity_engine.domain.errors import (
    EventIdentityConflictError,
    EventReferenceError,
    StateAlreadyExistsError,
    StateEvolutionError,
)
from continuity_engine.domain.events import (
    Event,
    EventClassification,
    EventTimeBasis,
    StateSection,
    StateUpdateRecord,
)
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

    def require_active(self, subject_id: str, environment: str | None = None) -> SubjectState:
        from continuity_engine.domain.subject_lifecycle import LifecycleError, SubjectLifecycle, lifecycle_status
        state = self.load(subject_id)
        if lifecycle_status(state) != 'ACTIVE':
            raise LifecycleError('SUBJECT_NOT_ACTIVE')
        if state.temporal.subject_lifecycle is not None and environment is not None:
            if SubjectLifecycle.from_dict(state.temporal.subject_lifecycle).environment != environment:
                raise LifecycleError('SUBJECT_ENVIRONMENT_MISMATCH')
        return state

    def save(self, state: SubjectState) -> SubjectState:
        """Persist direct edits retained for first-stage compatibility.

        New state changes should normally use apply_event so their causes and
        before/after differences are recorded.
        """
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        prior = self.require_active(state.subject_id) if self._repository.exists(state.subject_id) else None
        if any(getattr(owner,field) != (getattr(old,field) if old is not None else None)
               for owner,old,field in [(state.temporal,prior.temporal if prior else None,'subject_lifecycle'),
                                      (state.identity,prior.identity if prior else None,'self_narrative'),
                                      (state.relationship,prior.relationship if prior else None,'objects')]):
            raise LifecycleError('SUBJECT_INTERNAL_STATE_REQUIRES_EVOLUTION')
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
        return self._apply_event(subject_id, event, expected_revision=expected_revision)

    def _apply_event(self, subject_id, event, *, expected_revision=None, lifecycle_authorization=None):
        state = self.load(subject_id)
        history = self._repository.list_update_records(subject_id)
        existing = next(
            (record for record in history if record.event.event_id == event.event_id),
            None,
        )
        if existing is not None:
            if existing.event.canonical_dict() != event.canonical_dict():
                raise EventIdentityConflictError(
                    f"event identity conflicts with immutable history: {event.event_id}"
                )
            return StateEvolutionResult(
                state=state,
                update=existing,
                idempotent_replay=True,
            )

        from continuity_engine.domain.subject_lifecycle import LifecycleError
        lifecycle_write = any(m.field_path == 'temporal.subject_lifecycle' for m in event.mutations)
        if lifecycle_authorization is not None:
            lifecycle_authorization(state)
        else:
            if lifecycle_write:
                raise LifecycleError('SUBJECT_MANAGEMENT_AUTHORIZATION_REQUIRED')
            self.require_active(subject_id)

        applied_at = self._clock()
        if applied_at.tzinfo is None or applied_at.utcoffset() is None:
            raise StateEvolutionError("applied_at must include a timezone")
        applied_at = applied_at.astimezone(timezone.utc)
        if (
            event.time_basis is EventTimeBasis.EXPLICIT
            and event.recorded_at > applied_at
        ):
            raise StateEvolutionError(
                "an explicit recorded_at cannot be later than the authoritative applied_at"
            )

        known_event_ids = {record.event.event_id for record in history}
        for reference in event.references:
            if reference.target_subject_id != subject_id:
                raise EventReferenceError(
                    "event references cannot cross subject boundaries"
                )
            if reference.target_event_id not in known_event_ids:
                raise EventReferenceError(
                    f"referenced event does not exist: {reference.target_event_id}"
                )
        non_mutating_classifications = {
            EventClassification.FACT,
            EventClassification.OBSERVATION,
            EventClassification.INTENTION,
            EventClassification.CORRECTION,
            EventClassification.REVOCATION,
        }
        if event.classification in non_mutating_classifications and event.mutations:
            raise EventReferenceError(
                "fact, observation, intention, correction, and revocation events cannot "
                "mutate current SubjectState; append the history without mutations and "
                "use an Action-Gate-approved state_change event"
            )
        if expected_revision is not None and state.revision != expected_revision:
            raise StateEvolutionError(
                f"stale SubjectState revision: expected {expected_revision}, "
                f"found {state.revision}"
            )
        result = self._evolver.evolve(state, event, applied_at=applied_at)
        self._repository.save_transition(result.state, result.update)
        # Another local writer may have persisted the identical event first.
        # Return that authoritative update identity, never an unsaved UUID.
        persisted = next(
            record for record in self._repository.list_update_records(subject_id)
            if record.event.event_id == event.event_id
        )
        if persisted.update_id != result.update.update_id:
            return StateEvolutionResult(
                state=self.load(subject_id), update=persisted, idempotent_replay=True
            )
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
