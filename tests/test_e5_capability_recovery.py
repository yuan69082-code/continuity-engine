from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from continuity_engine.domain.capability import (
    CapabilityRequiredEnvelope,
    IntegrationThinkingMode,
)
from continuity_engine.domain.errors import (
    CapabilityConflictError,
    IntegrationExecutionError,
    IntegrationPersistenceError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.domain.integration_results import IntegrationDomainProgressStage
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationInitializationError,
    build_local_integration_app,
    initialize_local_integration,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
)
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from tests.test_contract_test_adapter import first_round_request
from tests.test_e5_capability_flow import capability_result_payload


class FailOnceAt:
    def __init__(self, target: str) -> None:
        self.target = target
        self.triggered = False

    def __call__(self, stage, operation) -> None:
        del operation
        if stage == self.target and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"simulated crash at {stage}")


class E5CapabilityRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "formal-data"
        fixture = SubjectBindingFixture.first_round()
        binding_file = self.root / "binding.json"
        binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        initialize_local_integration(
            data_dir=self.data,
            binding_file=binding_file,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
            cycle_id="formal-cycle-001",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def app(self):
        return build_local_integration_app(
            self.data,
            thinking_mode=IntegrationThinkingMode.CAPABILITY,
        )

    def counts(self) -> tuple[int, int, int, int]:
        app = self.app()
        wakes = len(JsonAwakeningRepository(self.data).list_sessions("subject-001"))
        thinks = len(JsonThinkingRepository(self.data).list_think_sessions("subject-001"))
        updates = len(app.subject_states.get_update_history("subject-001"))
        operations = len(app.ledger.list_operations())
        return wakes, thinks, updates, operations

    def recover_request_fault(self, point: str) -> CapabilityRequiredEnvelope:
        request = first_round_request()
        first = self.app()
        fault = FailOnceAt(point)
        first.adapter.service._fault_injector = fault  # noqa: SLF001
        with self.assertRaises(IntegrationExecutionError):
            first.adapter.submit(copy.deepcopy(request))
        self.assertTrue(fault.triggered)
        operation = first.ledger.load_operation("request-001")
        assert operation is not None
        rebuilt = self.app()
        result = rebuilt.adapter.submit(copy.deepcopy(request))
        self.assertIsInstance(result, CapabilityRequiredEnvelope)
        assert isinstance(result, CapabilityRequiredEnvelope)
        self.assertEqual(result.request_id, request["requestId"])
        self.assertEqual(result.request_hash, request["requestHash"])
        self.assertEqual(result.operation_id, operation.operation_id)
        self.assertEqual(self.counts(), (1, 1, 0, 1))
        replay = self.app().adapter.submit(copy.deepcopy(request))
        self.assertEqual(result, replay)
        return result

    def recover_result_fault(self, point: str) -> FirstRoundSuccessResult:
        request = first_round_request()
        first = self.app()
        required = first.adapter.submit(copy.deepcopy(request))
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        fault = FailOnceAt(point)
        first.adapter.service._fault_injector = fault  # noqa: SLF001
        with self.assertRaises(IntegrationExecutionError):
            first.adapter.submit_capability_result(copy.deepcopy(payload))
        self.assertTrue(fault.triggered)
        operation = first.ledger.load_operation("request-001")
        assert operation is not None
        rebuilt = self.app()
        result = rebuilt.adapter.submit_capability_result(copy.deepcopy(payload))
        self.last_recovery_log = tuple(rebuilt.adapter.service.last_call_log)
        self.assertIsInstance(result, FirstRoundSuccessResult)
        assert isinstance(result, FirstRoundSuccessResult)
        self.assertEqual(result.request_id, request["requestId"])
        self.assertEqual(result.request_hash, request["requestHash"])
        self.assertEqual(result.operation_id, operation.operation_id)
        self.assertEqual(result.response.content, "Hello from the bounded capability result.")
        self.assertFalse(result.state_projection.changed)
        self.assertEqual(self.counts(), (1, 1, 0, 1))
        final = self.app().adapter.submit_capability_result(copy.deepcopy(payload))
        self.assertEqual(final, result)
        request_id = required.capability_request.capability_request_id
        self.assertEqual(len(self.app().ledger.list_capability_attempts(request_id)), 1)
        return result

    def test_operation_reserved_recovery(self) -> None:
        self.recover_request_fault("after_operation_reserved")

    def test_perception_checkpoint_recovery(self) -> None:
        self.recover_request_fault("after_perception_checkpoint_saved")

    def test_before_capability_request_creation_recovery(self) -> None:
        self.recover_request_fault("before_capability_request_created")

    def test_request_saved_before_waiting_checkpoint_recovery(self) -> None:
        self.recover_request_fault("after_capability_request_saved")

    def test_capability_waiting_checkpoint_recovery(self) -> None:
        self.recover_request_fault("after_capability_request_checkpoint_saved")

    def test_result_received_before_persistence_recovery(self) -> None:
        self.recover_result_fault("after_capability_result_received")

    def test_result_persisted_before_operation_checkpoint_recovery(self) -> None:
        self.recover_result_fault("after_capability_result_persisted")

    def test_result_checkpoint_recovery(self) -> None:
        self.recover_result_fault("after_capability_result_checkpoint_saved")

    def test_thinking_completed_before_operation_checkpoint_recovery(self) -> None:
        self.recover_result_fault("after_capability_thinking_completed")

    def test_thinking_checkpoint_recovery(self) -> None:
        self.recover_result_fault("after_capability_thinking_checkpoint_saved")

    def test_action_completed_before_domain_checkpoint_recovery(self) -> None:
        result = self.recover_result_fault("after_action_completed")
        operation = self.app().ledger.load_operation(result.request_id)
        assert operation is not None and operation.domain_progress is not None
        self.assertIs(
            operation.domain_progress.stage,
            IntegrationDomainProgressStage.ACTION_COMPLETED,
        )
        self.assertIsNotNone(operation.domain_progress.action)
        self.assertNotIn("action", self.last_recovery_log)
        self.assertIn("action_reused", self.last_recovery_log)

    def test_domain_checkpoint_recovery(self) -> None:
        self.recover_result_fault("after_domain_completed")

    def test_completed_result_before_operation_completion_recovery(self) -> None:
        self.recover_result_fault("after_completed_result_saved")

    def test_corrupt_capability_checkpoint_fails_closed(self) -> None:
        app = self.app()
        app.adapter.submit(first_round_request())
        document = json.loads(app.ledger.operation_path.read_text(encoding="utf-8"))
        document["operations"][0]["capability"]["capabilityRequestId"] = "wrong"
        app.ledger.operation_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises((LocalIntegrationInitializationError, IntegrationPersistenceError)):
            self.app()

    def test_conflicting_result_replay_fails_closed_after_rebuild(self) -> None:
        app = self.app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        completed = app.adapter.submit_capability_result(payload)
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        conflicting = capability_result_payload(required, response="conflicting replay")
        with self.assertRaises(CapabilityConflictError):
            self.app().adapter.submit_capability_result(conflicting)
        self.assertEqual(self.app().adapter.query_request("request-001").result, completed)


if __name__ == "__main__":
    unittest.main()
