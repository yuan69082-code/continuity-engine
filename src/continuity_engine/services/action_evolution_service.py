from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from continuity_engine.domain.action import ApprovedStateAction
from continuity_engine.domain.events import Event, StateSection, StateUpdateRecord
from continuity_engine.domain.models import utc_now

from .subject_state_service import SubjectStateService


class ActionEvolutionService:
    """Apply only an Action-Gate-approved state authorization through Evolution."""

    def __init__(
        self,
        subject_states: SubjectStateService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._subject_states = subject_states
        self._clock = clock

    def evolve(
        self,
        approved: ApprovedStateAction | None,
        *,
        event_id: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> StateUpdateRecord | None:
        if approved is None:
            return None
        scopes: list[StateSection] = []
        for mutation in approved.mutations:
            section = StateSection(mutation.field_path.split(".", 1)[0])
            if section not in scopes:
                scopes.append(section)
        event = Event.create(
            event_id=event_id,
            occurred_at=occurred_at or self._clock(),
            source="action_engine",
            event_type="approved_internal_action",
            content=approved.result_summary,
            impact_scope=scopes,
            mutations=approved.mutations,
            reason=approved.rationale_summary,
            metadata={
                "action_session_id": approved.action_session_id,
                "action_decision_id": approved.decision_id,
                "action_plan_id": approved.plan_id,
                "think_id": approved.think_session_id,
                "wake_session_id": approved.wake_session_id,
                "perception_id": approved.perception_id,
                "thinking_result_id": approved.thinking_result_id,
                **dict(metadata or {}),
            },
        )
        return self._subject_states.apply_event(
            approved.subject_id,
            event,
            expected_revision=approved.expected_revision,
        ).update

    def find_update_by_event_id(
        self,
        subject_id: str,
        event_id: str,
    ) -> StateUpdateRecord | None:
        for update in self._subject_states.get_update_history(subject_id):
            if update.event.event_id == event_id:
                return update
        return None
