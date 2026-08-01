from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import rfc8785

from continuity_engine.domain.errors import (
    IntegrationLedgerConflictError,
    IntegrationPersistenceError,
    IntegrationRecordNotFoundError,
    MachineContractValidationError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    FirstRoundErrorCode,
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    LedgerLookupStatus,
    SubjectStateProjection,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_projection_content_hash,
    calculate_state_hash,
)
from continuity_engine.services.integration_result_factory import (
    FirstRoundResultFactory,
)
from continuity_engine.storage.json_integration_repository import (
    JsonIntegrationResultLedger,
    JsonSubjectBindingFixtureRepository,
)


BINDING_HASH = (
    "sha256:c75b72194c0158a549f3fb30f04a5147ea11a4e777cb1a9cc1a54da6b93359f6"
)
FIXED_TIME = datetime(2026, 7, 30, 1, 2, 3, tzinfo=timezone.utc)


def hash_value(character: str) -> str:
    return "sha256:" + (character * 64)


def subject_state(*, revision: int = 0, note: str = "持续存在") -> SubjectState:
    state = SubjectState.create("subject-001", now=FIXED_TIME)
    state.revision = revision
    state.identity.self_concept = note
    return state


def completed_result(
    *,
    request_id: str = "request-001",
    request_hash: str = hash_value("1"),
    operation_id: str = "operation-001",
    response_id: str = "response-001",
    response_content: str = "我在。",
    revision: int = 0,
    previous_revision: int | None = None,
    engine_update_id: str | None = None,
    note: str = "持续存在",
) -> FirstRoundSuccessResult:
    state = subject_state(revision=revision, note=note)
    factory = FirstRoundResultFactory(
        clock=lambda: FIXED_TIME,
        operation_id_factory=lambda: operation_id,
        response_id_factory=lambda: response_id,
    )
    return factory.create_completed_result(
        request_id=request_id,
        request_hash=request_hash,
        binding=SubjectBindingFixture.first_round(),
        response_content=response_content,
        subject_state=state,
        previous_revision=(revision if previous_revision is None else previous_revision),
        engine_update_id=engine_update_id,
        consumed_observation_ids=("observation-001",),
    )


class FirstRoundResultModelTests(unittest.TestCase):
    def test_success_result_has_exact_fields_and_round_trips(self) -> None:
        result = completed_result()
        payload = result.to_dict()

        self.assertEqual(
            set(payload),
            {
                "contractVersion",
                "requestId",
                "requestHash",
                "operationId",
                "status",
                "subjectId",
                "bindingId",
                "bindingVersion",
                "response",
                "stateProjection",
                "consumedObservationIds",
                "completedAt",
            },
        )
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(FirstRoundSuccessResult.from_dict(payload), result)

    def test_success_result_is_immutable(self) -> None:
        result = completed_result()
        with self.assertRaises(FrozenInstanceError):
            result.request_id = "changed"  # type: ignore[misc]

    def test_success_result_rejects_unknown_missing_or_non_completed_fields(self) -> None:
        payload = completed_result().to_dict()
        variants = []
        unknown = copy.deepcopy(payload)
        unknown["extra"] = True
        variants.append(unknown)
        missing = copy.deepcopy(payload)
        del missing["response"]
        variants.append(missing)
        pending = copy.deepcopy(payload)
        pending["status"] = "pending"
        variants.append(pending)
        for candidate in variants:
            with self.subTest(candidate=candidate):
                with self.assertRaises(MachineContractValidationError):
                    FirstRoundSuccessResult.from_dict(candidate)

    def test_all_four_error_envelopes_have_exact_fixed_values(self) -> None:
        expected = {
            FirstRoundErrorCode.SCHEMA_INVALID: (
                "Request schema is invalid.",
                "never",
                None,
            ),
            FirstRoundErrorCode.SUBJECT_BINDING_MISMATCH: (
                "Subject binding does not match.",
                "never",
                None,
            ),
            FirstRoundErrorCode.REVISION_CONFLICT: (
                "Engine revision does not match.",
                "reassemble",
                7,
            ),
            FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED: (
                "requestId is already bound to a different requestHash.",
                "never",
                None,
            ),
        }
        for code, (message, retry_class, revision) in expected.items():
            with self.subTest(code=code):
                envelope = FirstRoundErrorEnvelope.create(
                    "request-001",
                    code,
                    current_engine_revision=revision,
                )
                payload = envelope.to_dict()
                self.assertEqual(
                    set(payload),
                    {"contractVersion", "requestId", "operationId", "status", "error"},
                )
                self.assertIsNone(payload["operationId"])
                self.assertEqual(payload["status"], "failed_terminal")
                self.assertEqual(payload["error"]["message"], message)  # type: ignore[index]
                self.assertEqual(payload["error"]["retryClass"], retry_class)  # type: ignore[index]
                self.assertEqual(payload["error"]["currentEngineRevision"], revision)  # type: ignore[index]
                self.assertIsNone(payload["error"]["currentBindingVersion"])  # type: ignore[index]
                self.assertEqual(FirstRoundErrorEnvelope.from_dict(payload), envelope)

    def test_idempotency_conflict_alias_is_rejected(self) -> None:
        payload = FirstRoundErrorEnvelope.create(
            "request-001",
            FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED,
        ).to_dict()
        payload["error"]["code"] = "IDEMPOTENCY_CONFLICT"  # type: ignore[index]
        with self.assertRaises(MachineContractValidationError):
            FirstRoundErrorEnvelope.from_dict(payload)

    def test_error_envelope_rejects_non_null_operation_and_unknown_fields(self) -> None:
        payload = FirstRoundErrorEnvelope.create(
            "request-001",
            FirstRoundErrorCode.SCHEMA_INVALID,
        ).to_dict()
        non_null = copy.deepcopy(payload)
        non_null["operationId"] = "operation-001"
        unknown = copy.deepcopy(payload)
        unknown["debug"] = "details"
        for candidate in (non_null, unknown):
            with self.subTest(candidate=candidate):
                with self.assertRaises(MachineContractValidationError):
                    FirstRoundErrorEnvelope.from_dict(candidate)

    def test_unchanged_projection_has_exact_minimal_shape(self) -> None:
        projection = completed_result().state_projection
        payload = projection.to_dict()
        self.assertFalse(projection.changed)
        self.assertEqual(projection.previous_revision, projection.current_revision)
        self.assertIsNone(projection.engine_update_id)
        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "subjectId",
                "bindingId",
                "bindingVersion",
                "previousRevision",
                "currentRevision",
                "changed",
                "engineUpdateId",
                "snapshot",
                "contentHash",
            },
        )

    def test_changed_projection_advances_once_and_requires_update_id(self) -> None:
        projection = completed_result(
            revision=1,
            previous_revision=0,
            engine_update_id="update-001",
        ).state_projection
        self.assertTrue(projection.changed)
        self.assertEqual(projection.current_revision, 1)
        self.assertEqual(projection.snapshot.revision, 1)
        self.assertEqual(projection.engine_update_id, "update-001")

    def test_illegal_projection_invariant_combinations_are_rejected(self) -> None:
        unchanged = completed_result().state_projection.to_dict()
        changed = completed_result(
            revision=1,
            previous_revision=0,
            engine_update_id="update-001",
        ).state_projection.to_dict()
        invalid = []
        current_without_snapshot = copy.deepcopy(unchanged)
        current_without_snapshot["currentRevision"] = 1
        invalid.append(current_without_snapshot)
        unchanged_with_update = copy.deepcopy(unchanged)
        unchanged_with_update["engineUpdateId"] = "update-001"
        invalid.append(unchanged_with_update)
        skipped_revision = copy.deepcopy(changed)
        skipped_revision["currentRevision"] = 2
        skipped_revision["snapshot"]["revision"] = 2  # type: ignore[index]
        invalid.append(skipped_revision)
        changed_without_update = copy.deepcopy(changed)
        changed_without_update["engineUpdateId"] = None
        invalid.append(changed_without_update)
        mismatched_snapshot = copy.deepcopy(changed)
        mismatched_snapshot["snapshot"]["revision"] = 0  # type: ignore[index]
        invalid.append(mismatched_snapshot)
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(MachineContractValidationError):
                    SubjectStateProjection.from_dict(candidate)

    def test_snapshot_rejects_unknown_fields_and_full_subject_state(self) -> None:
        payload = completed_result().state_projection.to_dict()
        for field, value in (("identity", {}), ("delta", {}), ("unknown", True)):
            with self.subTest(field=field):
                candidate = copy.deepcopy(payload)
                candidate["snapshot"][field] = value  # type: ignore[index]
                with self.assertRaises(MachineContractValidationError):
                    SubjectStateProjection.from_dict(candidate)

    def test_state_hash_matches_independent_rfc8785_calculation(self) -> None:
        state = subject_state()
        independent = "sha256:" + hashlib.sha256(
            rfc8785.dumps(state.to_dict())
        ).hexdigest()
        self.assertEqual(calculate_state_hash(state), independent)

    def test_content_hash_matches_independent_minimal_snapshot_calculation(self) -> None:
        projection = completed_result().state_projection
        independent = "sha256:" + hashlib.sha256(
            rfc8785.dumps(projection.snapshot.to_dict())
        ).hexdigest()
        self.assertEqual(projection.content_hash, independent)
        with self.assertRaises(MachineContractValidationError):
            replace(projection, content_hash=hash_value("0"))

    def test_unicode_and_object_field_order_do_not_change_projection_hashes(self) -> None:
        state = subject_state(note="长期连续性 🌱")
        reordered_state = dict(reversed(list(state.to_dict().items())))
        self.assertEqual(calculate_state_hash(state), calculate_state_hash(reordered_state))

        snapshot = completed_result(note="长期连续性 🌱").state_projection.snapshot
        reordered_snapshot = dict(reversed(list(snapshot.to_dict().items())))
        self.assertEqual(
            calculate_projection_content_hash(snapshot),
            calculate_projection_content_hash(reordered_snapshot),
        )


class FixedBindingPersistenceTests(unittest.TestCase):
    def test_fixed_binding_persists_and_recovers_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            fixture = SubjectBindingFixture.first_round()
            repository.save_fixed(fixture, BINDING_HASH)

            restored = JsonSubjectBindingFixtureRepository(directory).load_fixed()
            self.assertEqual(restored, (fixture, BINDING_HASH))

    def test_missing_binding_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(IntegrationRecordNotFoundError):
                JsonSubjectBindingFixtureRepository(directory).load_fixed()

    def test_changed_binding_and_incorrect_declared_hash_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            fixture = SubjectBindingFixture.first_round()
            changed = replace(fixture, subject_id="subject-002")
            with self.assertRaises(IntegrationPersistenceError):
                repository.save_fixed(
                    changed,
                    calculate_binding_fixture_hash(changed),
                )
            with self.assertRaises(IntegrationPersistenceError):
                repository.save_fixed(fixture, hash_value("0"))

    def test_tampered_binding_fixture_is_rejected_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            repository.save_fixed(SubjectBindingFixture.first_round(), BINDING_HASH)
            document = json.loads(repository.path.read_text(encoding="utf-8"))
            document["fixture"]["assistantId"] = "assistant-002"
            repository.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                repository.load_fixed()

    def test_tampered_binding_hash_is_rejected_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            repository.save_fixed(SubjectBindingFixture.first_round(), BINDING_HASH)
            document = json.loads(repository.path.read_text(encoding="utf-8"))
            document["bindingFixtureHash"] = hash_value("0")
            repository.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                repository.load_fixed()

    def test_corrupt_binding_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            repository.path.parent.mkdir(parents=True)
            repository.path.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                repository.load_fixed()

    def test_unsupported_binding_persistence_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectBindingFixtureRepository(directory)
            repository.save_fixed(SubjectBindingFixture.first_round(), BINDING_HASH)
            document = json.loads(repository.path.read_text(encoding="utf-8"))
            document["bindingPersistenceFormatVersion"] = 2
            repository.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                repository.load_fixed()


class IntegrationResultLedgerTests(unittest.TestCase):
    def test_completed_result_replays_exactly_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = completed_result()
            JsonIntegrationResultLedger(directory).save_completed(result)

            lookup = JsonIntegrationResultLedger(directory).lookup(
                result.request_id,
                result.request_hash,
            )
            self.assertIs(lookup.status, LedgerLookupStatus.COMPLETED)
            self.assertEqual(lookup.result, result)
            self.assertEqual(lookup.result.to_dict(), result.to_dict())  # type: ignore[union-attr]

    def test_lookup_distinguishes_not_found_completed_and_hash_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            result = completed_result()
            self.assertIs(
                ledger.lookup("request-missing", hash_value("2")).status,
                LedgerLookupStatus.NOT_FOUND,
            )
            ledger.save_completed(result)
            self.assertIs(
                ledger.lookup(result.request_id, result.request_hash).status,
                LedgerLookupStatus.COMPLETED,
            )
            self.assertIs(
                ledger.lookup(result.request_id, hash_value("2")).status,
                LedgerLookupStatus.HASH_CONFLICT,
            )

    def test_same_request_and_hash_replay_creates_no_new_ids_or_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = completed_result()
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(result)
            clock = Mock(side_effect=AssertionError("clock must not be called"))
            operation_ids = Mock(side_effect=AssertionError("ID factory must not be called"))
            response_ids = Mock(side_effect=AssertionError("ID factory must not be called"))
            FirstRoundResultFactory(
                clock=clock,
                operation_id_factory=operation_ids,
                response_id_factory=response_ids,
            )

            replay = JsonIntegrationResultLedger(directory).lookup(
                result.request_id,
                result.request_hash,
            )
            self.assertEqual(replay.result, result)
            clock.assert_not_called()
            operation_ids.assert_not_called()
            response_ids.assert_not_called()

    def test_completed_request_id_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            replacement = completed_result(
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
            )
            with self.assertRaises(IntegrationLedgerConflictError):
                ledger.save_completed(replacement)

    def test_subject_revision_projection_is_unique(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            conflicting = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
                note="不同的主体状态",
            )
            with self.assertRaises(IntegrationLedgerConflictError):
                ledger.save_completed(conflicting)

    def test_multiple_unchanged_requests_can_reuse_same_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            first = completed_result()
            second = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
                response_content="仍然在。",
            )
            ledger.save_completed(first)
            ledger.save_completed(second)
            self.assertEqual(
                ledger.lookup(second.request_id, second.request_hash).result,
                second,
            )

    def test_unchanged_request_can_reference_snapshot_created_by_prior_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            changed = completed_result(
                revision=1,
                previous_revision=0,
                engine_update_id="update-001",
            )
            unchanged = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
                revision=1,
                previous_revision=1,
            )
            ledger.save_completed(changed)
            ledger.save_completed(unchanged)
            self.assertEqual(
                changed.state_projection.snapshot,
                unchanged.state_projection.snapshot,
            )

    def test_same_revision_with_different_content_or_state_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            candidate = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
            )
            changed_snapshot = replace(
                candidate.state_projection.snapshot,
                state_hash=hash_value("9"),
            )
            changed_projection = replace(
                candidate.state_projection,
                snapshot=changed_snapshot,
                content_hash=calculate_projection_content_hash(changed_snapshot),
            )
            candidate = replace(candidate, state_projection=changed_projection)
            with self.assertRaises(IntegrationLedgerConflictError):
                ledger.save_completed(candidate)

    def test_non_null_engine_update_id_must_be_unique(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            first = completed_result(
                revision=1,
                previous_revision=0,
                engine_update_id="update-001",
            )
            second = replace(
                first,
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response=replace(first.response, response_id="response-002"),
            )
            ledger.save_completed(first)
            with self.assertRaises(IntegrationLedgerConflictError):
                ledger.save_completed(second)

    def test_null_engine_update_id_has_no_global_uniqueness_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            first = completed_result()
            second = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
            )
            ledger.save_completed(first)
            ledger.save_completed(second)
            self.assertIsNone(second.state_projection.engine_update_id)

    def test_unsupported_ledger_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            document = json.loads(ledger.path.read_text(encoding="utf-8"))
            document["ledgerPersistenceFormatVersion"] = 2
            ledger.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                ledger.lookup("request-001", hash_value("1"))

    def test_corrupt_ledger_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.path.parent.mkdir(parents=True)
            ledger.path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                ledger.lookup("request-001", hash_value("1"))

    def test_missing_ledger_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.path.parent.mkdir(parents=True)
            ledger.path.write_text(
                json.dumps({"ledgerPersistenceFormatVersion": 1}),
                encoding="utf-8",
            )
            with self.assertRaises(IntegrationPersistenceError):
                ledger.lookup("request-001", hash_value("1"))

    def test_projection_hash_mismatch_is_rejected_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            document = json.loads(ledger.path.read_text(encoding="utf-8"))
            document["results"][0]["stateProjection"]["contentHash"] = hash_value("0")
            ledger.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                ledger.lookup("request-001", hash_value("1"))

    def test_half_completed_record_is_not_treated_as_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            ledger.save_completed(completed_result())
            document = json.loads(ledger.path.read_text(encoding="utf-8"))
            document["results"][0]["status"] = "processing"
            ledger.path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(IntegrationPersistenceError):
                ledger.lookup("request-001", hash_value("1"))

    def test_write_failure_leaves_previous_valid_ledger_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonIntegrationResultLedger(directory)
            first = completed_result()
            ledger.save_completed(first)
            second = completed_result(
                request_id="request-002",
                request_hash=hash_value("2"),
                operation_id="operation-002",
                response_id="response-002",
            )
            with patch(
                "continuity_engine.storage.json_integration_repository.os.replace",
                side_effect=OSError("simulated replace failure"),
            ):
                with self.assertRaises(IntegrationPersistenceError):
                    ledger.save_completed(second)

            restarted = JsonIntegrationResultLedger(directory)
            self.assertEqual(
                restarted.lookup(first.request_id, first.request_hash).result,
                first,
            )
            self.assertIs(
                restarted.lookup(second.request_id, second.request_hash).status,
                LedgerLookupStatus.NOT_FOUND,
            )


if __name__ == "__main__":
    unittest.main()
