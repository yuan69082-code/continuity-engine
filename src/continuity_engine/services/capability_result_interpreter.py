from __future__ import annotations

from continuity_engine.domain.capability import CapabilityResult, CapabilityStatus
from continuity_engine.domain.errors import CapabilityValidationError
from continuity_engine.domain.thinking import ThinkSession, ThinkingResult


class CapabilityResultInterpreter:
    """Convert a validated execution fact into a bounded ThinkingResult."""

    def interpret(
        self,
        result: CapabilityResult,
        session: ThinkSession,
        *,
        thinking_result_id: str,
    ) -> ThinkingResult:
        if result.status is not CapabilityStatus.SUCCEEDED or result.output is None:
            raise CapabilityValidationError(
                "only a successful CapabilityResult can resume Thinking"
            )
        if session.capability_request_id != result.capability_request_id:
            raise CapabilityValidationError(
                "CapabilityResult does not match the waiting ThinkSession"
            )
        return ThinkingResult.create(
            result_id=thinking_result_id,
            provider_id=session.provider_id,
            result_summary=result.output.response_candidate,
            rationale_summary=(
                "A validated external model execution fact supplied a bounded "
                "expression candidate. No model chain-of-thought or state mutation "
                "was accepted."
            ),
            generated_new_thought=bool(result.output.response_candidate),
            update_subject_state=False,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=session.token_budget,
        )
