class ContinuityEngineError(Exception):
    """Base error for expected continuity engine failures."""


class StateNotFoundError(ContinuityEngineError):
    """Raised when a requested subject state does not exist."""


class StateAlreadyExistsError(ContinuityEngineError):
    """Raised when creating a subject state that already exists."""


class StateValidationError(ContinuityEngineError):
    """Raised when persisted or supplied state data is invalid."""


class StateEvolutionError(ContinuityEngineError):
    """Raised when an event requests an invalid state transition."""


class EventIdentityConflictError(StateEvolutionError):
    """Raised when an event identity is reused with a different canonical body."""


class EventReferenceError(StateEvolutionError):
    """Raised when an event relation targets an invalid event or subject."""


class TimelineValidationError(ContinuityEngineError):
    """Raised when a read-only timeline query or projection is invalid."""


class TimelineReferenceError(TimelineValidationError):
    """Raised when timeline history contains an invalid event reference."""


class ContextRoutingError(ContinuityEngineError):
    """Base error for P05 read-only context routing failures."""


class ContextRoutingValidationError(ContextRoutingError):
    """Raised when a route request, source result, or trace is invalid."""


class ContextRoutingSourceError(ContextRoutingError):
    """Raised when a bounded read-only source cannot provide verified candidates."""


class ContextCompositionError(ContinuityEngineError):
    """Base error for P06 context composition failures."""


class ContextCompositionValidationError(ContextCompositionError):
    """Raised when a composition input, snapshot, or trace is invalid."""


class ContextCompositionSourceError(ContextCompositionError):
    """Raised when an exact P05 material reference cannot be safely resolved."""


class ContradictionError(ContinuityEngineError):
    """Base error for P07 non-authoritative contradiction processing."""


class ContradictionValidationError(ContradictionError):
    """Raised when a claim, case, transition, or P06 input is invalid."""


class ContradictionIdentityConflictError(ContradictionError):
    """Raised when an immutable P07 identity is reused with different content."""


class ContradictionPersistenceError(ContradictionError):
    """Raised when a P07 audit document fails closed-world validation."""


class ContradictionNotFoundError(ContradictionError):
    """Raised when a requested contradiction case does not exist."""


class MemoryValidationError(ContinuityEngineError):
    """Raised when a memory request, candidate, or decision is invalid."""


class MemoryInfluenceError(ContinuityEngineError):
    """Raised when an invalid memory influence is recorded."""


class MemoryNotFoundError(MemoryValidationError):
    """Raised when a formal Memory or DerivedSummary identity does not exist."""


class MemoryIdentityConflictError(MemoryValidationError):
    """Raised when an immutable Memory identity is reused inconsistently."""


class MemoryEvidenceConflictError(MemoryValidationError):
    """Raised when P04 receives unresolved contradictory memory evidence."""


class MemoryPersistenceError(MemoryValidationError):
    """Raised when the formal Memory document fails integrity verification."""


class MemoryLineageError(MemoryValidationError):
    """Raised when correction, revocation, or deletion lineage is invalid."""


class AwakeningValidationError(ContinuityEngineError):
    """Raised when an awakening cycle, session, context, or decision is invalid."""


class WakeNotDueError(ContinuityEngineError):
    """Raised when a scheduled wake cycle is invoked before it is due."""


class WakeExecutionError(ContinuityEngineError):
    """Raised after a failed wake has been finalized and logged."""

    def __init__(self, session_id: str, message: str) -> None:
        super().__init__(message)
        self.session_id = session_id


class ThinkingValidationError(ContinuityEngineError):
    """Raised when a thinking context, result, session, or budget is invalid."""


class ThinkingExecutionError(ContinuityEngineError):
    """Raised after a failed ThinkSession has been finalized and logged."""

    def __init__(self, think_id: str, message: str) -> None:
        super().__init__(message)
        self.think_id = think_id


class PerceptionValidationError(ContinuityEngineError):
    """Raised when perception input or output violates the stage-six contract."""


class ActionValidationError(ContinuityEngineError):
    """Raised when an action context, assessment, decision, or plan is invalid."""


class PermissionContinuityError(ContinuityEngineError):
    """Base error for permission continuity state and history failures."""


class PermissionValidationError(PermissionContinuityError):
    """Raised when permission continuity data is invalid."""


class PermissionNotFoundError(PermissionContinuityError):
    """Raised when a permission state does not exist."""


class PermissionAlreadyExistsError(PermissionContinuityError):
    """Raised when a permission identity already exists."""


class LearningContinuityError(ContinuityEngineError):
    """Base error for personality learning state and history failures."""


class LearningValidationError(LearningContinuityError):
    """Raised when learning evidence or a proposed personality change is invalid."""


class LearningNotFoundError(LearningContinuityError):
    """Raised when a learning candidate or personality trait does not exist."""


class LearningAlreadyExistsError(LearningContinuityError):
    """Raised when a learning identity or audit record already exists."""


class ResourceManagementError(ContinuityEngineError):
    """Base error for token and compute resource management failures."""


class ResourceValidationError(ResourceManagementError):
    """Raised when resource state, requests, decisions, or usage are invalid."""


class ResourceNotFoundError(ResourceManagementError):
    """Raised when a subject has no configured resource state."""


class ResourceAlreadyExistsError(ResourceManagementError):
    """Raised when creating a resource state that already exists."""


class MachineContractError(ContinuityEngineError):
    """Base error for the versioned Vio/Continuity Engine machine contract."""


class MachineContractValidationError(MachineContractError):
    """Raised when an untrusted contract document fails strict validation."""


class MachineContractSchemaError(MachineContractError):
    """Raised when a schema is missing, invalid, or cannot resolve locally."""


class IntegrationPersistenceError(MachineContractError):
    """Raised when first-round binding or result persistence is invalid."""


class IntegrationLedgerConflictError(IntegrationPersistenceError):
    """Raised when an immutable result or projection conflicts with the ledger."""


class IntegrationRecordNotFoundError(IntegrationPersistenceError):
    """Raised when required first-round persisted data does not exist."""


class MachineContractCallError(MachineContractError):
    """Raised when a local caller cannot supply a safe contract correlation ID."""


class IntegrationExecutionError(MachineContractError):
    """Raised for an unexpected local integration execution fault."""

    def __init__(
        self,
        request_id: str,
        operation_id: str | None,
        stage: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.operation_id = operation_id
        self.stage = stage


class CapabilityError(ContinuityEngineError):
    """Base error for the independent capability pause/resume protocol."""


class CapabilityValidationError(CapabilityError):
    """Raised when a capability document violates its strict machine contract."""


class CapabilityConflictError(CapabilityError):
    """Raised when an immutable capability identity is reused inconsistently."""


class CapabilityNotFoundError(CapabilityError):
    """Raised when a capability result cannot be associated with a request."""


class ModelProviderError(ContinuityEngineError):
    """Base error for host-neutral model execution coordination."""


class ModelProviderValidationError(ModelProviderError):
    """Raised when a profile, execution fact, or usage fact is invalid."""


class ModelProviderConflictError(ModelProviderError):
    """Raised when an immutable model execution identity is reused inconsistently."""


class ModelProviderNotFoundError(ModelProviderError):
    """Raised when a model execution or profile cannot be found."""


# Backward-compatible E3 name.  The execution fault now belongs to the shared
# integration core rather than to the test adapter.
ContractTestExecutionError = IntegrationExecutionError
