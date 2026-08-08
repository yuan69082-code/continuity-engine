from __future__ import annotations

from typing import Protocol

from continuity_engine.domain.action import ActionExecutionResult
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.domain.thinking import ThinkingExecutionResult


class SubjectBindingRepository(Protocol):
    """Persistence boundary for the single active runtime SubjectBinding."""

    def initialize(self, binding: SubjectBinding) -> None: ...

    def load_active(self) -> SubjectBinding: ...


class IntegrationReplyComposer(Protocol):
    """Subject-expression seam used after deterministic Thinking and Action."""

    def compose(
        self,
        thinking: ThinkingExecutionResult,
        action: ActionExecutionResult,
    ) -> str: ...
