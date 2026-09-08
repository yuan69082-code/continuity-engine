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
        continuity_core=None,
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
        self._continuity_core = continuity_core
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
        session_id: str | None = None,
    ) -> WakePerceptionThinkingActionResult:
        if self._continuity_core is not None and self._continuity_core.mind is not None:
            from continuity_engine.domain.dynamic_mind import MindValidationError
            from continuity_engine.domain.errors import StateNotFoundError
            core = self._continuity_core
            if self._awakening.get_cycle(cycle_id).subject_id != core.subject_id:
                raise MindValidationError('MIND_WAKE_CYCLE_SUBJECT_MISMATCH')
            if session_id is not None:
                try:
                    saved = self._awakening.get_session(core.subject_id, session_id)
                except StateNotFoundError:
                    pass
                else:
                    if saved.cycle_id != cycle_id or saved.wake_reason_detail != detail or saved.recovery_context is None:
                        raise MindValidationError('MIND_WAKE_IDENTITY_CONFLICT')
                    return self._continue(AwakeningResult(saved.recovery_context, saved), depth)
            awakening = self._awakening.wake_manual(cycle_id, detail=detail,
                session_id=session_id, preserve_recovery_context=True)
            return self._continue(awakening, depth)
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
        if self._continuity_core is not None and self._continuity_core.mind is not None:
            return self._continue_mind(awakening, depth)
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

    def _continue_mind(self, awakening, depth):
        """Reuse Wake/ThinkSession/Event identities; no new queue or request store.

        This native opportunity has no PlatformObservation and dispatches no
        external action. The normal C1 interaction entry still owns P08 dispatch.
        """
        from types import SimpleNamespace
        from continuity_engine.domain.errors import StateNotFoundError
        from continuity_engine.domain.dynamic_mind import MindValidationError
        from continuity_engine.domain.thinking import ThinkingExecutionResult
        from continuity_engine.domain.action import ActionType
        core = self._continuity_core
        wake = awakening.session
        if (wake.subject_id != core.subject_id or awakening.context.subject_state.subject_id != core.subject_id
                or not wake.completed_successfully or wake.recovery_context != awakening.context):
            raise MindValidationError('MIND_WAKE_ORIGINAL_BINDING_INVALID')
        think_id = str(uuid5(NAMESPACE_URL, 'p14-think|' + wake.session_id))
        event_id = str(uuid5(NAMESPACE_URL, 'p14-evolution|' + wake.session_id))
        context_id = str(uuid5(NAMESPACE_URL, 'p14-action|' + wake.session_id))
        try:
            session = self._thinking.get_session(core.subject_id, think_id)
        except StateNotFoundError:
            session = None
        if session is None:
            perception = self._perception.perceive(PerceptionContext.from_awakening(
                awakening, current_time=wake.wake_time),
                perception_id=str(uuid5(NAMESPACE_URL, 'p14-perception|' + wake.session_id)))
            if wake.decision is None or wake.decision.action is not WakeAction.THINK:
                return WakePerceptionThinkingActionResult(awakening, perception, None, None)
            if perception.external_facts:
                raise MindValidationError('MIND_NATIVE_OPPORTUNITY_HAS_EXTERNAL_OBSERVATION')
            perception = core.prepare(perception, SimpleNamespace(
                subject_id=core.subject_id, request_id='native:' + wake.session_id))
            core.before_thinking(perception)
            thinking = self._thinking.handle_perception(perception, depth=depth, think_id=think_id,
                result_id=str(uuid5(NAMESPACE_URL, 'p14-result|' + wake.session_id)),
                preserve_perception_snapshot=True, result_processor=core.mind.process)
            session = thinking.session
        else:
            perception = session.perception_snapshot
            if (perception is None or perception.wake_session_id != wake.session_id
                    or session.subject_id != core.subject_id or not session.completed_successfully
                    or session.result is None or session.provider_id != self._thinking.provider_id):
                raise MindValidationError('MIND_NATIVE_THINKING_BINDING_INVALID')
            thinking = ThinkingExecutionResult(perception, session)
        update = self._action_evolution.find_update_by_event_id(core.subject_id, event_id)
        if update is not None:
            intent_id = self._action._id('intent', session.result.result_id, ActionType.UPDATE_STATE.value, '0')
            decision_id = self._action._id('decision', context_id, intent_id, 'True')
            expected_metadata = {
                'action_session_id': self._action._id('session', context_id, think_id),
                'action_decision_id': decision_id, 'action_plan_id': self._action._id('plan', decision_id),
                'think_id': think_id, 'wake_session_id': wake.session_id,
                'perception_id': perception.perception_id, 'thinking_result_id': session.result.result_id,
            }
            if (update.event.metadata != expected_metadata or update.subject_id != core.subject_id
                    or update.event.source != 'action_engine' or update.event.event_type != 'approved_internal_action'
                    or update.before_revision != perception.source_revision
                    or update.after_revision != perception.source_revision + 1
                    or update.event.mutations != session.result.proposed_mutations
                    or update.event.reason != session.result.rationale_summary
                    or update.event.content != session.result.result_summary):
                raise MindValidationError('MIND_NATIVE_EVOLUTION_FACT_CONFLICT')
            if session.state_update_id not in {None, update.update_id}:
                raise MindValidationError('MIND_NATIVE_EVOLUTION_CHECKPOINT_CONFLICT')
            if session.state_update_id is None:
                self._thinking.record_evolution_result(thinking, update)
            return WakePerceptionThinkingActionResult(awakening, perception, thinking, None, update)
        if session.state_update_id is not None or session.state_written_back:
            raise MindValidationError('MIND_NATIVE_EVOLUTION_FACT_MISSING')
        core.before_thinking(perception)
        action = self._action.decide(ActionContext.from_results(
            subject_id=core.subject_id, subject_state_revision=perception.source_revision,
            thinking=thinking, perception=perception, current_time=self._clock(),
            available_permissions=self._available_permissions, resource_limits=self._resource_limits,
            permission_context=(self._permission_service.get_context(core.subject_id)
                                if self._permission_service is not None else None), context_id=context_id))
        # Current checks immediately precede the original atomic Evolution write.
        core.before_thinking(perception)
        update = self._action_evolution.evolve(ApprovedStateAction.from_execution(action), event_id=event_id)
        if update is not None:
            self._thinking.record_evolution_result(thinking, update)
        return WakePerceptionThinkingActionResult(awakening, perception, thinking, action, update)
