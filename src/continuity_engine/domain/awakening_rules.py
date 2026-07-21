from .awakening import WakeAction, WakeContext, WakeDecision


class WakeDecisionPolicy:
    """Deterministic fourth-stage decision policy; it never executes actions."""

    def decide(self, context: WakeContext) -> WakeDecision:
        selected = context.memory_result.selected_memories
        changed_updates = [update for update in context.recent_updates if update.changes]
        viewed_candidates = context.memory_result.decisions

        if selected:
            return WakeDecision(
                action=WakeAction.THINK,
                reason="Relevant memories were selected and should be considered later.",
                decided_at=context.time_info.current_time,
                evidence=[f"memory:{memory.memory_id}" for memory in selected],
            )

        if changed_updates:
            return WakeDecision(
                action=WakeAction.THINK,
                reason="Recent state evolution exists and should be considered later.",
                decided_at=context.time_info.current_time,
                evidence=[f"update:{update.update_id}" for update in changed_updates],
            )

        if viewed_candidates:
            return WakeDecision(
                action=WakeAction.CHECK_MEMORY,
                reason="Memory candidates were reviewed but none were selected as relevant.",
                decided_at=context.time_info.current_time,
                evidence=[
                    f"memory:{decision.candidate.memory_id}" for decision in viewed_candidates
                ],
            )

        continuity = context.subject_state.continuity
        if continuity.unfinished_items or continuity.current_focus:
            return WakeDecision(
                action=WakeAction.READY,
                reason="The subject has active continuity items and the wake context is ready.",
                decided_at=context.time_info.current_time,
                evidence=[
                    *[f"unfinished:{item}" for item in continuity.unfinished_items],
                    *[f"focus:{item}" for item in continuity.current_focus],
                ],
            )

        return WakeDecision(
            action=WakeAction.SLEEP,
            reason="No relevant memory, recent state change, or active continuity item was found.",
            decided_at=context.time_info.current_time,
            evidence=[],
        )
