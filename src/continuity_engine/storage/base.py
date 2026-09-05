from __future__ import annotations

from datetime import datetime
from typing import Protocol

from continuity_engine.domain.awakening import AwakeCycle, WakeSession
from continuity_engine.domain.action import ActionSession
from continuity_engine.domain.capability import (
    CapabilityAttempt,
    CapabilityRequest,
    CapabilityResult,
)
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    FirstRoundSuccessResult,
    IntegrationOperationRecord,
    LedgerLookupResult,
)
from continuity_engine.domain.learning import LearningEvent, LearningRecord, PersonalityTrait
from continuity_engine.domain.memory import (
    DerivedSummary,
    DerivedSummaryStatus,
    MemoryConsolidationOperation,
    MemoryKind,
    MemoryLineageRecord,
    MemoryRecord,
    MemoryStatus,
    MemoryTemperature,
    MemoryVisibility,
)
from continuity_engine.domain.contradiction import (
    AuditAction, ContradictionCase, ResolutionEvidence, VerifiedResolutionEvidence,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.permissions import PermissionChangeRecord, PermissionState
from continuity_engine.domain.resources import (
    ResourceDecision,
    ResourceState,
    TokenUsageRecord,
)
from continuity_engine.domain.thinking import ThinkSession
from continuity_engine.domain.scheduling import SchedulerQueue


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


class MemoryRepository(Protocol):
    """Single P04 authority for formal Memory, summary views, and lineage."""

    def save_memory(self, memory: MemoryRecord) -> bool: ...

    def load_memory(self, subject_id: str, memory_id: str) -> MemoryRecord: ...

    def list_memories(
        self,
        subject_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[MemoryRecord]: ...

    def query_memories(
        self,
        subject_id: str,
        *,
        environment: str,
        status: MemoryStatus,
        visibility: MemoryVisibility,
        excluded_temperatures: tuple[MemoryTemperature, ...],
        query_terms: tuple[str, ...],
        preferred_kinds: tuple[MemoryKind, ...],
        limit: int,
    ) -> list[MemoryRecord]: ...

    def memory_history(self, subject_id: str, memory_id: str) -> list[MemoryRecord]: ...

    def find_by_consolidation_id(
        self,
        subject_id: str,
        consolidation_id: str,
    ) -> MemoryRecord | None: ...

    def load_consolidation_operation(
        self,
        subject_id: str,
        consolidation_id: str,
    ) -> MemoryConsolidationOperation | None: ...

    def save_consolidation(
        self,
        memory: MemoryRecord,
        operation: MemoryConsolidationOperation,
    ) -> bool: ...

    def save_summary(self, summary: DerivedSummary) -> bool: ...

    def load_summary(self, subject_id: str, summary_id: str) -> DerivedSummary: ...

    def list_summaries(
        self,
        subject_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[DerivedSummary]: ...

    def query_summaries(
        self,
        subject_id: str,
        *,
        environment: str,
        status: DerivedSummaryStatus,
        query_terms: tuple[str, ...],
        preferred_scope_terms: tuple[str, ...],
        limit: int,
    ) -> list[DerivedSummary]: ...

    def summary_history(
        self,
        subject_id: str,
        summary_id: str,
    ) -> list[DerivedSummary]: ...

    def list_lineage(self, subject_id: str) -> list[MemoryLineageRecord]: ...

    def apply_propagation(
        self,
        memory: MemoryRecord,
        lineage: MemoryLineageRecord,
        summaries: list[DerivedSummary],
    ) -> bool: ...


class ResolutionEvidenceVerifier(Protocol):
    """Trusted, independently bound P07 evidence lookup, not caller attestation."""

    def verify(
        self, case: ContradictionCase, evidence: ResolutionEvidence, *, action: AuditAction
    ) -> VerifiedResolutionEvidence: ...


class ContradictionRepository(Protocol):
    """Non-authoritative P07 audit boundary; never a fact or state authority."""

    def save_detected(self, case: ContradictionCase) -> ContradictionCase: ...

    def append_transition(self, case: ContradictionCase) -> ContradictionCase: ...

    def load_case(self, subject_id: str, case_id: str) -> ContradictionCase: ...

    def case_history(self, subject_id: str, case_id: str) -> list[ContradictionCase]: ...

    def list_cases(self, subject_id: str) -> list[ContradictionCase]: ...


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


class SchedulerRepository(Protocol):
    """Single P11 scheduling authority; it owns no subject or action state."""

    def load_queue(self) -> SchedulerQueue: ...

    def save_queue(self, queue: SchedulerQueue, *, expected_revision: int) -> None: ...


class SubjectBindingFixtureRepository(Protocol):
    """Persistence boundary for the single fixed first-round binding fixture."""

    def save_fixed(
        self,
        fixture: SubjectBindingFixture,
        binding_fixture_hash: str,
    ) -> None: ...

    def load_fixed(self) -> tuple[SubjectBindingFixture, str]: ...


class IntegrationResultLedger(Protocol):
    """Completed-result ledger plus recoverable internal operation journal."""

    def lookup(self, request_id: str, request_hash: str) -> LedgerLookupResult: ...

    def save_completed(self, result: FirstRoundSuccessResult) -> None: ...

    def load_operation(self, request_id: str) -> IntegrationOperationRecord | None: ...

    def save_operation(self, operation: IntegrationOperationRecord) -> None: ...

    def load_completed(self, request_id: str) -> FirstRoundSuccessResult | None: ...

    def list_completed(self) -> list[FirstRoundSuccessResult]: ...

    def list_operations(self) -> list[IntegrationOperationRecord]: ...

    def initialize_empty(self) -> None: ...

    def validate_initialized(self) -> None: ...

    def initialize_capabilities(self) -> None: ...

    def validate_capability_initialized(self) -> None: ...

    def save_capability_request(self, request: CapabilityRequest) -> None: ...

    def load_capability_request(
        self,
        capability_request_id: str,
    ) -> CapabilityRequest | None: ...

    def find_capability_request_by_operation(
        self,
        operation_id: str,
    ) -> CapabilityRequest | None: ...

    def save_capability_result(
        self,
        result: CapabilityResult,
        *,
        received_at: str,
    ) -> CapabilityAttempt: ...

    def list_capability_attempts(
        self,
        capability_request_id: str,
    ) -> list[CapabilityAttempt]: ...
