from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationRequestQueryStatus,
)
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationInitializationError,
    build_local_integration_app,
    initialize_local_integration,
)
from continuity_engine.services.deterministic_integration_providers import (
    DeterministicThinkingProvider,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
)
from continuity_engine.storage.json_awakening_repository import (
    JsonAwakeningRepository,
)
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from tests.test_contract_test_adapter import first_round_request


class FailOnceAt:
    def __init__(self, target: str) -> None:
        self.target = target
        self.triggered = False

    def __call__(self, stage, operation) -> None:
        del operation
        if stage == self.target and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"simulated crash at {stage}")


class E4CrashRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "formal-data"
        self.binding_file = self.root / "binding.json"
        fixture = SubjectBindingFixture.first_round()
        self.binding_file.write_text(
            json.dumps(fixture.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
            cycle_id="formal-cycle-001",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _sessions(self):
        wakes = JsonAwakeningRepository(self.data).list_sessions("subject-001")
        thinks = JsonThinkingRepository(self.data).list_think_sessions("subject-001")
        return wakes, thinks

    def _recover_case(
        self,
        fault_point: str,
        *,
        content: str = "remember continuity test focus",
    ) -> FirstRoundSuccessResult:
        request = first_round_request(content)
        app = build_local_integration_app(self.data)
        fault = FailOnceAt(fault_point)
        app.adapter.service._fault_injector = fault  # noqa: SLF001 - crash injection
        with self.assertRaises(IntegrationExecutionError):
            app.adapter.submit(copy.deepcopy(request))
        self.assertTrue(fault.triggered)

        operation = app.ledger.load_operation(request["requestId"])
        self.assertIsNotNone(operation)
        assert operation is not None
        query = app.adapter.query_request(request["requestId"])
        self.assertIsNotNone(query)
        assert query is not None
        expected_query = (
            IntegrationRequestQueryStatus.COMPLETED
            if fault_point == "after_completed_result_saved"
            else IntegrationRequestQueryStatus.RECOVERY_REQUIRED
        )
        self.assertIs(query.status, expected_query)
        persisted_result = app.ledger.load_completed(request["requestId"])
        wakes_before, thinks_before = self._sessions()
        completed_thinking_exists = any(
            session.completed_successfully for session in thinks_before
        )

        provider_guard = (
            patch.object(
                DeterministicThinkingProvider,
                "think",
                side_effect=AssertionError(
                    "completed ThinkingProvider must not be invoked during recovery"
                ),
            )
            if completed_thinking_exists
            else nullcontext()
        )
        with provider_guard:
            rebuilt = build_local_integration_app(self.data)
            result = rebuilt.adapter.submit(copy.deepcopy(request))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        assert isinstance(result, FirstRoundSuccessResult)
        self.assertEqual(result.request_id, request["requestId"])
        self.assertEqual(result.request_hash, request["requestHash"])
        self.assertEqual(result.operation_id, operation.operation_id)
        final_operation = rebuilt.ledger.load_operation(request["requestId"])
        self.assertIsNotNone(final_operation)
        assert final_operation is not None
        if operation.domain_progress is not None:
            self.assertEqual(
                final_operation.domain_progress.wake_session_id,
                operation.domain_progress.wake_session_id,
            )
            self.assertEqual(
                final_operation.domain_progress.think_session_id,
                operation.domain_progress.think_session_id,
            )
            self.assertEqual(
                final_operation.domain_progress.response_id,
                operation.domain_progress.response_id,
            )
        if operation.domain is not None:
            self.assertEqual(final_operation.domain, operation.domain)
        if operation.evolution is not None:
            self.assertEqual(final_operation.evolution, operation.evolution)

        wakes_after, thinks_after = self._sessions()
        self.assertEqual(len(wakes_after), 1)
        self.assertEqual(len(thinks_after), 1)
        if wakes_before:
            self.assertEqual(
                {item.session_id for item in wakes_after},
                {item.session_id for item in wakes_before},
            )
        if completed_thinking_exists:
            self.assertEqual(
                {item.think_id for item in thinks_after},
                {item.think_id for item in thinks_before},
            )

        expected_revision = 1 if content == "remember continuity test focus" else 0
        self.assertEqual(rebuilt.subject_states.load("subject-001").revision, expected_revision)
        history = rebuilt.subject_states.get_update_history("subject-001")
        self.assertEqual(len(history), expected_revision)
        replay = rebuilt.adapter.submit(copy.deepcopy(request))
        self.assertEqual(replay, result)
        self.assertEqual(
            len(rebuilt.subject_states.get_update_history("subject-001")),
            expected_revision,
        )
        if persisted_result is not None:
            self.assertEqual(result, persisted_result)
        return result

    def test_operation_reserved_recovery(self) -> None:
        self._recover_case("after_operation_reserved")

    def test_wake_completed_before_operation_checkpoint_recovery(self) -> None:
        self._recover_case("after_wake_completed")

    def test_wake_checkpoint_recovery(self) -> None:
        self._recover_case("after_wake_checkpoint_saved")

    def test_perception_checkpoint_recovery(self) -> None:
        self._recover_case("after_perception_checkpoint_saved")

    def test_thinking_completed_before_operation_checkpoint_recovery(self) -> None:
        self._recover_case("after_thinking_completed")

    def test_thinking_checkpoint_recovery(self) -> None:
        self._recover_case("after_thinking_checkpoint_saved")

    def test_domain_checkpoint_recovery(self) -> None:
        self._recover_case("after_domain_completed")

    def test_evolution_commit_before_operation_checkpoint_recovery(self) -> None:
        self._recover_case("after_evolution_committed")

    def test_evolution_checkpoint_recovery(self) -> None:
        self._recover_case("after_evolution_checkpoint_saved")

    def test_completed_result_before_operation_completion_recovery(self) -> None:
        self._recover_case("after_completed_result_saved")

    def test_changed_false_recovers_without_event_or_revision_advance(self) -> None:
        result = self._recover_case(
            "after_thinking_completed",
            content="hello",
        )
        self.assertFalse(result.state_projection.changed)
        self.assertIsNone(result.state_projection.engine_update_id)

    def test_legacy_reserved_operation_with_completed_wake_and_thinking_recovers(self) -> None:
        request = first_round_request("remember continuity test focus")
        app = build_local_integration_app(self.data)
        app.adapter.service._fault_injector = FailOnceAt(  # noqa: SLF001
            "after_thinking_completed"
        )
        with self.assertRaises(IntegrationExecutionError):
            app.adapter.submit(copy.deepcopy(request))

        journal_path = app.ledger.operation_path
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["operationJournalFormatVersion"] = 1
        operation = journal["operations"][0]
        operation.pop("domainProgress")
        self.assertEqual(operation["stage"], "reserved")
        self.assertIsNone(operation["domain"])
        journal_path.write_text(json.dumps(journal), encoding="utf-8")

        wake_path = next((self.data / "awakening" / "sessions").rglob("*.json"))
        wake = json.loads(wake_path.read_text(encoding="utf-8"))
        wake.pop("recovery_context")
        wake_path.write_text(json.dumps(wake), encoding="utf-8")
        think_path = next((self.data / "thinking" / "sessions").rglob("*.json"))
        think = json.loads(think_path.read_text(encoding="utf-8"))
        think.pop("perception_snapshot")
        think_path.write_text(json.dumps(think), encoding="utf-8")

        with patch.object(
            DeterministicThinkingProvider,
            "think",
            side_effect=AssertionError("legacy completed Thinking must be reused"),
        ):
            rebuilt = build_local_integration_app(self.data)
            result = rebuilt.adapter.submit(copy.deepcopy(request))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        self.assertEqual(len(self._sessions()[0]), 1)
        self.assertEqual(len(self._sessions()[1]), 1)
        self.assertEqual(rebuilt.subject_states.load("subject-001").revision, 1)
        self.assertEqual(len(rebuilt.subject_states.get_update_history("subject-001")), 1)

    def test_conflicting_progress_fails_closed(self) -> None:
        app = build_local_integration_app(self.data)
        app.adapter.service._fault_injector = FailOnceAt(  # noqa: SLF001
            "after_wake_checkpoint_saved"
        )
        with self.assertRaises(IntegrationExecutionError):
            app.adapter.submit(first_round_request())
        journal_path = app.ledger.operation_path
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["operations"][0]["domainProgress"]["wakeContext"][
            "context_id"
        ] = "conflicting-context"
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(LocalIntegrationInitializationError):
            build_local_integration_app(self.data)

    def test_legacy_completed_operation_json_still_loads(self) -> None:
        request = first_round_request()
        app = build_local_integration_app(self.data)
        result = app.adapter.submit(copy.deepcopy(request))
        journal_path = app.ledger.operation_path
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["operationJournalFormatVersion"] = 1
        journal["operations"][0].pop("domainProgress")
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        replay = build_local_integration_app(self.data).adapter.submit(request)
        self.assertEqual(replay, result)

    def test_hash_conflict_remains_terminal_after_recovery(self) -> None:
        self._recover_case("after_wake_checkpoint_saved", content="hello")
        app = build_local_integration_app(self.data)
        conflict = app.adapter.submit(
            first_round_request("different", request_id="request-001")
        )
        self.assertIsInstance(conflict, FirstRoundErrorEnvelope)
        assert isinstance(conflict, FirstRoundErrorEnvelope)
        self.assertEqual(conflict.error.code.value, "IDEMPOTENCY_KEY_REUSED")

if __name__ == "__main__":
    unittest.main()
