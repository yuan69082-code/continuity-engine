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


class MemoryValidationError(ContinuityEngineError):
    """Raised when a memory request, candidate, or decision is invalid."""


class MemoryInfluenceError(ContinuityEngineError):
    """Raised when an invalid memory influence is recorded."""


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
