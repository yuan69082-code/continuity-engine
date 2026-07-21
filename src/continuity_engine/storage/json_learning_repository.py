from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.errors import (
    LearningAlreadyExistsError,
    LearningNotFoundError,
    LearningValidationError,
)
from continuity_engine.domain.learning import (
    LearningEvent,
    LearningRecord,
    PersonalityTrait,
)


LEARNING_FORMAT_VERSION = 1


class JsonLearningRepository:
    """Store candidates, consolidated traits, and append-only audit history."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "learning"

    @staticmethod
    def _hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise LearningValidationError(f"{field_name} must be non-empty")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _path(self, subject_id: str) -> Path:
        return self.root / f"{self._hash(subject_id, 'subject_id')}.json"

    def save_change(
        self,
        subject_id: str,
        learning_event: LearningEvent,
        record: LearningRecord,
        trait: PersonalityTrait | None = None,
    ) -> None:
        if (
            learning_event.subject_id != subject_id
            or record.subject_id != subject_id
            or record.learning_id != learning_event.learning_id
        ):
            raise LearningValidationError(
                "learning event and record must belong to the saved subject"
            )
        if trait is not None and trait.subject_id != subject_id:
            raise LearningValidationError("personality trait belongs to another subject")
        if trait is not None and record.trait_id != trait.trait_id:
            raise LearningValidationError("learning record does not match saved trait")

        path = self._path(subject_id)
        data = self._read_document(path) if path.is_file() else self._empty_document(subject_id)
        if data.get("subject_id") != subject_id:
            raise LearningValidationError("persisted learning subject does not match path")

        events = [LearningEvent.from_dict(item) for item in data["learning_events"]]
        traits = [PersonalityTrait.from_dict(item) for item in data["traits"]]
        records = [LearningRecord.from_dict(item) for item in data["records"]]

        existing_record = next(
            (item for item in records if item.record_id == record.record_id),
            None,
        )
        if existing_record is not None:
            saved_event = next(
                (
                    item
                    for item in events
                    if item.learning_id == learning_event.learning_id
                ),
                None,
            )
            saved_trait = (
                next(
                    (item for item in traits if item.trait_id == trait.trait_id),
                    None,
                )
                if trait is not None
                else None
            )
            if (
                existing_record.to_dict() == record.to_dict()
                and saved_event is not None
                and saved_event.to_dict() == learning_event.to_dict()
                and (
                    (trait is None and record.trait_id is None)
                    or (
                        trait is not None
                        and saved_trait is not None
                        and saved_trait.to_dict() == trait.to_dict()
                    )
                )
            ):
                return
            raise LearningAlreadyExistsError(
                f"learning record already exists: {record.record_id}"
            )

        event_index = next(
            (
                index
                for index, item in enumerate(events)
                if item.learning_id == learning_event.learning_id
            ),
            None,
        )
        if event_index is None:
            if learning_event.revision != 0:
                raise LearningValidationError(
                    "new learning candidates must start at revision zero"
                )
            events.append(learning_event)
        else:
            previous = events[event_index]
            if learning_event.revision != previous.revision + 1:
                raise LearningValidationError(
                    "learning candidate revision must advance by one"
                )
            events[event_index] = learning_event

        if trait is not None:
            trait_index = next(
                (
                    index
                    for index, item in enumerate(traits)
                    if item.trait_id == trait.trait_id
                ),
                None,
            )
            if trait_index is None:
                if trait.revision != 0:
                    raise LearningValidationError(
                        "new personality traits must start at revision zero"
                    )
                traits.append(trait)
            else:
                previous_trait = traits[trait_index]
                if trait.revision != previous_trait.revision + 1:
                    raise LearningValidationError(
                        "personality trait revision must advance by one"
                    )
                traits[trait_index] = trait

        records.append(record)

        events.sort(key=lambda item: (item.created_at, item.learning_id))
        traits.sort(key=lambda item: (item.created_at, item.trait_id))
        self._write_document(
            path,
            {
                "learning_format_version": LEARNING_FORMAT_VERSION,
                "subject_id": subject_id,
                "learning_events": [item.to_dict() for item in events],
                "traits": [item.to_dict() for item in traits],
                "records": [item.to_dict() for item in records],
            },
        )

    def load_learning_event(
        self,
        subject_id: str,
        learning_id: str,
    ) -> LearningEvent:
        data = self._load_subject(subject_id)
        for raw in data["learning_events"]:
            event = LearningEvent.from_dict(raw)
            if event.learning_id == learning_id:
                return event
        raise LearningNotFoundError(f"learning candidate not found: {learning_id}")

    def list_learning_events(self, subject_id: str) -> list[LearningEvent]:
        path = self._path(subject_id)
        if not path.is_file():
            return []
        data = self._read_document(path)
        self._validate_subject(data, subject_id)
        return [LearningEvent.from_dict(item) for item in data["learning_events"]]

    def load_trait(self, subject_id: str, trait_id: str) -> PersonalityTrait:
        data = self._load_subject(subject_id)
        for raw in data["traits"]:
            trait = PersonalityTrait.from_dict(raw)
            if trait.trait_id == trait_id:
                return trait
        raise LearningNotFoundError(f"personality trait not found: {trait_id}")

    def list_traits(
        self,
        subject_id: str,
        include_inactive: bool = True,
    ) -> list[PersonalityTrait]:
        path = self._path(subject_id)
        if not path.is_file():
            return []
        data = self._read_document(path)
        self._validate_subject(data, subject_id)
        traits = [PersonalityTrait.from_dict(item) for item in data["traits"]]
        return traits if include_inactive else [item for item in traits if item.active]

    def history(
        self,
        subject_id: str,
        learning_id: str | None = None,
    ) -> list[LearningRecord]:
        path = self._path(subject_id)
        if not path.is_file():
            if learning_id is None:
                return []
            raise LearningNotFoundError(f"learning candidate not found: {learning_id}")
        data = self._read_document(path)
        self._validate_subject(data, subject_id)
        records = [LearningRecord.from_dict(item) for item in data["records"]]
        if learning_id is not None:
            if not any(
                item.get("learning_id") == learning_id
                for item in data["learning_events"]
            ):
                raise LearningNotFoundError(
                    f"learning candidate not found: {learning_id}"
                )
            records = [item for item in records if item.learning_id == learning_id]
        return records

    def _load_subject(self, subject_id: str) -> dict[str, Any]:
        path = self._path(subject_id)
        if not path.is_file():
            raise LearningNotFoundError(f"learning subject not found: {subject_id}")
        data = self._read_document(path)
        self._validate_subject(data, subject_id)
        return data

    @staticmethod
    def _validate_subject(data: dict[str, Any], subject_id: str) -> None:
        if data.get("subject_id") != subject_id:
            raise LearningValidationError("persisted learning subject is invalid")

    @staticmethod
    def _empty_document(subject_id: str) -> dict[str, Any]:
        return {
            "learning_format_version": LEARNING_FORMAT_VERSION,
            "subject_id": subject_id,
            "learning_events": [],
            "traits": [],
            "records": [],
        }

    @staticmethod
    def _read_document(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LearningValidationError("unable to read valid learning data") from exc
        if not isinstance(data, dict) or data.get(
            "learning_format_version"
        ) != LEARNING_FORMAT_VERSION:
            raise LearningValidationError("unsupported learning persistence format")
        for key in ("learning_events", "traits", "records"):
            if not isinstance(data.get(key), list):
                raise LearningValidationError(f"learning {key} must be a list")
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
