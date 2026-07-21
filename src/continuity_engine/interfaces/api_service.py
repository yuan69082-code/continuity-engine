from __future__ import annotations

from collections.abc import Callable
from typing import Any

from continuity_engine.domain.awakening import AwakeMode
from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.memory import MemoryRetrievalRequest
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.services.user_interaction_service import UserInteractionService

from .models import (
    APIError,
    APIRequest,
    APIResponse,
    ActionPlanAPIRequest,
    ChatAPIRequest,
    ExternalOperation,
    MemoryAPIRequest,
    PerceptionAPIRequest,
    SubjectStateAPIRequest,
    ThinkingAPIRequest,
    WakeAPIRequest,
)
from .ports import ActionSessionProvider, PerceptionResultProvider
from .security import InterfaceAccessError, InterfaceAccessGuard


class InterfaceOperationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        current_revision: int | None = None,
        details=None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.current_revision = current_revision
        self.details = dict(details or {})


class APIService:
    """In-process API facade; transport frameworks bind to this class later."""

    def __init__(
        self,
        *,
        subject_states: SubjectStateService,
        memory: MemoryService,
        perceptions: PerceptionResultProvider,
        thinking: ThinkingService,
        actions: ActionSessionProvider,
        awakening: AwakeningService,
        access_guard: InterfaceAccessGuard,
        interactions: UserInteractionService | None = None,
        clock: Callable = utc_now,
    ) -> None:
        self._subject_states = subject_states
        self._memory = memory
        self._perceptions = perceptions
        self._thinking = thinking
        self._actions = actions
        self._awakening = awakening
        self._access_guard = access_guard
        self._interactions = interactions
        self._clock = clock

    def get_subject_state(self, request: SubjectStateAPIRequest) -> APIResponse:
        return self._invoke(
            request,
            ExternalOperation.GET_SUBJECT_STATE,
            lambda: self._subject_state_result(request.subject_id),
        )

    def submit_message(self, request: ChatAPIRequest) -> APIResponse:
        def operation():
            if self._interactions is None:
                raise InterfaceOperationError(
                    "INTERACTION_NOT_CONFIGURED",
                    "The user interaction pipeline is not configured.",
                )
            try:
                result = self._interactions.handle_message(
                    request_id=request.request_id,
                    subject_id=request.subject_id,
                    cycle_id=request.cycle_id,
                    message=request.message,
                    expected_revision=request.expected_revision,
                    user_id=request.user_id,
                    depth=request.depth,
                )
            except StateEvolutionError as exc:
                current = self._subject_states.load(request.subject_id)
                raise InterfaceOperationError(
                    "REVISION_CONFLICT",
                    str(exc),
                    current_revision=current.revision,
                    details={
                        "expected_revision": request.expected_revision,
                        "current_revision": current.revision,
                    },
                ) from exc
            return result.to_dict(), result.final_state.revision

        return self._invoke(request, ExternalOperation.SUBMIT_MESSAGE, operation)

    def query_memory(self, request: MemoryAPIRequest) -> APIResponse:
        def operation():
            state = self._subject_states.load(request.subject_id)
            memory_request = MemoryRetrievalRequest.create(
                request_id=request.request_id,
                subject_id=request.subject_id,
                query=request.query,
                requested_at=self._clock(),
                desired_scope=request.desired_scope,
                limit=request.limit,
                minimum_relevance=request.minimum_relevance,
                context={
                    **request.context,
                    "source": "continuity_api",
                    "subject_state_revision": state.revision,
                },
            )
            result = self._memory.retrieve(memory_request)
            return result.to_dict(), state.revision

        return self._invoke(request, ExternalOperation.QUERY_MEMORY, operation)

    def get_perception(self, request: PerceptionAPIRequest) -> APIResponse:
        def operation():
            state = self._subject_states.load(request.subject_id)
            perception = self._current_perception(request.subject_id, state.revision)
            return perception.to_dict(), state.revision

        return self._invoke(request, ExternalOperation.GET_PERCEPTION, operation)

    def request_thinking(self, request: ThinkingAPIRequest) -> APIResponse:
        def operation():
            state = self._subject_states.load(request.subject_id)
            perception = self._current_perception(request.subject_id, state.revision)
            execution = self._thinking.handle_perception(
                perception,
                depth=request.depth,
            )
            current = self._subject_states.load(request.subject_id)
            return {
                "think_session": execution.session.to_dict(),
                "thinking_result": (
                    execution.session.result.to_dict()
                    if execution.session.result is not None
                    else None
                ),
                "state_update": (
                    execution.state_update.to_dict()
                    if execution.state_update is not None
                    else None
                ),
            }, current.revision

        return self._invoke(request, ExternalOperation.REQUEST_THINKING, operation)

    def get_action_plan(self, request: ActionPlanAPIRequest) -> APIResponse:
        def operation():
            state = self._subject_states.load(request.subject_id)
            session = self._actions.get_latest_action_session(request.subject_id)
            if session is None:
                raise InterfaceOperationError(
                    "ACTION_PLAN_NOT_FOUND",
                    "No ActionDecision or ActionPlan exists for this subject.",
                    current_revision=state.revision,
                )
            if session.input_state_revision != state.revision:
                raise InterfaceOperationError(
                    "STALE_ACTION_PLAN",
                    "The latest ActionPlan was evaluated against an older state revision.",
                    current_revision=state.revision,
                    details={
                        "plan_revision": session.input_state_revision,
                        "current_revision": state.revision,
                    },
                )
            return {
                "action_session_id": session.action_session_id,
                "decision": session.final_decision.to_dict(),
                "plan": session.action_plan.to_dict(),
            }, state.revision

        return self._invoke(request, ExternalOperation.GET_ACTION_PLAN, operation)

    def trigger_manual_wake(self, request: WakeAPIRequest) -> APIResponse:
        def operation():
            state = self._subject_states.load(request.subject_id)
            cycle = self._awakening.get_cycle(request.cycle_id)
            if cycle.subject_id != request.subject_id:
                raise InterfaceOperationError(
                    "WAKE_SUBJECT_MISMATCH",
                    "The AwakeCycle does not belong to the requested subject.",
                    current_revision=state.revision,
                )
            if cycle.mode is not AwakeMode.MANUAL:
                raise InterfaceOperationError(
                    "WAKE_MODE_NOT_MANUAL",
                    "Only manual AwakeCycle values can be triggered through this endpoint.",
                    current_revision=state.revision,
                )
            awakening = self._awakening.wake_manual(
                request.cycle_id,
                detail=request.detail,
                session_id=request.request_id,
            )
            current = self._subject_states.load(request.subject_id)
            return {
                "wake_context": awakening.context.to_dict(),
                "wake_session": awakening.session.to_dict(),
            }, current.revision

        return self._invoke(request, ExternalOperation.TRIGGER_MANUAL_WAKE, operation)

    def _subject_state_result(self, subject_id: str):
        state = self._subject_states.load(subject_id)
        recent_updates = self._subject_states.get_update_history(subject_id)[-10:]
        return {
            "subject_state": state.to_dict(),
            "revision": state.revision,
            "summary": {
                "self_concept": state.identity.self_concept,
                "relationship_status": state.relationship.current_status,
                "current_focus": list(state.continuity.current_focus),
                "unfinished_items": list(state.continuity.unfinished_items),
                "last_interaction_at": state.to_dict()["temporal"][
                    "last_interaction_at"
                ],
            },
            "recent_events": [
                update.event.to_dict() for update in reversed(recent_updates)
            ],
        }, state.revision

    def _current_perception(
        self,
        subject_id: str,
        revision: int,
    ) -> PerceptionResult:
        perception = self._perceptions.get_current_perception(subject_id)
        if not isinstance(perception, PerceptionResult):
            raise InterfaceOperationError(
                "INVALID_PERCEPTION",
                "PerceptionResultProvider returned an invalid value.",
                current_revision=revision,
            )
        if perception.subject_id != subject_id:
            raise InterfaceOperationError(
                "PERCEPTION_SUBJECT_MISMATCH",
                "The current perception belongs to another subject.",
                current_revision=revision,
            )
        if perception.source_revision != revision:
            raise InterfaceOperationError(
                "STALE_PERCEPTION",
                "The current perception was built from an older state revision.",
                current_revision=revision,
                details={
                    "perception_revision": perception.source_revision,
                    "current_revision": revision,
                },
            )
        return perception

    def _invoke(
        self,
        request: APIRequest,
        operation: ExternalOperation,
        handler: Callable[[], tuple[Any, int]],
    ) -> APIResponse:
        try:
            self._access_guard.authorize(request, operation)
            result, revision = handler()
            return APIResponse(
                request_id=request.request_id,
                subject_id=request.subject_id,
                timestamp=self._clock(),
                current_revision=revision,
                result=result,
                error=None,
            )
        except InterfaceAccessError as exc:
            return self._error_response(
                request,
                exc.code,
                exc.message,
                details=exc.details,
            )
        except InterfaceOperationError as exc:
            return self._error_response(
                request,
                exc.code,
                exc.message,
                current_revision=exc.current_revision,
                details=exc.details,
            )
        except Exception as exc:
            return self._error_response(
                request,
                "OPERATION_FAILED",
                str(exc) or type(exc).__name__,
            )

    def _error_response(
        self,
        request: APIRequest,
        code: str,
        message: str,
        *,
        current_revision: int | None = None,
        details=None,
    ) -> APIResponse:
        return APIResponse(
            request_id=request.request_id,
            subject_id=request.subject_id,
            timestamp=self._clock(),
            current_revision=current_revision,
            result=None,
            error=APIError(code, message, dict(details or {})),
        )
