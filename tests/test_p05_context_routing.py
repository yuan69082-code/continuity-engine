import json
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.context_routing import (
    CandidateManifest,
    ContextCandidateReference,
    ContextPartition,
    ContextPartitionRequest,
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
    hash_signal,
)
from continuity_engine.domain.errors import ContextRoutingValidationError


UTC = timezone.utc
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


class P05ContextRoutingDomainTests(unittest.TestCase):
    def request(self, budget=None):
        return ContextRoutingRequest(
            "route:1",
            "perception:1",
            "subject:1",
            "TEST",
            3,
            NOW,
            ("relationship",),
            budget or RetrievalBudget(),
        )

    def candidate(self, stable_id="candidate:1"):
        return ContextSourceCandidate(
            "engine.memory",
            ContextPartition.MEMORY,
            stable_id,
            "subject:1",
            "TEST",
            "revision:1",
            hash_signal(stable_id),
            NOW - timedelta(hours=1),
            "ENGINE_PRIVATE",
            "MEMORY_RECORD",
            0.8,
            0.7,
            0.6,
            ("relationship",),
            ("relationship:current",),
        )

    def test_retrieval_budget_default_and_separate_context_hint(self):
        budget = RetrievalBudget(context_budget_hint=2048)
        self.assertEqual(budget.total_candidate_limit, 50)
        self.assertEqual(budget.context_budget_hint, 2048)
        self.assertNotIn("storage", budget.to_dict())

    def test_retrieval_budget_enforces_configurable_30_to_80_range(self):
        for value in (29, 81, True):
            with self.subTest(value=value), self.assertRaises(
                ContextRoutingValidationError
            ):
                RetrievalBudget(total_candidate_limit=value)
        self.assertEqual(RetrievalBudget(30).total_candidate_limit, 30)
        self.assertEqual(RetrievalBudget(80).total_candidate_limit, 80)

    def test_per_source_limits_are_stable_and_bounded(self):
        budget = RetrievalBudget(
            30, (("source:z", 3), ("source:a", 5))
        )
        self.assertEqual(
            budget.per_source_limits,
            (("source:a", 5), ("source:z", 3)),
        )
        self.assertEqual(budget.limit_for("source:a"), 5)
        self.assertEqual(budget.limit_for("source:other"), 30)

    def test_routing_request_normalizes_time_and_round_trips(self):
        local = NOW.astimezone(timezone(timedelta(hours=8)))
        request = ContextRoutingRequest(
            "route:1",
            "perception:1",
            "subject:1",
            "TEST",
            3,
            local,
            ("relationship",),
        )
        restored = ContextRoutingRequest.from_dict(request.to_dict())
        self.assertEqual(restored.to_dict(), request.to_dict())
        self.assertEqual(restored.routed_at.tzinfo, UTC)

    def test_route_plan_hash_is_deterministic(self):
        signal = RoutingSignal("signal:1", "relationship", hash_signal("private"), 1.0)
        partition = ContextPartitionRequest(
            ContextPartition.MEMORY, False, ("engine.memory",), 10, "SOURCE_CONFIGURED"
        )
        first = RoutePlan(self.request(), (signal,), (partition,), "p05-v1")
        second = RoutePlan(self.request(), (signal,), (partition,), "p05-v1")
        self.assertEqual(first.canonical_hash(), second.canonical_hash())

    def test_signal_contains_only_hash_not_sensitive_value(self):
        secret = "SECRET-BEARER-VALUE"
        signal = RoutingSignal("signal:1", "fact", hash_signal(secret), 0.8)
        serialized = json.dumps(signal.to_dict())
        self.assertNotIn(secret, serialized)
        self.assertTrue(signal.value_hash.startswith("sha256:"))

    def test_source_batch_rejects_duplicate_stable_identity(self):
        candidate = self.candidate()
        with self.assertRaises(ContextRoutingValidationError):
            ContextSourceBatch(
                "engine.memory",
                ContextPartition.MEMORY,
                "revision:1",
                (candidate, candidate),
            )

    def test_source_batch_rejects_partition_mismatch(self):
        with self.assertRaises(ContextRoutingValidationError):
            ContextSourceBatch(
                "engine.memory",
                ContextPartition.TIMELINE,
                "revision:1",
                (self.candidate(),),
            )

    def test_candidate_requires_version_hash_and_timezone(self):
        payload = {
            "source_id": "engine.memory",
            "partition": ContextPartition.MEMORY,
            "stable_id": "candidate:1",
            "subject_id": "subject:1",
            "environment": "TEST",
            "version": "revision:1",
            "content_hash": "bad",
            "occurred_at": NOW,
            "permission_scope": "ENGINE_PRIVATE",
            "authority_label": "MEMORY_RECORD",
            "relevance": 0.5,
        }
        with self.assertRaises(ContextRoutingValidationError):
            ContextSourceCandidate(**payload)
        payload["content_hash"] = hash_signal("candidate")
        payload["occurred_at"] = datetime(2026, 9, 1)
        with self.assertRaises(ContextRoutingValidationError):
            ContextSourceCandidate(**payload)

    def test_manifest_integrity_rejects_tampering(self):
        reference = ContextCandidateReference(
            "engine.memory",
            ContextPartition.MEMORY,
            "candidate:1",
            "subject:1",
            "TEST",
            "revision:1",
            hash_signal("candidate"),
            "MEMORY_RECORD",
            1,
            0.8,
            NOW,
            ("PURPOSE_RELEVANCE",),
        )
        manifest = CandidateManifest("route:1", hash_signal("plan"), (reference,))
        value = manifest.to_dict()
        value["candidates"][0]["score"] = 0.9
        with self.assertRaises(ContextRoutingValidationError):
            CandidateManifest.from_dict(value)

    def test_manifest_rejects_noncontiguous_ranks(self):
        reference = ContextCandidateReference(
            "engine.memory",
            ContextPartition.MEMORY,
            "candidate:1",
            "subject:1",
            "TEST",
            "revision:1",
            hash_signal("candidate"),
            "MEMORY_RECORD",
            2,
            0.8,
            NOW,
            ("PURPOSE_RELEVANCE",),
        )
        with self.assertRaises(ContextRoutingValidationError):
            CandidateManifest("route:1", hash_signal("plan"), (reference,))

    def test_trace_rejects_budget_overrun(self):
        with self.assertRaises(ContextRoutingValidationError):
            ContextTrace(
                "trace:1",
                "route:1",
                "perception:1",
                "subject:1",
                0,
                NOW,
                ("relationship",),
                hash_signal("plan"),
                hash_signal("manifest"),
                ContextRouteStatus.COMPLETE,
                "p05-v1",
                (
                    PartitionTrace(
                        ContextPartition.MEMORY,
                        PartitionDecisionStatus.OPENED,
                        "OK",
                        30,
                        ("engine.memory",),
                    ),
                ),
                (),
                (),
                30,
                31,
            )


if __name__ == "__main__":
    unittest.main()
