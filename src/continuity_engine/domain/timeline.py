from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable

from .errors import TimelineReferenceError, TimelineValidationError
from .events import (
    Event,
    EventClassification,
    EventRelationType,
    EventSourceKind,
    StateUpdateRecord,
    normalize_utc,
)


class TimelineEventStatus(str, Enum):
    ACTIVE = "active"
    CORRECTED = "corrected"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class TimelineRelativeOrder(str, Enum):
    BEFORE = "before"
    SAME_OCCURRED_AT = "same_occurred_at"
    AFTER = "after"


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    subject_id: str
    update_id: str
    event: Event
    status: TimelineEventStatus
    corrected_by: tuple[str, ...] = ()
    revoked_by: tuple[str, ...] = ()

    @property
    def sort_key(self) -> tuple[datetime, datetime, datetime, str]:
        assert self.event.observed_at is not None
        assert self.event.recorded_at is not None
        return (
            self.event.occurred_at,
            self.event.observed_at,
            self.event.recorded_at,
            self.event.event_id,
        )


@dataclass(frozen=True, slots=True)
class TimelineQuery:
    start_at: datetime | None = None
    end_at: datetime | None = None
    classifications: tuple[EventClassification, ...] = ()
    sources: tuple[str, ...] = ()
    source_kinds: tuple[EventSourceKind, ...] = ()
    correlation_id: str | None = None
    include_revoked: bool = True
    limit: int = 50

    def __post_init__(self) -> None:
        if self.start_at is not None:
            object.__setattr__(self, "start_at", normalize_utc(self.start_at, "start_at"))
        if self.end_at is not None:
            object.__setattr__(self, "end_at", normalize_utc(self.end_at, "end_at"))
        if self.start_at is not None and self.end_at is not None:
            if self.start_at > self.end_at:
                raise TimelineValidationError("timeline start_at cannot be after end_at")
        if not isinstance(self.limit, int) or isinstance(self.limit, bool) or not 20 <= self.limit <= 100:
            raise TimelineValidationError("timeline limit must be between 20 and 100")
        object.__setattr__(
            self,
            "classifications",
            tuple(
                item if isinstance(item, EventClassification) else EventClassification(item)
                for item in self.classifications
            ),
        )
        object.__setattr__(
            self,
            "source_kinds",
            tuple(
                item if isinstance(item, EventSourceKind) else EventSourceKind(item)
                for item in self.source_kinds
            ),
        )
        if self.correlation_id is not None and not self.correlation_id.strip():
            raise TimelineValidationError("correlation_id must be a non-empty string")
        if any(not isinstance(item, str) or not item.strip() for item in self.sources):
            raise TimelineValidationError("timeline sources must be non-empty strings")


@dataclass(frozen=True, slots=True)
class TimelineResult:
    subject_id: str
    entries: tuple[TimelineEntry, ...]
    total_matching: int
    query: TimelineQuery

    @property
    def first(self) -> TimelineEntry | None:
        return self.entries[0] if self.entries else None

    @property
    def last(self) -> TimelineEntry | None:
        return self.entries[-1] if self.entries else None


@dataclass(frozen=True, slots=True)
class TimelineProjection:
    """A deterministic in-memory projection rebuilt from Event history."""

    subject_id: str
    entries: tuple[TimelineEntry, ...] = field(default_factory=tuple)

    @classmethod
    def from_updates(
        cls,
        subject_id: str,
        updates: Iterable[StateUpdateRecord],
    ) -> TimelineProjection:
        records = list(updates)
        if any(record.subject_id != subject_id for record in records):
            raise TimelineReferenceError("timeline history crosses subject boundaries")
        by_id: dict[str, StateUpdateRecord] = {}
        seen_event_ids: set[str] = set()
        for record in records:
            existing = by_id.get(record.event.event_id)
            if existing is not None:
                if existing.event.canonical_dict() != record.event.canonical_dict():
                    raise TimelineReferenceError("timeline contains a conflicting event identity")
                raise TimelineReferenceError("timeline contains a duplicate event record")
            for reference in record.event.references:
                if reference.target_subject_id != subject_id:
                    raise TimelineReferenceError(
                        "timeline event reference crosses subject boundaries"
                    )
                if reference.target_event_id not in seen_event_ids:
                    raise TimelineReferenceError(
                        "timeline event reference must target an earlier event"
                    )
            by_id[record.event.event_id] = record
            seen_event_ids.add(record.event.event_id)

        corrected_by: dict[str, list[str]] = {event_id: [] for event_id in by_id}
        revoked_by: dict[str, list[str]] = {event_id: [] for event_id in by_id}
        status = {event_id: TimelineEventStatus.ACTIVE for event_id in by_id}
        for record in records:
            for reference in record.event.references:
                target = by_id.get(reference.target_event_id)
                if target is None:
                    raise TimelineReferenceError(
                        f"timeline event reference target is missing: {reference.target_event_id}"
                    )
                if reference.relation_type is EventRelationType.CORRECTS:
                    corrected_by[reference.target_event_id].append(record.event.event_id)
                    if status[reference.target_event_id] is not TimelineEventStatus.REVOKED:
                        status[reference.target_event_id] = (
                            TimelineEventStatus.SUPERSEDED
                            if target.event.classification is EventClassification.CORRECTION
                            or len(corrected_by[reference.target_event_id]) > 1
                            else TimelineEventStatus.CORRECTED
                        )
                elif reference.relation_type is EventRelationType.REVOKES:
                    revoked_by[reference.target_event_id].append(record.event.event_id)
                    status[reference.target_event_id] = TimelineEventStatus.REVOKED

        entries = tuple(
            sorted(
                (
                    TimelineEntry(
                        subject_id=subject_id,
                        update_id=record.update_id,
                        event=record.event,
                        status=status[record.event.event_id],
                        corrected_by=tuple(sorted(corrected_by[record.event.event_id])),
                        revoked_by=tuple(sorted(revoked_by[record.event.event_id])),
                    )
                    for record in records
                ),
                key=lambda item: item.sort_key,
            )
        )
        return cls(subject_id=subject_id, entries=entries)

    def get(self, event_id: str) -> TimelineEntry:
        for entry in self.entries:
            if entry.event.event_id == event_id:
                return entry
        raise TimelineReferenceError(f"timeline event does not exist: {event_id}")

    def query(self, query: TimelineQuery | None = None) -> TimelineResult:
        effective = query or TimelineQuery()
        matching = [entry for entry in self.entries if _matches(entry, effective)]
        return TimelineResult(
            subject_id=self.subject_id,
            entries=tuple(matching[: effective.limit]),
            total_matching=len(matching),
            query=effective,
        )

    def relative_order(
        self,
        left_event_id: str,
        right_event_id: str,
    ) -> TimelineRelativeOrder:
        left = self.get(left_event_id)
        right = self.get(right_event_id)
        if left.event.occurred_at == right.event.occurred_at:
            return TimelineRelativeOrder.SAME_OCCURRED_AT
        return (
            TimelineRelativeOrder.BEFORE
            if left.sort_key < right.sort_key
            else TimelineRelativeOrder.AFTER
        )

    def distance(self, from_event_id: str, to_event_id: str) -> timedelta:
        return self.get(to_event_id).event.occurred_at - self.get(from_event_id).event.occurred_at

    def chain(self, event_id: str) -> tuple[TimelineEntry, ...]:
        seed = self.get(event_id)
        selected = {seed.event.event_id}
        if seed.event.correlation_id is not None:
            selected.update(
                entry.event.event_id
                for entry in self.entries
                if entry.event.correlation_id == seed.event.correlation_id
            )
        changed = True
        while changed:
            changed = False
            for entry in self.entries:
                targets = {item.target_event_id for item in entry.event.references}
                if entry.event.event_id in selected or targets.intersection(selected):
                    before = len(selected)
                    selected.add(entry.event.event_id)
                    selected.update(targets)
                    changed = changed or len(selected) != before
        return tuple(entry for entry in self.entries if entry.event.event_id in selected)


def _event_sort_key(event: Event) -> tuple[datetime, datetime, datetime, str]:
    assert event.observed_at is not None and event.recorded_at is not None
    return event.occurred_at, event.observed_at, event.recorded_at, event.event_id


def _matches(entry: TimelineEntry, query: TimelineQuery) -> bool:
    event = entry.event
    if query.start_at is not None and event.occurred_at < query.start_at:
        return False
    if query.end_at is not None and event.occurred_at > query.end_at:
        return False
    if query.classifications and event.classification not in query.classifications:
        return False
    if query.sources and event.source not in query.sources:
        return False
    if query.source_kinds and event.source_kind not in query.source_kinds:
        return False
    if query.correlation_id is not None and event.correlation_id != query.correlation_id:
        return False
    if not query.include_revoked and entry.status is TimelineEventStatus.REVOKED:
        return False
    return True
