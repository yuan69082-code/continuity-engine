"""P09 second repair: independent Evolution checkpoint regressions in TEST roots."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from continuity_engine.domain.events import StateMutation, ChangeOperation, EventSourceKind, EventClassification
from continuity_engine.domain.errors import IntegrationExecutionError, CapabilityValidationError
from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.interfaces.local_integration_app import LocalIntegrationInitializationError
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import read_json, atomic_write_json, tree_inventory_hash


class P09RepairIndependentTests(unittest.TestCase):
    def fixture(self, *, state_update=True, gates=None):
        temp = tempfile.TemporaryDirectory(prefix="p9r-")
        self.addCleanup(temp.cleanup)
        f = P09Fixture(Path(temp.name))
        if gates is not None:
            f.gates = gates
            f.reopen()
        original = f.provider.think
        def think(perception, budget):
            return replace(original(perception, budget), update_subject_state=True,
                proposed_mutations=[StateMutation("continuity.current_focus", ChangeOperation.SET,
                    ["independent-repair-review"], "Synthetic legal state proposal.")])
        if state_update:
            f.provider.think = think
        return f

    def remove_checkpoint(self, f, request):
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["evolution"] = None
        atomic_write_json(f.app.ledger.operation_path, document)

    def invoke(self, f, request, route):
        service = f.app.adapter._service
        if route == "submit":
            return f.submit(request)
        if route == "query":
            return service.query_request(request["requestId"])
        if route == "retry":
            return service.retry_c1_actions(request["requestId"], request["requestHash"])
        # Test the completed-result callback's common guard with an isolated
        # coordination Port stub; genuine model/ledger compatibility has its own suite.
        accepted = SimpleNamespace(request_id=request["requestId"])
        coordination = SimpleNamespace(
            validator=SimpleNamespace(validate_result=lambda payload: accepted),
            accept_result=lambda *a, **kw: SimpleNamespace(result=accepted))
        with patch.object(service, "_thinking_mode", IntegrationThinkingMode.CAPABILITY), \
                patch.object(service, "_capabilities", coordination):
            return service.submit_capability_result({})

    def test_missing_evolution_checkpoint_cannot_skip_original_fact_validation(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        f.reopen()
        service = f.app.adapter._service
        operation = f.app.ledger.load_operation(request["requestId"])
        update = service._action_evolution.find_update_by_event_id(operation.subject_id, operation.evolution.event_id)
        wrong = replace(update, event=replace(update.event, reason="mismatched original authorization"))
        # The unmodified checkpoint correctly rejects a conflicting original fact.
        with patch.object(service._action_evolution, "find_update_by_event_id", return_value=wrong):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["evolution"] = None
        atomic_write_json(f.app.ledger.operation_path, document)
        state_before = tree_inventory_hash(f.runtime.data_root / "subject-state")
        blocked = False
        try:
            f.reopen()
            with patch.object(f.app.adapter._service._action_evolution,
                              "find_update_by_event_id", return_value=wrong) as query:
                result = f.submit(request)
                print("NULL_EVOLUTION_PROBE", type(result).__name__, "fact_queries", query.call_count,
                      "same_result", result.to_dict() == first.to_dict(), flush=True)
        except (IntegrationExecutionError, LocalIntegrationInitializationError):
            blocked = True
        self.assertEqual(tree_inventory_hash(f.runtime.data_root / "subject-state"), state_before)
        self.assertTrue(blocked, "null Evolution checkpoint bypassed conflicting original fact validation")

    def test_missing_evolution_checkpoint_cannot_skip_missing_original_fact_on_query(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        f.reopen()
        # Query path control with the original checkpoint: missing fact is rejected.
        service = f.app.adapter._service
        with patch.object(service._action_evolution, "find_update_by_event_id", return_value=None):
            with self.assertRaises(Exception) as caught:
                service.query_request(request["requestId"])
            self.assertIn("C1_COMMITTED_EVOLUTION_MISSING", str(caught.exception))
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["evolution"] = None
        atomic_write_json(f.app.ledger.operation_path, document)
        blocked = False
        try:
            f.reopen()
            with patch.object(f.app.adapter._service._action_evolution,
                              "find_update_by_event_id", return_value=None) as query:
                result = f.app.adapter._service.query_request(request["requestId"])
                print("NULL_EVOLUTION_QUERY_PROBE", result.status, "fact_queries", query.call_count, flush=True)
        except (IntegrationExecutionError, LocalIntegrationInitializationError):
            blocked = True
        except Exception as error:
            if "C1_COMMITTED_EVOLUTION_MISSING" in str(error):
                blocked = True
            else:
                raise
        self.assertTrue(blocked, "query reported completed state while skipping missing original fact")

    def test_verified_fact_replays_read_only_without_checkpoint_after_expiry(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        self.remove_checkpoint(f, request)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.permission.references_allowed = False
        f.reopen()
        before = tree_inventory_hash(f.runtime.data_root)
        port = f.app.adapter._service._action_evolution
        original = port.find_update_by_event_id
        with patch.object(port, "find_update_by_event_id", wraps=original) as facts:
            self.assertEqual(self.invoke(f, request, "submit").to_dict(), first.to_dict())
            self.assertEqual(self.invoke(f, request, "query").result.to_dict(), first.to_dict())
            self.assertEqual(self.invoke(f, request, "callback").to_dict(), first.to_dict())
            self.assertIsNone(self.invoke(f, request, "retry"))
            self.assertEqual(facts.call_count, 4)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        self.assertEqual(f.runtime.subject_state().revision, 2)
        self.assertEqual(f.provider.calls, 0)

    def test_missing_checkpoint_cross_checks_every_original_fact_binding_on_all_routes(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        operation = f.app.ledger.load_operation(request["requestId"])
        update = f.app.adapter._service._action_evolution.find_update_by_event_id(
            operation.subject_id, operation.evolution.event_id)
        self.remove_checkpoint(f, request)
        f.reopen()
        changed_event = lambda **kw: replace(update, event=replace(update.event, **kw))
        wrong = {
            "missing": None,
            "subject": replace(update, subject_id="different-subject"),
            "before_revision": replace(update, before_revision=0),
            "after_revision": replace(update, after_revision=3),
            "update_id": replace(update, update_id="different-update"),
            "event_id": changed_event(event_id="different-event"),
            "mutations": changed_event(mutations=[StateMutation("continuity.current_focus", ChangeOperation.SET,
                ["different"], "Different original mutation.")]),
            "event_reason": changed_event(reason="different event reason"),
            "record_reason": replace(update, reason="different record reason"),
            "content": changed_event(content="different original content"),
            "source": changed_event(source="different-authority"),
            "source_kind": changed_event(source_kind=EventSourceKind.EXTERNAL),
            "event_type": changed_event(event_type="different-type"),
            "classification": changed_event(classification=EventClassification.OBSERVATION),
        }
        for key in ("integration_request_id", "integration_operation_id", "action_session_id",
                    "action_decision_id", "action_plan_id", "think_id", "wake_session_id",
                    "perception_id", "thinking_result_id"):
            wrong[key] = changed_event(metadata={**update.event.metadata, key: "different-binding"})
        before = tree_inventory_hash(f.runtime.data_root)
        for route in ("submit", "query", "retry", "callback"):
            for field, value in wrong.items():
                with self.subTest(route=route, field=field):
                    with patch.object(f.app.adapter._service._action_evolution,
                                      "find_update_by_event_id", return_value=value) as facts:
                        with self.assertRaises((IntegrationExecutionError, CapabilityValidationError, RuntimeError)):
                            self.invoke(f, request, route)
                        self.assertGreater(facts.call_count, 0)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_completed_result_and_thinking_evidence_cannot_disagree_with_fact(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        self.remove_checkpoint(f, request)
        f.reopen()
        service = f.app.adapter._service
        operation = f.app.ledger.load_operation(request["requestId"])
        session = service._thinking.get_session(operation.subject_id, operation.domain.think_session_id)
        wrong_result = replace(first, state_projection=replace(first.state_projection,
                               engine_update_id="different-update"))
        before = tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.app.ledger, "load_completed", return_value=wrong_result):
            with self.assertRaises(CapabilityValidationError):
                self.invoke(f, request, "query")
        for fields in ({"state_update_id": "different-update"}, {"state_event_id": "different-event"},
                       {"state_written_back": False, "state_event_id": None, "state_update_id": None}):
            with self.subTest(fields=fields):
                with patch.object(service._thinking, "get_session", return_value=replace(session, **fields)):
                    with self.assertRaises(IntegrationExecutionError):
                        self.invoke(f, request, "submit")
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_committed_fact_before_checkpoint_or_result_survives_expired_context(self):
        for point in ("after_evolution_committed", "after_evolution_checkpoint_saved", "after_completed_result_saved"):
            with self.subTest(point=point):
                f = self.fixture()
                request = f.request()
                def crash(stage, operation):
                    if stage == point:
                        raise RuntimeError("controlled committed-state recovery stop")
                f.app.adapter._service._fault_injector = crash
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)
                before = tree_inventory_hash(f.runtime.data_root / "subject-state")
                f.runtime.clock.advance(timedelta(minutes=11))
                f.permission.references_allowed = False
                f.reopen()
                result = f.submit(request)
                self.assertTrue(result.state_projection.changed)
                self.assertEqual(result.state_projection.current_revision, 2)
                self.assertEqual(f.submit(request).to_dict(), result.to_dict())
                self.assertEqual(tree_inventory_hash(f.runtime.data_root / "subject-state"), before)
                self.assertEqual(f.provider.calls, 0)

    def test_no_state_update_and_genuine_legacy_completion_keep_original_behavior(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                f = self.fixture(state_update=legacy, gates=ContinuityCoreGates(enabled=False) if legacy else None)
                request = f.request()
                first = f.submit(request)
                f.reopen()
                before = tree_inventory_hash(f.runtime.data_root)
                with patch.object(f.app.adapter._service._action_evolution, "find_update_by_event_id",
                                  side_effect=AssertionError("non-C1-state replay queried Evolution")):
                    self.assertEqual(f.submit(request).to_dict(), first.to_dict())
                    self.assertEqual(self.invoke(f, request, "query").result.to_dict(), first.to_dict())
                self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_pre_binding_c1_records_still_require_original_state_fact(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        document = read_json(f.app.ledger.operation_path)
        item = next(x for x in document["operations"] if x["requestId"] == request["requestId"])
        item["evolution"] = None
        progress = item["domainProgress"]
        progress.pop("continuityContextHash")
        progress["action"]["context"]["perception_summary"].pop("continuity_context_hash")
        from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
        path = JsonThinkingRepository(f.runtime.data_root)._path(item["subjectId"], progress["thinkSessionId"])
        session = read_json(path)
        session["observation"].pop("continuity_context_hash")
        atomic_write_json(path, session)
        atomic_write_json(f.app.ledger.operation_path, document)
        f.reopen()
        with patch.object(f.app.adapter._service._action_evolution, "find_update_by_event_id", return_value=None) as facts:
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
            self.assertEqual(facts.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
