from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from continuity_engine.domain.awakening import AwakeCycle, WakeSession
from continuity_engine.domain.errors import AwakeningValidationError, StateNotFoundError


class JsonAwakeningRepository:
    """JSON persistence for wake cycles and WakeSession audit logs."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "awakening"
        self.cycles_dir = self.root / "cycles"
        self.sessions_dir = self.root / "sessions"

    @staticmethod
    def _hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AwakeningValidationError(f"{field_name} must be a non-empty string")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _cycle_path(self, cycle_id: str) -> Path:
        return self.cycles_dir / f"{self._hash(cycle_id, 'cycle_id')}.json"

    def _session_path(self, subject_id: str, session_id: str) -> Path:
        subject_hash = self._hash(subject_id, "subject_id")
        session_hash = self._hash(session_id, "session_id")
        return self.sessions_dir / subject_hash / f"{session_hash}.json"

    def save_cycle(self, cycle: AwakeCycle) -> None:
        self._write_json(self._cycle_path(cycle.cycle_id), cycle.to_dict())

    def load_cycle(self, cycle_id: str) -> AwakeCycle:
        path = self._cycle_path(cycle_id)
        if not path.is_file():
            raise StateNotFoundError(f"awake cycle not found: {cycle_id}")
        cycle = AwakeCycle.from_dict(self._read_json(path, "awake cycle"))
        if cycle.cycle_id != cycle_id:
            raise AwakeningValidationError("persisted cycle_id does not match requested cycle_id")
        return cycle

    def list_due_cycles(self, now: datetime) -> list[AwakeCycle]:
        if now.tzinfo is None:
            raise AwakeningValidationError("now must include a timezone")
        if not self.cycles_dir.is_dir():
            return []
        cycles = [
            AwakeCycle.from_dict(self._read_json(path, "awake cycle"))
            for path in self.cycles_dir.glob("*.json")
        ]
        return sorted(
            (cycle for cycle in cycles if cycle.is_due(now)),
            key=lambda cycle: (cycle.next_wake_at or now, cycle.cycle_id),
        )

    def save_session(self, session: WakeSession) -> None:
        path = self._session_path(session.subject_id, session.session_id)
        if path.is_file():
            previous = WakeSession.from_dict(self._read_json(path, "wake session"))
            if previous.subject_id != session.subject_id or previous.cycle_id != session.cycle_id:
                raise AwakeningValidationError("wake session identity cannot be changed")
            if (
                previous.completed_successfully is not None
                and session.completed_successfully is None
            ):
                raise AwakeningValidationError("a completed wake session cannot return to running")
            if (
                previous.recovery_context is not None
                and session.recovery_context != previous.recovery_context
            ):
                raise AwakeningValidationError(
                    "a persisted wake recovery context cannot be changed"
                )
        self._write_json(path, session.to_dict())

    def load_session(self, subject_id: str, session_id: str) -> WakeSession:
        path = self._session_path(subject_id, session_id)
        if not path.is_file():
            raise StateNotFoundError(f"wake session not found: {session_id}")
        session = WakeSession.from_dict(self._read_json(path, "wake session"))
        if session.subject_id != subject_id or session.session_id != session_id:
            raise AwakeningValidationError("persisted wake session identity does not match")
        return session

    def list_sessions(self, subject_id: str, limit: int | None = None) -> list[WakeSession]:
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise AwakeningValidationError("session limit must be a positive integer")
        subject_dir = self.sessions_dir / self._hash(subject_id, "subject_id")
        if not subject_dir.is_dir():
            return []
        sessions = [
            WakeSession.from_dict(self._read_json(path, "wake session"))
            for path in subject_dir.glob("*.json")
        ]
        sessions.sort(key=lambda session: (session.wake_time, session.session_id), reverse=True)
        return sessions[:limit] if limit is not None else sessions

    @staticmethod
    def _read_json(path: Path, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AwakeningValidationError(f"unable to read valid {label} data") from exc

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
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
