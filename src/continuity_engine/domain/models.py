from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .errors import StateValidationError


SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise StateValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateValidationError(f"{field_name} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise StateValidationError(f"{field_name} must include a timezone")
    return parsed


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise StateValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise StateValidationError(f"{field_name} must be an object")
    return value


def _string(value: Any, field_name: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise StateValidationError(f"{field_name} must be a string")
    return value


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise StateValidationError(f"{field_name} must be a list of strings")
    return list(value)


@dataclass(slots=True)
class IdentityState:
    stable_traits: list[str] = field(default_factory=list)
    expression_preferences: list[str] = field(default_factory=list)
    judgment_principles: list[str] = field(default_factory=list)
    self_concept: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> IdentityState:
        data = _mapping(value, "identity")
        return cls(
            stable_traits=_string_list(data.get("stable_traits"), "identity.stable_traits"),
            expression_preferences=_string_list(
                data.get("expression_preferences"), "identity.expression_preferences"
            ),
            judgment_principles=_string_list(
                data.get("judgment_principles"), "identity.judgment_principles"
            ),
            self_concept=_string(data.get("self_concept"), "identity.self_concept"),
        )


@dataclass(slots=True)
class RelationshipState:
    definition: str = ""
    interaction_preferences: list[str] = field(default_factory=list)
    important_moments: list[str] = field(default_factory=list)
    current_status: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> RelationshipState:
        data = _mapping(value, "relationship")
        return cls(
            definition=_string(data.get("definition"), "relationship.definition"),
            interaction_preferences=_string_list(
                data.get("interaction_preferences"), "relationship.interaction_preferences"
            ),
            important_moments=_string_list(
                data.get("important_moments"), "relationship.important_moments"
            ),
            current_status=_string(data.get("current_status"), "relationship.current_status"),
        )


@dataclass(slots=True)
class ContinuityState:
    unfinished_items: list[str] = field(default_factory=list)
    current_focus: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> ContinuityState:
        data = _mapping(value, "continuity")
        return cls(
            unfinished_items=_string_list(
                data.get("unfinished_items"), "continuity.unfinished_items"
            ),
            current_focus=_string_list(data.get("current_focus"), "continuity.current_focus"),
            recent_changes=_string_list(data.get("recent_changes"), "continuity.recent_changes"),
        )


@dataclass(slots=True)
class TemporalState:
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_interaction_at: datetime | None = None
    lifecycle_events: list[str] = field(default_factory=list)

    def seconds_since_last_interaction(self, now: datetime | None = None) -> float | None:
        if self.last_interaction_at is None:
            return None
        current = now or utc_now()
        if current.tzinfo is None:
            raise StateValidationError("now must include a timezone")
        return max(0.0, (current - self.last_interaction_at).total_seconds())

    @classmethod
    def from_dict(cls, value: Any) -> TemporalState:
        data = _mapping(value, "temporal")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if created_at is None or updated_at is None:
            raise StateValidationError("temporal.created_at and temporal.updated_at are required")
        last_interaction_at = data.get("last_interaction_at")
        return cls(
            created_at=_parse_datetime(created_at, "temporal.created_at"),
            updated_at=_parse_datetime(updated_at, "temporal.updated_at"),
            last_interaction_at=(
                _parse_datetime(last_interaction_at, "temporal.last_interaction_at")
                if last_interaction_at is not None
                else None
            ),
            lifecycle_events=_string_list(
                data.get("lifecycle_events"), "temporal.lifecycle_events"
            ),
        )


@dataclass(slots=True)
class IntentionsState:
    emerging_thoughts: list[str] = field(default_factory=list)
    judgments: list[str] = field(default_factory=list)
    action_tendencies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> IntentionsState:
        data = _mapping(value, "intentions")
        return cls(
            emerging_thoughts=_string_list(
                data.get("emerging_thoughts"), "intentions.emerging_thoughts"
            ),
            judgments=_string_list(data.get("judgments"), "intentions.judgments"),
            action_tendencies=_string_list(
                data.get("action_tendencies"), "intentions.action_tendencies"
            ),
        )


@dataclass(slots=True)
class EmotionState:
    interaction_state: str = ""
    emotions: list[str] = field(default_factory=list)
    continuity_notes: list[str] = field(default_factory=list)

    current_state: str | None = None
    intensity: float | None = None
    updated_at: str | None = None
    confidence: float | None = None
    baseline: float | None = None

    def to_dict(self):
        import math
        result = {"interaction_state": self.interaction_state,
                  "emotions": list(self.emotions), "continuity_notes": list(self.continuity_notes)}
        values = (self.current_state, self.intensity, self.updated_at, self.confidence, self.baseline)
        if any(v is not None for v in values):
            if (not isinstance(self.current_state, str) or not self.current_state
                    or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                           for v in (self.intensity, self.confidence, self.baseline))):
                raise StateValidationError("invalid C1 emotion result")
            _parse_datetime(self.updated_at, "emotion_state.updated_at")
            result.update(current_state=self.current_state, intensity=self.intensity,
                          updated_at=self.updated_at, confidence=self.confidence, baseline=self.baseline)
        return result

    def effective_at(self, at: datetime, *, half_life_seconds: float = 86400.0):
        import math
        self.to_dict()
        if at.tzinfo is None or type(half_life_seconds) not in (int, float) or not math.isfinite(half_life_seconds) or half_life_seconds <= 0:
            raise StateValidationError("invalid C1 emotion clock or half life")
        if self.current_state is None:
            return {"current_state": self.interaction_state, "intensity": 0.0,
                    "confidence": 0.0, "elapsed_seconds": 0.0}
        elapsed = max(0.0, (at - _parse_datetime(self.updated_at, "emotion_state.updated_at")).total_seconds())
        intensity = self.baseline + (self.intensity - self.baseline) * 2 ** (-elapsed / half_life_seconds)
        return {"current_state": self.current_state, "intensity": round(intensity, 9),
                "confidence": self.confidence, "elapsed_seconds": elapsed}

    @classmethod
    def from_dict(cls, value: Any) -> EmotionState:
        data = _mapping(value, "emotion_state")
        result = cls(
            current_state=data.get("current_state"), intensity=data.get("intensity"),
            updated_at=data.get("updated_at"), confidence=data.get("confidence"),
            baseline=data.get("baseline"),
            interaction_state=_string(
                data.get("interaction_state"), "emotion_state.interaction_state"
            ),
            emotions=_string_list(data.get("emotions"), "emotion_state.emotions"),
            continuity_notes=_string_list(
                data.get("continuity_notes"), "emotion_state.continuity_notes"
            ),
        )

        result.to_dict()
        return result


@dataclass(slots=True)
class SubjectState:
    subject_id: str
    identity: IdentityState = field(default_factory=IdentityState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    continuity: ContinuityState = field(default_factory=ContinuityState)
    temporal: TemporalState = field(default_factory=TemporalState)
    intentions: IntentionsState = field(default_factory=IntentionsState)
    emotion_state: EmotionState = field(default_factory=EmotionState)
    schema_version: int = SCHEMA_VERSION
    revision: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.subject_id, str) or not self.subject_id.strip():
            raise StateValidationError("subject_id must be a non-empty string")
        if self.schema_version != SCHEMA_VERSION:
            raise StateValidationError(
                f"unsupported schema_version {self.schema_version}; expected {SCHEMA_VERSION}"
            )
        if not isinstance(self.revision, int) or self.revision < 0:
            raise StateValidationError("revision must be a non-negative integer")

    @classmethod
    def create(cls, subject_id: str, now: datetime | None = None) -> SubjectState:
        created = now or utc_now()
        if created.tzinfo is None:
            raise StateValidationError("now must include a timezone")
        return cls(
            subject_id=subject_id,
            temporal=TemporalState(created_at=created, updated_at=created),
        )

    def mark_updated(self, now: datetime | None = None) -> None:
        updated = now or utc_now()
        if updated.tzinfo is None:
            raise StateValidationError("now must include a timezone")
        self.temporal.updated_at = updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "subject_id": self.subject_id,
            "identity": {
                "stable_traits": list(self.identity.stable_traits),
                "expression_preferences": list(self.identity.expression_preferences),
                "judgment_principles": list(self.identity.judgment_principles),
                "self_concept": self.identity.self_concept,
            },
            "relationship": {
                "definition": self.relationship.definition,
                "interaction_preferences": list(self.relationship.interaction_preferences),
                "important_moments": list(self.relationship.important_moments),
                "current_status": self.relationship.current_status,
            },
            "continuity": {
                "unfinished_items": list(self.continuity.unfinished_items),
                "current_focus": list(self.continuity.current_focus),
                "recent_changes": list(self.continuity.recent_changes),
            },
            "temporal": {
                "created_at": _format_datetime(self.temporal.created_at),
                "updated_at": _format_datetime(self.temporal.updated_at),
                "last_interaction_at": (
                    _format_datetime(self.temporal.last_interaction_at)
                    if self.temporal.last_interaction_at is not None
                    else None
                ),
                "lifecycle_events": list(self.temporal.lifecycle_events),
            },
            "intentions": {
                "emerging_thoughts": list(self.intentions.emerging_thoughts),
                "judgments": list(self.intentions.judgments),
                "action_tendencies": list(self.intentions.action_tendencies),
            },
            "emotion_state": self.emotion_state.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> SubjectState:
        data = _mapping(value, "subject_state")
        schema_version = data.get("schema_version")
        if not isinstance(schema_version, int):
            raise StateValidationError("schema_version must be an integer")
        return cls(
            schema_version=schema_version,
            revision=data.get("revision", 0),
            subject_id=_string(data.get("subject_id"), "subject_id"),
            identity=IdentityState.from_dict(data.get("identity")),
            relationship=RelationshipState.from_dict(data.get("relationship")),
            continuity=ContinuityState.from_dict(data.get("continuity")),
            temporal=TemporalState.from_dict(data.get("temporal")),
            intentions=IntentionsState.from_dict(data.get("intentions")),
            emotion_state=EmotionState.from_dict(data.get("emotion_state")),
        )
