"""Independent review of P09 first repair; all faults use disposable TEST roots."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.interfaces.local_integration_app import LocalIntegrationInitializationError
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import read_json, atomic_write_json, tree_inventory_hash


class P09RepairIndependentTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="p9r-")
        self.addCleanup(temp.cleanup)
        f = P09Fixture(Path(temp.name))
        original = f.provider.think
        def think(perception, budget):
            return replace(original(perception, budget), update_subject_state=True,
                proposed_mutations=[StateMutation("continuity.current_focus", ChangeOperation.SET,
                    ["independent-repair-review"], "Synthetic legal state proposal.")])
        f.provider.think = think
        return f

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
