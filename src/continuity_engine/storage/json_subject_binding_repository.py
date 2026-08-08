from __future__ import annotations

from pathlib import Path

from continuity_engine.domain.errors import (
    IntegrationLedgerConflictError,
    IntegrationPersistenceError,
    IntegrationRecordNotFoundError,
    MachineContractValidationError,
)
from continuity_engine.domain.integration_hashing import calculate_binding_fixture_hash
from continuity_engine.domain.subject_binding import SubjectBinding

from .json_integration_repository import _atomic_write_json, _read_json, _strict_document


RUNTIME_BINDING_PERSISTENCE_FORMAT_VERSION = 1
_RUNTIME_BINDING_FILE_NAME = "subject-binding.runtime-v1.json"


class JsonSubjectBindingRepository:
    """Atomic persistence for the one immutable active runtime binding."""

    def __init__(self, root: str | Path) -> None:
        self._path = Path(root) / "integration" / _RUNTIME_BINDING_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def initialize(self, binding: SubjectBinding) -> None:
        if not isinstance(binding, SubjectBinding):
            raise IntegrationPersistenceError("binding must be a SubjectBinding")
        self._validate_hash(binding)
        if self._path.exists():
            if self.load_active() == binding:
                return
            raise IntegrationLedgerConflictError(
                "the active runtime SubjectBinding is immutable"
            )
        _atomic_write_json(
            self._path,
            {
                "bindingPersistenceFormatVersion": (
                    RUNTIME_BINDING_PERSISTENCE_FORMAT_VERSION
                ),
                "binding": binding.to_dict(),
            },
            name="runtime SubjectBinding",
        )

    def load_active(self) -> SubjectBinding:
        try:
            raw = _read_json(self._path, name="runtime SubjectBinding")
        except FileNotFoundError as exc:
            raise IntegrationRecordNotFoundError(
                "the runtime SubjectBinding has not been initialized"
            ) from exc
        document = _strict_document(
            raw,
            name="runtime SubjectBinding document",
            expected_keys={"bindingPersistenceFormatVersion", "binding"},
        )
        if (
            document["bindingPersistenceFormatVersion"]
            != RUNTIME_BINDING_PERSISTENCE_FORMAT_VERSION
        ):
            raise IntegrationPersistenceError(
                "unsupported runtime SubjectBinding persistence format version"
            )
        try:
            binding = SubjectBinding.from_dict(document["binding"])
        except MachineContractValidationError as exc:
            raise IntegrationPersistenceError(str(exc)) from exc
        self._validate_hash(binding)
        return binding

    @staticmethod
    def _validate_hash(binding: SubjectBinding) -> None:
        calculated = calculate_binding_fixture_hash(binding.to_fixture())
        if calculated != binding.binding_fixture_hash:
            raise IntegrationPersistenceError(
                "persisted runtime SubjectBinding hash does not match its fixture"
            )
