from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from continuity_engine.domain.action import WakePerceptionThinkingActionResult
from continuity_engine.domain.errors import StateEvolutionError, StateValidationError
from continuity_engine.domain.events import Event, JsonValue, StateSection, StateUpdateRecord
from continuity_engine.domain.models import SubjectState, utc_now
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.thinking import ThinkingDepth

from .awakening_service import AwakeningService
from .subject_state_service import SubjectStateService
from .wake_perception_thinking_action_service import (
    WakePerceptionThinkingActionService,
)


class InteractionReplyComposer(Protocol):
    def compose(
        self,
        *,
        user_message: str,
        flow: WakePerceptionThinkingActionResult,
    ) -> str: ...


class DeterministicReplyComposer:
    """Produce a displayable reply without an AI or external platform call."""

    def compose(
        self,
        *,
        user_message: str,
        flow: WakePerceptionThinkingActionResult,
    ) -> str:
        thinking = flow.thinking_result
        if thinking is not None:
            summary = thinking.result_summary
        else:
            summary = flow.perception.summary
        action = flow.action_decision
        action_label = (
            action.selected_action.action_type.value
            if action is not None
            else "NO_ACTION"
        )
        return f"已完成本次连续性处理。{summary}（行动决定：{action_label}）"


@dataclass(slots=True)
class UserInteractionResult:
    request_id: str
    subject_id: str
    user_id: str | None
    user_event: Event
    interaction_update: StateUpdateRecord
    flow: WakePerceptionThinkingActionResult
    final_state: SubjectState
    reply: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "user_id": self.user_id,
            "reply": {
                "role": "assistant",
                "content": self.reply,
            },
            "user_event": self.user_event.to_dict(),
            "interaction_update": self.interaction_update.to_dict(),
            "wake": {
                "context": self.flow.awakening.context.to_dict(),
                "session": self.flow.awakening.session.to_dict(),
            },
            "perception": self.flow.perception.to_dict(),
            "thinking": (
                {
                    "session": self.flow.thinking.session.to_dict(),
                    "result": (
                        self.flow.thinking.session.result.to_dict()
                        if self.flow.thinking.session.result is not None
                        else None
                    ),
                }
                if self.flow.thinking is not None
                else None
            ),
            "action": (
                {
                    "decision": self.flow.action.decision.to_dict(),
                    "plan": self.flow.action.plan.to_dict(),
                }
                if self.flow.action is not None
                else None
            ),
            "state_update": (
                self.flow.state_update.to_dict()
                if self.flow.state_update is not None
                else None
            ),
            "final_revision": self.final_state.revision,
        }


class UserInteractionService:
    """Convert one frontend message into the existing continuity pipeline."""

    def __init__(
        self,
        subject_states: SubjectStateService,
        awakening: AwakeningService,
        flow: WakePerceptionThinkingActionService,
        *,
        reply_composer: InteractionReplyComposer | None = None,
        clock: Callable = utc_now,
    ) -> None:
        self._subject_states = subject_states
        self._awakening = awakening
        self._flow = flow
        self._reply_composer = reply_composer or DeterministicReplyComposer()
        self._clock = clock
        self._latest_perceptions: dict[str, PerceptionResult] = {}

    def handle_message(
        self,
        *,
        request_id: str,
        subject_id: str,
        cycle_id: str,
        message: str,
        expected_revision: int,
        user_id: str | None = None,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> UserInteractionResult:
        for value, field_name in (
            (request_id, "request_id"),
            (subject_id, "subject_id"),
            (cycle_id, "cycle_id"),
            (message, "message"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise StateValidationError(f"{field_name} must be a non-empty string")
        if len(message) > 10_000:
            raise StateValidationError("message must not exceed 10000 characters")
        if user_id is not None and (not isinstance(user_id, str) or not user_id.strip()):
            raise StateValidationError("user_id must be non-empty when supplied")
        if not isinstance(expected_revision, int) or expected_revision < 0:
            raise StateValidationError("expected_revision must be non-negative")

        cycle = self._awakening.get_cycle(cycle_id)
        if cycle.subject_id != subject_id:
            raise StateValidationError("AwakeCycle does not belong to the subject")
        if not cycle.enabled:
            raise StateValidationError("AwakeCycle is disabled")
        current = self._subject_states.load(subject_id)
        if current.revision != expected_revision:
            raise StateEvolutionError(
                f"stale SubjectState revision: expected {expected_revision}, "
                f"found {current.revision}"
            )

        event = Event.create(
            event_id=f"frontend-interaction:{request_id}",
            occurred_at=self._clock(),
            source="frontend",
            event_type="interaction",
            content=message.strip(),
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Record an explicit user interaction before rebuilding context.",
            metadata={
                "external_request_id": request_id,
                "user_id": user_id,
            },
        )
        evolution = self._subject_states.apply_event(
            subject_id,
            event,
            expected_revision=expected_revision,
        )
        flow = self._flow.wake_for_event(
            cycle_id,
            source_event_id=event.event_id,
            detail="A frontend user message created a continuity event.",
            depth=depth,
        )
        self._latest_perceptions[subject_id] = PerceptionResult.from_dict(
            flow.perception.to_dict()
        )
        final_state = self._subject_states.load(subject_id)
        reply = self._reply_composer.compose(
            user_message=message,
            flow=flow,
        )
        if not isinstance(reply, str) or not reply.strip():
            raise StateValidationError("InteractionReplyComposer returned an empty reply")
        return UserInteractionResult(
            request_id=request_id,
            subject_id=subject_id,
            user_id=user_id,
            user_event=event,
            interaction_update=evolution.update,
            flow=flow,
            final_state=final_state,
            reply=reply,
        )

    def get_current_perception(self, subject_id: str) -> PerceptionResult:
        perception = self._latest_perceptions.get(subject_id)
        if perception is None:
            raise StateValidationError(
                "no perception has been produced for this subject in the current process"
            )
        return PerceptionResult.from_dict(perception.to_dict())
