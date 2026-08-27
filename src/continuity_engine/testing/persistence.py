from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from continuity_engine.domain.action import ActionSession
from continuity_engine.domain.errors import ActionValidationError, StateNotFoundError
from continuity_engine.domain.integration_hashing import canonicalize_json, sha256_hash
from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryInfluenceRecord,
    MemoryRetrievalRequest,
)

from .models import SandboxOperationError, format_utc, parse_utc


REPARSE_POINT_ATTRIBUTE = 0x400


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SandboxOperationError("SANDBOX_DATA_INVALID", f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise SandboxOperationError("SANDBOX_DATA_INVALID", f"expected object: {path.name}")
    return value


def file_hash(path: Path) -> str:
    try:
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    except OSError as exc:
        raise SandboxOperationError("SNAPSHOT_INCOMPLETE", f"cannot hash {path.name}") from exc


def canonical_hash(value: Any) -> str:
    return sha256_hash(canonicalize_json(value))


def is_link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & REPARSE_POINT_ATTRIBUTE)
    except FileNotFoundError:
        return False


def assert_no_link_components(path: Path, *, stop_at: Path) -> None:
    current = path
    boundary = stop_at.resolve(strict=False)
    while True:
        if current.exists() and is_link_like(current):
            raise SandboxOperationError(
                "SANDBOX_PATH_FORBIDDEN",
                "symbolic links and junctions are not allowed in P01 sandbox paths",
            )
        if current.resolve(strict=False) == boundary:
            break
        if current.parent == current:
            raise SandboxOperationError(
                "SANDBOX_PATH_FORBIDDEN", "sandbox path escaped its registered root"
            )
        current = current.parent


def assert_descendant(path: Path, parent: Path) -> None:
    resolved = path.resolve(strict=False)
    base = parent.resolve(strict=False)
    if resolved == base or base not in resolved.parents:
        raise SandboxOperationError(
            "SANDBOX_PATH_FORBIDDEN", "target is outside the registered sandbox root"
        )


def copy_tree_without_links(source: Path, target: Path, *, boundary: Path) -> None:
    assert_descendant(source, boundary)
    assert_no_link_components(source, stop_at=boundary)
    for item in source.rglob("*"):
        if is_link_like(item):
            raise SandboxOperationError(
                "SANDBOX_PATH_FORBIDDEN", "snapshot source contains a link or junction"
            )
    shutil.copytree(source, target, copy_function=shutil.copy2)


def remove_tree_safely(target: Path, *, allowed_parent: Path) -> None:
    assert_descendant(target, allowed_parent)
    assert_no_link_components(target, stop_at=allowed_parent)
    if is_link_like(target):
        raise SandboxOperationError(
            "SANDBOX_CLEANUP_FORBIDDEN", "cleanup target is a link or junction"
        )
    if target.exists():
        shutil.rmtree(target)


def physical_file_inventory(root: Path) -> list[dict[str, str]]:
    """Return a stable, closed-world inventory without following links."""

    if not root.is_dir() or is_link_like(root):
        raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "inventory root is missing or unsafe")
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if is_link_like(path):
            raise SandboxOperationError(
                "SNAPSHOT_INCOMPLETE", "inventory contains a symbolic link or junction"
            )
        if path.is_file():
            entries.append(
                {
                    "relativePath": path.relative_to(root).as_posix(),
                    "fileHash": file_hash(path),
                }
            )
    return entries


def tree_inventory_hash(root: Path) -> str:
    """Hash a full directory tree for an external, read-only isolation check."""

    if not root.exists():
        return canonical_hash([])
    return canonical_hash(physical_file_inventory(root))


class SandboxFrozenClock:
    """A persisted subject clock used only inside one sandbox branch."""

    FORMAT_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def create(cls, path: Path, frozen_at: datetime) -> SandboxFrozenClock:
        clock = cls(path)
        if frozen_at.tzinfo is None:
            raise SandboxOperationError("CLOCK_INVALID", "frozen time must be timezone-aware")
        if path.exists():
            raise SandboxOperationError("CLOCK_INVALID", "subject clock already exists")
        atomic_write_json(
            path,
            {
                "formatVersion": cls.FORMAT_VERSION,
                "environment": "TEST",
                "frozen": True,
                "currentTime": format_utc(frozen_at),
            },
        )
        return clock

    def now(self) -> datetime:
        value = read_json(self._path)
        if (
            value.get("formatVersion") != self.FORMAT_VERSION
            or value.get("environment") != "TEST"
            or value.get("frozen") is not True
        ):
            raise SandboxOperationError("CLOCK_INVALID", "subject clock is invalid")
        return parse_utc(value.get("currentTime"), "currentTime")

    def advance(self, amount: timedelta) -> datetime:
        if not isinstance(amount, timedelta) or amount.total_seconds() <= 0:
            raise SandboxOperationError("CLOCK_INVALID", "advance must be positive")
        advanced = self.now() + amount
        atomic_write_json(
            self._path,
            {
                "formatVersion": self.FORMAT_VERSION,
                "environment": "TEST",
                "frozen": True,
                "currentTime": format_utc(advanced),
            },
        )
        return advanced

    def to_dict(self) -> dict[str, Any]:
        return read_json(self._path)


class SandboxMemoryRepository:
    """Persistent test-only memory and influence records under a sandbox root."""

    FORMAT_VERSION = 1

    def __init__(self, root: Path) -> None:
        self.path = root / "test-memory" / "memory-ledger.v1.json"

    def initialize(self, subject_id: str) -> None:
        if self.path.exists():
            document = self._load()
            if document.get("subjectId") != subject_id:
                raise SandboxOperationError("SANDBOX_DATA_INVALID", "memory subject mismatch")
            return
        atomic_write_json(
            self.path,
            {
                "formatVersion": self.FORMAT_VERSION,
                "environment": "TEST",
                "synthetic": True,
                "subjectId": subject_id,
                "memories": [],
                "influences": [],
            },
        )

    def save_memory(self, memory: MemoryCandidate) -> None:
        document = self._load()
        if memory.subject_id != document["subjectId"]:
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "memory belongs to another subject")
        if any(item.get("memory_id") == memory.memory_id for item in document["memories"]):
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "duplicate test memory")
        document["memories"].append(memory.to_dict())
        atomic_write_json(self.path, document)

    def save_influence(self, influence: MemoryInfluenceRecord) -> None:
        document = self._load()
        if influence.subject_id != document["subjectId"]:
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "influence belongs to another subject")
        if any(
            item.get("influence_id") == influence.influence_id
            for item in document["influences"]
        ):
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "duplicate test influence")
        document["influences"].append(influence.to_dict())
        atomic_write_json(self.path, document)

    def retrieve(self, request: MemoryRetrievalRequest) -> list[MemoryCandidate]:
        document = self._load()
        if request.subject_id != document["subjectId"]:
            raise SandboxOperationError(
                "SANDBOX_DATA_INVALID", "memory request belongs to another subject"
            )
        return self.list_memories()

    def record_influence(self, record: MemoryInfluenceRecord) -> None:
        self.save_influence(record)

    def list_memories(self) -> list[MemoryCandidate]:
        return [MemoryCandidate.from_dict(item) for item in self._load()["memories"]]

    def list_influences(self) -> list[MemoryInfluenceRecord]:
        return [
            MemoryInfluenceRecord.from_dict(item) for item in self._load()["influences"]
        ]

    def to_dict(self) -> dict[str, Any]:
        return self._load()

    def _load(self) -> dict[str, Any]:
        value = read_json(self.path)
        if (
            value.get("formatVersion") != self.FORMAT_VERSION
            or value.get("environment") != "TEST"
            or value.get("synthetic") is not True
            or not isinstance(value.get("memories"), list)
            or not isinstance(value.get("influences"), list)
        ):
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "test memory ledger is invalid")
        return value


class SandboxActionRepository:
    """Persistent ActionRepository implementation scoped to one P01 sandbox."""

    FORMAT_VERSION = 1

    def __init__(self, root: Path) -> None:
        self.path = root / "test-actions" / "action-sessions.v1.json"

    def initialize(self, subject_id: str) -> None:
        if self.path.exists():
            document = self._load()
            if document.get("subjectId") != subject_id:
                raise SandboxOperationError("SANDBOX_DATA_INVALID", "action subject mismatch")
            return
        atomic_write_json(
            self.path,
            {
                "formatVersion": self.FORMAT_VERSION,
                "environment": "TEST",
                "synthetic": True,
                "subjectId": subject_id,
                "sessions": [],
            },
        )

    def save_action_session(self, session: ActionSession) -> None:
        document = self._load()
        if session.subject_id != document["subjectId"]:
            raise ActionValidationError("ActionSession belongs to another sandbox subject")
        existing = next(
            (
                item
                for item in document["sessions"]
                if item.get("action_session_id") == session.action_session_id
            ),
            None,
        )
        serialized = session.to_dict()
        if existing is not None:
            if existing != serialized:
                raise ActionValidationError(
                    "a persisted ActionSession cannot be overwritten with different data"
                )
            return
        document["sessions"].append(serialized)
        atomic_write_json(self.path, document)

    def load_action_session(
        self,
        subject_id: str,
        action_session_id: str,
    ) -> ActionSession:
        document = self._load()
        if subject_id != document["subjectId"]:
            raise StateNotFoundError(f"ActionSession not found: {action_session_id}")
        item = next(
            (
                value
                for value in document["sessions"]
                if value.get("action_session_id") == action_session_id
            ),
            None,
        )
        if item is None:
            raise StateNotFoundError(f"ActionSession not found: {action_session_id}")
        return ActionSession.from_dict(item)

    def list_action_sessions(
        self,
        subject_id: str,
        limit: int | None = None,
    ) -> list[ActionSession]:
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ActionValidationError("ActionSession limit must be positive")
        document = self._load()
        if subject_id != document["subjectId"]:
            return []
        sessions = [ActionSession.from_dict(item) for item in document["sessions"]]
        sessions.sort(
            key=lambda item: (item.created_at, item.action_session_id), reverse=True
        )
        return sessions[:limit] if limit is not None else sessions

    def to_dict(self) -> dict[str, Any]:
        return self._load()

    def _load(self) -> dict[str, Any]:
        value = read_json(self.path)
        if (
            value.get("formatVersion") != self.FORMAT_VERSION
            or value.get("environment") != "TEST"
            or value.get("synthetic") is not True
            or not isinstance(value.get("sessions"), list)
        ):
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "action ledger is invalid")
        return value


class SandboxTraceRepository:
    """Structured test trace; it is never a formal thought or Event history."""

    FORMAT_VERSION = 1

    def __init__(self, root: Path) -> None:
        self.path = root / "test-trace" / "subject-clock-trace.v1.json"

    def initialize(self, subject_id: str) -> None:
        atomic_write_json(
            self.path,
            {
                "formatVersion": self.FORMAT_VERSION,
                "environment": "TEST",
                "synthetic": True,
                "subjectId": subject_id,
                "entries": [],
            },
        )

    def record(self, component: str, occurred_at: datetime, payload: dict[str, Any]) -> None:
        value = self.to_dict()
        value["entries"].append(
            {
                "component": component,
                "occurredAt": format_utc(occurred_at),
                "payload": payload,
                "synthetic": True,
            }
        )
        atomic_write_json(self.path, value)

    def to_dict(self) -> dict[str, Any]:
        value = read_json(self.path)
        if (
            value.get("formatVersion") != self.FORMAT_VERSION
            or value.get("environment") != "TEST"
            or value.get("synthetic") is not True
            or not isinstance(value.get("entries"), list)
        ):
            raise SandboxOperationError("SANDBOX_DATA_INVALID", "test trace is invalid")
        return value
