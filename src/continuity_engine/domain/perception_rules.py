from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .events import ChangeOperation, StateSection
from .perception import (
    CurrentFocus,
    Drive,
    DriveKind,
    DriveStrength,
    InteractionFrequencyTrend,
    MemoryImpact,
    MemoryInfluence,
    Observation,
    PerceptionContext,
    PerceptionResult,
    RelationshipDirection,
    RelationshipPerception,
    StateStability,
    TemporalMeaning,
    TemporalPerception,
)


class PerceptionPolicy:
    """Deterministic, model-free interpretation of a read-only wake snapshot."""

    RECENT_WINDOW = timedelta(days=1)
    LONG_SILENCE_WINDOW = timedelta(days=7)
    IMPORTANT_DATE_WINDOW = timedelta(days=7)

    def perceive(self, context: PerceptionContext) -> PerceptionResult:
        focus = self._current_focus(context)
        temporal = self._temporal(context)
        relationship = self._relationship(context, focus, temporal)
        memory = self._memory_influence(context)
        observation = self._observation(context, focus, memory)
        drives = self._drives(context, focus, temporal, memory, observation)
        summary = self._summary(
            focus,
            temporal,
            relationship,
            memory,
            observation,
            drives,
        )
        return PerceptionResult.create(
            context=context,
            current_focus=focus,
            temporal_perception=temporal,
            relationship_perception=relationship,
            memory_influence=memory,
            observation=observation,
            internal_drives=drives,
            summary=summary,
        )

    @staticmethod
    def _current_focus(context: PerceptionContext) -> CurrentFocus:
        state = context.subject_state
        topics = list(state.continuity.current_focus)
        unfinished = list(state.continuity.unfinished_items)
        if topics and unfinished:
            summary = (
                f"Attention remains on {topics[0]}, with unfinished work still present: "
                f"{unfinished[0]}."
            )
        elif topics:
            summary = f"Attention remains centered on {topics[0]}."
        elif unfinished:
            summary = f"The clearest focus is the unfinished item: {unfinished[0]}."
        else:
            summary = "No explicit current focus is present in the subject state."
        return CurrentFocus(topics=topics, unfinished_items=unfinished, summary=summary)

    def _temporal(self, context: PerceptionContext) -> TemporalPerception:
        last = context.subject_state.temporal.last_interaction_at
        if last is None:
            meaning = TemporalMeaning.UNKNOWN
        else:
            elapsed = max(timedelta(0), context.current_time - last)
            if elapsed < self.RECENT_WINDOW:
                meaning = TemporalMeaning.RECENT
            elif elapsed < self.LONG_SILENCE_WINDOW:
                meaning = TemporalMeaning.QUIET
            else:
                meaning = TemporalMeaning.LONG_SILENCE

        frequency = self._interaction_frequency(context)
        dates = self._approaching_dates(context)
        long_silence = meaning is TemporalMeaning.LONG_SILENCE

        meanings = {
            TemporalMeaning.UNKNOWN: "There is no prior interaction point from which to interpret the present interval.",
            TemporalMeaning.RECENT: "The latest interaction still belongs to the immediate continuity of the present moment.",
            TemporalMeaning.QUIET: "A quiet interval has formed, so prior unfinished context may carry more weight.",
            TemporalMeaning.LONG_SILENCE: "A long silence separates the present from the last interaction, making waiting and continuity especially salient.",
        }
        text = meanings[meaning]
        if frequency is InteractionFrequencyTrend.INCREASING:
            text += " Interactions have recently become more frequent."
        elif frequency is InteractionFrequencyTrend.DECREASING:
            text += " Interactions have recently become less frequent."
        if dates:
            text += f" An important date is approaching: {dates[0]}."
        return TemporalPerception(
            last_interaction_meaning=meaning,
            interaction_frequency_trend=frequency,
            long_silence=long_silence,
            approaching_important_dates=dates,
            meaning=text,
        )

    @staticmethod
    def _interaction_frequency(context: PerceptionContext) -> InteractionFrequencyTrend:
        interactions = sorted(
            (
                event.occurred_at
                for event in context.recent_events
                if event.event_type == "interaction"
            )
        )
        if len(interactions) < 3:
            return InteractionFrequencyTrend.UNKNOWN
        previous_gap = (interactions[-2] - interactions[-3]).total_seconds()
        latest_gap = (interactions[-1] - interactions[-2]).total_seconds()
        if previous_gap <= 0 or latest_gap <= 0:
            return InteractionFrequencyTrend.UNKNOWN
        ratio = latest_gap / previous_gap
        if ratio <= 0.75:
            return InteractionFrequencyTrend.INCREASING
        if ratio >= 1.25:
            return InteractionFrequencyTrend.DECREASING
        return InteractionFrequencyTrend.STABLE

    def _approaching_dates(self, context: PerceptionContext) -> list[str]:
        dates: list[str] = []
        cutoff = context.current_time + self.IMPORTANT_DATE_WINDOW
        for event in context.recent_events:
            raw = event.metadata.get("important_at", event.metadata.get("important_date"))
            parsed = self._metadata_datetime(raw, context.current_time)
            if parsed is not None and context.current_time <= parsed <= cutoff:
                label = event.metadata.get("important_label")
                dates.append(
                    label.strip()
                    if isinstance(label, str) and label.strip()
                    else parsed.date().isoformat()
                )
        return list(dict.fromkeys(dates))

    @staticmethod
    def _metadata_datetime(value: Any, current_time: datetime) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value).replace(
                    tzinfo=current_time.tzinfo
                )
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=current_time.tzinfo)
        return parsed

    @staticmethod
    def _relationship(
        context: PerceptionContext,
        focus: CurrentFocus,
        temporal: TemporalPerception,
    ) -> RelationshipPerception:
        relation_changes = [
            change
            for update in context.wake_context.recent_updates
            for change in update.changes
            if change.field_path.startswith("relationship.")
        ]
        declared_directions = [
            event.metadata.get("relationship_direction")
            for event in context.recent_events
        ]
        if any(value in ("closer", "CLOSER") for value in declared_directions):
            direction = RelationshipDirection.CLOSER
        elif any(value in ("farther", "FARTHER") for value in declared_directions):
            direction = RelationshipDirection.FARTHER
        elif relation_changes:
            direction = RelationshipDirection.CHANGED
        elif context.subject_state.relationship.current_status:
            direction = RelationshipDirection.STABLE
        else:
            direction = RelationshipDirection.UNCLEAR

        unfinished = bool(focus.unfinished_items)
        waiting = unfinished and temporal.long_silence
        observations: list[str] = []
        if relation_changes:
            observations.append("Recent state evolution includes a relationship change.")
        if unfinished:
            observations.append("An unfinished exchange or shared task remains visible.")
        if focus.topics:
            observations.append("A topic continues to hold attention across the current state.")
        if waiting:
            observations.append("The unfinished context now carries a sense of waiting.")
        if not observations:
            observations.append("No explicit relationship movement is visible in the available context.")

        direction_text = {
            RelationshipDirection.CLOSER: "The available evidence marks the relationship as moving closer.",
            RelationshipDirection.FARTHER: "The available evidence marks the relationship as moving farther apart.",
            RelationshipDirection.CHANGED: "The relationship has changed, but the available structured evidence does not establish closer or farther.",
            RelationshipDirection.STABLE: "The relationship appears stable in the available recent context.",
            RelationshipDirection.UNCLEAR: "There is not enough structured evidence to interpret relationship movement.",
        }[direction]
        if waiting:
            direction_text += " An unfinished matter remains present through a long silence."
        return RelationshipPerception(
            direction=direction,
            unfinished_exchange=unfinished,
            sustained_topics=list(focus.topics),
            waiting_signal=waiting,
            observations=observations,
            summary=direction_text,
        )

    @staticmethod
    def _memory_influence(context: PerceptionContext) -> MemoryInfluence:
        impacts: list[MemoryImpact] = []
        for decision in context.memory_result.decisions:
            if not decision.selected:
                continue
            candidate = decision.candidate
            scopes = [section.value for section in candidate.related_scope]
            scope_text = ", ".join(scopes) if scopes else "the current context"
            reason = " ".join(decision.reasons)
            impacts.append(
                MemoryImpact(
                    memory_id=candidate.memory_id,
                    recalled_experience=candidate.content,
                    affected_scopes=scopes,
                    influence_reason=(
                        f"This experience is present because it is relevant to {scope_text}. "
                        f"{reason}"
                    ),
                    relevance_score=decision.relevance_score,
                )
            )
        if impacts:
            first = impacts[0]
            summary = (
                f"The experience '{first.recalled_experience}' has returned to attention; "
                f"{first.influence_reason}"
            )
        else:
            summary = "No retrieved experience currently exerts a selected influence on perception."
        return MemoryInfluence(impacts=impacts, summary=summary)

    @staticmethod
    def _observation(
        context: PerceptionContext,
        focus: CurrentFocus,
        memory: MemoryInfluence,
    ) -> Observation:
        changes = [
            change
            for update in context.wake_context.recent_updates
            for change in update.changes
            if change.field_path != "temporal.updated_at"
        ]
        changed_fields = {change.field_path for change in changes}
        major = bool(
            any(
                field.startswith("identity.") or field.startswith("relationship.")
                for field in changed_fields
            )
            or len(changed_fields) >= 3
        )
        decisions = context.memory_result.decisions
        needs_information = (
            bool(decisions) and not memory.impacts
        ) or (not focus.topics and not focus.unfinished_items and not memory.impacts)

        values_by_field: dict[str, list[Any]] = defaultdict(list)
        operations_by_field: dict[str, list[ChangeOperation]] = defaultdict(list)
        for change in changes:
            values_by_field[change.field_path].append(change.after)
            operations_by_field[change.field_path].append(change.operation)
        conflicts = [
            f"Recent SET changes disagree on {field_path}."
            for field_path, values in values_by_field.items()
            if len(values) > 1
            and all(op is ChangeOperation.SET for op in operations_by_field[field_path])
            and any(value != values[0] for value in values[1:])
        ]

        notes = [
            (
                "The subject state has recent substantive changes."
                if changes
                else "The subject state is stable across the available recent evolution."
            )
        ]
        if major:
            notes.append("At least one change crosses a major identity or relationship boundary.")
        if needs_information:
            notes.append("The available evidence leaves an information gap.")
        if conflicts:
            notes.append("Potentially conflicting recent state values require interpretation.")
        return Observation(
            state_stability=(StateStability.CHANGED if changes else StateStability.STABLE),
            major_change=major,
            needs_more_information=needs_information,
            conflicts=conflicts,
            notes=notes,
        )

    @staticmethod
    def _drives(
        context: PerceptionContext,
        focus: CurrentFocus,
        temporal: TemporalPerception,
        memory: MemoryInfluence,
        observation: Observation,
    ) -> list[Drive]:
        drives: list[Drive] = []
        if focus.topics:
            drives.append(
                Drive(
                    DriveKind.CONTINUE_TOPIC,
                    f"A tendency exists to continue attending to {focus.topics[0]}.",
                    "current_focus",
                    DriveStrength.NORMAL,
                )
            )
        if focus.unfinished_items:
            drives.append(
                Drive(
                    DriveKind.CONFIRM_UNFINISHED,
                    f"A tendency exists to clarify the unfinished matter: {focus.unfinished_items[0]}.",
                    "unfinished_exchange",
                    DriveStrength.HIGH,
                )
            )
        if temporal.long_silence:
            drives.append(
                Drive(
                    DriveKind.KEEP_WAITING,
                    "A tendency exists to preserve continuity without converting silence into an action.",
                    "temporal_perception",
                    DriveStrength.NORMAL,
                )
            )
        if memory.impacts:
            drives.append(
                Drive(
                    DriveKind.INTEGRATE_MEMORY,
                    "A tendency exists to integrate the recalled experience into later thinking.",
                    "memory_influence",
                    DriveStrength.NORMAL,
                )
            )
        elif context.memory_result.decisions or observation.needs_more_information:
            drives.append(
                Drive(
                    DriveKind.EXPLORE_MEMORY,
                    "A tendency exists to seek more relevant memory before reaching a conclusion.",
                    "information_gap",
                    DriveStrength.NORMAL,
                )
            )
        if not drives:
            drives.append(
                Drive(
                    DriveKind.MAINTAIN_STABILITY,
                    "A tendency exists to preserve the current stable state.",
                    "stable_observation",
                    DriveStrength.LOW,
                )
            )
        return drives

    @staticmethod
    def _summary(
        focus: CurrentFocus,
        temporal: TemporalPerception,
        relationship: RelationshipPerception,
        memory: MemoryInfluence,
        observation: Observation,
        drives: list[Drive],
    ) -> str:
        stability = (
            "The current state appears stable."
            if observation.state_stability is StateStability.STABLE
            else "Recent state evolution remains perceptible."
        )
        return " ".join(
            (
                focus.summary,
                temporal.meaning,
                relationship.summary,
                memory.summary,
                stability,
                drives[0].tendency,
            )
        )
