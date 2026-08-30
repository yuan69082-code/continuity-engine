import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.errors import TimelineReferenceError, TimelineValidationError
from continuity_engine.domain.events import (
    Event,
    EventClassification,
    EventReference,
    EventRelationType,
    EventSourceKind,
    StateSection,
)
from continuity_engine.domain.timeline import (
    TimelineEventStatus,
    TimelineProjection,
    TimelineQuery,
    TimelineRelativeOrder,
)
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p03_timeline_fixture import (
    P03_GOLDEN_SCENARIO_VERSION,
    run_p03_golden_scenario,
)


UTC = timezone.utc


class _MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def _event(
    event_id: str,
    occurred_at: datetime,
    *,
    observed_at: datetime | None = None,
    recorded_at: datetime | None = None,
    classification: EventClassification = EventClassification.FACT,
    source: str = "p03-test",
    source_kind: EventSourceKind = EventSourceKind.TEST,
    correlation_id: str | None = None,
    references: list[EventReference] | None = None,
) -> Event:
    return Event.create(
        event_id=event_id,
        occurred_at=occurred_at,
        observed_at=observed_at or occurred_at + timedelta(seconds=1),
        recorded_at=recorded_at or occurred_at + timedelta(seconds=2),
        source=source,
        source_kind=source_kind,
        event_type=classification.value,
        classification=classification,
        content=f"Timeline event {event_id}",
        impact_scope=[StateSection.TEMPORAL],
        mutations=[],
        reason="Exercise read-only Timeline semantics.",
        correlation_id=correlation_id,
        references=references or [],
    )


class P03TimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        self.repository = JsonSubjectStateRepository(self.temporary.name)
        self.clock = _MutableClock(self.now)
        self.states = SubjectStateService(self.repository, clock=self.clock)
        self.states.create("subject-1")
        self.timeline = TimelineService(self.repository)

    def apply(self, event: Event) -> None:
        self.clock.current = max(self.clock.current, event.recorded_at)
        self.states.apply_event("subject-1", event)

    def test_timeline_orders_by_three_times_then_event_id(self) -> None:
        same = self.now
        self.apply(_event("event-b", same))
        self.apply(_event("event-a", same))
        late_recorded = _event(
            "late-recorded",
            same - timedelta(hours=1),
            observed_at=same + timedelta(minutes=1),
            recorded_at=same + timedelta(minutes=2),
        )
        self.apply(late_recorded)

        ids = [entry.event.event_id for entry in self.timeline.query("subject-1").entries]
        self.assertEqual(ids, ["late-recorded", "event-a", "event-b"])

    def test_timezone_forms_of_the_same_instant_have_deterministic_tie_break(self) -> None:
        plus_eight = timezone(timedelta(hours=8))
        minus_five = timezone(timedelta(hours=-5))
        self.apply(_event("z", datetime(2026, 8, 3, 10, 0, tzinfo=UTC)))
        self.apply(_event("plus", datetime(2026, 8, 3, 18, 0, tzinfo=plus_eight)))
        self.apply(_event("minus", datetime(2026, 8, 3, 5, 0, tzinfo=minus_five)))

        entries = self.timeline.query("subject-1").entries
        self.assertEqual([item.event.event_id for item in entries], ["minus", "plus", "z"])
        self.assertEqual(len({item.event.occurred_at for item in entries}), 1)

    def test_range_filters_are_inclusive_and_empty_query_is_unique(self) -> None:
        self.apply(_event("boundary", self.now))
        exact = self.timeline.query(
            "subject-1", TimelineQuery(start_at=self.now, end_at=self.now, limit=20)
        )
        empty = self.timeline.query(
            "subject-1",
            TimelineQuery(
                start_at=self.now + timedelta(seconds=1),
                end_at=self.now + timedelta(seconds=1),
                limit=20,
            ),
        )
        self.assertEqual([item.event.event_id for item in exact.entries], ["boundary"])
        self.assertEqual(empty.entries, ())
        self.assertIsNone(empty.first)
        self.assertIsNone(empty.last)

    def test_query_filters_first_last_distance_and_relative_order(self) -> None:
        self.apply(
            _event(
                "first",
                self.now,
                source="source-a",
                correlation_id="chain-a",
                classification=EventClassification.INTENTION,
            )
        )
        self.apply(
            _event(
                "last",
                self.now + timedelta(hours=2),
                source="source-b",
                correlation_id="chain-a",
            )
        )
        result = self.timeline.query(
            "subject-1",
            TimelineQuery(
                classifications=(EventClassification.INTENTION,),
                sources=("source-a",),
                source_kinds=(EventSourceKind.TEST,),
                correlation_id="chain-a",
                limit=20,
            ),
        )
        self.assertEqual(result.first.event.event_id, "first")
        self.assertEqual(result.last.event.event_id, "first")
        self.assertEqual(
            self.timeline.relative_order("subject-1", "first", "last"),
            TimelineRelativeOrder.BEFORE,
        )
        self.assertEqual(
            self.timeline.distance("subject-1", "first", "last"), timedelta(hours=2)
        )

    def test_query_limit_is_configurable_only_from_twenty_to_one_hundred(self) -> None:
        for invalid in (0, 19, 101, True):
            with self.subTest(invalid=invalid), self.assertRaises(TimelineValidationError):
                TimelineQuery(limit=invalid)
        self.assertEqual(TimelineQuery().limit, 50)
        self.assertEqual(TimelineQuery(limit=100).limit, 100)

    def test_correction_and_revocation_are_append_only_and_revocation_is_terminal(self) -> None:
        target = _event("target", self.now)
        correction = _event(
            "correction",
            self.now + timedelta(minutes=1),
            classification=EventClassification.CORRECTION,
            references=[
                EventReference("target", "subject-1", EventRelationType.CORRECTS)
            ],
        )
        revocation = _event(
            "revocation",
            self.now + timedelta(minutes=2),
            classification=EventClassification.REVOCATION,
            references=[
                EventReference("target", "subject-1", EventRelationType.REVOKES)
            ],
        )
        later_correction = _event(
            "later-correction",
            self.now + timedelta(minutes=3),
            classification=EventClassification.CORRECTION,
            references=[
                EventReference("target", "subject-1", EventRelationType.CORRECTS)
            ],
        )
        for event in (target, correction, revocation, later_correction):
            self.apply(event)

        entry = self.timeline.rebuild("subject-1").get("target")
        self.assertIs(entry.status, TimelineEventStatus.REVOKED)
        self.assertEqual(entry.corrected_by, ("correction", "later-correction"))
        self.assertEqual(entry.revoked_by, ("revocation",))
        self.assertEqual(len(self.states.get_update_history("subject-1")), 4)

    def test_correction_of_a_correction_is_marked_superseded(self) -> None:
        target = _event("target", self.now)
        correction = _event(
            "correction",
            self.now + timedelta(minutes=1),
            classification=EventClassification.CORRECTION,
            references=[EventReference("target", "subject-1", EventRelationType.CORRECTS)],
        )
        correction_of_correction = _event(
            "correction-2",
            self.now + timedelta(minutes=2),
            classification=EventClassification.CORRECTION,
            references=[
                EventReference("correction", "subject-1", EventRelationType.CORRECTS)
            ],
        )
        for event in (target, correction, correction_of_correction):
            self.apply(event)
        self.assertIs(
            self.timeline.rebuild("subject-1").get("correction").status,
            TimelineEventStatus.SUPERSEDED,
        )

    def test_projection_rejects_forward_reference_even_if_target_exists_later(self) -> None:
        target = _event("target", self.now)
        self.apply(target)
        correction = _event(
            "correction",
            self.now + timedelta(minutes=1),
            classification=EventClassification.CORRECTION,
            references=[EventReference("target", "subject-1", EventRelationType.CORRECTS)],
        )
        self.apply(correction)
        reversed_history = list(reversed(self.states.get_update_history("subject-1")))
        with self.assertRaises(TimelineReferenceError):
            TimelineProjection.from_updates("subject-1", reversed_history)

    def test_chain_follows_correlation_and_event_references(self) -> None:
        first = _event("first", self.now, correlation_id="chain")
        second = _event("second", self.now + timedelta(minutes=1), correlation_id="chain")
        correction = _event(
            "correction",
            self.now + timedelta(minutes=2),
            classification=EventClassification.CORRECTION,
            references=[EventReference("first", "subject-1", EventRelationType.CORRECTS)],
        )
        for event in (first, second, correction):
            self.apply(event)
        self.assertEqual(
            [item.event.event_id for item in self.timeline.chain("subject-1", "first")],
            ["first", "second", "correction"],
        )

    def test_restart_rebuild_is_identical_and_timeline_has_no_write_surface(self) -> None:
        self.apply(_event("first", self.now))
        before = [entry.event.canonical_hash() for entry in self.timeline.query("subject-1").entries]
        restarted = TimelineService(JsonSubjectStateRepository(self.temporary.name))
        after = [entry.event.canonical_hash() for entry in restarted.query("subject-1").entries]

        self.assertEqual(before, after)
        for forbidden in ("save", "update", "delete", "overwrite"):
            self.assertFalse(hasattr(restarted, forbidden))

    def test_versioned_golden_scenario_preserves_fact_intention_and_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = run_p03_golden_scenario(directory)
            restarted = TimelineService(JsonSubjectStateRepository(directory)).query(
                "p03-golden-subject", TimelineQuery(limit=50)
            )

            self.assertEqual(first.version, P03_GOLDEN_SCENARIO_VERSION)
            self.assertEqual(
                [entry.event.classification for entry in first.evening_entries],
                [EventClassification.INTENTION, EventClassification.FACT],
            )
            self.assertEqual(first.subject_state.relationship.current_status, "reconciled")
            self.assertEqual(first.subject_state.revision, 2)
            self.assertEqual(
                [entry.event.event_id for entry in first.all_entries],
                [entry.event.event_id for entry in restarted.entries],
            )
            self.assertEqual(len(first.all_entries), len({e.event.event_id for e in first.all_entries}))
            self.assertEqual(
                first.trace,
                (
                    ("day1-noodle-intention", "intention", 0),
                    ("day1-no-noodles-fact", "fact", 0),
                    ("day2-argument-fact", "fact", 0),
                    ("day2-conflict-state-change", "state_change", 1),
                    ("day2-reconciliation-fact", "fact", 1),
                    ("day2-reconciled-state-change", "state_change", 2),
                ),
            )


if __name__ == "__main__":
    unittest.main()
