from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
