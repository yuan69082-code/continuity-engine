from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.errors import (
    IntegrationExecutionError,
    IntegrationLedgerConflictError,
    IntegrationPersistenceError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    IntegrationOperationRecord,
    IntegrationOperationStage,
    IntegrationRequestQueryStatus,
)
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.interfaces.contract_test_adapter import ContractTestAdapter
from continuity_engine.interfaces.integration_adapter import IntegrationAdapter
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationInitializationError,
    build_local_integration_app,
    initialize_local_integration,
)
from continuity_engine.services.continuity_interaction_service import (
    ContinuityInteractionService,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_request_hash,
)
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from continuity_engine.storage.json_subject_binding_repository import JsonSubjectBindingRepository
from tests.test_contract_test_adapter import first_round_request
from tests.shared.contract_runtime import build_shared_contract_runtime


ROOT = Path(__file__).resolve().parents[1]


class E4LocalIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "formal-data"
        self.binding_file = self.root / "binding.json"
        self.fixture = SubjectBindingFixture.first_round()
        self.binding_hash = calculate_binding_fixture_hash(self.fixture)
        self.binding_file.write_text(
            json.dumps(self.fixture.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.cycle_id = "formal-cycle-001"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initialize(self) -> SubjectBinding:
        return initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=self.binding_hash,
            cycle_id=self.cycle_id,
        )

    def test_empty_directory_explicit_initialization_succeeds(self) -> None:
        binding = self.initialize()
        app = build_local_integration_app(self.data)
        self.assertEqual(binding.subject_id, "subject-001")
        self.assertEqual(app.subject_states.load(binding.subject_id).revision, 0)
        self.assertTrue(app.is_ready())

    def test_runtime_binding_is_not_the_fixture_model(self) -> None:
        binding = self.initialize()
        self.assertIsInstance(binding, SubjectBinding)
        self.assertNotIsInstance(binding, SubjectBindingFixture)
        self.assertEqual(binding.to_fixture(), self.fixture)

    def test_binding_hash_is_independently_recalculated(self) -> None:
        binding = self.initialize()
        self.assertEqual(
            calculate_binding_fixture_hash(binding.to_fixture()),
            binding.binding_fixture_hash,
        )

    def test_binding_timestamps_are_preserved(self) -> None:
        binding = self.initialize()
        self.assertEqual(binding.created_at, "2026-07-30T00:00:00Z")
        self.assertEqual(binding.effective_at, "2026-07-30T00:00:00Z")

    def test_cycle_id_is_not_part_of_fixture_hash(self) -> None:
        binding = self.initialize()
        other = replace(binding, cycle_id="another-cycle")
        self.assertEqual(
            calculate_binding_fixture_hash(binding.to_fixture()),
            calculate_binding_fixture_hash(other.to_fixture()),
        )

    def test_same_configuration_repeated_init_is_idempotent(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        app.adapter.submit(first_round_request("remember continuity test focus"))
        before = {path: path.read_bytes() for path in self.data.rglob("*.json")}
        self.initialize()
        after = {path: path.read_bytes() for path in self.data.rglob("*.json")}
        self.assertEqual(before, after)
        self.assertEqual(build_local_integration_app(self.data).subject_states.load("subject-001").revision, 1)

    def test_different_cycle_id_is_rejected(self) -> None:
        self.initialize()
        with self.assertRaises(LocalIntegrationInitializationError):
            initialize_local_integration(
                data_dir=self.data,
                binding_file=self.binding_file,
                binding_fixture_hash=self.binding_hash,
                cycle_id="different-cycle",
            )

    def test_different_binding_is_rejected(self) -> None:
        self.initialize()
        changed = copy.deepcopy(self.fixture.to_dict())
        changed["bindingId"] = "binding-002"
        self.binding_file.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            self.initialize()

    def test_wrong_binding_hash_is_rejected_without_data_creation(self) -> None:
        with self.assertRaises(LocalIntegrationInitializationError):
            initialize_local_integration(
                data_dir=self.data,
                binding_file=self.binding_file,
                binding_fixture_hash="sha256:" + "0" * 64,
                cycle_id=self.cycle_id,
            )
        self.assertFalse(self.data.exists())

    def test_unknown_binding_field_is_rejected(self) -> None:
        changed = self.fixture.to_dict()
        changed["secret"] = "must-not-persist"
        self.binding_file.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            self.initialize()

    def test_corrupt_binding_input_is_rejected(self) -> None:
        self.binding_file.write_text("{broken", encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            self.initialize()

    def test_formal_binding_repository_is_immutable(self) -> None:
        binding = self.initialize()
        repository = JsonSubjectBindingRepository(self.data)
        with self.assertRaises(IntegrationLedgerConflictError):
            repository.initialize(replace(binding, cycle_id="new-cycle"))

    def test_corrupt_persisted_binding_is_rejected(self) -> None:
        self.initialize()
        repository = JsonSubjectBindingRepository(self.data)
        repository.path.write_text("{}", encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            build_local_integration_app(self.data)

    def test_partial_initialization_is_rejected(self) -> None:
        self.data.mkdir()
        JsonSubjectBindingRepository(self.data).initialize(
            SubjectBinding.from_fixture(
                self.fixture,
                cycle_id=self.cycle_id,
                binding_fixture_hash=self.binding_hash,
            )
        )
        with self.assertRaises(LocalIntegrationInitializationError):
            self.initialize()
        unrelated = self.root / "partial-without-binding"
        unrelated.mkdir()
        (unrelated / "unexpected.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            initialize_local_integration(
                data_dir=unrelated,
                binding_file=self.binding_file,
                binding_fixture_hash=self.binding_hash,
                cycle_id=self.cycle_id,
            )

    def test_uninitialized_serve_graph_does_not_create_state(self) -> None:
        with self.assertRaises(LocalIntegrationInitializationError):
            build_local_integration_app(self.data)
        self.assertFalse(self.data.exists())

    def test_formal_build_does_not_call_contract_test_bootstrap(self) -> None:
        self.initialize()
        with patch(
            "continuity_engine.services.contract_test_bootstrap.FirstRoundContractBootstrap.prepare",
            side_effect=AssertionError("formal app must not call test bootstrap"),
        ):
            self.assertTrue(build_local_integration_app(self.data).is_ready())

    def test_formal_adapter_and_test_adapter_share_service_class(self) -> None:
        self.initialize()
        formal = build_local_integration_app(self.data).adapter
        test_adapter = build_shared_contract_runtime(self.root / "test-data").adapter
        self.assertIsInstance(formal, IntegrationAdapter)
        self.assertIsInstance(test_adapter, ContractTestAdapter)
        self.assertIsInstance(formal.service, ContinuityInteractionService)
        self.assertIsInstance(test_adapter.service, ContinuityInteractionService)

    def test_changed_false_does_not_evolve(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        result = app.adapter.submit(first_round_request())
        self.assertFalse(result.state_projection.changed)
        self.assertIsNone(result.state_projection.engine_update_id)
        self.assertEqual(app.subject_states.load("subject-001").revision, 0)
        self.assertEqual(app.subject_states.get_update_history("subject-001"), [])

    def test_changed_true_evolves_exactly_once(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        request = first_round_request("remember continuity test focus")
        first = app.adapter.submit(request)
        replay = app.adapter.submit(request)
        self.assertEqual(first, replay)
        self.assertTrue(first.state_projection.changed)
        self.assertEqual(app.subject_states.load("subject-001").revision, 1)
        self.assertEqual(len(app.subject_states.get_update_history("subject-001")), 1)

    def test_completed_query_returns_first_complete_result(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        result = app.adapter.submit(first_round_request())
        query = app.adapter.query_request("request-001")
        self.assertIsNotNone(query)
        assert query is not None
        self.assertIs(query.status, IntegrationRequestQueryStatus.COMPLETED)
        self.assertEqual(query.request_hash, result.request_hash)
        self.assertEqual(query.operation_id, result.operation_id)
        self.assertEqual(query.result, result)

    def test_unknown_query_returns_none_without_domain_execution(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        self.assertIsNone(app.adapter.query_request("missing-request"))
        self.assertEqual(app.adapter.service.last_call_log, [])
        self.assertEqual(app.subject_states.get_update_history("subject-001"), [])

    def test_nonterminal_operation_query_is_recovery_required(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        now = "2026-07-30T00:00:00Z"
        operation = IntegrationOperationRecord(
            request_id="request-recovery",
            request_hash="sha256:" + "1" * 64,
            operation_id="operation-recovery",
            subject_id="subject-001",
            binding_id="binding-001",
            binding_version=1,
            input_revision=0,
            consumed_observation_ids=("observation-request-recovery",),
            stage=IntegrationOperationStage.RESERVED,
            reserved_at=now,
            updated_at=now,
        )
        app.ledger.save_operation(operation)
        query = app.adapter.query_request(operation.request_id)
        self.assertIsNotNone(query)
        assert query is not None
        self.assertIs(query.status, IntegrationRequestQueryStatus.RECOVERY_REQUIRED)
        self.assertIsNone(query.result)
        self.assertEqual(query.operation_id, operation.operation_id)

    def test_reserved_recovery_post_reuses_operation_id(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        request = first_round_request(request_id="request-recovery")
        now = "2026-07-30T00:00:00Z"
        app.ledger.save_operation(
            IntegrationOperationRecord(
                request_id="request-recovery",
                request_hash=request["requestHash"],
                operation_id="operation-stable",
                subject_id="subject-001",
                binding_id="binding-001",
                binding_version=1,
                input_revision=0,
                consumed_observation_ids=("observation-001",),
                stage=IntegrationOperationStage.RESERVED,
                reserved_at=now,
                updated_at=now,
            )
        )
        result = app.adapter.submit(request)
        self.assertEqual(result.operation_id, "operation-stable")

    def test_recovery_with_different_hash_returns_idempotency_error(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        original = first_round_request(request_id="request-stable")
        app.adapter.submit(original)
        changed = first_round_request("different", request_id="request-stable")
        result = app.adapter.submit(changed)
        self.assertEqual(result.error.code.value, "IDEMPOTENCY_KEY_REUSED")

    def test_rebuild_restores_completed_result_exactly(self) -> None:
        self.initialize()
        first_app = build_local_integration_app(self.data)
        result = first_app.adapter.submit(
            first_round_request("remember continuity test focus")
        )
        second_app = build_local_integration_app(self.data)
        replay = second_app.adapter.submit(
            first_round_request("remember continuity test focus")
        )
        self.assertEqual(replay.to_dict(), result.to_dict())
        self.assertEqual(second_app.subject_states.load("subject-001").revision, 1)
        self.assertEqual(len(second_app.subject_states.get_update_history("subject-001")), 1)

    def test_completed_result_with_noncompleted_operation_is_reconciled(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        result = app.adapter.submit(first_round_request())
        operation = app.ledger.load_operation(result.request_id)
        assert operation is not None
        app.ledger._operation_path.write_text(  # noqa: SLF001 - deliberate recovery fixture
            json.dumps(
                {
                    "operationJournalFormatVersion": 1,
                    "operations": [
                        replace(
                            operation,
                            stage=IntegrationOperationStage.DOMAIN_COMPLETED,
                        ).to_dict()
                    ],
                }
            ),
            encoding="utf-8",
        )
        rebuilt = build_local_integration_app(self.data)
        replay = rebuilt.adapter.submit(first_round_request())
        self.assertEqual(replay, result)
        self.assertIs(
            rebuilt.ledger.load_operation(result.request_id).stage,
            IntegrationOperationStage.COMPLETED,
        )

    def test_query_model_has_exact_envelope_shape(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        app.adapter.submit(first_round_request())
        payload = app.adapter.query_request("request-001").to_dict()
        self.assertEqual(
            set(payload),
            {"contractVersion", "requestId", "requestHash", "operationId", "status", "result"},
        )

    def test_ledger_initialization_rejects_one_missing_file(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        app.adapter.submit(first_round_request())
        ledger = JsonIntegrationResultLedger(self.data)
        ledger.operation_path.unlink()
        with self.assertRaises(IntegrationPersistenceError):
            ledger.initialize_empty()
        ledger.operation_path.write_text(
            json.dumps(
                {"operationJournalFormatVersion": 1, "operations": []}
            ),
            encoding="utf-8",
        )
        with self.assertRaises(LocalIntegrationInitializationError):
            build_local_integration_app(self.data)

    def test_service_wraps_unexpected_fault_in_formal_error(self) -> None:
        self.initialize()
        app = build_local_integration_app(self.data)
        with patch.object(app.ledger, "lookup", side_effect=RuntimeError("secret details")):
            with self.assertRaises(IntegrationExecutionError) as raised:
                app.adapter.submit(first_round_request())
        self.assertEqual(raised.exception.stage, "ledger")
        self.assertNotIn("secret details", str(raised.exception))

    def test_init_cli_succeeds_and_is_idempotent(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        command = [
            sys.executable,
            "-m",
            "continuity_engine.integration_server",
            "init",
            "--data-dir",
            str(self.data),
            "--binding-file",
            str(self.binding_file),
            "--binding-fixture-hash",
            self.binding_hash,
            "--cycle-id",
            self.cycle_id,
        ]
        first = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        second = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(first.returncode, 0, first.stderr.decode())
        self.assertEqual(second.returncode, 0, second.stderr.decode())
        self.assertTrue(build_local_integration_app(self.data).is_ready())

    def test_init_cli_rejects_different_existing_configuration(self) -> None:
        self.initialize()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "continuity_engine.integration_server",
                "init",
                "--data-dir",
                str(self.data),
                "--binding-file",
                str(self.binding_file),
                "--binding-fixture-hash",
                self.binding_hash,
                "--cycle-id",
                "different-cycle",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn(self.fixture.to_dict()["userId"].encode(), completed.stderr)

    def test_formal_modules_do_not_import_test_or_legacy_boundaries(self) -> None:
        formal_files = [
            ROOT / "src/continuity_engine/services/continuity_interaction_service.py",
            ROOT / "src/continuity_engine/interfaces/integration_adapter.py",
            ROOT / "src/continuity_engine/interfaces/local_integration_app.py",
            ROOT / "src/continuity_engine/interfaces/integration_http_server.py",
            ROOT / "src/continuity_engine/integration_server.py",
        ]
        forbidden = (
            "from tests",
            "import tests",
            "contract_test_adapter",
            "contract_test_bootstrap",
            "continuity_contract_jsonl_runner",
            "APIService",
            "UserInteractionService",
            "interfaces.http_server",
        )
        for path in formal_files:
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, source)

    def test_only_shared_service_defines_domain_processing_methods(self) -> None:
        definitions = []
        for path in (ROOT / "src/continuity_engine").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for name in ("_run_domain", "_complete_evolution", "_build_result"):
                if f"def {name}(" in source:
                    definitions.append((path.name, name))
        self.assertEqual(
            definitions,
            [
                ("continuity_interaction_service.py", "_run_domain"),
                ("continuity_interaction_service.py", "_complete_evolution"),
                ("continuity_interaction_service.py", "_build_result"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
