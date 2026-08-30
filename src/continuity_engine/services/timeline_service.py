from __future__ import annotations

from datetime import timedelta

from continuity_engine.domain.timeline import (
    TimelineEntry,
    TimelineProjection,
    TimelineQuery,
    TimelineRelativeOrder,
    TimelineResult,
)
from continuity_engine.storage.base import StateUpdateRecordRepository


class TimelineService:
    """Read-only Event-history projection with no persistence authority."""

    def __init__(self, event_history: StateUpdateRecordRepository) -> None:
        self._event_history = event_history

    def rebuild(self, subject_id: str) -> TimelineProjection:
        return TimelineProjection.from_updates(
            subject_id,
            self._event_history.list_update_records(subject_id),
        )

    def query(
        self,
        subject_id: str,
        query: TimelineQuery | None = None,
    ) -> TimelineResult:
        return self.rebuild(subject_id).query(query)

    def first(self, subject_id: str, query: TimelineQuery | None = None) -> TimelineEntry | None:
        return self.query(subject_id, query).first

    def last(self, subject_id: str, query: TimelineQuery | None = None) -> TimelineEntry | None:
        return self.query(subject_id, query).last

    def relative_order(
        self,
        subject_id: str,
        left_event_id: str,
        right_event_id: str,
    ) -> TimelineRelativeOrder:
        return self.rebuild(subject_id).relative_order(left_event_id, right_event_id)

    def distance(
        self,
        subject_id: str,
        from_event_id: str,
        to_event_id: str,
    ) -> timedelta:
        return self.rebuild(subject_id).distance(from_event_id, to_event_id)

    def chain(self, subject_id: str, event_id: str) -> tuple[TimelineEntry, ...]:
        return self.rebuild(subject_id).chain(event_id)
