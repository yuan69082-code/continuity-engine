from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.errors import StateNotFoundError, ThinkingValidationError
from continuity_engine.domain.thinking import ThinkSession, ThinkSessionStatus


class JsonThinkingRepository:
    """Persist ThinkSession summaries without storing model chain-of-thought."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "thinking" / "sessions"

    @staticmethod
    def _hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ThinkingValidationError(f"{field_name} must be a non-empty string")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _path(self, subject_id: str, think_id: str) -> Path:
        return (
            self.root
            / self._hash(subject_id, "subject_id")
            / f"{self._hash(think_id, 'think_id')}.json"
        )

    def save_think_session(self, session: ThinkSession) -> None:
        path = self._path(session.subject_id, session.think_id)
        if path.is_file():
            previous = ThinkSession.from_dict(self._read_json(path))
            if (
                previous.subject_id != session.subject_id
                or previous.wake_session_id != session.wake_session_id
                or previous.provider_id != session.provider_id
            ):
                raise ThinkingValidationError("ThinkSession identity cannot be changed")
            if (
                previous.completed_successfully is not None
                and session.completed_successfully is None
            ):
                raise ThinkingValidationError("a completed ThinkSession cannot return to running")
            allowed_transitions = {
                ThinkSessionStatus.RUNNING: {
                    ThinkSessionStatus.RUNNING,
                    ThinkSessionStatus.WAITING_CAPABILITY,
                    ThinkSessionStatus.COMPLETED,
                    ThinkSessionStatus.FAILED,
                },
                ThinkSessionStatus.WAITING_CAPABILITY: {
                    ThinkSessionStatus.RUNNING,
                    ThinkSessionStatus.WAITING_CAPABILITY,
                    ThinkSessionStatus.COMPLETED,
                    ThinkSessionStatus.FAILED,
                },
                ThinkSessionStatus.COMPLETED: {ThinkSessionStatus.COMPLETED},
                ThinkSessionStatus.FAILED: {ThinkSessionStatus.FAILED},
            }
            if session.status not in allowed_transitions[previous.status]:
                raise ThinkingValidationError(
                    "ThinkSession status cannot move backwards"
                )
            if (
                previous.capability_request_id is not None
                and session.capability_request_id != previous.capability_request_id
            ):
                raise ThinkingValidationError(
                    "ThinkSession capability_request_id cannot be changed"
                )
            if (
                previous.result is not None
                and session.result != previous.result
            ):
                raise ThinkingValidationError(
                    "a completed ThinkSession result cannot be changed"
                )
            if (
                previous.perception_snapshot is not None
                and session.perception_snapshot != previous.perception_snapshot
            ):
                raise ThinkingValidationError(
                    "a persisted ThinkSession perception snapshot cannot be changed"
                )
        self._write_json(path, session.to_dict())

    def load_think_session(self, subject_id: str, think_id: str) -> ThinkSession:
        path = self._path(subject_id, think_id)
        if not path.is_file():
            raise StateNotFoundError(f"ThinkSession not found: {think_id}")
        session = ThinkSession.from_dict(self._read_json(path))
        if session.subject_id != subject_id or session.think_id != think_id:
            raise ThinkingValidationError("persisted ThinkSession identity does not match")
        return session

    def list_think_sessions(
        self,
        subject_id: str,
        limit: int | None = None,
    ) -> list[ThinkSession]:
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ThinkingValidationError("ThinkSession limit must be a positive integer")
        subject_dir = self.root / self._hash(subject_id, "subject_id")
        if not subject_dir.is_dir():
            return []
        sessions = [
            ThinkSession.from_dict(self._read_json(path))
            for path in subject_dir.glob("*.json")
        ]
        sessions.sort(key=lambda item: (item.started_at, item.think_id), reverse=True)
        return sessions[:limit] if limit is not None else sessions

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ThinkingValidationError("unable to read valid ThinkSession data") from exc

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
