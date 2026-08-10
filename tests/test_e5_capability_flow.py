from __future__ import annotations

import copy
import inspect
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.capability import (
    CAPABILITY_CONTRACT_VERSION,
    CAPABILITY_RESULT_SCHEMA_VERSION,
    CapabilityFailedEnvelope,
    CapabilityRequiredEnvelope,
    CapabilityStatus,
    IntegrationThinkingMode,
    calculate_capability_content_hash,
)
from continuity_engine.domain.errors import (
    CapabilityConflictError,
    CapabilityNotFoundError,
    CapabilityValidationError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    FirstRoundSuccessResult,
    format_contract_datetime,
)
from continuity_engine.domain.thinking import ThinkSessionStatus
from continuity_engine.interfaces.capability_schema import (
    CAPABILITY_MODEL_OUTPUT_SCHEMA_ID,
    CAPABILITY_REQUEST_SCHEMA_ID,
    CAPABILITY_RESULT_SCHEMA_ID,
    DEFAULT_CAPABILITY_SCHEMA_REGISTRY,
)
from continuity_engine.interfaces import local_integration_app as formal_assembly
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationInitializationError,
    build_local_integration_app,
    initialize_local_integration,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
)
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from tests.test_contract_test_adapter import first_round_request


def capability_result_payload(
    required: CapabilityRequiredEnvelope,
    *,
    result_id: str = "capability-result-001",
    status: CapabilityStatus = CapabilityStatus.SUCCEEDED,
    response: str = "Hello from the bounded capability result.",
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, object]:
    request = required.capability_request
    request_created_at = datetime.fromisoformat(
        request.created_at[:-1] + "+00:00"
    )
    actual_started_at = started_at or format_contract_datetime(
        request_created_at + timedelta(seconds=1)
    )
    parsed_started_at = datetime.fromisoformat(
        actual_started_at[:-1] + "+00:00"
    )
    actual_completed_at = completed_at or format_contract_datetime(
        parsed_started_at + timedelta(seconds=1)
    )
    output = (
        {
            "schemaVersion": "continuity-model-output/v1",
            "responseCandidate": response,
            "metadata": {"finishReason": "stop"},
        }
        if status is CapabilityStatus.SUCCEEDED
        else None
    )
    retry_class = (
        None
        if status is CapabilityStatus.SUCCEEDED
        else "retry"
        if status is CapabilityStatus.FAILED_RETRYABLE
        else "query"
        if status is CapabilityStatus.UNKNOWN
        else "never"
    )
    return {
        "contractVersion": CAPABILITY_CONTRACT_VERSION,
        "schemaVersion": CAPABILITY_RESULT_SCHEMA_VERSION,
        "capabilityResultId": result_id,
        "capabilityRequestId": request.capability_request_id,
        "operationId": required.operation_id,
        "requestId": required.request_id,
        "requestHash": required.request_hash,
        "subjectId": required.subject_id,
        "bindingId": request.binding_id,
        "bindingVersion": request.binding_version,
        "status": status.value,
        "capabilityType": "model.generate",
        "provider": {
            "providerType": "model",
            "providerId": "vio-test-provider",
            "modelName": "deterministic-model-stub",
        },
        "output": output,
        "contentHash": calculate_capability_content_hash(output),
        "startedAt": actual_started_at,
        "completedAt": actual_completed_at,
        "actualUsage": {"inputTokens": 12, "outputTokens": 8, "totalTokens": 20},
        "vioLedgerEntryId": f"vio-ledger-{result_id}",
        "errorCode": None if output is not None else f"{status.value}_TEST",
        "retryClass": retry_class,
        "auditRef": f"audit-{result_id}",
        "executionFact": True,
    }


class CapabilityFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "formal-data"
        fixture = SubjectBindingFixture.first_round()
        self.binding_file = self.root / "binding.json"
        self.binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        self.binding_fixture_hash = calculate_binding_fixture_hash(fixture)
        initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=self.binding_fixture_hash,
            cycle_id="formal-cycle-001",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def capability_app(self):
        return build_local_integration_app(
            self.data,
            thinking_mode=IntegrationThinkingMode.CAPABILITY,
        )

    def initialize_again(self) -> None:
        initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=self.binding_fixture_hash,
            cycle_id="formal-cycle-001",
        )

    def persisted_json(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.data).as_posix(): path.read_bytes()
            for path in sorted(self.data.rglob("*.json"))
        }


class E5CapabilityFlowTests(CapabilityFixture):
    def test_schema_registry_is_closed_and_complete(self) -> None:
        self.assertEqual(
            set(DEFAULT_CAPABILITY_SCHEMA_REGISTRY.schema_ids),
            {
                CAPABILITY_REQUEST_SCHEMA_ID,
                CAPABILITY_RESULT_SCHEMA_ID,
                CAPABILITY_MODEL_OUTPUT_SCHEMA_ID,
            },
        )

    def test_capability_mode_returns_durable_capability_required(self) -> None:
        app = self.capability_app()
        with (
            patch("socket.create_connection") as create_connection,
            patch("urllib.request.urlopen") as urlopen,
        ):
            result = app.adapter.submit(first_round_request())
        create_connection.assert_not_called()
        urlopen.assert_not_called()
        assembly_source = inspect.getsource(formal_assembly)
        self.assertNotIn("ContractTestAdapter", assembly_source)
        self.assertNotIn("contract_runtime", assembly_source)
        self.assertNotIn("tests.shared", assembly_source)
        self.assertIsInstance(result, CapabilityRequiredEnvelope)
        assert isinstance(result, CapabilityRequiredEnvelope)
        self.assertEqual(result.status, "capability_required")
        self.assertEqual(result.capability_request.originating_session_type, "thinking")
        self.assertEqual(result.capability_request.capability_type, "model.generate")
        self.assertEqual(result.capability_request.task_type, "conversation_response")
        self.assertEqual(result.capability_request.input.source_revision, 0)
        self.assertNotIn("StateMutation", json.dumps(result.to_dict()))
        self.assertNotIn("apiKey", json.dumps(result.to_dict()))

    def test_repeated_query_returns_identical_capability_request(self) -> None:
        app = self.capability_app()
        first = app.adapter.submit(first_round_request())
        second = app.adapter.query_request("request-001")
        third = app.adapter.query_request("request-001")
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_capability_request_survives_rebuild_exactly(self) -> None:
        first_app = self.capability_app()
        first = first_app.adapter.submit(first_round_request())
        second_app = self.capability_app()
        second = second_app.adapter.query_request("request-001")
        self.assertEqual(first, second)

    def test_think_session_waits_with_stable_binding(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        sessions = JsonThinkingRepository(self.data).list_think_sessions("subject-001")
        self.assertEqual(len(sessions), 1)
        self.assertIs(sessions[0].status, ThinkSessionStatus.WAITING_CAPABILITY)
        self.assertEqual(
            sessions[0].capability_request_id,
            required.capability_request.capability_request_id,
        )
        self.assertEqual(
            sessions[0].think_id,
            required.capability_request.originating_session_id,
        )

    def test_success_resumes_thinking_action_and_reply_without_state_change(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required, response="Capability expression")
        completed = app.adapter.submit_capability_result(payload)
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        assert isinstance(completed, FirstRoundSuccessResult)
        self.assertEqual(completed.response.content, "Capability expression")
        self.assertFalse(completed.state_projection.changed)
        self.assertEqual(completed.state_projection.current_revision, 0)
        self.assertIsNone(completed.state_projection.engine_update_id)
        self.assertEqual(app.subject_states.get_update_history("subject-001"), [])
        session = JsonThinkingRepository(self.data).list_think_sessions("subject-001")[0]
        self.assertIs(session.status, ThinkSessionStatus.COMPLETED)
        self.assertFalse(session.result.update_subject_state)
        self.assertIn("action", app.adapter.service.last_call_log)

    def test_exact_result_replay_returns_first_completed_result(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        first = app.adapter.submit_capability_result(copy.deepcopy(payload))
        replay = app.adapter.submit_capability_result(copy.deepcopy(payload))
        self.assertEqual(first, replay)
        self.assertEqual(len(JsonThinkingRepository(self.data).list_think_sessions("subject-001")), 1)

    def test_result_id_reuse_with_different_content_is_rejected(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        app.adapter.submit_capability_result(payload)
        changed = capability_result_payload(required, response="different")
        with self.assertRaises(CapabilityConflictError):
            app.adapter.submit_capability_result(changed)

    def test_wrong_identity_fields_are_rejected(self) -> None:
        fields = {
            "requestId": "request-other",
            "requestHash": "sha256:" + "1" * 64,
            "operationId": "operation-other",
            "capabilityRequestId": "capability-other",
            "subjectId": "subject-other",
            "bindingId": "binding-other",
        }
        for field, value in fields.items():
            with self.subTest(field=field):
                data = self.root / field
                data.mkdir()
                fixture = SubjectBindingFixture.first_round()
                binding_file = data / "binding.json"
                binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
                initialized = data / "runtime"
                initialize_local_integration(
                    data_dir=initialized,
                    binding_file=binding_file,
                    binding_fixture_hash=calculate_binding_fixture_hash(fixture),
                    cycle_id="formal-cycle-001",
                )
                app = build_local_integration_app(
                    initialized,
                    thinking_mode=IntegrationThinkingMode.CAPABILITY,
                )
                required = app.adapter.submit(first_round_request())
                assert isinstance(required, CapabilityRequiredEnvelope)
                payload = capability_result_payload(required)
                payload[field] = value
                with self.assertRaises(
                    (CapabilityValidationError, CapabilityNotFoundError)
                ) as raised:
                    app.adapter.submit_capability_result(payload)
                self.assertIsNotNone(raised.exception)

    def test_wrong_content_hash_is_rejected(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        payload["contentHash"] = "sha256:" + "0" * 64
        with self.assertRaises(CapabilityValidationError):
            app.adapter.submit_capability_result(payload)

    def test_result_cannot_exceed_request_output_limit(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required, response="x" * 4097)
        with self.assertRaises(CapabilityValidationError):
            app.adapter.submit_capability_result(payload)

    def test_result_completion_cannot_precede_start(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        payload = capability_result_payload(required)
        completed_at = datetime.fromisoformat(
            str(payload["completedAt"])[:-1] + "+00:00"
        )
        payload["startedAt"] = format_contract_datetime(
            completed_at + timedelta(seconds=1)
        )
        with self.assertRaises(CapabilityValidationError):
            app.adapter.submit_capability_result(payload)

    def test_blank_success_is_rejected_before_persistence_and_valid_retry_completes(
        self,
    ) -> None:
        for index, response in enumerate(("", "   "), start=1):
            with self.subTest(response=repr(response)):
                request_id = f"request-blank-{index}"
                app = self.capability_app()
                required = app.adapter.submit(
                    first_round_request(request_id=request_id)
                )
                assert isinstance(required, CapabilityRequiredEnvelope)
                operation_before = app.ledger.load_operation(request_id)
                thinking_before = JsonThinkingRepository(
                    self.data
                ).list_think_sessions("subject-001")
                payload = capability_result_payload(
                    required,
                    result_id=f"blank-result-{index}",
                    response=response,
                )

                with self.assertRaises(CapabilityValidationError):
                    app.adapter.submit_capability_result(payload)

                self.assertEqual(
                    app.ledger.list_capability_attempts(
                        required.capability_request.capability_request_id
                    ),
                    [],
                )
                self.assertEqual(app.ledger.load_operation(request_id), operation_before)
                self.assertEqual(
                    JsonThinkingRepository(self.data).list_think_sessions(
                        "subject-001"
                    ),
                    thinking_before,
                )
                self.assertNotIn("action", app.adapter.service.last_call_log)
                self.assertEqual(app.subject_states.load("subject-001").revision, 0)
                self.assertEqual(
                    app.subject_states.get_update_history("subject-001"),
                    [],
                )
                self.assertIsNone(app.ledger.load_completed(request_id))

                completed = app.adapter.submit_capability_result(
                    capability_result_payload(
                        required,
                        result_id=f"valid-result-{index}",
                    )
                )
                self.assertIsInstance(completed, FirstRoundSuccessResult)

    def test_result_start_cannot_precede_request_creation(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        created_at = datetime.fromisoformat(
            required.capability_request.created_at[:-1] + "+00:00"
        )
        payload = capability_result_payload(
            required,
            started_at=format_contract_datetime(created_at - timedelta(seconds=1)),
            completed_at=format_contract_datetime(created_at + timedelta(seconds=1)),
        )
        operation_before = app.ledger.load_operation(required.request_id)
        with self.assertRaises(CapabilityValidationError):
            app.adapter.submit_capability_result(payload)
        self.assertEqual(
            app.ledger.list_capability_attempts(
                required.capability_request.capability_request_id
            ),
            [],
        )
        self.assertEqual(app.ledger.load_operation(required.request_id), operation_before)

    def test_result_completion_cannot_precede_request_creation(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        created_at = datetime.fromisoformat(
            required.capability_request.created_at[:-1] + "+00:00"
        )
        payload = capability_result_payload(
            required,
            started_at=format_contract_datetime(created_at - timedelta(seconds=2)),
            completed_at=format_contract_datetime(created_at - timedelta(seconds=1)),
        )
        operation_before = app.ledger.load_operation(required.request_id)
        with self.assertRaises(CapabilityValidationError):
            app.adapter.submit_capability_result(payload)
        self.assertEqual(
            app.ledger.list_capability_attempts(
                required.capability_request.capability_request_id
            ),
            [],
        )
        self.assertEqual(app.ledger.load_operation(required.request_id), operation_before)

    def test_repeated_init_is_idempotent_for_unused_and_waiting_capability_data(
        self,
    ) -> None:
        unused_before = self.persisted_json()
        self.initialize_again()
        self.assertEqual(self.persisted_json(), unused_before)

        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        waiting_before = self.persisted_json()
        self.initialize_again()
        self.assertEqual(self.persisted_json(), waiting_before)
        restored = self.capability_app().adapter.query_request(required.request_id)
        self.assertEqual(restored, required)

    def test_repeated_init_is_idempotent_for_retryable_and_unknown_attempts(
        self,
    ) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        for status in (CapabilityStatus.FAILED_RETRYABLE, CapabilityStatus.UNKNOWN):
            app.adapter.submit_capability_result(
                capability_result_payload(
                    required,
                    result_id=f"init-{status.value.lower()}",
                    status=status,
                )
            )
            before = self.persisted_json()
            self.initialize_again()
            self.assertEqual(self.persisted_json(), before)
            app = self.capability_app()

    def test_repeated_init_preserves_completed_capability_history_and_mode_guard(
        self,
    ) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        completed = app.adapter.submit_capability_result(
            capability_result_payload(required)
        )
        before = self.persisted_json()

        self.initialize_again()

        self.assertEqual(self.persisted_json(), before)
        restored_app = self.capability_app()
        self.assertEqual(
            restored_app.adapter.query_request(required.request_id).result,
            completed,
        )
        with self.assertRaises(LocalIntegrationInitializationError):
            build_local_integration_app(self.data)

    def test_unknown_fields_and_mutation_fields_are_rejected(self) -> None:
        for field in ("unknown", "stateMutation", "event", "subjectStatePatch"):
            with self.subTest(field=field):
                app = self.capability_app()
                required = app.adapter.submit(
                    first_round_request(request_id=f"request-{field}")
                )
                assert isinstance(required, CapabilityRequiredEnvelope)
                payload = capability_result_payload(
                    required,
                    result_id=f"result-{field}",
                )
                payload[field] = {}
                with self.assertRaises(CapabilityValidationError):
                    app.adapter.submit_capability_result(payload)

    def test_retryable_and_unknown_remain_capability_required(self) -> None:
        for status in (CapabilityStatus.FAILED_RETRYABLE, CapabilityStatus.UNKNOWN):
            with self.subTest(status=status):
                request_id = f"request-{status.value.lower()}"
                app = self.capability_app()
                required = app.adapter.submit(first_round_request(request_id=request_id))
                assert isinstance(required, CapabilityRequiredEnvelope)
                response = app.adapter.submit_capability_result(
                    capability_result_payload(
                        required,
                        result_id=f"result-{status.value.lower()}",
                        status=status,
                    )
                )
                self.assertIsInstance(response, CapabilityRequiredEnvelope)
                self.assertEqual(
                    response.capability_request.capability_request_id,
                    required.capability_request.capability_request_id,
                )
                self.assertEqual(app.subject_states.load("subject-001").revision, 0)

    def test_terminal_statuses_return_capability_failed_without_state_change(self) -> None:
        for status in (
            CapabilityStatus.FAILED_TERMINAL,
            CapabilityStatus.CANCELLED,
            CapabilityStatus.EXPIRED,
        ):
            with self.subTest(status=status):
                request_id = f"request-{status.value.lower()}"
                app = self.capability_app()
                required = app.adapter.submit(first_round_request(request_id=request_id))
                assert isinstance(required, CapabilityRequiredEnvelope)
                response = app.adapter.submit_capability_result(
                    capability_result_payload(
                        required,
                        result_id=f"result-{status.value.lower()}",
                        status=status,
                    )
                )
                self.assertIsInstance(response, CapabilityFailedEnvelope)
                self.assertEqual(response.failure_status, status)
                self.assertEqual(app.subject_states.load("subject-001").revision, 0)

    def test_retryable_attempt_can_be_followed_by_success(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        app.adapter.submit_capability_result(
            capability_result_payload(
                required,
                result_id="retryable-result",
                status=CapabilityStatus.FAILED_RETRYABLE,
            )
        )
        completed = app.adapter.submit_capability_result(
            capability_result_payload(required, result_id="successful-result")
        )
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        self.assertEqual(
            len(app.ledger.list_capability_attempts(required.capability_request.capability_request_id)),
            2,
        )

    def test_second_success_for_same_request_is_rejected(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        app.adapter.submit_capability_result(capability_result_payload(required))
        with self.assertRaises(CapabilityConflictError):
            app.adapter.submit_capability_result(
                capability_result_payload(required, result_id="second-success")
            )

    def test_request_and_result_schema_reject_unknown_fields(self) -> None:
        app = self.capability_app()
        required = app.adapter.submit(first_round_request())
        assert isinstance(required, CapabilityRequiredEnvelope)
        request = required.capability_request.to_dict()
        request["unknown"] = True
        with self.assertRaises(CapabilityValidationError):
            DEFAULT_CAPABILITY_SCHEMA_REGISTRY.validate(
                CAPABILITY_REQUEST_SCHEMA_ID,
                request,
            )
        result = capability_result_payload(required)
        result["unknown"] = True
        with self.assertRaises(CapabilityValidationError):
            DEFAULT_CAPABILITY_SCHEMA_REGISTRY.validate(
                CAPABILITY_RESULT_SCHEMA_ID,
                result,
            )

    def test_default_deterministic_mode_retains_e4_behavior(self) -> None:
        capability_path = self.capability_app().ledger.capability_path
        capability_path.unlink()
        app = build_local_integration_app(self.data)
        result = app.adapter.submit(first_round_request("remember continuity test focus"))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        self.assertTrue(result.state_projection.changed)
        self.assertEqual(result.state_projection.current_revision, 1)
        initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=self.binding_fixture_hash,
            cycle_id="formal-cycle-001",
        )
        self.assertTrue(capability_path.is_file())
        self.assertIs(
            self.capability_app().thinking_mode,
            IntegrationThinkingMode.CAPABILITY,
        )


if __name__ == "__main__":
    unittest.main()
