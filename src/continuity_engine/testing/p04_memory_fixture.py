from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.memory import (
    DerivedSummary,
    MemoryEvidenceType,
    MemoryKind,
    MemoryRecord,
    MemoryTimeRange,
    MemoryVisibility,
)
from continuity_engine.services.memory_consolidation_service import (
    MemoryConsolidationService,
)
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository

from .p03_timeline_fixture import P03GoldenScenarioResult, run_p03_golden_scenario


P04_GOLDEN_SCENARIO_VERSION = "p04-memory-golden-v1"


@dataclass(frozen=True, slots=True)
class P04GoldenScenarioResult:
    version: str
    p03: P03GoldenScenarioResult
    memories: tuple[MemoryRecord, ...]
    relational_summary: DerivedSummary
    trace: tuple[tuple[str, str, int], ...]


def run_p04_golden_scenario(root: Path | str) -> P04GoldenScenarioResult:
    """Build P04 memory only from the local, versioned P03 golden history."""

    p03 = run_p03_golden_scenario(root)
    subject_id = p03.subject_state.subject_id
    now = datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc)
    repository = JsonMemoryRepository(root, environment="TEST")
    service = MemoryConsolidationService(repository, clock=lambda: now)
    selected = {
        "day1-noodle-intention": (
            MemoryKind.EPISODIC,
            MemoryEvidenceType.EXPERIENTIAL,
            "meal:day1:intention",
        ),
        "day1-no-noodles-fact": (
            MemoryKind.EPISODIC,
            MemoryEvidenceType.EXPERIENTIAL,
            "meal:day1:fact",
        ),
        "day2-argument-fact": (
            MemoryKind.RELATIONAL,
            MemoryEvidenceType.EXPERIENTIAL,
            "relationship:day2:argument",
        ),
        "day2-reconciliation-fact": (
            MemoryKind.RELATIONAL,
            MemoryEvidenceType.EXPERIENTIAL,
            "relationship:day2:reconciliation",
        ),
    }
    memories: list[MemoryRecord] = []
    trace: list[tuple[str, str, int]] = []
    for entry in p03.all_entries:
        event = entry.event
        if event.event_id not in selected:
            continue
        kind, evidence_type, scope = selected[event.event_id]
        record = MemoryRecord(
            memory_id=f"memory:{event.event_id}",
            subject_id=subject_id,
            environment="TEST",
            kind=kind,
            evidence_type=evidence_type,
            content=event.content,
            root_evidence_ids=[f"event:{event.event_id}"],
            source_event_ids=[event.event_id],
            occurred_at=event.occurred_at,
            observed_at=event.observed_at,
            recorded_at=event.recorded_at,
            consolidated_at=now,
            confidence=0.9,
            importance=0.8 if kind is MemoryKind.RELATIONAL else 0.6,
            activation=0.0,
            scope=scope,
            time_range=MemoryTimeRange(event.occurred_at, event.occurred_at),
            tags=[event.classification.value, "synthetic", P04_GOLDEN_SCENARIO_VERSION],
            visibility=MemoryVisibility.ENGINE_PRIVATE,
            relation_relevance=0.9 if kind is MemoryKind.RELATIONAL else 0.1,
            emotional_weight=0.7 if "argument" in event.event_id else 0.2,
            consolidation_id=f"consolidation:{event.event_id}",
        )
        result = service.consolidate(record)
        memories.append(result.memory)
        trace.append(
            (
                result.memory.memory_id,
                result.memory.kind.value,
                result.memory.unique_evidence_count,
            )
        )
    relationship_ids = [
        item.memory_id for item in memories if item.kind is MemoryKind.RELATIONAL
    ]
    summary = service.generate_summary(
        subject_id,
        summary_id="summary:relationship:day2",
        summary_type="relationship.day",
        scope="relationship:day2",
        source_memory_ids=relationship_ids,
        confidence=0.9,
    )
    return P04GoldenScenarioResult(
        version=P04_GOLDEN_SCENARIO_VERSION,
        p03=p03,
        memories=tuple(memories),
        relational_summary=summary,
        trace=tuple(trace),
    )
