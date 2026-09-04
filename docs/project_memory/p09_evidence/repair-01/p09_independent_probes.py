"""Read-only Engine review; all mutations below are inside disposable TEST roots."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import read_json, atomic_write_json
from continuity_engine.domain.action_capability import ReceiptQuery


class IndependentP09Review(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="p09-review-")
        self.addCleanup(temp.cleanup)
        return P09Fixture(Path(temp.name))

    def state_writer(self, f):
        original = f.provider.think
        def think(perception, budget):
            return replace(original(perception, budget), update_subject_state=True,
                proposed_mutations=[StateMutation("continuity.current_focus", ChangeOperation.SET,
                    ["independent-review-state-write"], "Synthetic legal proposal for boundary test.")])
        f.provider.think = think

    def test_current_context_allows_legal_state_update_control(self):
        f = self.fixture()
        self.state_writer(f)
        self.assertIsInstance(f.submit(), FirstRoundSuccessResult)
        self.assertEqual(f.runtime.subject_state().revision, 2)

    def test_expired_context_must_block_first_state_commit_after_thinking_crash(self):
        f = self.fixture()
        self.state_writer(f)
        request = f.request()
        def crash(point, operation):
            if point == "after_thinking_completed":
                raise RuntimeError("review stop before Action/Evolution")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.runtime.subject_state().revision, 1)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.reopen()
        self.assertFalse(f.core.current(f.context(request)))
        result = f.submit(request)
        print("EXPIRED_CONTEXT_PROBE", type(result).__name__, "revision", f.runtime.subject_state().revision,
              "thinking_calls", f.provider.calls, flush=True)
        self.assertEqual(f.runtime.subject_state().revision, 1,
                         "expired Context authorized a new StateMutation/Evolution commit")

    def test_revoked_reference_must_block_first_state_commit_after_thinking_crash(self):
        f = self.fixture()
        self.state_writer(f)
        request = f.request()
        def crash(point, operation):
            if point == "after_thinking_completed":
                raise RuntimeError("review stop before Action/Evolution")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.runtime.subject_state().revision, 1)
        f.permission.references_allowed = False
        f.reopen()
        self.assertFalse(f.core.current(f.context(request)))
        result = f.submit(request)
        print("REVOKED_REFERENCE_PROBE", type(result).__name__, "revision", f.runtime.subject_state().revision,
              "thinking_calls", f.provider.calls, flush=True)
        self.assertEqual(f.runtime.subject_state().revision, 1,
                         "revoked Context authorized a new StateMutation/Evolution commit")

    def test_checkpoint_gate_flip_cannot_bypass_completed_receipt_verification(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        # Positive rejection control: the unchanged C1 checkpoint rejects UNKNOWN.
        with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["domainProgress"]["perception"]["continuity_context"]["actions_enabled"] = False
        # Fault injection in this disposable root only; original ThinkSession,
        # ActionContext, result ledger, action ledger and receipt remain untouched.
        atomic_write_json(f.app.ledger.operation_path, document)
        f.reopen()
        with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN) as query:
            blocked = False
            try:
                restored = f.submit(request)
                print("GATE_FLIP_PROBE", type(restored).__name__, "query_calls", query.call_count,
                      "same_result", restored.to_dict() == first.to_dict(), flush=True)
            except IntegrationExecutionError:
                blocked = True
            self.assertTrue(blocked, "checkpoint gate flip bypassed historical receipt verification")

    def test_checkpoint_context_removal_cannot_downgrade_c1_to_legacy_replay(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["domainProgress"]["perception"].pop("continuity_context")
        atomic_write_json(f.app.ledger.operation_path, document)
        f.reopen()
        with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN) as query:
            blocked = False
            try:
                restored = f.submit(request)
                print("CONTEXT_REMOVAL_PROBE", type(restored).__name__, "query_calls", query.call_count,
                      "same_result", restored.to_dict() == first.to_dict(), flush=True)
            except IntegrationExecutionError:
                blocked = True
            self.assertTrue(blocked, "missing Context downgraded C1 history to legacy replay")

    def test_already_committed_state_recovers_after_expiry_control(self):
        f = self.fixture()
        self.state_writer(f)
        request = f.request()
        def crash(point, operation):
            if point == "after_evolution_committed":
                raise RuntimeError("review stop after actual Evolution commit")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.runtime.subject_state().revision, 2)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.permission.references_allowed = False
        f.reopen()
        self.assertIsInstance(f.submit(request), FirstRoundSuccessResult)
        self.assertEqual(f.runtime.subject_state().revision, 2)
        self.assertEqual(f.provider.calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
