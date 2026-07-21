from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.errors import (
    PermissionAlreadyExistsError,
    PermissionNotFoundError,
    PermissionValidationError,
)
from continuity_engine.domain.permissions import (
    PermissionChangeRecord,
    PermissionChangeType,
    PermissionState,
)


PERMISSION_FORMAT_VERSION = 1


class JsonPermissionRepository:
    """Persist current permission state and its complete change history atomically."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "permissions"

    @staticmethod
    def _hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise PermissionValidationError(f"{field_name} must be non-empty")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _subject_dir(self, subject_id: str) -> Path:
        return self.root / self._hash(subject_id, "subject_id")

    def _path(self, subject_id: str, permission_id: str) -> Path:
        return self._subject_dir(subject_id) / (
            f"{self._hash(permission_id, 'permission_id')}.json"
        )

    def save(
        self,
        permission: PermissionState,
        change: PermissionChangeRecord,
    ) -> None:
        if permission.permission_id != change.permission_id:
            raise PermissionValidationError(
                "permission change does not match saved permission"
            )
        if change.after_state != permission.to_dict():
            raise PermissionValidationError(
                "permission change after_state must equal saved state"
            )
        path = self._path(permission.subject_id, permission.permission_id)
        history: list[PermissionChangeRecord] = []
        if path.is_file():
            data = self._read_document(path)
            previous = PermissionState.from_dict(data.get("state"))
            history = [
                PermissionChangeRecord.from_dict(item)
                for item in data.get("history", [])
            ]
            if previous.subject_id != permission.subject_id or (
                previous.permission_id != permission.permission_id
            ):
                raise PermissionValidationError(
                    "persisted permission identity does not match path"
                )
            if permission.revision != previous.revision + 1:
                raise PermissionValidationError(
                    "permission update revision must advance by one"
                )
            if change.before_state != previous.to_dict():
                raise PermissionValidationError(
                    "permission change before_state does not match persisted state"
                )
        else:
            if permission.revision != 0 or change.before_state is not None:
                raise PermissionValidationError(
                    "new permissions must start at revision zero without before_state"
                )
            if change.change_type is not PermissionChangeType.GRANTED:
                raise PermissionValidationError(
                    "new permission history must begin with GRANTED"
                )
        if any(item.record_id == change.record_id for item in history):
            if history[-1].to_dict() == change.to_dict():
                return
            raise PermissionAlreadyExistsError(
                f"permission history record already exists: {change.record_id}"
            )
        history.append(change)
        self._write_document(
            path,
            {
                "permission_format_version": PERMISSION_FORMAT_VERSION,
                "state": permission.to_dict(),
                "history": [item.to_dict() for item in history],
            },
        )

    def load(self, subject_id: str, permission_id: str) -> PermissionState:
        path = self._path(subject_id, permission_id)
        if not path.is_file():
            raise PermissionNotFoundError(f"permission not found: {permission_id}")
        permission = PermissionState.from_dict(self._read_document(path).get("state"))
        if permission.subject_id != subject_id or permission.permission_id != permission_id:
            raise PermissionValidationError(
                "persisted permission identity does not match request"
            )
        return permission

    def list(self, subject_id: str) -> list[PermissionState]:
        subject_dir = self._subject_dir(subject_id)
        if not subject_dir.is_dir():
            return []
        permissions = [
            PermissionState.from_dict(self._read_document(path).get("state"))
            for path in subject_dir.glob("*.json")
        ]
        if any(item.subject_id != subject_id for item in permissions):
            raise PermissionValidationError(
                "permission directory contains a different subject"
            )
        permissions.sort(key=lambda item: (item.name, item.permission_id))
        return permissions

    def history(
        self,
        subject_id: str,
        permission_id: str | None = None,
    ) -> list[PermissionChangeRecord]:
        paths: list[Path]
        if permission_id is not None:
            path = self._path(subject_id, permission_id)
            if not path.is_file():
                raise PermissionNotFoundError(
                    f"permission not found: {permission_id}"
                )
            paths = [path]
        else:
            subject_dir = self._subject_dir(subject_id)
            paths = list(subject_dir.glob("*.json")) if subject_dir.is_dir() else []
        records = [
            PermissionChangeRecord.from_dict(item)
            for path in paths
            for item in self._read_document(path).get("history", [])
        ]
        records.sort(key=lambda item: (item.created_at, item.record_id))
        return records

    @staticmethod
    def _read_document(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PermissionValidationError(
                "unable to read valid permission data"
            ) from exc
        if not isinstance(data, dict) or data.get(
            "permission_format_version"
        ) != PERMISSION_FORMAT_VERSION:
            raise PermissionValidationError("unsupported permission persistence format")
        if not isinstance(data.get("history"), list):
            raise PermissionValidationError("permission history must be a list")
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
