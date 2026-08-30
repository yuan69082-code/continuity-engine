import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.action import ApprovedStateAction
from continuity_engine.domain.errors import (
    EventIdentityConflictError,
    EventReferenceError,
    StateEvolutionError,
    StateValidationError,
)
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    EventClassification,
    EventEvidenceReference,
    EventReference,
    EventRelationType,
    EventSourceKind,
    EventTimeBasis,
    StateMutation,
    StateSection,
)
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p03_timeline_fixture import (
    P03LocalEventFixtureAdapter,
    P03TemporalFactFixture,
    P03_TIME_FIXTURE_VERSION,
)


UTC = timezone.utc


class _MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.current


def _relationship_mutation(reason: str) -> StateMutation:
    return StateMutation(
        "relationship.current_status",
        ChangeOperation.SET,
        "conflict",
        reason,
    )


def _explicit_state_change_event(
    event_id: str,
    occurred_at: datetime,
    *,
    recorded_at: datetime,
    value: str,
) -> Event:
    return Event.create(
        event_id=event_id,
        occurred_at=occurred_at,
        observed_at=occurred_at + timedelta(minutes=1),
        recorded_at=recorded_at,
        source="p03-test-source",
        source_kind=EventSourceKind.TEST,
        source_event_id=f"source:{event_id}",
        correlation_id="p03-replay-chain",
        event_type=EventClassification.STATE_CHANGE.value,
        classification=EventClassification.STATE_CHANGE,
        content=f"Apply {value} through an explicit state change.",
        impact_scope=[StateSection.CONTINUITY],
        mutations=[
            StateMutation(
                "continuity.current_focus",
                ChangeOperation.APPEND,
                value,
                "Exercise exact replay with an authoritative state change.",
            )
        ],
        reason="Exercise P03 exact replay across clock recovery.",
    )


def _historical_event(
    event_id: str,
    occurred_at: datetime,
    *,
    recorded_at: datetime | None = None,
    classification: EventClassification = EventClassification.FACT,
    references: list[EventReference] | None = None,
    mutations: list[StateMutation] | None = None,
) -> Event:
    observed_at = occurred_at + timedelta(minutes=1)
    final_recorded_at = recorded_at or observed_at + timedelta(minutes=1)
    return Event.create(
        event_id=event_id,
        occurred_at=occurred_at,
        observed_at=observed_at,
        recorded_at=final_recorded_at,
        source="p03-test-source",
        source_kind=EventSourceKind.TEST,
        source_event_id=f"source:{event_id}",
        correlation_id="p03-test-chain",
        event_type=classification.value,
        classification=classification,
        content=f"P03 event {event_id}",
        impact_scope=[StateSection.RELATIONSHIP if mutations else StateSection.TEMPORAL],
        mutations=mutations or [],
        reason="Exercise P03 event semantics.",
        evidence=[EventEvidenceReference(f"evidence:{event_id}", "test_fixture")],
        references=references or [],
    )


class P03EventSemanticsTests(unittest.TestCase):
    def test_explicit_three_times_are_normalized_to_utc(self) -> None:
        plus_eight = timezone(timedelta(hours=8))
        event = Event.create(
            event_id="three-times",
            occurred_at=datetime(2026, 8, 3, 18, 0, tzinfo=plus_eight),
            observed_at=datetime(2026, 8, 3, 18, 1, tzinfo=plus_eight),
            recorded_at=datetime(2026, 8, 3, 18, 2, tzinfo=plus_eight),
            source="test",
            event_type="fact",
            content="Three independently supplied times.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Test UTC normalization.",
            classification=EventClassification.FACT,
        )

        self.assertIs(event.time_basis, EventTimeBasis.EXPLICIT)
        self.assertEqual(event.to_dict()["occurred_at"], "2026-08-03T10:00:00Z")
        self.assertEqual(event.to_dict()["observed_at"], "2026-08-03T10:01:00Z")
        self.assertEqual(event.to_dict()["recorded_at"], "2026-08-03T10:02:00Z")

    def test_time_basis_cannot_claim_times_that_were_not_supplied(self) -> None:
        now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        with self.assertRaises(StateValidationError):
            Event.create(
                event_id="false-explicit",
                occurred_at=now,
                source="test",
                event_type="fact",
                content="Missing observed and recorded times.",
                impact_scope=[StateSection.TEMPORAL],
                mutations=[],
                reason="Reject a false time basis.",
                time_basis=EventTimeBasis.EXPLICIT,
            )
        with self.assertRaises(StateValidationError):
            Event.create(
                event_id="false-partial",
                occurred_at=now,
                observed_at=now,
                recorded_at=now,
                source="test",
                event_type="fact",
                content="All times were supplied.",
                impact_scope=[StateSection.TEMPORAL],
                mutations=[],
                reason="Reject a false time basis.",
                time_basis=EventTimeBasis.PARTIALLY_COALESCED,
            )

    def test_partial_and_legacy_time_basis_round_trip_truthfully(self) -> None:
        now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        partial = Event.create(
            event_id="partial",
            occurred_at=now,
            recorded_at=now + timedelta(minutes=2),
            source="test",
            event_type="legacy-compatible",
            content="Observed time is deterministically coalesced.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Test partial time compatibility.",
        )
        legacy = Event.create(
            event_id="legacy",
            occurred_at=now,
            source="test",
            event_type="legacy-compatible",
            content="Only occurrence time was available.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Test legacy time compatibility.",
        )

        self.assertIs(partial.time_basis, EventTimeBasis.PARTIALLY_COALESCED)
        self.assertIs(Event.from_dict(partial.to_dict()).time_basis, EventTimeBasis.PARTIALLY_COALESCED)
        self.assertIs(legacy.time_basis, EventTimeBasis.LEGACY_COALESCED)
        self.assertIs(Event.from_dict(legacy.to_dict()).time_basis, EventTimeBasis.LEGACY_COALESCED)

    def test_explicit_time_order_is_fail_closed(self) -> None:
        now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        with self.assertRaises(StateValidationError):
            _historical_event("invalid-order", now, recorded_at=now - timedelta(minutes=1))

    def test_old_event_json_is_backward_compatible_and_marked_legacy(self) -> None:
        old = {
            "event_id": "old-event",
            "occurred_at": "2026-08-03T10:00:00Z",
            "source": "legacy",
            "event_type": "state_update",
            "content": "Old persisted event.",
            "impact_scope": ["temporal"],
            "mutations": [],
            "reason": "Load old history.",
            "metadata": {},
        }
        restored = Event.from_dict(old)

        self.assertIs(restored.time_basis, EventTimeBasis.LEGACY_COALESCED)
        self.assertIs(restored.classification, EventClassification.LEGACY)
        self.assertEqual(restored.occurred_at, restored.observed_at)
        self.assertEqual(restored.observed_at, restored.recorded_at)

    def test_source_identity_and_internal_event_identity_remain_distinct(self) -> None:
        now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        event = _historical_event("engine-event-id", now)
        self.assertEqual(event.event_id, "engine-event-id")
        self.assertEqual(event.source_event_id, "source:engine-event-id")
        self.assertNotEqual(event.event_id, event.source_event_id)

    def test_versioned_fixture_requires_explicit_adaptation_and_does_not_auto_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectStateRepository(directory)
            service = SubjectStateService(
                repository,
                clock=lambda: self.now_for_fixture + timedelta(minutes=2),
            )
            service.create("subject-1")
            fixture = P03TemporalFactFixture(
                fixture_version=P03_TIME_FIXTURE_VERSION,
                record_kind="observation",
                source_event_id="platform-source-event",
                occurred_at=self.now_for_fixture,
                observed_at=self.now_for_fixture + timedelta(minutes=1),
                recorded_at=self.now_for_fixture + timedelta(minutes=2),
                content="A versioned source observation.",
            )
            event = P03LocalEventFixtureAdapter().to_event(
                fixture, event_id="internal-engine-event"
            )

            self.assertEqual(service.get_update_history("subject-1"), [])
            self.assertEqual(event.source_event_id, "platform-source-event")
            self.assertEqual(event.event_id, "internal-engine-event")
            service.apply_event("subject-1", event)
            self.assertEqual(len(service.get_update_history("subject-1")), 1)

    @property
    def now_for_fixture(self) -> datetime:
        return datetime(2026, 8, 3, 10, 0, tzinfo=UTC)

    def test_explicit_late_fact_can_append_history_but_cannot_mutate_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current_time = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: current_time + timedelta(hours=2),
            )
            service.create("subject-1")
            service.apply_event(
                "subject-1", _historical_event("current-fact", current_time)
            )
            late_occurred = current_time - timedelta(days=1)
            late_recorded = current_time + timedelta(hours=1)
            mutation = StateMutation(
                "relationship.current_status",
                ChangeOperation.SET,
                "conflict",
                "A late fact must not rewrite current state.",
            )
            with self.assertRaises(EventReferenceError):
                service.apply_event(
                    "subject-1",
                    _historical_event(
                        "late-mutating-fact",
                        late_occurred,
                        recorded_at=late_recorded,
                        mutations=[mutation],
                    ),
                )

            result = service.apply_event(
                "subject-1",
                _historical_event(
                    "late-historical-fact",
                    late_occurred,
                    recorded_at=late_recorded,
                ),
            )
            self.assertEqual(result.state.revision, 0)
            self.assertEqual(result.state.relationship.current_status, "")
            self.assertEqual(len(service.get_update_history("subject-1")), 2)

    def test_current_fact_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=10),
            )
            service.create("subject-1")
            event = _historical_event(
                "current-mutating-fact",
                now,
                mutations=[_relationship_mutation("A fact cannot mutate current state.")],
            )

            with self.assertRaises(EventReferenceError):
                service.apply_event("subject-1", event)

            self.assertEqual(service.load("subject-1").revision, 0)
            self.assertEqual(service.load("subject-1").relationship.current_status, "")
            self.assertEqual(service.get_update_history("subject-1"), [])

    def test_current_correction_and_revocation_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=20),
            )
            service.create("subject-1")
            service.apply_event("subject-1", _historical_event("target", now))

            cases = (
                (
                    EventClassification.CORRECTION,
                    EventRelationType.CORRECTS,
                ),
                (
                    EventClassification.REVOCATION,
                    EventRelationType.REVOKES,
                ),
            )
            for classification, relation in cases:
                with self.subTest(classification=classification.value):
                    event = _historical_event(
                        f"current-mutating-{classification.value}",
                        now + timedelta(minutes=3),
                        classification=classification,
                        references=[EventReference("target", "subject-1", relation)],
                        mutations=[
                            _relationship_mutation(
                                f"A {classification.value} cannot mutate current state."
                            )
                        ],
                    )
                    with self.assertRaises(EventReferenceError):
                        service.apply_event("subject-1", event)

            self.assertEqual(service.load("subject-1").revision, 0)
            self.assertEqual(service.load("subject-1").relationship.current_status, "")
            self.assertEqual(len(service.get_update_history("subject-1")), 1)

    def test_current_observation_and_intention_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=10),
            )
            service.create("subject-1")
            for classification in (
                EventClassification.OBSERVATION,
                EventClassification.INTENTION,
            ):
                with self.subTest(classification=classification.value):
                    event = _historical_event(
                        f"current-mutating-{classification.value}",
                        now,
                        classification=classification,
                        mutations=[
                            _relationship_mutation(
                                f"A {classification.value} cannot mutate current state."
                            )
                        ],
                    )
                    with self.assertRaises(EventReferenceError):
                        service.apply_event("subject-1", event)

            self.assertEqual(service.load("subject-1").revision, 0)
            self.assertEqual(service.get_update_history("subject-1"), [])

    def test_future_explicit_recorded_at_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            clock = _MutableClock(now + timedelta(minutes=2))
            service = SubjectStateService(JsonSubjectStateRepository(directory), clock=clock)
            service.create("subject-1")
            clock.calls = 0
            event = _historical_event(
                "future-recorded-at",
                now,
                recorded_at=now + timedelta(minutes=3),
            )

            with self.assertRaises(StateEvolutionError):
                service.apply_event("subject-1", event)

            self.assertEqual(clock.calls, 1)
            self.assertEqual(service.get_update_history("subject-1"), [])

    def test_explicit_recorded_at_equal_to_applied_at_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            applied_at = now + timedelta(minutes=2)
            clock = _MutableClock(applied_at)
            service = SubjectStateService(JsonSubjectStateRepository(directory), clock=clock)
            service.create("subject-1")
            clock.calls = 0

            result = service.apply_event(
                "subject-1",
                _historical_event("recorded-at-equal", now, recorded_at=applied_at),
            )

            self.assertEqual(clock.calls, 1)
            self.assertEqual(result.update.applied_at, applied_at)
            self.assertEqual(len(service.get_update_history("subject-1")), 1)

    def test_explicit_recorded_at_before_applied_at_uses_one_clock_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            applied_at = now + timedelta(minutes=5)
            clock = _MutableClock(applied_at)
            service = SubjectStateService(JsonSubjectStateRepository(directory), clock=clock)
            service.create("subject-1")
            clock.calls = 0

            result = service.apply_event(
                "subject-1",
                _historical_event(
                    "recorded-at-before",
                    now,
                    recorded_at=now + timedelta(minutes=2),
                ),
            )

            self.assertEqual(clock.calls, 1)
            self.assertEqual(result.update.applied_at, applied_at)
            self.assertLess(result.update.event.recorded_at, result.update.applied_at)

    def test_backward_clock_exact_replay_after_restart_skips_new_event_time_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            event = _explicit_state_change_event(
                "backward-clock-replay",
                now,
                recorded_at=now + timedelta(minutes=2),
                value="first focus",
            )
            first_clock = _MutableClock(now + timedelta(minutes=5))
            first_service = SubjectStateService(
                JsonSubjectStateRepository(directory), clock=first_clock
            )
            first_service.create("subject-1")
            first_result = first_service.apply_event("subject-1", event)

            replay_clock = _MutableClock(now - timedelta(hours=1))
            restarted = SubjectStateService(
                JsonSubjectStateRepository(directory), clock=replay_clock
            )
            replay = restarted.apply_event("subject-1", event)

            self.assertTrue(replay.idempotent_replay)
            self.assertEqual(replay.update.to_dict(), first_result.update.to_dict())
            self.assertEqual(replay.state.revision, 1)
            self.assertEqual(len(restarted.get_update_history("subject-1")), 1)
            self.assertEqual(replay_clock.calls, 0)

    def test_backward_clock_replay_after_later_revision_returns_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            first = _explicit_state_change_event(
                "backward-clock-first",
                now,
                recorded_at=now + timedelta(minutes=2),
                value="first focus",
            )
            second = _explicit_state_change_event(
                "backward-clock-second",
                now + timedelta(minutes=3),
                recorded_at=now + timedelta(minutes=5),
                value="second focus",
            )
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=10),
            )
            service.create("subject-1")
            first_result = service.apply_event("subject-1", first)
            service.apply_event("subject-1", second)

            replay_clock = _MutableClock(now - timedelta(hours=1))
            restarted = SubjectStateService(
                JsonSubjectStateRepository(directory), clock=replay_clock
            )
            replay = restarted.apply_event("subject-1", first)

            self.assertTrue(replay.idempotent_replay)
            self.assertEqual(replay.state.revision, 2)
            self.assertEqual(replay.update.after_revision, 1)
            self.assertEqual(replay.update.to_dict(), first_result.update.to_dict())
            self.assertEqual(len(restarted.get_update_history("subject-1")), 2)
            self.assertEqual(replay_clock.calls, 0)

    def test_backward_clock_conflicting_duplicate_reports_identity_conflict_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            original = _explicit_state_change_event(
                "backward-clock-conflict",
                now,
                recorded_at=now + timedelta(minutes=2),
                value="original focus",
            )
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=5),
            )
            service.create("subject-1")
            service.apply_event("subject-1", original)
            payload = original.to_dict()
            payload["content"] = "A conflicting canonical body."
            conflicting = Event.from_dict(payload)

            replay_clock = _MutableClock(now - timedelta(hours=1))
            restarted = SubjectStateService(
                JsonSubjectStateRepository(directory), clock=replay_clock
            )
            with self.assertRaises(EventIdentityConflictError):
                restarted.apply_event("subject-1", conflicting)

            self.assertEqual(replay_clock.calls, 0)
            self.assertEqual(restarted.load("subject-1").revision, 1)
            self.assertEqual(len(restarted.get_update_history("subject-1")), 1)

    def test_current_action_state_change_can_reference_a_late_historical_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
            clock = lambda: now + timedelta(hours=3)
            service = SubjectStateService(JsonSubjectStateRepository(directory), clock=clock)
            service.create("subject-1")
            service.apply_event("subject-1", _historical_event("newer-fact", now))
            late = _historical_event(
                "late-fact",
                now - timedelta(days=1),
                recorded_at=now + timedelta(hours=1),
            )
            service.apply_event("subject-1", late)
            action_service = ActionEvolutionService(service, clock=clock)
            update = action_service.evolve(
                ApprovedStateAction(
                    action_session_id="action-session",
                    decision_id="decision",
                    plan_id="plan",
                    subject_id="subject-1",
                    expected_revision=0,
                    think_session_id="think",
                    wake_session_id="wake",
                    perception_id="perception",
                    thinking_result_id="thinking-result",
                    result_summary="Apply current reconciled relationship state.",
                    rationale_summary="The Action Gate approved the current state change.",
                    mutations=[
                        StateMutation(
                            "relationship.current_status",
                            ChangeOperation.SET,
                            "reconciled",
                            "Apply the present approved relationship state.",
                        )
                    ],
                ),
                event_id="current-state-change",
                occurred_at=now + timedelta(hours=2),
                observed_at=now + timedelta(hours=2, minutes=1),
                recorded_at=now + timedelta(hours=2, minutes=2),
                references=[
                    EventReference(
                        "late-fact", "subject-1", EventRelationType.CAUSED_BY
                    )
                ],
            )

            self.assertIsNotNone(update)
            assert update is not None
            self.assertIs(update.event.classification, EventClassification.STATE_CHANGE)
            self.assertEqual(service.load("subject-1").relationship.current_status, "reconciled")
            self.assertEqual(service.load("subject-1").revision, 1)

    def test_missing_and_cross_subject_references_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now + timedelta(minutes=10),
            )
            service.create("subject-1")
            for target_subject in ("subject-1", "subject-2"):
                event = _historical_event(
                    f"correction-{target_subject}",
                    now,
                    classification=EventClassification.CORRECTION,
                    references=[
                        EventReference(
                            "missing-target", target_subject, EventRelationType.CORRECTS
                        )
                    ],
                )
                with self.assertRaises(EventReferenceError):
                    service.apply_event("subject-1", event)

    def test_repository_rejects_tampered_forward_reference_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
            repository = JsonSubjectStateRepository(directory)
            service = SubjectStateService(
                repository,
                clock=lambda: now + timedelta(hours=2),
            )
            service.create("subject-1")
            target = _historical_event("target", now)
            service.apply_event("subject-1", target)
            correction = _historical_event(
                "correction",
                now + timedelta(hours=1),
                classification=EventClassification.CORRECTION,
                references=[
                    EventReference("target", "subject-1", EventRelationType.CORRECTS)
                ],
            )
            service.apply_event("subject-1", correction)
            path = next(Path(directory).glob("*.json"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["updates"] = [payload["updates"][1], payload["updates"][0]]
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(StateValidationError):
                repository.list_update_records("subject-1")


if __name__ == "__main__":
    unittest.main()
