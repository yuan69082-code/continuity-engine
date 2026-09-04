from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.capability import CapabilityStatus, IntegrationThinkingMode, CapabilityRequiredEnvelope
from continuity_engine.domain.errors import IntegrationExecutionError, CapabilityValidationError
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.services.action_planning_service import ReceiptQuery
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import tree_inventory_hash
from tests.test_e5_capability_flow import capability_result_payload


class P09RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.f = P09Fixture(Path(temp.name))

    def interrupt_at(self, stage):
        def fault(point, operation):
            if point == stage:
                raise RuntimeError("injected C1 checkpoint interruption")
        self.f.app.adapter._service._fault_injector = fault

    def test_lost_action_response_recovers_after_expiry_and_permission_loss(self):
        f = self.f
        request = f.request()
        f.adapter.mode = "lost_response"
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.adapter.effect_count, 1)
        f.runtime.clock.advance(timedelta(days=1))
        f.permission.allowed = False
        f.constraints.context_allowed = False
        f.reopen()
        result = f.submit(request)
        self.assertIsInstance(result, FirstRoundSuccessResult)
        self.assertEqual((f.adapter.effect_count, f.adapter.credits, f.adapter.execute_calls), (1, 1, 0))
        self.assertEqual(f.provider.calls, 0)

    def test_unknown_needs_explicit_retry_and_independent_nonexecution(self):
        f = self.f
        request = f.request()
        f.adapter.mode = "unknown"
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.adapter.execute_calls, 0)
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.adapter.execute_calls, 0)
        f.app.adapter._service.retry_c1_actions(request["requestId"], request["requestHash"])
        self.assertIsInstance(f.submit(request), FirstRoundSuccessResult)
        self.assertEqual((f.adapter.execute_calls, f.adapter.effect_count, f.adapter.credits), (1, 1, 1))

    def test_unknown_query_exception_and_string_cannot_authorize_execution(self):
        f = self.f
        request = f.request()
        for response in (ReceiptQuery.UNKNOWN, "NOT_EXECUTED", RuntimeError("query unavailable")):
            with self.subTest(response=str(response)):
                options = {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
                with patch.object(f.adapter, "query", **options):
                    with self.assertRaises(IntegrationExecutionError):
                        f.submit(request)
                self.assertEqual(f.adapter.execute_calls, 0)
                self.assertIs(f.core.last_action.results[0].status, CapabilityStatus.UNKNOWN)

    def test_expired_context_never_retries_unexecuted_request(self):
        f = self.f
        request = f.request()
        f.adapter.mode = "unknown"
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.reopen()
        with self.assertRaises(CapabilityValidationError):
            f.app.adapter._service.retry_c1_actions(request["requestId"], request["requestHash"])
        self.assertEqual(f.adapter.execute_calls, 0)

    def test_success_and_failure_replay_require_independent_receipts(self):
        f = self.f
        for status in ("success", "terminal"):
            with self.subTest(status=status):
                request = f.request()
                f.adapter.mode = status
                if status == "success":
                    f.submit(request)
                else:
                    with self.assertRaises(IntegrationExecutionError):
                        f.submit(request)
                before = tree_inventory_hash(f.runtime.data_root)
                with patch.object(f.adapter, "query", return_value=ReceiptQuery.NOT_EXECUTED):
                    with self.assertRaises(IntegrationExecutionError):
                        f.submit(request)
                self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_conflicting_adapter_receipt_blocks_completed_result_replay(self):
        f = self.f
        request = f.request()
        f.submit(request)
        receipt = replace(f.adapter.receipts()[0], output_hash="sha256:" + "f" * 64)
        with patch.object(f.adapter, "query", return_value=receipt):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        self.assertEqual(f.adapter.execute_calls, 1)

    def test_step_invalidation_retains_first_fact_and_blocks_next_step(self):
        f = self.f
        f.mode = "complex"
        f.reopen()
        def invalidate(point):
            if point == "after_adapter_before_result":
                f.constraints.context_allowed = False
        f.core.fault = invalidate
        request = f.request()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(len(f.adapter.receipts()), 1)
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.adapter.execute_calls, 0)
        self.assertEqual(len(f.adapter.receipts()), 1)
        self.assertEqual(f.adapter.effect_count, 0)  # Lookup only; contact never executes.

    def test_crashes_at_thinking_action_and_completion_checkpoints_do_not_duplicate(self):
        f = self.f
        for point in ("after_thinking_completed", "after_action_completed", "after_c1_action_completed",
                      "after_completed_result_saved"):
            with self.subTest(point=point):
                request = f.request()
                before = f.adapter.effect_count
                self.interrupt_at(point)
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)
                f.reopen()
                first = f.submit(request)
                self.assertIsInstance(first, FirstRoundSuccessResult)
                self.assertEqual(f.provider.calls, 0)
                self.assertEqual(f.adapter.effect_count, before + 1)
                self.assertEqual(f.submit(request).to_dict(), first.to_dict())

    def test_model_and_action_share_ledger_across_waiting_restart_and_result_loss(self):
        f = self.f
        f.thinking_mode = IntegrationThinkingMode.CAPABILITY
        f.reopen()
        request = f.request()
        waiting = f.submit(request)
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), waiting.to_dict())
        f.adapter.mode = "lost_response"
        payload = capability_result_payload(waiting, response="Synthetic C1 model expression.")
        # The model contract reports completion two seconds after proposal.
        f.runtime.clock.advance(timedelta(seconds=3))
        with self.assertRaisesRegex(CapabilityValidationError, "C1_ACTION_WAITING_CAPABILITY"):
            f.app.adapter.submit_capability_result(payload)
        f.reopen()
        first = f.app.adapter.submit_capability_result(payload)
        self.assertIsInstance(first, FirstRoundSuccessResult)
        before_replay = tree_inventory_hash(f.runtime.data_root)
        self.assertEqual(f.app.adapter.submit_capability_result(payload).to_dict(), first.to_dict())
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before_replay)
        self.assertEqual(f.adapter.execute_calls, 0)
        self.assertEqual(f.adapter.credits, 1)
        self.assertEqual(f.runtime.subject_state().revision, 1)
        import json
        ledger = json.loads(f.app.ledger.capability_path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["requests"]), 2)
        self.assertEqual(sum(r.get("capabilityType") == "model.generate" for r in ledger["requests"]), 1)
        self.assertEqual(f.core.last_action.requests[0].capability_type, "expression.emit")

    def test_local_expiry_requires_nonexecution_and_cannot_hide_receipt_conflict(self):
        f = self.f
        f.core.context_ttl = timedelta(days=1)
        request = f.request()
        self.interrupt_at("after_action_completed")
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        f.app.adapter._service._fault_injector = None
        f.runtime.clock.advance(timedelta(minutes=11))
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertIs(f.core.last_action.results[0].status, CapabilityStatus.EXPIRED)
        self.assertEqual(f.adapter.execute_calls, 0)
        with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        expired_request = f.core.last_action.requests[0]
        # An independently observed later fact must conflict with local EXPIRED;
        # it cannot be silently treated as proof that execution never occurred.
        f.adapter.execute(expired_request)
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.adapter.effect_count, 1)


if __name__ == "__main__":
    unittest.main()
