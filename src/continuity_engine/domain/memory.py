from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .errors import MemoryValidationError
from .events import JsonValue, StateSection


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryValidationError(f"{field_name} must be a non-empty string")
    return value


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise MemoryValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise MemoryValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryValidationError(f"{field_name} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise MemoryValidationError(f"{field_name} must include a timezone")
    return parsed


def _json_object(value: Any, field_name: str) -> dict[str, JsonValue]:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise MemoryValidationError(f"{field_name} must be an object with string keys")
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise MemoryValidationError(f"{field_name} must contain JSON-compatible data") from exc
    return dict(value)


def _sections(value: Iterable[StateSection | str], field_name: str) -> list[StateSection]:
    result: list[StateSection] = []
    for item in value:
        try:
            section = item if isinstance(item, StateSection) else StateSection(item)
        except ValueError as exc:
            raise MemoryValidationError(f"{field_name} contains an unsupported section") from exc
        if section not in result:
            result.append(section)
    return result


def _text_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MemoryValidationError(f"{field_name} must be a list of strings")
    return list(value)


@dataclass(slots=True)
class MemoryRetrievalRequest:
    request_id: str
    subject_id: str
    query: str
    requested_at: datetime
    desired_scope: list[StateSection] = field(default_factory=list)
    limit: int = 5
    minimum_relevance: float = 0.5
    context: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.subject_id, "subject_id")
        _require_text(self.query, "query")
        if self.requested_at.tzinfo is None:
            raise MemoryValidationError("requested_at must include a timezone")
        self.desired_scope = _sections(self.desired_scope, "desired_scope")
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise MemoryValidationError("limit must be an integer between 1 and 100")
        if not isinstance(self.minimum_relevance, (int, float)) or not 0 <= float(
            self.minimum_relevance
        ) <= 1:
            raise MemoryValidationError("minimum_relevance must be between 0 and 1")
        self.minimum_relevance = float(self.minimum_relevance)
        self.context = _json_object(self.context, "context")

    @classmethod
    def create(
        cls,
        *,
        subject_id: str,
        query: str,
        requested_at: datetime,
        desired_scope: Iterable[StateSection] = (),
        limit: int = 5,
        minimum_relevance: float = 0.5,
        context: dict[str, JsonValue] | None = None,
        request_id: str | None = None,
    ) -> MemoryRetrievalRequest:
        return cls(
            request_id=request_id or str(uuid4()),
            subject_id=subject_id,
            query=query,
            requested_at=requested_at,
            desired_scope=list(desired_scope),
            limit=limit,
            minimum_relevance=minimum_relevance,
            context=dict(context or {}),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "query": self.query,
            "requested_at": _format_datetime(self.requested_at),
            "desired_scope": [section.value for section in self.desired_scope],
            "limit": self.limit,
            "minimum_relevance": self.minimum_relevance,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryRetrievalRequest:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory retrieval request must be an object")
        raw_scope = value.get("desired_scope", [])
        if not isinstance(raw_scope, list):
            raise MemoryValidationError("desired_scope must be a list")
        return cls(
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            query=value.get("query"),
            requested_at=_parse_datetime(value.get("requested_at"), "requested_at"),
            desired_scope=raw_scope,
            limit=value.get("limit", 5),
            minimum_relevance=value.get("minimum_relevance", 0.5),
            context=_json_object(value.get("context", {}), "context"),
        )


@dataclass(slots=True)
class MemoryCandidate:
    memory_id: str
    subject_id: str
    content: str
    source: str
    occurred_at: datetime | None
    provider_relevance: float
    related_scope: list[StateSection] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.memory_id, "memory_id")
        _require_text(self.subject_id, "memory.subject_id")
        _require_text(self.content, "memory.content")
        _require_text(self.source, "memory.source")
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise MemoryValidationError("memory.occurred_at must include a timezone")
        if not isinstance(self.provider_relevance, (int, float)) or not 0 <= float(
            self.provider_relevance
        ) <= 1:
            raise MemoryValidationError("provider_relevance must be between 0 and 1")
        self.provider_relevance = float(self.provider_relevance)
        self.related_scope = _sections(self.related_scope, "related_scope")
        self.tags = _text_list(self.tags, "tags")
        self.metadata = _json_object(self.metadata, "metadata")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "memory_id": self.memory_id,
            "subject_id": self.subject_id,
            "content": self.content,
            "source": self.source,
            "occurred_at": _format_datetime(self.occurred_at) if self.occurred_at else None,
            "provider_relevance": self.provider_relevance,
            "related_scope": [section.value for section in self.related_scope],
            "tags": list(self.tags),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryCandidate:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory candidate must be an object")
        raw_scope = value.get("related_scope", [])
        if not isinstance(raw_scope, list):
            raise MemoryValidationError("related_scope must be a list")
        occurred_at = value.get("occurred_at")
        return cls(
            memory_id=value.get("memory_id"),
            subject_id=value.get("subject_id"),
            content=value.get("content"),
            source=value.get("source"),
            occurred_at=(
                _parse_datetime(occurred_at, "memory.occurred_at")
                if occurred_at is not None
                else None
            ),
            provider_relevance=value.get("provider_relevance"),
            related_scope=raw_scope,
            tags=_text_list(value.get("tags", []), "tags"),
            metadata=_json_object(value.get("metadata", {}), "metadata"),
        )


@dataclass(slots=True)
class MemoryRelevanceDecision:
    candidate: MemoryCandidate
    relevant: bool
    relevance_score: float
    reasons: list[str]
    selected: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.relevant, bool) or not isinstance(self.selected, bool):
            raise MemoryValidationError("relevant and selected must be booleans")
        if not 0 <= self.relevance_score <= 1:
            raise MemoryValidationError("relevance_score must be between 0 and 1")
        self.reasons = _text_list(self.reasons, "relevance reasons")
        if not self.reasons:
            raise MemoryValidationError("a relevance decision must explain its reasons")
        if self.selected and not self.relevant:
            raise MemoryValidationError("an irrelevant memory cannot be selected")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "candidate": self.candidate.to_dict(),
            "relevant": self.relevant,
            "relevance_score": self.relevance_score,
            "reasons": list(self.reasons),
            "selected": self.selected,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryRelevanceDecision:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory relevance decision must be an object")
        return cls(
            candidate=MemoryCandidate.from_dict(value.get("candidate")),
            relevant=value.get("relevant"),
            relevance_score=value.get("relevance_score"),
            reasons=_text_list(value.get("reasons"), "relevance reasons"),
            selected=value.get("selected", False),
        )


@dataclass(slots=True)
class MemoryRetrievalResult:
    request: MemoryRetrievalRequest
    evaluated_at: datetime
    decisions: list[MemoryRelevanceDecision]

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None:
            raise MemoryValidationError("evaluated_at must include a timezone")
        if any(not isinstance(item, MemoryRelevanceDecision) for item in self.decisions):
            raise MemoryValidationError("decisions must contain relevance decisions")

    @property
    def selected_memories(self) -> list[MemoryCandidate]:
        return [decision.candidate for decision in self.decisions if decision.selected]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request": self.request.to_dict(),
            "evaluated_at": _format_datetime(self.evaluated_at),
            "decisions": [decision.to_dict() for decision in self.decisions],
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryRetrievalResult:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory retrieval result must be an object")
        raw_decisions = value.get("decisions")
        if not isinstance(raw_decisions, list):
            raise MemoryValidationError("decisions must be a list")
        return cls(
            request=MemoryRetrievalRequest.from_dict(value.get("request")),
            evaluated_at=_parse_datetime(value.get("evaluated_at"), "evaluated_at"),
            decisions=[MemoryRelevanceDecision.from_dict(item) for item in raw_decisions],
        )


@dataclass(slots=True)
class MemoryInfluenceRecord:
    influence_id: str
    request_id: str
    subject_id: str
    memory_id: str
    recorded_at: datetime
    influence_type: str
    summary: str
    reason: str
    affected_fields: list[str] = field(default_factory=list)
    related_event_id: str | None = None
    related_update_id: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.influence_id, "influence_id")
        _require_text(self.request_id, "influence.request_id")
        _require_text(self.subject_id, "influence.subject_id")
        _require_text(self.memory_id, "influence.memory_id")
        if self.recorded_at.tzinfo is None:
            raise MemoryValidationError("recorded_at must include a timezone")
        _require_text(self.influence_type, "influence_type")
        _require_text(self.summary, "influence.summary")
        _require_text(self.reason, "influence.reason")
        self.affected_fields = _text_list(self.affected_fields, "affected_fields")
        if self.related_event_id is not None:
            _require_text(self.related_event_id, "related_event_id")
        if self.related_update_id is not None:
            _require_text(self.related_update_id, "related_update_id")
        self.metadata = _json_object(self.metadata, "metadata")

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        subject_id: str,
        memory_id: str,
        recorded_at: datetime,
        influence_type: str,
        summary: str,
        reason: str,
        affected_fields: Iterable[str] = (),
        related_event_id: str | None = None,
        related_update_id: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
        influence_id: str | None = None,
    ) -> MemoryInfluenceRecord:
        return cls(
            influence_id=influence_id or str(uuid4()),
            request_id=request_id,
            subject_id=subject_id,
            memory_id=memory_id,
            recorded_at=recorded_at,
            influence_type=influence_type,
            summary=summary,
            reason=reason,
            affected_fields=list(dict.fromkeys(affected_fields)),
            related_event_id=related_event_id,
            related_update_id=related_update_id,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "influence_id": self.influence_id,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "memory_id": self.memory_id,
            "recorded_at": _format_datetime(self.recorded_at),
            "influence_type": self.influence_type,
            "summary": self.summary,
            "reason": self.reason,
            "affected_fields": list(self.affected_fields),
            "related_event_id": self.related_event_id,
            "related_update_id": self.related_update_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryInfluenceRecord:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory influence record must be an object")
        return cls(
            influence_id=value.get("influence_id"),
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            memory_id=value.get("memory_id"),
            recorded_at=_parse_datetime(value.get("recorded_at"), "recorded_at"),
            influence_type=value.get("influence_type"),
            summary=value.get("summary"),
            reason=value.get("reason"),
            affected_fields=_text_list(value.get("affected_fields", []), "affected_fields"),
            related_event_id=value.get("related_event_id"),
            related_update_id=value.get("related_update_id"),
            metadata=_json_object(value.get("metadata", {}), "metadata"),
        )


class MemoryRelevancePolicy:
    """Deterministic relevance checks around scores supplied by a memory provider."""

    def evaluate(
        self,
        request: MemoryRetrievalRequest,
        candidate: MemoryCandidate,
    ) -> MemoryRelevanceDecision:
        reasons: list[str] = []
        relevant = True

        if candidate.subject_id != request.subject_id:
            relevant = False
            reasons.append("The memory belongs to a different subject.")

        if candidate.occurred_at is not None and candidate.occurred_at > request.requested_at:
            relevant = False
            reasons.append("The memory occurs after the retrieval request time.")

        requested_scope = set(request.desired_scope)
        candidate_scope = set(candidate.related_scope)
        if requested_scope and candidate_scope and requested_scope.isdisjoint(candidate_scope):
            relevant = False
            reasons.append("The memory does not overlap the requested state scope.")
        elif requested_scope and candidate_scope:
            reasons.append("The memory overlaps the requested state scope.")
        elif requested_scope:
            reasons.append("The provider did not declare a state scope for this memory.")

        if candidate.provider_relevance < request.minimum_relevance:
            relevant = False
            reasons.append("The provider relevance score is below the request threshold.")
        else:
            reasons.append("The provider relevance score meets the request threshold.")

        return MemoryRelevanceDecision(
            candidate=candidate,
            relevant=relevant,
            relevance_score=candidate.provider_relevance,
            reasons=reasons,
        )


class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    RELATIONAL = "relational"


class MemoryEvidenceType(str, Enum):
    EXPERIENTIAL = "experiential"
    ANALYTICAL = "analytical"
    EXTERNAL = "external"


class MemoryTemperature(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    ARCHIVED = "ARCHIVED"


class MemoryVisibility(str, Enum):
    ENGINE_PRIVATE = "ENGINE_PRIVATE"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CORRECTED = "CORRECTED"
    REVOKED = "REVOKED"
    DELETED = "DELETED"


class MemoryLineageType(str, Enum):
    CORRECTION = "CORRECTION"
    REVOCATION = "REVOCATION"
    DELETION = "DELETION"


class MemoryLifecycle(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MemoryLifecycleSignal(str, Enum):
    COMMAND = 'LIFECYCLE'


class DerivedSummaryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


def _enum_value(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        raise MemoryValidationError(f"{field_name} is unsupported") from exc


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise MemoryValidationError(f"{field_name} must include a timezone")
    return value.astimezone(timezone.utc)


def _optional_utc(value: datetime | None, field_name: str) -> datetime | None:
    return None if value is None else _utc(value, field_name)


def _ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemoryValidationError(f"{field_name} must be a number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise MemoryValidationError(f"{field_name} must be between zero and one")
    return normalized


def _unique_texts(value: Iterable[str], field_name: str, *, required: bool = False) -> list[str]:
    if isinstance(value, (str, bytes)):
        raise MemoryValidationError(f"{field_name} must be a list of strings")
    items = list(value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise MemoryValidationError(f"{field_name} must contain non-empty strings")
    if len(set(items)) != len(items):
        raise MemoryValidationError(f"{field_name} must not contain duplicates")
    if required and not items:
        raise MemoryValidationError(f"{field_name} must not be empty")
    return items


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


@dataclass(slots=True)
class MemoryTimeRange:
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        self.start_at = _utc(self.start_at, "time_range.start_at")
        self.end_at = _utc(self.end_at, "time_range.end_at")
        if self.end_at < self.start_at:
            raise MemoryValidationError("time_range.end_at cannot precede start_at")

    def to_dict(self) -> dict[str, str]:
        return {
            "start_at": _format_datetime(self.start_at),
            "end_at": _format_datetime(self.end_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryTimeRange:
        if not isinstance(value, dict):
            raise MemoryValidationError("time_range must be an object")
        return cls(
            _parse_datetime(value.get("start_at"), "time_range.start_at"),
            _parse_datetime(value.get("end_at"), "time_range.end_at"),
        )


@dataclass(slots=True)
class MemoryRecord:
    memory_id: str
    subject_id: str
    environment: str
    kind: MemoryKind
    evidence_type: MemoryEvidenceType
    content: str
    root_evidence_ids: list[str]
    occurred_at: datetime
    observed_at: datetime
    recorded_at: datetime
    consolidated_at: datetime
    confidence: float
    importance: float
    activation: float
    scope: str
    time_range: MemoryTimeRange
    consolidation_id: str
    source_event_ids: list[str] = field(default_factory=list)
    source_memory_ids: list[str] = field(default_factory=list)
    source_message_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    temperature: MemoryTemperature = MemoryTemperature.HOT
    visibility: MemoryVisibility = MemoryVisibility.ENGINE_PRIVATE
    status: MemoryStatus = MemoryStatus.ACTIVE
    revision: int = 0
    memory_version: int = 1
    access_count: int = 0
    last_accessed_at: datetime | None = None
    relation_relevance: float = 0.0
    emotional_weight: float = 0.0
    activation_explanation: list[str] = field(default_factory=list)
    lineage_event_id: str | None = None
    consolidation_input_hash: str | None = None
    lifecycle: MemoryLifecycle | None = None
    retrieval_weight: float | None = None
    weight_updated_at: datetime | None = None
    lifecycle_command_id: str | None = None
    source_memory_bindings: dict[str, str] | None = None
    historical_only: bool = field(default=False,repr=False,compare=False)
    consumption_weight: float | None = field(default=None,repr=False,compare=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.memory_id, "memory_id"),
            (self.subject_id, "memory subject_id"),
            (self.environment, "memory environment"),
            (self.content, "memory content"),
            (self.scope, "memory scope"),
            (self.consolidation_id, "consolidation_id"),
        ):
            _require_text(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise MemoryValidationError("memory environment is unsupported")
        self.kind = _enum_value(self.kind, MemoryKind, "memory kind")  # type: ignore[assignment]
        self.evidence_type = _enum_value(  # type: ignore[assignment]
            self.evidence_type, MemoryEvidenceType, "memory evidence_type"
        )
        self.temperature = _enum_value(  # type: ignore[assignment]
            self.temperature, MemoryTemperature, "memory temperature"
        )
        self.visibility = _enum_value(  # type: ignore[assignment]
            self.visibility, MemoryVisibility, "memory visibility"
        )
        self.status = _enum_value(self.status, MemoryStatus, "memory status")  # type: ignore[assignment]
        if self.lifecycle is not None:
            self.lifecycle = _enum_value(self.lifecycle, MemoryLifecycle, "memory lifecycle")
        if self.retrieval_weight is not None:
            self.retrieval_weight = _ratio(self.retrieval_weight, "retrieval weight")
        self.weight_updated_at = _optional_utc(self.weight_updated_at, "weight_updated_at")
        if self.lifecycle_command_id is not None:
            _require_text(self.lifecycle_command_id, "lifecycle_command_id")
        if self.source_memory_bindings is not None:
            if (not isinstance(self.source_memory_bindings,dict)
                    or set(self.source_memory_bindings)!=set(self.source_memory_ids)
                    or any(not isinstance(h,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',h) for h in self.source_memory_bindings.values())):
                raise MemoryValidationError('source memory version bindings invalid')
        self.root_evidence_ids = _unique_texts(
            self.root_evidence_ids, "root_evidence_ids", required=True
        )
        self.source_event_ids = _unique_texts(self.source_event_ids, "source_event_ids")
        self.source_memory_ids = _unique_texts(self.source_memory_ids, "source_memory_ids")
        self.source_message_ids = _unique_texts(
            self.source_message_ids, "source_message_ids"
        )
        if not (self.source_event_ids or self.source_memory_ids or self.source_message_ids):
            raise MemoryValidationError("a memory requires a non-empty source chain")
        if self.memory_id in self.source_memory_ids:
            raise MemoryValidationError("a memory cannot source itself")
        self.tags = _unique_texts(self.tags, "memory tags")
        self.activation_explanation = _unique_texts(
            self.activation_explanation, "activation_explanation"
        )
        self.occurred_at = _utc(self.occurred_at, "memory occurred_at")
        self.observed_at = _utc(self.observed_at, "memory observed_at")
        self.recorded_at = _utc(self.recorded_at, "memory recorded_at")
        self.consolidated_at = _utc(self.consolidated_at, "memory consolidated_at")
        self.last_accessed_at = _optional_utc(
            self.last_accessed_at, "memory last_accessed_at"
        )
        if not (
            self.occurred_at
            <= self.observed_at
            <= self.recorded_at
            <= self.consolidated_at
        ):
            raise MemoryValidationError("memory times must be monotonic")
        self.confidence = _ratio(self.confidence, "memory confidence")
        self.importance = _ratio(self.importance, "memory importance")
        self.activation = _ratio(self.activation, "memory activation")
        self.relation_relevance = _ratio(
            self.relation_relevance, "memory relation_relevance"
        )
        self.emotional_weight = _ratio(
            self.emotional_weight, "memory emotional_weight"
        )
        if not isinstance(self.time_range, MemoryTimeRange):
            raise MemoryValidationError("time_range must be a MemoryTimeRange")
        if self.time_range.start_at > self.occurred_at or self.time_range.end_at < self.occurred_at:
            raise MemoryValidationError("memory occurred_at must fall within time_range")
        if not isinstance(self.revision, int) or self.revision < 0:
            raise MemoryValidationError("memory revision must be non-negative")
        if not isinstance(self.memory_version, int) or self.memory_version != self.revision + 1:
            raise MemoryValidationError("memory_version must equal revision + 1")
        if not isinstance(self.access_count, int) or self.access_count < 0:
            raise MemoryValidationError("memory access_count must be non-negative")
        if self.lineage_event_id is not None:
            _require_text(self.lineage_event_id, "lineage_event_id")
        if self.status is not MemoryStatus.ACTIVE and self.lineage_event_id is None:
            raise MemoryValidationError("inactive memory requires lineage_event_id")
        if self.consolidation_input_hash is None:
            self.consolidation_input_hash = self.consolidation_hash()
        elif not re.fullmatch(r"sha256:[0-9a-f]{64}", self.consolidation_input_hash):
            raise MemoryValidationError("consolidation_input_hash must be a SHA-256 value")

    @property
    def unique_evidence_count(self) -> int:
        return len(self.root_evidence_ids)

    @property
    def effective_lifecycle(self) -> MemoryLifecycle:
        if self.status is MemoryStatus.DELETED:
            return MemoryLifecycle.DELETED
        if self.lifecycle is not None:
            return self.lifecycle
        if self.status is not MemoryStatus.ACTIVE:
            return MemoryLifecycle.INACTIVE
        return (MemoryLifecycle.ARCHIVED if self.temperature is MemoryTemperature.ARCHIVED
                else MemoryLifecycle.ACTIVE)

    @property
    def effective_weight(self) -> float:
        own=1.0 if self.retrieval_weight is None else self.retrieval_weight
        return own if self.consumption_weight is None else min(own,self.consumption_weight)

    @property
    def is_available(self) -> bool:
        return (not self.historical_only and self.status is MemoryStatus.ACTIVE
                and self.effective_lifecycle is MemoryLifecycle.ACTIVE
                and self.effective_weight > 0)

    def to_dict(self) -> dict[str, JsonValue]:
        body = {
            "memory_id": self.memory_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "kind": self.kind.value,
            "evidence_type": self.evidence_type.value,
            "content": self.content,
            "root_evidence_ids": list(self.root_evidence_ids),
            "source_event_ids": list(self.source_event_ids),
            "source_memory_ids": list(self.source_memory_ids),
            "source_message_ids": list(self.source_message_ids),
            "occurred_at": _format_datetime(self.occurred_at),
            "observed_at": _format_datetime(self.observed_at),
            "recorded_at": _format_datetime(self.recorded_at),
            "consolidated_at": _format_datetime(self.consolidated_at),
            "confidence": self.confidence,
            "importance": self.importance,
            "activation": self.activation,
            "scope": self.scope,
            "time_range": self.time_range.to_dict(),
            "tags": list(self.tags),
            "temperature": self.temperature.value,
            "visibility": self.visibility.value,
            "status": self.status.value,
            "revision": self.revision,
            "memory_version": self.memory_version,
            "access_count": self.access_count,
            "last_accessed_at": (
                _format_datetime(self.last_accessed_at) if self.last_accessed_at else None
            ),
            "relation_relevance": self.relation_relevance,
            "emotional_weight": self.emotional_weight,
            "activation_explanation": list(self.activation_explanation),
            "consolidation_id": self.consolidation_id,
            "consolidation_input_hash": self.consolidation_input_hash,
            "lineage_event_id": self.lineage_event_id,
        }
        # Omit P12 fields on genuinely old records: canonical identities survive.
        if self.lifecycle is not None:
            body['lifecycle'] = self.lifecycle.value
        if self.retrieval_weight is not None:
            body['retrieval_weight'] = self.retrieval_weight
        if self.weight_updated_at is not None:
            body['weight_updated_at'] = _format_datetime(self.weight_updated_at)
        if self.lifecycle_command_id is not None:
            body['lifecycle_command_id'] = self.lifecycle_command_id
        if self.source_memory_bindings is not None:
            body['source_memory_bindings'] = dict(self.source_memory_bindings)
        return body

    @classmethod
    def from_dict(cls, value: Any) -> MemoryRecord:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory record must be an object")
        last_accessed_at = value.get("last_accessed_at")
        return cls(
            memory_id=value.get("memory_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            kind=value.get("kind"),
            evidence_type=value.get("evidence_type"),
            content=value.get("content"),
            root_evidence_ids=_text_list(value.get("root_evidence_ids"), "root_evidence_ids"),
            source_event_ids=_text_list(value.get("source_event_ids", []), "source_event_ids"),
            source_memory_ids=_text_list(value.get("source_memory_ids", []), "source_memory_ids"),
            source_message_ids=_text_list(value.get("source_message_ids", []), "source_message_ids"),
            occurred_at=_parse_datetime(value.get("occurred_at"), "memory occurred_at"),
            observed_at=_parse_datetime(value.get("observed_at"), "memory observed_at"),
            recorded_at=_parse_datetime(value.get("recorded_at"), "memory recorded_at"),
            consolidated_at=_parse_datetime(
                value.get("consolidated_at"), "memory consolidated_at"
            ),
            confidence=value.get("confidence"),
            importance=value.get("importance"),
            activation=value.get("activation"),
            scope=value.get("scope"),
            time_range=MemoryTimeRange.from_dict(value.get("time_range")),
            tags=_text_list(value.get("tags", []), "memory tags"),
            temperature=value.get("temperature"),
            visibility=value.get("visibility"),
            status=value.get("status"),
            revision=value.get("revision"),
            memory_version=value.get("memory_version"),
            access_count=value.get("access_count", 0),
            last_accessed_at=(
                _parse_datetime(last_accessed_at, "memory last_accessed_at")
                if last_accessed_at is not None
                else None
            ),
            relation_relevance=value.get("relation_relevance", 0.0),
            emotional_weight=value.get("emotional_weight", 0.0),
            activation_explanation=_text_list(
                value.get("activation_explanation", []), "activation_explanation"
            ),
            consolidation_id=value.get("consolidation_id"),
            consolidation_input_hash=value.get("consolidation_input_hash"),
            lineage_event_id=value.get("lineage_event_id"),
            lifecycle=value.get('lifecycle'), retrieval_weight=value.get('retrieval_weight'),
            weight_updated_at=(_parse_datetime(value['weight_updated_at'], 'weight_updated_at')
                               if value.get('weight_updated_at') is not None else None),
            lifecycle_command_id=value.get('lifecycle_command_id'),
            source_memory_bindings=value.get('source_memory_bindings'),
        )

    def canonical_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def consolidation_hash(self) -> str:
        body = self.to_dict()
        for field_name in (
            "revision",
            "memory_version",
            "activation",
            "temperature",
            "access_count",
            "last_accessed_at",
            "activation_explanation",
            "lineage_event_id",
            "status",
            "consolidation_input_hash",
            "lifecycle", "retrieval_weight", "weight_updated_at", "lifecycle_command_id",
            "source_memory_bindings",
        ):
            body.pop(field_name, None)
        return _canonical_hash(body)


@dataclass(slots=True)
class MemoryConsolidationOperation:
    """Durable idempotency identity inside the single P04 Memory authority."""

    consolidation_id: str
    subject_id: str
    environment: str
    canonical_input_hash: str
    canonical_input: dict[str, JsonValue]
    result_memory_id: str
    result_memory_revision: int
    result_memory_canonical_hash: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.consolidation_id, "operation consolidation_id"),
            (self.subject_id, "operation subject_id"),
            (self.environment, "operation environment"),
            (self.result_memory_id, "operation result_memory_id"),
        ):
            _require_text(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise MemoryValidationError("operation environment is unsupported")
        if not isinstance(self.canonical_input_hash, str) or re.fullmatch(
            r"sha256:[0-9a-f]{64}", self.canonical_input_hash
        ) is None:
            raise MemoryValidationError(
                "operation canonical_input_hash must be a SHA-256 value"
            )
        if (
            not isinstance(self.result_memory_revision, int)
            or isinstance(self.result_memory_revision, bool)
            or self.result_memory_revision < 0
        ):
            raise MemoryValidationError(
                "operation result_memory_revision must be a non-negative integer"
            )
        if not isinstance(self.result_memory_canonical_hash, str) or re.fullmatch(
            r"sha256:[0-9a-f]{64}", self.result_memory_canonical_hash
        ) is None:
            raise MemoryValidationError(
                "operation result_memory_canonical_hash must be a SHA-256 value"
            )
        self.canonical_input = _json_object(
            self.canonical_input, "operation canonical_input"
        )
        candidate = MemoryRecord.from_dict(self.canonical_input)
        if (
            candidate.subject_id != self.subject_id
            or candidate.environment != self.environment
            or candidate.consolidation_id != self.consolidation_id
            or candidate.consolidation_hash() != self.canonical_input_hash
        ):
            raise MemoryValidationError(
                "operation canonical input does not match its durable identity"
            )
        self.recorded_at = _utc(self.recorded_at, "operation recorded_at")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "consolidation_id": self.consolidation_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "canonical_input_hash": self.canonical_input_hash,
            "canonical_input": self.canonical_input,
            "result_memory_id": self.result_memory_id,
            "result_memory_revision": self.result_memory_revision,
            "result_memory_canonical_hash": self.result_memory_canonical_hash,
            "recorded_at": _format_datetime(self.recorded_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> MemoryConsolidationOperation:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory consolidation operation must be an object")
        return cls(
            consolidation_id=value.get("consolidation_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            canonical_input_hash=value.get("canonical_input_hash"),
            canonical_input=_json_object(
                value.get("canonical_input"), "operation canonical_input"
            ),
            result_memory_id=value.get("result_memory_id"),
            result_memory_revision=value.get("result_memory_revision"),
            result_memory_canonical_hash=value.get(
                "result_memory_canonical_hash"
            ),
            recorded_at=_parse_datetime(value.get("recorded_at"), "operation recorded_at"),
        )

    def canonical_hash(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(slots=True)
class MemoryLineageRecord:
    lineage_id: str
    subject_id: str
    environment: str
    target_memory_id: str
    signal: MemoryLineageType | MemoryLifecycleSignal
    source_event_id: str | None
    root_evidence_ids: list[str]
    recorded_at: datetime
    replacement_memory_id: str | None = None
    command: dict[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.lineage_id, "lineage_id"),
            (self.subject_id, "lineage subject_id"),
            (self.environment, "lineage environment"),
            (self.target_memory_id, "target_memory_id"),
        ):
            _require_text(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise MemoryValidationError("lineage environment is unsupported")
        self.signal = (MemoryLifecycleSignal.COMMAND if self.signal == MemoryLifecycleSignal.COMMAND
                       else _enum_value(self.signal, MemoryLineageType, "lineage signal"))
        if self.signal is MemoryLifecycleSignal.COMMAND:
            if self.source_event_id is not None or not isinstance(self.command, dict):
                raise MemoryValidationError('lifecycle lineage requires a command, not an Event')
        else:
            _require_text(self.source_event_id, 'lineage source_event_id')
            if self.command is not None:
                raise MemoryValidationError('fact lineage cannot carry lifecycle command')
        self.root_evidence_ids = _unique_texts(
            self.root_evidence_ids, "lineage root_evidence_ids", required=True
        )
        self.recorded_at = _utc(self.recorded_at, "lineage recorded_at")
        if self.replacement_memory_id is not None:
            _require_text(self.replacement_memory_id, "replacement_memory_id")
            if self.replacement_memory_id == self.target_memory_id:
                raise MemoryValidationError("replacement memory must use a distinct identity")

    def to_dict(self) -> dict[str, JsonValue]:
        body = {
            "lineage_id": self.lineage_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "target_memory_id": self.target_memory_id,
            "signal": self.signal.value,
            "source_event_id": self.source_event_id,
            "root_evidence_ids": list(self.root_evidence_ids),
            "recorded_at": _format_datetime(self.recorded_at),
            "replacement_memory_id": self.replacement_memory_id,
        }
        if self.command is not None:
            body['command'] = dict(self.command)
        return body

    @classmethod
    def from_dict(cls, value: Any) -> MemoryLineageRecord:
        if not isinstance(value, dict):
            raise MemoryValidationError("memory lineage record must be an object")
        return cls(
            lineage_id=value.get("lineage_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            target_memory_id=value.get("target_memory_id"),
            signal=value.get("signal"),
            source_event_id=value.get("source_event_id"),
            root_evidence_ids=_text_list(
                value.get("root_evidence_ids"), "lineage root_evidence_ids"
            ),
            recorded_at=_parse_datetime(value.get("recorded_at"), "lineage recorded_at"),
            replacement_memory_id=value.get("replacement_memory_id"),
            command=value.get('command'),
        )

    def canonical_hash(self) -> str:
        return _canonical_hash(self.to_dict())


_SUMMARY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(slots=True)
class DerivedSummary:
    summary_id: str
    subject_id: str
    environment: str
    summary_type: str
    scope: str
    time_range: MemoryTimeRange
    generated_at: datetime
    summary_version: int
    source_event_ids: list[str]
    source_memory_ids: list[str]
    source_message_ids: list[str]
    root_evidence_ids: list[str]
    confidence: float
    content: str
    status: DerivedSummaryStatus = DerivedSummaryStatus.ACTIVE
    invalidation_reason: str | None = None
    retrieval_weight: float = field(default=1.0,repr=False,compare=False)
    supersedes_version: int | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.summary_id, "summary_id"),
            (self.subject_id, "summary subject_id"),
            (self.environment, "summary environment"),
            (self.summary_type, "summary_type"),
            (self.scope, "summary scope"),
            (self.content, "summary content"),
        ):
            _require_text(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise MemoryValidationError("summary environment is unsupported")
        if _SUMMARY_TYPE_PATTERN.fullmatch(self.summary_type) is None:
            raise MemoryValidationError("summary_type must be a validated extensible identifier")
        if not isinstance(self.time_range, MemoryTimeRange):
            raise MemoryValidationError("summary time_range must be a MemoryTimeRange")
        self.generated_at = _utc(self.generated_at, "summary generated_at")
        if not isinstance(self.summary_version, int) or self.summary_version < 1:
            raise MemoryValidationError("summary_version must be positive")
        self.source_event_ids = _unique_texts(self.source_event_ids, "summary source_event_ids")
        self.source_memory_ids = _unique_texts(
            self.source_memory_ids, "summary source_memory_ids", required=True
        )
        self.source_message_ids = _unique_texts(
            self.source_message_ids, "summary source_message_ids"
        )
        self.root_evidence_ids = _unique_texts(
            self.root_evidence_ids, "summary root_evidence_ids", required=True
        )
        self.confidence = _ratio(self.confidence, "summary confidence")
        self.status = _enum_value(  # type: ignore[assignment]
            self.status, DerivedSummaryStatus, "summary status"
        )
        if self.status is DerivedSummaryStatus.ACTIVE:
            if self.invalidation_reason is not None:
                raise MemoryValidationError("an active summary cannot have invalidation_reason")
        else:
            self.invalidation_reason = _require_text(
                self.invalidation_reason, "summary invalidation_reason"
            )
        if self.supersedes_version is not None:
            if (
                not isinstance(self.supersedes_version, int)
                or self.supersedes_version < 1
                or self.supersedes_version >= self.summary_version
            ):
                raise MemoryValidationError("supersedes_version must precede summary_version")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "summary_id": self.summary_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "summary_type": self.summary_type,
            "scope": self.scope,
            "time_range": self.time_range.to_dict(),
            "generated_at": _format_datetime(self.generated_at),
            "summary_version": self.summary_version,
            "source_event_ids": list(self.source_event_ids),
            "source_memory_ids": list(self.source_memory_ids),
            "source_message_ids": list(self.source_message_ids),
            "root_evidence_ids": list(self.root_evidence_ids),
            "confidence": self.confidence,
            "content": self.content,
            "status": self.status.value,
            "invalidation_reason": self.invalidation_reason,
            "supersedes_version": self.supersedes_version,
        }

    @classmethod
    def from_dict(cls, value: Any) -> DerivedSummary:
        if not isinstance(value, dict):
            raise MemoryValidationError("derived summary must be an object")
        return cls(
            summary_id=value.get("summary_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            summary_type=value.get("summary_type"),
            scope=value.get("scope"),
            time_range=MemoryTimeRange.from_dict(value.get("time_range")),
            generated_at=_parse_datetime(value.get("generated_at"), "summary generated_at"),
            summary_version=value.get("summary_version"),
            source_event_ids=_text_list(
                value.get("source_event_ids", []), "summary source_event_ids"
            ),
            source_memory_ids=_text_list(
                value.get("source_memory_ids"), "summary source_memory_ids"
            ),
            source_message_ids=_text_list(
                value.get("source_message_ids", []), "summary source_message_ids"
            ),
            root_evidence_ids=_text_list(
                value.get("root_evidence_ids"), "summary root_evidence_ids"
            ),
            confidence=value.get("confidence"),
            content=value.get("content"),
            status=value.get("status", DerivedSummaryStatus.ACTIVE.value),
            invalidation_reason=value.get("invalidation_reason"),
            supersedes_version=value.get("supersedes_version"),
        )

    def canonical_hash(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(slots=True, frozen=True)
class MemoryActivationConfig:
    hot_threshold: float = 0.75
    warm_threshold: float = 0.45
    cold_threshold: float = 0.15
    hot_capacity: int = 300
    warm_capacity: int = 3000
    cold_capacity: int = 30000
    decay_days: float = 180.0

    def __post_init__(self) -> None:
        for value, name in (
            (self.hot_threshold, "hot_threshold"),
            (self.warm_threshold, "warm_threshold"),
            (self.cold_threshold, "cold_threshold"),
        ):
            _ratio(value, name)
        if not self.hot_threshold > self.warm_threshold > self.cold_threshold:
            raise MemoryValidationError("activation thresholds must descend HOT to COLD")
        for value, name in (
            (self.hot_capacity, "hot_capacity"),
            (self.warm_capacity, "warm_capacity"),
            (self.cold_capacity, "cold_capacity"),
        ):
            if not isinstance(value, int) or value < 1:
                raise MemoryValidationError(f"{name} must be positive")
        if isinstance(self.decay_days, bool) or self.decay_days <= 0:
            raise MemoryValidationError("decay_days must be positive")


@dataclass(slots=True, frozen=True)
class MemoryActivationDecision:
    activation: float
    temperature: MemoryTemperature
    explanation: tuple[str, ...]


class MemoryActivationPolicy:
    """Explainable, explicitly invoked activity scoring; it never deletes memory."""

    def __init__(self, config: MemoryActivationConfig | None = None) -> None:
        self.config = config or MemoryActivationConfig()

    def evaluate(self, memory: MemoryRecord, now: datetime) -> MemoryActivationDecision:
        evaluated_at = _utc(now, "activation now")
        age_days = max(0.0, (evaluated_at - memory.occurred_at).total_seconds() / 86400)
        recency = max(0.0, 1.0 - age_days / self.config.decay_days)
        accessed = memory.last_accessed_at or memory.consolidated_at
        access_age = max(0.0, (evaluated_at - accessed).total_seconds() / 86400)
        access_recency = max(0.0, 1.0 - access_age / self.config.decay_days)
        reinforcement = min(1.0, memory.unique_evidence_count / 5.0)
        activation = round(
            0.30 * memory.importance
            + 0.20 * max(recency, access_recency)
            + 0.20 * memory.relation_relevance
            + 0.15 * memory.emotional_weight
            + 0.15 * reinforcement,
            6,
        )
        if activation >= self.config.hot_threshold:
            temperature = MemoryTemperature.HOT
        elif activation >= self.config.warm_threshold:
            temperature = MemoryTemperature.WARM
        elif activation >= self.config.cold_threshold:
            temperature = MemoryTemperature.COLD
        else:
            temperature = MemoryTemperature.ARCHIVED
        return MemoryActivationDecision(
            activation=activation,
            temperature=temperature,
            explanation=(
                f"importance={memory.importance:.6f}",
                f"recency={max(recency, access_recency):.6f}",
                f"relation_relevance={memory.relation_relevance:.6f}",
                f"emotional_weight={memory.emotional_weight:.6f}",
                f"unique_reinforcement={reinforcement:.6f}",
            ),
        )
