from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from continuity_engine.domain.errors import (
    ThinkingExecutionError,
    ThinkingValidationError,
)
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.thinking import (
    ThinkSession,
    ThinkingDepth,
    ThinkingExecutionResult,
    ThinkingResult,
    TokenBudget,
    TokenBudgetRequest,
)
from continuity_engine.storage.base import ThinkingRepository

from .subject_state_service import SubjectStateService
from .thinking_ports import ThinkingProvider, TokenBudgetManager


class ThinkingService:
    """Run a model-agnostic ThinkSession from PerceptionResult only."""

    def __init__(
        self,
        provider: ThinkingProvider,
        token_budgets: TokenBudgetManager,
        subject_states: SubjectStateService,
        repository: ThinkingRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._provider = provider
        self._token_budgets = token_budgets
        self._subject_states = subject_states
        self._repository = repository
        self._clock = clock

    @property
    def subject_states(self) -> SubjectStateService:
        """Expose the shared Evolution facade for application-level orchestration."""
        return self._subject_states

    @property
    def clock(self) -> Callable[[], datetime]:
        return self._clock

    @property
    def provider_id(self) -> str:
        return self._provider.provider_id

    def handle_perception(
        self,
        perception: PerceptionResult,
        *,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
        think_id: str | None = None,
        result_id: str | None = None,
        preserve_perception_snapshot: bool = False,
    ) -> ThinkingExecutionResult:
        if not isinstance(perception, PerceptionResult):
            raise ThinkingValidationError("thinking requires a PerceptionResult")
        thinking_reason = (
            "Perception identified information requiring internal thought: "
            f"{perception.summary}"
        )

        created_at = self._clock()
        think_id = think_id or str(uuid4())
        budget_request = TokenBudgetRequest(
            subject_id=perception.subject_id,
            wake_session_id=perception.wake_session_id,
            depth=depth,
            requested_at=created_at,
            session_id=think_id,
            model_name=self._provider.provider_id,
            reason=thinking_reason,
        )

        try:
            budget = self._token_budgets.allocate(budget_request)
            if not isinstance(budget, TokenBudget):
                raise ThinkingValidationError(
                    "TokenBudgetManager returned an invalid budget"
                )
            if self._depth_rank(budget.depth) > self._depth_rank(depth):
                raise ThinkingValidationError(
                    "allocated TokenBudget depth cannot exceed the requested depth"
                )
        except Exception as exc:
            fallback_budget = TokenBudget(0, 0, 0, depth)
            session = ThinkSession.start(
                wake_session_id=perception.wake_session_id,
                subject_id=perception.subject_id,
                provider_id=self._provider.provider_id,
                started_at=created_at,
                thinking_reason=thinking_reason,
                token_budget=fallback_budget,
                perception=perception,
                think_id=think_id,
                retain_perception_snapshot=preserve_perception_snapshot,
            )
            self._repository.save_think_session(session)
            failure_result = self._failure_result(
                provider_id=self._provider.provider_id,
                budget=fallback_budget,
                summary=(
                    "Thinking could not start because no usable token budget was allocated."
                ),
                result_id=result_id,
            )
            session.fail(
                ended_at=self._clock(),
                result=failure_result,
                error=str(exc) or type(exc).__name__,
            )
            self._repository.save_think_session(session)
            raise ThinkingExecutionError(
                session.think_id,
                f"ThinkSession failed and was logged: {session.think_id}",
            ) from exc

        session = ThinkSession.start(
            wake_session_id=perception.wake_session_id,
            subject_id=perception.subject_id,
            provider_id=self._provider.provider_id,
            started_at=created_at,
            thinking_reason=thinking_reason,
            token_budget=budget,
            perception=perception,
            think_id=think_id,
            retain_perception_snapshot=preserve_perception_snapshot,
        )
        self._repository.save_think_session(session)
        if budget.session_tokens == 0:
            deferred_result = ThinkingResult.create(
                result_id=result_id,
                provider_id=self._provider.provider_id,
                result_summary="Thinking was deferred by the resource policy.",
                rationale_summary=(
                    "The remaining token or compute budget could not safely support "
                    "even LOW-depth thinking, so the session will wait."
                ),
                generated_new_thought=False,
                update_subject_state=False,
                request_more_memory=False,
                should_wait=True,
                suggest_future_user_contact=False,
                token_budget=budget,
            )
            session.complete(
                ended_at=self._clock(),
                result=deferred_result,
                state_written_back=False,
            )
            self._repository.save_think_session(session)
            return ThinkingExecutionResult(
                perception=perception,
                session=session,
                state_update=None,
            )
        try:
            result = self._provider.think(perception, budget)
            if result_id is not None:
                result = replace(result, result_id=result_id)
            self._validate_provider_result(result, budget)
            session.complete(
                ended_at=self._clock(),
                result=result,
                state_written_back=False,
            )
            self._repository.save_think_session(session)
            return ThinkingExecutionResult(
                perception=perception,
                session=session,
                state_update=None,
            )
        except Exception as exc:
            failure_result = self._failure_result(
                provider_id=self._provider.provider_id,
                budget=budget,
                summary="Thinking did not produce a usable completed result.",
                result_id=result_id,
            )
            session.fail(
                ended_at=self._clock(),
                result=failure_result,
                error=str(exc) or type(exc).__name__,
                state_written_back=False,
            )
            self._repository.save_think_session(session)
            raise ThinkingExecutionError(
                session.think_id,
                f"ThinkSession failed and was logged: {session.think_id}",
            ) from exc

    def get_sessions(self, subject_id: str, limit: int | None = None) -> list[ThinkSession]:
        return self._repository.list_think_sessions(subject_id, limit)

    def get_session(self, subject_id: str, think_id: str) -> ThinkSession:
        return self._repository.load_think_session(subject_id, think_id)

    def record_evolution_result(
        self,
        execution: ThinkingExecutionResult,
        update: StateUpdateRecord,
    ) -> None:
        """Attach a state update only after an approved Action produced it."""
        session = execution.session
        if session.result is None or not session.result.update_subject_state:
            raise ThinkingValidationError(
                "state evolution cannot be attached without a state-update thought"
            )
        action_session_id = update.event.metadata.get("action_session_id")
        if not isinstance(action_session_id, str) or not action_session_id.strip():
            raise ThinkingValidationError(
                "state evolution must reference an approved ActionSession"
            )
        if update.subject_id != session.subject_id:
            raise ThinkingValidationError("state update subject does not match ThinkSession")
        if update.before_revision != session.observation.state_revision:
            raise ThinkingValidationError("state update revision does not match perception")
        session.state_written_back = bool(update.changes)
        session.state_event_id = update.event.event_id
        session.state_update_id = update.update_id
        execution.state_update = update
        self._repository.save_think_session(session)

    def _validate_provider_result(
        self,
        result: ThinkingResult,
        budget: TokenBudget,
    ) -> None:
        if not isinstance(result, ThinkingResult):
            raise ThinkingValidationError("ThinkingProvider returned an invalid result")
        if result.provider_id != self._provider.provider_id:
            raise ThinkingValidationError(
                "ThinkingResult provider_id does not match provider"
            )
        if result.token_budget != budget:
            raise ThinkingValidationError(
                "ThinkingResult must preserve the allocated TokenBudget"
            )

    @staticmethod
    def _depth_rank(depth: ThinkingDepth) -> int:
        return {
            ThinkingDepth.LOW: 0,
            ThinkingDepth.NORMAL: 1,
            ThinkingDepth.DEEP: 2,
        }[depth]

    @staticmethod
    def _failure_result(
        *,
        provider_id: str,
        budget: TokenBudget,
        summary: str,
        result_id: str | None = None,
    ) -> ThinkingResult:
        return ThinkingResult.create(
            result_id=result_id,
            provider_id=provider_id,
            result_summary=summary,
            rationale_summary=(
                "The framework recorded a failure summary; no chain-of-thought was stored."
            ),
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=True,
            suggest_future_user_contact=False,
            token_budget=budget,
        )
