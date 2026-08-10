from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from continuity_engine.domain.errors import (
    CapabilityConflictError,
    CapabilityValidationError,
    IntegrationLedgerConflictError,
    IntegrationPersistenceError,
    IntegrationRecordNotFoundError,
    MachineContractValidationError,
)
from continuity_engine.domain.capability import (
    CapabilityAttempt,
    CapabilityRequest,
    CapabilityResult,
    CapabilityStatus,
    calculate_capability_result_hash,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import (
    HASH_PATTERN,
    calculate_binding_fixture_hash,
    calculate_projection_content_hash,
    verify_declared_hash,
)
from continuity_engine.domain.integration_results import (
    FirstRoundSuccessResult,
    IntegrationOperationRecord,
    IntegrationOperationStage,
    LedgerLookupResult,
    LedgerLookupStatus,
    SubjectStateProjection,
)


BINDING_PERSISTENCE_FORMAT_VERSION = 1
LEDGER_PERSISTENCE_FORMAT_VERSION = 1
OPERATION_JOURNAL_FORMAT_VERSION = 3
CAPABILITY_LEDGER_FORMAT_VERSION = 1
_BINDING_FILE_NAME = "subject-binding.first-round-v1.json"
_LEDGER_FILE_NAME = "result-ledger.first-round-v1.json"
_OPERATION_FILE_NAME = "operation-journal.first-round-v1.json"
_CAPABILITY_FILE_NAME = "capability-ledger.v1.json"


def _strict_document(
    value: Any,
    *,
    name: str,
    expected_keys: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntegrationPersistenceError(f"{name} must contain a JSON object")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unknown = sorted(actual_keys - expected_keys)
        details: list[str] = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise IntegrationPersistenceError(
            f"{name} has an invalid shape ({'; '.join(details)})"
        )
    return value


def _read_json(path: Path, *, name: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrationPersistenceError(f"cannot read valid {name}: {path}") from exc


def _atomic_write_json(path: Path, value: dict[str, Any], *, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError) as exc:
        raise IntegrationPersistenceError(f"cannot atomically save {name}: {path}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


class JsonSubjectBindingFixtureRepository:
    """Local persistence for the one immutable first-round binding fixture."""

    def __init__(self, root: str | Path) -> None:
        self._path = Path(root) / "integration" / _BINDING_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def save_fixed(
        self,
        fixture: SubjectBindingFixture,
        binding_fixture_hash: str,
    ) -> None:
        expected = SubjectBindingFixture.first_round()
        if fixture != expected:
            raise IntegrationPersistenceError(
                "only the exact fixed first-round SubjectBinding may be persisted"
            )
        try:
            verify_declared_hash(
                declared=binding_fixture_hash,
                calculated=calculate_binding_fixture_hash(fixture),
                field_name="bindingFixtureHash",
            )
        except MachineContractValidationError as exc:
            raise IntegrationPersistenceError(str(exc)) from exc

        if self._path.exists():
            persisted_fixture, persisted_hash = self.load_fixed()
            if persisted_fixture == fixture and persisted_hash == binding_fixture_hash:
                return
            raise IntegrationLedgerConflictError(
                "the persisted first-round SubjectBinding is immutable"
            )

        _atomic_write_json(
            self._path,
            {
                "bindingPersistenceFormatVersion": BINDING_PERSISTENCE_FORMAT_VERSION,
                "fixture": fixture.to_dict(),
                "bindingFixtureHash": binding_fixture_hash,
            },
            name="first-round SubjectBinding",
        )

    def load_fixed(self) -> tuple[SubjectBindingFixture, str]:
        try:
            raw = _read_json(self._path, name="first-round SubjectBinding")
        except FileNotFoundError as exc:
            raise IntegrationRecordNotFoundError(
                "the fixed first-round SubjectBinding has not been persisted"
            ) from exc
        document = _strict_document(
            raw,
            name="first-round SubjectBinding document",
            expected_keys={
                "bindingPersistenceFormatVersion",
                "fixture",
                "bindingFixtureHash",
            },
        )
        if (
            document["bindingPersistenceFormatVersion"]
            != BINDING_PERSISTENCE_FORMAT_VERSION
        ):
            raise IntegrationPersistenceError(
                "unsupported first-round SubjectBinding persistence format version"
            )
        expected = SubjectBindingFixture.first_round()
        fixture_value = document["fixture"]
        if fixture_value != expected.to_dict():
            raise IntegrationPersistenceError(
                "persisted SubjectBinding does not match the fixed first-round fixture"
            )
        binding_hash = document["bindingFixtureHash"]
        try:
            verify_declared_hash(
                declared=binding_hash,
                calculated=calculate_binding_fixture_hash(fixture_value),
                field_name="bindingFixtureHash",
            )
        except MachineContractValidationError as exc:
            raise IntegrationPersistenceError(str(exc)) from exc
        return expected, binding_hash


class JsonIntegrationResultLedger:
    """Atomic-per-file result ledger with a recoverable operation journal."""

    def __init__(self, root: str | Path) -> None:
        self._path = Path(root) / "integration" / _LEDGER_FILE_NAME
        self._operation_path = Path(root) / "integration" / _OPERATION_FILE_NAME
        self._capability_path = Path(root) / "integration" / _CAPABILITY_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    @property
    def operation_path(self) -> Path:
        return self._operation_path

    @property
    def capability_path(self) -> Path:
        return self._capability_path

    def lookup(self, request_id: str, request_hash: str) -> LedgerLookupResult:
        if not isinstance(request_id, str) or not request_id.strip():
            raise IntegrationPersistenceError("request_id must be a non-empty string")
        if not isinstance(request_hash, str) or HASH_PATTERN.fullmatch(request_hash) is None:
            raise IntegrationPersistenceError(
                "request_hash must use sha256: followed by 64 lowercase hexadecimal digits"
            )
        results = self._load_results()
        for result in results:
            if result.request_id != request_id:
                continue
            if result.request_hash == request_hash:
                return LedgerLookupResult(
                    status=LedgerLookupStatus.COMPLETED,
                    result=result,
                )
            return LedgerLookupResult(status=LedgerLookupStatus.HASH_CONFLICT)
        operation = self.load_operation(request_id)
        if operation is not None and operation.request_hash != request_hash:
            return LedgerLookupResult(status=LedgerLookupStatus.HASH_CONFLICT)
        return LedgerLookupResult(status=LedgerLookupStatus.NOT_FOUND)

    def load_completed(self, request_id: str) -> FirstRoundSuccessResult | None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise IntegrationPersistenceError("request_id must be a non-empty string")
        return next(
            (item for item in self._load_results() if item.request_id == request_id),
            None,
        )

    def list_completed(self) -> list[FirstRoundSuccessResult]:
        return list(self._load_results())

    def list_operations(self) -> list[IntegrationOperationRecord]:
        return list(self._load_operations())

    def initialize_empty(self) -> None:
        if self._path.exists() != self._operation_path.exists():
            raise IntegrationPersistenceError(
                "integration result ledger is only partially initialized"
            )
        if self._path.exists():
            self.validate_initialized()
            return
        _atomic_write_json(
            self._path,
            {
                "ledgerPersistenceFormatVersion": LEDGER_PERSISTENCE_FORMAT_VERSION,
                "results": [],
            },
            name="first-round result ledger",
        )
        try:
            _atomic_write_json(
                self._operation_path,
                {
                    "operationJournalFormatVersion": OPERATION_JOURNAL_FORMAT_VERSION,
                    "operations": [],
                },
                name="first-round operation journal",
            )
            self.initialize_capabilities()
        except Exception:
            try:
                self._path.unlink()
            except OSError:
                pass
            raise

    def validate_initialized(self) -> None:
        if not self._path.exists() or not self._operation_path.exists():
            raise IntegrationRecordNotFoundError(
                "integration result ledger has not been fully initialized"
            )
        self._load_results()
        self._load_operations()
        if self._capability_path.exists():
            self.validate_capability_initialized()

    def initialize_capabilities(self) -> None:
        if self._capability_path.exists():
            self.validate_capability_initialized()
            return
        _atomic_write_json(
            self._capability_path,
            {
                "capabilityLedgerFormatVersion": CAPABILITY_LEDGER_FORMAT_VERSION,
                "requests": [],
                "attempts": [],
            },
            name="capability ledger",
        )

    def validate_capability_initialized(self) -> None:
        if not self._capability_path.exists():
            raise IntegrationRecordNotFoundError(
                "capability ledger has not been initialized"
            )
        self._load_capability_document()

    def save_capability_request(self, request: CapabilityRequest) -> None:
        if not isinstance(request, CapabilityRequest):
            raise IntegrationPersistenceError(
                "capability ledger accepts CapabilityRequest values"
            )
        requests, attempts = self._load_capability_document()
        for existing in requests:
            same_identity = (
                existing.capability_request_id == request.capability_request_id
                or existing.operation_id == request.operation_id
                or existing.request_id == request.request_id
            )
            if not same_identity:
                continue
            if existing != request:
                raise CapabilityConflictError(
                    "an immutable CapabilityRequest cannot be changed"
                )
            return
        requests.append(request)
        self._write_capability_document(requests, attempts)

    def load_capability_request(
        self,
        capability_request_id: str,
    ) -> CapabilityRequest | None:
        requests, _ = self._load_capability_document()
        return next(
            (
                item for item in requests
                if item.capability_request_id == capability_request_id
            ),
            None,
        )

    def find_capability_request_by_operation(
        self,
        operation_id: str,
    ) -> CapabilityRequest | None:
        requests, _ = self._load_capability_document()
        return next((item for item in requests if item.operation_id == operation_id), None)

    def save_capability_result(
        self,
        result: CapabilityResult,
        *,
        received_at: str,
    ) -> CapabilityAttempt:
        if not isinstance(result, CapabilityResult):
            raise IntegrationPersistenceError(
                "capability ledger accepts CapabilityResult values"
            )
        requests, attempts = self._load_capability_document()
        request = next(
            (
                item for item in requests
                if item.capability_request_id == result.capability_request_id
            ),
            None,
        )
        if request is None:
            raise IntegrationRecordNotFoundError(
                "CapabilityResult references an unknown CapabilityRequest"
            )
        result_hash = calculate_capability_result_hash(result)
        for attempt in attempts:
            if attempt.result.capability_result_id != result.capability_result_id:
                continue
            if attempt.result_hash != result_hash or attempt.result != result:
                raise CapabilityConflictError(
                    "capabilityResultId was reused with different content"
                )
            return attempt
        request_attempts = [
            item for item in attempts
            if item.result.capability_request_id == result.capability_request_id
        ]
        if any(item.result.status is CapabilityStatus.SUCCEEDED for item in request_attempts):
            raise CapabilityConflictError(
                "a CapabilityRequest can accept only one successful result"
            )
        if any(item.result.status.failed_terminally for item in request_attempts):
            raise CapabilityConflictError(
                "a terminal CapabilityRequest cannot accept another result"
            )
        attempt = CapabilityAttempt(
            result_hash=result_hash,
            received_at=received_at,
            result=result,
        )
        attempts.append(attempt)
        self._write_capability_document(requests, attempts)
        return attempt

    def list_capability_attempts(
        self,
        capability_request_id: str,
    ) -> list[CapabilityAttempt]:
        _, attempts = self._load_capability_document()
        return [
            item for item in attempts
            if item.result.capability_request_id == capability_request_id
        ]

    def _load_capability_document(
        self,
    ) -> tuple[list[CapabilityRequest], list[CapabilityAttempt]]:
        if not self._capability_path.exists():
            raise IntegrationRecordNotFoundError(
                "capability ledger has not been initialized"
            )
        raw = _read_json(self._capability_path, name="capability ledger")
        document = _strict_document(
            raw,
            name="capability ledger document",
            expected_keys={"capabilityLedgerFormatVersion", "requests", "attempts"},
        )
        if document["capabilityLedgerFormatVersion"] != CAPABILITY_LEDGER_FORMAT_VERSION:
            raise IntegrationPersistenceError(
                "unsupported capability ledger format version"
            )
        if not isinstance(document["requests"], list) or not isinstance(
            document["attempts"], list
        ):
            raise IntegrationPersistenceError(
                "capability requests and attempts must be arrays"
            )
        try:
            requests = [CapabilityRequest.from_dict(item) for item in document["requests"]]
            attempts = [CapabilityAttempt.from_dict(item) for item in document["attempts"]]
        except CapabilityValidationError as exc:
            raise IntegrationPersistenceError(
                f"persisted capability record is invalid: {exc}"
            ) from exc
        request_ids: set[str] = set()
        operation_ids: set[str] = set()
        result_ids: set[str] = set()
        request_by_id = {item.capability_request_id: item for item in requests}
        for request in requests:
            if request.capability_request_id in request_ids or request.operation_id in operation_ids:
                raise IntegrationPersistenceError(
                    "capability ledger contains duplicate request identities"
                )
            request_ids.add(request.capability_request_id)
            operation_ids.add(request.operation_id)
        successful_requests: set[str] = set()
        terminal_requests: set[str] = set()
        for attempt in attempts:
            result = attempt.result
            if result.capability_result_id in result_ids:
                raise IntegrationPersistenceError(
                    "capability ledger contains duplicate capabilityResultId values"
                )
            result_ids.add(result.capability_result_id)
            request = request_by_id.get(result.capability_request_id)
            if request is None or any(
                (
                    result.operation_id != request.operation_id,
                    result.request_id != request.request_id,
                    result.request_hash != request.request_hash,
                    result.subject_id != request.subject_id,
                    result.binding_id != request.binding_id,
                    result.binding_version != request.binding_version,
                    result.capability_type != request.capability_type,
                )
            ):
                raise IntegrationPersistenceError(
                    "CapabilityResult does not match its persisted request"
                )
            if result.status is CapabilityStatus.SUCCEEDED:
                if result.capability_request_id in successful_requests:
                    raise IntegrationPersistenceError(
                        "capability ledger contains multiple successful results"
                    )
                successful_requests.add(result.capability_request_id)
            if result.status.failed_terminally:
                if result.capability_request_id in terminal_requests:
                    raise IntegrationPersistenceError(
                        "capability ledger contains multiple terminal results"
                    )
                terminal_requests.add(result.capability_request_id)
        return requests, attempts

    def _write_capability_document(
        self,
        requests: list[CapabilityRequest],
        attempts: list[CapabilityAttempt],
    ) -> None:
        _atomic_write_json(
            self._capability_path,
            {
                "capabilityLedgerFormatVersion": CAPABILITY_LEDGER_FORMAT_VERSION,
                "requests": [item.to_dict() for item in requests],
                "attempts": [item.to_dict() for item in attempts],
            },
            name="capability ledger",
        )

    def load_operation(self, request_id: str) -> IntegrationOperationRecord | None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise IntegrationPersistenceError("request_id must be a non-empty string")
        for operation in self._load_operations():
            if operation.request_id == request_id:
                return operation
        return None

    def save_operation(self, operation: IntegrationOperationRecord) -> None:
        if not isinstance(operation, IntegrationOperationRecord):
            raise IntegrationPersistenceError(
                "the operation journal accepts IntegrationOperationRecord values"
            )
        operations = self._load_operations()
        existing = next(
            (item for item in operations if item.request_id == operation.request_id),
            None,
        )
        if existing is not None:
            self._validate_operation_progress(existing, operation)
            operations = [
                operation if item.request_id == operation.request_id else item
                for item in operations
            ]
        else:
            if any(item.operation_id == operation.operation_id for item in operations):
                raise IntegrationLedgerConflictError(
                    "operationId must be unique in the operation journal"
                )
            operations.append(operation)
        self._validate_operation_set(operations)
        _atomic_write_json(
            self._operation_path,
            {
                "operationJournalFormatVersion": OPERATION_JOURNAL_FORMAT_VERSION,
                "operations": [item.to_dict() for item in operations],
            },
            name="first-round operation journal",
        )

    def save_completed(self, result: FirstRoundSuccessResult) -> None:
        if not isinstance(result, FirstRoundSuccessResult):
            raise IntegrationPersistenceError(
                "the ledger accepts only completed first-round results"
            )
        results = self._load_results()
        if any(item.request_id == result.request_id for item in results):
            raise IntegrationLedgerConflictError(
                "a completed requestId cannot be overwritten"
            )
        operation = self.load_operation(result.request_id)
        if operation is not None:
            if (
                operation.request_hash != result.request_hash
                or operation.operation_id != result.operation_id
                or operation.subject_id != result.subject_id
                or operation.binding_id != result.binding_id
                or operation.binding_version != result.binding_version
                or operation.domain is None
                or operation.domain.response_id != result.response.response_id
                or operation.domain.response_content != result.response.content
                or operation.consumed_observation_ids
                != result.consumed_observation_ids
            ):
                raise IntegrationLedgerConflictError(
                    "completed result does not match its reserved operation"
                )
        self._validate_new_projection(results, result)
        updated = [*results, result]
        self._validate_result_set(updated)
        _atomic_write_json(
            self._path,
            {
                "ledgerPersistenceFormatVersion": LEDGER_PERSISTENCE_FORMAT_VERSION,
                "results": [item.to_dict() for item in updated],
            },
            name="first-round result ledger",
        )

    def _load_operations(self) -> list[IntegrationOperationRecord]:
        if not self._operation_path.exists():
            return []
        raw = _read_json(
            self._operation_path,
            name="first-round operation journal",
        )
        document = _strict_document(
            raw,
            name="first-round operation journal document",
            expected_keys={"operationJournalFormatVersion", "operations"},
        )
        if document["operationJournalFormatVersion"] not in (1, 2, 3):
            raise IntegrationPersistenceError(
                "unsupported first-round operation journal format version"
            )
        raw_operations = document["operations"]
        if not isinstance(raw_operations, list):
            raise IntegrationPersistenceError("journal operations must be an array")
        try:
            operations = [
                IntegrationOperationRecord.from_dict(item)
                for item in raw_operations
            ]
        except MachineContractValidationError as exc:
            raise IntegrationPersistenceError(
                f"persisted first-round operation is invalid: {exc}"
            ) from exc
        self._validate_operation_set(operations)
        return operations

    @staticmethod
    def _validate_operation_set(
        operations: list[IntegrationOperationRecord],
    ) -> None:
        request_ids: set[str] = set()
        operation_ids: set[str] = set()
        response_ids: set[str] = set()
        for operation in operations:
            if operation.request_id in request_ids:
                raise IntegrationPersistenceError(
                    "operation journal contains duplicate requestId values"
                )
            request_ids.add(operation.request_id)
            if operation.operation_id in operation_ids:
                raise IntegrationPersistenceError(
                    "operation journal contains duplicate operationId values"
                )
            operation_ids.add(operation.operation_id)
            response_id = (
                operation.domain.response_id
                if operation.domain is not None
                else (
                    operation.domain_progress.response_id
                    if operation.domain_progress is not None
                    else None
                )
            )
            if response_id is not None:
                if response_id in response_ids:
                    raise IntegrationPersistenceError(
                        "operation journal contains duplicate responseId values"
                    )
                response_ids.add(response_id)

    @staticmethod
    def _validate_operation_progress(
        previous: IntegrationOperationRecord,
        current: IntegrationOperationRecord,
    ) -> None:
        identity_fields = (
            "request_id",
            "request_hash",
            "operation_id",
            "subject_id",
            "binding_id",
            "binding_version",
            "input_revision",
            "consumed_observation_ids",
            "reserved_at",
        )
        if any(
            getattr(previous, field) != getattr(current, field)
            for field in identity_fields
        ):
            raise IntegrationLedgerConflictError(
                "a reserved operation identity cannot be changed"
            )
        order = {
            IntegrationOperationStage.RESERVED: 0,
            IntegrationOperationStage.WAITING_CAPABILITY: 1,
            IntegrationOperationStage.DOMAIN_COMPLETED: 2,
            IntegrationOperationStage.EVOLUTION_COMMITTED: 3,
            IntegrationOperationStage.COMPLETED: 4,
        }
        if order[current.stage] < order[previous.stage]:
            raise IntegrationLedgerConflictError(
                "an operation journal stage cannot move backwards"
            )
        if previous.domain is not None and current.domain != previous.domain:
            raise IntegrationLedgerConflictError(
                "a persisted domain checkpoint cannot be changed"
            )
        if previous.capability is not None:
            if current.capability is None:
                raise IntegrationLedgerConflictError(
                    "a durable capability checkpoint cannot be removed"
                )
            if (
                previous.capability.capability_request_id
                != current.capability.capability_request_id
            ):
                raise IntegrationLedgerConflictError(
                    "capabilityRequestId cannot be changed"
                )
            if previous.capability.status is CapabilityStatus.SUCCEEDED and (
                current.capability.accepted_result_id
                != previous.capability.accepted_result_id
                or current.capability.accepted_result_hash
                != previous.capability.accepted_result_hash
            ):
                raise IntegrationLedgerConflictError(
                    "an accepted CapabilityResult cannot be changed"
                )
            if previous.capability.status.failed_terminally and (
                current.capability != previous.capability
            ):
                raise IntegrationLedgerConflictError(
                    "a terminal capability checkpoint cannot be changed"
                )
        if previous.domain_progress is not None:
            if current.domain_progress is None:
                raise IntegrationLedgerConflictError(
                    "durable domain progress cannot be removed"
                )
            progress_identity_fields = (
                "wake_session_id",
                "wake_context_id",
                "perception_context_id",
                "perception_id",
                "think_session_id",
                "thinking_result_id",
                "action_context_id",
                "response_id",
            )
            if any(
                getattr(previous.domain_progress, field)
                != getattr(current.domain_progress, field)
                for field in progress_identity_fields
            ):
                raise IntegrationLedgerConflictError(
                    "durable domain recovery identities cannot be changed"
                )
            progress_order = {
                "prepared": 0,
                "wake_completed": 1,
                "perception_completed": 2,
                "thinking_completed": 3,
                "action_completed": 4,
            }
            if (
                progress_order[current.domain_progress.stage.value]
                < progress_order[previous.domain_progress.stage.value]
            ):
                raise IntegrationLedgerConflictError(
                    "durable domain progress cannot move backwards"
                )
            for field in (
                "wake_context",
                "perception",
                "perception_at",
                "action_at",
                "response_completed_at",
                "action",
            ):
                previous_value = getattr(previous.domain_progress, field)
                if (
                    previous_value is not None
                    and getattr(current.domain_progress, field) != previous_value
                ):
                    raise IntegrationLedgerConflictError(
                        "a completed domain recovery fact cannot be changed"
                    )
        if previous.evolution is not None and current.evolution != previous.evolution:
            raise IntegrationLedgerConflictError(
                "a persisted evolution checkpoint cannot be changed"
            )

    def _load_results(self) -> list[FirstRoundSuccessResult]:
        if not self._path.exists():
            return []
        raw = _read_json(self._path, name="first-round result ledger")
        document = _strict_document(
            raw,
            name="first-round result ledger document",
            expected_keys={"ledgerPersistenceFormatVersion", "results"},
        )
        if (
            document["ledgerPersistenceFormatVersion"]
            != LEDGER_PERSISTENCE_FORMAT_VERSION
        ):
            raise IntegrationPersistenceError(
                "unsupported first-round result ledger persistence format version"
            )
        raw_results = document["results"]
        if not isinstance(raw_results, list):
            raise IntegrationPersistenceError("ledger results must be an array")
        try:
            results = [FirstRoundSuccessResult.from_dict(item) for item in raw_results]
        except MachineContractValidationError as exc:
            raise IntegrationPersistenceError(
                f"persisted first-round result is invalid: {exc}"
            ) from exc
        self._validate_result_set(results)
        return results

    def _validate_result_set(self, results: list[FirstRoundSuccessResult]) -> None:
        request_ids: set[str] = set()
        operation_ids: set[str] = set()
        response_ids: set[str] = set()
        projection_by_revision: dict[tuple[str, int], SubjectStateProjection] = {}
        engine_update_ids: set[str] = set()

        for result in results:
            if result.request_id in request_ids:
                raise IntegrationPersistenceError(
                    "persisted ledger contains duplicate requestId values"
                )
            request_ids.add(result.request_id)
            if result.operation_id in operation_ids:
                raise IntegrationPersistenceError(
                    "persisted ledger contains duplicate operationId values"
                )
            operation_ids.add(result.operation_id)
            if result.response.response_id in response_ids:
                raise IntegrationPersistenceError(
                    "persisted ledger contains duplicate responseId values"
                )
            response_ids.add(result.response.response_id)

            projection = result.state_projection
            calculated_content_hash = calculate_projection_content_hash(
                projection.snapshot
            )
            try:
                verify_declared_hash(
                    declared=projection.content_hash,
                    calculated=calculated_content_hash,
                    field_name="stateProjection.contentHash",
                )
            except MachineContractValidationError as exc:
                raise IntegrationPersistenceError(str(exc)) from exc

            projection_key = (projection.subject_id, projection.current_revision)
            existing_projection = projection_by_revision.get(projection_key)
            if existing_projection is None:
                projection_by_revision[projection_key] = projection
            elif not self._has_same_projection_content(
                existing_projection,
                projection,
            ):
                raise IntegrationPersistenceError(
                    "a subject revision has conflicting state projections"
                )

            if projection.engine_update_id is not None:
                if projection.engine_update_id in engine_update_ids:
                    raise IntegrationPersistenceError(
                        "persisted ledger contains duplicate non-null engineUpdateId values"
                    )
                engine_update_ids.add(projection.engine_update_id)

    def _validate_new_projection(
        self,
        results: list[FirstRoundSuccessResult],
        candidate: FirstRoundSuccessResult,
    ) -> None:
        projection = candidate.state_projection
        for existing_result in results:
            existing = existing_result.state_projection
            same_revision = (
                existing.subject_id == projection.subject_id
                and existing.current_revision == projection.current_revision
            )
            if same_revision and not self._has_same_projection_content(
                existing,
                projection,
            ):
                raise IntegrationLedgerConflictError(
                    "a subject revision cannot be associated with different projection content"
                )
            if (
                projection.engine_update_id is not None
                and existing.engine_update_id == projection.engine_update_id
            ):
                raise IntegrationLedgerConflictError(
                    "a non-null engineUpdateId must be unique"
                )

    @staticmethod
    def _has_same_projection_content(
        first: SubjectStateProjection,
        second: SubjectStateProjection,
    ) -> bool:
        return (
            first.snapshot == second.snapshot
            and first.content_hash == second.content_hash
        )
