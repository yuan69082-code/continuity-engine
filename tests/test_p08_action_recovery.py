from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from continuity_engine.domain.action_capability import InternalActionRequest
from continuity_engine.domain.capability import CapabilityStatus
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from continuity_engine.testing.p08_action_fixture import P08Fixture, FakeActionAdapter
from tests.test_e5_capability_flow import CapabilityFixture, capability_result_payload
from tests.test_contract_test_adapter import first_round_request


class P08ActionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = P08Fixture(Path(self.tmp.name))

    def restart(self):
        self.f.ledger = JsonIntegrationResultLedger(self.f.root)
        self.f.adapter = FakeActionAdapter(self.f.root)
        return self.f.service()

    def test_restart_completed_returns_exact_result_and_no_execution(self):
        c = self.f.choice()
        before = self.f.service().run(c, self.f.context)
        after = self.restart().run(c, self.f.context)
        self.assertEqual(before.canonical_hash(), after.canonical_hash())
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 1)
        self.assertEqual(self.f.adapter.credits, 1)

    def test_crash_matrix_keeps_single_effect_and_step_identity(self):
        for point in ("after_requests", "before_adapter", "after_adapter_before_result", "after_result"):
            with self.subTest(point=point):
                c = self.f.choice(point, ("test.lookup", "contact.send"))
                fired = []
                def fault(stage):
                    if stage == point and not fired:
                        fired.append(stage)
                        raise RuntimeError("synthetic interruption")
                with self.assertRaises(RuntimeError):
                    self.f.service(fault=fault).run(c, self.f.context)
                service = self.restart()
                result = service.run(c, self.f.context, retry=True)
                self.assertEqual(result.status, "COMPLETED")
                stable = result.canonical_hash()
                self.assertEqual(service.run(c, self.f.context).canonical_hash(), stable)
                for request in result.requests:
                    attempts = self.f.ledger.list_capability_attempts(request.capability_request_id)
                    self.assertEqual(sum(x.result.status is CapabilityStatus.SUCCEEDED for x in attempts), 1)
        self.assertEqual(self.f.adapter.effect_count, 4)
        self.assertEqual(self.f.adapter.credits, 4)

    def test_effect_before_engine_receipt_crash_recovers_by_query_only(self):
        c = self.f.choice()
        def crash(point):
            if point == "after_adapter_before_result":
                raise RuntimeError("crash after Fake effect")
        with self.assertRaises(RuntimeError):
            self.f.service(fault=crash).run(c, self.f.context)
        self.assertEqual(self.f.adapter.effect_count, 1)
        result = self.restart().run(c, self.f.context)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertGreater(self.f.adapter.query_calls, 0)
        self.assertEqual(self.f.adapter.credits, 1)

    def test_lost_response_preserves_unknown_history_then_resolves_once(self):
        c = self.f.choice()
        self.f.adapter.mode = "lost_response"
        result = self.f.service().run(c, self.f.context)
        self.assertEqual(result.results[0].status, CapabilityStatus.UNKNOWN)
        result = self.restart().run(c, self.f.context)
        attempts = self.f.ledger.list_capability_attempts(result.requests[0].capability_request_id)
        self.assertEqual([x.result.status.value for x in attempts], ["PROPOSED", "UNKNOWN", "SUCCEEDED"])
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 1)

    def test_unknown_never_blindly_retries(self):
        c = self.f.choice()
        self.f.adapter.mode = "unknown"
        for retry in (False, True, True):
            result = self.f.service().run(c, self.f.context, retry=retry)
            self.assertEqual(result.results[0].status, CapabilityStatus.UNKNOWN)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 0)

    def test_not_executed_requires_explicit_controlled_retry(self):
        c = self.f.choice()
        self.f.adapter.mode = "before_failure"
        self.f.service().run(c, self.f.context)
        calls = self.f.adapter.execute_calls
        self.f.adapter.mode = "success"
        self.assertEqual(self.f.service().run(c, self.f.context).status, "WAITING_CAPABILITY")
        self.assertEqual(self.f.adapter.execute_calls, calls)
        self.assertEqual(self.f.service().run(c, self.f.context, retry=True).status, "COMPLETED")
        self.assertEqual(self.f.adapter.effect_count, 1)

    def test_repeat_result_does_not_append_attempt_or_credit(self):
        result = self.f.service().run(self.f.choice(), self.f.context)
        path = self.f.ledger.capability_path
        before = path.read_bytes()
        value = result.results[0]
        for _ in range(3):
            self.f.service().coordination.accept_action_result(value, received_at=value.completed_at,
                                                               receipt_verifier=self.f.adapter)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(self.f.adapter.credits, 1)

    def test_model_wait_and_action_share_ledger_without_cross_resume(self):
        old = CapabilityFixture()
        old.setUp()
        self.addCleanup(old.tearDown)
        app = old.capability_app()
        required = app.adapter.submit(first_round_request())
        ledger = JsonIntegrationResultLedger(old.data)
        initial = json.loads(ledger.capability_path.read_text(encoding="utf-8"))
        self.assertEqual(initial["capabilityLedgerFormatVersion"], 1)
        # Explicit temporary copy of the old-format model ledger is opened by the new code.
        self.f.ledger = ledger
        action = self.f.service().run(self.f.choice(), self.f.context)
        mixed = json.loads(ledger.capability_path.read_text(encoding="utf-8"))
        self.assertEqual(mixed["capabilityLedgerFormatVersion"], 2)
        self.assertEqual(mixed["requests"][0], initial["requests"][0])
        self.assertIsInstance(ledger.load_capability_request(action.requests[0].capability_request_id), InternalActionRequest)
        completed = old.capability_app().adapter.submit_capability_result(capability_result_payload(required))
        replay = old.capability_app().adapter.submit(first_round_request())
        self.assertEqual(completed.to_dict(), replay.to_dict())
        self.assertEqual(required.capability_request.originating_session_id,
                         ledger.load_capability_request(required.capability_request.capability_request_id).originating_session_id)
        self.assertEqual(self.f.service().run(self.f.producer.resolve("choice-one"), self.f.context).canonical_hash(),
                         action.canonical_hash())

    def test_old_completed_records_remain_exact_and_no_second_result(self):
        old = CapabilityFixture()
        old.setUp()
        self.addCleanup(old.tearDown)
        app = old.capability_app()
        req = app.adapter.submit(first_round_request())
        complete = app.adapter.submit_capability_result(capability_result_payload(req))
        ledger = JsonIntegrationResultLedger(old.data)
        model_before = json.loads(ledger.capability_path.read_text(encoding="utf-8"))
        self.f.ledger = ledger
        self.f.service().run(self.f.choice(), self.f.context)
        model_after = json.loads(ledger.capability_path.read_text(encoding="utf-8"))
        self.assertEqual(model_after["requests"][0], model_before["requests"][0])
        self.assertEqual(model_after["attempts"][0], model_before["attempts"][0])
        self.assertEqual(old.capability_app().adapter.submit(first_round_request()).to_dict(), complete.to_dict())
        self.assertEqual(len(ledger.list_completed()), 1)
        self.assertEqual(len(ledger.list_operations()), 1)

    def test_pending_action_cannot_switch_adapter_after_unconfirmed_effect(self):
        from continuity_engine.domain.errors import CapabilityConflictError
        c = self.f.choice()
        def crash(point):
            if point == "after_adapter_before_result":
                raise RuntimeError("synthetic interrupted receipt delivery")
        with self.assertRaises(RuntimeError):
            self.f.service(fault=crash).run(c, self.f.context)
        original_adapter = self.f.adapter
        self.assertEqual(original_adapter.effect_count, 1)
        self.f.adapter = FakeActionAdapter(self.f.root / "different-adapter")
        self.f.adapter.adapter_id = "different-adapter-v1"
        with self.assertRaises(CapabilityConflictError):
            self.f.service().run(c, self.f.context, retry=True)
        self.assertEqual(self.f.adapter.effect_count, 0)

    def test_context_change_between_steps_blocks_later_effect(self):
        from continuity_engine.domain.errors import CapabilityValidationError
        from continuity_engine.domain.action_planning import digest
        c = self.f.choice("context-drift", ("contact.send", "contact.send"))
        results_saved = []
        def change_context(point):
            if point == "after_result":
                results_saved.append(point)
                if len(results_saved) == 2:
                    self.f.constraints.context_hash = digest("new revision")
        with self.assertRaises(CapabilityValidationError):
            self.f.service(fault=change_context).run(c, self.f.context)
        self.assertEqual(self.f.adapter.effect_count, 1)

    def test_terminal_replay_does_not_read_clock_or_reexecute(self):
        c = self.f.choice()
        original = self.f.service().run(c, self.f.context)
        service = self.restart()
        def no_clock():
            raise AssertionError("completed replay must not generate a new time")
        service.clock = no_clock
        self.assertEqual(service.run(c, self.f.context).canonical_hash(), original.canonical_hash())
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_policy_drift_on_pending_request_fails_closed(self):
        from dataclasses import replace
        from continuity_engine.domain.errors import CapabilityConflictError
        c = self.f.choice()
        self.f.adapter.mode = "unknown"
        self.f.service().run(c, self.f.context)
        service = self.f.service()
        service.capabilities["contact.send"] = replace(service.capabilities["contact.send"], cost=2)
        with self.assertRaises(CapabilityConflictError):
            service.run(c, self.f.context, retry=True)
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_forged_persisted_success_cannot_release_dependent_action(self):
        from continuity_engine.domain.action_capability import ActionReceipt, InternalActionResult
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("forged-history", ("test.lookup", "contact.send"))
        self.f.adapter.mode = "unknown"
        waiting = self.f.service().run(c, self.f.context)
        request = waiting.requests[0]
        receipt = ActionReceipt(
            "forged-receipt", request.capability_request_id, request.request_hash,
            request.adapter_id, request.subject_id, request.choice.environment,
            request.step_id, "SUCCEEDED", 0, 0, "2026-09-04T08:00:00Z", digest("forged"),
        )
        result = InternalActionResult(request, CapabilityStatus.SUCCEEDED,
                                      "VERIFIED_RECEIPT", receipt.completed_at, receipt)
        # Bypass coordinator to model a self-consistent forged persisted ledger.
        self.f.ledger.save_capability_result(result, received_at=result.completed_at)
        self.assertEqual(self.f.adapter.receipts(), ())
        service = self.restart()
        error = None
        recovered = None
        before = self.f.ledger.capability_path.read_bytes()
        try:
            recovered = service.run(c, self.f.context)
        except CapabilityValidationError as exc:
            error = exc
        print("FORGED_HISTORY_RECOVERY", recovered.status if recovered else "REJECTED",
              "effect=", self.f.adapter.effect_count, "query_calls=", self.f.adapter.query_calls)
        self.assertIsInstance(error, CapabilityValidationError)
        self.assertEqual(self.f.adapter.effect_count, 0)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)

    def test_stale_context_recovers_already_executed_receipt_without_new_authorization(self):
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("stale-receipt")
        def crash(point):
            if point == "after_adapter_before_result":
                raise RuntimeError("effect committed before Engine receipt")
        with self.assertRaises(RuntimeError):
            self.f.service(fault=crash).run(c, self.f.context)
        self.assertEqual(self.f.adapter.effect_count, 1)
        self.f.constraints.context_hash = digest("context revoked after execution")
        service = self.restart()
        error = None
        recovered = None
        try:
            recovered = service.run(c, self.f.context)
        except CapabilityValidationError as exc:
            error = exc
        print("STALE_CONTEXT_RECEIPT_RECOVERY", str(error) if error else recovered.status,
              "effect=", self.f.adapter.effect_count, "query_calls=", self.f.adapter.query_calls)
        self.assertIsNone(error)
        self.assertEqual(recovered.status, "COMPLETED")
        self.assertGreater(self.f.adapter.query_calls, 0)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 1)
        self.assertEqual(self.f.adapter.credits, 1)
        attempts = self.f.ledger.list_capability_attempts(recovered.requests[0].capability_request_id)
        self.assertEqual(sum(x.result.status is CapabilityStatus.SUCCEEDED for x in attempts), 1)

    def test_historical_receipt_requires_independent_query_on_load_replay_and_append(self):
        from dataclasses import replace
        from unittest.mock import patch
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        from continuity_engine.services.action_planning_service import ReceiptQuery
        c = self.f.choice("verify-history")
        original = self.f.service().run(c, self.f.context)
        receipt = original.results[0].receipt
        for mode in ("missing", "unknown", "drift", "unavailable"):
            with self.subTest(mode=mode):
                service = self.restart()
                before = self.f.ledger.capability_path.read_bytes()
                facts = self.f.adapter.path.read_bytes()
                value = {"missing": ReceiptQuery.NOT_EXECUTED, "unknown": ReceiptQuery.UNKNOWN,
                         "drift": replace(receipt, output_hash=digest("different output"))}.get(mode)
                kwargs = {"side_effect": RuntimeError("query unavailable")} if mode == "unavailable" else {"return_value": value}
                with patch.object(self.f.adapter, "query", **kwargs) as query:
                    for consume in (
                        lambda: service.coordination.action_attempts(original.requests[0], receipt_verifier=self.f.adapter),
                        lambda: service.run(c, self.f.context, retry=True),
                        lambda: service.coordination.accept_action_result(
                            original.results[0], received_at=original.results[0].completed_at,
                            receipt_verifier=self.f.adapter),
                    ):
                        with self.assertRaisesRegex(CapabilityValidationError, "EXECUTION_FACT_"):
                            consume()
                    self.assertEqual(query.call_count, 3)
                self.assertEqual(self.f.adapter.execute_calls, 0)
                self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
                self.assertEqual(self.f.adapter.path.read_bytes(), facts)

    def test_rehashed_persisted_receipt_field_drift_is_not_execution_proof(self):
        from copy import deepcopy
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("rehashed-history")
        self.f.service().run(c, self.f.context)
        original = json.loads(self.f.ledger.capability_path.read_text(encoding="utf-8"))
        for change in (
            {"receipt_id": "other-receipt"}, {"output_hash": digest("forged output")},
            {"effect_count": 0, "test_credits": 0}, {"completed_at": "2026-09-04T08:00:01Z"},
            {"status": "FAILED_TERMINAL", "effect_count": 0, "test_credits": 0},
        ):
            with self.subTest(change=change):
                data = deepcopy(original)
                attempt = data["attempts"][-1]
                attempt["result"]["receipt"].update(change)
                attempt["result"]["status"] = attempt["result"]["receipt"]["status"]
                attempt["result"]["completedAt"] = attempt["result"]["receipt"]["completed_at"]
                attempt["receivedAt"] = attempt["result"]["completedAt"]
                attempt["resultHash"] = digest(attempt["result"])
                self.f.ledger.capability_path.write_text(json.dumps(data), encoding="utf-8")
                service = self.restart()
                before = self.f.ledger.capability_path.read_bytes()
                with self.assertRaisesRegex(CapabilityValidationError, "EXECUTION_FACT_"):
                    service.run(c, self.f.context)
                self.assertEqual(self.f.adapter.execute_calls, 0)
                self.assertEqual(self.f.adapter.effect_count, 1)
                self.assertEqual(self.f.adapter.credits, 1)
                self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)

    def test_stale_context_terminal_replay_preserves_exact_history_without_clock_or_new_gates(self):
        from continuity_engine.domain.action_planning import digest
        c = self.f.choice("stale-terminal")
        original = self.f.service().run(c, self.f.context)
        before = self.f.ledger.capability_path.read_bytes()
        self.f.constraints.context_hash = digest("revoked")
        self.f.constraints.confirmed_ids.clear()
        self.f.constraints.recovery_ready = self.f.constraints.reality_ready = False
        self.f.permissions.allowed = False
        service = self.restart()
        def no_clock():
            raise AssertionError("exact history replay must not create a timestamp")
        service.clock = no_clock
        permission_calls = self.f.permissions.calls
        for retry in (False, True, False):
            result = service.run(c, self.f.context, retry=retry)
            self.assertEqual(result.canonical_hash(), original.canonical_hash())
        self.assertEqual(self.f.adapter.query_calls, 3)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.permissions.calls, permission_calls)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))

    def test_stale_context_archives_first_effect_but_blocks_unexecuted_plan_step(self):
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("stale-plan", ("contact.send", "contact.send"))
        def crash(point):
            if point == "after_adapter_before_result":
                raise RuntimeError("first effect before result")
        with self.assertRaises(RuntimeError):
            self.f.service(fault=crash).run(c, self.f.context)
        self.f.constraints.context_hash = digest("revoked before recovery")
        service = self.restart()
        for retry in (False, True):
            with self.assertRaisesRegex(CapabilityValidationError, "CONTEXT_CHANGED_BEFORE_ACTION"):
                service.run(c, self.f.context, retry=retry)
        document = json.loads(self.f.ledger.capability_path.read_text(encoding="utf-8"))
        requests = tuple(InternalActionRequest.from_dict(x) for x in document["requests"])
        by_step = {x.step_id: self.f.ledger.list_capability_attempts(x.capability_request_id) for x in requests}
        self.assertEqual(sum(x.result.status is CapabilityStatus.SUCCEEDED for x in by_step["step-0"]), 1)
        self.assertEqual(len(by_step["step-1"]), 0)
        self.assertEqual(len(self.f.adapter.receipts()), 1)
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))
        self.assertEqual(self.f.adapter.execute_calls, 0)

    def test_stale_context_unknown_remains_query_only_even_with_retry(self):
        from continuity_engine.domain.action_planning import digest
        c = self.f.choice("stale-unknown")
        self.f.adapter.mode = "unknown"
        original = self.f.service().run(c, self.f.context)
        before = self.f.ledger.capability_path.read_bytes()
        self.f.constraints.context_hash = digest("revoked")
        service = self.restart()
        self.f.adapter.mode = "unknown"
        for retry in (False, True):
            result = service.run(c, self.f.context, retry=retry)
            self.assertEqual(result.canonical_hash(), original.canonical_hash())
        self.assertEqual(self.f.adapter.query_calls, 2)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.receipts(), ())
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)

    def test_stale_context_not_executed_retry_and_new_request_are_blocked(self):
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("stale-retry")
        self.f.adapter.mode = "before_failure"
        self.f.service().run(c, self.f.context)
        self.f.constraints.context_hash = digest("revoked")
        service = self.restart()
        before = self.f.ledger.capability_path.read_bytes()
        with self.assertRaisesRegex(CapabilityValidationError, "CONTEXT_CHANGED_BEFORE_ACTION"):
            service.run(c, self.f.context, retry=True)
        queries = self.f.adapter.query_calls
        new = self.f.choice("new-stale-choice")
        with self.assertRaisesRegex(CapabilityValidationError, "CONTEXT_STALE_OR_UNAUTHORIZED"):
            service.run(new, self.f.context)
        self.assertEqual(self.f.adapter.query_calls, queries)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.receipts(), ())
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)

    def test_stale_recovery_keeps_choice_snapshot_producer_adapter_and_policy_binding(self):
        from dataclasses import replace
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError, CapabilityConflictError
        c = self.f.choice("stale-identity")
        self.f.service().run(c, self.f.context)
        self.f.constraints.context_hash = digest("revoked")
        service = self.restart()
        for change in ({"subject_id": "different"}, {"environment": "RESEARCH"},
                       {"snapshot_hash": digest("different snapshot")}, {"source_revision": 999},
                       {"producer_id": "different-producer"}, {"source_fragment_ids": ("missing",)}):
            with self.subTest(change=change), self.assertRaises(CapabilityValidationError):
                service.run(replace(c, **change), self.f.context)
        binding = service.capabilities["contact.send"]
        service.capabilities["contact.send"] = replace(binding, cost=2)
        with self.assertRaises(CapabilityConflictError):
            service.run(c, self.f.context)
        other = FakeActionAdapter(self.f.root / "other")
        other.adapter_id = "other-adapter"
        service.capabilities["contact.send"] = replace(binding, adapter=other)
        with self.assertRaises(CapabilityConflictError):
            service.run(c, self.f.context)
        self.assertEqual(self.f.adapter.query_calls, 0)
        self.assertEqual(other.query_calls, 0)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 1)

    def test_receipt_recovery_does_not_authorize_next_step_through_other_gates(self):
        from continuity_engine.domain.action import ResourceLimits
        for gate in ("permission", "confirmation", "resource", "recoverability", "reality"):
            with self.subTest(gate=gate):
                f = P08Fixture(self.f.root / gate)
                c = f.choice(gate, ("contact.send", "contact.send"))
                def crash(point):
                    if point == "after_adapter_before_result":
                        raise RuntimeError("first effect")
                with self.assertRaises(RuntimeError):
                    f.service(fault=crash).run(c, f.context)
                f.ledger = JsonIntegrationResultLedger(f.root)
                f.adapter = FakeActionAdapter(f.root)
                if gate == "permission":
                    f.permissions.allowed = False
                elif gate == "confirmation":
                    f.constraints.confirmed_ids.clear()
                elif gate == "recoverability":
                    f.constraints.recovery_ready = False
                elif gate == "reality":
                    f.constraints.reality_ready = False
                limits = ResourceLimits(maximum_estimated_cost=0) if gate == "resource" else None
                result = f.service(limits=limits).run(c, f.context, retry=True)
                self.assertIs(result.results[0].status, CapabilityStatus.SUCCEEDED)
                self.assertIsNot(result.results[1].status, CapabilityStatus.SUCCEEDED)
                self.assertEqual(f.adapter.execute_calls, 0)
                self.assertEqual((f.adapter.effect_count, f.adapter.credits), (1, 1))
                self.assertEqual(len(f.adapter.receipts()), 1)

    def test_receiptless_terminal_failure_cannot_mask_lost_success_on_append(self):
        from continuity_engine.domain.action_capability import InternalActionResult
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("receiptless-failure")
        self.f.adapter.mode = "lost_response"
        waiting = self.f.service().run(c, self.f.context)
        self.assertIs(waiting.results[0].status, CapabilityStatus.UNKNOWN)
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))
        before = self.f.ledger.capability_path.read_bytes()
        calls = self.f.adapter.query_calls
        error = None
        try:
            forged = InternalActionResult(waiting.requests[0], CapabilityStatus.FAILED_TERMINAL,
                                          "VERIFIED_RECEIPT", "2026-09-04T08:00:00Z", None)
            self.f.service().coordination.accept_action_result(
                forged, received_at=forged.completed_at, receipt_verifier=self.f.adapter)
        except CapabilityValidationError as exc:
            error = exc
        append_queries = self.f.adapter.query_calls - calls
        if error is not None:
            self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        recovered = self.restart().run(c, self.f.context)
        print("RECEIPTLESS_FAILURE", "REJECTED" if error else "ACCEPTED",
              "append_queries=", append_queries, "recovered=", recovered.status,
              "effect=", self.f.adapter.effect_count)
        self.assertIsInstance(error, CapabilityValidationError)
        self.assertEqual(recovered.status, "COMPLETED")
        self.assertEqual(self.f.adapter.execute_calls, 0)
        # Recovery may append the real success, but must never contain the forged failure.
        attempts = self.f.ledger.list_capability_attempts(waiting.requests[0].capability_request_id)
        self.assertFalse(any(x.result.status is CapabilityStatus.FAILED_TERMINAL for x in attempts))
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))

    def test_rehashed_expired_terminal_cannot_hide_independent_success(self):
        from datetime import timedelta
        from continuity_engine.domain.capability import parse_capability_datetime
        from continuity_engine.domain.integration_results import format_contract_datetime
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("forged-expiry")
        self.f.adapter.mode = "lost_response"
        waiting = self.f.service().run(c, self.f.context)
        data = json.loads(self.f.ledger.capability_path.read_text(encoding="utf-8"))
        attempt = data["attempts"][-1]
        after_expiry = format_contract_datetime(parse_capability_datetime(c.expires_at) + timedelta(hours=1))
        attempt["result"].update(status="EXPIRED", reason="CHOICE_EXPIRED", receipt=None,
                                 completedAt=after_expiry, gateReasons=["CHOICE_EXPIRED"])
        attempt["receivedAt"] = after_expiry
        attempt["resultHash"] = digest(attempt["result"])
        self.f.ledger.capability_path.write_text(json.dumps(data), encoding="utf-8")
        before = self.f.ledger.capability_path.read_bytes()
        receipts = self.f.adapter.path.read_bytes()
        service = self.restart()
        error = None
        recovered = None
        try:
            recovered = service.run(c, self.f.context)
        except CapabilityValidationError as exc:
            error = exc
        print("REHASHED_EXPIRED", "REJECTED" if error else recovered.status,
              "query_calls=", self.f.adapter.query_calls, "effect=", self.f.adapter.effect_count)
        self.assertIsInstance(error, CapabilityValidationError)
        self.assertGreater(self.f.adapter.query_calls, 0)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual(self.f.adapter.path.read_bytes(), receipts)
        self.assertEqual(self.f.adapter.receipts()[0].status, "SUCCEEDED")

    def test_internal_result_status_evidence_matrix_and_roundtrip(self):
        from dataclasses import replace
        from continuity_engine.domain.action_capability import InternalActionResult
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("status-matrix")
        original = self.f.service().run(c, self.f.context).results[0]
        failure = replace(original.receipt, status="FAILED_TERMINAL", effect_count=0, test_credits=0)
        valid = (
            original, replace(original, status=CapabilityStatus.FAILED_TERMINAL, receipt=failure),
            InternalActionResult(original.request, CapabilityStatus.EXPIRED, "CHOICE_EXPIRED",
                                 c.expires_at, gate_reasons=("CHOICE_EXPIRED",)),
            InternalActionResult(original.request, CapabilityStatus.PROPOSED, "READY_TO_EXECUTE", original.completed_at),
            InternalActionResult(original.request, CapabilityStatus.UNKNOWN, "EXECUTION_UNCONFIRMED", original.completed_at),
        )
        for result in valid:
            with self.subTest(status=result.status):
                self.assertEqual(InternalActionResult.from_dict(result.to_dict()), result)
        for status in (CapabilityStatus.SUCCEEDED, CapabilityStatus.FAILED_TERMINAL,
                       CapabilityStatus.CANCELLED, CapabilityStatus.FAILED_RETRYABLE):
            with self.subTest(missing=status), self.assertRaises(CapabilityValidationError):
                InternalActionResult(original.request, status, "VERIFIED_RECEIPT", original.completed_at)
        for change in (
            {"status": CapabilityStatus.CANCELLED}, {"status": CapabilityStatus.FAILED_RETRYABLE},
            {"status": CapabilityStatus.FAILED_TERMINAL}, {"reason": "asserted-success"},
        ):
            with self.subTest(change=change), self.assertRaises(CapabilityValidationError):
                replace(original, **change)
        expiry = valid[2]
        for change in ({"reason": "VERIFIED_RECEIPT"}, {"completed_at": original.completed_at},
                       {"gate_reasons": ()}, {"receipt": original.receipt}):
            with self.subTest(expiry=change), self.assertRaises(CapabilityValidationError):
                replace(expiry, **change)
        for status in (CapabilityStatus.PROPOSED, CapabilityStatus.UNKNOWN):
            with self.subTest(nonterminal=status), self.assertRaises(CapabilityValidationError):
                InternalActionResult(original.request, status, "VERIFIED_RECEIPT", original.completed_at)

    def test_invalid_terminal_shapes_rehashed_reload_fails_closed(self):
        from copy import deepcopy
        from continuity_engine.domain.action_capability import InternalActionResult
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError, IntegrationPersistenceError
        c = self.f.choice("invalid-terminal-load")
        self.f.adapter.mode = "lost_response"
        waiting = self.f.service().run(c, self.f.context)
        original = json.loads(self.f.ledger.capability_path.read_text(encoding="utf-8"))
        changes = (
            {"status": "FAILED_TERMINAL", "reason": "VERIFIED_RECEIPT", "receipt": None},
            {"status": "SUCCEEDED", "reason": "VERIFIED_RECEIPT", "receipt": None},
            {"status": "CANCELLED"}, {"status": "FAILED_RETRYABLE"},
            {"status": "EXPIRED", "reason": "CHOICE_EXPIRED", "gateReasons": ["CHOICE_EXPIRED"]},
            {"status": "EXPIRED", "reason": "asserted-expiry", "completedAt": c.expires_at},
            {"status": "UNKNOWN", "reason": "VERIFIED_RECEIPT"}, {"receipt": {}},
        )
        for change in changes:
            with self.subTest(change=change):
                data = deepcopy(original)
                attempt = data["attempts"][-1]
                attempt["result"].update(change)
                attempt["receivedAt"] = attempt["result"]["completedAt"]
                attempt["resultHash"] = digest(attempt["result"])
                with self.assertRaises(CapabilityValidationError):
                    InternalActionResult.from_dict(attempt["result"])
                self.f.ledger.capability_path.write_text(json.dumps(data), encoding="utf-8")
                before = self.f.ledger.capability_path.read_bytes()
                service = self.restart()
                with self.assertRaises(IntegrationPersistenceError):
                    self.f.ledger.list_capability_attempts(waiting.requests[0].capability_request_id)
                with self.assertRaises(IntegrationPersistenceError):
                    service.run(c, self.f.context)
                self.assertEqual(self.f.adapter.execute_calls, 0)
                self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
                self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))

    def test_legal_success_and_failure_receipts_restart_and_duplicate_exactly(self):
        for mode, status, effects in (("success", CapabilityStatus.SUCCEEDED, 1),
                                      ("terminal", CapabilityStatus.FAILED_TERMINAL, 0)):
            with self.subTest(mode=mode):
                f = P08Fixture(self.f.root / mode)
                c = f.choice(mode)
                f.adapter.mode = mode
                original = f.service().run(c, f.context)
                self.assertIs(original.results[0].status, status)
                before = f.ledger.capability_path.read_bytes()
                f.ledger = JsonIntegrationResultLedger(f.root)
                f.adapter = FakeActionAdapter(f.root)
                service = f.service()
                for _ in range(2):
                    self.assertEqual(service.run(c, f.context).canonical_hash(), original.canonical_hash())
                    value = original.results[0]
                    service.coordination.accept_action_result(value, received_at=value.completed_at, receipt_verifier=f.adapter)
                self.assertEqual(f.ledger.capability_path.read_bytes(), before)
                self.assertEqual(len(f.adapter.receipts()), 1)
                self.assertEqual((f.adapter.effect_count, f.adapter.credits), (effects, effects))
                self.assertEqual(f.adapter.execute_calls, 0)
                self.assertGreater(f.adapter.query_calls, 0)

    def test_legal_expiry_requires_not_executed_and_replays_without_clock(self):
        from continuity_engine.domain.capability import parse_capability_datetime
        c = self.f.choice("legal-expiry")
        service = self.f.service()
        service.clock = lambda: parse_capability_datetime(c.expires_at)
        original = service.run(c, self.f.context)
        self.assertIs(original.results[0].status, CapabilityStatus.EXPIRED)
        self.assertGreaterEqual(self.f.adapter.query_calls, 2)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        before = self.f.ledger.capability_path.read_bytes()
        service = self.restart()
        def no_clock():
            raise AssertionError("expiry replay uses original decision time")
        service.clock = no_clock
        for retry in (False, True):
            self.assertEqual(service.run(c, self.f.context, retry=retry).canonical_hash(), original.canonical_hash())
            result = original.results[0]
            service.coordination.accept_action_result(result, received_at=result.completed_at,
                                                       receipt_verifier=self.f.adapter)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual(self.f.adapter.receipts(), ())
        self.assertEqual(self.f.adapter.execute_calls, 0)

        self.assertEqual(self.f.adapter.query_calls, 6)

    def test_expired_choice_and_stale_context_still_recover_actual_success(self):
        from continuity_engine.domain.capability import parse_capability_datetime
        from continuity_engine.domain.action_planning import digest
        c = self.f.choice("expired-success")
        self.f.adapter.mode = "lost_response"
        waiting = self.f.service().run(c, self.f.context)
        self.assertIs(waiting.results[0].status, CapabilityStatus.UNKNOWN)
        self.f.constraints.context_hash = digest("stale context")
        self.f.constraints.confirmed_ids.clear()
        self.f.constraints.reality_ready = self.f.constraints.recovery_ready = False
        self.f.permissions.allowed = False
        service = self.restart()
        service.clock = lambda: parse_capability_datetime(c.expires_at)
        result = service.run(c, self.f.context, retry=True)
        self.assertEqual(result.status, "COMPLETED")
        self.assertIs(result.results[0].status, CapabilityStatus.SUCCEEDED)
        self.assertEqual(service.run(c, self.f.context).canonical_hash(), result.canonical_hash())
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))
        attempts = self.f.ledger.list_capability_attempts(result.requests[0].capability_request_id)
        self.assertEqual([x.result.status.value for x in attempts], ["PROPOSED", "UNKNOWN", "SUCCEEDED"])

    def test_expired_unknown_invalid_query_and_query_exception_do_not_prove_nonexecution(self):
        from unittest.mock import patch
        from continuity_engine.domain.capability import parse_capability_datetime
        from continuity_engine.services.action_planning_service import ReceiptQuery
        for mode in ("unknown", "exception", "null", "string"):
            with self.subTest(mode=mode):
                f = P08Fixture(self.f.root / mode)
                c = f.choice(mode)
                service = f.service()
                service.clock = lambda: parse_capability_datetime(c.expires_at)
                options = {"side_effect": RuntimeError("synthetic query unavailable")} if mode == "exception" else {
                    "return_value": {"unknown": ReceiptQuery.UNKNOWN, "null": None, "string": "NOT_EXECUTED"}[mode]}
                with patch.object(f.adapter, "query", **options) as query:
                    for retry in (False, True):
                        result = service.run(c, f.context, retry=retry)
                        self.assertIs(result.results[0].status, CapabilityStatus.UNKNOWN)
                    self.assertEqual(query.call_count, 2)
                self.assertEqual(f.adapter.execute_calls, 0)
                self.assertEqual(f.adapter.receipts(), ())
                attempts = f.ledger.list_capability_attempts(result.requests[0].capability_request_id)
                self.assertFalse(any(x.result.status.failed_terminally for x in attempts))

    def test_expiry_append_checks_typed_nonexecution_not_caller_assertion(self):
        from unittest.mock import patch
        from continuity_engine.domain.action_capability import InternalActionResult
        from continuity_engine.domain.errors import CapabilityValidationError
        from continuity_engine.services.action_planning_service import ReceiptQuery
        c = self.f.choice("expiry-append")
        self.f.adapter.mode = "unknown"
        waiting = self.f.service().run(c, self.f.context)
        expiry = InternalActionResult(waiting.requests[0], CapabilityStatus.EXPIRED, "CHOICE_EXPIRED",
                                      c.expires_at, gate_reasons=("CHOICE_EXPIRED",))
        before = self.f.ledger.capability_path.read_bytes()
        for value in (ReceiptQuery.UNKNOWN, None, "NOT_EXECUTED", False):
            with self.subTest(query=value), patch.object(self.f.adapter, "query", return_value=value):
                with self.assertRaisesRegex(CapabilityValidationError, "LOCAL_STOP_NOT_EXECUTED_UNVERIFIED"):
                    self.f.service().coordination.accept_action_result(expiry, received_at=c.expires_at,
                                                                       receipt_verifier=self.f.adapter)
        with patch.object(self.f.adapter, "query", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(CapabilityValidationError, "EXECUTION_FACT_UNVERIFIABLE"):
                self.f.service().coordination.accept_action_result(expiry, received_at=c.expires_at,
                                                                   receipt_verifier=self.f.adapter)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual(self.f.adapter.receipts(), ())
        self.assertEqual(self.f.adapter.execute_calls, 0)

        # A well-shaped local stop also cannot replace a real execution fact.
        self.f.adapter.mode = "success"
        self.f.adapter.execute(waiting.requests[0])
        with self.assertRaisesRegex(CapabilityValidationError, "LOCAL_STOP_CONFLICTS_WITH_EXECUTION_FACT"):
            self.f.service().coordination.accept_action_result(expiry, received_at=c.expires_at,
                                                               receipt_verifier=self.f.adapter)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))

    def test_persisted_expiry_cannot_replay_when_nonexecution_becomes_unverifiable_or_conflicted(self):
        from unittest.mock import patch
        from continuity_engine.domain.capability import parse_capability_datetime
        from continuity_engine.domain.errors import CapabilityValidationError
        from continuity_engine.services.action_planning_service import ReceiptQuery
        c = self.f.choice("expiry-consume")
        service = self.f.service()
        service.clock = lambda: parse_capability_datetime(c.expires_at)
        original = service.run(c, self.f.context)
        before = self.f.ledger.capability_path.read_bytes()
        service = self.restart()
        for options in ({"return_value": ReceiptQuery.UNKNOWN}, {"side_effect": RuntimeError("unavailable")}):
            with self.subTest(options=options), patch.object(self.f.adapter, "query", **options):
                with self.assertRaises(CapabilityValidationError):
                    service.run(c, self.f.context, retry=True)
        # Simulate a contradictory late Adapter report in its independent fact file.
        self.f.adapter.execute(original.requests[0])
        service = self.restart()
        with self.assertRaisesRegex(CapabilityValidationError, "LOCAL_STOP_CONFLICTS_WITH_EXECUTION_FACT"):
            service.run(c, self.f.context)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
        self.assertEqual(self.f.adapter.receipts()[0].status, "SUCCEEDED")
        self.assertEqual((self.f.adapter.effect_count, self.f.adapter.credits), (1, 1))

    def test_bypassed_domain_terminal_is_rechecked_at_coordinator_and_storage_append(self):
        from continuity_engine.domain.action_capability import InternalActionResult
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("tampered-object")
        self.f.adapter.mode = "unknown"
        waiting = self.f.service().run(c, self.f.context)
        before = self.f.ledger.capability_path.read_bytes()
        for status in (CapabilityStatus.FAILED_TERMINAL, CapabilityStatus.CANCELLED, CapabilityStatus.EXPIRED):
            forged = InternalActionResult(waiting.requests[0], CapabilityStatus.UNKNOWN,
                                          "EXECUTION_UNCONFIRMED", waiting.results[0].completed_at)
            object.__setattr__(forged, "status", status)
            object.__setattr__(forged, "reason", "VERIFIED_RECEIPT")
            with self.subTest(status=status):
                with self.assertRaises(CapabilityValidationError):
                    self.f.service().coordination.accept_action_result(forged, received_at=forged.completed_at,
                                                                       receipt_verifier=self.f.adapter)
                with self.assertRaises(CapabilityValidationError):
                    self.f.ledger.save_capability_result(forged, received_at=forged.completed_at)
                self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)

    def test_expired_dependency_with_real_lookup_success_is_rejected_before_contact(self):
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.errors import CapabilityValidationError
        c = self.f.choice("expired-dependency", ("test.lookup", "contact.send"))
        self.f.adapter.mode = "lost_response"
        waiting = self.f.service().run(c, self.f.context)
        self.assertIsNone(waiting.results[1])
        self.assertEqual(len(self.f.adapter.receipts()), 1)
        data = json.loads(self.f.ledger.capability_path.read_text(encoding="utf-8"))
        attempt = data["attempts"][-1]
        attempt["result"].update(status="EXPIRED", reason="CHOICE_EXPIRED", receipt=None,
                                 completedAt=c.expires_at, gateReasons=["CHOICE_EXPIRED"])
        attempt["receivedAt"] = c.expires_at
        attempt["resultHash"] = digest(attempt["result"])
        self.f.ledger.capability_path.write_text(json.dumps(data), encoding="utf-8")
        before = self.f.ledger.capability_path.read_bytes()
        service = self.restart()
        with self.assertRaisesRegex(CapabilityValidationError, "LOCAL_STOP_CONFLICTS_WITH_EXECUTION_FACT"):
            service.run(c, self.f.context, retry=True)
        self.assertEqual(self.f.adapter.execute_calls, 0)
        self.assertEqual(self.f.adapter.effect_count, 0)
        self.assertEqual(len(self.f.adapter.receipts()), 1)
        self.assertEqual(self.f.ledger.capability_path.read_bytes(), before)
