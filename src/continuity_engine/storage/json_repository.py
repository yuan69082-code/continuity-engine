from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.errors import StateEvolutionError, StateNotFoundError, StateValidationError
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.models import SubjectState


PERSISTENCE_FORMAT_VERSION = 1


class JsonSubjectStateRepository:
    """Persist each SubjectState as one UTF-8 JSON document.

    Subject identifiers are hashed for filenames so identifiers can safely contain
    spaces, Unicode, or path-like characters. The original identifier remains in
    the JSON document and is verified when loading.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @staticmethod
    def _validate_subject_id(subject_id: str) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise StateValidationError("subject_id must be a non-empty string")

    def _path_for(self, subject_id: str) -> Path:
        self._validate_subject_id(subject_id)
        digest = hashlib.sha256(subject_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def exists(self, subject_id: str) -> bool:
        return self._path_for(subject_id).is_file()

    def load(self, subject_id: str) -> SubjectState:
        path = self._path_for(subject_id)
        if not path.is_file():
            raise StateNotFoundError(f"subject state not found: {subject_id}")
        state, _ = self._decode_document(self._read_payload(path, subject_id))
        if state.subject_id != subject_id:
            raise StateValidationError("persisted subject_id does not match requested subject_id")
        return state

    def save(self, state: SubjectState) -> None:
        path = self._path_for(state.subject_id)
        updates: list[StateUpdateRecord] | None = None
        if path.is_file():
            raw = self._read_payload(path, state.subject_id)
            if self._is_envelope(raw):
                current, updates = self._decode_document(raw)
                if state.to_dict() != current.to_dict():
                    raise StateEvolutionError(
                        "event-backed state cannot be changed with direct save; use save_transition"
                    )
        payload: dict[str, Any] = state.to_dict()
        if updates is not None:
            payload = self._envelope(state, updates)
        self._write_payload(path, payload)

    def save_transition(self, state: SubjectState, update: StateUpdateRecord) -> None:
        path = self._path_for(state.subject_id)
        if not path.is_file():
            raise StateNotFoundError(f"subject state not found: {state.subject_id}")

        current, updates = self._decode_document(self._read_payload(path, state.subject_id))
        if current.subject_id != state.subject_id or update.subject_id != state.subject_id:
            raise StateEvolutionError("transition subject identifiers do not match")
        if current.revision != update.before_revision:
            raise StateEvolutionError(
                f"stale state revision: stored {current.revision}, event expected "
                f"{update.before_revision}"
            )
        if state.revision != update.after_revision:
            raise StateEvolutionError("updated state revision does not match its update record")
        if any(record.update_id == update.update_id for record in updates):
            raise StateEvolutionError(f"duplicate update record: {update.update_id}")
        if any(record.event.event_id == update.event.event_id for record in updates):
            raise StateEvolutionError(f"event was already applied: {update.event.event_id}")

        self._write_payload(path, self._envelope(state, [*updates, update]))

    def list_update_records(self, subject_id: str) -> list[StateUpdateRecord]:
        path = self._path_for(subject_id)
        if not path.is_file():
            raise StateNotFoundError(f"subject state not found: {subject_id}")
        state, updates = self._decode_document(self._read_payload(path, subject_id))
        if state.subject_id != subject_id:
            raise StateValidationError("persisted subject_id does not match requested subject_id")
        return updates

    @staticmethod
    def _is_envelope(data: Any) -> bool:
        return isinstance(data, dict) and "state" in data and "updates" in data

    @staticmethod
    def _envelope(
        state: SubjectState,
        updates: list[StateUpdateRecord],
    ) -> dict[str, Any]:
        return {
            "persistence_format_version": PERSISTENCE_FORMAT_VERSION,
            "state": state.to_dict(),
            "updates": [record.to_dict() for record in updates],
        }

    @staticmethod
    def _decode_document(data: Any) -> tuple[SubjectState, list[StateUpdateRecord]]:
        if JsonSubjectStateRepository._is_envelope(data):
            format_version = data.get("persistence_format_version")
            if format_version != PERSISTENCE_FORMAT_VERSION:
                raise StateValidationError(
                    f"unsupported persistence format version: {format_version}"
                )
            raw_updates = data.get("updates")
            if not isinstance(raw_updates, list):
                raise StateValidationError("updates must be a list")
            return (
                SubjectState.from_dict(data.get("state")),
                [StateUpdateRecord.from_dict(item) for item in raw_updates],
            )
        return SubjectState.from_dict(data), []

    @staticmethod
    def _read_payload(path: Path, subject_id: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateValidationError(f"unable to read valid state data for: {subject_id}") from exc

    def _write_payload(self, path: Path, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.stem}.",
                suffix=".tmp",
                dir=self.root,
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
