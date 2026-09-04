"""P09 review regressions: four counterexamples and two legal Evolution controls.

Derived from the 2026-09-04 independent probe; all fault injection stays in P01 TEST roots.
"""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.domain.errors import (IntegrationExecutionError, IntegrationPersistenceError,
    MachineContractValidationError, ThinkingValidationError, CapabilityValidationError)
from continuity_engine.interfaces.local_integration_app import LocalIntegrationInitializationError
from continuity_engine.domain.integration_results import IntegrationOperationRecord
from continuity_engine.domain.action import ResourceLimits, PermissionCheck
from continuity_engine.domain.continuity_core import ContinuityCoreContext
from continuity_engine.domain.thinking import ThinkSession
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import read_json, atomic_write_json
from continuity_engine.domain.action_capability import ReceiptQuery


class P09ReviewRegressionTests(unittest.TestCase):
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

    def assert_replay_blocked(self, f, request, first, label):
        receipt_before = f.adapter.path.read_bytes()
        blocked = False
        try:
            f.reopen()
            with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN) as query:
                restored = f.submit(request)
                print(label, type(restored).__name__, "query_calls", query.call_count,
                      "same_result", restored.to_dict() == first.to_dict(), flush=True)
        except (IntegrationExecutionError, LocalIntegrationInitializationError) as error:
            blocked = True
            print(label, "REJECTED", type(error).__name__, flush=True)
        self.assertTrue(blocked, "C1 checkpoint downgrade bypassed historical receipt verification")
        self.assertEqual(f.adapter.path.read_bytes(), receipt_before)

    def stop_state_before(self, point):
        f = self.fixture()
        self.state_writer(f)
        request = f.request()
        def crash(stage, operation):
            if stage == point:
                raise RuntimeError("P09 review controlled checkpoint stop")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        return f, request

    def raw_operation(self, f, request):
        doc = read_json(f.app.ledger.operation_path)
        return doc, next(x for x in doc["operations"] if x["requestId"] == request["requestId"])

    def raw_session(self, f, item):
        path = JsonThinkingRepository(f.runtime.data_root)._path(item["subjectId"], item["domainProgress"]["thinkSessionId"])
        return path, read_json(path)

    def state_inventory(self, f):
        return tree_inventory_hash(f.runtime.data_root / "subject-state")

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
        try:
            result = f.submit(request)
        except IntegrationExecutionError as error:
            result = error
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
        try:
            result = f.submit(request)
        except IntegrationExecutionError as error:
            result = error
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
        self.assert_replay_blocked(f, request, first, "GATE_FLIP_PROBE")

    def test_checkpoint_context_removal_cannot_downgrade_c1_to_legacy_replay(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["domainProgress"]["perception"].pop("continuity_context")
        atomic_write_json(f.app.ledger.operation_path, document)
        self.assert_replay_blocked(f, request, first, "CONTEXT_REMOVAL_PROBE")

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

    def test_first_commit_rechecks_action_and_domain_recovery_checkpoints(self):
        for point in ("after_action_completed", "after_domain_completed"):
            for invalidation in ("expired", "revoked"):
                with self.subTest(point=point, invalidation=invalidation):
                    f, request = self.stop_state_before(point)
                    self.assertEqual(f.runtime.subject_state().revision, 1)
                    before = self.state_inventory(f)
                    if invalidation == "expired":
                        f.runtime.clock.advance(timedelta(minutes=11))
                    else:
                        f.permission.references_allowed = False
                    f.reopen()
                    with self.assertRaises(IntegrationExecutionError):
                        f.submit(request)
                    self.assertEqual(self.state_inventory(f), before)
                    self.assertEqual(f.provider.calls, 0)

    def test_first_commit_uses_current_action_permission_time_and_resources(self):
        for kind in ("permission_set", "permission_time", "resources"):
            with self.subTest(kind=kind):
                f, request = self.stop_state_before("after_domain_completed")
                old_time = f.runtime.clock.now()
                f.runtime.clock.advance(timedelta(seconds=1))
                f.reopen()
                service = f.app.adapter._service
                before = self.state_inventory(f)
                if kind == "permission_set":
                    service._available_permissions = ()
                elif kind == "resources":
                    service._resource_limits = ResourceLimits(maximum_estimated_cost=0)
                else:
                    original = service._action._permissions.check
                    def check(permission, **kwargs):
                        if kwargs["at"] > old_time:
                            return PermissionCheck.missing(permission, "Current permission revoked")
                        return original(permission, **kwargs)
                    service._action._permissions.check = check
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)
                self.assertEqual(self.state_inventory(f), before)

    def test_committed_evolution_checkpoint_recovers_without_reauthorization_or_writes(self):
        f, request = self.stop_state_before("after_evolution_checkpoint_saved")
        self.assertEqual(f.runtime.subject_state().revision, 2)
        before = self.state_inventory(f)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.permission.references_allowed = False
        f.reopen()
        f.app.adapter._service._available_permissions = ()
        first = f.submit(request)
        self.assertIsInstance(first, FirstRoundSuccessResult)
        self.assertEqual(self.state_inventory(f), before)
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
        self.assertEqual(self.state_inventory(f), before)
        self.assertEqual(f.provider.calls, 0)

    def test_completed_state_replay_rejects_conflicting_evolution_binding(self):
        f = self.fixture()
        self.state_writer(f)
        request = f.request()
        f.submit(request)
        f.reopen()
        service = f.app.adapter._service
        operation = f.app.ledger.load_operation(request["requestId"])
        update = service._action_evolution.find_update_by_event_id(operation.subject_id, operation.evolution.event_id)
        wrong = replace(update, event=replace(update.event, reason="different original authorization"))
        before = self.state_inventory(f)
        with patch.object(service._action_evolution, "find_update_by_event_id", return_value=wrong):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        self.assertEqual(self.state_inventory(f), before)

    def test_journal_binding_checks_deserialization_loading_submit_and_query(self):
        for change in ("remove", "flip"):
            with self.subTest(change=change):
                f = self.fixture()
                request = f.request()
                f.submit(request)
                document, item = self.raw_operation(f, request)
                if change == "remove":
                    item["domainProgress"]["perception"].pop("continuity_context")
                else:
                    item["domainProgress"]["perception"]["continuity_context"]["actions_enabled"] = False
                with self.assertRaises(MachineContractValidationError):
                    IntegrationOperationRecord.from_dict(item)
                atomic_write_json(f.app.ledger.operation_path, document)
                before = tree_inventory_hash(f.runtime.data_root)
                with self.assertRaises(IntegrationPersistenceError):
                    f.app.ledger.load_operation(request["requestId"])
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)
                with self.assertRaises(IntegrationPersistenceError):
                    f.app.adapter._service.query_request(request["requestId"])
                self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_rehashed_journal_cannot_override_original_thinking_input(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        document, item = self.raw_operation(f, request)
        progress = item["domainProgress"]
        context = progress["perception"]["continuity_context"]
        context["actions_enabled"] = False
        altered = ContinuityCoreContext.from_dict(context).binding_hash()
        progress["continuityContextHash"] = altered
        progress["action"]["context"]["perception_summary"]["continuity_context_hash"] = altered
        atomic_write_json(f.app.ledger.operation_path, document)
        self.assert_replay_blocked(f, request, first, "REHASHED_JOURNAL")

    def test_thinking_binding_rejects_removed_context_or_snapshot(self):
        for change in ("context", "snapshot"):
            with self.subTest(change=change):
                f = self.fixture()
                request = f.request()
                f.submit(request)
                _, item = self.raw_operation(f, request)
                path, session = self.raw_session(f, item)
                if change == "context":
                    session["perception_snapshot"].pop("continuity_context")
                else:
                    session.pop("perception_snapshot")
                with self.assertRaises(ThinkingValidationError):
                    ThinkSession.from_dict(session)
                atomic_write_json(path, session)
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)

    def test_consistently_disabled_inputs_cannot_hide_existing_e5_action(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        document, item = self.raw_operation(f, request)
        path, session = self.raw_session(f, item)
        progress = item["domainProgress"]
        progress["perception"]["continuity_context"]["actions_enabled"] = False
        context = progress["perception"]["continuity_context"]
        altered = ContinuityCoreContext.from_dict(context).binding_hash()
        progress["continuityContextHash"] = altered
        progress["action"]["context"]["perception_summary"]["continuity_context_hash"] = altered
        session["perception_snapshot"]["continuity_context"]["actions_enabled"] = False
        session["observation"]["continuity_context_hash"] = altered
        atomic_write_json(f.app.ledger.operation_path, document)
        atomic_write_json(path, session)
        self.assert_replay_blocked(f, request, first, "DISABLED_INPUTS_WITH_E5_HISTORY")

    def test_pre_binding_c1_and_real_legacy_disabled_records_remain_compatible(self):
        for gates in (ContinuityCoreGates(), ContinuityCoreGates(actions=False), ContinuityCoreGates(enabled=False)):
            with self.subTest(gates=gates):
                f = self.fixture()
                f.gates = gates
                f.reopen()
                request = f.request()
                first = f.submit(request)
                document, item = self.raw_operation(f, request)
                path, session = self.raw_session(f, item)
                progress = item["domainProgress"]
                progress.pop("continuityContextHash", None)
                progress["action"]["context"]["perception_summary"].pop("continuity_context_hash", None)
                session["observation"].pop("continuity_context_hash", None)
                atomic_write_json(f.app.ledger.operation_path, document)
                atomic_write_json(path, session)
                before = tree_inventory_hash(f.runtime.data_root)
                f.reopen()
                self.assertEqual(f.submit(request).to_dict(), first.to_dict())
                self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
                self.assertEqual(f.adapter.execute_calls, 0)
                if gates.enabled and gates.actions:
                    with patch.object(f.adapter, "query", return_value=ReceiptQuery.UNKNOWN):
                        with self.assertRaises(IntegrationExecutionError):
                            f.submit(request)
                else:
                    with patch.object(f.adapter, "query", side_effect=AssertionError("disabled adapter accessed")):
                        self.assertEqual(f.submit(request).to_dict(), first.to_dict())

    def test_missing_context_before_thinking_cannot_downgrade_to_legacy(self):
        f, request = self.stop_state_before("after_perception_checkpoint_saved")
        document, item = self.raw_operation(f, request)
        item["domainProgress"]["perception"].pop("continuity_context")
        atomic_write_json(f.app.ledger.operation_path, document)
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.runtime.subject_state().revision, 1)
        self.assertEqual(f.provider.calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
