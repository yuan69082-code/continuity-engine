from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .errors import StateEvolutionError
from .events import (
    ChangeOperation,
    Event,
    FieldChange,
    JsonValue,
    StateSection,
    StateUpdateRecord,
)
from .models import SubjectState


@dataclass(frozen=True, slots=True)
class FieldRule:
    section: StateSection
    value_type: type
    list_item_type: type | None = None


FIELD_RULES: dict[str, FieldRule] = {
    "identity.stable_traits": FieldRule(StateSection.IDENTITY, list, str),
    "identity.expression_preferences": FieldRule(StateSection.IDENTITY, list, str),
    "identity.judgment_principles": FieldRule(StateSection.IDENTITY, list, str),
    "identity.self_concept": FieldRule(StateSection.IDENTITY, str),
    "relationship.definition": FieldRule(StateSection.RELATIONSHIP, str),
    "relationship.interaction_preferences": FieldRule(StateSection.RELATIONSHIP, list, str),
    "relationship.important_moments": FieldRule(StateSection.RELATIONSHIP, list, str),
    "relationship.current_status": FieldRule(StateSection.RELATIONSHIP, str),
    "continuity.unfinished_items": FieldRule(StateSection.CONTINUITY, list, str),
    "continuity.current_focus": FieldRule(StateSection.CONTINUITY, list, str),
    "continuity.recent_changes": FieldRule(StateSection.CONTINUITY, list, str),
    "temporal.lifecycle_events": FieldRule(StateSection.TEMPORAL, list, str),
    "intentions.emerging_thoughts": FieldRule(StateSection.INTENTIONS, list, str),
    "intentions.judgments": FieldRule(StateSection.INTENTIONS, list, str),
    "intentions.action_tendencies": FieldRule(StateSection.INTENTIONS, list, str),
    "emotion_state.current_state": FieldRule(StateSection.EMOTION_STATE, str),
    "emotion_state.intensity": FieldRule(StateSection.EMOTION_STATE, float),
    "emotion_state.updated_at": FieldRule(StateSection.EMOTION_STATE, str),
    "emotion_state.confidence": FieldRule(StateSection.EMOTION_STATE, float),
    "emotion_state.baseline": FieldRule(StateSection.EMOTION_STATE, float),
    "emotion_state.interaction_state": FieldRule(StateSection.EMOTION_STATE, str),
    "emotion_state.emotions": FieldRule(StateSection.EMOTION_STATE, list, str),
    "emotion_state.continuity_notes": FieldRule(StateSection.EMOTION_STATE, list, str),
}


@dataclass(slots=True)
class StateEvolutionResult:
    state: SubjectState
    update: StateUpdateRecord
    idempotent_replay: bool = False


def _json_value(value: Any) -> JsonValue:
    if isinstance(value, list):
        return list(value)
    return value


def _field_owner(state: SubjectState, field_path: str) -> tuple[Any, str]:
    section_name, attribute_name = field_path.split(".", 1)
    return getattr(state, section_name), attribute_name


class SubjectStateEvolver:
    """Apply explicit event effects under a small, auditable rule set."""

    def evolve(
        self,
        state: SubjectState,
        event: Event,
        *,
        applied_at: datetime,
    ) -> StateEvolutionResult:
        if applied_at.tzinfo is None:
            raise StateEvolutionError("applied_at must include a timezone")

        evolved = SubjectState.from_dict(state.to_dict())
        changes: list[FieldChange] = []
        scope = set(event.impact_scope)

        for mutation in event.mutations:
            rule = FIELD_RULES.get(mutation.field_path)
            if rule is None:
                raise StateEvolutionError(f"field cannot be changed by events: {mutation.field_path}")
            if rule.section not in scope:
                raise StateEvolutionError(
                    f"field {mutation.field_path} is outside the event impact scope"
                )

            owner, attribute_name = _field_owner(evolved, mutation.field_path)
            before = _json_value(getattr(owner, attribute_name))
            after = self._apply_mutation(before, mutation.operation, mutation.value, rule)
            if after == before:
                continue
            setattr(owner, attribute_name, after)
            changes.append(
                FieldChange(
                    field_path=mutation.field_path,
                    operation=mutation.operation,
                    before=before,
                    after=_json_value(after),
                    reason=mutation.reason,
                )
            )

        if event.event_type == "interaction":
            if StateSection.TEMPORAL not in scope:
                raise StateEvolutionError("interaction events must include temporal impact scope")
            previous_interaction = evolved.temporal.last_interaction_at
            next_interaction = event.occurred_at
            if previous_interaction is None or next_interaction > previous_interaction:
                evolved.temporal.last_interaction_at = next_interaction
                changes.append(
                    FieldChange(
                        field_path="temporal.last_interaction_at",
                        operation=ChangeOperation.SET,
                        before=(
                            previous_interaction.astimezone(timezone.utc).isoformat().replace(
                                "+00:00", "Z"
                            )
                            if previous_interaction is not None
                            else None
                        ),
                        after=next_interaction.astimezone(timezone.utc).isoformat().replace(
                            "+00:00", "Z"
                        ),
                        reason="The event represents a newer interaction.",
                    )
                )

        before_revision = state.revision
        if changes:
            previous_updated_at = evolved.temporal.updated_at
            effective_applied_at = max(applied_at, previous_updated_at)
            if effective_applied_at != previous_updated_at:
                evolved.temporal.updated_at = effective_applied_at
                changes.append(
                    FieldChange(
                        field_path="temporal.updated_at",
                        operation=ChangeOperation.SET,
                        before=previous_updated_at.astimezone(timezone.utc).isoformat().replace(
                            "+00:00", "Z"
                        ),
                        after=effective_applied_at.astimezone(timezone.utc).isoformat().replace(
                            "+00:00", "Z"
                        ),
                        reason="SubjectState changed while applying the event.",
                    )
                )
            evolved.revision += 1

        update = StateUpdateRecord(
            update_id=str(uuid4()),
            subject_id=state.subject_id,
            event=event,
            applied_at=applied_at,
            before_revision=before_revision,
            after_revision=evolved.revision,
            changes=changes,
            reason=event.reason,
        )
        return StateEvolutionResult(state=evolved, update=update)

    @staticmethod
    def _apply_mutation(
        before: JsonValue,
        operation: ChangeOperation,
        value: JsonValue,
        rule: FieldRule,
    ) -> JsonValue:
        if operation is ChangeOperation.SET:
            if rule.value_type is float:
                import math
                if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise StateEvolutionError("emotion value must be a finite ratio")
                return float(value)
            if rule.value_type is str:
                if not isinstance(value, str):
                    raise StateEvolutionError("set value must be a string for this field")
                return value
            if not isinstance(value, list) or any(
                not isinstance(item, rule.list_item_type) for item in value
            ):
                raise StateEvolutionError("set value must be a valid list for this field")
            return list(value)

        if rule.value_type is not list:
            raise StateEvolutionError(f"{operation.value} is only supported for list fields")
        if not isinstance(value, rule.list_item_type):
            raise StateEvolutionError("list mutation value has an invalid type")

        current = list(before) if isinstance(before, list) else []
        if operation is ChangeOperation.APPEND:
            if value not in current:
                current.append(value)
            return current
        if operation is ChangeOperation.REMOVE:
            if value in current:
                current.remove(value)
            return current
        raise StateEvolutionError(f"unsupported change operation: {operation}")
