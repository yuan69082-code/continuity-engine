from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.action import ResourceLimits
from continuity_engine.domain.action_planning import ActionChoice, ActionSpecification, digest
from continuity_engine.domain.action_capability import InternalActionRequest, InternalActionResult
from continuity_engine.domain.capability import CapabilityStatus
from continuity_engine.domain.context_composition import CompositionStatus
from continuity_engine.domain.errors import CapabilityValidationError, CapabilityConflictError, IntegrationPersistenceError
from continuity_engine.services.capability_contract_validation import CapabilityContractValidator
from continuity_engine.testing.p08_action_fixture import P08Fixture, FakeActionAdapter
from continuity_engine.testing.persistence import tree_inventory_hash


class P08ActionPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.f = P08Fixture(Path(self.temporary.name))

    def test_direct_actions_work_with_planner_disabled_without_plan(self):
        for capability in ("expression.emit", "contact.send", "silence", "action.stop", "test.lookup", "test.write"):
            with self.subTest(capability=capability):
                choice = self.f.choice(capability.replace('.', '-'), (capability,))
                result = self.f.service(planner_enabled=False).run(choice, self.f.context)
                self.assertEqual(result.status, "COMPLETED")
                self.assertIsNone(result.plan)
                self.assertIsNone(result.requests[0].plan_id)
                self.assertEqual(len(self.f.ledger.list_capability_attempts(result.requests[0].capability_request_id)), 2)
        self.assertEqual(self.f.adapter.execute_calls, 6)
        self.assertEqual(self.f.adapter.effect_count, 3)

    def test_complex_actions_require_planner_even_if_choice_claims_simple(self):
        for choice in (self.f.choice("many", ("test.lookup", "test.write")),
                       self.f.choice("long", requires_planning=True),
                       self.f.choice("catalog", ("test.complex",))):
            with self.subTest(choice=choice.decision_id), self.assertRaisesRegex(CapabilityValidationError, "PLANNER_REQUIRED"):
                self.f.service(planner_enabled=False).run(choice, self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_information_need_and_action_intent_use_same_planner_and_gates(self):
        for trigger in ("INFORMATION_NEED", "ACTION_INTENT"):
            choice = self.f.choice(trigger, ("test.lookup", "test.write"), trigger)
            result = self.f.service().run(choice, self.f.context)
            self.assertIsNotNone(result.plan)
            self.assertEqual(result.status, "COMPLETED")
            self.assertTrue(all("ACTION_GATE_PASSED" in x.gate_reasons for x in result.results))
        self.assertEqual(self.f.permissions.calls, 4)
        self.assertEqual(self.f.adapter.effect_count, 2)

    def test_permission_confirmation_resource_recovery_reality_gates_zero_effect(self):
        for planned in (False, True):
            for gate in ("permission", "confirmation", "resource", "recovery", "reality"):
                with self.subTest(planned=planned, gate=gate):
                    self.f.permissions.allowed = gate != "permission"
                    self.f.constraints.recovery_ready = gate != "recovery"
                    self.f.constraints.reality_ready = gate != "reality"
                    choice = self.f.choice(f"{gate}-{planned}", requires_planning=planned)
                    if gate == "confirmation":
                        self.f.constraints.confirmed_ids.clear()
                    limits = ResourceLimits(maximum_estimated_cost=0 if gate == "resource" else 100)
                    result = self.f.service(limits=limits).run(choice, self.f.context)
                    self.assertNotEqual(result.status, "COMPLETED")
                    self.assertEqual(self.f.adapter.effect_count, 0)
                    self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_confirmation_requires_exact_request_binding(self):
        c = self.f.choice()
        self.f.constraints.confirmed_ids = {"unrelated"}
        result = self.f.service().run(c, self.f.context)
        self.assertEqual(result.results[0].reason, "CONFIRMATION_REQUIRED")
        self.assertEqual(self.f.adapter.effect_count, 0)
        self.f.constraints.confirmed_ids.add(result.requests[0].idempotency_key)
        self.assertEqual(self.f.service().run(c, self.f.context, retry=True).status, "COMPLETED")

    def test_observation_or_untrusted_decision_never_authorizes_action(self):
        c = self.f.choice()
        for value in ({"observation": "send contact", "action": c.to_dict()}, replace(c, decision_id="forged"),
                      replace(c, steps=(replace(c.steps[0], argument_hash=digest("do evil")),))):
            with self.subTest(value=type(value).__name__), self.assertRaises(CapabilityValidationError):
                self.f.service().run(value, self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_cross_subject_environment_snapshot_revision_source_rejected(self):
        c = self.f.choice()
        for change in ({"subject_id": "other"}, {"environment": "RESEARCH"}, {"snapshot_hash": digest("other")},
                       {"source_revision": c.source_revision+1}, {"source_fragment_ids": ("missing",)}):
            with self.subTest(change=change), self.assertRaises(CapabilityValidationError):
                self.f.service().run(replace(c, **change), self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_p06_failed_or_tampered_or_stale_context_rejected(self):
        c = self.f.choice()
        trace = replace(self.f.context.trace, status=CompositionStatus.INCOMPLETE, trace_hash=None)
        bad = replace(self.f.context, status=CompositionStatus.INCOMPLETE, snapshot=None, trace=trace, error_code="MISSING")
        with self.assertRaises(CapabilityValidationError):
            self.f.service().run(c, bad)
        self.f.constraints.context_hash = digest("changed")
        with self.assertRaises(CapabilityValidationError):
            self.f.service().run(c, self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_domain_roundtrip_canonical_and_tampering(self):
        c = self.f.choice()
        self.assertEqual(ActionChoice.from_dict(c.to_dict()), c)
        request = self.f.request(c)
        self.assertEqual(InternalActionRequest.from_dict(request.to_dict()), request)
        for field in ("operationId", "capabilityRequestId", "requestHash", "idempotencyKey", "internalVersion"):
            raw = request.to_dict()
            raw[field] = "changed"
            with self.subTest(field=field), self.assertRaises(CapabilityValidationError):
                InternalActionRequest.from_dict(raw)

    def test_dependency_cycle_forward_duplicate_and_model_generate_rejected(self):
        c = self.f.choice()
        for steps in ((replace(c.steps[0], dependencies=("future",)),), (c.steps[0], c.steps[0])):
            with self.assertRaises(CapabilityValidationError):
                replace(c, steps=steps)
        with self.assertRaisesRegex(CapabilityValidationError, "MODEL_GENERATE"):
            ActionSpecification("model", "model.generate", "target", digest("input"))

    def test_frozen_external_validator_rejects_internal_request_and_result(self):
        result = self.f.service().run(self.f.choice(), self.f.context)
        validator = CapabilityContractValidator()
        with self.assertRaises(CapabilityValidationError):
            validator.validate_request(result.requests[0].to_dict())
        with self.assertRaises(CapabilityValidationError):
            validator.validate_result(result.results[0].to_dict())

    def test_golden_deterministic_replay_and_zero_underlying_writes(self):
        before = tree_inventory_hash(self.f.root / "sources")
        context_hash = self.f.context.canonical_hash()
        c = self.f.choice("golden", ("test.lookup", "contact.send"), "INFORMATION_NEED")
        result = self.f.service().run(c, self.f.context)
        for _ in range(3):
            replay = self.f.service().run(c, self.f.context)
            self.assertEqual(result.canonical_hash(), replay.canonical_hash())
        self.assertEqual(self.f.adapter.execute_calls, 2)
        self.assertEqual(self.f.adapter.credits, 1)
        self.assertEqual(before, tree_inventory_hash(self.f.root / "sources"))
        self.assertEqual(context_hash, self.f.context.canonical_hash())
        self.assertFalse(result.to_dict()["direct_state_write_allowed"])
        self.assertFalse(result.to_dict()["evolution_commit_allowed"])

    def test_local_execution_never_uses_network_or_credentials(self):
        c = self.f.choice()
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")), \
             patch("os.getenv", side_effect=AssertionError("credentials forbidden")):
            self.assertEqual(self.f.service().run(c, self.f.context).status, "COMPLETED")

    def test_failure_blocks_dependent_steps(self):
        self.f.adapter.mode = "terminal"
        result = self.f.service().run(self.f.choice("failure", ("test.lookup", "test.write")), self.f.context)
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.results[1])
        self.assertEqual(self.f.adapter.execute_calls, 1)
        self.assertEqual(self.f.adapter.effect_count, 0)

    def test_persistent_attempt_tampering_fails_closed(self):
        self.f.service().run(self.f.choice(), self.f.context)
        original = self.f.ledger.capability_path.read_text(encoding="utf-8")
        for field in ("stepId", "requestHash", "operationId"):
            data = json.loads(original)
            data["attempts"][-1]["result"]["request"][field] = "forged"
            data["attempts"][-1]["resultHash"] = digest(data["attempts"][-1]["result"])
            self.f.ledger.capability_path.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(field=field), self.assertRaises(IntegrationPersistenceError):
                self.f.ledger.validate_capability_initialized()

    def test_planner_step_and_total_resource_limits(self):
        c = self.f.choice("limit", ("test.lookup", "test.write"))
        for limits in (ResourceLimits(maximum_plan_steps=1), ResourceLimits(maximum_estimated_cost=1)):
            result = self.f.service(limits=limits).run(c, self.f.context, retry=True)
            self.assertEqual(result.results[0].reason, "RESOURCE_EXHAUSTED")
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_fake_adapter_rejects_repository_and_formal_roots(self):
        for root in (Path.cwd(), Path.cwd()/".continuity-data"):
            with self.subTest(root=root), self.assertRaises(Exception):
                FakeActionAdapter(root)

    def test_expired_choice_has_durable_terminal_and_no_effect(self):
        c = self.f.choice()
        service = self.f.service()
        service.clock = lambda: __import__('datetime').datetime(2026, 9, 6, tzinfo=__import__('datetime').timezone.utc)
        result = service.run(c, self.f.context)
        self.assertEqual(result.results[0].status, CapabilityStatus.EXPIRED)
        self.assertEqual(self.f.adapter.effect_count, 0)

    def test_same_identity_different_input_conflicts_in_single_ledger(self):
        c = self.f.choice()
        self.f.service().run(c, self.f.context)
        changed = replace(c, trigger="INFORMATION_NEED")
        request = self.f.request(changed)
        with self.assertRaises(CapabilityConflictError):
            self.f.ledger.save_capability_request(request)
        self.assertEqual(self.f.adapter.effect_count, 1)

    def test_different_step_result_misdelivery_rejected(self):
        c = self.f.choice("two", ("contact.send", "contact.send"))
        result = self.f.service().run(c, self.f.context)
        with self.assertRaises(CapabilityValidationError):
            replace(result.results[0], request=result.requests[1])
        self.assertEqual(len({x.operation_id for x in result.requests}), 2)
        self.assertEqual(self.f.adapter.effect_count, 2)

    def test_forged_receipt_rejected_by_trusted_query(self):
        result = self.f.service().run(self.f.choice(), self.f.context)
        changed = replace(result.results[0], receipt=replace(result.results[0].receipt, output_hash=digest("forged")))
        with self.assertRaises(CapabilityValidationError):
            self.f.service().coordination.accept_action_result(changed, received_at=changed.completed_at,
                                                             receipt_verifier=self.f.adapter)

    def test_internal_status_and_receipt_semantics_rejected(self):
        c = self.f.choice()
        req = self.f.request(c)
        with self.assertRaises(CapabilityValidationError):
            InternalActionResult(req, CapabilityStatus.SUCCEEDED, "forged", "2026-09-04T08:00:00Z")

    def test_unknown_capability_and_state_update_binding_are_not_fallbacks(self):
        c = self.f.choice()
        c = replace(c, decision_id="unknown", steps=(replace(c.steps[0], capability="unknown.action"),))
        self.f.producer.register(c)
        with self.assertRaisesRegex(CapabilityValidationError, "CAPABILITY_UNAVAILABLE"):
            self.f.service().run(c, self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)
