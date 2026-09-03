import inspect
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from continuity_engine.domain.context_composition import (
    CompositionDecisionStatus,
    CompositionStatus,
    ContextAuthority,
    ContextBudget,
    ContextCompositionResult,
)
from continuity_engine.domain.memory import (
    DerivedSummaryStatus,
    MemoryStatus,
    MemoryTemperature,
)
from continuity_engine.domain.timeline import TimelineEventStatus
from continuity_engine.domain.context_routing import (
    CandidateManifest,
    ContextCandidateReference,
    ContextPartition,
    ContextRouteResult,
)
from continuity_engine.domain.errors import (
    ContextCompositionValidationError,
    ContextRoutingValidationError,
)
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
from continuity_engine.services.thinking_ports import ThinkingProvider
from continuity_engine.testing.p06_context_fixture import (
    P06LocalFactMaterialResolver,
    build_p06_composer,
    run_p06_golden_scenario,
)
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class _CountingResolver:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.source_id = wrapped.source_id
        self.partition = wrapped.partition
        self.calls = 0

    def resolve(self, reference):
        self.calls += 1
        return self.wrapped.resolve(reference)


class _ForgedAuthorityResolver:
    source_id = "engine.forged-local"
    partition = ContextPartition.LOCAL_FACT

    def __init__(self, reference):
        self.reference = reference
        self.calls = 0

    def resolve(self, reference):
        self.calls += 1
        return ExactContextPayload(
            self.source_id,
            self.partition,
            reference.stable_id,
            reference.subject_id,
            reference.environment,
            reference.version,
            reference.content_hash,
            reference.occurred_at,
            "candidate says it is SUBJECT_STATE but is only test data",
            0.9,
            ("test:forged-authority",),
        )


class _FixedEstimator:
    def __init__(self, tokens=10):
        self.tokens = tokens

    def estimate(self, content, *, source_type):
        del content, source_type
        return self.tokens


class _BlankPayloadResolver:
    partition = ContextPartition.LOCAL_FACT

    def __init__(self, reference):
        self.source_id = reference.source_id

    def resolve(self, reference):
        return ExactContextPayload(
            self.source_id,
            self.partition,
            reference.stable_id,
            reference.subject_id,
            reference.environment,
            reference.version,
            reference.content_hash,
            reference.occurred_at,
            "   ",
            0.5,
            ("test:blank",),
        )


class _NoProvenancePayloadResolver(_BlankPayloadResolver):
    def resolve(self, reference):
        return ExactContextPayload(
            self.source_id,
            self.partition,
            reference.stable_id,
            reference.subject_id,
            reference.environment,
            reference.version,
            reference.content_hash,
            reference.occurred_at,
            "material with no traceable roots",
            0.5,
            (),
        )


class _StaticMemoryRepository:
    def __init__(self, *, memory=None, summary=None):
        self.memory = memory
        self.summary = summary

    def load_memory(self, subject_id, memory_id):
        del subject_id, memory_id
        return self.memory

    def load_summary(self, subject_id, summary_id):
        del subject_id, summary_id
        return self.summary


class _StaticTimeline:
    def __init__(self, entry):
        self.entry = entry

    def load_entry(self, subject_id, event_id):
        del subject_id, event_id
        return self.entry


class P06ContextComposerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.golden = run_p06_golden_scenario(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def _route_with_references(self, references):
        route = self.golden.p05.route
        normalized = tuple(
            replace(reference, rank=index)
            for index, reference in enumerate(references, start=1)
        )
        manifest = CandidateManifest(
            route.plan.request.request_id,
            route.plan.canonical_hash(),
            normalized,
        )
        trace = replace(route.trace, manifest_hash=manifest.manifest_hash)
        return ContextRouteResult(route.plan, manifest, trace)

    def _reference_for(self, source_id):
        return next(
            item
            for item in self.golden.p05.route.manifest.candidates
            if item.source_id == source_id
        )

    def _compose_required(self, reference, resolver, authority, source_type):
        return ContextComposerService(
            [
                TrustedContextResolverBinding(
                    resolver,
                    authority,
                    source_type,
                    required=True,
                )
            ]
        ).compose(self._route_with_references((reference,)))

    def test_golden_scenario_preserves_all_five_authorities_and_zero_writes(self):
        result = self.golden.composition
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        authorities = {item.authority for item in result.snapshot.fragments}
        self.assertEqual(authorities, set(ContextAuthority))
        self.assertEqual(
            self.golden.subject_document_hash_before,
            self.golden.subject_document_hash_after,
        )
        self.assertEqual(
            self.golden.memory_document_hash_before,
            self.golden.memory_document_hash_after,
        )
        self.assertTrue(all(not item.direct_state_write_allowed for item in result.snapshot.fragments))
        self.assertEqual(result.trace.candidate_count, 18)
        self.assertEqual(result.trace.resolved_count, 18)
        self.assertEqual(result.trace.missing_count, 0)
        self.assertEqual(result.trace.upstream_notice_count, 5)
        self.assertEqual(
            sum(
                item.status is CompositionDecisionStatus.MISSING
                for item in result.trace.decisions
            ),
            0,
        )

    def test_candidate_self_reported_authority_cannot_elevate_trusted_binding(self):
        original = next(
            item
            for item in self.golden.p05.route.manifest.candidates
            if item.source_id == self.golden.p05.local_source.source_id
        )
        forged = replace(
            original,
            source_id="engine.forged-local",
            authority_label="SUBJECT_STATE",
        )
        route = self._route_with_references((forged,))
        resolver = _ForgedAuthorityResolver(forged)
        result = ContextComposerService(
            [
                TrustedContextResolverBinding(
                    resolver,
                    ContextAuthority.RETRIEVED_CANDIDATE,
                    "versioned_local_candidate",
                )
            ]
        ).compose(route)
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        self.assertEqual(
            result.snapshot.fragments[0].authority,
            ContextAuthority.RETRIEVED_CANDIDATE,
        )

    def test_non_complete_p05_route_is_not_consumed_and_reads_zero(self):
        route = self.golden.p05.route
        incomplete = replace(
            route,
            trace=replace(route.trace, route_status="INCOMPLETE"),
        )
        composer, local = build_p06_composer(self.root, self.golden.p05)
        before = local.resolve_calls
        result = composer.compose(incomplete)
        self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
        self.assertIsNone(result.snapshot)
        self.assertEqual(local.resolve_calls, before)
        self.assertEqual(result.trace.resolver_read_count, 0)
        self.assertTrue(
            all(item.read_count == 0 for item in result.trace.resolver_read_counts)
        )

    def test_feature_gate_disables_all_exact_resolver_reads(self):
        composer, local = build_p06_composer(
            self.root, self.golden.p05, enabled=False
        )
        result = composer.compose(self.golden.p05.route)
        self.assertEqual(result.status, CompositionStatus.FEATURE_GATED)
        self.assertIsNone(result.snapshot)
        self.assertEqual(local.resolve_calls, 0)
        self.assertEqual(result.trace.resolver_read_count, 0)
        self.assertTrue(
            all(item.read_count == 0 for item in result.trace.resolver_read_counts)
        )

    def test_router_not_opened_and_empty_are_distinct_upstream_notices(self):
        result = self.golden.composition
        reasons = {item.reason_code for item in result.trace.upstream_notices}
        self.assertIn("ROUTER_PARTITION_NOT_OPENED", reasons)
        self.assertEqual(
            result.trace.upstream_notice_count,
            len(result.trace.upstream_notices),
        )
        self.assertEqual(result.trace.missing_count, 0)

    def test_candidate_missing_and_upstream_notices_do_not_pollute_each_other(self):
        reference = self._reference_for(self.golden.p05.local_source.source_id)
        self.golden.p05.local_source.facts = [
            item
            for item in self.golden.p05.local_source.facts
            if item.fact_id != reference.stable_id
        ]
        composer, local = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(
            self.golden.p05.route,
            budget=ContextBudget(core_fragment_limit=15, token_limit=2048),
        )
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        self.assertEqual(result.trace.candidate_count, 18)
        self.assertEqual(result.trace.resolved_count, 17)
        self.assertEqual(result.trace.missing_count, 1)
        self.assertEqual(result.trace.upstream_notice_count, 5)
        self.assertEqual(
            sum(
                item.status is CompositionDecisionStatus.MISSING
                for item in result.trace.decisions
            ),
            1,
        )
        self.assertEqual(
            result.trace.resolved_count + result.trace.missing_count,
            result.trace.candidate_count,
        )
        self.assertEqual(local.resolve_calls, 1)

    def test_composer_owned_resolver_read_audit_matches_manifest_by_source(self):
        trace = self.golden.composition.trace
        expected = {}
        for item in self.golden.p05.route.manifest.candidates:
            expected[item.source_id] = expected.get(item.source_id, 0) + 1
        actual = {
            item.source_id: item.read_count for item in trace.resolver_read_counts
        }
        self.assertEqual(trace.resolver_read_count, 18)
        self.assertEqual(sum(actual.values()), 18)
        for source_id, count in expected.items():
            self.assertEqual(actual[source_id], count)

    def test_manifest_only_resolution_does_not_read_unreferenced_resolver(self):
        route = self._route_with_references(
            (self.golden.p05.route.manifest.candidates[0],)
        )
        composer, local = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(route)
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        self.assertEqual(local.resolve_calls, 0)
        reads = {item.source_id: item.read_count for item in result.trace.resolver_read_counts}
        self.assertEqual(reads[local.source_id], 0)
        self.assertEqual(result.trace.resolver_read_count, 1)

    def test_exact_duplicate_reference_is_rejected_before_spending_context_budget(self):
        reference = self.golden.p05.route.manifest.candidates[0]
        with self.assertRaises(ContextRoutingValidationError):
            self._route_with_references((reference, reference))

    def test_required_version_or_hash_drift_fails_closed_without_snapshot(self):
        self.golden.p05.local_source.facts[0] = replace(
            self.golden.p05.local_source.facts[0],
            version="version:drifted",
            content="drifted content",
        )
        state_bindings, local = build_p06_composer(self.root, self.golden.p05)
        bindings = list(state_bindings._bindings.values())
        hardened = [
            replace(item, required=True)
            if item.resolver.source_id == local.source_id
            else item
            for item in bindings
        ]
        result = ContextComposerService(hardened).compose(self.golden.p05.route)
        self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
        self.assertIsNone(result.snapshot)
        self.assertIn(
            "SOURCE_VERSION_DRIFT",
            {item.reason_code for item in result.trace.decisions},
        )

    def test_permission_change_after_routing_fails_closed(self):
        self.golden.p05.local_source.facts[0] = replace(
            self.golden.p05.local_source.facts[0], permission_scope="SECRET"
        )
        composer, local = build_p06_composer(self.root, self.golden.p05)
        bindings = [
            replace(item, required=True)
            if item.resolver.source_id == local.source_id
            else item
            for item in composer._bindings.values()
        ]
        result = ContextComposerService(bindings).compose(self.golden.p05.route)
        self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
        self.assertIsNone(result.snapshot)
        self.assertIn(
            "SOURCE_VISIBILITY_DENIED",
            {item.reason_code for item in result.trace.decisions},
        )

    def test_missing_material_content_has_a_distinct_reason_code(self):
        reference = next(
            item
            for item in self.golden.p05.route.manifest.candidates
            if item.partition is ContextPartition.LOCAL_FACT
        )
        route = self._route_with_references((reference,))
        result = ContextComposerService(
            [
                TrustedContextResolverBinding(
                    _BlankPayloadResolver(reference),
                    ContextAuthority.RETRIEVED_CANDIDATE,
                    "versioned_local_candidate",
                    required=True,
                )
            ]
        ).compose(route)
        self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
        self.assertEqual(result.trace.decisions[0].reason_code, "MATERIAL_CONTENT_MISSING")

    def test_missing_material_provenance_has_a_distinct_reason_code(self):
        reference = self._reference_for(self.golden.p05.local_source.source_id)
        result = self._compose_required(
            reference,
            _NoProvenancePayloadResolver(reference),
            ContextAuthority.RETRIEVED_CANDIDATE,
            "versioned_local_candidate",
        )
        self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
        self.assertEqual(
            result.trace.decisions[0].reason_code,
            "MATERIAL_PROVENANCE_INVALID",
        )

    def test_builtin_exact_resolvers_surface_stable_top_level_failure_reasons(self):
        state_reference = self._reference_for("engine.subject-state")
        state_repository = JsonSubjectStateRepository(self.root)
        memory_repository = JsonMemoryRepository(self.root, environment="TEST")
        memory_reference = self._reference_for("engine.memory")
        summary_reference = self._reference_for("engine.derived-summary")
        timeline_reference = self._reference_for("engine.timeline")

        memory = memory_repository.load_memory(
            memory_reference.subject_id, memory_reference.stable_id
        )
        terminal_memory = replace(
            memory,
            status=MemoryStatus.REVOKED,
            lineage_event_id="event:p06-test-revocation",
        )
        summary = memory_repository.load_summary(
            summary_reference.subject_id, summary_reference.stable_id
        )
        invalid_summary = replace(
            summary,
            status=DerivedSummaryStatus.INVALIDATED,
            invalidation_reason="P06_TEST_INVALIDATION",
        )
        timeline_entry = TimelineService(state_repository).load_entry(
            timeline_reference.subject_id, timeline_reference.stable_id
        )
        revoked_entry = replace(
            timeline_entry,
            status=TimelineEventStatus.REVOKED,
            revoked_by=("event:p06-test-revocation",),
        )
        cases = (
            (
                "subject-state-version",
                replace(state_reference, version="revision:999"),
                SubjectStateMaterialResolver(state_repository, environment="TEST"),
                ContextAuthority.CONFIRMED_STATE,
                "subject_state_section",
                "SOURCE_VERSION_DRIFT",
            ),
            (
                "memory-status",
                memory_reference,
                MemoryMaterialResolver(
                    _StaticMemoryRepository(memory=terminal_memory),
                    environment="TEST",
                ),
                ContextAuthority.CONFIRMED_MEMORY,
                "memory_record",
                "SOURCE_STATUS_INELIGIBLE",
            ),
            (
                "summary-status",
                summary_reference,
                DerivedSummaryMaterialResolver(
                    _StaticMemoryRepository(summary=invalid_summary),
                    environment="TEST",
                ),
                ContextAuthority.DERIVED_SUMMARY,
                "derived_summary",
                "SOURCE_STATUS_INELIGIBLE",
            ),
            (
                "timeline-status",
                timeline_reference,
                TimelineMaterialResolver(_StaticTimeline(revoked_entry), environment="TEST"),
                ContextAuthority.RAW_SOURCE,
                "timeline_event",
                "SOURCE_STATUS_INELIGIBLE",
            ),
        )
        for name, reference, resolver, authority, source_type, expected in cases:
            with self.subTest(case=name):
                result = self._compose_required(
                    reference, resolver, authority, source_type
                )
                self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
                self.assertEqual(result.trace.decisions[0].reason_code, expected)
                self.assertEqual(result.trace.resolver_read_count, 1)

    def test_cross_subject_and_environment_reference_fail_closed(self):
        reference = self.golden.p05.route.manifest.candidates[0]
        for field, value in (("subject_id", "subject:other"), ("environment", "RESEARCH")):
            with self.subTest(field=field):
                route = self._route_with_references((replace(reference, **{field: value}),))
                composer, _ = build_p06_composer(self.root, self.golden.p05)
                result = composer.compose(route)
                self.assertEqual(result.status, CompositionStatus.INCOMPLETE)
                self.assertIsNone(result.snapshot)
                self.assertEqual(
                    result.trace.decisions[0].reason_code,
                    "SOURCE_SUBJECT_MISMATCH"
                    if field == "subject_id"
                    else "SOURCE_ENVIRONMENT_MISMATCH",
                )
                self.assertEqual(result.trace.resolver_read_count, 0)

    def test_unknown_source_binding_is_rejected_not_broadly_searched(self):
        reference = self.golden.p05.route.manifest.candidates[-1]
        unknown = replace(reference, source_id="engine.unknown-source")
        route = self._route_with_references((unknown,))
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(route)
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        self.assertEqual(
            result.trace.decisions[0].reason_code,
            "SOURCE_MISSING",
        )
        self.assertEqual(result.trace.resolver_read_count, 0)

    def test_summary_and_raw_source_are_not_semantically_merged(self):
        fragments = self.golden.composition.snapshot.fragments
        summary = next(
            item
            for item in fragments
            if item.stable_source_id == "summary:relationship:day2"
        )
        raw = next(
            item
            for item in fragments
            if item.stable_source_id == "day2-reconciliation-fact"
        )
        self.assertEqual(summary.authority, ContextAuthority.DERIVED_SUMMARY)
        self.assertEqual(raw.authority, ContextAuthority.RAW_SOURCE)
        self.assertNotEqual(summary.fragment_id, raw.fragment_id)
        self.assertNotEqual(summary.provenance_roots, raw.provenance_roots)

    def test_raw_source_and_confirmed_memory_coexist_without_auto_overwrite(self):
        fragments = self.golden.composition.snapshot.fragments
        authorities = {
            (item.authority, item.stable_source_id) for item in fragments
        }
        self.assertIn(
            (ContextAuthority.CONFIRMED_MEMORY, "memory:day2-reconciliation-fact"),
            authorities,
        )
        self.assertIn(
            (ContextAuthority.RAW_SOURCE, "day2-reconciliation-fact"),
            authorities,
        )

    def test_context_budget_retains_identity_continuity_and_relationship_first(self):
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(
            self.golden.p05.route,
            budget=ContextBudget(core_fragment_limit=6, token_limit=2048),
        )
        protected = {
            item.protection_role
            for item in result.snapshot.fragments
            if item.protected
        }
        self.assertEqual(protected, {"identity", "continuity", "relationship"})
        self.assertEqual(len(result.snapshot.fragments), 6)
        self.assertIn(
            "CONTEXT_FRAGMENT_LIMIT",
            {item.reason_code for item in result.trace.decisions},
        )

    def test_budget_too_small_for_protected_identity_fails_explicitly(self):
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(
            self.golden.p05.route,
            budget=ContextBudget(core_fragment_limit=6, token_limit=1),
        )
        self.assertEqual(
            result.status, CompositionStatus.INSUFFICIENT_CONTEXT_BUDGET
        )
        self.assertEqual(result.error_code, "INSUFFICIENT_CONTEXT_BUDGET")
        self.assertIsNone(result.snapshot)

    def test_context_budget_hint_is_used_when_no_explicit_budget_is_passed(self):
        route = self.golden.p05.route
        request = replace(
            route.plan.request,
            budget=replace(route.plan.request.budget, context_budget_hint=321),
        )
        plan = replace(route.plan, request=request)
        manifest = CandidateManifest(
            request.request_id, plan.canonical_hash(), route.manifest.candidates
        )
        trace = replace(
            route.trace,
            route_plan_hash=plan.canonical_hash(),
            manifest_hash=manifest.manifest_hash,
        )
        hinted = ContextRouteResult(plan, manifest, trace)
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(hinted)
        self.assertEqual(result.trace.budget.token_limit, 321)

    def test_fixed_inputs_clock_and_estimator_are_fully_deterministic(self):
        first_composer, _ = build_p06_composer(self.root, self.golden.p05)
        second_composer, _ = build_p06_composer(self.root, self.golden.p05)
        first = first_composer.compose(self.golden.p05.route)
        second = second_composer.compose(self.golden.p05.route)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.canonical_hash(), second.canonical_hash())

    def test_trace_never_contains_material_body_or_secret(self):
        serialized = json.dumps(
            self.golden.composition.trace.to_dict(), ensure_ascii=False
        )
        for fragment in self.golden.composition.snapshot.fragments:
            self.assertNotIn(fragment.content, serialized)
        self.assertNotIn("TOP SECRET", serialized)
        self.assertNotIn("hidden chain", serialized.casefold())

    def test_test_only_thinking_consumer_sees_authority_without_production_integration(self):
        self.assertTrue(self.golden.consumer_view)
        self.assertIn(
            ("confirmed_state", "p03-golden-subject:identity"),
            self.golden.consumer_view,
        )
        signature = str(inspect.signature(ThinkingProvider.think))
        self.assertIn("perception", signature)
        self.assertNotIn("ComposedContextSnapshot", signature)

    def test_output_tampering_and_count_mismatch_fail_closed(self):
        value = self.golden.composition.to_dict()
        value["snapshot"]["fragments"][0]["authority"] = "raw_source"
        with self.assertRaises(ContextCompositionValidationError):
            ContextCompositionResult.from_dict(value)
        value = self.golden.composition.to_dict()
        value["trace"]["retained_count"] += 1
        with self.assertRaises(ContextCompositionValidationError):
            ContextCompositionResult.from_dict(value)

    def test_optional_material_drift_is_excluded_with_stable_missing_notice(self):
        self.golden.p05.local_source.facts[0] = replace(
            self.golden.p05.local_source.facts[0], content="changed after route"
        )
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        result = composer.compose(self.golden.p05.route)
        self.assertEqual(result.status, CompositionStatus.COMPLETE)
        self.assertIn(
            "SOURCE_HASH_DRIFT",
            {item.reason_code for item in result.snapshot.missing_notices},
        )
        self.assertNotIn(
            "fact:relationship:love",
            {item.stable_source_id for item in result.snapshot.fragments},
        )

    def test_p05_route_result_is_not_modified_by_composition(self):
        before = self.golden.p05.route.to_dict()
        composer, _ = build_p06_composer(self.root, self.golden.p05)
        composer.compose(self.golden.p05.route)
        self.assertEqual(self.golden.p05.route.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
