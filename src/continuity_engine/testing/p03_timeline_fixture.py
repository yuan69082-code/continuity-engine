from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.action import ApprovedStateAction
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    EventClassification,
    EventEvidenceReference,
    EventReference,
    EventRelationType,
    EventSourceKind,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.errors import StateValidationError
from continuity_engine.domain.timeline import TimelineEntry, TimelineQuery
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


P03_GOLDEN_SCENARIO_VERSION = "p03-golden-scenario-v1"
P03_TIME_FIXTURE_VERSION = "p03-time-fixture-v1"


@dataclass(frozen=True, slots=True)
class P03TemporalFactFixture:
    """Versioned source-side time fixture; it is not an Engine Event authority."""

    fixture_version: str
    record_kind: str
    source_event_id: str
    occurred_at: datetime
    observed_at: datetime
    recorded_at: datetime
    content: str
    source: str = "continuity_engine.testing.p03_fixture"
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.fixture_version != P03_TIME_FIXTURE_VERSION:
            raise StateValidationError("unsupported P03 temporal fixture version")
        if self.record_kind not in {"fact", "observation", "intention"}:
            raise StateValidationError("unsupported P03 temporal fixture record_kind")
        for value, name in (
            (self.source_event_id, "source_event_id"),
            (self.content, "content"),
            (self.source, "source"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise StateValidationError(f"P03 fixture {name} must be non-empty")


class P03LocalEventFixtureAdapter:
    """Explicitly adapt a test fixture to an Event without persisting either one."""

    def to_event(self, fixture: P03TemporalFactFixture, *, event_id: str) -> Event:
        if not isinstance(fixture, P03TemporalFactFixture):
            raise StateValidationError("P03 fixture adapter requires P03TemporalFactFixture")
        classification = EventClassification(fixture.record_kind)
        return Event.create(
            event_id=event_id,
            occurred_at=fixture.occurred_at,
            observed_at=fixture.observed_at,
            recorded_at=fixture.recorded_at,
            source=fixture.source,
            source_kind=EventSourceKind.TEST,
            source_event_id=fixture.source_event_id,
            correlation_id=fixture.correlation_id,
            event_type=fixture.record_kind,
            classification=classification,
            content=fixture.content,
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Explicitly adapt a versioned synthetic P03 time fixture.",
            evidence=[
                EventEvidenceReference(
                    evidence_id=fixture.source_event_id,
                    evidence_type="synthetic_fixture",
                    source=fixture.fixture_version,
                )
            ],
            metadata={"synthetic": True, "fixtureVersion": fixture.fixture_version},
        )


class _MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


@dataclass(frozen=True, slots=True)
class P03GoldenScenarioResult:
    version: str
    subject_state: SubjectState
    evening_entries: tuple[TimelineEntry, ...]
    all_entries: tuple[TimelineEntry, ...]
    trace: tuple[tuple[str, str, int], ...]


def run_p03_golden_scenario(root: Path | str) -> P03GoldenScenarioResult:
    """Run the versioned, local-only P03 golden timeline scenario."""

    zone = timezone(timedelta(hours=8))
    day1 = datetime(2026, 8, 3, 0, 0, tzinfo=zone)
    clock = _MutableClock(day1.astimezone(timezone.utc))
    repository = JsonSubjectStateRepository(root)
    states = SubjectStateService(repository, clock=clock)
    timeline = TimelineService(repository)
    actions = ActionEvolutionService(states, clock=clock)
    subject_id = "p03-golden-subject"
    states.create(subject_id)

    trace: list[tuple[str, str, int]] = []
    fixture_adapter = P03LocalEventFixtureAdapter()

    def historical(
        event_id: str,
        *,
        occurred_at: datetime,
        content: str,
        classification: EventClassification,
        source_event_id: str,
    ) -> Event:
        observed_at = occurred_at + timedelta(minutes=1)
        recorded_at = observed_at + timedelta(minutes=1)
        clock.current = recorded_at.astimezone(timezone.utc)
        event = fixture_adapter.to_event(
            P03TemporalFactFixture(
                fixture_version=P03_TIME_FIXTURE_VERSION,
                record_kind=classification.value,
                source_event_id=source_event_id,
                occurred_at=occurred_at,
                observed_at=observed_at,
                recorded_at=recorded_at,
                content=content,
                correlation_id="p03-golden-chain",
            ),
            event_id=event_id,
        )
        result = states.apply_event(subject_id, event)
        trace.append((event.event_id, event.classification.value, result.state.revision))
        return event

    def relationship_action(
        event_id: str,
        *,
        occurred_at: datetime,
        observed_at: datetime,
        recorded_at: datetime,
        status: str,
        cause: Event,
    ) -> None:
        clock.current = recorded_at.astimezone(timezone.utc)
        current = states.load(subject_id)
        update = actions.evolve(
            ApprovedStateAction(
                action_session_id=f"action:{event_id}",
                decision_id=f"decision:{event_id}",
                plan_id=f"plan:{event_id}",
                subject_id=subject_id,
                expected_revision=current.revision,
                think_session_id=f"think:{event_id}",
                wake_session_id=f"wake:{event_id}",
                perception_id=f"perception:{event_id}",
                thinking_result_id=f"thinking-result:{event_id}",
                result_summary=f"Set relationship state to {status}.",
                rationale_summary="Apply a synthetic Action-Gate-approved state change.",
                mutations=[
                    StateMutation(
                        field_path="relationship.current_status",
                        operation=ChangeOperation.SET,
                        value=status,
                        reason="Reflect the latest approved relationship state.",
                    )
                ],
            ),
            event_id=event_id,
            occurred_at=occurred_at,
            observed_at=observed_at,
            recorded_at=recorded_at,
            correlation_id="p03-golden-chain",
            references=[
                EventReference(
                    target_event_id=cause.event_id,
                    target_subject_id=subject_id,
                    relation_type=EventRelationType.CAUSED_BY,
                )
            ],
            metadata={"synthetic": True, "fixtureVersion": P03_GOLDEN_SCENARIO_VERSION},
        )
        assert update is not None
        trace.append((update.event.event_id, update.event.classification.value, update.after_revision))

    historical(
        "day1-noodle-intention",
        occurred_at=day1 + timedelta(hours=18),
        content="The subject intended to eat noodles.",
        classification=EventClassification.INTENTION,
        source_event_id="fixture:noodle-intention",
    )
    historical(
        "day1-no-noodles-fact",
        occurred_at=day1 + timedelta(hours=21),
        content="It was confirmed that the subject did not eat noodles.",
        classification=EventClassification.FACT,
        source_event_id="fixture:no-noodles-fact",
    )
    argument = historical(
        "day2-argument-fact",
        occurred_at=day1 + timedelta(days=1, hours=15),
        content="An argument occurred.",
        classification=EventClassification.FACT,
        source_event_id="fixture:argument-fact",
    )
    relationship_action(
        "day2-conflict-state-change",
        occurred_at=day1 + timedelta(days=1, hours=15, minutes=3),
        observed_at=day1 + timedelta(days=1, hours=15, minutes=4),
        recorded_at=day1 + timedelta(days=1, hours=15, minutes=5),
        status="conflict",
        cause=argument,
    )
    reconciliation = historical(
        "day2-reconciliation-fact",
        occurred_at=day1 + timedelta(days=1, hours=21),
        content="A reconciliation was completed.",
        classification=EventClassification.FACT,
        source_event_id="fixture:reconciliation-fact",
    )
    relationship_action(
        "day2-reconciled-state-change",
        occurred_at=day1 + timedelta(days=1, hours=21, minutes=3),
        observed_at=day1 + timedelta(days=1, hours=21, minutes=4),
        recorded_at=day1 + timedelta(days=1, hours=21, minutes=5),
        status="reconciled",
        cause=reconciliation,
    )

    evening = timeline.query(
        subject_id,
        TimelineQuery(
            start_at=day1 + timedelta(hours=18),
            end_at=day1 + timedelta(hours=23, minutes=59, seconds=59),
            limit=50,
        ),
    )
    all_entries = timeline.query(subject_id, TimelineQuery(limit=50)).entries
    return P03GoldenScenarioResult(
        version=P03_GOLDEN_SCENARIO_VERSION,
        subject_state=states.load(subject_id),
        evening_entries=evening.entries,
        all_entries=all_entries,
        trace=tuple(trace),
    )
