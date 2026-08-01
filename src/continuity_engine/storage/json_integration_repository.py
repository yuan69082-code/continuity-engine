from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from continuity_engine.domain.errors import (
    IntegrationLedgerConflictError,
    IntegrationPersistenceError,
    IntegrationRecordNotFoundError,
    MachineContractValidationError,
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
    LedgerLookupResult,
    LedgerLookupStatus,
    SubjectStateProjection,
)


BINDING_PERSISTENCE_FORMAT_VERSION = 1
LEDGER_PERSISTENCE_FORMAT_VERSION = 1
_BINDING_FILE_NAME = "subject-binding.first-round-v1.json"
_LEDGER_FILE_NAME = "result-ledger.first-round-v1.json"


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
    """Atomic, immutable first-round completed-result ledger."""

    def __init__(self, root: str | Path) -> None:
        self._path = Path(root) / "integration" / _LEDGER_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

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
        return LedgerLookupResult(status=LedgerLookupStatus.NOT_FOUND)

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
