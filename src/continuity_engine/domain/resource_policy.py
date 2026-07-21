from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from .errors import ResourceValidationError
from .resources import (
    ResourceDecision,
    ResourceRequest,
    ResourceSessionType,
    ResourceState,
    RuntimeMode,
)
from .thinking import ThinkingDepth


_DEPTH_ORDER = {
    ThinkingDepth.LOW: 0,
    ThinkingDepth.NORMAL: 1,
    ThinkingDepth.DEEP: 2,
}


@dataclass(frozen=True, slots=True)
class DepthCost:
    tokens: int
    compute: int


class ResourcePolicy:
    """Deterministically approve, downgrade, or defer resource requests."""

    DEPTH_COSTS = {
        ThinkingDepth.LOW: DepthCost(tokens=256, compute=1),
        ThinkingDepth.NORMAL: DepthCost(tokens=1024, compute=2),
        ThinkingDepth.DEEP: DepthCost(tokens=4096, compute=4),
    }
    MODE_DEPTH_CAPS = {
        RuntimeMode.LOW_FREQUENCY: ThinkingDepth.LOW,
        RuntimeMode.SCHEDULED: ThinkingDepth.NORMAL,
        RuntimeMode.CONTINUOUS: ThinkingDepth.NORMAL,
        RuntimeMode.DEEP_THINKING: ThinkingDepth.DEEP,
    }

    def __init__(self, *, token_reserve_ratio: float = 0.1) -> None:
        if not isinstance(token_reserve_ratio, (int, float)) or not 0 <= float(
            token_reserve_ratio
        ) < 1:
            raise ResourceValidationError(
                "token_reserve_ratio must be between zero and one"
            )
        self._token_reserve_ratio = float(token_reserve_ratio)

    def evaluate(
        self,
        state: ResourceState,
        request: ResourceRequest,
        *,
        decided_at: datetime,
    ) -> ResourceDecision:
        if state.subject_id != request.subject_id:
            raise ResourceValidationError(
                "resource request subject does not match state"
            )
        if request.session_type is ResourceSessionType.THINKING:
            return self._evaluate_thinking(state, request, decided_at)
        return self._evaluate_standard(state, request, decided_at)

    def _evaluate_thinking(
        self,
        state: ResourceState,
        request: ResourceRequest,
        decided_at: datetime,
    ) -> ResourceDecision:
        assert request.requested_depth is not None
        token_ratio = self._ratio(state.token_remaining, state.token_budget)
        compute_ratio = self._ratio(state.compute_remaining or 0, state.compute_budget)
        cap = self.MODE_DEPTH_CAPS[state.current_mode]
        approved_depth = self._shallower(request.requested_depth, cap)
        reasons: list[str] = []
        if approved_depth is not request.requested_depth:
            reasons.append(
                f"runtime mode {state.current_mode.value} caps thinking at "
                f"{approved_depth.value}"
            )
        if min(token_ratio, compute_ratio) <= 0.3 and approved_depth is not ThinkingDepth.LOW:
            approved_depth = ThinkingDepth.LOW
            reasons.append("remaining resources require LOW thinking depth")

        tokens, compute = self._cost_for_depth(request, approved_depth)
        if not self._fits(state, tokens, compute) and approved_depth is not ThinkingDepth.LOW:
            approved_depth = ThinkingDepth.LOW
            tokens, compute = self._cost_for_depth(request, approved_depth)
            reasons.append("requested depth did not fit; the request was downgraded to LOW")

        lower_frequency, recommended_mode = self._frequency_advice(
            state, token_ratio, compute_ratio
        )
        if not self._fits(state, tokens, compute):
            return self._decision(
                state,
                request,
                allowed=False,
                approved_depth=ThinkingDepth.LOW,
                allocated_tokens=0,
                allocated_compute=0,
                lower_frequency=True,
                defer=True,
                reason=(
                    "Even LOW thinking would cross the protected resource reserve; "
                    "the session must wait for a later budget window."
                ),
                recommended_mode=RuntimeMode.LOW_FREQUENCY,
                decided_at=decided_at,
            )

        if not reasons:
            reasons.append(
                f"resources allow {approved_depth.value} thinking in "
                f"{state.current_mode.value} mode"
            )
        return self._decision(
            state,
            request,
            allowed=True,
            approved_depth=approved_depth,
            allocated_tokens=tokens,
            allocated_compute=compute,
            lower_frequency=lower_frequency,
            defer=False,
            reason="; ".join(reasons) + ".",
            recommended_mode=recommended_mode,
            decided_at=decided_at,
        )

    def _evaluate_standard(
        self,
        state: ResourceState,
        request: ResourceRequest,
        decided_at: datetime,
    ) -> ResourceDecision:
        token_ratio = self._ratio(state.token_remaining, state.token_budget)
        compute_ratio = self._ratio(state.compute_remaining or 0, state.compute_budget)
        lower_frequency, recommended_mode = self._frequency_advice(
            state, token_ratio, compute_ratio
        )
        if not self._fits(
            state, request.estimated_tokens, request.estimated_compute
        ):
            label = request.session_type.value.lower()
            return self._decision(
                state,
                request,
                allowed=False,
                approved_depth=None,
                allocated_tokens=0,
                allocated_compute=0,
                lower_frequency=True,
                defer=True,
                reason=(
                    f"The {label} request would exceed the protected token or "
                    "compute budget and was deferred instead of failed."
                ),
                recommended_mode=RuntimeMode.LOW_FREQUENCY,
                decided_at=decided_at,
            )
        return self._decision(
            state,
            request,
            allowed=True,
            approved_depth=None,
            allocated_tokens=request.estimated_tokens,
            allocated_compute=request.estimated_compute,
            lower_frequency=lower_frequency,
            defer=False,
            reason=(
                f"The {request.session_type.value.lower()} request fits the current "
                "token and compute budgets."
            ),
            recommended_mode=recommended_mode,
            decided_at=decided_at,
        )

    def _fits(self, state: ResourceState, tokens: int, compute: int) -> bool:
        protected_tokens = int(state.token_budget * self._token_reserve_ratio)
        usable_tokens = max(0, state.token_remaining - protected_tokens)
        return tokens <= usable_tokens and compute <= (state.compute_remaining or 0)

    def _cost_for_depth(
        self,
        request: ResourceRequest,
        depth: ThinkingDepth,
    ) -> tuple[int, int]:
        standard = self.DEPTH_COSTS[depth]
        return (
            min(request.estimated_tokens, standard.tokens),
            min(request.estimated_compute, standard.compute),
        )

    @staticmethod
    def _shallower(left: ThinkingDepth, right: ThinkingDepth) -> ThinkingDepth:
        return left if _DEPTH_ORDER[left] <= _DEPTH_ORDER[right] else right

    @staticmethod
    def _ratio(remaining: int, budget: int) -> float:
        return remaining / budget if budget > 0 else 0.0

    @staticmethod
    def _frequency_advice(
        state: ResourceState,
        token_ratio: float,
        compute_ratio: float,
    ) -> tuple[bool, RuntimeMode]:
        constrained = min(token_ratio, compute_ratio) <= 0.4
        continuous_pressure = (
            state.current_mode is RuntimeMode.CONTINUOUS
            and min(token_ratio, compute_ratio) <= 0.6
        )
        if constrained or continuous_pressure:
            return True, RuntimeMode.LOW_FREQUENCY
        return False, state.current_mode

    @staticmethod
    def _decision(
        state: ResourceState,
        request: ResourceRequest,
        *,
        allowed: bool,
        approved_depth: ThinkingDepth | None,
        allocated_tokens: int,
        allocated_compute: int,
        lower_frequency: bool,
        defer: bool,
        reason: str,
        recommended_mode: RuntimeMode,
        decided_at: datetime,
    ) -> ResourceDecision:
        return ResourceDecision(
            decision_id=str(uuid4()),
            request_id=request.request_id,
            subject_id=state.subject_id,
            session_id=request.session_id,
            allowed=allowed,
            approved_depth=approved_depth,
            allocated_tokens=allocated_tokens,
            allocated_compute=allocated_compute,
            lower_frequency=lower_frequency,
            defer=defer,
            reason=reason,
            recommended_mode=recommended_mode,
            decided_at=decided_at,
        )
