from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.domain.model_provider import ProviderModelProfile
from continuity_engine.interfaces.local_integration_app import initialize_local_integration
from continuity_engine.interfaces.local_model_capability_app import (
    build_local_model_capability_app,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
)
from continuity_engine.services.model_profile_policy import (
    ConfiguredModelProfilePolicy,
)
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from continuity_engine.testing.fake_model_provider import ScriptedFakeModelProvider
from tests.test_p02_model_capability import ResolvingModelProvider, p02_request


class FailOnceAt:
    def __init__(self, target: str) -> None:
        self.target = target
        self.triggered = False

    def __call__(self, stage, record) -> None:
        del record
        if stage == self.target and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"simulated P02 crash at {stage}")


class P02ModelRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "engine-data"
        self.provider_root = self.root / "provider-fixture"
        fixture = SubjectBindingFixture.first_round()
        binding_file = self.root / "binding.json"
        binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        initialize_local_integration(
            data_dir=self.data,
            binding_file=binding_file,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
            cycle_id="p02-recovery-cycle",
        )
        self.profile = ProviderModelProfile(
            "p02-recovery-profile",
            1,
            "Alibaba Cloud Model Studio",
            "qwen-flash-2025-07-28",
            True,
            1024,
            10240,
            1,
        )
        self.policy = ConfiguredModelProfilePolicy(
            (self.profile,), selected_profile_id=self.profile.profile_id
        )
        self.clock = lambda: datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def app(self, *, p02_fault=None, engine_fault=None):
        provider = ScriptedFakeModelProvider(self.provider_root)
        app = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy,
            clock=self.clock,
            fault_injector=p02_fault,
        )
        if engine_fault is not None:
            app.integration.adapter.service._fault_injector = engine_fault  # noqa: SLF001
        return app, provider

    def recover_p02_fault(self, point: str) -> FirstRoundSuccessResult:
        request = p02_request(1)
        fault = FailOnceAt(point)
        first, _ = self.app(p02_fault=fault)
        with self.assertRaises(RuntimeError):
            first.models.submit(copy.deepcopy(request))
        self.assertTrue(fault.triggered)
        operation_before = first.integration.ledger.load_operation("p02-request-001")
        assert operation_before is not None
        rebuilt, provider = self.app()
        completed = rebuilt.models.submit(copy.deepcopy(request))
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        assert isinstance(completed, FirstRoundSuccessResult)
        operation_after = rebuilt.integration.ledger.load_operation("p02-request-001")
        assert operation_after is not None and operation_after.domain is not None
        self.assertEqual(operation_after.operation_id, operation_before.operation_id)
        record = rebuilt.model_ledger.list_executions()[0]
        self.assertEqual(record.operation_id, operation_after.operation_id)
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 1)
        self.assertEqual(len(record.capability_results), 1)
        self.assertEqual(len(record.delivered_result_ids), 1)
        self.assertEqual(record.completed_response_id, completed.response.response_id)
        self.assertEqual(
            len(JsonAwakeningRepository(self.data).list_sessions("subject-001")),
            1,
        )
        self.assertEqual(
            len(JsonThinkingRepository(self.data).list_think_sessions("subject-001")),
            1,
        )
        self.assertEqual(len(rebuilt.integration.ledger.list_operations()), 1)
        self.assertEqual(len(rebuilt.integration.ledger.list_completed()), 1)
        self.assertEqual(rebuilt.integration.subject_states.load("subject-001").revision, 0)
        replay = rebuilt.models.submit(copy.deepcopy(request))
        self.assertEqual(replay, completed)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 1)
        return completed

    def recover_engine_fault(self, point: str) -> FirstRoundSuccessResult:
        request = p02_request(1)
        fault = FailOnceAt(point)
        first, _ = self.app(engine_fault=fault)
        with self.assertRaises(Exception):
            first.models.submit(copy.deepcopy(request))
        self.assertTrue(fault.triggered)
        operation_before = first.integration.ledger.load_operation("p02-request-001")
        assert operation_before is not None
        rebuilt, provider = self.app()
        completed = rebuilt.models.submit(copy.deepcopy(request))
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        assert isinstance(completed, FirstRoundSuccessResult)
        operation_after = rebuilt.integration.ledger.load_operation("p02-request-001")
        assert operation_after is not None
        self.assertEqual(operation_after.operation_id, operation_before.operation_id)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 1)
        record = rebuilt.model_ledger.list_executions()[0]
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(record.capability_results), 1)
        self.assertEqual(record.completed_response_id, completed.response.response_id)
        self.assertEqual(
            len(JsonThinkingRepository(self.data).list_think_sessions("subject-001")),
            1,
        )
        self.assertEqual(len(rebuilt.integration.ledger.list_completed()), 1)
        return completed

    def test_recovery_after_model_execution_reserved(self) -> None:
        self.recover_p02_fault("after_model_execution_reserved")

    def test_recovery_after_provider_dispatch_reserved(self) -> None:
        self.recover_p02_fault("after_provider_dispatch_reserved")

    def test_recovery_queries_provider_after_response_was_generated_but_not_recorded(
        self,
    ) -> None:
        self.recover_p02_fault("after_provider_returned_before_fact")

    def test_recovery_after_provider_fact_before_usage(self) -> None:
        self.recover_p02_fault("after_provider_fact_persisted")

    def test_recovery_after_usage_before_capability_result(self) -> None:
        self.recover_p02_fault("after_usage_persisted")

    def test_recovery_after_capability_result_before_e5_acceptance(self) -> None:
        self.recover_p02_fault("after_capability_result_prepared")

    def test_response_loss_after_engine_completion_replays_original_result(self) -> None:
        self.recover_p02_fault("after_engine_result_before_delivery_checkpoint")

    def test_recovery_after_delivery_checkpoint(self) -> None:
        self.recover_p02_fault("after_delivery_checkpoint_saved")

    def test_recovery_after_ambiguous_query_resolution_checkpoint(self) -> None:
        provider = ResolvingModelProvider()
        fault = FailOnceAt("after_provider_query_resolution_persisted")
        first = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy,
            clock=self.clock,
            fault_injector=fault,
        )
        waiting = first.models.submit(p02_request(1))
        self.assertNotIsInstance(waiting, FirstRoundSuccessResult)
        with self.assertRaises(RuntimeError):
            first.models.recover("p02-request-001")
        self.assertTrue(fault.triggered)

        rebuilt = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy,
            clock=self.clock,
        )
        completed = rebuilt.models.recover("p02-request-001")
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        record = rebuilt.model_ledger.list_executions()[0]
        self.assertEqual(provider.execute_count, 1)
        self.assertEqual(provider.query_count, 1)
        self.assertEqual(len(record.attempts[0].query_resolutions), 1)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 1)
        self.assertEqual(len(record.capability_results), 2)
        self.assertEqual(len(rebuilt.integration.ledger.list_completed()), 1)

    def test_e5_result_persisted_checkpoint_recovery(self) -> None:
        self.recover_engine_fault("after_capability_result_persisted")

    def test_e5_original_thinking_resume_recovery(self) -> None:
        self.recover_engine_fault("after_capability_thinking_completed")

    def test_e5_action_recovery_does_not_create_second_action(self) -> None:
        completed = self.recover_engine_fault("after_action_completed")
        operation = self.app()[0].integration.ledger.load_operation(completed.request_id)
        assert operation is not None and operation.domain is not None
        self.assertIsNotNone(operation.domain.action_session_id)

    def test_e5_completed_result_response_loss_recovery(self) -> None:
        self.recover_engine_fault("after_completed_result_saved")

    def test_restart_can_continue_with_a_new_round(self) -> None:
        first, _ = self.app()
        result_one = first.models.submit(p02_request(1))
        rebuilt, provider = self.app()
        result_two = rebuilt.models.submit(p02_request(2))
        self.assertIsInstance(result_one, FirstRoundSuccessResult)
        self.assertIsInstance(result_two, FirstRoundSuccessResult)
        self.assertEqual(len(rebuilt.model_ledger.list_executions()), 2)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 2)
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(rebuilt.integration.subject_states.load("subject-001").revision, 0)


if __name__ == "__main__":
    unittest.main()
