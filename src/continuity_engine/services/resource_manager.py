from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from continuity_engine.domain.errors import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.resource_policy import ResourcePolicy
from continuity_engine.domain.resources import (
    ResourceAllocation,
    ResourceDecision,
    ResourceRequest,
    ResourceSessionType,
    ResourceState,
    RuntimeMode,
    TokenUsageRecord,
)
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    TokenBudget,
    TokenBudgetRequest,
)
from continuity_engine.storage.base import ResourceRepository


class ResourceManager:
    """Allocate estimated resources and preserve every usage decision."""

    def __init__(
        self,
        repository: ResourceRepository,
        *,
        policy: ResourcePolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._policy = policy or ResourcePolicy()
        self._clock = clock
        self._session_subjects: dict[str, str] = {}

    def create_resource_state(
        self,
        subject_id: str,
        *,
        token_budget: int,
        compute_budget: int,
        current_mode: RuntimeMode = RuntimeMode.LOW_FREQUENCY,
        resource_id: str | None = None,
    ) -> ResourceState:
        try:
            self._repository.load(subject_id)
        except ResourceNotFoundError:
            pass
        else:
            raise ResourceAlreadyExistsError(
                f"resource state already exists: {subject_id}"
            )
        state = ResourceState.create(
            subject_id=subject_id,
            token_budget=token_budget,
            compute_budget=compute_budget,
            current_mode=current_mode,
            updated_at=self._clock(),
            resource_id=resource_id,
        )
        self._repository.create(state)
        return state

    def get_resource_state(self, subject_id: str) -> ResourceState:
        return self._repository.load(subject_id)

    def set_runtime_mode(
        self,
        subject_id: str,
        mode: RuntimeMode,
        *,
        expected_revision: int | None = None,
    ) -> ResourceState:
        current = self._repository.load(subject_id)
        if expected_revision is not None and current.revision != expected_revision:
            raise ResourceValidationError(
                "resource state does not match expected_revision"
            )
        try:
            next_mode = mode if isinstance(mode, RuntimeMode) else RuntimeMode(mode)
        except ValueError as exc:
            raise ResourceValidationError("unsupported runtime mode") from exc
        if current.current_mode is next_mode:
            return current
        updated = ResourceState.from_dict(current.to_dict())
        updated.current_mode = next_mode
        updated.updated_at = self._clock()
        updated.revision += 1
        updated.__post_init__()
        self._repository.save_state(
            updated,
            expected_revision=current.revision,
        )
        return updated

    def preview(self, request: ResourceRequest) -> ResourceDecision:
        state = self._repository.load(request.subject_id)
        return self._policy.evaluate(state, request, decided_at=self._clock())

    def request_resources(self, request: ResourceRequest) -> ResourceAllocation:
        state = self._repository.load(request.subject_id)
        decision = self._policy.evaluate(state, request, decided_at=self._clock())
        if not decision.allowed:
            self._repository.save_decision(decision)
            return ResourceAllocation(
                state=state,
                request=request,
                decision=decision,
                usage=None,
            )

        usage = TokenUsageRecord(
            usage_id=str(uuid4()),
            subject_id=request.subject_id,
            session_id=request.session_id,
            session_type=request.session_type,
            estimated_tokens=decision.allocated_tokens,
            actual_tokens=None,
            model_name=request.model_name,
            reason=request.reason,
            created_at=self._clock(),
            estimated_compute=decision.allocated_compute,
        )
        updated = ResourceState.from_dict(state.to_dict())
        updated.token_used += usage.estimated_tokens
        updated.token_remaining = max(0, updated.token_budget - updated.token_used)
        updated.compute_used += usage.estimated_compute
        updated.compute_remaining = max(
            0, updated.compute_budget - updated.compute_used
        )
        updated.updated_at = self._clock()
        updated.revision += 1
        updated.__post_init__()
        self._repository.save_allocation(
            updated,
            usage,
            decision,
            expected_revision=state.revision,
        )
        self._session_subjects[request.session_id] = request.subject_id
        return ResourceAllocation(
            state=updated,
            request=request,
            decision=decision,
            usage=usage,
        )

    def request_thinking(
        self,
        subject_id: str,
        session_id: str,
        *,
        depth: ThinkingDepth,
        model_name: str,
        reason: str,
    ) -> ResourceAllocation:
        try:
            requested_depth = (
                depth if isinstance(depth, ThinkingDepth) else ThinkingDepth(depth)
            )
        except ValueError as exc:
            raise ResourceValidationError("unsupported thinking depth") from exc
        cost = self._policy.DEPTH_COSTS[requested_depth]
        return self.request_resources(
            ResourceRequest.create(
                subject_id=subject_id,
                session_id=session_id,
                session_type=ResourceSessionType.THINKING,
                estimated_tokens=cost.tokens,
                estimated_compute=cost.compute,
                model_name=model_name,
                reason=reason,
                requested_at=self._clock(),
                requested_depth=requested_depth,
            )
        )

    def request_learning(
        self,
        subject_id: str,
        session_id: str,
        *,
        reason: str,
        estimated_tokens: int = 128,
        estimated_compute: int = 2,
    ) -> ResourceAllocation:
        return self.request_resources(
            ResourceRequest.create(
                subject_id=subject_id,
                session_id=session_id,
                session_type=ResourceSessionType.LEARNING,
                estimated_tokens=estimated_tokens,
                estimated_compute=estimated_compute,
                model_name="not-applicable",
                reason=reason,
                requested_at=self._clock(),
            )
        )

    def request_wake(
        self,
        subject_id: str,
        session_id: str,
        *,
        reason: str,
        estimated_tokens: int = 64,
        estimated_compute: int = 1,
    ) -> ResourceAllocation:
        return self.request_resources(
            ResourceRequest.create(
                subject_id=subject_id,
                session_id=session_id,
                session_type=ResourceSessionType.OTHER,
                estimated_tokens=estimated_tokens,
                estimated_compute=estimated_compute,
                model_name="not-applicable",
                reason=reason,
                requested_at=self._clock(),
            )
        )

    def request_memory(
        self,
        subject_id: str,
        session_id: str,
        *,
        reason: str,
        estimated_tokens: int = 128,
        estimated_compute: int = 1,
    ) -> ResourceAllocation:
        return self.request_resources(
            ResourceRequest.create(
                subject_id=subject_id,
                session_id=session_id,
                session_type=ResourceSessionType.MEMORY,
                estimated_tokens=estimated_tokens,
                estimated_compute=estimated_compute,
                model_name="not-applicable",
                reason=reason,
                requested_at=self._clock(),
            )
        )

    def allocate(self, request: TokenBudgetRequest) -> TokenBudget:
        """Implement the existing Thinking TokenBudgetManager port."""
        session_id = request.session_id or request.wake_session_id
        allocation = self.request_thinking(
            request.subject_id,
            session_id,
            depth=request.depth,
            model_name=request.model_name,
            reason=request.reason,
        )
        decision = allocation.decision
        depth = decision.approved_depth or ThinkingDepth.LOW
        if not decision.allowed:
            return TokenBudget(
                maximum_tokens=allocation.state.token_budget,
                remaining_tokens=allocation.state.token_remaining,
                session_tokens=0,
                depth=depth,
            )
        remaining_before_allocation = (
            allocation.state.token_remaining + decision.allocated_tokens
        )
        return TokenBudget(
            maximum_tokens=allocation.state.token_budget,
            remaining_tokens=min(
                allocation.state.token_budget, remaining_before_allocation
            ),
            session_tokens=decision.allocated_tokens,
            depth=depth,
        )

    def record_usage(self, session_id: str, actual_tokens: int) -> TokenUsageRecord:
        subject_id = self._session_subjects.get(session_id)
        if subject_id is None:
            raise ResourceNotFoundError(
                "resource session is unknown; use record_actual_usage with subject_id"
            )
        return self.record_actual_usage(subject_id, session_id, actual_tokens)

    def record_actual_usage(
        self,
        subject_id: str,
        session_id: str,
        actual_tokens: int,
    ) -> TokenUsageRecord:
        if isinstance(actual_tokens, bool) or not isinstance(actual_tokens, int) or actual_tokens < 0:
            raise ResourceValidationError("actual_tokens must be non-negative")
        current = self._repository.load(subject_id)
        matches = [
            item
            for item in self._repository.list_usage(subject_id)
            if item.session_id == session_id
        ]
        if len(matches) != 1:
            raise ResourceNotFoundError(
                f"exactly one usage record is required for session: {session_id}"
            )
        previous = matches[0]
        if previous.actual_tokens is not None:
            raise ResourceValidationError("actual token usage was already recorded")
        updated_usage = TokenUsageRecord.from_dict(previous.to_dict())
        updated_usage.actual_tokens = actual_tokens
        updated_usage.__post_init__()

        updated_state = ResourceState.from_dict(current.to_dict())
        updated_state.token_used = max(
            0,
            current.token_used - previous.estimated_tokens + actual_tokens,
        )
        updated_state.token_remaining = max(
            0, updated_state.token_budget - updated_state.token_used
        )
        updated_state.updated_at = self._clock()
        updated_state.revision += 1
        updated_state.__post_init__()
        self._repository.reconcile_usage(
            updated_state,
            updated_usage,
            expected_revision=current.revision,
        )
        return updated_usage

    def get_usage_history(self, subject_id: str) -> list[TokenUsageRecord]:
        return self._repository.list_usage(subject_id)

    def get_decision_history(self, subject_id: str) -> list[ResourceDecision]:
        return self._repository.list_decisions(subject_id)
