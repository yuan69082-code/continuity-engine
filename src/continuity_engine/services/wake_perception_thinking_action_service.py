from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from continuity_engine.domain.action import (
    ActionContext,
    ApprovedStateAction,
    ResourceLimits,
    WakePerceptionThinkingActionResult,
)
from continuity_engine.domain.awakening import AwakeningResult, WakeAction
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.perception import PerceptionContext
from continuity_engine.domain.thinking import ThinkingDepth

from .action_service import ActionService
from .action_evolution_service import ActionEvolutionService
from .awakening_service import AwakeningService
from .perception_service import PerceptionService
from .permission_service import PermissionService
from .subject_state_service import SubjectStateService
from .thinking_service import ThinkingService


class WakePerceptionThinkingActionService:
    """Wake -> Perception -> Thinking -> Action -> optional Evolution."""

    def __init__(
        self,
        awakening: AwakeningService,
        perception: PerceptionService,
        thinking: ThinkingService,
        action: ActionService,
        subject_states: SubjectStateService,
        *,
        available_permissions: Iterable[str] = (),
        resource_limits: ResourceLimits | None = None,
        permission_service: PermissionService | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._awakening = awakening
        self._perception = perception
        self._thinking = thinking
        self._action = action
        self._subject_states = subject_states
        self._available_permissions = list(available_permissions)
        self._resource_limits = resource_limits or ResourceLimits()
        self._permission_service = permission_service
        self._clock = clock
        self._action_evolution = ActionEvolutionService(
            subject_states,
            clock=clock,
        )

    def wake_manual(
        self,
        cycle_id: str,
        *,
        detail: str,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingActionResult:
        awakening = self._awakening.wake_manual(cycle_id, detail=detail)
        return self._continue(awakening, depth)

    def wake_scheduled(
        self,
        cycle_id: str,
        *,
        detail: str = "The scheduled wake time was reached.",
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingActionResult:
        awakening = self._awakening.wake_scheduled(cycle_id, detail=detail)
        return self._continue(awakening, depth)

    def wake_for_event(
        self,
        cycle_id: str,
        *,
        source_event_id: str,
        detail: str,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingActionResult:
        awakening = self._awakening.wake_for_event(
            cycle_id,
            source_event_id=source_event_id,
            detail=detail,
        )
        return self._continue(awakening, depth)

    def _continue(
        self,
        awakening: AwakeningResult,
        depth: ThinkingDepth,
    ) -> WakePerceptionThinkingActionResult:
        perception_context = PerceptionContext.from_awakening(
            awakening,
            current_time=self._clock(),
        )
        perception = self._perception.perceive(perception_context)
        decision = awakening.session.decision
        thinking = None
        action = None
        state_update: StateUpdateRecord | None = None

        if decision is not None and decision.action is WakeAction.THINK:
            thinking = self._thinking.handle_perception(perception, depth=depth)
            current_state = self._subject_states.load(perception.subject_id)
            action_context = ActionContext.from_results(
                subject_id=perception.subject_id,
                subject_state_revision=current_state.revision,
                thinking=thinking,
                perception=perception,
                current_time=self._clock(),
                available_permissions=self._available_permissions,
                resource_limits=self._resource_limits,
                permission_context=(
                    self._permission_service.get_context(perception.subject_id)
                    if self._permission_service is not None
                    else None
                ),
                context_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        "|".join(
                            (
                                "action-context",
                                perception.perception_id,
                                thinking.session.think_id,
                                str(current_state.revision),
                            )
                        ),
                    )
                ),
            )
            action = self._action.decide(action_context)
            state_update = self._evolve_approved_state_action(action)
            if state_update is not None:
                self._thinking.record_evolution_result(thinking, state_update)

        return WakePerceptionThinkingActionResult(
            awakening=awakening,
            perception=perception,
            thinking=thinking,
            action=action,
            state_update=state_update,
        )

    def _evolve_approved_state_action(self, action) -> StateUpdateRecord | None:
        return self._action_evolution.evolve(
            ApprovedStateAction.from_execution(action)
        )
