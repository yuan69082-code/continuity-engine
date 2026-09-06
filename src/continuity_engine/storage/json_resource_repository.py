from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from continuity_engine.domain.errors import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from continuity_engine.domain.resources import (
    ResourceDecision,
    ResourceState,
    TokenUsageRecord,
)


RESOURCE_FORMAT_VERSION = 1

# Local repository instances share read/check/write protection.
_RESOURCE_WRITE_LOCK = RLock()


class JsonResourceRepository:
    """Atomically persist resource state, usage, and policy decisions."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "resources"

    @staticmethod
    def _hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResourceValidationError(f"{field_name} must be non-empty")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _path(self, subject_id: str) -> Path:
        return self.root / f"{self._hash(subject_id, 'subject_id')}.json"

    def create(self, state: ResourceState) -> None:
        with _RESOURCE_WRITE_LOCK:
            path = self._path(state.subject_id)
            if path.is_file():
                raise ResourceAlreadyExistsError(
                    f"resource state already exists: {state.subject_id}"
                )
            if state.revision != 0:
                raise ResourceValidationError("new resource state must start at revision zero")
            self._write_document(path, self._document(state))

    def load(self, subject_id: str) -> ResourceState:
        data = self._load_document(subject_id)
        return ResourceState.from_dict(data["state"])

    def save_state(
        self,
        state: ResourceState,
        *,
        expected_revision: int,
    ) -> None:
        with _RESOURCE_WRITE_LOCK:
            path = self._path(state.subject_id)
            data = self._load_document(state.subject_id)
            self._validate_next_revision(data, state, expected_revision)
            data["state"] = state.to_dict()
            self._write_document(path, data)

    def save_allocation(
        self,
        state: ResourceState,
        usage: TokenUsageRecord,
        decision: ResourceDecision,
        *,
        expected_revision: int,
    ) -> None:
        with _RESOURCE_WRITE_LOCK:
            if (
                not decision.allowed
                or decision.defer
                or state.subject_id != usage.subject_id
                or state.subject_id != decision.subject_id
                or usage.session_id != decision.session_id
                or usage.estimated_tokens != decision.allocated_tokens
                or usage.estimated_compute != decision.allocated_compute
            ):
                raise ResourceValidationError("resource allocation data is inconsistent")
            path = self._path(state.subject_id)
            data = self._load_document(state.subject_id)
            self._validate_request_identity(data, decision)
            self._validate_next_revision(data, state, expected_revision)
            if any(item.get("usage_id") == usage.usage_id for item in data["usage_records"]):
                raise ResourceValidationError(f"duplicate resource usage: {usage.usage_id}")
            if any(
                item.get("decision_id") == decision.decision_id
                for item in data["decisions"]
            ):
                raise ResourceValidationError(
                    f"duplicate resource decision: {decision.decision_id}"
                )
            data["state"] = state.to_dict()
            data["usage_records"].append(usage.to_dict())
            data["decisions"].append(decision.to_dict())
            self._write_document(path, data)

    def save_decision(self, decision: ResourceDecision) -> None:
        with _RESOURCE_WRITE_LOCK:
            if decision.allowed:
                raise ResourceValidationError(
                    "allowed decisions must be saved with their usage allocation"
                )
            path = self._path(decision.subject_id)
            data = self._load_document(decision.subject_id)
            self._validate_request_identity(data, decision)
            if any(
                item.get("decision_id") == decision.decision_id
                for item in data["decisions"]
            ):
                raise ResourceValidationError(
                    f"duplicate resource decision: {decision.decision_id}"
                )
            data["decisions"].append(decision.to_dict())
            self._write_document(path, data)

    @staticmethod
    def _validate_request_identity(data: dict[str, Any], decision: ResourceDecision) -> None:
        """Check both outcomes against the same locked, current document."""
        if any(item.get("request_id") == decision.request_id for item in data["decisions"]):
            raise ResourceValidationError("duplicate or conflicting resource request identity")
        if any(item.get("session_id") == decision.session_id for item in data["usage_records"]):
            raise ResourceValidationError("resource session already has an allocation")

    def reconcile_usage(
        self,
        state: ResourceState,
        usage: TokenUsageRecord,
        *,
        expected_revision: int,
    ) -> None:
        with _RESOURCE_WRITE_LOCK:
            path = self._path(state.subject_id)
            data = self._load_document(state.subject_id)
            self._validate_next_revision(data, state, expected_revision)
            usage_index = next(
                (
                    index
                    for index, item in enumerate(data["usage_records"])
                    if item.get("usage_id") == usage.usage_id
                ),
                None,
            )
            if usage_index is None:
                raise ResourceNotFoundError(f"resource usage not found: {usage.usage_id}")
            previous = TokenUsageRecord.from_dict(data["usage_records"][usage_index])
            if (
                previous.subject_id != usage.subject_id
                or previous.session_id != usage.session_id
                or previous.actual_tokens is not None
            ):
                raise ResourceValidationError("resource usage cannot be reconciled")
            data["state"] = state.to_dict()
            data["usage_records"][usage_index] = usage.to_dict()
            self._write_document(path, data)

    def list_usage(self, subject_id: str) -> list[TokenUsageRecord]:
        path = self._path(subject_id)
        if not path.is_file():
            return []
        data = self._load_document(subject_id)
        return [TokenUsageRecord.from_dict(item) for item in data["usage_records"]]

    def list_decisions(self, subject_id: str) -> list[ResourceDecision]:
        path = self._path(subject_id)
        if not path.is_file():
            return []
        data = self._load_document(subject_id)
        return [ResourceDecision.from_dict(item) for item in data["decisions"]]

    def _load_document(self, subject_id: str) -> dict[str, Any]:
        path = self._path(subject_id)
        if not path.is_file():
            raise ResourceNotFoundError(f"resource state not found: {subject_id}")
        data = self._read_document(path)
        state = ResourceState.from_dict(data.get("state"))
        if state.subject_id != subject_id:
            raise ResourceValidationError("persisted resource subject is invalid")
        return data

    @staticmethod
    def _validate_next_revision(
        data: dict[str, Any],
        state: ResourceState,
        expected_revision: int,
    ) -> None:
        current = ResourceState.from_dict(data["state"])
        if current.revision != expected_revision:
            raise ResourceValidationError(
                "resource state does not match expected_revision"
            )
        if state.revision != current.revision + 1:
            raise ResourceValidationError("resource revision must advance by one")
        if state.resource_id != current.resource_id or state.subject_id != current.subject_id:
            raise ResourceValidationError("resource identity cannot change")

    @staticmethod
    def _document(state: ResourceState) -> dict[str, Any]:
        return {
            "resource_format_version": RESOURCE_FORMAT_VERSION,
            "state": state.to_dict(),
            "usage_records": [],
            "decisions": [],
        }

    @staticmethod
    def _read_document(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResourceValidationError("unable to read valid resource data") from exc
        if not isinstance(data, dict) or data.get(
            "resource_format_version"
        ) != RESOURCE_FORMAT_VERSION:
            raise ResourceValidationError("unsupported resource persistence format")
        if not isinstance(data.get("usage_records"), list) or not isinstance(
            data.get("decisions"), list
        ):
            raise ResourceValidationError("resource history collections are invalid")
        return data

    @staticmethod
    def _write_document(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.stem}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
