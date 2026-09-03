from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from continuity_engine.domain.context_routing import (
    ContextPartition,
    ContextRouteResult,
    ContextSourceBatch,
    ContextSourceCandidate,
)
from continuity_engine.domain.perception import (
    CurrentFocus,
    Drive,
    DriveKind,
    DriveStrength,
    InteractionFrequencyTrend,
    MemoryImpact,
    MemoryInfluence,
    Observation,
    PerceptionResult,
    RelationshipDirection,
    RelationshipPerception,
    StateStability,
    TemporalMeaning,
    TemporalPerception,
)
from continuity_engine.services.context_router_service import (
    ContextRouterService,
    ContextSourceBinding,
    ContextSourceQuery,
    ContextSourceValidation,
    DerivedSummaryContextSource,
    EnginePrivateContextPermissionPolicy,
    MemoryContextSource,
    SubjectStateContextSource,
    TimelineContextSource,
)
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository

from .p04_memory_fixture import P04GoldenScenarioResult, run_p04_golden_scenario


P05_GOLDEN_SCENARIO_VERSION = "p05-context-router-golden-v1"


def _hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


@dataclass(frozen=True, slots=True)
class P05VersionedLocalFact:
    fact_id: str
    subject_id: str
    environment: str
    version: str
    content: str
    occurred_at: datetime
    permission_scope: str
    relevance: float
    tags: tuple[str, ...]


class P05LocalFactSource:
    """Versioned local test source; it is not an Event or fact authority."""

    source_id = "engine.local-fact-fixture"
    partition = ContextPartition.LOCAL_FACT

    def __init__(
        self,
        facts: list[P05VersionedLocalFact],
        *,
        source_id: str = "engine.local-fact-fixture",
    ) -> None:
        self.source_id = source_id
        self.facts = list(facts)
        self.retrieve_calls = 0
        self.requested_limits: list[int] = []
        self.revalidate_calls = 0
        self.mutate_before_revalidation = False

    def _source_version(self) -> str:
        return "v-" + _hash(
            [(item.fact_id, item.version, _hash(item.content)) for item in self.facts]
        ).removeprefix("sha256:")

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch:
        self.retrieve_calls += 1
        self.requested_limits.append(query.limit)
        ordered = sorted(self.facts, key=lambda item: (item.fact_id, item.version))
        return ContextSourceBatch(
            self.source_id,
            self.partition,
            self._source_version(),
            tuple(
                ContextSourceCandidate(
                    source_id=self.source_id,
                    partition=self.partition,
                    stable_id=item.fact_id,
                    subject_id=item.subject_id,
                    environment=item.environment,
                    version=item.version,
                    content_hash=_hash(item.content),
                    occurred_at=item.occurred_at,
                    permission_scope=item.permission_scope,
                    authority_label="VERSIONED_LOCAL_CANDIDATE",
                    relevance=item.relevance,
                    importance=0.5,
                    activation=0.0,
                    tags=item.tags,
                    scopes=("local-fact",),
                )
                for item in ordered[: query.limit]
            ),
        )

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation:
        del query
        self.revalidate_calls += 1
        if self.mutate_before_revalidation:
            self.mutate_before_revalidation = False
            first = self.facts[0]
            self.facts[0] = P05VersionedLocalFact(
                first.fact_id,
                first.subject_id,
                first.environment,
                "version:changed",
                first.content + " changed",
                first.occurred_at,
                first.permission_scope,
                first.relevance,
                first.tags,
            )
        current = next((item for item in self.facts if item.fact_id == candidate.stable_id), None)
        current_source_version = self._source_version()
        if current is None:
            return ContextSourceValidation(
                False, "SOURCE_MISSING", current_source_version, "missing", candidate.content_hash
            )
        content_hash = _hash(current.content)
        valid = (
            current_source_version == source_version
            and current.version == candidate.version
            and content_hash == candidate.content_hash
        )
        return ContextSourceValidation(
            valid,
            "SOURCE_VERIFIED" if valid else "STALE_SOURCE",
            current_source_version,
            current.version,
            content_hash,
        )


@dataclass(frozen=True, slots=True)
class P05GoldenScenarioResult:
    version: str
    p04: P04GoldenScenarioResult
    perception: PerceptionResult
    route: ContextRouteResult
    local_source: P05LocalFactSource
    subject_document_hash_before: str
    subject_document_hash_after: str
    memory_document_hash_before: str
    memory_document_hash_after: str


def build_p05_perception(p04: P04GoldenScenarioResult) -> PerceptionResult:
    state = p04.p03.subject_state
    now = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)
    relationship_memories = [
        item for item in p04.memories if item.kind.value == "relational"
    ]
    return PerceptionResult(
        perception_id="perception:p05:love",
        subject_id=state.subject_id,
        source_revision=state.revision,
        wake_session_id="wake:p05:love",
        wake_context_id="wake-context:p05:love",
        perceived_at=now,
        current_focus=CurrentFocus(
            topics=["relationship", "love"],
            unfinished_items=[],
            summary="The user said 我爱你; route relationship context only.",
        ),
        temporal_perception=TemporalPerception(
            TemporalMeaning.RECENT,
            InteractionFrequencyTrend.STABLE,
            False,
            [],
            "The relationship interaction is recent.",
        ),
        relationship_perception=RelationshipPerception(
            RelationshipDirection.CLOSER,
            False,
            ["love", "reconciliation"],
            False,
            ["The user expressed affection."],
            "Relationship context is primary.",
        ),
        memory_influence=MemoryInfluence(
            impacts=[
                MemoryImpact(
                    item.memory_id,
                    item.content,
                    ["relationship"],
                    "The relationship memory is relevant.",
                    0.95,
                )
                for item in relationship_memories
            ],
            summary="Relevant relational memories are available.",
        ),
        observation=Observation(
            StateStability.STABLE,
            False,
            False,
            [],
            ["No contradiction was detected by Perception."],
        ),
        internal_drives=[
            Drive(
                DriveKind.INTEGRATE_MEMORY,
                "Integrate relevant relationship memory.",
                "perception-memory-influence",
                DriveStrength.NORMAL,
            )
        ],
        summary="Route relationship state, history, memory, and local facts.",
        recent_event_ids=[item.event.event_id for item in p04.p03.all_entries[-3:]],
        recent_update_ids=[item.update_id for item in p04.p03.all_entries[-3:]],
        viewed_memory_ids=[item.memory_id for item in relationship_memories],
        selected_memory_ids=[item.memory_id for item in relationship_memories],
        memory_request_id="memory-request:p05:love",
    )


def run_p05_golden_scenario(root: Path | str) -> P05GoldenScenarioResult:
    """Run P05 entirely against local TEST authorities and versioned candidates."""

    root_path = Path(root)
    p04 = run_p04_golden_scenario(root_path)
    perception = build_p05_perception(p04)
    state_repository = JsonSubjectStateRepository(root_path)
    memory_repository = JsonMemoryRepository(root_path, environment="TEST")
    state_path = state_repository._path_for(perception.subject_id)  # test evidence only
    memory_path = memory_repository._path(perception.subject_id)  # test evidence only
    subject_before = _hash(state_path.read_bytes().hex())
    memory_before = _hash(memory_path.read_bytes().hex())
    now = perception.perceived_at
    local_source = P05LocalFactSource(
        [
            P05VersionedLocalFact(
                "fact:relationship:love",
                perception.subject_id,
                "TEST",
                "version:1",
                "The user expressed affection with 我爱你.",
                now,
                "ENGINE_PRIVATE",
                1.0,
                ("relationship", "love"),
            ),
            P05VersionedLocalFact(
                "fact:project:irrelevant",
                perception.subject_id,
                "TEST",
                "version:1",
                "Unrelated project build details.",
                now,
                "ENGINE_PRIVATE",
                0.0,
                ("project",),
            ),
            P05VersionedLocalFact(
                "fact:secret:denied",
                perception.subject_id,
                "TEST",
                "version:1",
                "TOP SECRET AUTHORIZATION VALUE MUST NOT ENTER TRACE",
                now,
                "SECRET",
                1.0,
                ("relationship", "secret"),
            ),
        ]
    )
    router = ContextRouterService(
        [
            ContextSourceBinding(
                SubjectStateContextSource(state_repository, environment="TEST"),
                required=True,
            ),
            ContextSourceBinding(
                MemoryContextSource(memory_repository, environment="TEST")
            ),
            ContextSourceBinding(
                DerivedSummaryContextSource(memory_repository, environment="TEST")
            ),
            ContextSourceBinding(
                TimelineContextSource(
                    TimelineService(state_repository), environment="TEST"
                )
            ),
            ContextSourceBinding(local_source),
        ],
        permission_policy=EnginePrivateContextPermissionPolicy(),
    )
    route = router.route(
        perception,
        request_id="route:p05:golden:v1",
        environment="TEST",
    )
    subject_after = _hash(state_path.read_bytes().hex())
    memory_after = _hash(memory_path.read_bytes().hex())
    return P05GoldenScenarioResult(
        P05_GOLDEN_SCENARIO_VERSION,
        p04,
        perception,
        route,
        local_source,
        subject_before,
        subject_after,
        memory_before,
        memory_after,
    )
