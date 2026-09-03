import inspect
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.context_routing import (
    CandidateDecisionStatus,
    ContextPartition,
    ContextRouteStatus,
    ContextRouteResult,
    ContextSourceBatch,
    ContextSourceCandidate,
    RetrievalBudget,
)
from continuity_engine.domain.errors import (
    ContextRoutingSourceError,
    ContextRoutingValidationError,
)
from continuity_engine.domain.events import (
    Event,
    EventClassification,
    EventReference,
    EventRelationType,
    EventSourceKind,
    StateSection,
)
from continuity_engine.domain.memory import (
    DerivedSummary,
    MemoryEvidenceType,
    MemoryKind,
    MemoryLineageType,
    MemoryRecord,
    MemoryTemperature,
    MemoryTimeRange,
    MemoryVisibility,
)
from continuity_engine.domain.perception import (
    CurrentFocus,
    InteractionFrequencyTrend,
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
    ContextPermissionDecision,
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
from continuity_engine.services.memory_consolidation_service import (
    MemoryConsolidationService,
)
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_ports import ThinkingProvider
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p04_memory_fixture import run_p04_golden_scenario
from continuity_engine.testing.p05_context_fixture import (
    P05LocalFactSource,
    P05VersionedLocalFact,
    build_p05_perception,
    run_p05_golden_scenario,
)


UTC = timezone.utc


class _DenySourcePolicy(EnginePrivateContextPermissionPolicy):
    def authorize_source(self, request, source_id, partition):
        del request, source_id, partition
        return ContextPermissionDecision(False, "SOURCE_PERMISSION_DENIED", "deny-v1")


class _DenyNamedSourcePolicy(EnginePrivateContextPermissionPolicy):
    def __init__(self, denied_source_id):
        self.denied_source_id = denied_source_id

    def authorize_source(self, request, source_id, partition):
        if source_id == self.denied_source_id:
            return ContextPermissionDecision(
                False, "SOURCE_PERMISSION_DENIED", "deny-named-v1"
            )
        return super().authorize_source(request, source_id, partition)


class _BrokenSource(P05LocalFactSource):
    def retrieve(self, query):
        del query
        raise ContextRoutingSourceError("synthetic bounded source failure")


class _OverReturningSource(P05LocalFactSource):
    def retrieve(self, query):
        return super().retrieve(replace(query, limit=query.limit + 1))


class _BoundedOnlyJsonMemoryRepository(JsonMemoryRepository):
    def __init__(self, root, *, environment):
        super().__init__(root, environment=environment)
        self.memory_query_limits = []
        self.summary_query_limits = []

    def list_memories(self, *args, **kwargs):
        raise AssertionError("P05 must not use unbounded list_memories")

    def list_summaries(self, *args, **kwargs):
        raise AssertionError("P05 must not use unbounded list_summaries")

    def query_memories(self, subject_id, **kwargs):
        self.memory_query_limits.append(kwargs["limit"])
        return super().query_memories(subject_id, **kwargs)

    def query_summaries(self, subject_id, **kwargs):
        self.summary_query_limits.append(kwargs["limit"])
        return super().query_summaries(subject_id, **kwargs)


class P05ContextRouterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.p04 = run_p04_golden_scenario(self.root)
        self.perception = build_p05_perception(self.p04)
        self.state_repository = JsonSubjectStateRepository(self.root)
        self.memory_repository = JsonMemoryRepository(self.root, environment="TEST")
        self.now = self.perception.perceived_at
        self._golden_index = 0

    def golden(self):
        self._golden_index += 1
        return run_p05_golden_scenario(
            self.root / f"p05-golden-{self._golden_index}"
        )

    def fact(
        self,
        fact_id,
        *,
        subject_id=None,
        environment="TEST",
        permission_scope="ENGINE_PRIVATE",
        relevance=1.0,
        content="relationship candidate",
    ):
        return P05VersionedLocalFact(
            fact_id,
            subject_id or self.perception.subject_id,
            environment,
            "version:1",
            content,
            self.now,
            permission_scope,
            relevance,
            ("relationship",),
        )

    def neutral_perception(self):
        perception = PerceptionResult.from_dict(self.perception.to_dict())
        perception.current_focus = CurrentFocus(
            ["continuity"], [], "Maintain the current continuity baseline."
        )
        perception.temporal_perception = TemporalPerception(
            TemporalMeaning.UNKNOWN,
            InteractionFrequencyTrend.STABLE,
            False,
            [],
            "No temporal lookup is required.",
        )
        perception.relationship_perception = RelationshipPerception(
            RelationshipDirection.UNCLEAR,
            False,
            [],
            False,
            [],
            "No relationship lookup is required.",
        )
        perception.memory_influence = MemoryInfluence(
            [], "No memory lookup is required."
        )
        perception.observation = Observation(
            StateStability.STABLE,
            False,
            False,
            [],
            ["No fact lookup is required."],
        )
        perception.internal_drives = []
        perception.summary = "Continue without opening optional context partitions."
        perception.external_facts = ()
        return perception

    def route_with_source(
        self,
        source,
        *,
        required=True,
        enabled=True,
        permission_policy=None,
        budget=None,
    ):
        return ContextRouterService(
            [ContextSourceBinding(source, required=required)],
            enabled=enabled,
            permission_policy=permission_policy,
        ).route(
            self.perception,
            request_id="route:test",
            environment="TEST",
            budget=budget,
            required_partitions=(ContextPartition.LOCAL_FACT,) if required else (),
        )

    def test_golden_scenario_routes_relationship_authorities(self):
        result = self.golden()
        self.assertEqual(result.route.trace.route_status, ContextRouteStatus.COMPLETE)
        partitions = {item.partition for item in result.route.manifest.candidates}
        self.assertTrue(
            {
                ContextPartition.SUBJECT_STATE,
                ContextPartition.MEMORY,
                ContextPartition.DERIVED_SUMMARY,
                ContextPartition.TIMELINE,
                ContextPartition.LOCAL_FACT,
            }.issubset(partitions)
        )
        identifiers = {item.stable_id for item in result.route.manifest.candidates}
        self.assertIn(f"{self.perception.subject_id}:relationship", identifiers)
        self.assertIn(f"{self.perception.subject_id}:identity", identifiers)
        self.assertIn(f"{self.perception.subject_id}:emotion_state", identifiers)
        self.assertIn("fact:relationship:love", identifiers)

    def test_golden_scenario_excludes_irrelevant_and_secret_candidates(self):
        result = self.golden()
        retained = {item.stable_id for item in result.route.manifest.candidates}
        rejected = {
            item.stable_id: item.reason_code
            for item in result.route.trace.candidate_decisions
            if item.status is CandidateDecisionStatus.REJECTED
        }
        self.assertNotIn("fact:project:irrelevant", retained)
        self.assertNotIn("fact:secret:denied", retained)
        self.assertEqual(
            rejected["fact:project:irrelevant"], "BELOW_RELEVANCE_THRESHOLD"
        )
        self.assertEqual(rejected["fact:secret:denied"], "PERMISSION_DENIED")
        serialized = json.dumps(result.route.to_dict(), ensure_ascii=False)
        self.assertNotIn("TOP SECRET AUTHORIZATION VALUE", serialized)

    def test_route_is_deterministic_across_new_router_instances(self):
        root = self.root / "deterministic"
        first = run_p05_golden_scenario(root)
        state_repository = JsonSubjectStateRepository(root)
        memory_repository = JsonMemoryRepository(root, environment="TEST")
        restarted = ContextRouterService(
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
                ContextSourceBinding(P05LocalFactSource(list(first.local_source.facts))),
            ]
        )
        second = restarted.route(
            first.perception,
            request_id="route:p05:golden:v1",
            environment="TEST",
        )
        self.assertEqual(first.route.to_dict(), second.to_dict())
        self.assertEqual(first.route.manifest.manifest_hash, second.manifest.manifest_hash)
        restored = ContextRouteResult.from_dict(
            json.loads(json.dumps(second.to_dict(), ensure_ascii=False))
        )
        self.assertEqual(restored.to_dict(), second.to_dict())

    def test_router_does_not_modify_subject_or_memory_authorities(self):
        result = self.golden()
        self.assertEqual(
            result.subject_document_hash_before, result.subject_document_hash_after
        )
        self.assertEqual(
            result.memory_document_hash_before, result.memory_document_hash_after
        )
        self.assertEqual(
            result.p04.p03.subject_state.revision,
            self.state_repository.load(self.perception.subject_id).revision,
        )

    def test_total_retrieval_budget_caps_candidates_without_fallback(self):
        first_source = P05LocalFactSource(
            [self.fact(f"fact:a:{i:02d}") for i in range(20)],
            source_id="engine.local-fact-a",
        )
        second_source = P05LocalFactSource(
            [self.fact(f"fact:b:{i:02d}") for i in range(20)],
            source_id="engine.local-fact-b",
        )
        result = ContextRouterService(
            [ContextSourceBinding(first_source), ContextSourceBinding(second_source)]
        ).route(
            self.perception,
            request_id="route:budget",
            environment="TEST",
            budget=RetrievalBudget(30),
            required_partitions=(),
        )
        self.assertEqual(len(result.manifest.candidates), 30)
        self.assertEqual(result.trace.budget_used, 30)
        self.assertEqual(first_source.requested_limits, [15])
        self.assertEqual(second_source.requested_limits, [15])
        self.assertEqual(
            sum(item.requested_limit for item in result.trace.source_traces), 30
        )
        self.assertEqual(
            sum(item.retrieved_count for item in result.trace.source_traces), 30
        )
        self.assertEqual(
            sum(item.evaluated_count for item in result.trace.source_traces), 30
        )
        self.assertEqual(
            sum(item.retained_count for item in result.trace.source_traces), 30
        )
        self.assertEqual(
            sum(item.rejected_count for item in result.trace.source_traces), 0
        )
        self.assertEqual((first_source.retrieve_calls, second_source.retrieve_calls), (1, 1))

    def test_neutral_continuity_opens_only_required_subject_state(self):
        optional_sources = []
        for partition in (
            ContextPartition.MEMORY,
            ContextPartition.DERIVED_SUMMARY,
            ContextPartition.TIMELINE,
            ContextPartition.LOCAL_FACT,
        ):
            source = P05LocalFactSource(
                [self.fact(f"fact:unselected:{partition.value}", relevance=1.0)],
                source_id=f"engine.unselected.{partition.value}",
            )
            source.partition = partition
            optional_sources.append(source)
        result = ContextRouterService(
            [
                ContextSourceBinding(
                    SubjectStateContextSource(
                        self.state_repository, environment="TEST"
                    ),
                    required=True,
                ),
                *(ContextSourceBinding(source) for source in optional_sources),
            ]
        ).route(
            self.neutral_perception(),
            request_id="route:neutral-continuity",
            environment="TEST",
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.COMPLETE)
        self.assertEqual(
            {item.partition for item in result.manifest.candidates},
            {ContextPartition.SUBJECT_STATE},
        )
        self.assertTrue(all(source.retrieve_calls == 0 for source in optional_sources))
        partitions = {item.partition: item for item in result.plan.partitions}
        traces = {item.partition: item for item in result.trace.partition_traces}
        for source in optional_sources:
            self.assertFalse(partitions[source.partition].selected)
            self.assertEqual(partitions[source.partition].candidate_limit, 0)
            self.assertEqual(
                traces[source.partition].status.value, "NOT_OPENED"
            )
            self.assertEqual(
                traces[source.partition].reason_code, "PURPOSE_NOT_SELECTED"
            )

    def test_required_source_denial_discards_optional_success_candidates(self):
        required = P05LocalFactSource(
            [self.fact("fact:required")], source_id="engine.required-fact"
        )
        optional = P05LocalFactSource(
            [self.fact("fact:optional")], source_id="engine.optional-fact"
        )
        result = ContextRouterService(
            [
                ContextSourceBinding(required, required=True),
                ContextSourceBinding(optional),
            ],
            permission_policy=_DenyNamedSourcePolicy(required.source_id),
        ).route(
            self.perception,
            request_id="route:required-denied-optional-success",
            environment="TEST",
            required_partitions=(ContextPartition.LOCAL_FACT,),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.REJECTED)
        self.assertEqual(result.manifest.candidates, ())
        self.assertEqual(required.retrieve_calls, 0)
        self.assertEqual(optional.retrieve_calls, 1)
        optional_trace = next(
            item
            for item in result.trace.source_traces
            if item.source_id == optional.source_id
        )
        self.assertEqual(optional_trace.retrieved_count, 1)
        self.assertEqual(optional_trace.evaluated_count, 1)
        self.assertEqual(optional_trace.retained_count, 0)
        self.assertEqual(optional_trace.rejected_count, 1)
        self.assertIn(
            "ROUTE_NOT_CONSUMABLE_REQUIRED_SOURCE_FAILURE",
            {item.reason_code for item in result.trace.candidate_decisions},
        )

    def test_memory_and_summary_sources_use_bounded_repository_queries(self):
        root = self.root / "bounded-memory-query"
        repository = _BoundedOnlyJsonMemoryRepository(root, environment="TEST")
        for index in range(40):
            occurred = self.now - timedelta(days=40 - index)
            memory = MemoryRecord(
                memory_id=f"memory:bounded:{index:02d}",
                subject_id=self.perception.subject_id,
                environment="TEST",
                kind=MemoryKind.RELATIONAL,
                evidence_type=MemoryEvidenceType.EXPERIENTIAL,
                content=f"relationship bounded memory {index:02d}",
                root_evidence_ids=[f"event:bounded-{index:02d}"],
                source_event_ids=[f"bounded-{index:02d}"],
                occurred_at=occurred,
                observed_at=occurred,
                recorded_at=occurred,
                consolidated_at=self.now,
                confidence=0.8,
                importance=0.8,
                activation=0.8,
                scope="relationship:bounded",
                time_range=MemoryTimeRange(occurred, occurred),
                consolidation_id=f"consolidation:bounded:{index:02d}",
                visibility=MemoryVisibility.ENGINE_PRIVATE,
            )
            repository.save_memory(memory)
            repository.save_summary(
                DerivedSummary(
                    summary_id=f"summary:bounded:{index:02d}",
                    subject_id=self.perception.subject_id,
                    environment="TEST",
                    summary_type="relationship",
                    scope="relationship:bounded",
                    time_range=MemoryTimeRange(occurred, occurred),
                    generated_at=self.now,
                    summary_version=1,
                    source_event_ids=[f"bounded-{index:02d}"],
                    source_memory_ids=[memory.memory_id],
                    source_message_ids=[],
                    root_evidence_ids=[f"event:bounded-{index:02d}"],
                    confidence=0.8,
                    content=f"relationship bounded summary {index:02d}",
                )
            )
        result = ContextRouterService(
            [
                ContextSourceBinding(
                    MemoryContextSource(repository, environment="TEST")
                ),
                ContextSourceBinding(
                    DerivedSummaryContextSource(repository, environment="TEST")
                ),
            ]
        ).route(
            self.perception,
            request_id="route:bounded-memory-summary",
            environment="TEST",
            budget=RetrievalBudget(30),
            required_partitions=(),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.COMPLETE)
        self.assertEqual(len(result.manifest.candidates), 30)
        self.assertTrue(repository.memory_query_limits)
        self.assertTrue(repository.summary_query_limits)
        self.assertEqual(set(repository.memory_query_limits), {15})
        self.assertEqual(set(repository.summary_query_limits), {15})
        self.assertEqual(
            sum(item.requested_limit for item in result.trace.source_traces), 30
        )

    def test_large_timeline_uses_recent_relevant_stable_window(self):
        service = SubjectStateService(
            self.state_repository, clock=lambda: self.now
        )
        for index in range(120):
            occurred = self.now - timedelta(minutes=120 - index)
            event = Event.create(
                event_id=f"event:p05:history:{index:03d}",
                occurred_at=occurred,
                observed_at=occurred,
                recorded_at=occurred,
                source="continuity_engine.testing.p05",
                event_type="relationship-history",
                classification=EventClassification.FACT,
                source_kind=EventSourceKind.TEST,
                content=(
                    "relationship recent marker"
                    if index == 119
                    else f"relationship history {index:03d}"
                ),
                impact_scope=[StateSection.RELATIONSHIP],
                mutations=[],
                reason="Exercise the bounded P05 Timeline routing window.",
            )
            service.apply_event(self.perception.subject_id, event)
        perception = PerceptionResult.from_dict(self.perception.to_dict())
        perception.source_revision = self.state_repository.load(
            self.perception.subject_id
        ).revision
        source = TimelineContextSource(
            TimelineService(self.state_repository), environment="TEST"
        )
        result = ContextRouterService([ContextSourceBinding(source)]).route(
            perception,
            request_id="route:large-timeline",
            environment="TEST",
            budget=RetrievalBudget(30),
            required_partitions=(ContextPartition.TIMELINE,),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.COMPLETE)
        retained = {item.stable_id for item in result.manifest.candidates}
        self.assertIn("event:p05:history:119", retained)
        timeline_trace = next(
            item
            for item in result.trace.source_traces
            if item.source_id == source.source_id
        )
        self.assertEqual(timeline_trace.requested_limit, 30)
        self.assertEqual(timeline_trace.retrieved_count, 30)
        self.assertEqual(timeline_trace.evaluated_count, 30)

    def test_per_source_limit_is_forwarded_and_enforced(self):
        source = P05LocalFactSource([self.fact(f"fact:{i:02d}") for i in range(20)])
        budget = RetrievalBudget(30, ((source.source_id, 5),))
        result = self.route_with_source(source, budget=budget)
        self.assertEqual(len(result.manifest.candidates), 5)
        trace = next(
            item
            for item in result.trace.partition_traces
            if item.partition is ContextPartition.LOCAL_FACT
        )
        self.assertEqual(trace.candidate_count, 5)

    def test_source_cannot_return_more_than_its_bounded_scope(self):
        source = _OverReturningSource([self.fact("fact:one"), self.fact("fact:two")])
        result = self.route_with_source(
            source,
            budget=RetrievalBudget(30, ((source.source_id, 1),)),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.INCOMPLETE)
        self.assertEqual(result.manifest.candidates, ())
        source_trace = next(
            item for item in result.trace.source_traces if item.source_id == source.source_id
        )
        self.assertEqual(source_trace.reason_code, "SOURCE_SCOPE_VIOLATION")
        self.assertEqual(source_trace.candidate_count, 2)
        self.assertEqual(source_trace.requested_limit, 1)
        self.assertEqual(source_trace.retrieved_count, 2)
        self.assertEqual(source_trace.evaluated_count, 0)
        self.assertEqual(source_trace.retained_count, 0)
        self.assertEqual(source_trace.rejected_count, 2)

    def test_stable_tie_break_uses_source_identity_and_version(self):
        source = P05LocalFactSource([self.fact("fact:z"), self.fact("fact:a")])
        result = self.route_with_source(source)
        self.assertEqual(
            [item.stable_id for item in result.manifest.candidates],
            ["fact:a", "fact:z"],
        )

    def test_feature_gate_returns_explicit_empty_result_without_reads(self):
        source = P05LocalFactSource([self.fact("fact:one")])
        result = self.route_with_source(source, enabled=False)
        self.assertEqual(result.trace.route_status, ContextRouteStatus.FEATURE_GATED)
        self.assertEqual(result.manifest.candidates, ())
        self.assertEqual(source.retrieve_calls, 0)
        self.assertTrue(
            all(
                item.status.value == "FEATURE_GATED"
                for item in result.trace.partition_traces
            )
        )

    def test_missing_required_source_is_incomplete(self):
        result = ContextRouterService([]).route(
            self.perception,
            request_id="route:missing",
            environment="TEST",
            required_partitions=(ContextPartition.MEMORY,),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.INCOMPLETE)
        self.assertEqual(result.manifest.candidates, ())

    def test_required_source_permission_denial_rejects_route(self):
        result = self.route_with_source(
            P05LocalFactSource([self.fact("fact:one")]),
            permission_policy=_DenySourcePolicy(),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.REJECTED)
        self.assertEqual(result.manifest.candidates, ())

    def test_optional_source_failure_is_traced_without_expanding_scope(self):
        source = _BrokenSource([self.fact("fact:one")])
        result = self.route_with_source(source, required=False)
        self.assertEqual(result.trace.route_status, ContextRouteStatus.COMPLETE)
        trace = next(
            item
            for item in result.trace.partition_traces
            if item.partition is ContextPartition.LOCAL_FACT
        )
        self.assertEqual(trace.reason_code, "SOURCE_READ_FAILED")
        self.assertEqual(result.manifest.candidates, ())

    def test_required_source_failure_is_incomplete(self):
        result = self.route_with_source(
            _BrokenSource([self.fact("fact:one")]), required=True
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.INCOMPLETE)

    def test_cross_subject_and_environment_candidates_fail_closed(self):
        source = P05LocalFactSource(
            [
                self.fact("fact:other-subject", subject_id="subject:other"),
                self.fact("fact:other-env", environment="RESEARCH"),
            ]
        )
        result = self.route_with_source(source)
        self.assertEqual(result.manifest.candidates, ())
        reasons = {item.reason_code for item in result.trace.candidate_decisions}
        self.assertEqual(reasons, {"CROSS_SUBJECT", "CROSS_ENVIRONMENT"})

    def test_unknown_visibility_is_rejected_without_content_disclosure(self):
        source = P05LocalFactSource(
            [self.fact("fact:private", permission_scope="UNKNOWN", content="do-not-leak")]
        )
        result = self.route_with_source(source)
        self.assertEqual(result.manifest.candidates, ())
        self.assertNotIn("do-not-leak", json.dumps(result.to_dict()))

    def test_source_change_between_route_and_use_fails_revalidation(self):
        source = P05LocalFactSource([self.fact("fact:one")])
        source.mutate_before_revalidation = True
        result = self.route_with_source(source)
        self.assertEqual(result.trace.route_status, ContextRouteStatus.INCOMPLETE)
        self.assertEqual(result.manifest.candidates, ())
        self.assertIn(
            "STALE_SOURCE",
            {item.reason_code for item in result.trace.candidate_decisions},
        )

    def test_subject_revision_change_is_incomplete_not_stale_fallback(self):
        source = SubjectStateContextSource(self.state_repository, environment="TEST")
        stale = build_p05_perception(self.p04)
        stale.source_revision += 1
        result = ContextRouterService([ContextSourceBinding(source, required=True)]).route(
            stale,
            request_id="route:stale-state",
            environment="TEST",
            required_partitions=(ContextPartition.SUBJECT_STATE,),
        )
        self.assertEqual(result.trace.route_status, ContextRouteStatus.INCOMPLETE)
        self.assertEqual(result.manifest.candidates, ())

    def test_archived_memory_is_not_routed_but_remains_loadable(self):
        root = self.root / "temperature"
        repository = JsonMemoryRepository(root, environment="TEST")
        for index, temperature in enumerate(MemoryTemperature):
            occurred = self.now - timedelta(days=index + 1)
            record = MemoryRecord(
                memory_id=f"memory:{temperature.value.lower()}",
                subject_id=self.perception.subject_id,
                environment="TEST",
                kind=MemoryKind.RELATIONAL,
                evidence_type=MemoryEvidenceType.EXPERIENTIAL,
                content=f"relationship {temperature.value}",
                root_evidence_ids=[f"event:{temperature.value.lower()}"],
                source_event_ids=[temperature.value.lower()],
                occurred_at=occurred,
                observed_at=occurred,
                recorded_at=occurred,
                consolidated_at=self.now,
                confidence=0.8,
                importance=0.8,
                activation=0.8,
                scope="relationship:current",
                time_range=MemoryTimeRange(occurred, occurred),
                consolidation_id=f"consolidation:{temperature.value.lower()}",
                temperature=temperature,
                visibility=MemoryVisibility.ENGINE_PRIVATE,
            )
            repository.save_memory(record)
        source = MemoryContextSource(repository, environment="TEST")
        result = ContextRouterService([ContextSourceBinding(source)]).route(
            self.perception,
            request_id="route:temperature",
            environment="TEST",
            required_partitions=(),
        )
        retained = {item.stable_id for item in result.manifest.candidates}
        self.assertTrue(
            {"memory:hot", "memory:warm", "memory:cold"}.issubset(retained)
        )
        self.assertNotIn("memory:archived", retained)
        self.assertEqual(
            repository.load_memory(self.perception.subject_id, "memory:archived").temperature,
            MemoryTemperature.ARCHIVED,
        )

    def test_invalidated_summary_is_not_routed(self):
        source = DerivedSummaryContextSource(self.memory_repository, environment="TEST")
        before = ContextRouterService([ContextSourceBinding(source)]).route(
            self.perception,
            request_id="route:summary-before",
            environment="TEST",
            required_partitions=(),
        )
        self.assertTrue(before.manifest.candidates)
        service = MemoryConsolidationService(
            self.memory_repository, clock=lambda: self.now + timedelta(minutes=1)
        )
        target = self.p04.relational_summary.source_memory_ids[0]
        service.propagate_signal(
            self.perception.subject_id,
            lineage_id="lineage:p05:revoke",
            target_memory_id=target,
            signal=MemoryLineageType.REVOCATION,
            source_event_id="p05-revocation",
            root_evidence_ids=["event:p05-revocation"],
        )
        after = ContextRouterService([ContextSourceBinding(source)]).route(
            self.perception,
            request_id="route:summary-after",
            environment="TEST",
            required_partitions=(),
        )
        self.assertEqual(after.manifest.candidates, ())

    def test_revoked_timeline_target_is_not_routed(self):
        service = SubjectStateService(
            self.state_repository, clock=lambda: self.now + timedelta(minutes=2)
        )
        revocation = Event.create(
            event_id="event:p05:revoke-day1",
            occurred_at=self.now,
            observed_at=self.now + timedelta(minutes=1),
            recorded_at=self.now + timedelta(minutes=2),
            source="continuity_engine.testing.p05",
            event_type="revocation",
            classification=EventClassification.REVOCATION,
            source_kind=EventSourceKind.TEST,
            content="Revoke the historical fixture fact for routing eligibility.",
            impact_scope=[StateSection.TEMPORAL],
            mutations=[],
            reason="Exercise Timeline source invalidation.",
            references=[
                EventReference(
                    "day1-no-noodles-fact",
                    self.perception.subject_id,
                    EventRelationType.REVOKES,
                )
            ],
        )
        service.apply_event(self.perception.subject_id, revocation)
        current = build_p05_perception(self.p04)
        current.source_revision = self.state_repository.load(self.perception.subject_id).revision
        source = TimelineContextSource(
            TimelineService(self.state_repository), environment="TEST"
        )
        result = ContextRouterService([ContextSourceBinding(source)]).route(
            current,
            request_id="route:timeline-revoked",
            environment="TEST",
            required_partitions=(),
        )
        retained = {item.stable_id for item in result.manifest.candidates}
        self.assertNotIn("day1-no-noodles-fact", retained)
        self.assertIn("event:p05:revoke-day1", retained)

    def test_future_partitions_are_explicitly_unavailable(self):
        result = self.route_with_source(P05LocalFactSource([self.fact("fact:one")]))
        traces = {item.partition: item for item in result.trace.partition_traces}
        for partition in (
            ContextPartition.ATTENTION,
            ContextPartition.DESIRE,
            ContextPartition.CONFLICT,
            ContextPartition.SOMATIC,
            ContextPartition.EXPRESSION,
        ):
            self.assertEqual(traces[partition].status.value, "NOT_OPENED")
            self.assertEqual(traces[partition].reason_code, "PURPOSE_NOT_SELECTED")

    def test_route_result_contains_references_not_composed_context(self):
        result = self.golden().route
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn('"content"', serialized)
        self.assertFalse(hasattr(result, "thinking_context"))
        self.assertFalse(hasattr(result, "token_plan"))
        signature = str(inspect.signature(ThinkingProvider.think))
        self.assertIn("perception", signature)
        self.assertNotIn("ContextRouteResult", signature)

    def test_trace_cannot_be_used_as_a_perception_input(self):
        result = self.golden().route
        with self.assertRaises(ContextRoutingValidationError):
            ContextRouterService([]).route(
                result.trace,
                request_id="route:trace-feedback",
                environment="TEST",
            )


if __name__ == "__main__":
    unittest.main()
