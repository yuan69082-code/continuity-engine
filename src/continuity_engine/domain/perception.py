from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .awakening import AwakeningResult, WakeContext
from .errors import PerceptionValidationError
from .events import Event, JsonValue
from .memory import MemoryRetrievalResult
from .models import SubjectState


class TemporalMeaning(str, Enum):
    UNKNOWN = "UNKNOWN"
    RECENT = "RECENT"
    QUIET = "QUIET"
    LONG_SILENCE = "LONG_SILENCE"


class InteractionFrequencyTrend(str, Enum):
    UNKNOWN = "UNKNOWN"
    INCREASING = "INCREASING"
    STABLE = "STABLE"
    DECREASING = "DECREASING"


class RelationshipDirection(str, Enum):
    UNCLEAR = "UNCLEAR"
    STABLE = "STABLE"
    CHANGED = "CHANGED"
    CLOSER = "CLOSER"
    FARTHER = "FARTHER"


class StateStability(str, Enum):
    STABLE = "STABLE"
    CHANGED = "CHANGED"


class DriveKind(str, Enum):
    CONTINUE_TOPIC = "CONTINUE_TOPIC"
    CONFIRM_UNFINISHED = "CONFIRM_UNFINISHED"
    KEEP_WAITING = "KEEP_WAITING"
    EXPLORE_MEMORY = "EXPLORE_MEMORY"
    INTEGRATE_MEMORY = "INTEGRATE_MEMORY"
    MAINTAIN_STABILITY = "MAINTAIN_STABILITY"


class DriveStrength(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PerceptionValidationError(f"{field_name} must be a non-empty string")
    return value


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise PerceptionValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise PerceptionValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PerceptionValidationError(
            f"{field_name} is not a valid ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None:
        raise PerceptionValidationError(f"{field_name} must include a timezone")
    return parsed


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PerceptionValidationError(
            f"{field_name} must be a list of non-empty strings"
        )
    return list(value)


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        raise PerceptionValidationError(f"unsupported {field_name}") from exc


@dataclass(slots=True)
class PerceptionContext:
    """Read-only, unified input boundary for one perception pass."""

    context_id: str
    wake_session_id: str
    subject_state: SubjectState
    wake_context: WakeContext
    memory_result: MemoryRetrievalResult
    recent_events: list[Event]
    current_time: datetime

    def __post_init__(self) -> None:
        _require_text(self.context_id, "perception context_id")
        _require_text(self.wake_session_id, "perception wake_session_id")
        if self.current_time.tzinfo is None:
            raise PerceptionValidationError("perception current_time must include a timezone")
        subject_id = self.subject_state.subject_id
        if self.wake_context.subject_state.subject_id != subject_id:
            raise PerceptionValidationError("WakeContext subject does not match perception")
        if self.wake_context.subject_state.revision != self.subject_state.revision:
            raise PerceptionValidationError("WakeContext revision does not match perception")
        if self.memory_result.request.subject_id != subject_id:
            raise PerceptionValidationError("memory result subject does not match perception")
        if (
            self.memory_result.request.request_id
            != self.wake_context.memory_result.request.request_id
        ):
            raise PerceptionValidationError("memory result does not match WakeContext")
        if [item.event_id for item in self.recent_events] != [
            item.event_id for item in self.wake_context.recent_events
        ]:
            raise PerceptionValidationError("recent events do not match WakeContext")
        if any(
            decision.candidate.subject_id != subject_id
            for decision in self.memory_result.decisions
            if decision.relevant
        ):
            raise PerceptionValidationError("a relevant memory belongs to another subject")

    @classmethod
    def from_awakening(
        cls,
        awakening: AwakeningResult,
        *,
        current_time: datetime,
        context_id: str | None = None,
    ) -> PerceptionContext:
        session = awakening.session
        if not session.completed_successfully or session.decision is None:
            raise PerceptionValidationError(
                "perception requires a successfully completed WakeSession"
            )
        if session.subject_id != awakening.context.subject_state.subject_id:
            raise PerceptionValidationError("WakeSession subject does not match WakeContext")
        return cls(
            context_id=context_id or str(uuid4()),
            wake_session_id=session.session_id,
            subject_state=SubjectState.from_dict(
                awakening.context.subject_state.to_dict()
            ),
            wake_context=awakening.context,
            memory_result=awakening.context.memory_result,
            recent_events=list(awakening.context.recent_events),
            current_time=current_time,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "context_id": self.context_id,
            "wake_session_id": self.wake_session_id,
            "subject_state": self.subject_state.to_dict(),
            "wake_context": self.wake_context.to_dict(),
            "memory_result": self.memory_result.to_dict(),
            "recent_events": [item.to_dict() for item in self.recent_events],
            "current_time": _format_datetime(self.current_time),
        }

    @classmethod
    def from_dict(cls, value: Any) -> PerceptionContext:
        if not isinstance(value, dict) or not isinstance(
            value.get("recent_events"), list
        ):
            raise PerceptionValidationError(
                "perception context must contain recent_events"
            )
        return cls(
            context_id=value.get("context_id"),
            wake_session_id=value.get("wake_session_id"),
            subject_state=SubjectState.from_dict(value.get("subject_state")),
            wake_context=WakeContext.from_dict(value.get("wake_context")),
            memory_result=MemoryRetrievalResult.from_dict(
                value.get("memory_result")
            ),
            recent_events=[
                Event.from_dict(item) for item in value["recent_events"]
            ],
            current_time=_parse_datetime(
                value.get("current_time"), "perception current_time"
            ),
        )


@dataclass(slots=True)
class CurrentFocus:
    topics: list[str]
    unfinished_items: list[str]
    summary: str

    def __post_init__(self) -> None:
        self.topics = _text_list(self.topics, "focus topics")
        self.unfinished_items = _text_list(
            self.unfinished_items, "focus unfinished_items"
        )
        _require_text(self.summary, "focus summary")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "topics": list(self.topics),
            "unfinished_items": list(self.unfinished_items),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CurrentFocus:
        if not isinstance(value, dict):
            raise PerceptionValidationError("current_focus must be an object")
        return cls(
            topics=_text_list(value.get("topics", []), "focus topics"),
            unfinished_items=_text_list(
                value.get("unfinished_items", []), "focus unfinished_items"
            ),
            summary=value.get("summary"),
        )


@dataclass(slots=True)
class TemporalPerception:
    last_interaction_meaning: TemporalMeaning
    interaction_frequency_trend: InteractionFrequencyTrend
    long_silence: bool
    approaching_important_dates: list[str]
    meaning: str

    def __post_init__(self) -> None:
        self.last_interaction_meaning = _enum(
            self.last_interaction_meaning, TemporalMeaning, "temporal meaning"
        )
        self.interaction_frequency_trend = _enum(
            self.interaction_frequency_trend,
            InteractionFrequencyTrend,
            "interaction frequency trend",
        )
        if not isinstance(self.long_silence, bool):
            raise PerceptionValidationError("long_silence must be a boolean")
        self.approaching_important_dates = _text_list(
            self.approaching_important_dates, "approaching important dates"
        )
        _require_text(self.meaning, "temporal meaning summary")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "last_interaction_meaning": self.last_interaction_meaning.value,
            "interaction_frequency_trend": self.interaction_frequency_trend.value,
            "long_silence": self.long_silence,
            "approaching_important_dates": list(self.approaching_important_dates),
            "meaning": self.meaning,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TemporalPerception:
        if not isinstance(value, dict):
            raise PerceptionValidationError("temporal_perception must be an object")
        return cls(
            last_interaction_meaning=value.get("last_interaction_meaning"),
            interaction_frequency_trend=value.get("interaction_frequency_trend"),
            long_silence=value.get("long_silence"),
            approaching_important_dates=_text_list(
                value.get("approaching_important_dates", []),
                "approaching important dates",
            ),
            meaning=value.get("meaning"),
        )


@dataclass(slots=True)
class RelationshipPerception:
    direction: RelationshipDirection
    unfinished_exchange: bool
    sustained_topics: list[str]
    waiting_signal: bool
    observations: list[str]
    summary: str

    def __post_init__(self) -> None:
        self.direction = _enum(
            self.direction, RelationshipDirection, "relationship direction"
        )
        if not isinstance(self.unfinished_exchange, bool) or not isinstance(
            self.waiting_signal, bool
        ):
            raise PerceptionValidationError(
                "relationship flags must be booleans"
            )
        self.sustained_topics = _text_list(
            self.sustained_topics, "relationship sustained_topics"
        )
        self.observations = _text_list(
            self.observations, "relationship observations"
        )
        _require_text(self.summary, "relationship summary")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "direction": self.direction.value,
            "unfinished_exchange": self.unfinished_exchange,
            "sustained_topics": list(self.sustained_topics),
            "waiting_signal": self.waiting_signal,
            "observations": list(self.observations),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RelationshipPerception:
        if not isinstance(value, dict):
            raise PerceptionValidationError("relationship_perception must be an object")
        return cls(
            direction=value.get("direction"),
            unfinished_exchange=value.get("unfinished_exchange"),
            sustained_topics=_text_list(
                value.get("sustained_topics", []), "relationship sustained_topics"
            ),
            waiting_signal=value.get("waiting_signal"),
            observations=_text_list(
                value.get("observations", []), "relationship observations"
            ),
            summary=value.get("summary"),
        )


@dataclass(slots=True)
class MemoryImpact:
    memory_id: str
    recalled_experience: str
    affected_scopes: list[str]
    influence_reason: str
    relevance_score: float

    def __post_init__(self) -> None:
        _require_text(self.memory_id, "memory impact memory_id")
        _require_text(self.recalled_experience, "recalled experience")
        self.affected_scopes = _text_list(
            self.affected_scopes, "memory affected_scopes"
        )
        _require_text(self.influence_reason, "memory influence_reason")
        if not isinstance(self.relevance_score, (int, float)) or not 0 <= float(
            self.relevance_score
        ) <= 1:
            raise PerceptionValidationError(
                "memory relevance_score must be between 0 and 1"
            )
        self.relevance_score = float(self.relevance_score)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "memory_id": self.memory_id,
            "recalled_experience": self.recalled_experience,
            "affected_scopes": list(self.affected_scopes),
            "influence_reason": self.influence_reason,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryImpact:
        if not isinstance(value, dict):
            raise PerceptionValidationError("memory impact must be an object")
        return cls(
            memory_id=value.get("memory_id"),
            recalled_experience=value.get("recalled_experience"),
            affected_scopes=_text_list(
                value.get("affected_scopes", []), "memory affected_scopes"
            ),
            influence_reason=value.get("influence_reason"),
            relevance_score=value.get("relevance_score"),
        )


@dataclass(slots=True)
class MemoryInfluence:
    impacts: list[MemoryImpact]
    summary: str

    def __post_init__(self) -> None:
        if any(not isinstance(item, MemoryImpact) for item in self.impacts):
            raise PerceptionValidationError("memory impacts must contain MemoryImpact")
        _require_text(self.summary, "memory influence summary")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "impacts": [item.to_dict() for item in self.impacts],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryInfluence:
        if not isinstance(value, dict) or not isinstance(value.get("impacts"), list):
            raise PerceptionValidationError("memory_influence must contain impacts")
        return cls(
            impacts=[MemoryImpact.from_dict(item) for item in value["impacts"]],
            summary=value.get("summary"),
        )


@dataclass(slots=True)
class Drive:
    kind: DriveKind
    tendency: str
    source: str
    strength: DriveStrength = DriveStrength.NORMAL

    def __post_init__(self) -> None:
        self.kind = _enum(self.kind, DriveKind, "drive kind")
        self.strength = _enum(self.strength, DriveStrength, "drive strength")
        _require_text(self.tendency, "drive tendency")
        _require_text(self.source, "drive source")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "kind": self.kind.value,
            "tendency": self.tendency,
            "source": self.source,
            "strength": self.strength.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> Drive:
        if not isinstance(value, dict):
            raise PerceptionValidationError("drive must be an object")
        return cls(
            kind=value.get("kind"),
            tendency=value.get("tendency"),
            source=value.get("source"),
            strength=value.get("strength", DriveStrength.NORMAL.value),
        )


@dataclass(slots=True)
class Observation:
    state_stability: StateStability
    major_change: bool
    needs_more_information: bool
    conflicts: list[str]
    notes: list[str]

    def __post_init__(self) -> None:
        self.state_stability = _enum(
            self.state_stability, StateStability, "state stability"
        )
        if not isinstance(self.major_change, bool) or not isinstance(
            self.needs_more_information, bool
        ):
            raise PerceptionValidationError("observation flags must be booleans")
        self.conflicts = _text_list(self.conflicts, "observation conflicts")
        self.notes = _text_list(self.notes, "observation notes")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "state_stability": self.state_stability.value,
            "major_change": self.major_change,
            "needs_more_information": self.needs_more_information,
            "conflicts": list(self.conflicts),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, value: Any) -> Observation:
        if not isinstance(value, dict):
            raise PerceptionValidationError("observation must be an object")
        return cls(
            state_stability=value.get("state_stability"),
            major_change=value.get("major_change"),
            needs_more_information=value.get("needs_more_information"),
            conflicts=_text_list(value.get("conflicts", []), "observation conflicts"),
            notes=_text_list(value.get("notes", []), "observation notes"),
        )


@dataclass(slots=True)
class PerceptionResult:
    perception_id: str
    subject_id: str
    source_revision: int
    wake_session_id: str
    wake_context_id: str
    perceived_at: datetime
    current_focus: CurrentFocus
    temporal_perception: TemporalPerception
    relationship_perception: RelationshipPerception
    memory_influence: MemoryInfluence
    observation: Observation
    internal_drives: list[Drive]
    summary: str
    recent_event_ids: list[str] = field(default_factory=list)
    recent_update_ids: list[str] = field(default_factory=list)
    viewed_memory_ids: list[str] = field(default_factory=list)
    selected_memory_ids: list[str] = field(default_factory=list)
    memory_request_id: str = ""

    def __post_init__(self) -> None:
        _require_text(self.perception_id, "perception_id")
        _require_text(self.subject_id, "perception subject_id")
        _require_text(self.wake_session_id, "perception wake_session_id")
        _require_text(self.wake_context_id, "perception wake_context_id")
        _require_text(self.memory_request_id, "perception memory_request_id")
        if not isinstance(self.source_revision, int) or self.source_revision < 0:
            raise PerceptionValidationError("source_revision must be non-negative")
        if self.perceived_at.tzinfo is None:
            raise PerceptionValidationError("perceived_at must include a timezone")
        if any(not isinstance(item, Drive) for item in self.internal_drives):
            raise PerceptionValidationError("internal_drives must contain Drive values")
        _require_text(self.summary, "perception summary")
        for values, name in (
            (self.recent_event_ids, "recent_event_ids"),
            (self.recent_update_ids, "recent_update_ids"),
            (self.viewed_memory_ids, "viewed_memory_ids"),
            (self.selected_memory_ids, "selected_memory_ids"),
        ):
            normalized = _text_list(values, name)
            setattr(self, name, normalized)

    @classmethod
    def create(
        cls,
        *,
        context: PerceptionContext,
        current_focus: CurrentFocus,
        temporal_perception: TemporalPerception,
        relationship_perception: RelationshipPerception,
        memory_influence: MemoryInfluence,
        observation: Observation,
        internal_drives: Iterable[Drive],
        summary: str,
        perception_id: str | None = None,
    ) -> PerceptionResult:
        memory_result = context.memory_result
        return cls(
            perception_id=perception_id or str(uuid4()),
            subject_id=context.subject_state.subject_id,
            source_revision=context.subject_state.revision,
            wake_session_id=context.wake_session_id,
            wake_context_id=context.wake_context.context_id,
            perceived_at=context.current_time,
            current_focus=current_focus,
            temporal_perception=temporal_perception,
            relationship_perception=relationship_perception,
            memory_influence=memory_influence,
            observation=observation,
            internal_drives=list(internal_drives),
            summary=summary,
            recent_event_ids=[item.event_id for item in context.recent_events],
            recent_update_ids=[
                item.update_id for item in context.wake_context.recent_updates
            ],
            viewed_memory_ids=[
                item.candidate.memory_id for item in memory_result.decisions
            ],
            selected_memory_ids=[
                item.memory_id for item in memory_result.selected_memories
            ],
            memory_request_id=memory_result.request.request_id,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "perception_id": self.perception_id,
            "subject_id": self.subject_id,
            "source_revision": self.source_revision,
            "wake_session_id": self.wake_session_id,
            "wake_context_id": self.wake_context_id,
            "perceived_at": _format_datetime(self.perceived_at),
            "current_focus": self.current_focus.to_dict(),
            "temporal_perception": self.temporal_perception.to_dict(),
            "relationship_perception": self.relationship_perception.to_dict(),
            "memory_influence": self.memory_influence.to_dict(),
            "observation": self.observation.to_dict(),
            "internal_drives": [item.to_dict() for item in self.internal_drives],
            "summary": self.summary,
            "recent_event_ids": list(self.recent_event_ids),
            "recent_update_ids": list(self.recent_update_ids),
            "viewed_memory_ids": list(self.viewed_memory_ids),
            "selected_memory_ids": list(self.selected_memory_ids),
            "memory_request_id": self.memory_request_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> PerceptionResult:
        if not isinstance(value, dict) or not isinstance(
            value.get("internal_drives"), list
        ):
            raise PerceptionValidationError(
                "perception result must contain internal_drives"
            )
        revision = value.get("source_revision")
        if not isinstance(revision, int):
            raise PerceptionValidationError("source_revision must be an integer")
        return cls(
            perception_id=value.get("perception_id"),
            subject_id=value.get("subject_id"),
            source_revision=revision,
            wake_session_id=value.get("wake_session_id"),
            wake_context_id=value.get("wake_context_id"),
            perceived_at=_parse_datetime(value.get("perceived_at"), "perceived_at"),
            current_focus=CurrentFocus.from_dict(value.get("current_focus")),
            temporal_perception=TemporalPerception.from_dict(
                value.get("temporal_perception")
            ),
            relationship_perception=RelationshipPerception.from_dict(
                value.get("relationship_perception")
            ),
            memory_influence=MemoryInfluence.from_dict(
                value.get("memory_influence")
            ),
            observation=Observation.from_dict(value.get("observation")),
            internal_drives=[Drive.from_dict(item) for item in value["internal_drives"]],
            summary=value.get("summary"),
            recent_event_ids=_text_list(
                value.get("recent_event_ids", []), "recent_event_ids"
            ),
            recent_update_ids=_text_list(
                value.get("recent_update_ids", []), "recent_update_ids"
            ),
            viewed_memory_ids=_text_list(
                value.get("viewed_memory_ids", []), "viewed_memory_ids"
            ),
            selected_memory_ids=_text_list(
                value.get("selected_memory_ids", []), "selected_memory_ids"
            ),
            memory_request_id=value.get("memory_request_id"),
        )
