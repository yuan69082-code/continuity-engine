from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from continuity_engine.domain.context_routing import (
    CandidateDecision,
    CandidateDecisionStatus,
    CandidateManifest,
    ContextCandidateReference,
    ContextPartition,
    ContextPartitionRequest,
    ContextRouteResult,
    ContextRouteStatus,
    ContextRoutingRequest,
    ContextSourceBatch,
    ContextSourceCandidate,
    ContextTrace,
    PartitionDecisionStatus,
    PartitionTrace,
    RetrievalBudget,
    RoutePlan,
    RoutingSignal,
    SourceTrace,
    hash_signal,
)
from continuity_engine.domain.errors import (
    ContinuityEngineError,
    ContextRoutingSourceError,
    ContextRoutingValidationError,
)
from continuity_engine.domain.memory import (
    DerivedSummaryStatus,
    MemoryKind,
    MemoryStatus,
    MemoryTemperature,
    MemoryVisibility,
)
from continuity_engine.domain.perception import (
    PerceptionResult,
    RelationshipDirection,
    StateStability,
    TemporalMeaning,
)
from continuity_engine.domain.timeline import TimelineEventStatus
from continuity_engine.storage.base import MemoryRepository, SubjectStateRepository

from .timeline_service import TimelineService


_TERM = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")
_IMPLEMENTED_PARTITIONS = (
    ContextPartition.SUBJECT_STATE,
    ContextPartition.MEMORY,
    ContextPartition.DERIVED_SUMMARY,
    ContextPartition.TIMELINE,
    ContextPartition.LOCAL_FACT,
)
_FUTURE_PARTITIONS = (
    ContextPartition.ATTENTION,
    ContextPartition.DESIRE,
    ContextPartition.CONFLICT,
    ContextPartition.SOMATIC,
    ContextPartition.EXPRESSION,
)
_PARTITION_PURPOSES: dict[ContextPartition, frozenset[str]] = {
    ContextPartition.MEMORY: frozenset({"memory", "relationship"}),
    ContextPartition.DERIVED_SUMMARY: frozenset({"memory", "relationship"}),
    ContextPartition.TIMELINE: frozenset({"temporal", "relationship", "fact"}),
    ContextPartition.LOCAL_FACT: frozenset({"fact", "relationship"}),
    ContextPartition.ATTENTION: frozenset({"attention"}),
    ContextPartition.DESIRE: frozenset({"desire"}),
    ContextPartition.CONFLICT: frozenset({"conflict"}),
    ContextPartition.SOMATIC: frozenset({"somatic"}),
    ContextPartition.EXPRESSION: frozenset({"expression"}),
}


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _version_hash(value: object) -> str:
    return f"v-{_canonical_hash(value).removeprefix('sha256:')}"


def _terms(*values: object) -> tuple[str, ...]:
    result: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            result.update(_terms(*value))
            continue
        for item in _TERM.findall(str(value).casefold()):
            if item.strip():
                result.add(item)
    return tuple(sorted(result))


def _lexical_relevance(query_terms: Sequence[str], *values: object) -> float:
    expected = set(query_terms)
    if not expected:
        return 0.0
    actual = set(_terms(*values))
    return round(len(expected.intersection(actual)) / len(expected), 6)


@dataclass(frozen=True, slots=True)
class ContextSourceQuery:
    request_id: str
    subject_id: str
    environment: str
    source_revision: int
    routed_at: datetime
    purpose: tuple[str, ...]
    query_terms: tuple[str, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class ContextSourceValidation:
    valid: bool
    reason_code: str
    source_version: str
    candidate_version: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class ContextPermissionDecision:
    allowed: bool
    reason_code: str
    policy_version: str


class ContextCandidateSource(Protocol):
    source_id: str
    partition: ContextPartition

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch: ...

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation: ...


class ContextPermissionPolicy(Protocol):
    def authorize_source(
        self, request: ContextRoutingRequest, source_id: str, partition: ContextPartition
    ) -> ContextPermissionDecision: ...

    def authorize_candidate(
        self,
        request: ContextRoutingRequest,
        candidate: ContextSourceCandidate,
    ) -> ContextPermissionDecision: ...


@dataclass(frozen=True, slots=True)
class ContextSourceBinding:
    source: ContextCandidateSource
    required: bool = False


class EnginePrivateContextPermissionPolicy:
    """Narrow local policy for Engine-private, same-boundary P05 reads."""

    policy_version = "p05-engine-private-v1"

    def authorize_source(
        self, request: ContextRoutingRequest, source_id: str, partition: ContextPartition
    ) -> ContextPermissionDecision:
        del request, source_id, partition
        return ContextPermissionDecision(True, "SOURCE_AUTHORIZED", self.policy_version)

    def authorize_candidate(
        self,
        request: ContextRoutingRequest,
        candidate: ContextSourceCandidate,
    ) -> ContextPermissionDecision:
        if candidate.subject_id != request.subject_id:
            return ContextPermissionDecision(False, "CROSS_SUBJECT", self.policy_version)
        if candidate.environment != request.environment:
            return ContextPermissionDecision(False, "CROSS_ENVIRONMENT", self.policy_version)
        if candidate.permission_scope != MemoryVisibility.ENGINE_PRIVATE.value:
            return ContextPermissionDecision(False, "PERMISSION_DENIED", self.policy_version)
        return ContextPermissionDecision(True, "CANDIDATE_AUTHORIZED", self.policy_version)


class SubjectStateContextSource:
    source_id = "engine.subject-state"
    partition = ContextPartition.SUBJECT_STATE

    def __init__(self, repository: SubjectStateRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch:
        state = self._repository.load(query.subject_id)
        if state.revision != query.source_revision:
            raise ContextRoutingSourceError("subject state revision changed before routing")
        document = state.to_dict()
        sections = (
            "identity",
            "relationship",
            "continuity",
            "temporal",
            "intentions",
            "emotion_state",
        )
        candidates = []
        for section in sections[: query.limit]:
            content = document[section]
            purpose_relevance = 0.0
            if section == "relationship" and "relationship" in query.purpose:
                purpose_relevance = 1.0
            elif section == "temporal" and "temporal" in query.purpose:
                purpose_relevance = 0.9
            elif section == "continuity" and "continuity" in query.purpose:
                purpose_relevance = 0.9
            elif section == "intentions" and "internal_drive" in query.purpose:
                purpose_relevance = 0.8
            elif section in {"identity", "emotion_state"} and "relationship" in query.purpose:
                purpose_relevance = 0.7
            candidates.append(
                ContextSourceCandidate(
                    source_id=self.source_id,
                    partition=self.partition,
                    stable_id=f"{query.subject_id}:{section}",
                    subject_id=query.subject_id,
                    environment=self._environment,
                    version=f"revision:{state.revision}",
                    content_hash=_canonical_hash(content),
                    occurred_at=state.temporal.updated_at,
                    permission_scope=MemoryVisibility.ENGINE_PRIVATE.value,
                    authority_label="SUBJECT_STATE_PARTITION",
                    relevance=max(
                        purpose_relevance,
                        _lexical_relevance(query.query_terms, section, content),
                    ),
                    importance=1.0 if section in {"identity", "relationship"} else 0.7,
                    activation=1.0,
                    tags=(section,),
                    scopes=(section,),
                )
            )
        return ContextSourceBatch(
            self.source_id,
            self.partition,
            f"revision:{state.revision}",
            tuple(candidates),
        )

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation:
        state = self._repository.load(query.subject_id)
        section = candidate.stable_id.rsplit(":", 1)[-1]
        document = state.to_dict()
        if section not in document:
            return ContextSourceValidation(
                False, "SOURCE_MISSING", f"revision:{state.revision}", "missing", candidate.content_hash
            )
        current_version = f"revision:{state.revision}"
        current_hash = _canonical_hash(document[section])
        valid = (
            source_version == current_version
            and candidate.version == current_version
            and candidate.content_hash == current_hash
        )
        return ContextSourceValidation(
            valid,
            "SOURCE_VERIFIED" if valid else "STALE_SOURCE",
            current_version,
            current_version,
            current_hash,
        )


class MemoryContextSource:
    source_id = "engine.memory"
    partition = ContextPartition.MEMORY

    def __init__(self, repository: MemoryRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def _query(self, query: ContextSourceQuery):
        preferred = (
            (MemoryKind.RELATIONAL,)
            if "relationship" in query.purpose
            else tuple(MemoryKind)
            if "memory" in query.purpose
            else ()
        )
        return self._repository.query_memories(
            query.subject_id,
            environment=query.environment,
            status=MemoryStatus.ACTIVE,
            visibility=MemoryVisibility.ENGINE_PRIVATE,
            excluded_temperatures=(MemoryTemperature.ARCHIVED,),
            query_terms=query.query_terms,
            preferred_kinds=preferred,
            limit=query.limit,
        )

    @staticmethod
    def _source_version(memories) -> str:
        return _version_hash(
            [(item.memory_id, item.revision, item.canonical_hash()) for item in memories]
        )

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch:
        ordered = self._query(query)
        source_version = _version_hash(
            [(item.memory_id, item.revision, item.canonical_hash()) for item in ordered]
        )
        return ContextSourceBatch(
            self.source_id,
            self.partition,
            source_version,
            tuple(
                ContextSourceCandidate(
                    source_id=self.source_id,
                    partition=self.partition,
                    stable_id=item.memory_id,
                    subject_id=item.subject_id,
                    environment=item.environment,
                    version=f"revision:{item.revision}",
                    content_hash=item.canonical_hash(),
                    occurred_at=item.occurred_at,
                    permission_scope=item.visibility.value,
                    authority_label="MEMORY_RECORD",
                    relevance=max(
                        0.9
                        if "relationship" in query.purpose
                        and item.kind.value == "relational"
                        else 0.6
                        if "memory" in query.purpose
                        else 0.0,
                        _lexical_relevance(
                            query.query_terms,
                            item.content,
                            item.tags,
                            item.scope,
                            item.kind.value,
                        ),
                    ),
                    importance=item.importance,
                    activation=item.activation,
                    tags=tuple(item.tags) + (item.kind.value, item.temperature.value),
                    scopes=(item.scope,),
                )
                for item in ordered
            ),
        )

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation:
        memories = self._query(query)
        current_source_version = self._source_version(memories)
        current = next(
            (item for item in memories if item.memory_id == candidate.stable_id), None
        )
        if current is None:
            return ContextSourceValidation(
                False, "SOURCE_MISSING", current_source_version, "missing", candidate.content_hash
            )
        version = f"revision:{current.revision}"
        content_hash = current.canonical_hash()
        valid = (
            source_version == current_source_version
            and version == candidate.version
            and content_hash == candidate.content_hash
            and current.status is MemoryStatus.ACTIVE
            and current.temperature is not MemoryTemperature.ARCHIVED
            and current.visibility is MemoryVisibility.ENGINE_PRIVATE
            and current.environment == query.environment
        )
        return ContextSourceValidation(
            valid,
            "SOURCE_VERIFIED" if valid else "STALE_OR_INELIGIBLE_SOURCE",
            current_source_version,
            version,
            content_hash,
        )


class DerivedSummaryContextSource:
    source_id = "engine.derived-summary"
    partition = ContextPartition.DERIVED_SUMMARY

    def __init__(self, repository: MemoryRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def _query(self, query: ContextSourceQuery):
        preferred = (
            ("relationship",)
            if "relationship" in query.purpose
            else ("memory",)
            if "memory" in query.purpose
            else ()
        )
        return self._repository.query_summaries(
            query.subject_id,
            environment=query.environment,
            status=DerivedSummaryStatus.ACTIVE,
            query_terms=query.query_terms,
            preferred_scope_terms=preferred,
            limit=query.limit,
        )

    @staticmethod
    def _source_version(summaries) -> str:
        return _version_hash(
            [
                (item.summary_id, item.summary_version, item.canonical_hash())
                for item in summaries
            ]
        )

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch:
        ordered = self._query(query)
        source_version = _version_hash(
            [
                (item.summary_id, item.summary_version, item.canonical_hash())
                for item in ordered
            ]
        )
        return ContextSourceBatch(
            self.source_id,
            self.partition,
            source_version,
            tuple(
                ContextSourceCandidate(
                    source_id=self.source_id,
                    partition=self.partition,
                    stable_id=item.summary_id,
                    subject_id=item.subject_id,
                    environment=item.environment,
                    version=f"version:{item.summary_version}",
                    content_hash=item.canonical_hash(),
                    occurred_at=item.time_range.end_at,
                    permission_scope=MemoryVisibility.ENGINE_PRIVATE.value,
                    authority_label="DERIVED_MEMORY_VIEW",
                    relevance=max(
                        0.9
                        if "relationship" in query.purpose
                        and "relationship" in item.scope.casefold()
                        else 0.6
                        if "memory" in query.purpose
                        else 0.0,
                        _lexical_relevance(
                            query.query_terms, item.content, item.scope, item.summary_type
                        ),
                    ),
                    importance=item.confidence,
                    activation=0.0,
                    tags=(item.summary_type,),
                    scopes=(item.scope,),
                )
                for item in ordered
            ),
        )

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation:
        summaries = self._query(query)
        current_source_version = self._source_version(summaries)
        current = next(
            (item for item in summaries if item.summary_id == candidate.stable_id), None
        )
        if current is None:
            return ContextSourceValidation(
                False, "SOURCE_MISSING", current_source_version, "missing", candidate.content_hash
            )
        version = f"version:{current.summary_version}"
        content_hash = current.canonical_hash()
        valid = (
            source_version == current_source_version
            and version == candidate.version
            and content_hash == candidate.content_hash
            and current.status is DerivedSummaryStatus.ACTIVE
            and current.environment == query.environment
        )
        return ContextSourceValidation(
            valid,
            "SOURCE_VERIFIED" if valid else "STALE_OR_INELIGIBLE_SOURCE",
            current_source_version,
            version,
            content_hash,
        )


class TimelineContextSource:
    source_id = "engine.timeline"
    partition = ContextPartition.TIMELINE

    def __init__(self, timeline: TimelineService, *, environment: str) -> None:
        self._timeline = timeline
        self._environment = environment

    def _entries(self, query: ContextSourceQuery):
        projection = self._timeline.rebuild(query.subject_id)
        eligible = [
            item
            for item in projection.entries
            if item.status is TimelineEventStatus.ACTIVE
        ]
        return tuple(
            sorted(
                eligible,
                key=lambda item: (
                    -max(
                        0.9
                        if "relationship" in query.purpose
                        and any(
                            section.value == "relationship"
                            for section in item.event.impact_scope
                        )
                        else 0.5
                        if "temporal" in query.purpose
                        else 0.0,
                        _lexical_relevance(
                            query.query_terms,
                            item.event.content,
                            item.event.event_type,
                            item.event.classification.value,
                            [section.value for section in item.event.impact_scope],
                        ),
                    ),
                    -item.event.occurred_at.timestamp(),
                    item.event.event_id,
                    item.update_id,
                ),
            )[: query.limit]
        )

    def retrieve(self, query: ContextSourceQuery) -> ContextSourceBatch:
        ordered = self._entries(query)
        source_version = _version_hash(
            [
                (item.update_id, item.event.event_id, item.status.value, item.event.canonical_hash())
                for item in ordered
            ]
        )
        return ContextSourceBatch(
            self.source_id,
            self.partition,
            source_version,
            tuple(
                ContextSourceCandidate(
                    source_id=self.source_id,
                    partition=self.partition,
                    stable_id=item.event.event_id,
                    subject_id=item.subject_id,
                    environment=self._environment,
                    version=f"update:{item.update_id}",
                    content_hash=item.event.canonical_hash(),
                    occurred_at=item.event.occurred_at,
                    permission_scope=MemoryVisibility.ENGINE_PRIVATE.value,
                    authority_label="TIMELINE_EVENT_PROJECTION",
                    relevance=max(
                        0.9
                        if "relationship" in query.purpose
                        and any(
                            section.value == "relationship"
                            for section in item.event.impact_scope
                        )
                        else 0.5
                        if "temporal" in query.purpose
                        else 0.0,
                        _lexical_relevance(
                            query.query_terms,
                            item.event.content,
                            item.event.event_type,
                            item.event.classification.value,
                            [section.value for section in item.event.impact_scope],
                        ),
                    ),
                    importance=0.5,
                    activation=0.0,
                    tags=tuple(
                        dict.fromkeys(
                            (item.event.classification.value, item.event.event_type)
                        )
                    ),
                    scopes=tuple(section.value for section in item.event.impact_scope),
                )
                for item in ordered
            ),
        )

    def revalidate(
        self,
        query: ContextSourceQuery,
        candidate: ContextSourceCandidate,
        source_version: str,
    ) -> ContextSourceValidation:
        entries = self._entries(query)
        current_source_version = _version_hash(
            [
                (item.update_id, item.event.event_id, item.status.value, item.event.canonical_hash())
                for item in entries
            ]
        )
        current = next(
            (item for item in entries if item.event.event_id == candidate.stable_id), None
        )
        if current is None:
            return ContextSourceValidation(
                False, "SOURCE_MISSING", current_source_version, "missing", candidate.content_hash
            )
        version = f"update:{current.update_id}"
        content_hash = current.event.canonical_hash()
        valid = (
            source_version == current_source_version
            and version == candidate.version
            and content_hash == candidate.content_hash
            and current.status is TimelineEventStatus.ACTIVE
        )
        return ContextSourceValidation(
            valid,
            "SOURCE_VERIFIED" if valid else "STALE_OR_INELIGIBLE_SOURCE",
            current_source_version,
            version,
            content_hash,
        )


class ContextRouterService:
    """P05 deterministic read-only router; it never composes Thinking context."""

    def __init__(
        self,
        sources: Sequence[ContextSourceBinding],
        *,
        permission_policy: ContextPermissionPolicy | None = None,
        enabled: bool = True,
        feature_gate_version: str = "p05-context-router-v1",
        minimum_relevance: float = 0.05,
    ) -> None:
        self._bindings = tuple(sources)
        self._permission = permission_policy or EnginePrivateContextPermissionPolicy()
        self._enabled = enabled
        self._feature_gate_version = feature_gate_version
        if not 0.0 <= minimum_relevance <= 1.0:
            raise ContextRoutingValidationError("minimum_relevance is invalid")
        self._minimum_relevance = minimum_relevance
        identities = [item.source.source_id for item in self._bindings]
        if len(identities) != len(set(identities)):
            raise ContextRoutingValidationError("context sources must have unique identities")

    def route(
        self,
        perception: PerceptionResult,
        *,
        request_id: str,
        environment: str,
        budget: RetrievalBudget | None = None,
        required_partitions: Sequence[ContextPartition] = (ContextPartition.SUBJECT_STATE,),
    ) -> ContextRouteResult:
        if not isinstance(perception, PerceptionResult):
            raise ContextRoutingValidationError("routing requires a PerceptionResult")
        purposes, signals, query_terms = self._derive_signals(perception)
        request = ContextRoutingRequest(
            request_id=request_id,
            perception_id=perception.perception_id,
            subject_id=perception.subject_id,
            environment=environment,
            source_revision=perception.source_revision,
            routed_at=perception.perceived_at,
            purpose=purposes,
            budget=budget or RetrievalBudget(),
        )
        required = {ContextPartition(item) for item in required_partitions}
        by_partition: dict[ContextPartition, list[ContextSourceBinding]] = {}
        for binding in self._bindings:
            by_partition.setdefault(binding.source.partition, []).append(binding)
            if binding.required:
                required.add(binding.source.partition)
        selected = self._select_partitions(request.purpose, required)
        allocations = self._allocate_budget(request.budget, selected, by_partition)
        partitions = tuple(
            ContextPartitionRequest(
                partition=partition,
                required=partition in required,
                source_ids=tuple(
                    sorted(item.source.source_id for item in by_partition.get(partition, []))
                ),
                candidate_limit=sum(
                    allocations.get(item.source.source_id, 0)
                    for item in by_partition.get(partition, [])
                ),
                reason_code=(
                    "PURPOSE_NOT_SELECTED"
                    if partition not in selected
                    else "SOURCE_NOT_CONFIGURED"
                    if not by_partition.get(partition)
                    else "RETRIEVAL_BUDGET_NOT_ALLOCATED"
                    if not any(
                        allocations.get(item.source.source_id, 0) > 0
                        for item in by_partition.get(partition, [])
                    )
                    else "REQUIRED_PARTITION_SELECTED"
                    if partition in required
                    else "PURPOSE_SELECTED"
                ),
                selected=partition in selected,
            )
            for partition in (*_IMPLEMENTED_PARTITIONS, *_FUTURE_PARTITIONS)
        )
        plan = RoutePlan(request, signals, partitions, self._feature_gate_version)
        if not self._enabled:
            return self._feature_gated(plan)
        return self._execute(plan, query_terms, by_partition, allocations)

    def _execute(
        self,
        plan: RoutePlan,
        query_terms: tuple[str, ...],
        by_partition: dict[ContextPartition, list[ContextSourceBinding]],
        allocations: dict[str, int],
    ) -> ContextRouteResult:
        request = plan.request
        ranked_pool: list[tuple[float, ContextSourceCandidate, tuple[str, ...]]] = []
        decisions: list[CandidateDecision] = []
        traces: list[PartitionTrace] = []
        source_traces: list[SourceTrace] = []
        required_failed = False
        required_denied = False
        route_failed = False
        evaluated_by_source: dict[str, int] = {}

        for partition_request in plan.partitions:
            bindings = by_partition.get(partition_request.partition, [])
            if not partition_request.selected:
                traces.append(
                    PartitionTrace(
                        partition_request.partition,
                        PartitionDecisionStatus.NOT_OPENED,
                        partition_request.reason_code,
                        0,
                        partition_request.source_ids,
                    )
                )
                source_traces.extend(
                    SourceTrace(
                        binding.source.source_id,
                        binding.source.partition,
                        PartitionDecisionStatus.NOT_OPENED,
                        "PARTITION_NOT_SELECTED",
                        0,
                        None,
                        getattr(
                            self._permission,
                            "policy_version",
                            "p05-permission-policy-opaque",
                        ),
                    )
                    for binding in sorted(
                        bindings, key=lambda item: item.source.source_id
                    )
                )
                continue
            if not bindings:
                traces.append(
                    PartitionTrace(
                        partition_request.partition,
                        PartitionDecisionStatus.UNAVAILABLE,
                        partition_request.reason_code,
                        partition_request.candidate_limit,
                        (),
                    )
                )
                if partition_request.required:
                    required_failed = True
                continue
            partition_candidates = 0
            partition_rejected = 0
            source_versions: list[tuple[str, str]] = []
            opened_sources: list[str] = []
            partition_status = PartitionDecisionStatus.OPENED
            partition_reason = "BOUNDED_READ_COMPLETE"
            for binding in sorted(bindings, key=lambda item: item.source.source_id):
                source = binding.source
                source_required = binding.required or partition_request.required
                limit = allocations.get(source.source_id, 0)
                if limit <= 0:
                    source_traces.append(
                        SourceTrace(
                            source.source_id,
                            source.partition,
                            PartitionDecisionStatus.NOT_OPENED,
                            "RETRIEVAL_BUDGET_NOT_ALLOCATED",
                            0,
                            None,
                            getattr(
                                self._permission,
                                "policy_version",
                                "p05-permission-policy-opaque",
                            ),
                        )
                    )
                    partition_status = PartitionDecisionStatus.NOT_OPENED
                    partition_reason = "RETRIEVAL_BUDGET_NOT_ALLOCATED"
                    if source_required:
                        required_failed = True
                    continue
                permission = self._permission.authorize_source(
                    request, source.source_id, source.partition
                )
                if not permission.allowed:
                    source_traces.append(
                        SourceTrace(
                            source.source_id,
                            source.partition,
                            PartitionDecisionStatus.REJECTED,
                            permission.reason_code,
                            limit,
                            None,
                            permission.policy_version,
                        )
                    )
                    partition_status = PartitionDecisionStatus.REJECTED
                    partition_reason = permission.reason_code
                    if source_required:
                        required_denied = True
                    continue
                query = ContextSourceQuery(
                    request.request_id,
                    request.subject_id,
                    request.environment,
                    request.source_revision,
                    request.routed_at,
                    request.purpose,
                    query_terms,
                    limit,
                )
                try:
                    batch = source.retrieve(query)
                except ContinuityEngineError:
                    source_traces.append(
                        SourceTrace(
                            source.source_id,
                            source.partition,
                            PartitionDecisionStatus.UNAVAILABLE,
                            "SOURCE_READ_FAILED",
                            limit,
                            None,
                            permission.policy_version,
                        )
                    )
                    partition_status = PartitionDecisionStatus.UNAVAILABLE
                    partition_reason = "SOURCE_READ_FAILED"
                    if source_required:
                        required_failed = True
                    continue
                if (
                    batch.source_id != source.source_id
                    or batch.partition is not source.partition
                    or len(batch.candidates) > limit
                ):
                    partition_candidates += len(batch.candidates)
                    source_traces.append(
                        SourceTrace(
                            source.source_id,
                            source.partition,
                            PartitionDecisionStatus.REJECTED,
                            "SOURCE_SCOPE_VIOLATION",
                            limit,
                            batch.source_version,
                            permission.policy_version,
                            len(batch.candidates),
                            0,
                            len(batch.candidates),
                        )
                    )
                    partition_status = PartitionDecisionStatus.REJECTED
                    partition_reason = "SOURCE_SCOPE_VIOLATION"
                    route_failed = True
                    if source_required:
                        required_failed = True
                    continue
                opened_sources.append(source.source_id)
                source_versions.append((source.source_id, batch.source_version))
                source_traces.append(
                    SourceTrace(
                        source.source_id,
                        source.partition,
                        PartitionDecisionStatus.OPENED,
                        "BOUNDED_READ_COMPLETE",
                        limit,
                        batch.source_version,
                        permission.policy_version,
                        len(batch.candidates),
                    )
                )
                for candidate in batch.candidates:
                    partition_candidates += 1
                    evaluated_by_source[source.source_id] = (
                        evaluated_by_source.get(source.source_id, 0) + 1
                    )
                    reason = self._candidate_boundary_reason(request, candidate)
                    candidate_permission = self._permission.authorize_candidate(
                        request, candidate
                    )
                    if reason is None and not candidate_permission.allowed:
                        reason = candidate_permission.reason_code
                    if reason is None:
                        try:
                            validation = source.revalidate(
                                query, candidate, batch.source_version
                            )
                        except ContinuityEngineError:
                            reason = "SOURCE_REVALIDATION_FAILED"
                            if source_required:
                                required_failed = True
                        else:
                            if not validation.valid:
                                reason = validation.reason_code
                                if source_required:
                                    required_failed = True
                    if reason is not None and source_required:
                        required_failed = True
                    score = self._score(candidate, request.routed_at)
                    if reason is None and candidate.relevance < self._minimum_relevance:
                        reason = "BELOW_RELEVANCE_THRESHOLD"
                    if reason is not None:
                        partition_rejected += 1
                        decisions.append(
                            CandidateDecision(
                                candidate.source_id,
                                candidate.partition,
                                candidate.stable_id,
                                CandidateDecisionStatus.REJECTED,
                                reason,
                                score,
                            )
                        )
                        continue
                    ranked_pool.append(
                        (
                            score,
                            candidate,
                            (
                                "PURPOSE_RELEVANCE",
                                "RECENCY",
                                "IMPORTANCE",
                                "ACTIVATION",
                                "STABLE_TIE_BREAK",
                            ),
                        )
                    )
            traces.append(
                PartitionTrace(
                    partition_request.partition,
                    partition_status,
                    partition_reason,
                    partition_request.candidate_limit,
                    tuple(opened_sources),
                    tuple(sorted(source_versions)),
                    partition_candidates,
                    0,
                    partition_rejected,
                )
            )

        ranked_pool.sort(
            key=lambda item: (
                -item[0],
                -item[1].occurred_at.timestamp(),
                item[1].source_id,
                item[1].stable_id,
                item[1].version,
            )
        )
        non_consumable = required_denied or required_failed or route_failed
        if non_consumable:
            selected = []
            for score, candidate, _ in ranked_pool:
                decisions.append(
                    CandidateDecision(
                        candidate.source_id,
                        candidate.partition,
                        candidate.stable_id,
                        CandidateDecisionStatus.REJECTED,
                        "ROUTE_NOT_CONSUMABLE_REQUIRED_SOURCE_FAILURE",
                        score,
                    )
                )
        else:
            selected = ranked_pool[: request.budget.total_candidate_limit]
            for score, candidate, _ in ranked_pool[
                request.budget.total_candidate_limit :
            ]:
                decisions.append(
                    CandidateDecision(
                        candidate.source_id,
                        candidate.partition,
                        candidate.stable_id,
                        CandidateDecisionStatus.REJECTED,
                        "RETRIEVAL_BUDGET_EXHAUSTED",
                        score,
                    )
                )
        references = tuple(
            ContextCandidateReference(
                candidate.source_id,
                candidate.partition,
                candidate.stable_id,
                candidate.subject_id,
                candidate.environment,
                candidate.version,
                candidate.content_hash,
                candidate.authority_label,
                rank,
                score,
                candidate.occurred_at,
                explanation,
            )
            for rank, (score, candidate, explanation) in enumerate(selected, start=1)
        )
        for score, candidate, _ in selected:
            decisions.append(
                CandidateDecision(
                    candidate.source_id,
                    candidate.partition,
                    candidate.stable_id,
                    CandidateDecisionStatus.RETAINED,
                    "VERIFIED_AND_RETAINED",
                    score,
                )
            )
        retained_by_source: dict[str, int] = {}
        rejected_by_source: dict[str, int] = {}
        for decision in decisions:
            by_source = (
                retained_by_source
                if decision.status is CandidateDecisionStatus.RETAINED
                else rejected_by_source
            )
            by_source[decision.source_id] = by_source.get(decision.source_id, 0) + 1
        source_traces = [
            SourceTrace(
                item.source_id,
                item.partition,
                item.status,
                item.reason_code,
                item.requested_limit,
                item.source_version,
                item.permission_policy_version,
                item.candidate_count,
                retained_by_source.get(item.source_id, item.retained_count),
                max(rejected_by_source.get(item.source_id, 0), item.rejected_count),
                evaluated_by_source.get(item.source_id, item.evaluated_count),
            )
            for item in source_traces
        ]
        partition_metrics: dict[ContextPartition, tuple[int, int, int, int]] = {}
        for item in source_traces:
            retrieved, retained, rejected, evaluated = partition_metrics.get(
                item.partition, (0, 0, 0, 0)
            )
            partition_metrics[item.partition] = (
                retrieved + item.candidate_count,
                retained + item.retained_count,
                rejected + item.rejected_count,
                evaluated + item.evaluated_count,
            )
        traces = [
            PartitionTrace(
                item.partition,
                item.status,
                item.reason_code,
                item.requested_limit,
                item.source_ids,
                item.source_versions,
                *partition_metrics.get(item.partition, (0, 0, 0, 0)),
            )
            for item in traces
        ]
        status = (
            ContextRouteStatus.REJECTED
            if required_denied
            else ContextRouteStatus.INCOMPLETE
            if required_failed or route_failed
            else ContextRouteStatus.COMPLETE
        )
        manifest = CandidateManifest(request.request_id, plan.canonical_hash(), references)
        trace = ContextTrace(
            trace_id=f"trace:{request.request_id}",
            request_id=request.request_id,
            perception_id=request.perception_id,
            subject_id=request.subject_id,
            source_revision=request.source_revision,
            routed_at=request.routed_at,
            purpose=request.purpose,
            route_plan_hash=plan.canonical_hash(),
            manifest_hash=manifest.manifest_hash or "",
            route_status=status,
            feature_gate_version=plan.feature_gate_version,
            partition_traces=tuple(traces),
            source_traces=tuple(source_traces),
            candidate_decisions=tuple(
                sorted(
                    decisions,
                    key=lambda item: (
                        item.partition.value,
                        item.source_id,
                        item.stable_id,
                        item.status.value,
                    ),
                )
            ),
            budget_limit=request.budget.total_candidate_limit,
            budget_used=sum(item.candidate_count for item in source_traces),
        )
        return ContextRouteResult(plan, manifest, trace)

    def _feature_gated(self, plan: RoutePlan) -> ContextRouteResult:
        manifest = CandidateManifest(plan.request.request_id, plan.canonical_hash(), ())
        traces = tuple(
            PartitionTrace(
                item.partition,
                PartitionDecisionStatus.FEATURE_GATED,
                "P05_FEATURE_GATE_DISABLED",
                0,
                (),
            )
            for item in plan.partitions
        )
        trace = ContextTrace(
            trace_id=f"trace:{plan.request.request_id}",
            request_id=plan.request.request_id,
            perception_id=plan.request.perception_id,
            subject_id=plan.request.subject_id,
            source_revision=plan.request.source_revision,
            routed_at=plan.request.routed_at,
            purpose=plan.request.purpose,
            route_plan_hash=plan.canonical_hash(),
            manifest_hash=manifest.manifest_hash or "",
            route_status=ContextRouteStatus.FEATURE_GATED,
            feature_gate_version=plan.feature_gate_version,
            partition_traces=traces,
            source_traces=tuple(
                SourceTrace(
                    source_id,
                    item.partition,
                    PartitionDecisionStatus.FEATURE_GATED,
                    "P05_FEATURE_GATE_DISABLED",
                    0,
                    None,
                    getattr(
                        self._permission,
                        "policy_version",
                        "p05-permission-policy-opaque",
                    ),
                )
                for item in plan.partitions
                for source_id in item.source_ids
            ),
            candidate_decisions=(),
            budget_limit=plan.request.budget.total_candidate_limit,
            budget_used=0,
        )
        return ContextRouteResult(plan, manifest, trace)

    @staticmethod
    def _select_partitions(
        purpose: tuple[str, ...],
        required: set[ContextPartition],
    ) -> set[ContextPartition]:
        selected = set(required)
        purpose_set = set(purpose)
        for partition, accepted_purposes in _PARTITION_PURPOSES.items():
            if purpose_set.intersection(accepted_purposes):
                selected.add(partition)
        return selected

    @staticmethod
    def _allocate_budget(
        budget: RetrievalBudget,
        selected: set[ContextPartition],
        by_partition: dict[ContextPartition, list[ContextSourceBinding]],
    ) -> dict[str, int]:
        ordered_sources = [
            binding.source.source_id
            for partition in (*_IMPLEMENTED_PARTITIONS, *_FUTURE_PARTITIONS)
            if partition in selected
            for binding in sorted(
                by_partition.get(partition, []),
                key=lambda item: item.source.source_id,
            )
        ]
        remaining = budget.total_candidate_limit
        allocations: dict[str, int] = {}
        for index, source_id in enumerate(ordered_sources):
            remaining_sources = len(ordered_sources) - index
            share = (
                (remaining + remaining_sources - 1) // remaining_sources
                if remaining_sources and remaining
                else 0
            )
            allocated = min(budget.limit_for(source_id), share)
            allocations[source_id] = allocated
            remaining -= allocated
        if sum(allocations.values()) > budget.total_candidate_limit:
            raise ContextRoutingValidationError(
                "retrieval budget allocation exceeds total_candidate_limit"
            )
        return allocations

    @staticmethod
    def _candidate_boundary_reason(
        request: ContextRoutingRequest,
        candidate: ContextSourceCandidate,
    ) -> str | None:
        if candidate.subject_id != request.subject_id:
            return "CROSS_SUBJECT"
        if candidate.environment != request.environment:
            return "CROSS_ENVIRONMENT"
        if not candidate.eligible:
            return candidate.invalid_reason or "SOURCE_INELIGIBLE"
        if candidate.status != "ACTIVE":
            return "SOURCE_NOT_ACTIVE"
        return None

    @staticmethod
    def _score(candidate: ContextSourceCandidate, now: datetime) -> float:
        age_days = max(
            0.0,
            (now.astimezone(timezone.utc) - candidate.occurred_at).total_seconds()
            / 86400,
        )
        recency = max(0.0, 1.0 - age_days / 365.0)
        return round(
            min(
                1.0,
                0.45 * candidate.relevance
                + 0.20 * recency
                + 0.20 * candidate.importance
                + 0.15 * candidate.activation,
            ),
            6,
        )

    @staticmethod
    def _derive_signals(
        perception: PerceptionResult,
    ) -> tuple[tuple[str, ...], tuple[RoutingSignal, ...], tuple[str, ...]]:
        purposes: set[str] = {"subject_state"}
        values: list[tuple[str, str, float]] = []

        focus_values = [
            *perception.current_focus.topics,
            *perception.current_focus.unfinished_items,
            perception.current_focus.summary,
        ]
        if focus_values:
            purposes.update({"topic", "continuity"})
            values.append(("focus", "focus", 0.9))
        relationship = perception.relationship_perception
        if (
            relationship.direction is not RelationshipDirection.UNCLEAR
            or relationship.unfinished_exchange
            or relationship.waiting_signal
            or relationship.sustained_topics
            or relationship.observations
        ):
            purposes.add("relationship")
            values.append(("relationship", "relationship", 1.0))
        temporal = perception.temporal_perception
        if (
            temporal.last_interaction_meaning is not TemporalMeaning.UNKNOWN
            or temporal.long_silence
            or temporal.approaching_important_dates
        ):
            purposes.add("temporal")
            values.append(("temporal", "temporal", 0.8))
        if perception.memory_influence.impacts:
            purposes.add("memory")
            values.append(("memory", "memory", 0.9))
        if (
            perception.observation.state_stability is StateStability.CHANGED
            or perception.observation.needs_more_information
            or perception.observation.conflicts
            or perception.external_facts
        ):
            purposes.add("fact")
            values.append(("observation", "fact", 0.8))
        if perception.internal_drives:
            purposes.add("internal_drive")
            values.append(("drive", "internal_drive", 0.7))
        query_terms = _terms(
            focus_values,
            relationship.sustained_topics,
            relationship.observations,
            relationship.summary,
            temporal.approaching_important_dates,
            temporal.meaning,
            [item.affected_scopes for item in perception.memory_influence.impacts],
            [item.influence_reason for item in perception.memory_influence.impacts],
            perception.observation.conflicts,
            perception.observation.notes,
            [item.tendency for item in perception.internal_drives],
            [item.source for item in perception.internal_drives],
            [item.observation_type for item in perception.external_facts],
        )
        signals = tuple(
            RoutingSignal(
                signal_id=f"signal:{perception.perception_id}:{index}",
                signal_kind=kind,
                value_hash=hash_signal(f"{label}:{'|'.join(query_terms)}"),
                weight=weight,
            )
            for index, (label, kind, weight) in enumerate(values, start=1)
        )
        return tuple(sorted(purposes)), signals, query_terms
