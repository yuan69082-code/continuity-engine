from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.errors import (
    MemoryIdentityConflictError,
    MemoryLineageError,
    MemoryNotFoundError,
    MemoryPersistenceError,
    MemoryValidationError,
)
from continuity_engine.domain.memory import (
    DerivedSummary,
    DerivedSummaryStatus,
    MemoryConsolidationOperation,
    MemoryLineageRecord,
    MemoryLineageType,
    MemoryRecord,
    MemoryStatus,
)


MEMORY_FORMAT_VERSION = 1


class JsonMemoryRepository:
    """Atomic, subject/environment isolated P04 Memory authority.

    Derived summaries live in the same integrity-checked document and remain
    rebuildable views.  The repository never reads Event or SubjectState data.
    """

    def __init__(self, root: Path | str, *, environment: str) -> None:
        if environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise MemoryValidationError("memory repository environment is unsupported")
        requested = Path(root)
        if requested.exists() and requested.is_symlink():
            raise MemoryPersistenceError("memory repository root cannot be a symbolic link")
        self.root = requested.resolve(strict=False) / "memory" / environment.lower()
        self.environment = environment

    @staticmethod
    def _identity_hash(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise MemoryValidationError(f"{field_name} must be non-empty")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _path(self, subject_id: str) -> Path:
        return self.root / f"{self._identity_hash(subject_id, 'subject_id')}.json"

    def save_memory(self, memory: MemoryRecord) -> bool:
        self._require_boundary(memory.subject_id, memory.environment)
        path = self._path(memory.subject_id)
        data = self._load_or_empty(memory.subject_id)
        memories = [MemoryRecord.from_dict(item) for item in data["memory_records"]]
        changed = self._append_memory(memories, memory)
        if not changed:
            return False
        data["memory_records"] = [item.to_dict() for item in memories]
        self._write_document(path, data)
        return True

    def save_consolidation(
        self,
        memory: MemoryRecord,
        operation: MemoryConsolidationOperation,
    ) -> bool:
        """Atomically persist a Memory result and its durable operation identity."""

        self._require_boundary(memory.subject_id, memory.environment)
        self._require_boundary(operation.subject_id, operation.environment)
        if operation.subject_id != memory.subject_id:
            raise MemoryIdentityConflictError(
                "consolidation operation and result subjects must match"
            )
        if operation.result_memory_id != memory.memory_id:
            raise MemoryIdentityConflictError(
                "consolidation operation result identity does not match memory"
            )
        if operation.result_memory_revision != memory.revision:
            raise MemoryIdentityConflictError(
                "consolidation operation result revision does not match memory"
            )
        if operation.result_memory_canonical_hash != memory.canonical_hash():
            raise MemoryIdentityConflictError(
                "consolidation operation result hash does not match memory"
            )
        path = self._path(memory.subject_id)
        data = self._load_or_empty(memory.subject_id)
        memories = [MemoryRecord.from_dict(item) for item in data["memory_records"]]
        try:
            operations = [
                MemoryConsolidationOperation.from_dict(item)
                for item in data["consolidation_operations"]
            ]
        except MemoryValidationError as exc:
            raise MemoryPersistenceError(
                "invalid consolidation operation in persistence"
            ) from exc
        existing = next(
            (
                item
                for item in operations
                if item.consolidation_id == operation.consolidation_id
            ),
            None,
        )
        if existing is not None:
            if existing.canonical_hash() == operation.canonical_hash():
                return False
            raise MemoryIdentityConflictError(
                f"consolidation identity conflict: {operation.consolidation_id}"
            )
        self._validate_operation_source_chain(operation, memories)
        self._append_memory(memories, memory)
        operations.append(operation)
        data["memory_records"] = [item.to_dict() for item in memories]
        data["consolidation_operations"] = [item.to_dict() for item in operations]
        self._write_document(path, data)
        return True

    def load_memory(self, subject_id: str, memory_id: str) -> MemoryRecord:
        memories = self.memory_history(subject_id, memory_id)
        if not memories:
            raise MemoryNotFoundError(f"memory not found: {memory_id}")
        return memories[-1]

    def list_memories(
        self,
        subject_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[MemoryRecord]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        latest: dict[str, MemoryRecord] = {}
        for raw in data["memory_records"]:
            memory = MemoryRecord.from_dict(raw)
            latest[memory.memory_id] = memory
        records = sorted(
            latest.values(), key=lambda item: (item.occurred_at, item.memory_id)
        )
        if include_inactive:
            return records
        return [item for item in records if item.status is MemoryStatus.ACTIVE]

    def memory_history(self, subject_id: str, memory_id: str) -> list[MemoryRecord]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        result = [
            MemoryRecord.from_dict(item)
            for item in data["memory_records"]
            if item.get("memory_id") == memory_id
        ]
        return sorted(result, key=lambda item: item.revision)

    def save_summary(self, summary: DerivedSummary) -> bool:
        self._require_boundary(summary.subject_id, summary.environment)
        path = self._path(summary.subject_id)
        data = self._load_or_empty(summary.subject_id)
        summaries = [DerivedSummary.from_dict(item) for item in data["derived_summaries"]]
        memories = [MemoryRecord.from_dict(item) for item in data["memory_records"]]
        changed = self._append_summary(summaries, summary, memories)
        if not changed:
            return False
        data["derived_summaries"] = [item.to_dict() for item in summaries]
        self._write_document(path, data)
        return True

    def load_summary(self, subject_id: str, summary_id: str) -> DerivedSummary:
        history = self.summary_history(subject_id, summary_id)
        if not history:
            raise MemoryNotFoundError(f"derived summary not found: {summary_id}")
        return history[-1]

    def list_summaries(
        self,
        subject_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[DerivedSummary]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        latest: dict[str, DerivedSummary] = {}
        for raw in data["derived_summaries"]:
            summary = DerivedSummary.from_dict(raw)
            latest[summary.summary_id] = summary
        records = sorted(latest.values(), key=lambda item: item.summary_id)
        if include_inactive:
            return records
        return [item for item in records if item.status is DerivedSummaryStatus.ACTIVE]

    def summary_history(
        self,
        subject_id: str,
        summary_id: str,
    ) -> list[DerivedSummary]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        result = [
            DerivedSummary.from_dict(item)
            for item in data["derived_summaries"]
            if item.get("summary_id") == summary_id
        ]
        return sorted(result, key=lambda item: item.summary_version)

    def list_lineage(self, subject_id: str) -> list[MemoryLineageRecord]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        return [MemoryLineageRecord.from_dict(item) for item in data["lineage_records"]]

    def apply_propagation(
        self,
        memory: MemoryRecord,
        lineage: MemoryLineageRecord,
        summaries: list[DerivedSummary],
    ) -> bool:
        self._require_boundary(memory.subject_id, memory.environment)
        self._require_boundary(lineage.subject_id, lineage.environment)
        if memory.subject_id != lineage.subject_id:
            raise MemoryLineageError("memory and lineage subjects must match")
        path = self._path(memory.subject_id)
        data = self._load_or_empty(memory.subject_id)
        memories = [MemoryRecord.from_dict(item) for item in data["memory_records"]]
        summary_records = [
            DerivedSummary.from_dict(item) for item in data["derived_summaries"]
        ]
        lineage_records = [
            MemoryLineageRecord.from_dict(item) for item in data["lineage_records"]
        ]
        existing = next(
            (item for item in lineage_records if item.lineage_id == lineage.lineage_id),
            None,
        )
        if existing is not None:
            if existing.canonical_hash() == lineage.canonical_hash():
                return False
            raise MemoryIdentityConflictError(
                f"memory lineage identity conflict: {lineage.lineage_id}"
            )
        current = self._latest_memory(memories, lineage.target_memory_id)
        if current is None:
            raise MemoryLineageError(
                f"memory lineage target does not exist: {lineage.target_memory_id}"
            )
        if memory.memory_id != current.memory_id:
            raise MemoryLineageError("propagation must update its target memory")
        expected_status = {
            MemoryLineageType.CORRECTION: MemoryStatus.CORRECTED,
            MemoryLineageType.REVOCATION: MemoryStatus.REVOKED,
            MemoryLineageType.DELETION: MemoryStatus.DELETED,
        }[lineage.signal]
        if memory.status is not expected_status or memory.lineage_event_id != lineage.source_event_id:
            raise MemoryLineageError("propagated memory status does not match lineage signal")
        self._append_memory(memories, memory)
        for summary in summaries:
            if summary.subject_id != memory.subject_id:
                raise MemoryLineageError("propagated summary belongs to another subject")
            if memory.memory_id not in summary.source_memory_ids:
                raise MemoryLineageError("propagated summary does not reference target memory")
            if summary.status is DerivedSummaryStatus.ACTIVE:
                raise MemoryLineageError("propagation cannot leave a dependent summary active")
            self._append_summary(summary_records, summary, memories)
        lineage_records.append(lineage)
        data["memory_records"] = [item.to_dict() for item in memories]
        data["derived_summaries"] = [item.to_dict() for item in summary_records]
        data["lineage_records"] = [item.to_dict() for item in lineage_records]
        self._write_document(path, data)
        return True

    def find_by_consolidation_id(
        self,
        subject_id: str,
        consolidation_id: str,
    ) -> MemoryRecord | None:
        operation = self.load_consolidation_operation(subject_id, consolidation_id)
        if operation is not None:
            matches = [
                item
                for item in self.memory_history(subject_id, operation.result_memory_id)
                if item.revision == operation.result_memory_revision
            ]
            if len(matches) != 1:
                raise MemoryPersistenceError(
                    "consolidation operation result revision is unavailable"
                )
            result = matches[0]
            if result.canonical_hash() != operation.result_memory_canonical_hash:
                raise MemoryPersistenceError(
                    "consolidation operation result hash does not match history"
                )
            return result
        data = self._load_if_exists(subject_id)
        if data is None:
            return None
        matches = [
            MemoryRecord.from_dict(item)
            for item in data["memory_records"]
            if item.get("consolidation_id") == consolidation_id
        ]
        return matches[-1] if matches else None

    def load_consolidation_operation(
        self,
        subject_id: str,
        consolidation_id: str,
    ) -> MemoryConsolidationOperation | None:
        data = self._load_if_exists(subject_id)
        if data is None:
            return None
        matches = [
            MemoryConsolidationOperation.from_dict(item)
            for item in data["consolidation_operations"]
            if item.get("consolidation_id") == consolidation_id
        ]
        return matches[-1] if matches else None

    def _load_if_exists(self, subject_id: str) -> dict[str, Any] | None:
        path = self._path(subject_id)
        if not path.is_file():
            return None
        return self._read_document(path, subject_id)

    def _load_or_empty(self, subject_id: str) -> dict[str, Any]:
        return self._load_if_exists(subject_id) or self._empty_document(subject_id)

    def _require_boundary(self, subject_id: str, environment: str) -> None:
        if environment != self.environment:
            raise MemoryValidationError("memory environment does not match repository")
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise MemoryValidationError("memory subject_id must be non-empty")

    def _append_memory(self, records: list[MemoryRecord], memory: MemoryRecord) -> bool:
        existing_revision = next(
            (
                item
                for item in records
                if item.memory_id == memory.memory_id and item.revision == memory.revision
            ),
            None,
        )
        if existing_revision is not None:
            if existing_revision.canonical_hash() == memory.canonical_hash():
                return False
            raise MemoryIdentityConflictError(
                f"memory identity conflict: {memory.memory_id}@{memory.revision}"
            )
        current = self._latest_memory(records, memory.memory_id)
        known_ids = {item.memory_id for item in records}
        if any(identifier not in known_ids for identifier in memory.source_memory_ids):
            raise MemoryValidationError("memory source chain is missing or crosses subjects")
        source_roots = {
            *(f"event:{identifier}" for identifier in memory.source_event_ids),
            *(f"message:{identifier}" for identifier in memory.source_message_ids),
        }
        for identifier in memory.source_memory_ids:
            source = self._latest_memory(records, identifier)
            assert source is not None
            source_roots.update(source.root_evidence_ids)
        if not set(memory.root_evidence_ids).issubset(source_roots):
            raise MemoryValidationError("memory root evidence is not traceable to its source chain")
        if current is None:
            if memory.revision != 0:
                raise MemoryValidationError("new memory must start at revision zero")
        else:
            if memory.revision != current.revision + 1:
                raise MemoryValidationError("memory revision must advance by one")
            if (
                memory.subject_id != current.subject_id
                or memory.environment != current.environment
                or memory.kind is not current.kind
                or memory.memory_version != current.memory_version + 1
            ):
                raise MemoryIdentityConflictError("memory stable identity fields changed")
            if not set(current.root_evidence_ids).issubset(memory.root_evidence_ids):
                raise MemoryValidationError("memory root evidence cannot silently disappear")
            if current.status is not MemoryStatus.ACTIVE:
                raise MemoryValidationError("terminal memory cannot be revised in place")
        records.append(memory)
        return True

    def _append_summary(
        self,
        records: list[DerivedSummary],
        summary: DerivedSummary,
        memories: list[MemoryRecord],
    ) -> bool:
        existing = next(
            (
                item
                for item in records
                if item.summary_id == summary.summary_id
                and item.summary_version == summary.summary_version
            ),
            None,
        )
        if existing is not None:
            if existing.canonical_hash() == summary.canonical_hash():
                return False
            raise MemoryIdentityConflictError(
                f"summary identity conflict: {summary.summary_id}@{summary.summary_version}"
            )
        history = [item for item in records if item.summary_id == summary.summary_id]
        expected_version = 1 if not history else history[-1].summary_version + 1
        if summary.summary_version != expected_version:
            raise MemoryValidationError("summary_version must advance by one")
        if history and summary.supersedes_version != history[-1].summary_version:
            raise MemoryValidationError("summary must reference the preceding version")
        if not history and summary.supersedes_version is not None:
            raise MemoryValidationError("first summary version cannot supersede history")
        memory_ids = {item.memory_id for item in memories}
        if any(identifier not in memory_ids for identifier in summary.source_memory_ids):
            raise MemoryValidationError("summary source memory is missing or crosses subjects")
        source_roots: set[str] = set()
        for identifier in summary.source_memory_ids:
            versions = [item for item in memories if item.memory_id == identifier]
            for version in versions:
                source_roots.update(version.root_evidence_ids)
        if not set(summary.root_evidence_ids).issubset(source_roots):
            raise MemoryValidationError("summary root evidence is not traceable to its memories")
        records.append(summary)
        return True

    @staticmethod
    def _latest_memory(records: list[MemoryRecord], memory_id: str) -> MemoryRecord | None:
        matches = [item for item in records if item.memory_id == memory_id]
        return matches[-1] if matches else None

    @staticmethod
    def _validate_operation_source_chain(
        operation: MemoryConsolidationOperation,
        memories: list[MemoryRecord],
    ) -> None:
        """Validate an operation input against its own prior provenance.

        Alias deduplication may select an existing result Memory, but that
        result cannot supply provenance the candidate itself did not declare.
        """

        candidate = MemoryRecord.from_dict(operation.canonical_input)
        traceable_roots = {
            *(f"event:{identifier}" for identifier in candidate.source_event_ids),
            *(f"message:{identifier}" for identifier in candidate.source_message_ids),
        }
        for source_memory_id in candidate.source_memory_ids:
            eligible = [
                item
                for item in memories
                if item.memory_id == source_memory_id
                and item.subject_id == candidate.subject_id
                and item.environment == candidate.environment
                and item.consolidated_at <= candidate.consolidated_at
            ]
            if not eligible:
                raise MemoryPersistenceError(
                    "consolidation operation source memory is missing, forward, or cross-boundary"
                )
            source = max(eligible, key=lambda item: item.revision)
            traceable_roots.update(source.root_evidence_ids)
        if not set(candidate.root_evidence_ids).issubset(traceable_roots):
            raise MemoryPersistenceError(
                "consolidation operation input evidence is not traceable to its own source chain"
            )

    def _read_document(self, path: Path, subject_id: str) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryPersistenceError("unable to read valid memory data") from exc
        if not isinstance(data, dict):
            raise MemoryPersistenceError("memory document must be an object")
        supplied_hash = data.get("document_hash")
        content = dict(data)
        content.pop("document_hash", None)
        if supplied_hash != self._document_hash(content):
            raise MemoryPersistenceError("memory document integrity check failed")
        self._validate_document(content, subject_id)
        return content

    def _validate_document(self, data: dict[str, Any], subject_id: str) -> None:
        if data.get("memory_format_version") != MEMORY_FORMAT_VERSION:
            raise MemoryPersistenceError("unsupported memory persistence format")
        if data.get("environment") != self.environment or data.get("subject_id") != subject_id:
            raise MemoryPersistenceError("memory subject/environment boundary mismatch")
        for key in (
            "memory_records",
            "consolidation_operations",
            "derived_summaries",
            "lineage_records",
        ):
            if not isinstance(data.get(key), list):
                raise MemoryPersistenceError(f"memory {key} must be a list")
        memories = [MemoryRecord.from_dict(item) for item in data["memory_records"]]
        seen_versions: set[tuple[str, int]] = set()
        latest_revision: dict[str, int] = {}
        known_ids: set[str] = set()
        known_roots: dict[str, set[str]] = {}
        consolidation_inputs: dict[str, str] = {}
        for memory in memories:
            if memory.subject_id != subject_id or memory.environment != self.environment:
                raise MemoryPersistenceError(
                    "memory record subject/environment boundary mismatch"
                )
            self._require_boundary(memory.subject_id, memory.environment)
            identity = (memory.memory_id, memory.revision)
            if identity in seen_versions:
                raise MemoryPersistenceError("duplicate memory version in persistence")
            seen_versions.add(identity)
            expected = latest_revision.get(memory.memory_id, -1) + 1
            if memory.revision != expected:
                raise MemoryPersistenceError("memory revisions are not contiguous")
            if any(item not in known_ids for item in memory.source_memory_ids):
                raise MemoryPersistenceError("memory source chain is forward or cross-subject")
            source_roots = {
                *(f"event:{identifier}" for identifier in memory.source_event_ids),
                *(f"message:{identifier}" for identifier in memory.source_message_ids),
            }
            for identifier in memory.source_memory_ids:
                source_roots.update(known_roots[identifier])
            if not set(memory.root_evidence_ids).issubset(source_roots):
                raise MemoryPersistenceError("memory root evidence chain is not traceable")
            previous_input = consolidation_inputs.get(memory.consolidation_id)
            if (
                previous_input is not None
                and previous_input != memory.consolidation_input_hash
            ):
                raise MemoryPersistenceError("consolidation identity has conflicting input")
            consolidation_inputs[memory.consolidation_id] = memory.consolidation_input_hash or ""
            latest_revision[memory.memory_id] = memory.revision
            known_ids.add(memory.memory_id)
            known_roots.setdefault(memory.memory_id, set()).update(memory.root_evidence_ids)
        try:
            operations = [
                MemoryConsolidationOperation.from_dict(item)
                for item in data["consolidation_operations"]
            ]
        except MemoryValidationError as exc:
            raise MemoryPersistenceError(
                "invalid consolidation operation in persistence"
            ) from exc
        seen_operations: dict[str, MemoryConsolidationOperation] = {}
        first_memories: dict[str, MemoryRecord] = {}
        memory_versions: dict[tuple[str, int], MemoryRecord] = {}
        for memory in memories:
            first_memories.setdefault(memory.memory_id, memory)
            memory_versions[(memory.memory_id, memory.revision)] = memory
        for operation in operations:
            if (
                operation.subject_id != subject_id
                or operation.environment != self.environment
            ):
                raise MemoryPersistenceError(
                    "consolidation operation subject/environment boundary mismatch"
                )
            self._require_boundary(operation.subject_id, operation.environment)
            existing_operation = seen_operations.get(operation.consolidation_id)
            if existing_operation is not None:
                if existing_operation.canonical_hash() != operation.canonical_hash():
                    raise MemoryPersistenceError(
                        "consolidation operation identity has conflicting input"
                    )
                raise MemoryPersistenceError(
                    "duplicate consolidation operation identity in persistence"
                )
            result = memory_versions.get(
                (operation.result_memory_id, operation.result_memory_revision)
            )
            if result is None:
                raise MemoryPersistenceError(
                    "consolidation operation result revision is missing, forward, or cross-subject"
                )
            if result.canonical_hash() != operation.result_memory_canonical_hash:
                raise MemoryPersistenceError(
                    "consolidation operation result hash does not match history"
                )
            if operation.recorded_at < result.consolidated_at:
                raise MemoryPersistenceError(
                    "consolidation operation predates its result memory"
                )
            candidate = MemoryRecord.from_dict(operation.canonical_input)
            if candidate.consolidated_at > operation.recorded_at:
                raise MemoryPersistenceError(
                    "consolidation operation predates its canonical input"
                )
            self._validate_operation_source_chain(operation, memories)
            if (
                candidate.kind is not result.kind
                or candidate.evidence_type is not result.evidence_type
                or candidate.scope != result.scope
                or candidate.content != result.content
                or not set(candidate.root_evidence_ids).issubset(
                    result.root_evidence_ids
                )
            ):
                raise MemoryPersistenceError(
                    "consolidation operation input is not traceable to its result memory"
                )
            seen_operations[operation.consolidation_id] = operation
        summaries = [DerivedSummary.from_dict(item) for item in data["derived_summaries"]]
        summary_versions: dict[str, int] = {}
        seen_summary_versions: set[tuple[str, int]] = set()
        all_roots: dict[str, set[str]] = {}
        for memory in memories:
            all_roots.setdefault(memory.memory_id, set()).update(memory.root_evidence_ids)
        for summary in summaries:
            if summary.subject_id != subject_id or summary.environment != self.environment:
                raise MemoryPersistenceError(
                    "summary subject/environment boundary mismatch"
                )
            self._require_boundary(summary.subject_id, summary.environment)
            identity = (summary.summary_id, summary.summary_version)
            if identity in seen_summary_versions:
                raise MemoryPersistenceError("duplicate summary version in persistence")
            seen_summary_versions.add(identity)
            expected = summary_versions.get(summary.summary_id, 0) + 1
            if summary.summary_version != expected:
                raise MemoryPersistenceError("summary versions are not contiguous")
            if expected > 1 and summary.supersedes_version != expected - 1:
                raise MemoryPersistenceError("summary version lineage is broken")
            if any(item not in known_ids for item in summary.source_memory_ids):
                raise MemoryPersistenceError("summary source is missing or cross-subject")
            traceable = set().union(
                *(all_roots[item] for item in summary.source_memory_ids)
            )
            if not set(summary.root_evidence_ids).issubset(traceable):
                raise MemoryPersistenceError("summary evidence chain is broken")
            summary_versions[summary.summary_id] = summary.summary_version
        lineage = [MemoryLineageRecord.from_dict(item) for item in data["lineage_records"]]
        seen_lineage: set[str] = set()
        for record in lineage:
            if record.subject_id != subject_id or record.environment != self.environment:
                raise MemoryPersistenceError(
                    "lineage subject/environment boundary mismatch"
                )
            self._require_boundary(record.subject_id, record.environment)
            if record.lineage_id in seen_lineage:
                raise MemoryPersistenceError("duplicate lineage identity in persistence")
            if record.target_memory_id not in known_ids:
                raise MemoryPersistenceError("lineage target is missing or cross-subject")
            if record.replacement_memory_id and record.replacement_memory_id not in known_ids:
                raise MemoryPersistenceError("lineage replacement is missing or forward")
            target_first = first_memories[record.target_memory_id]
            if target_first.consolidated_at > record.recorded_at:
                raise MemoryPersistenceError("lineage target is forward in persistence")
            source_root = (
                record.source_event_id
                if record.source_event_id.startswith("event:")
                else f"event:{record.source_event_id}"
            )
            if source_root not in record.root_evidence_ids:
                raise MemoryPersistenceError(
                    "lineage root evidence omits its source event identity"
                )
            target_roots_at_recording = set().union(
                *(
                    set(item.root_evidence_ids)
                    for item in memories
                    if item.memory_id == record.target_memory_id
                    and item.consolidated_at <= record.recorded_at
                )
            )
            allowed_roots = {source_root, *target_roots_at_recording}
            if record.replacement_memory_id:
                replacement_first = first_memories[record.replacement_memory_id]
                if replacement_first.consolidated_at > record.recorded_at:
                    raise MemoryPersistenceError("lineage replacement is forward in persistence")
                allowed_roots.update(
                    set().union(
                        *(
                            set(item.root_evidence_ids)
                            for item in memories
                            if item.memory_id == record.replacement_memory_id
                            and item.consolidated_at <= record.recorded_at
                        )
                    )
                )
            if not set(record.root_evidence_ids).issubset(allowed_roots):
                raise MemoryPersistenceError(
                    "lineage root evidence is not traceable to target or replacement"
                )
            expected_status = {
                MemoryLineageType.CORRECTION: MemoryStatus.CORRECTED,
                MemoryLineageType.REVOCATION: MemoryStatus.REVOKED,
                MemoryLineageType.DELETION: MemoryStatus.DELETED,
            }[record.signal]
            if not any(
                item.memory_id == record.target_memory_id
                and item.status is expected_status
                and item.lineage_event_id == record.source_event_id
                for item in memories
            ):
                raise MemoryPersistenceError(
                    "lineage has no matching append-only terminal memory version"
                )
            seen_lineage.add(record.lineage_id)
        for memory in memories:
            if memory.status is MemoryStatus.ACTIVE:
                continue
            if not any(
                item.target_memory_id == memory.memory_id
                and item.source_event_id == memory.lineage_event_id
                for item in lineage
            ):
                raise MemoryPersistenceError("terminal memory lacks append-only lineage evidence")
        latest_memories = {
            identifier: self._latest_memory(memories, identifier) for identifier in known_ids
        }
        latest_summaries: dict[str, DerivedSummary] = {}
        for summary in summaries:
            latest_summaries[summary.summary_id] = summary
        for summary in latest_summaries.values():
            if summary.status is not DerivedSummaryStatus.ACTIVE:
                continue
            if any(
                latest_memories[identifier] is None
                or latest_memories[identifier].status is not MemoryStatus.ACTIVE
                for identifier in summary.source_memory_ids
            ):
                raise MemoryPersistenceError(
                    "active summary depends on an inactive source memory"
                )

    def _empty_document(self, subject_id: str) -> dict[str, Any]:
        return {
            "memory_format_version": MEMORY_FORMAT_VERSION,
            "environment": self.environment,
            "subject_id": subject_id,
            "memory_records": [],
            "consolidation_operations": [],
            "derived_summaries": [],
            "lineage_records": [],
        }

    @staticmethod
    def _document_hash(data: dict[str, Any]) -> str:
        payload = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    def _write_document(self, path: Path, data: dict[str, Any]) -> None:
        self._validate_document(data, data["subject_id"])
        document = dict(data)
        document["document_hash"] = self._document_hash(data)
        payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
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
