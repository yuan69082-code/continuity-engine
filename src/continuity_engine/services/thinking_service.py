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
    ThinkSessionStatus,
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
        result_processor=None,
        result_validator=None,
    ) -> ThinkingExecutionResult:
        if not isinstance(perception, PerceptionResult):
            raise ThinkingValidationError("thinking requires a PerceptionResult")
        self._subject_states.require_active(perception.subject_id)
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
        material_error = None
        try:
            result = self._provider.think(perception, budget)
            if result_validator is not None:
                try:
                    result_validator(perception, result)
                except Exception as exc:
                    material_error = exc
                    raise
            if result_id is not None:
                result = replace(result, result_id=result_id)
            self._validate_provider_result(result, budget)
            if result_processor is not None:
                result = result_processor(perception, result)
                if result_validator is not None:
                    try:
                        result_validator(perception, result)
                    except Exception as exc:
                        material_error = exc
                        raise
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
            if material_error is exc:
                # The optional boundary returns a safe, static rejection. Keep
                # it visible to the caller, while persisting only the failure
                # summary above, never the rejected result.
                raise
            raise ThinkingExecutionError(
                session.think_id,
                f"ThinkSession failed and was logged: {session.think_id}",
            ) from exc

    def begin_capability_wait(
        self,
        perception: PerceptionResult,
        *,
        capability_request_id: str,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
        think_id: str,
        preserve_perception_snapshot: bool = True,
        started_at: datetime | None = None,
    ) -> ThinkSession:
        """Persist one stable ThinkSession without invoking the provider."""

        if not isinstance(perception, PerceptionResult):
            raise ThinkingValidationError("thinking requires a PerceptionResult")
        self._subject_states.require_active(perception.subject_id)
        created_at = started_at or self._clock()
        reason = (
            "Perception requires an external model capability before Thinking can "
            f"complete: {perception.summary}"
        )
        budget_request = TokenBudgetRequest(
            subject_id=perception.subject_id,
            wake_session_id=perception.wake_session_id,
            depth=depth,
            requested_at=created_at,
            session_id=think_id,
            model_name=self._provider.provider_id,
            reason=reason,
        )
        budget = self._token_budgets.allocate(budget_request)
        if not isinstance(budget, TokenBudget):
            raise ThinkingValidationError(
                "TokenBudgetManager returned an invalid budget"
            )
        if budget.session_tokens <= 0:
            raise ThinkingValidationError(
                "capability Thinking requires a positive allocated session budget"
            )
        session = ThinkSession.start(
            wake_session_id=perception.wake_session_id,
            subject_id=perception.subject_id,
            provider_id=self._provider.provider_id,
            started_at=created_at,
            thinking_reason=reason,
            token_budget=budget,
            perception=perception,
            think_id=think_id,
            retain_perception_snapshot=preserve_perception_snapshot,
        )
        session.wait_for_capability(capability_request_id)
        self._repository.save_think_session(session)
        return session

    def complete_capability_wait(
        self,
        perception: PerceptionResult,
        *,
        think_id: str,
        result: ThinkingResult,
        ended_at: datetime,
        result_processor=None,
        result_validator=None,
    ) -> ThinkingExecutionResult:
        """Complete the original waiting session from a validated execution fact."""

        session = self.get_session(perception.subject_id, think_id)
        if result_validator is not None:
            result_validator(perception, result)
            if session.result is not None:
                result_validator(perception, session.result)
        if session.status is ThinkSessionStatus.COMPLETED:
            if session.result != result:
                raise ThinkingValidationError(
                    "completed capability ThinkingResult cannot be replaced"
                )
            return ThinkingExecutionResult(perception=perception, session=session)
        if session.status is ThinkSessionStatus.WAITING_CAPABILITY:
            session.resume_from_capability()
            self._repository.save_think_session(session)
        elif (
            session.status is not ThinkSessionStatus.RUNNING
            or session.capability_request_id is None
        ):
            raise ThinkingValidationError(
                "capability result requires the original capability ThinkSession"
            )
        if session.perception_snapshot != perception:
            raise ThinkingValidationError(
                "capability result perception does not match ThinkSession"
            )
        self._validate_provider_result(result, session.token_budget)
        if result_processor is not None:
            result = result_processor(perception, result)
            if result_validator is not None:
                result_validator(perception, result)
        session.complete(
            ended_at=ended_at,
            result=result,
            state_written_back=False,
        )
        self._repository.save_think_session(session)
        return ThinkingExecutionResult(
            perception=perception,
            session=session,
            state_update=None,
        )

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
        if any(m.field_path == 'intentions.dynamic_mind' for m in result.proposed_mutations):
            raise ThinkingValidationError('Provider cannot supply P14 internal state directly')
        if any(m.field_path in {'temporal.subject_lifecycle',
                               'identity.self_narrative','relationship.objects'} for m in result.proposed_mutations):
            raise ThinkingValidationError('Provider cannot supply internal subject state directly')

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
