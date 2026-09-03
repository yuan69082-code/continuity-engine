import json
import unittest
from datetime import datetime, timezone

from continuity_engine.domain.context_composition import (
    ComposedContextFragment,
    ComposedContextSnapshot,
    CompositionDecision,
    CompositionDecisionStatus,
    CompositionStatus,
    CompositionTrace,
    ContextAuthority,
    ContextBudget,
    ContextCompositionResult,
    MissingContextNotice,
    ResolverReadCount,
    ResolvedContextMaterial,
    composition_hash,
)
from continuity_engine.domain.context_routing import ContextPartition
from continuity_engine.domain.errors import ContextCompositionValidationError


NOW = datetime(2026, 9, 3, 8, 0, tzinfo=timezone.utc)
HASH = composition_hash("material")


class P06ContextCompositionDomainTests(unittest.TestCase):
    def material(self, authority=ContextAuthority.CONFIRMED_MEMORY, **changes):
        values = dict(
            reference_id=composition_hash("reference"),
            source_id="engine.memory",
            partition=ContextPartition.MEMORY,
            stable_source_id="memory:1",
            subject_id="subject:1",
            environment="TEST",
            version="revision:1",
            content_hash=HASH,
            source_type="memory_record",
            authority=authority,
            occurred_at=NOW,
            relevance=0.8,
            confidence=0.9,
            provenance_roots=("event:1",),
            content="remembered relationship fact",
        )
        values.update(changes)
        return ResolvedContextMaterial(**values)

    def fragment(self, **changes):
        material = self.material()
        values = dict(
            fragment_id=composition_hash("fragment"),
            reference_id=material.reference_id,
            subject_id=material.subject_id,
            environment=material.environment,
            authority=material.authority,
            source_id=material.source_id,
            source_type=material.source_type,
            stable_source_id=material.stable_source_id,
            version=material.version,
            content_hash=material.content_hash,
            occurred_at=material.occurred_at,
            relevance=material.relevance,
            confidence=material.confidence,
            provenance_roots=material.provenance_roots,
            conflict_markers=(),
            missing_markers=(),
            estimated_tokens=7,
            rank=1,
            retained_reason="VERIFIED_CONTEXT_RETAINED",
            content=material.content,
        )
        values.update(changes)
        return ComposedContextFragment(**values)

    def trace(self, **changes):
        decision = CompositionDecision(
            composition_hash("reference"),
            "engine.memory",
            "memory:1",
            CompositionDecisionStatus.RETAINED,
            "VERIFIED_CONTEXT_RETAINED",
            ContextAuthority.CONFIRMED_MEMORY,
            7,
        )
        values = dict(
            trace_id="composition-trace:1",
            request_id="route:1",
            subject_id="subject:1",
            environment="TEST",
            source_revision=1,
            composed_at=NOW,
            status=CompositionStatus.COMPLETE,
            route_result_hash=composition_hash("route"),
            route_plan_hash=composition_hash("plan"),
            manifest_hash=composition_hash("manifest"),
            p05_trace_hash=composition_hash("p05-trace"),
            feature_gate_version="p06-v1",
            budget=ContextBudget(),
            candidate_count=1,
            resolved_count=1,
            retained_count=1,
            deduplicated_count=0,
            excluded_count=0,
            missing_count=0,
            upstream_notice_count=0,
            resolver_read_count=1,
            resolver_read_counts=(ResolverReadCount("engine.memory", 1),),
            tokens_used=7,
            decisions=(decision,),
            upstream_notices=(),
        )
        values.update(changes)
        return CompositionTrace(**values)

    def snapshot(self, **changes):
        values = dict(
            snapshot_id="context-snapshot:1",
            request_id="route:1",
            subject_id="subject:1",
            environment="TEST",
            source_revision=1,
            composed_at=NOW,
            route_result_hash=composition_hash("route"),
            route_plan_hash=composition_hash("plan"),
            manifest_hash=composition_hash("manifest"),
            budget=ContextBudget(),
            fragments=(self.fragment(),),
        )
        values.update(changes)
        return ComposedContextSnapshot(**values)

    def test_five_authorities_round_trip_without_numeric_truth_ranking(self):
        for authority in ContextAuthority:
            with self.subTest(authority=authority):
                material = self.material(authority=authority)
                restored = ResolvedContextMaterial.from_dict(material.to_dict())
                self.assertEqual(restored.authority, authority)
        self.assertEqual(
            [item.value for item in ContextAuthority],
            [
                "confirmed_state",
                "confirmed_memory",
                "derived_summary",
                "retrieved_candidate",
                "raw_source",
            ],
        )

    def test_context_budget_is_separate_and_enforces_fragment_range(self):
        self.assertEqual(ContextBudget().core_fragment_limit, 10)
        self.assertEqual(ContextBudget().token_limit, 2048)
        self.assertNotIn("retrieval", ContextBudget().to_dict())
        self.assertNotIn("provider", ContextBudget().to_dict())
        for value in (5, 16, True):
            with self.subTest(value=value), self.assertRaises(
                ContextCompositionValidationError
            ):
                ContextBudget(core_fragment_limit=value)

    def test_only_confirmed_state_can_be_budget_protected(self):
        with self.assertRaises(ContextCompositionValidationError):
            self.material(protected=True, protection_role="identity")
        protected = self.material(
            ContextAuthority.CONFIRMED_STATE,
            source_id="engine.subject-state",
            partition=ContextPartition.SUBJECT_STATE,
            stable_source_id="subject:1:identity",
            source_type="subject_state_section",
            protected=True,
            protection_role="identity",
        )
        self.assertTrue(protected.protected)

    def test_material_and_fragment_can_never_enable_direct_state_write(self):
        with self.assertRaises(ContextCompositionValidationError):
            self.material(direct_state_write_allowed=True)
        with self.assertRaises(ContextCompositionValidationError):
            self.fragment(direct_state_write_allowed=True)

    def test_snapshot_and_result_round_trip_with_canonical_hash(self):
        snapshot = self.snapshot()
        trace = self.trace()
        result = ContextCompositionResult(
            CompositionStatus.COMPLETE, trace, snapshot
        )
        restored = ContextCompositionResult.from_dict(result.to_dict())
        self.assertEqual(restored.to_dict(), result.to_dict())
        self.assertEqual(restored.canonical_hash(), result.canonical_hash())

    def test_snapshot_tampering_is_rejected(self):
        value = self.snapshot().to_dict()
        value["fragments"][0]["content"] = "tampered body"
        with self.assertRaises(ContextCompositionValidationError):
            ComposedContextSnapshot.from_dict(value)

    def test_trace_tampering_and_count_mismatch_are_rejected(self):
        value = self.trace().to_dict()
        value["retained_count"] = 0
        value["excluded_count"] = 0
        with self.assertRaises(ContextCompositionValidationError):
            CompositionTrace.from_dict(value)

        value = self.trace().to_dict()
        value["resolver_read_count"] = 2
        with self.assertRaises(ContextCompositionValidationError):
            CompositionTrace.from_dict(value)

    def test_candidate_missing_and_upstream_notices_use_independent_invariants(self):
        missing = MissingContextNotice(
            composition_hash("candidate-missing"),
            "engine.memory",
            "memory:1",
            False,
            "SOURCE_MISSING",
        )
        upstream = MissingContextNotice(
            composition_hash("upstream-notice"),
            "p05.route",
            "partition:local_fact",
            False,
            "ROUTER_PARTITION_NOT_OPENED",
        )
        trace = self.trace(
            resolved_count=0,
            retained_count=0,
            missing_count=1,
            upstream_notice_count=1,
            resolver_read_count=0,
            resolver_read_counts=(ResolverReadCount("engine.memory", 0),),
            tokens_used=0,
            decisions=(
                CompositionDecision(
                    missing.reference_id,
                    missing.source_id,
                    missing.stable_source_id,
                    CompositionDecisionStatus.MISSING,
                    missing.reason_code,
                ),
            ),
            upstream_notices=(upstream,),
        )
        restored = CompositionTrace.from_dict(trace.to_dict())
        self.assertEqual(restored.missing_count, 1)
        self.assertEqual(restored.upstream_notice_count, 1)
        self.assertEqual(restored.resolved_count + restored.missing_count, 1)

    def test_trace_contains_no_fragment_content_or_secret(self):
        trace = self.trace()
        serialized = json.dumps(trace.to_dict(), ensure_ascii=False)
        self.assertNotIn("remembered relationship fact", serialized)
        self.assertNotIn("secret", serialized.casefold())

    def test_failed_result_cannot_expose_a_consumable_snapshot(self):
        trace = self.trace(
            status=CompositionStatus.INCOMPLETE,
            retained_count=0,
            excluded_count=1,
            tokens_used=0,
            decisions=(
                CompositionDecision(
                    composition_hash("reference"),
                    "engine.memory",
                    "memory:1",
                    CompositionDecisionStatus.EXCLUDED,
                    "COMPOSITION_NOT_CONSUMABLE_REQUIRED_SOURCE_FAILURE",
                    ContextAuthority.CONFIRMED_MEMORY,
                ),
            ),
        )
        with self.assertRaises(ContextCompositionValidationError):
            ContextCompositionResult(
                CompositionStatus.INCOMPLETE,
                trace,
                self.snapshot(),
                "REQUIRED_CONTEXT_SOURCE_UNAVAILABLE",
            )

    def test_fragment_rank_and_snapshot_budget_are_integrity_checked(self):
        with self.assertRaises(ContextCompositionValidationError):
            self.snapshot(fragments=(self.fragment(rank=2),))
        with self.assertRaises(ContextCompositionValidationError):
            self.snapshot(
                budget=ContextBudget(token_limit=1),
                fragments=(self.fragment(estimated_tokens=7),),
            )


if __name__ == "__main__":
    unittest.main()
