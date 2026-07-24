from __future__ import annotations

from datetime import datetime
from typing import Protocol

from continuity_engine.domain.awakening import AwakeCycle, WakeSession
from continuity_engine.domain.action import ActionSession
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.learning import LearningEvent, LearningRecord, PersonalityTrait
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.permissions import PermissionChangeRecord, PermissionState
from continuity_engine.domain.resources import (
    ResourceDecision,
    ResourceState,
    TokenUsageRecord,
)
from continuity_engine.domain.thinking import ThinkSession


class SubjectStateRepository(Protocol):
    def exists(self, subject_id: str) -> bool: ...

    def load(self, subject_id: str) -> SubjectState: ...

    def save(self, state: SubjectState) -> None: ...


class StateUpdateRecordRepository(Protocol):
    def save_transition(self, state: SubjectState, update: StateUpdateRecord) -> None: ...

    def list_update_records(self, subject_id: str) -> list[StateUpdateRecord]: ...


class ContinuityRepository(SubjectStateRepository, StateUpdateRecordRepository, Protocol):
    """Storage contract required by the event-driven continuity service."""


class AwakeningRepository(Protocol):
    def save_cycle(self, cycle: AwakeCycle) -> None: ...

    def load_cycle(self, cycle_id: str) -> AwakeCycle: ...

    def list_due_cycles(self, now: datetime) -> list[AwakeCycle]: ...

    def save_session(self, session: WakeSession) -> None: ...

    def load_session(self, subject_id: str, session_id: str) -> WakeSession: ...

    def list_sessions(self, subject_id: str, limit: int | None = None) -> list[WakeSession]: ...


class ThinkingRepository(Protocol):
    def save_think_session(self, session: ThinkSession) -> None: ...

    def load_think_session(self, subject_id: str, think_id: str) -> ThinkSession: ...

    def list_think_sessions(
        self,
        subject_id: str,
        limit: int | None = None,
    ) -> list[ThinkSession]: ...


class ActionRepository(Protocol):
    def save_action_session(self, session: ActionSession) -> None: ...

    def load_action_session(
        self,
        subject_id: str,
        action_session_id: str,
    ) -> ActionSession: ...

    def list_action_sessions(
        self,
        subject_id: str,
        limit: int | None = None,
    ) -> list[ActionSession]: ...


class PermissionRepository(Protocol):
    def save(
        self,
        permission: PermissionState,
        change: PermissionChangeRecord,
    ) -> None: ...

    def load(self, subject_id: str, permission_id: str) -> PermissionState: ...

    def list(self, subject_id: str) -> list[PermissionState]: ...

    def history(
        self,
        subject_id: str,
        permission_id: str | None = None,
    ) -> list[PermissionChangeRecord]: ...


class LearningRepository(Protocol):
    def save_change(
        self,
        subject_id: str,
        learning_event: LearningEvent,
        record: LearningRecord,
        trait: PersonalityTrait | None = None,
    ) -> None: ...

    def load_learning_event(
        self,
        subject_id: str,
        learning_id: str,
    ) -> LearningEvent: ...

    def list_learning_events(self, subject_id: str) -> list[LearningEvent]: ...

    def load_trait(self, subject_id: str, trait_id: str) -> PersonalityTrait: ...

    def list_traits(
        self,
        subject_id: str,
        include_inactive: bool = True,
    ) -> list[PersonalityTrait]: ...

    def history(
        self,
        subject_id: str,
        learning_id: str | None = None,
    ) -> list[LearningRecord]: ...


class ResourceRepository(Protocol):
    def create(self, state: ResourceState) -> None: ...

    def load(self, subject_id: str) -> ResourceState: ...

    def save_state(
        self,
        state: ResourceState,
        *,
        expected_revision: int,
    ) -> None: ...

    def save_allocation(
        self,
        state: ResourceState,
        usage: TokenUsageRecord,
        decision: ResourceDecision,
        *,
        expected_revision: int,
    ) -> None: ...

    def save_decision(self, decision: ResourceDecision) -> None: ...

    def reconcile_usage(
        self,
        state: ResourceState,
        usage: TokenUsageRecord,
        *,
        expected_revision: int,
    ) -> None: ...

    def list_usage(self, subject_id: str) -> list[TokenUsageRecord]: ...

    def list_decisions(self, subject_id: str) -> list[ResourceDecision]: ...
