from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .errors import LearningValidationError
from .events import (
    ChangeOperation,
    Event,
    JsonValue,
    StateMutation,
    StateUpdateRecord,
)
from .memory import MemoryInfluenceRecord
from .models import SubjectState
from .perception import PerceptionResult
from .resources import ResourceDecision
from .thinking import ThinkingResult


LEARNABLE_FIELD_PATHS = frozenset(
    {
        "identity.stable_traits",
        "identity.expression_preferences",
        "identity.judgment_principles",
        "relationship.interaction_preferences",
    }
)


class LearningValidationStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class LearningRecordType(str, Enum):
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    CONFIDENCE_ADJUSTED = "CONFIDENCE_ADJUSTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CONSOLIDATED = "CONSOLIDATED"
    ROLLED_BACK = "ROLLED_BACK"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LearningValidationError(f"{field_name} must be a non-empty string")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _confidence(value: Any, field_name: str = "confidence") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LearningValidationError(f"{field_name} must be a number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise LearningValidationError(f"{field_name} must be between zero and one")
    return normalized


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise LearningValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise LearningValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningValidationError(f"{field_name} is not a valid datetime") from exc
    if parsed.tzinfo is None:
        raise LearningValidationError(f"{field_name} must include a timezone")
    return parsed


def _json_value(value: Any, field_name: str) -> JsonValue:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise LearningValidationError(
            f"{field_name} must contain JSON-compatible data"
        ) from exc
    return value


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise LearningValidationError(
            f"{field_name} must be a list of non-empty strings"
        )
    return list(dict.fromkeys(value))


def validate_learning_mutation(mutation: StateMutation) -> None:
    if not isinstance(mutation, StateMutation):
        raise LearningValidationError("proposed_change must be a StateMutation")
    if mutation.field_path not in LEARNABLE_FIELD_PATHS:
        raise LearningValidationError(
            "learning changes are limited to approved long-term characteristic fields"
        )
    if mutation.operation is not ChangeOperation.APPEND:
        raise LearningValidationError(
            "learning candidates may only append one long-term characteristic"
        )
    _require_text(mutation.value, "proposed_change.value")


@dataclass(slots=True)
class LearningEvent:
    learning_id: str
    subject_id: str
    source_event_id: str | None
    source_memory_id: str | None
    related_state_revision: int
    observation: str
    hypothesis: str
    proposed_change: StateMutation
    confidence: float
    validation_status: LearningValidationStatus
    created_at: datetime
    revision: int = 0
    evidence_learning_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.learning_id, "learning_id")
        _require_text(self.subject_id, "learning subject_id")
        self.source_event_id = _optional_text(self.source_event_id, "source_event_id")
        self.source_memory_id = _optional_text(self.source_memory_id, "source_memory_id")
        if self.source_event_id is None and self.source_memory_id is None:
            raise LearningValidationError(
                "a learning candidate requires a source event or source memory"
            )
        if (
            not isinstance(self.related_state_revision, int)
            or self.related_state_revision < 0
        ):
            raise LearningValidationError("related_state_revision must be non-negative")
        _require_text(self.observation, "learning observation")
        _require_text(self.hypothesis, "learning hypothesis")
        validate_learning_mutation(self.proposed_change)
        self.confidence = _confidence(self.confidence)
        try:
            self.validation_status = (
                self.validation_status
                if isinstance(self.validation_status, LearningValidationStatus)
                else LearningValidationStatus(self.validation_status)
            )
        except ValueError as exc:
            raise LearningValidationError("unsupported learning validation status") from exc
        if self.created_at.tzinfo is None:
            raise LearningValidationError("learning created_at must include a timezone")
        if not isinstance(self.revision, int) or self.revision < 0:
            raise LearningValidationError("learning revision must be non-negative")
        self.evidence_learning_ids = _text_list(
            self.evidence_learning_ids, "evidence_learning_ids"
        )

    @property
    def source_identity(self) -> str:
        if self.source_event_id is not None:
            return f"event:{self.source_event_id}"
        assert self.source_memory_id is not None
        return f"memory:{self.source_memory_id}"

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "learning_id": self.learning_id,
            "subject_id": self.subject_id,
            "source_event_id": self.source_event_id,
            "source_memory_id": self.source_memory_id,
            "related_state_revision": self.related_state_revision,
            "observation": self.observation,
            "hypothesis": self.hypothesis,
            "proposed_change": self.proposed_change.to_dict(),
            "confidence": self.confidence,
            "validation_status": self.validation_status.value,
            "created_at": _format_datetime(self.created_at),
            "revision": self.revision,
            "evidence_learning_ids": list(self.evidence_learning_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> LearningEvent:
        if not isinstance(value, dict):
            raise LearningValidationError("learning event must be an object")
        return cls(
            learning_id=value.get("learning_id"),
            subject_id=value.get("subject_id"),
            source_event_id=value.get("source_event_id"),
            source_memory_id=value.get("source_memory_id"),
            related_state_revision=value.get("related_state_revision"),
            observation=value.get("observation"),
            hypothesis=value.get("hypothesis"),
            proposed_change=StateMutation.from_dict(value.get("proposed_change")),
            confidence=value.get("confidence"),
            validation_status=value.get("validation_status"),
            created_at=_parse_datetime(value.get("created_at"), "learning created_at"),
            revision=value.get("revision", 0),
            evidence_learning_ids=_text_list(
                value.get("evidence_learning_ids", []), "evidence_learning_ids"
            ),
        )


@dataclass(slots=True)
class PersonalityTrait:
    trait_id: str
    subject_id: str
    name: str
    description: str
    field_path: str
    current_value: str
    confidence: float
    created_at: datetime
    last_updated_at: datetime
    evidence_count: int
    active: bool = True
    revision: int = 0

    def __post_init__(self) -> None:
        for value, name in (
            (self.trait_id, "trait_id"),
            (self.subject_id, "trait subject_id"),
            (self.name, "trait name"),
            (self.description, "trait description"),
            (self.field_path, "trait field_path"),
            (self.current_value, "trait current_value"),
        ):
            _require_text(value, name)
        if self.field_path not in LEARNABLE_FIELD_PATHS:
            raise LearningValidationError("trait field_path is not learnable")
        self.confidence = _confidence(self.confidence, "trait confidence")
        if self.created_at.tzinfo is None or self.last_updated_at.tzinfo is None:
            raise LearningValidationError("trait timestamps must include a timezone")
        if not isinstance(self.evidence_count, int) or self.evidence_count < 1:
            raise LearningValidationError("trait evidence_count must be positive")
        if not isinstance(self.active, bool):
            raise LearningValidationError("trait active must be a boolean")
        if not isinstance(self.revision, int) or self.revision < 0:
            raise LearningValidationError("trait revision must be non-negative")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "trait_id": self.trait_id,
            "subject_id": self.subject_id,
            "name": self.name,
            "description": self.description,
            "field_path": self.field_path,
            "current_value": self.current_value,
            "confidence": self.confidence,
            "created_at": _format_datetime(self.created_at),
            "last_updated_at": _format_datetime(self.last_updated_at),
            "evidence_count": self.evidence_count,
            "active": self.active,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, value: Any) -> PersonalityTrait:
        if not isinstance(value, dict):
            raise LearningValidationError("personality trait must be an object")
        return cls(
            trait_id=value.get("trait_id"),
            subject_id=value.get("subject_id"),
            name=value.get("name"),
            description=value.get("description"),
            field_path=value.get("field_path"),
            current_value=value.get("current_value"),
            confidence=value.get("confidence"),
            created_at=_parse_datetime(value.get("created_at"), "trait created_at"),
            last_updated_at=_parse_datetime(
                value.get("last_updated_at"), "trait last_updated_at"
            ),
            evidence_count=value.get("evidence_count"),
            active=value.get("active", True),
            revision=value.get("revision", 0),
        )


@dataclass(slots=True)
class LearningRecord:
    record_id: str
    learning_id: str
    subject_id: str
    record_type: LearningRecordType
    original_experience: JsonValue
    observation: str
    hypothesis: str
    validation_status: LearningValidationStatus
    permanently_consolidated: bool
    field_path: str
    before_value: JsonValue
    after_value: JsonValue
    reason: str
    source: str
    created_at: datetime
    evidence_learning_ids: list[str] = field(default_factory=list)
    trait_id: str | None = None
    state_event_id: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.record_id, "learning record_id"),
            (self.learning_id, "record learning_id"),
            (self.subject_id, "record subject_id"),
            (self.field_path, "record field_path"),
            (self.observation, "record observation"),
            (self.hypothesis, "record hypothesis"),
            (self.reason, "learning record reason"),
            (self.source, "learning record source"),
        ):
            _require_text(value, name)
        try:
            self.record_type = (
                self.record_type
                if isinstance(self.record_type, LearningRecordType)
                else LearningRecordType(self.record_type)
            )
            self.validation_status = (
                self.validation_status
                if isinstance(self.validation_status, LearningValidationStatus)
                else LearningValidationStatus(self.validation_status)
            )
        except ValueError as exc:
            raise LearningValidationError("unsupported learning record state") from exc
        if self.field_path not in LEARNABLE_FIELD_PATHS:
            raise LearningValidationError("learning record field_path is not learnable")
        self.original_experience = _json_value(
            self.original_experience, "original_experience"
        )
        self.before_value = _json_value(self.before_value, "before_value")
        self.after_value = _json_value(self.after_value, "after_value")
        if not isinstance(self.permanently_consolidated, bool):
            raise LearningValidationError("permanently_consolidated must be a boolean")
        if self.created_at.tzinfo is None:
            raise LearningValidationError("record created_at must include a timezone")
        self.evidence_learning_ids = _text_list(
            self.evidence_learning_ids, "record evidence_learning_ids"
        )
        self.trait_id = _optional_text(self.trait_id, "record trait_id")
        self.state_event_id = _optional_text(
            self.state_event_id, "record state_event_id"
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "record_id": self.record_id,
            "learning_id": self.learning_id,
            "subject_id": self.subject_id,
            "record_type": self.record_type.value,
            "original_experience": self.original_experience,
            "observation": self.observation,
            "hypothesis": self.hypothesis,
            "validation_status": self.validation_status.value,
            "permanently_consolidated": self.permanently_consolidated,
            "field_path": self.field_path,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "reason": self.reason,
            "source": self.source,
            "created_at": _format_datetime(self.created_at),
            "evidence_learning_ids": list(self.evidence_learning_ids),
            "trait_id": self.trait_id,
            "state_event_id": self.state_event_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> LearningRecord:
        if not isinstance(value, dict):
            raise LearningValidationError("learning record must be an object")
        return cls(
            record_id=value.get("record_id"),
            learning_id=value.get("learning_id"),
            subject_id=value.get("subject_id"),
            record_type=value.get("record_type"),
            original_experience=value.get("original_experience"),
            observation=value.get("observation"),
            hypothesis=value.get("hypothesis"),
            validation_status=value.get("validation_status"),
            permanently_consolidated=value.get("permanently_consolidated"),
            field_path=value.get("field_path"),
            before_value=value.get("before_value"),
            after_value=value.get("after_value"),
            reason=value.get("reason"),
            source=value.get("source"),
            created_at=_parse_datetime(value.get("created_at"), "record created_at"),
            evidence_learning_ids=_text_list(
                value.get("evidence_learning_ids", []),
                "record evidence_learning_ids",
            ),
            trait_id=value.get("trait_id"),
            state_event_id=value.get("state_event_id"),
        )


@dataclass(slots=True)
class LearningContext:
    context_id: str
    subject_state: SubjectState
    recent_events: list[Event]
    memory_influences: list[MemoryInfluenceRecord]
    perception_result: PerceptionResult
    thinking_result: ThinkingResult
    created_at: datetime
    recent_state_updates: list[StateUpdateRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.context_id, "learning context_id")
        if not isinstance(self.subject_state, SubjectState):
            raise LearningValidationError("LearningContext requires SubjectState")
        subject_id = self.subject_state.subject_id
        if any(not isinstance(item, Event) for item in self.recent_events):
            raise LearningValidationError("recent_events must contain Event values")
        if any(
            not isinstance(item, MemoryInfluenceRecord)
            or item.subject_id != subject_id
            for item in self.memory_influences
        ):
            raise LearningValidationError(
                "memory influences must belong to the learning subject"
            )
        if (
            not isinstance(self.perception_result, PerceptionResult)
            or self.perception_result.subject_id != subject_id
        ):
            raise LearningValidationError("perception does not match learning subject")
        if self.perception_result.source_revision != self.subject_state.revision:
            raise LearningValidationError(
                "perception revision does not match learning SubjectState"
            )
        if not isinstance(self.thinking_result, ThinkingResult):
            raise LearningValidationError("LearningContext requires ThinkingResult")
        if any(
            not isinstance(item, StateUpdateRecord) or item.subject_id != subject_id
            for item in self.recent_state_updates
        ):
            raise LearningValidationError(
                "recent state updates must belong to the learning subject"
            )
        if self.created_at.tzinfo is None:
            raise LearningValidationError("learning context time must include a timezone")

    @property
    def subject_id(self) -> str:
        return self.subject_state.subject_id

    @classmethod
    def create(
        cls,
        *,
        subject_state: SubjectState,
        recent_events: list[Event],
        memory_influences: list[MemoryInfluenceRecord],
        perception_result: PerceptionResult,
        thinking_result: ThinkingResult,
        created_at: datetime,
        recent_state_updates: list[StateUpdateRecord] | None = None,
        context_id: str | None = None,
    ) -> LearningContext:
        return cls(
            context_id=context_id or str(uuid4()),
            subject_state=subject_state,
            recent_events=list(recent_events),
            memory_influences=list(memory_influences),
            perception_result=perception_result,
            thinking_result=thinking_result,
            created_at=created_at,
            recent_state_updates=list(recent_state_updates or []),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "context_id": self.context_id,
            "subject_state": self.subject_state.to_dict(),
            "recent_events": [item.to_dict() for item in self.recent_events],
            "memory_influences": [item.to_dict() for item in self.memory_influences],
            "perception_result": self.perception_result.to_dict(),
            "thinking_result": self.thinking_result.to_dict(),
            "created_at": _format_datetime(self.created_at),
            "recent_state_updates": [
                item.to_dict() for item in self.recent_state_updates
            ],
        }

    @classmethod
    def from_dict(cls, value: Any) -> LearningContext:
        if not isinstance(value, dict):
            raise LearningValidationError("learning context must be an object")
        collections = (
            "recent_events",
            "memory_influences",
            "recent_state_updates",
        )
        if any(not isinstance(value.get(name, []), list) for name in collections):
            raise LearningValidationError("learning context collections are invalid")
        return cls(
            context_id=value.get("context_id"),
            subject_state=SubjectState.from_dict(value.get("subject_state")),
            recent_events=[Event.from_dict(item) for item in value.get("recent_events", [])],
            memory_influences=[
                MemoryInfluenceRecord.from_dict(item)
                for item in value.get("memory_influences", [])
            ],
            perception_result=PerceptionResult.from_dict(value.get("perception_result")),
            thinking_result=ThinkingResult.from_dict(value.get("thinking_result")),
            created_at=_parse_datetime(value.get("created_at"), "context created_at"),
            recent_state_updates=[
                StateUpdateRecord.from_dict(item)
                for item in value.get("recent_state_updates", [])
            ],
        )


@dataclass(slots=True)
class LearningResult:
    candidates: list[LearningEvent]
    suggested_changes: list[StateMutation]
    confidence: float
    resource_decision: ResourceDecision | None = None

    def __post_init__(self) -> None:
        if any(not isinstance(item, LearningEvent) for item in self.candidates):
            raise LearningValidationError("candidates must contain LearningEvent values")
        if any(not isinstance(item, StateMutation) for item in self.suggested_changes):
            raise LearningValidationError(
                "suggested_changes must contain StateMutation values"
            )
        self.confidence = _confidence(self.confidence, "learning result confidence")
        if self.resource_decision is not None and not isinstance(
            self.resource_decision, ResourceDecision
        ):
            raise LearningValidationError(
                "resource_decision must be a ResourceDecision or null"
            )

    @property
    def deferred(self) -> bool:
        return self.resource_decision is not None and self.resource_decision.defer


@dataclass(slots=True)
class LearningCandidateResult:
    learning_event: LearningEvent
    record: LearningRecord


@dataclass(slots=True)
class LearningChangeResult:
    learning_event: LearningEvent
    record: LearningRecord
    trait: PersonalityTrait | None = None
    event: Event | None = None
