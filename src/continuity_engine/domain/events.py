from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .errors import StateValidationError


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class StateSection(str, Enum):
    IDENTITY = "identity"
    RELATIONSHIP = "relationship"
    CONTINUITY = "continuity"
    TEMPORAL = "temporal"
    INTENTIONS = "intentions"
    EMOTION_STATE = "emotion_state"


class ChangeOperation(str, Enum):
    SET = "set"
    APPEND = "append"
    REMOVE = "remove"


class EventClassification(str, Enum):
    """Validated semantic role of an event without replacing event_type."""

    LEGACY = "legacy"
    FACT = "fact"
    OBSERVATION = "observation"
    INTENTION = "intention"
    INTERACTION = "interaction"
    STATE_CHANGE = "state_change"
    CORRECTION = "correction"
    REVOCATION = "revocation"


class EventSourceKind(str, Enum):
    """Host-neutral source class; source keeps the concrete producer name."""

    LEGACY = "legacy"
    INTERNAL = "internal"
    USER = "user"
    SYSTEM = "system"
    PLATFORM = "platform"
    EXTERNAL = "external"
    TEST = "test"


class EventTimeBasis(str, Enum):
    """Whether the three event times were measured or deterministically filled."""

    EXPLICIT = "explicit"
    PARTIALLY_COALESCED = "partially_coalesced"
    LEGACY_COALESCED = "legacy_coalesced"


class EventRelationType(str, Enum):
    CAUSED_BY = "caused_by"
    CORRECTS = "corrects"
    REVOKES = "revokes"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateValidationError(f"{field_name} must be a non-empty string")
    return value


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


def normalize_utc(value: datetime, field_name: str = "datetime") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise StateValidationError(f"{field_name} must include a timezone")
    return value.astimezone(timezone.utc)


def _validate_json_value(value: Any, field_name: str) -> JsonValue:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise StateValidationError(f"{field_name} must contain JSON-compatible data") from exc
    return value


@dataclass(slots=True)
class StateMutation:
    field_path: str
    operation: ChangeOperation
    value: JsonValue
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.field_path, "mutation.field_path")
        if "." not in self.field_path:
            raise StateValidationError("mutation.field_path must include a state section")
        if not isinstance(self.operation, ChangeOperation):
            try:
                self.operation = ChangeOperation(self.operation)
            except ValueError as exc:
                raise StateValidationError("mutation.operation is not supported") from exc
        _validate_json_value(self.value, "mutation.value")
        _require_text(self.reason, "mutation.reason")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "field_path": self.field_path,
            "operation": self.operation.value,
            "value": self.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> StateMutation:
        if not isinstance(value, dict):
            raise StateValidationError("mutation must be an object")
        return cls(
            field_path=value.get("field_path"),
            operation=value.get("operation"),
            value=value.get("value"),
            reason=value.get("reason"),
        )


@dataclass(frozen=True, slots=True)
class EventEvidenceReference:
    evidence_id: str
    evidence_type: str
    source: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence.evidence_id")
        _require_text(self.evidence_type, "evidence.evidence_type")
        if self.source is not None:
            _require_text(self.source, "evidence.source")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, value: Any) -> EventEvidenceReference:
        if not isinstance(value, dict):
            raise StateValidationError("event evidence reference must be an object")
        return cls(
            evidence_id=value.get("evidence_id"),
            evidence_type=value.get("evidence_type"),
            source=value.get("source"),
        )


@dataclass(frozen=True, slots=True)
class EventReference:
    target_event_id: str
    target_subject_id: str
    relation_type: EventRelationType

    def __post_init__(self) -> None:
        _require_text(self.target_event_id, "event_reference.target_event_id")
        _require_text(self.target_subject_id, "event_reference.target_subject_id")
        if not isinstance(self.relation_type, EventRelationType):
            try:
                object.__setattr__(
                    self,
                    "relation_type",
                    EventRelationType(self.relation_type),
                )
            except ValueError as exc:
                raise StateValidationError(
                    "event_reference.relation_type is not supported"
                ) from exc

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "target_event_id": self.target_event_id,
            "target_subject_id": self.target_subject_id,
            "relation_type": self.relation_type.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> EventReference:
        if not isinstance(value, dict):
            raise StateValidationError("event reference must be an object")
        return cls(
            target_event_id=value.get("target_event_id"),
            target_subject_id=value.get("target_subject_id"),
            relation_type=value.get("relation_type"),
        )


@dataclass(slots=True)
class Event:
    event_id: str
    occurred_at: datetime
    source: str
    event_type: str
    content: str
    impact_scope: list[StateSection]
    mutations: list[StateMutation]
    reason: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    observed_at: datetime | None = None
    recorded_at: datetime | None = None
    time_basis: EventTimeBasis | str | None = None
    classification: EventClassification | str = EventClassification.LEGACY
    source_kind: EventSourceKind | str = EventSourceKind.LEGACY
    source_event_id: str | None = None
    correlation_id: str | None = None
    evidence: list[EventEvidenceReference] = field(default_factory=list)
    references: list[EventReference] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        self.occurred_at = normalize_utc(self.occurred_at, "occurred_at")
        observed_was_missing = self.observed_at is None
        recorded_was_missing = self.recorded_at is None
        supplied_time_basis = self.time_basis
        if observed_was_missing:
            self.observed_at = self.occurred_at
        else:
            self.observed_at = normalize_utc(self.observed_at, "observed_at")
        if recorded_was_missing:
            self.recorded_at = self.observed_at
        else:
            self.recorded_at = normalize_utc(self.recorded_at, "recorded_at")
        if self.time_basis is None:
            if observed_was_missing and recorded_was_missing:
                self.time_basis = EventTimeBasis.LEGACY_COALESCED
            elif observed_was_missing or recorded_was_missing:
                self.time_basis = EventTimeBasis.PARTIALLY_COALESCED
            else:
                self.time_basis = EventTimeBasis.EXPLICIT
        elif not isinstance(self.time_basis, EventTimeBasis):
            try:
                self.time_basis = EventTimeBasis(self.time_basis)
            except ValueError as exc:
                raise StateValidationError("event.time_basis is not supported") from exc
        if supplied_time_basis is not None:
            if self.time_basis is EventTimeBasis.EXPLICIT and (
                observed_was_missing or recorded_was_missing
            ):
                raise StateValidationError(
                    "explicit time_basis requires observed_at and recorded_at"
                )
            if self.time_basis is EventTimeBasis.PARTIALLY_COALESCED:
                if observed_was_missing and recorded_was_missing:
                    raise StateValidationError(
                        "partially_coalesced time_basis cannot omit both event times"
                    )
                if not observed_was_missing and not recorded_was_missing:
                    assert self.observed_at is not None and self.recorded_at is not None
                    if not (
                        self.occurred_at == self.observed_at
                        or self.observed_at == self.recorded_at
                    ):
                        raise StateValidationError(
                            "partially_coalesced event times must contain a coalesced pair"
                        )
            if self.time_basis is EventTimeBasis.LEGACY_COALESCED:
                if observed_was_missing != recorded_was_missing:
                    raise StateValidationError(
                        "legacy_coalesced time_basis requires both event times to be coalesced"
                    )
        assert self.observed_at is not None and self.recorded_at is not None
        if not self.occurred_at <= self.observed_at <= self.recorded_at:
            raise StateValidationError(
                "event times must satisfy occurred_at <= observed_at <= recorded_at"
            )
        if (
            self.time_basis is EventTimeBasis.LEGACY_COALESCED
            and not self.occurred_at == self.observed_at == self.recorded_at
        ):
            raise StateValidationError(
                "legacy_coalesced event times must all represent the same instant"
            )
        _require_text(self.source, "source")
        _require_text(self.event_type, "event_type")
        _require_text(self.content, "content")
        _require_text(self.reason, "reason")
        if not self.impact_scope:
            raise StateValidationError("impact_scope must contain at least one state section")
        normalized_scope: list[StateSection] = []
        for section in self.impact_scope:
            try:
                normalized = section if isinstance(section, StateSection) else StateSection(section)
            except ValueError as exc:
                raise StateValidationError(f"unsupported impact scope: {section}") from exc
            if normalized not in normalized_scope:
                normalized_scope.append(normalized)
        self.impact_scope = normalized_scope
        if any(not isinstance(mutation, StateMutation) for mutation in self.mutations):
            raise StateValidationError("mutations must contain StateMutation values")
        _validate_json_value(self.metadata, "metadata")
        try:
            self.classification = (
                self.classification
                if isinstance(self.classification, EventClassification)
                else EventClassification(self.classification)
            )
        except ValueError as exc:
            raise StateValidationError("event.classification is not supported") from exc
        try:
            self.source_kind = (
                self.source_kind
                if isinstance(self.source_kind, EventSourceKind)
                else EventSourceKind(self.source_kind)
            )
        except ValueError as exc:
            raise StateValidationError("event.source_kind is not supported") from exc
        if self.source_event_id is not None:
            _require_text(self.source_event_id, "source_event_id")
        if self.correlation_id is not None:
            _require_text(self.correlation_id, "correlation_id")
        if any(not isinstance(item, EventEvidenceReference) for item in self.evidence):
            raise StateValidationError("evidence must contain EventEvidenceReference values")
        if any(not isinstance(item, EventReference) for item in self.references):
            raise StateValidationError("references must contain EventReference values")
        evidence_keys = [(item.evidence_type, item.evidence_id) for item in self.evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise StateValidationError("event evidence references must be unique")
        reference_keys = [
            (item.relation_type.value, item.target_subject_id, item.target_event_id)
            for item in self.references
        ]
        if len(reference_keys) != len(set(reference_keys)):
            raise StateValidationError("event references must be unique")
        if any(item.target_event_id == self.event_id for item in self.references):
            raise StateValidationError("an event cannot reference itself")
        correction_refs = [
            item for item in self.references if item.relation_type is EventRelationType.CORRECTS
        ]
        revocation_refs = [
            item for item in self.references if item.relation_type is EventRelationType.REVOKES
        ]
        if self.classification is EventClassification.CORRECTION and len(correction_refs) != 1:
            raise StateValidationError("a correction event must reference exactly one target")
        if self.classification is EventClassification.REVOCATION and len(revocation_refs) != 1:
            raise StateValidationError("a revocation event must reference exactly one target")
        if correction_refs and self.classification is not EventClassification.CORRECTION:
            raise StateValidationError("corrects references require correction classification")
        if revocation_refs and self.classification is not EventClassification.REVOCATION:
            raise StateValidationError("revokes references require revocation classification")

    @classmethod
    def create(
        cls,
        *,
        occurred_at: datetime,
        source: str,
        event_type: str,
        content: str,
        impact_scope: Iterable[StateSection],
        mutations: Iterable[StateMutation],
        reason: str,
        metadata: dict[str, JsonValue] | None = None,
        event_id: str | None = None,
        observed_at: datetime | None = None,
        recorded_at: datetime | None = None,
        classification: EventClassification = EventClassification.LEGACY,
        source_kind: EventSourceKind = EventSourceKind.LEGACY,
        source_event_id: str | None = None,
        correlation_id: str | None = None,
        evidence: Iterable[EventEvidenceReference] = (),
        references: Iterable[EventReference] = (),
        time_basis: EventTimeBasis | None = None,
    ) -> Event:
        derived_time_basis = (
            EventTimeBasis.LEGACY_COALESCED
            if observed_at is None and recorded_at is None
            else EventTimeBasis.PARTIALLY_COALESCED
            if observed_at is None or recorded_at is None
            else EventTimeBasis.EXPLICIT
        )
        if time_basis is not None:
            try:
                normalized_time_basis = (
                    time_basis
                    if isinstance(time_basis, EventTimeBasis)
                    else EventTimeBasis(time_basis)
                )
            except ValueError as exc:
                raise StateValidationError("event.time_basis is not supported") from exc
            if normalized_time_basis is not derived_time_basis:
                raise StateValidationError(
                    "event.time_basis does not match the supplied event times"
                )
        return cls(
            event_id=event_id or str(uuid4()),
            occurred_at=occurred_at,
            source=source,
            event_type=event_type,
            content=content,
            impact_scope=list(impact_scope),
            mutations=list(mutations),
            reason=reason,
            metadata=dict(metadata or {}),
            observed_at=observed_at,
            recorded_at=recorded_at,
            time_basis=derived_time_basis,
            classification=classification,
            source_kind=source_kind,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            evidence=list(evidence),
            references=list(references),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "event_id": self.event_id,
            "occurred_at": _format_datetime(self.occurred_at),
            "source": self.source,
            "event_type": self.event_type,
            "content": self.content,
            "impact_scope": [section.value for section in self.impact_scope],
            "mutations": [mutation.to_dict() for mutation in self.mutations],
            "reason": self.reason,
            "metadata": self.metadata,
            "observed_at": _format_datetime(self.observed_at),
            "recorded_at": _format_datetime(self.recorded_at),
            "time_basis": self.time_basis.value,
            "classification": self.classification.value,
            "source_kind": self.source_kind.value,
            "source_event_id": self.source_event_id,
            "correlation_id": self.correlation_id,
            "evidence": [item.to_dict() for item in self.evidence],
            "references": [item.to_dict() for item in self.references],
        }

    def canonical_dict(self) -> dict[str, JsonValue]:
        value = self.to_dict()
        value["impact_scope"] = sorted(value["impact_scope"])
        value["evidence"] = sorted(
            value["evidence"],
            key=lambda item: (item["evidence_type"], item["evidence_id"], item["source"] or ""),
        )
        value["references"] = sorted(
            value["references"],
            key=lambda item: (
                item["relation_type"],
                item["target_subject_id"],
                item["target_event_id"],
            ),
        )
        return value

    def canonical_hash(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @classmethod
    def from_dict(cls, value: Any) -> Event:
        if not isinstance(value, dict):
            raise StateValidationError("event must be an object")
        raw_scope = value.get("impact_scope")
        raw_mutations = value.get("mutations")
        if not isinstance(raw_scope, list):
            raise StateValidationError("impact_scope must be a list")
        if not isinstance(raw_mutations, list):
            raise StateValidationError("mutations must be a list")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise StateValidationError("metadata must be an object")
        raw_evidence = value.get("evidence", [])
        raw_references = value.get("references", [])
        if not isinstance(raw_evidence, list):
            raise StateValidationError("event.evidence must be a list")
        if not isinstance(raw_references, list):
            raise StateValidationError("event.references must be a list")
        return cls(
            event_id=value.get("event_id"),
            occurred_at=_parse_datetime(value.get("occurred_at"), "occurred_at"),
            source=value.get("source"),
            event_type=value.get("event_type"),
            content=value.get("content"),
            impact_scope=[StateSection(section) for section in raw_scope],
            mutations=[StateMutation.from_dict(item) for item in raw_mutations],
            reason=value.get("reason"),
            metadata=metadata,
            observed_at=(
                _parse_datetime(value.get("observed_at"), "observed_at")
                if value.get("observed_at") is not None
                else None
            ),
            recorded_at=(
                _parse_datetime(value.get("recorded_at"), "recorded_at")
                if value.get("recorded_at") is not None
                else None
            ),
            time_basis=value.get("time_basis"),
            classification=value.get("classification", EventClassification.LEGACY.value),
            source_kind=value.get("source_kind", EventSourceKind.LEGACY.value),
            source_event_id=value.get("source_event_id"),
            correlation_id=value.get("correlation_id"),
            evidence=[EventEvidenceReference.from_dict(item) for item in raw_evidence],
            references=[EventReference.from_dict(item) for item in raw_references],
        )


@dataclass(slots=True)
class FieldChange:
    field_path: str
    operation: ChangeOperation
    before: JsonValue
    after: JsonValue
    reason: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "field_path": self.field_path,
            "operation": self.operation.value,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> FieldChange:
        if not isinstance(value, dict):
            raise StateValidationError("field change must be an object")
        return cls(
            field_path=_require_text(value.get("field_path"), "field_change.field_path"),
            operation=ChangeOperation(value.get("operation")),
            before=_validate_json_value(value.get("before"), "field_change.before"),
            after=_validate_json_value(value.get("after"), "field_change.after"),
            reason=_require_text(value.get("reason"), "field_change.reason"),
        )


@dataclass(slots=True)
class StateUpdateRecord:
    update_id: str
    subject_id: str
    event: Event
    applied_at: datetime
    before_revision: int
    after_revision: int
    changes: list[FieldChange]
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.update_id, "update_id")
        _require_text(self.subject_id, "subject_id")
        self.applied_at = normalize_utc(self.applied_at, "applied_at")
        if (
            self.event.time_basis is EventTimeBasis.EXPLICIT
            and self.event.recorded_at > self.applied_at
        ):
            raise StateValidationError(
                "an explicit event recorded_at cannot be later than update.applied_at"
            )
        if self.before_revision < 0 or self.after_revision < self.before_revision:
            raise StateValidationError("update revisions are invalid")
        _require_text(self.reason, "update.reason")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "update_id": self.update_id,
            "subject_id": self.subject_id,
            "event": self.event.to_dict(),
            "applied_at": _format_datetime(self.applied_at),
            "before_revision": self.before_revision,
            "after_revision": self.after_revision,
            "changes": [change.to_dict() for change in self.changes],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> StateUpdateRecord:
        if not isinstance(value, dict):
            raise StateValidationError("state update record must be an object")
        raw_changes = value.get("changes")
        if not isinstance(raw_changes, list):
            raise StateValidationError("update.changes must be a list")
        before_revision = value.get("before_revision")
        after_revision = value.get("after_revision")
        if not isinstance(before_revision, int) or not isinstance(after_revision, int):
            raise StateValidationError("update revisions must be integers")
        return cls(
            update_id=value.get("update_id"),
            subject_id=value.get("subject_id"),
            event=Event.from_dict(value.get("event")),
            applied_at=_parse_datetime(value.get("applied_at"), "applied_at"),
            before_revision=before_revision,
            after_revision=after_revision,
            changes=[FieldChange.from_dict(item) for item in raw_changes],
            reason=value.get("reason"),
        )
