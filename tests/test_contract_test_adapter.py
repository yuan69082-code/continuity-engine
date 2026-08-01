from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.errors import (
    ContractTestExecutionError,
    IntegrationLedgerConflictError,
    MachineContractCallError,
    StateAlreadyExistsError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import (
    calculate_projection_content_hash,
    calculate_state_hash,
)
from continuity_engine.domain.integration_results import (
    FirstRoundErrorCode,
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationOperationStage,
)
from continuity_engine.interfaces.api_service import APIService
from continuity_engine.interfaces.contract_test_adapter import ContractTestAdapter
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.contract_test_bootstrap import (
    FirstRoundContractBootstrap,
)
from continuity_engine.services.contract_test_doubles import (
    DeterministicContractReplyComposer,
    DeterministicMemoryInfluenceRecorder,
    DeterministicMemoryRetriever,
    DeterministicThinkingProvider,
    DeterministicTokenBudgetManager,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_content_hash,
    calculate_request_hash,
)
from continuity_engine.services.integration_contract_validation import (
    MachineContractValidator,
)
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.services.user_interaction_service import UserInteractionService
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_awakening_repository import (
    JsonAwakeningRepository,
)
from continuity_engine.storage.json_integration_repository import (
    JsonIntegrationResultLedger,
    JsonSubjectBindingFixtureRepository,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


FIXED_TIME = datetime(2026, 7, 30, 2, 0, tzinfo=timezone.utc)


def first_round_request(
    content: str = "hello",
    *,
    request_id: str = "request-001",
    expected_revision: int = 0,
) -> dict[str, object]:
    identity = {
        "userId": "user-001",
        "assistantId": "assistant-001",
        "subjectId": "subject-001",
        "bindingId": "binding-001",
        "bindingVersion": 1,
    }
    conversation = {
        "conversationId": "conversation-001",
        "messageId": "message-001",
        "messageVersionId": "message-version-001",
    }
    payload: dict[str, object] = {
        "contractVersion": "continuity-integration/v1.1",
        "schemaVersion": "continuity-interaction-request/first-round-v1",
        "requestId": request_id,
        "requestHash": "sha256:" + ("0" * 64),
        "requestType": "user_message",
        "identity": identity,
        "conversation": conversation,
        "expectedEngineRevision": expected_revision,
        "platformFactPackage": {
            "schemaVersion": "vio-platform-fact-package/first-round-v1",
            "facts": [
                {
                    "schemaVersion": (
                        "vio-platform-fact/message-version-first-round-v1"
                    ),
                    "factId": "fact-001",
                    "factType": "message_version",
                    "identity": dict(identity),
                    "conversationId": "conversation-001",
                    "messageId": "message-001",
                    "messageVersionId": "message-version-001",
                    "senderType": "user",
                    "content": content,
                    "contentHash": calculate_content_hash(content),
                    "createdAt": "2026-07-30T00:00:00Z",
                }
            ],
            "observationRefs": ["observation-001"],
        },
        "observations": [
            {
                "schemaVersion": (
                    "vio-platform-observation/message-created-first-round-v1"
                ),
                "observationId": "observation-001",
                "sourceEventId": "event-001",
                "observationType": "message_created",
                "identity": dict(identity),
                "occurredAt": "2026-07-30T00:00:00Z",
                "observedAt": "2026-07-30T00:00:00Z",
                "messageVersionRef": dict(conversation),
            }
        ],
        "constraints": {"purpose": "reply_to_user_message"},
        "createdAt": "2026-07-30T00:00:00Z",
    }
    payload["requestHash"] = calculate_request_hash(payload)
    return payload


def replace_identity(
    payload: dict[str, object],
    field: str,
    value: object,
) -> None:
    payload["identity"][field] = value  # type: ignore[index]
    payload["observations"][0]["identity"][field] = value  # type: ignore[index]
    payload["platformFactPackage"]["facts"][0]["identity"][field] = value  # type: ignore[index]
    payload["requestHash"] = calculate_request_hash(payload)


class CountingIdFactory:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.call_count = 0

    def __call__(self) -> str:
        self.call_count += 1
        return f"{self.prefix}-{self.call_count:03d}"


class FailOnceAt:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.triggered = False

    def __call__(self, stage, operation) -> None:
        if stage == self.stage and not self.triggered:
            self.triggered = True
            raise RuntimeError(f"simulated fault at {stage}")


class StaticBindingRepository:
    def __init__(self, fixture: SubjectBindingFixture) -> None:
        self.fixture = fixture

    def save_fixed(self, fixture, binding_fixture_hash) -> None:
        raise AssertionError("the static binding repository is read-only")

    def load_fixed(self):
        return self.fixture, calculate_binding_fixture_hash(self.fixture)


class RuntimeBundle:
    pass


class ContractTestAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = self._prepare()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _state_service(self) -> SubjectStateService:
        return SubjectStateService(
            JsonSubjectStateRepository(self.root / "subject-state"),
            clock=lambda: FIXED_TIME,
        )

    def _prepare(self):
        return FirstRoundContractBootstrap(
            self._state_service(),
            JsonSubjectBindingFixtureRepository(self.root),
            JsonAwakeningRepository(self.root),
            clock=lambda: FIXED_TIME,
        ).prepare()

    def _runtime(
        self,
        *,
        grant_update: bool = True,
        bindings=None,
        fault_injector=None,
    ) -> RuntimeBundle:
        bundle = RuntimeBundle()
        bundle.state = self._state_service()
        bundle.bindings = bindings or JsonSubjectBindingFixtureRepository(self.root)
        bundle.ledger = JsonIntegrationResultLedger(self.root)
        bundle.awakening_repository = JsonAwakeningRepository(self.root)
        bundle.memory_retriever = DeterministicMemoryRetriever()
        bundle.memory_recorder = DeterministicMemoryInfluenceRecorder()
        memory = MemoryService(
            bundle.memory_retriever,
            bundle.memory_recorder,
            clock=lambda: FIXED_TIME,
        )
        awakening = AwakeningService(
            bundle.state,
            memory,
            bundle.awakening_repository,
            clock=lambda: FIXED_TIME,
        )
        bundle.thinking_provider_ids = CountingIdFactory("thinking-result")
        bundle.thinking_provider = DeterministicThinkingProvider(
            result_id_factory=bundle.thinking_provider_ids
        )
        bundle.token_budgets = DeterministicTokenBudgetManager(
            clock=lambda: FIXED_TIME,
            usage_id_factory=CountingIdFactory("usage"),
        )
        bundle.thinking = ThinkingService(
            bundle.thinking_provider,
            bundle.token_budgets,
            bundle.state,
            JsonThinkingRepository(self.root),
            clock=lambda: FIXED_TIME,
        )
        grants = (
            [
                PermissionGrant(
                    permission="subject_state:update",
                    subject_id="subject-001",
                    valid_from=FIXED_TIME - timedelta(days=1),
                    scopes=["*"],
                )
            ]
            if grant_update
            else []
        )
        bundle.action_repository = InMemoryActionRepository()
        bundle.action = ActionService(
            InMemoryPermissionProvider(grants),
            bundle.action_repository,
        )
        bundle.reply = DeterministicContractReplyComposer()
        bundle.operation_ids = CountingIdFactory("operation-e3")
        bundle.response_ids = CountingIdFactory("response-e3")
        bundle.trace: list[str] = []
        bundle.adapter = ContractTestAdapter(
            validator=MachineContractValidator(),
            bindings=bundle.bindings,
            ledger=bundle.ledger,
            subject_states=bundle.state,
            awakening=awakening,
            perception=PerceptionService(),
            thinking=bundle.thinking,
            action=bundle.action,
            action_evolution=ActionEvolutionService(
                bundle.state,
                clock=lambda: FIXED_TIME,
            ),
            reply_composer=bundle.reply,
            cycle_id=self.fixture.cycle_id,
            available_permissions=(
                ["subject_state:update"] if grant_update else []
            ),
            clock=lambda: FIXED_TIME,
            operation_id_factory=bundle.operation_ids,
            response_id_factory=bundle.response_ids,
            trace=bundle.trace.append,
            fault_injector=fault_injector,
        )
        return bundle

    @staticmethod
    def _success(value) -> FirstRoundSuccessResult:
        if not isinstance(value, FirstRoundSuccessResult):
            raise AssertionError(f"expected success, got {value!r}")
        return value

    @staticmethod
    def _error(value) -> FirstRoundErrorEnvelope:
        if not isinstance(value, FirstRoundErrorEnvelope):
            raise AssertionError(f"expected error, got {value!r}")
        return value

    def test_bootstrap_creates_fresh_subject_and_fixed_binding(self) -> None:
        self.assertEqual(self.fixture.subject_id, "subject-001")
        self.assertEqual(self.fixture.initial_revision, 0)
        self.assertEqual(self._state_service().load("subject-001").revision, 0)
        fixture, declared_hash = JsonSubjectBindingFixtureRepository(
            self.root
        ).load_fixed()
        self.assertEqual(fixture, SubjectBindingFixture.first_round())
        self.assertEqual(
            declared_hash,
            calculate_binding_fixture_hash(fixture),
        )

    def test_repeated_bootstrap_does_not_overwrite_existing_subject(self) -> None:
        before = self._state_service().load("subject-001").to_dict()
        with self.assertRaises(StateAlreadyExistsError):
            self._prepare()
        self.assertEqual(self._state_service().load("subject-001").to_dict(), before)

    def test_hello_conformance_request_completes(self) -> None:
        result = self._success(self._runtime().adapter.submit(first_round_request()))
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.response.content)

    def test_hello_crosses_all_real_domain_boundaries(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        self.assertEqual(runtime.memory_retriever.call_count, 1)
        self.assertEqual(runtime.thinking_provider.call_count, 1)
        self.assertEqual(runtime.token_budgets.call_count, 1)
        self.assertEqual(runtime.reply.call_count, 1)
        self.assertEqual(len(runtime.action_repository.list_action_sessions("subject-001")), 1)

    def test_hello_does_not_create_event_or_advance_revision(self) -> None:
        runtime = self._runtime()
        result = self._success(runtime.adapter.submit(first_round_request()))
        self.assertEqual(runtime.state.load("subject-001").revision, 0)
        self.assertEqual(runtime.state.get_update_history("subject-001"), [])
        self.assertFalse(result.state_projection.changed)
        self.assertIsNone(result.state_projection.engine_update_id)

    def test_external_source_event_never_enters_internal_history(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        self.assertEqual(runtime.state.get_update_history("subject-001"), [])

    def test_thinking_reads_message_only_from_perception_result(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        self.assertEqual(runtime.thinking_provider.seen_contents, ["hello"])
        sessions = runtime.thinking.get_sessions("subject-001")
        self.assertEqual(
            sessions[0].observation.perceived_external_fact_ids,
            ["fact-001"],
        )

    def test_perception_remains_read_only_and_serializable(self) -> None:
        runtime = self._runtime()
        before = runtime.state.load("subject-001").to_dict()
        runtime.adapter.submit(first_round_request())
        after = runtime.state.load("subject-001").to_dict()
        self.assertEqual(before, after)
        sessions = runtime.thinking.get_sessions("subject-001")
        restored = type(sessions[0]).from_dict(sessions[0].to_dict())
        self.assertEqual(restored.to_dict(), sessions[0].to_dict())

    def test_deterministic_doubles_have_no_capability_protocol_output(self) -> None:
        runtime = self._runtime()
        result = self._success(runtime.adapter.submit(first_round_request()))
        serialized = json.dumps(result.to_dict())
        self.assertNotIn("CapabilityRequest", serialized)
        self.assertNotIn("capabilityRequestId", serialized)

    def test_same_process_replay_is_exact(self) -> None:
        runtime = self._runtime()
        request = first_round_request()
        first = self._success(runtime.adapter.submit(request))
        second = self._success(runtime.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(second, first)
        self.assertEqual(second.to_dict(), first.to_dict())

    def test_same_process_replay_skips_all_domain_services(self) -> None:
        runtime = self._runtime()
        request = first_round_request()
        runtime.adapter.submit(request)
        runtime.adapter.submit(copy.deepcopy(request))
        self.assertEqual(runtime.memory_retriever.call_count, 1)
        self.assertEqual(runtime.thinking_provider.call_count, 1)
        self.assertEqual(runtime.reply.call_count, 1)
        self.assertEqual(len(runtime.action_repository.list_action_sessions("subject-001")), 1)

    def test_replay_reuses_operation_response_and_completion_time(self) -> None:
        runtime = self._runtime()
        request = first_round_request()
        first = self._success(runtime.adapter.submit(request))
        second = self._success(runtime.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(second.operation_id, first.operation_id)
        self.assertEqual(second.response.response_id, first.response.response_id)
        self.assertEqual(second.completed_at, first.completed_at)
        self.assertEqual(runtime.operation_ids.call_count, 1)
        self.assertEqual(runtime.response_ids.call_count, 1)

    def test_restart_replays_exact_completed_result(self) -> None:
        request = first_round_request()
        first = self._success(self._runtime().adapter.submit(request))
        restarted = self._runtime()
        second = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(second.to_dict(), first.to_dict())

    def test_restart_replay_does_not_invoke_new_doubles_or_ids(self) -> None:
        request = first_round_request()
        self._runtime().adapter.submit(request)
        restarted = self._runtime()
        restarted.adapter.submit(copy.deepcopy(request))
        self.assertEqual(restarted.memory_retriever.call_count, 0)
        self.assertEqual(restarted.thinking_provider.call_count, 0)
        self.assertEqual(restarted.reply.call_count, 0)
        self.assertEqual(restarted.operation_ids.call_count, 0)
        self.assertEqual(restarted.response_ids.call_count, 0)

    def test_same_request_id_with_different_valid_hash_is_rejected(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        changed = first_round_request("different content")
        error = self._error(runtime.adapter.submit(changed))
        self.assertIs(error.error.code, FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED)

    def _assert_binding_error(self, field: str, value: object) -> FirstRoundErrorEnvelope:
        runtime = self._runtime()
        request = first_round_request()
        replace_identity(request, field, value)
        return self._error(runtime.adapter.submit(request))

    def test_wrong_user_id_is_binding_mismatch(self) -> None:
        self.assertIs(
            self._assert_binding_error("userId", "user-002").error.code,
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
        )

    def test_wrong_assistant_id_is_binding_mismatch(self) -> None:
        self.assertIs(
            self._assert_binding_error("assistantId", "assistant-002").error.code,
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
        )

    def test_wrong_subject_id_is_binding_mismatch(self) -> None:
        self.assertIs(
            self._assert_binding_error("subjectId", "subject-002").error.code,
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
        )

    def test_wrong_binding_id_is_binding_mismatch(self) -> None:
        self.assertIs(
            self._assert_binding_error("bindingId", "binding-002").error.code,
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
        )

    def test_wrong_binding_version_is_binding_mismatch(self) -> None:
        self.assertIs(
            self._assert_binding_error("bindingVersion", 2).error.code,
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH,
        )

    def test_non_active_binding_is_indistinguishable_mismatch(self) -> None:
        repository = StaticBindingRepository(
            replace(SubjectBindingFixture.first_round(), status="revoked")
        )
        error = self._error(
            self._runtime(bindings=repository).adapter.submit(first_round_request())
        )
        self.assertIs(error.error.code, FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH)

    def test_all_binding_failures_have_identical_non_leaking_envelope(self) -> None:
        envelopes = [
            self._assert_binding_error(field, value).to_dict()
            for field, value in (
                ("userId", "user-002"),
                ("assistantId", "assistant-002"),
                ("subjectId", "subject-002"),
                ("bindingId", "binding-002"),
                ("bindingVersion", 2),
            )
        ]
        errors = [item["error"] for item in envelopes]
        self.assertTrue(all(item == envelopes[0] for item in envelopes[1:]))
        self.assertTrue(all(item == errors[0] for item in errors[1:]))
        self.assertIsNone(errors[0]["currentEngineRevision"])

    def _advance_to_revision_one(self) -> None:
        result = self._success(
            self._runtime().adapter.submit(
                first_round_request(
                    "remember continuity test focus",
                    request_id="request-update",
                )
            )
        )
        self.assertEqual(result.state_projection.current_revision, 1)

    def test_expected_revision_less_than_current_conflicts(self) -> None:
        self._advance_to_revision_one()
        error = self._error(
            self._runtime().adapter.submit(
                first_round_request(request_id="request-old", expected_revision=0)
            )
        )
        self.assertIs(error.error.code, FirstRoundErrorCode.REVISION_CONFLICT)
        self.assertEqual(error.error.current_engine_revision, 1)

    def test_expected_revision_greater_than_current_conflicts(self) -> None:
        self._advance_to_revision_one()
        error = self._error(
            self._runtime().adapter.submit(
                first_round_request(request_id="request-future", expected_revision=2)
            )
        )
        self.assertIs(error.error.code, FirstRoundErrorCode.REVISION_CONFLICT)
        self.assertEqual(error.error.current_engine_revision, 1)

    def test_revision_is_disclosed_only_after_complete_binding_validation(self) -> None:
        self._advance_to_revision_one()
        valid = self._error(
            self._runtime().adapter.submit(
                first_round_request(request_id="request-old", expected_revision=0)
            )
        )
        invalid_request = first_round_request(
            request_id="request-wrong-binding",
            expected_revision=0,
        )
        replace_identity(invalid_request, "bindingId", "binding-002")
        invalid = self._error(self._runtime().adapter.submit(invalid_request))
        self.assertEqual(valid.error.current_engine_revision, 1)
        self.assertIsNone(invalid.error.current_engine_revision)

    def test_unknown_field_returns_schema_invalid(self) -> None:
        request = first_round_request()
        request["unknown"] = True
        error = self._error(self._runtime().adapter.submit(request))
        self.assertIs(error.error.code, FirstRoundErrorCode.SCHEMA_INVALID)

    def test_forbidden_state_write_field_returns_schema_invalid(self) -> None:
        request = first_round_request()
        request["mutation"] = {"fieldPath": "continuity.current_focus"}
        error = self._error(self._runtime().adapter.submit(request))
        self.assertIs(error.error.code, FirstRoundErrorCode.SCHEMA_INVALID)

    def test_duplicate_message_body_returns_schema_invalid(self) -> None:
        request = first_round_request()
        request["observations"][0]["content"] = "hello"  # type: ignore[index]
        error = self._error(self._runtime().adapter.submit(request))
        self.assertIs(error.error.code, FirstRoundErrorCode.SCHEMA_INVALID)

    def test_cross_reference_mismatch_returns_schema_invalid(self) -> None:
        request = first_round_request()
        request["platformFactPackage"]["observationRefs"] = ["wrong"]  # type: ignore[index]
        request["requestHash"] = calculate_request_hash(request)
        error = self._error(self._runtime().adapter.submit(request))
        self.assertIs(error.error.code, FirstRoundErrorCode.SCHEMA_INVALID)

    def test_request_hash_mismatch_returns_schema_invalid(self) -> None:
        request = first_round_request()
        request["requestHash"] = "sha256:" + ("f" * 64)
        error = self._error(self._runtime().adapter.submit(request))
        self.assertIs(error.error.code, FirstRoundErrorCode.SCHEMA_INVALID)

    def test_missing_safe_request_id_is_local_call_error(self) -> None:
        request = first_round_request()
        del request["requestId"]
        with self.assertRaises(MachineContractCallError):
            self._runtime().adapter.submit(request)

    def test_validation_order_is_fixed_before_domain_execution(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        self.assertEqual(
            runtime.adapter.last_call_log[:5],
            ["schema", "binding", "ledger", "revision", "operation"],
        )
        self.assertEqual(
            runtime.adapter.last_call_log[5:],
            [
                "wake",
                "perception",
                "thinking",
                "action",
                "result",
                "completed",
            ],
        )

    def test_update_fixture_runs_thinking_action_event_and_evolution(self) -> None:
        runtime = self._runtime()
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        sessions = runtime.action_repository.list_action_sessions("subject-001")
        history = runtime.state.get_update_history("subject-001")
        self.assertEqual(sessions[0].final_decision.selected_action.action_type.value, "UPDATE_STATE")
        self.assertTrue(sessions[0].final_decision.approved)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].event.source, "action_engine")
        self.assertTrue(result.state_projection.changed)

    def test_update_fixture_advances_revision_exactly_once(self) -> None:
        runtime = self._runtime()
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        self.assertEqual(result.state_projection.previous_revision, 0)
        self.assertEqual(result.state_projection.current_revision, 1)
        self.assertEqual(runtime.state.load("subject-001").revision, 1)

    def test_engine_update_id_is_state_update_record_id(self) -> None:
        runtime = self._runtime()
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        update = runtime.state.get_update_history("subject-001")[0]
        self.assertEqual(result.state_projection.engine_update_id, update.update_id)

    def test_projection_hashes_match_authoritative_final_state(self) -> None:
        runtime = self._runtime()
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        state = runtime.state.load("subject-001")
        self.assertEqual(
            result.state_projection.snapshot.state_hash,
            calculate_state_hash(state),
        )
        self.assertEqual(
            result.state_projection.content_hash,
            calculate_projection_content_hash(result.state_projection.snapshot),
        )

    def test_completed_result_keeps_e2_projection_uniqueness(self) -> None:
        runtime = self._runtime()
        original = self._success(runtime.adapter.submit(first_round_request()))
        conflicting_snapshot = replace(
            original.state_projection.snapshot,
            state_hash="sha256:" + ("f" * 64),
        )
        conflicting_projection = replace(
            original.state_projection,
            snapshot=conflicting_snapshot,
            content_hash=calculate_projection_content_hash(conflicting_snapshot),
        )
        second_request = first_round_request(request_id="request-projection-conflict")
        conflicting_result = replace(
            original,
            request_id="request-projection-conflict",
            request_hash=str(second_request["requestHash"]),
            operation_id="operation-projection-conflict",
            response=replace(
                original.response,
                response_id="response-projection-conflict",
            ),
            state_projection=conflicting_projection,
        )

        with self.assertRaises(IntegrationLedgerConflictError):
            runtime.ledger.save_completed(conflicting_result)

    def test_missing_update_permission_blocks_action_and_revision(self) -> None:
        runtime = self._runtime(grant_update=False)
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        action = runtime.action_repository.list_action_sessions("subject-001")[0]
        self.assertFalse(action.final_decision.approved)
        self.assertFalse(result.state_projection.changed)
        self.assertEqual(runtime.state.load("subject-001").revision, 0)

    def test_unapproved_action_cannot_create_mutation_event(self) -> None:
        runtime = self._runtime(grant_update=False)
        runtime.adapter.submit(first_round_request("remember continuity test focus"))
        self.assertEqual(runtime.state.get_update_history("subject-001"), [])

    def test_completed_changed_replay_does_not_create_second_event(self) -> None:
        runtime = self._runtime()
        request = first_round_request("remember continuity test focus")
        first = self._success(runtime.adapter.submit(request))
        second = self._success(runtime.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(second, first)
        self.assertEqual(len(runtime.state.get_update_history("subject-001")), 1)
        self.assertEqual(runtime.state.load("subject-001").revision, 1)

    def test_restart_changed_replay_does_not_advance_again(self) -> None:
        request = first_round_request("remember continuity test focus")
        first = self._success(self._runtime().adapter.submit(request))
        restarted = self._runtime()
        second = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(second, first)
        self.assertEqual(restarted.state.load("subject-001").revision, 1)
        self.assertEqual(len(restarted.state.get_update_history("subject-001")), 1)

    def test_old_completed_result_keeps_original_projection_after_later_update(self) -> None:
        runtime = self._runtime()
        old_request = first_round_request(request_id="request-old")
        old = self._success(runtime.adapter.submit(old_request))
        runtime.adapter.submit(
            first_round_request(
                "remember continuity test focus",
                request_id="request-update",
            )
        )
        replay = self._success(runtime.adapter.submit(copy.deepcopy(old_request)))
        self.assertEqual(replay, old)
        self.assertEqual(replay.state_projection.current_revision, 0)
        self.assertEqual(runtime.state.load("subject-001").revision, 1)

    def test_operation_reservation_fault_recovers_with_same_operation(self) -> None:
        fault = FailOnceAt("after_operation_reserved")
        runtime = self._runtime(fault_injector=fault)
        request = first_round_request()
        with self.assertRaises(ContractTestExecutionError):
            runtime.adapter.submit(request)
        reserved = runtime.ledger.load_operation("request-001")
        self.assertIs(reserved.stage, IntegrationOperationStage.RESERVED)
        restarted = self._runtime()
        result = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(result.operation_id, reserved.operation_id)

    def test_domain_checkpoint_fault_recovers_without_rerunning_domain(self) -> None:
        fault = FailOnceAt("after_domain_completed")
        runtime = self._runtime(fault_injector=fault)
        request = first_round_request()
        with self.assertRaises(ContractTestExecutionError):
            runtime.adapter.submit(request)
        checkpoint = runtime.ledger.load_operation("request-001")
        self.assertIs(checkpoint.stage, IntegrationOperationStage.DOMAIN_COMPLETED)
        restarted = self._runtime()
        result = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(result.response.response_id, checkpoint.domain.response_id)
        self.assertEqual(restarted.memory_retriever.call_count, 0)
        self.assertEqual(restarted.thinking_provider.call_count, 0)
        self.assertEqual(restarted.reply.call_count, 0)

    def test_evolution_commit_fault_recovers_without_second_event(self) -> None:
        fault = FailOnceAt("after_evolution_committed")
        runtime = self._runtime(fault_injector=fault)
        request = first_round_request("remember continuity test focus")
        with self.assertRaises(ContractTestExecutionError):
            runtime.adapter.submit(request)
        self.assertEqual(runtime.state.load("subject-001").revision, 1)
        self.assertEqual(len(runtime.state.get_update_history("subject-001")), 1)
        restarted = self._runtime()
        result = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(result.state_projection.current_revision, 1)
        self.assertEqual(len(restarted.state.get_update_history("subject-001")), 1)

    def test_completed_result_save_fault_replays_ledger_result(self) -> None:
        fault = FailOnceAt("after_completed_result_saved")
        runtime = self._runtime(fault_injector=fault)
        request = first_round_request()
        with self.assertRaises(ContractTestExecutionError):
            runtime.adapter.submit(request)
        persisted = runtime.ledger.lookup(
            request["requestId"], request["requestHash"]
        ).result
        restarted = self._runtime()
        replay = self._success(restarted.adapter.submit(copy.deepcopy(request)))
        self.assertEqual(replay, persisted)
        self.assertEqual(restarted.thinking_provider.call_count, 0)
        self.assertIs(
            restarted.ledger.load_operation("request-001").stage,
            IntegrationOperationStage.COMPLETED,
        )

    def test_normal_completion_marks_internal_operation_completed(self) -> None:
        runtime = self._runtime()
        runtime.adapter.submit(first_round_request())
        operation = runtime.ledger.load_operation("request-001")
        self.assertIs(operation.stage, IntegrationOperationStage.COMPLETED)

    def test_stable_internal_event_links_request_and_operation_not_source_event(self) -> None:
        runtime = self._runtime()
        result = self._success(
            runtime.adapter.submit(
                first_round_request("remember continuity test focus")
            )
        )
        event = runtime.state.get_update_history("subject-001")[0].event
        self.assertEqual(event.metadata["integration_request_id"], "request-001")
        self.assertEqual(event.metadata["integration_operation_id"], result.operation_id)
        self.assertNotEqual(event.event_id, "event-001")
        self.assertNotIn("event-001", json.dumps(event.to_dict()))

    def test_existing_api_http_and_user_interaction_entries_are_not_called(self) -> None:
        with (
            patch.object(
                APIService,
                "submit_message",
                side_effect=AssertionError("APIService must not be used"),
            ),
            patch.object(
                UserInteractionService,
                "handle_message",
                side_effect=AssertionError("UserInteractionService must not be used"),
            ),
            patch(
                "continuity_engine.interfaces.http_server.create_frontend_server",
                side_effect=AssertionError("local HTTP must not be used"),
            ),
        ):
            result = self._runtime().adapter.submit(first_round_request())
        self.assertIsInstance(result, FirstRoundSuccessResult)

    def test_contract_adapter_performs_no_network_access(self) -> None:
        with patch(
            "socket.create_connection",
            side_effect=AssertionError("network access is forbidden"),
        ):
            result = self._runtime().adapter.submit(first_round_request())
        self.assertIsInstance(result, FirstRoundSuccessResult)


if __name__ == "__main__":
    unittest.main()
