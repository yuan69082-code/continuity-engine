from dataclasses import replace

from continuity_engine.domain.awakening import WakeContext
from continuity_engine.domain.errors import PerceptionValidationError
from continuity_engine.domain.events import Event
from continuity_engine.domain.memory import MemoryRetrievalResult
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.perception import (
    PerceivedPlatformFact,
    PerceptionContext,
    PerceptionResult,
)
from continuity_engine.domain.perception_rules import PerceptionPolicy


class PerceptionService:
    """Run perception without storage access or SubjectState mutation."""

    def __init__(self, policy: PerceptionPolicy | None = None) -> None:
        self._policy = policy or PerceptionPolicy()

    def perceive(
        self,
        context: PerceptionContext,
        *,
        perception_id: str | None = None,
    ) -> PerceptionResult:
        state_before = context.subject_state.to_dict()
        wake_state_before = context.wake_context.subject_state.to_dict()
        working_context = PerceptionContext(
            context_id=context.context_id,
            wake_session_id=context.wake_session_id,
            subject_state=SubjectState.from_dict(state_before),
            wake_context=WakeContext.from_dict(context.wake_context.to_dict()),
            memory_result=MemoryRetrievalResult.from_dict(
                context.memory_result.to_dict()
            ),
            recent_events=[Event.from_dict(item.to_dict()) for item in context.recent_events],
            current_time=context.current_time,
            external_facts=tuple(
                PerceivedPlatformFact.from_dict(item.to_dict())
                for item in context.external_facts
            ),
        )
        result = self._policy.perceive(working_context)
        if not isinstance(result, PerceptionResult):
            raise PerceptionValidationError(
                "PerceptionPolicy returned an invalid PerceptionResult"
            )
        if perception_id is not None:
            result = replace(result, perception_id=perception_id)
        if working_context.subject_state.to_dict() != state_before:
            raise PerceptionValidationError(
                "Perception Engine must not modify its SubjectState input"
            )
        if (
            working_context.wake_context.subject_state.to_dict()
            != wake_state_before
        ):
            raise PerceptionValidationError(
                "Perception Engine must not modify WakeContext SubjectState"
            )
        if context.subject_state.to_dict() != state_before or (
            context.wake_context.subject_state.to_dict() != wake_state_before
        ):
            raise PerceptionValidationError(
                "Perception Engine changed the caller-owned state snapshot"
            )
        if result.subject_id != context.subject_state.subject_id:
            raise PerceptionValidationError("PerceptionResult subject does not match input")
        if result.source_revision != context.subject_state.revision:
            raise PerceptionValidationError("PerceptionResult revision does not match input")
        return result
