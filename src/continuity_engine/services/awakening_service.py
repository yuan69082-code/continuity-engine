from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from continuity_engine.domain.awakening import (
    AwakeCycle,
    AwakeMode,
    AwakeningResult,
    WakeAction,
    WakeContext,
    WakeDecision,
    WakeObservationLog,
    WakeReason,
    WakeSession,
    WakeTimeInfo,
    WakeTrigger,
)
from continuity_engine.domain.awakening_rules import WakeDecisionPolicy
from continuity_engine.domain.errors import (
    AwakeningValidationError,
    WakeExecutionError,
    WakeNotDueError,
)
from continuity_engine.domain.events import StateSection
from continuity_engine.domain.memory import MemoryRetrievalRequest
from continuity_engine.domain.models import SubjectState, utc_now
from continuity_engine.storage.base import AwakeningRepository

from .memory_service import MemoryService
from .subject_state_service import SubjectStateService


class AwakeningService:
    """Run the fourth-stage wake pipeline without executing autonomous actions."""

    def __init__(
        self,
        subject_states: SubjectStateService,
        memory: MemoryService,
        awakening_repository: AwakeningRepository,
        *,
        decision_policy: WakeDecisionPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
        recent_update_limit: int = 10,
        memory_limit: int = 5,
        minimum_memory_relevance: float = 0.5,
    ) -> None:
        if not isinstance(recent_update_limit, int) or recent_update_limit <= 0:
            raise AwakeningValidationError("recent_update_limit must be positive")
        if not isinstance(memory_limit, int) or memory_limit <= 0:
            raise AwakeningValidationError("memory_limit must be positive")
        if not 0 <= minimum_memory_relevance <= 1:
            raise AwakeningValidationError(
                "minimum_memory_relevance must be between 0 and 1"
            )
        self._subject_states = subject_states
        self._memory = memory
        self._repository = awakening_repository
        self._decision_policy = decision_policy or WakeDecisionPolicy()
        self._clock = clock
        self._recent_update_limit = recent_update_limit
        self._memory_limit = memory_limit
        self._minimum_memory_relevance = minimum_memory_relevance

    def create_manual_cycle(self, subject_id: str) -> AwakeCycle:
        cycle = AwakeCycle.manual(subject_id=subject_id, created_at=self._clock())
        self._repository.save_cycle(cycle)
        return cycle

    def create_scheduled_cycle(
        self,
        subject_id: str,
        *,
        interval_seconds: int,
        first_wake_at: datetime,
    ) -> AwakeCycle:
        cycle = AwakeCycle.scheduled(
            subject_id=subject_id,
            created_at=self._clock(),
            interval_seconds=interval_seconds,
            first_wake_at=first_wake_at,
        )
        self._repository.save_cycle(cycle)
        return cycle

    def list_due_cycles(self, now: datetime | None = None) -> list[AwakeCycle]:
        return self._repository.list_due_cycles(now or self._clock())

    def get_cycle(self, cycle_id: str) -> AwakeCycle:
        return self._repository.load_cycle(cycle_id)

    def wake_manual(
        self,
        cycle_id: str,
        *,
        detail: str,
        session_id: str | None = None,
        context_id: str | None = None,
        preserve_recovery_context: bool = False,
    ) -> AwakeningResult:
        cycle = self._repository.load_cycle(cycle_id)
        if cycle.mode is not AwakeMode.MANUAL:
            raise AwakeningValidationError("wake_manual requires a manual AwakeCycle")
        if not cycle.enabled:
            raise AwakeningValidationError("awake cycle is disabled")
        now = self._clock()
        return self._run(
            cycle,
            WakeTrigger.manual(triggered_at=now, detail=detail),
            session_id=session_id,
            context_id=context_id,
            preserve_recovery_context=preserve_recovery_context,
        )

    def wake_scheduled(
        self,
        cycle_id: str,
        *,
        detail: str = "The scheduled wake time was reached.",
        session_id: str | None = None,
    ) -> AwakeningResult:
        cycle = self._repository.load_cycle(cycle_id)
        if cycle.mode is not AwakeMode.SCHEDULED:
            raise AwakeningValidationError("wake_scheduled requires a scheduled AwakeCycle")
        now = self._clock()
        if not cycle.is_due(now):
            raise WakeNotDueError(f"awake cycle is not due: {cycle_id}")
        return self._run(
            cycle,
            WakeTrigger.scheduled(triggered_at=now, detail=detail),
            session_id=session_id,
        )

    def wake_for_event(
        self,
        cycle_id: str,
        *,
        source_event_id: str,
        detail: str,
        session_id: str | None = None,
    ) -> AwakeningResult:
        cycle = self._repository.load_cycle(cycle_id)
        if not cycle.enabled:
            raise AwakeningValidationError("awake cycle is disabled")
        now = self._clock()
        return self._run(
            cycle,
            WakeTrigger.event(
                triggered_at=now,
                detail=detail,
                source_event_id=source_event_id,
            ),
            session_id=session_id,
        )

    def get_sessions(self, subject_id: str, limit: int | None = None) -> list[WakeSession]:
        return self._repository.list_sessions(subject_id, limit)

    def get_session(self, subject_id: str, session_id: str) -> WakeSession:
        return self._repository.load_session(subject_id, session_id)

    def recover_completed(
        self,
        session: WakeSession,
        *,
        context_id: str,
        legacy_context_time: datetime | None = None,
    ) -> AwakeningResult:
        """Restore one completed wake without creating or rewriting a session."""
        if not session.completed_successfully or session.decision is None:
            raise AwakeningValidationError(
                "only a successfully completed WakeSession can be recovered"
            )
        if session.recovery_context is not None:
            context = WakeContext.from_dict(session.recovery_context.to_dict())
            if context.context_id != context_id:
                raise AwakeningValidationError(
                    "persisted WakeContext identity does not match recovery identity"
                )
            return AwakeningResult(context=context, session=session)
        if legacy_context_time is None:
            raise AwakeningValidationError(
                "legacy WakeSession lacks the context required for safe recovery"
            )

        state = self._subject_states.load(session.subject_id)
        if state.revision != session.subject_revision:
            raise AwakeningValidationError(
                "legacy WakeSession revision no longer matches SubjectState"
            )
        history = self._subject_states.get_update_history(session.subject_id)
        recent_updates = history[-self._recent_update_limit :]
        recent_events = [update.event for update in recent_updates]
        if (
            [update.update_id for update in recent_updates]
            != session.observation.update_ids
            or [event.event_id for event in recent_events]
            != session.observation.event_ids
            or session.observation.context_id != context_id
            or session.observation.memory_request_id is None
        ):
            raise AwakeningValidationError(
                "legacy WakeSession observation cannot be reconstructed uniquely"
            )
        memory_request = self._memory_request(
            state,
            recent_event_ids=session.observation.event_ids,
            requested_at=legacy_context_time,
            request_id=session.observation.memory_request_id,
        )
        memory_result = self._memory.retrieve(memory_request)
        if (
            [
                decision.candidate.memory_id
                for decision in memory_result.decisions
            ]
            != session.observation.viewed_memory_ids
            or [
                candidate.memory_id
                for candidate in memory_result.selected_memories
            ]
            != session.observation.selected_memory_ids
        ):
            raise AwakeningValidationError(
                "legacy WakeSession memory observation cannot be reconstructed uniquely"
            )
        context = WakeContext(
            context_id=context_id,
            subject_state=state,
            recent_events=recent_events,
            recent_updates=recent_updates,
            memory_result=memory_result,
            time_info=WakeTimeInfo(
                current_time=legacy_context_time,
                last_interaction_at=state.temporal.last_interaction_at,
                seconds_since_last_interaction=(
                    state.temporal.seconds_since_last_interaction(legacy_context_time)
                ),
            ),
            created_at=legacy_context_time,
        )
        recovered_decision = self._decision_policy.decide(context)
        if (
            recovered_decision.action is not session.decision.action
            or recovered_decision.reason != session.decision.reason
            or recovered_decision.evidence != session.decision.evidence
        ):
            raise AwakeningValidationError(
                "legacy WakeSession decision conflicts with reconstructed context"
            )
        return AwakeningResult(context=context, session=session)

    def _run(
        self,
        cycle: AwakeCycle,
        trigger: WakeTrigger,
        *,
        session_id: str | None = None,
        context_id: str | None = None,
        preserve_recovery_context: bool = False,
    ) -> AwakeningResult:
        session = WakeSession.start(cycle, trigger, session_id=session_id)
        self._repository.save_session(session)
        state: SubjectState | None = None
        observation = WakeObservationLog()

        try:
            # 1. WakeSession already exists and the wake reason is logged.
            # 2. Read current SubjectState.
            state = self._subject_states.load(cycle.subject_id)
            observation.state_revision = state.revision

            # 3. Read recent state evolution and its source events.
            history = self._subject_states.get_update_history(cycle.subject_id)
            recent_updates = history[-self._recent_update_limit :]
            recent_events = [update.event for update in recent_updates]
            observation.update_ids = [update.update_id for update in recent_updates]
            observation.event_ids = [event.event_id for event in recent_events]

            # 4. Ask the current Memory Manager interface for relevant memories.
            context_time = self._clock()
            memory_request = self._memory_request(
                state,
                recent_event_ids=observation.event_ids,
                requested_at=context_time,
            )
            memory_result = self._memory.retrieve(memory_request)
            observation.memory_request_id = memory_request.request_id
            observation.viewed_memory_ids = [
                decision.candidate.memory_id for decision in memory_result.decisions
            ]
            observation.selected_memory_ids = [
                candidate.memory_id for candidate in memory_result.selected_memories
            ]

            # 5. Build one unified WakeContext.
            context = WakeContext(
                context_id=context_id or str(uuid4()),
                subject_state=state,
                recent_events=recent_events,
                recent_updates=recent_updates,
                memory_result=memory_result,
                time_info=WakeTimeInfo(
                    current_time=context_time,
                    last_interaction_at=state.temporal.last_interaction_at,
                    seconds_since_last_interaction=(
                        state.temporal.seconds_since_last_interaction(context_time)
                    ),
                ),
                created_at=context_time,
            )

            # 6. Return a decision object only. No action is executed here.
            decision = self._decision_policy.decide(context)

            # 7. Finalize and persist the WakeSession audit log.
            session.complete(
                context=context,
                decision=decision,
                completed_at=self._clock(),
                retain_recovery_context=preserve_recovery_context,
            )
            cycle.mark_woken(trigger.triggered_at)
            self._repository.save_cycle(cycle)
            self._repository.save_session(session)
            return AwakeningResult(context=context, session=session)
        except Exception as exc:
            failed_at = self._clock()
            failure_decision = WakeDecision(
                action=WakeAction.SLEEP,
                reason="The wake pipeline failed, so no autonomous action may proceed.",
                decided_at=failed_at,
                evidence=[f"error:{type(exc).__name__}"],
            )
            session.fail(
                decision=failure_decision,
                completed_at=failed_at,
                error=str(exc) or type(exc).__name__,
                subject_revision=state.revision if state is not None else None,
                observation=observation,
            )
            cycle.mark_woken(trigger.triggered_at)
            self._repository.save_cycle(cycle)
            self._repository.save_session(session)
            raise WakeExecutionError(
                session.session_id,
                f"wake session failed and was logged: {session.session_id}",
            ) from exc

    def _memory_request(
        self,
        state: SubjectState,
        *,
        recent_event_ids: list[str],
        requested_at: datetime,
        request_id: str | None = None,
    ) -> MemoryRetrievalRequest:
        focus = state.continuity.current_focus
        unfinished = state.continuity.unfinished_items
        query_parts = ["Retrieve memories relevant to the subject's current continuity."]
        if focus:
            query_parts.append(f"Current focus: {'; '.join(focus)}.")
        if unfinished:
            query_parts.append(f"Unfinished items: {'; '.join(unfinished)}.")
        if recent_event_ids:
            query_parts.append("Recent state evolution is available for comparison.")

        return MemoryRetrievalRequest.create(
            subject_id=state.subject_id,
            query=" ".join(query_parts),
            requested_at=requested_at,
            desired_scope=[
                StateSection.CONTINUITY,
                StateSection.RELATIONSHIP,
                StateSection.INTENTIONS,
            ],
            limit=self._memory_limit,
            minimum_relevance=self._minimum_memory_relevance,
            context={
                "subject_revision": state.revision,
                "current_focus": list(focus),
                "unfinished_items": list(unfinished),
                "relationship_status": state.relationship.current_status,
                "recent_event_ids": list(recent_event_ids),
            },
            request_id=request_id,
        )
