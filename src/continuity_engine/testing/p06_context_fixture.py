from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from continuity_engine.domain.context_composition import (
    ComposedContextSnapshot,
    ContextAuthority,
    ContextBudget,
    ContextCompositionResult,
)
from continuity_engine.domain.context_routing import (
    ContextCandidateReference,
    ContextPartition,
)
from continuity_engine.domain.errors import ContextCompositionSourceError
from continuity_engine.services.context_composer_service import (
    ContextComposerService,
    TrustedContextResolverBinding,
)
from continuity_engine.services.context_material_resolvers import (
    DerivedSummaryMaterialResolver,
    ExactContextPayload,
    MemoryMaterialResolver,
    SubjectStateMaterialResolver,
    TimelineMaterialResolver,
)
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository

from .p05_context_fixture import (
    P05GoldenScenarioResult,
    P05LocalFactSource,
    run_p05_golden_scenario,
)


P06_GOLDEN_SCENARIO_VERSION = "p06-context-composer-golden-v1"


def _hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class P06LocalFactMaterialResolver:
    """Exact TEST resolver; local candidates remain retrieved_candidate authority."""

    partition = ContextPartition.LOCAL_FACT

    def __init__(self, source: P05LocalFactSource) -> None:
        self._source = source
        self.source_id = source.source_id
        self.resolve_calls = 0

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload:
        self.resolve_calls += 1
        if (
            reference.source_id != self.source_id
            or reference.partition is not self.partition
        ):
            raise ContextCompositionSourceError("MATERIAL_PROVENANCE_INVALID")
        fact = next(
            (item for item in self._source.facts if item.fact_id == reference.stable_id),
            None,
        )
        if fact is None:
            raise ContextCompositionSourceError("SOURCE_MISSING")
        if fact.subject_id != reference.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        if fact.environment != reference.environment:
            raise ContextCompositionSourceError("SOURCE_ENVIRONMENT_MISMATCH")
        if fact.permission_scope != "ENGINE_PRIVATE":
            raise ContextCompositionSourceError("SOURCE_VISIBILITY_DENIED")
        if fact.version != reference.version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if _hash(fact.content) != reference.content_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        return ExactContextPayload(
            self.source_id,
            self.partition,
            fact.fact_id,
            fact.subject_id,
            fact.environment,
            fact.version,
            _hash(fact.content),
            fact.occurred_at,
            fact.content,
            0.5,
            (f"test-local-fact:{fact.fact_id}:{fact.version}",),
        )


class P06TestThinkingConsumer:
    """Test-only proof that a Thinking consumer can see Authority without a Provider."""

    def consume(self, snapshot: ComposedContextSnapshot) -> tuple[tuple[str, str], ...]:
        return tuple(
            (item.authority.value, item.stable_source_id)
            for item in snapshot.fragments
        )


@dataclass(frozen=True, slots=True)
class P06GoldenScenarioResult:
    version: str
    p05: P05GoldenScenarioResult
    composition: ContextCompositionResult
    local_resolver: P06LocalFactMaterialResolver
    consumer_view: tuple[tuple[str, str], ...]
    subject_document_hash_before: str
    subject_document_hash_after: str
    memory_document_hash_before: str
    memory_document_hash_after: str


def build_p06_composer(
    root: Path | str,
    p05: P05GoldenScenarioResult,
    *,
    enabled: bool = True,
) -> tuple[ContextComposerService, P06LocalFactMaterialResolver]:
    root_path = Path(root)
    state_repository = JsonSubjectStateRepository(root_path)
    memory_repository = JsonMemoryRepository(root_path, environment="TEST")
    local = P06LocalFactMaterialResolver(p05.local_source)
    composer = ContextComposerService(
        [
            TrustedContextResolverBinding(
                SubjectStateMaterialResolver(state_repository, environment="TEST"),
                ContextAuthority.CONFIRMED_STATE,
                "subject_state_section",
                required=True,
            ),
            TrustedContextResolverBinding(
                MemoryMaterialResolver(memory_repository, environment="TEST"),
                ContextAuthority.CONFIRMED_MEMORY,
                "memory_record",
            ),
            TrustedContextResolverBinding(
                DerivedSummaryMaterialResolver(memory_repository, environment="TEST"),
                ContextAuthority.DERIVED_SUMMARY,
                "derived_summary",
            ),
            TrustedContextResolverBinding(
                TimelineMaterialResolver(
                    TimelineService(state_repository), environment="TEST"
                ),
                ContextAuthority.RAW_SOURCE,
                "timeline_event",
            ),
            TrustedContextResolverBinding(
                local,
                ContextAuthority.RETRIEVED_CANDIDATE,
                "versioned_local_candidate",
            ),
        ],
        clock=lambda: datetime(2026, 9, 3, 8, 0, tzinfo=timezone.utc),
        enabled=enabled,
    )
    return composer, local


def run_p06_golden_scenario(root: Path | str) -> P06GoldenScenarioResult:
    """Compose the P05 golden Manifest without writing or re-routing any source."""

    root_path = Path(root)
    p05 = run_p05_golden_scenario(root_path)
    state_repository = JsonSubjectStateRepository(root_path)
    memory_repository = JsonMemoryRepository(root_path, environment="TEST")
    state_path = state_repository._path_for(p05.perception.subject_id)  # test evidence
    memory_path = memory_repository._path(p05.perception.subject_id)  # test evidence
    state_before = _hash(state_path.read_bytes().hex())
    memory_before = _hash(memory_path.read_bytes().hex())
    composer, local = build_p06_composer(root_path, p05)
    # The Golden Scenario intentionally uses the supported upper fragment bound
    # so all five Authority classes can be observed in one deterministic proof.
    result = composer.compose(
        p05.route, budget=ContextBudget(core_fragment_limit=15, token_limit=2048)
    )
    state_after = _hash(state_path.read_bytes().hex())
    memory_after = _hash(memory_path.read_bytes().hex())
    if result.snapshot is None:
        raise AssertionError("P06 golden composition did not produce a snapshot")
    consumer_view = P06TestThinkingConsumer().consume(result.snapshot)
    return P06GoldenScenarioResult(
        P06_GOLDEN_SCENARIO_VERSION,
        p05,
        result,
        local,
        consumer_view,
        state_before,
        state_after,
        memory_before,
        memory_after,
    )
