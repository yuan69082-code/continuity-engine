from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from threading import RLock
from functools import wraps
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
    MemoryKind,
    MemoryLineageRecord,
    MemoryLineageType,
    MemoryRecord,
    MemoryStatus,
    MemoryTemperature,
    MemoryVisibility,
    MemoryLifecycle,
    MemoryLifecycleSignal,
)


MEMORY_FORMAT_VERSION = 1
_QUERY_TERM = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")
_MEMORY_TRANSACTION = RLock()


def _write_transaction(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        # Same local process: protect read/validate/append/replace as one operation.
        with _MEMORY_TRANSACTION:
            return method(*args, **kwargs)
    return wrapped


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

    @_write_transaction
    def initialize_empty(self, subject_id: str) -> None:
        """Explicit initialization; ordinary reads never create a document."""
        if self._load_if_exists(subject_id) is None:
            self._write_document(self._path(subject_id), self._empty_document(subject_id))

    @_write_transaction
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

    @_write_transaction
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
        latest={m.memory_id:m for m in memories}
        current=latest.get(memory.memory_id)
        if current is not None and (
                (memory.revision<=current.revision and memory.canonical_hash()!=current.canonical_hash())
                or not self._usable_in(latest,current.memory_id)):
            raise MemoryValidationError('new consolidation cannot alias stale or unavailable material')
        if any(not self._usable_in(latest,m.memory_id)
               and set(m.root_evidence_ids).intersection(memory.root_evidence_ids) for m in latest.values()):
            raise MemoryValidationError('new consolidation uses currently unavailable root evidence')
        self._append_memory(memories, memory)
        operations.append(operation)
        data["memory_records"] = [item.to_dict() for item in memories]
        data["consolidation_operations"] = [item.to_dict() for item in operations]
        self._write_document(path, data)
        return True

    def load_memory(self, subject_id: str, memory_id: str) -> MemoryRecord:
        memories = [m for m in self.list_memories(subject_id,include_inactive=True) if m.memory_id==memory_id]
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
        self._project_consumption_weights(latest)
        records = sorted(
            latest.values(), key=lambda item: (item.occurred_at, item.memory_id)
        )
        if include_inactive:
            return records
        # Legacy enumeration includes temperature archives; ordinary query/retriever
        # still excludes them. Explicit P12 inactive states are never ordinary input.
        return [item for item in records if item.status is MemoryStatus.ACTIVE
                and (item.lifecycle is None and not item.source_memory_ids and item.effective_weight > 0
                     or self._usable_in(latest,item.memory_id))]

    def query_memories(
        self,
        subject_id: str,
        *,
        environment: str,
        status: MemoryStatus,
        visibility: MemoryVisibility,
        excluded_temperatures: tuple[MemoryTemperature, ...],
        query_terms: tuple[str, ...],
        preferred_kinds: tuple[MemoryKind, ...],
        limit: int,
    ) -> list[MemoryRecord]:
        """Return a bounded, deterministic read-only window from Memory authority.

        The atomic P04 document is still fully integrity-checked on load, but P05
        never receives an unbounded list and cannot turn this lookup into a second
        store or authority.
        """

        self._require_boundary(subject_id, environment)
        self._require_query_limit(limit)
        effective_status = (
            status if isinstance(status, MemoryStatus) else MemoryStatus(status)
        )
        effective_visibility = (
            visibility
            if isinstance(visibility, MemoryVisibility)
            else MemoryVisibility(visibility)
        )
        excluded = {
            item
            if isinstance(item, MemoryTemperature)
            else MemoryTemperature(item)
            for item in excluded_temperatures
        }
        preferred = {
            item if isinstance(item, MemoryKind) else MemoryKind(item)
            for item in preferred_kinds
        }
        terms = self._normalize_query_terms(query_terms)
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        latest: dict[str, MemoryRecord] = {}
        for raw in data["memory_records"]:
            memory = MemoryRecord.from_dict(raw)
            latest[memory.memory_id] = memory
        self._project_consumption_weights(latest)
        eligible = (
            item
            for item in latest.values()
            if item.environment == environment
            and item.status is effective_status
            and (effective_status is not MemoryStatus.ACTIVE or self._usable_in(latest,item.memory_id))
            and item.visibility is effective_visibility
            and (item.temperature not in excluded or item.lifecycle is MemoryLifecycle.ACTIVE)
        )
        return sorted(
            eligible,
            key=lambda item: (
                -max(
                    1.0 if item.kind in preferred else 0.0,
                    self._lexical_query_score(
                        terms,
                        item.content,
                        item.tags,
                        item.scope,
                        item.kind.value,
                    ),
                    ) * item.effective_weight,
                    -item.importance * item.effective_weight,
                    -item.activation * item.effective_weight,
                -item.occurred_at.timestamp(),
                item.memory_id,
                item.revision,
            ),
        )[:limit]

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

    @_write_transaction
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

    def query_summaries(
        self,
        subject_id: str,
        *,
        environment: str,
        status: DerivedSummaryStatus,
        query_terms: tuple[str, ...],
        preferred_scope_terms: tuple[str, ...],
        limit: int,
    ) -> list[DerivedSummary]:
        """Return a bounded deterministic DerivedSummary window."""

        self._require_boundary(subject_id, environment)
        self._require_query_limit(limit)
        effective_status = (
            status
            if isinstance(status, DerivedSummaryStatus)
            else DerivedSummaryStatus(status)
        )
        terms = self._normalize_query_terms(query_terms)
        preferred = self._normalize_query_terms(preferred_scope_terms)
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        latest: dict[str, DerivedSummary] = {}
        memories={m.memory_id:m for m in (MemoryRecord.from_dict(x) for x in data['memory_records'])}
        for raw in data["derived_summaries"]:
            summary = DerivedSummary.from_dict(raw)
            summary.retrieval_weight=self._summary_weight_in(memories,summary)
            latest[summary.summary_id] = summary
        eligible = (
            item
            for item in latest.values()
            if item.environment == environment and item.status is effective_status
            and (effective_status is not DerivedSummaryStatus.ACTIVE or item.retrieval_weight > 0)
        )
        return sorted(
            eligible,
            key=lambda item: (
                -max(
                    1.0
                    if preferred
                    and preferred.intersection(
                        self._normalize_query_terms((item.scope, item.summary_type))
                    )
                    else 0.0,
                    self._lexical_query_score(
                        terms,
                        item.content,
                        item.scope,
                        item.summary_type,
                    ),
                ),
                -item.confidence * item.retrieval_weight,
                -item.generated_at.timestamp(),
                item.summary_id,
                item.summary_version,
            ),
        )[:limit]

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

    @_write_transaction
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

    @staticmethod
    def _require_query_limit(limit: int) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise MemoryValidationError("memory query limit must be positive")

    @staticmethod
    def _normalize_query_terms(values: tuple[str, ...]) -> set[str]:
        if not isinstance(values, tuple) or any(
            not isinstance(item, str) for item in values
        ):
            raise MemoryValidationError("memory query terms must be strings")
        return {
            term
            for value in values
            for term in _QUERY_TERM.findall(value.casefold())
            if term.strip()
        }

    @classmethod
    def _lexical_query_score(cls, terms: set[str], *values: object) -> float:
        if not terms:
            return 0.0
        actual = cls._normalize_query_terms(
            tuple(
                str(item)
                for value in values
                for item in (value if isinstance(value, (list, tuple, set)) else (value,))
            )
        )
        return round(len(terms.intersection(actual)) / len(terms), 6)

    def _append_memory(self, records: list[MemoryRecord], memory: MemoryRecord) -> bool:
        if memory.historical_only:
            raise MemoryValidationError('historical receipt is not current material')
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
            if (memory.source_memory_bindings is not None
                    and (current is None or memory.source_memory_bindings!=current.source_memory_bindings)
                    and memory.source_memory_bindings[identifier]!=source.canonical_hash()):
                raise MemoryValidationError('source memory current version/hash mismatch')
        if not set(memory.root_evidence_ids).issubset(source_roots):
            raise MemoryValidationError("memory root evidence is not traceable to its source chain")
        if current is None:
            latest={m.memory_id:m for m in records}
            if any(not item.is_available
                   and set(item.root_evidence_ids).intersection(memory.root_evidence_ids) for item in latest.values()):
                raise MemoryValidationError('unavailable evidence cannot create a new memory alias')
            if memory.revision != 0:
                raise MemoryValidationError("new memory must start at revision zero")
        else:
            self._require_lifecycle_continuity(current,memory)
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
            if current.status is not MemoryStatus.ACTIVE or current.effective_lifecycle is MemoryLifecycle.DELETED:
                raise MemoryValidationError("terminal memory cannot be revised in place")
        records.append(memory)
        return True

    @staticmethod
    def _require_lifecycle_continuity(previous, successor):
        fields=('lifecycle','retrieval_weight','weight_updated_at','lifecycle_command_id')
        if (previous.lifecycle_command_id is not None
                and any(getattr(previous,field) is not None and getattr(successor,field) is None for field in fields)):
            raise MemoryValidationError('governed memory successor cannot discard lifecycle history')

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
        known_memory_hashes: dict[str, set[str]] = {}
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
                if (memory.source_memory_bindings is not None
                        and memory.source_memory_bindings[identifier] not in known_memory_hashes.get(identifier,set())):
                    raise MemoryPersistenceError('memory source version/hash is missing or forward')
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
            known_memory_hashes.setdefault(memory.memory_id,set()).add(memory.canonical_hash())
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
            if record.signal is MemoryLifecycleSignal.COMMAND:
                self._validate_lifecycle_lineage(record, memory_versions)
                seen_lineage.add(record.lineage_id)
                continue
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
            if memory.lifecycle_command_id is not None:
                matches = [r for r in lineage if r.lineage_id == memory.lifecycle_command_id
                           and r.signal is MemoryLifecycleSignal.COMMAND
                           and r.target_memory_id == memory.memory_id]
                if len(matches) != 1:
                    raise MemoryPersistenceError('memory lifecycle change lacks lineage')
                if memory.revision == 0:
                    raise MemoryPersistenceError('first memory cannot carry lifecycle history')
                previous=memory_versions[(memory.memory_id,memory.revision-1)]
                fields=('lifecycle','retrieval_weight','weight_updated_at','lifecycle_command_id')
                if any(getattr(previous,f)!=getattr(memory,f) for f in fields):
                    if matches[0].command['input']['expected_revision'] != memory.revision-1:
                        raise MemoryPersistenceError('lifecycle transition lacks exact command binding')
            elif any(x is not None for x in (memory.lifecycle,memory.retrieval_weight,memory.weight_updated_at)):
                raise MemoryPersistenceError('lifecycle fields lack a command')
            if memory.revision:
                previous=memory_versions[(memory.memory_id,memory.revision-1)]
                try:
                    self._require_lifecycle_continuity(previous,memory)
                except MemoryValidationError as exc:
                    raise MemoryPersistenceError('governed memory history was downgraded') from exc
                if previous.effective_lifecycle is MemoryLifecycle.DELETED:
                    raise MemoryPersistenceError('deleted memory cannot have a subsequent revision')
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

    @staticmethod
    def _validate_lifecycle_lineage(record, versions):
        from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand, lifecycle_result
        try:
            body=record.command
            if set(body) != {'input','input_hash','result_hash'}:
                raise MemoryValidationError('invalid lifecycle binding fields')
            command=MemoryLifecycleCommand.from_dict(body['input'])
            before=versions[(record.target_memory_id, command.expected_revision)]
            after=versions[(record.target_memory_id, command.expected_revision+1)]
            if (command.command_id!=record.lineage_id or command.subject_id!=record.subject_id
                    or command.environment!=record.environment or body['input_hash']!=command.canonical_hash()
                    or set(record.root_evidence_ids)!=set(before.root_evidence_ids)
                    or not command.issued_at <= record.recorded_at < command.expires_at):
                raise MemoryValidationError('lifecycle lineage identity mismatch')
            expected=lifecycle_result(before,command,record.recorded_at)
            if after.canonical_hash()!=expected.canonical_hash() or body['result_hash']!=after.canonical_hash():
                raise MemoryValidationError('lifecycle result binding mismatch')
        except (KeyError,TypeError,ValueError,MemoryValidationError) as exc:
            raise MemoryPersistenceError('invalid lifecycle lineage') from exc

    @staticmethod
    def _usable_in(records, identifier, seen=frozenset(), check_self=True):
        if not seen:
            JsonMemoryRepository._project_consumption_weights(records)
        m=records.get(identifier)
        if m is None or identifier in seen or (check_self and not m.is_available): return False
        # History/restore may disregard this item's temporary inactive state,
        # but cannot bypass a deleted root through another surviving Memory ID.
        if not check_self and any(item.lifecycle is MemoryLifecycle.DELETED
                and set(item.root_evidence_ids).intersection(m.root_evidence_ids) for item in records.values()):
            return False
        for parent_id in m.source_memory_ids:
            parent=records.get(parent_id)
            if parent is None: return False
            if m.source_memory_bindings is not None:
                if m.source_memory_bindings[parent_id]!=parent.canonical_hash(): return False
            elif parent.lifecycle_command_id is not None:
                return False
            if not JsonMemoryRepository._usable_in(records,parent_id,seen|{identifier}): return False
        return True

    def current_usable(self, subject_id: str, memory_id: str, *, include_self=True) -> bool:
        """Recheck current transitive Memory sources; reads never persist activation."""
        records={m.memory_id:m for m in self.list_memories(subject_id,include_inactive=True)}
        return self._usable_in(records,memory_id,check_self=include_self)

    def summary_weight(self, summary):
        data=self._load_if_exists(summary.subject_id)
        if data is None: return 0.0
        records={m.memory_id:m for m in (MemoryRecord.from_dict(x) for x in data['memory_records'])}
        return self._summary_weight_in(records,summary)

    def event_recall_weights(self, subject_id):
        """Ordinary C1 material policy only; never modify or delete raw Event history."""
        data=self._load_if_exists(subject_id)
        if data is None: return {}
        latest={m.memory_id:m for m in (MemoryRecord.from_dict(x) for x in data['memory_records'])}
        weights={}
        for memory in latest.values():
            if memory.lifecycle_command_id is None and memory.retrieval_weight is None and memory.status is MemoryStatus.ACTIVE:
                continue
            weight=memory.effective_weight if self._usable_in(latest,memory.memory_id) else 0.0
            for root in memory.root_evidence_ids:
                if root.startswith('event:'):
                    weights[root[6:]]=min(weights.get(root[6:],1.0),weight)
        return weights

    @staticmethod
    def _project_consumption_weights(records):
        # The existing root identities share an explicit use ceiling regardless of
        # Memory ID/scope or intermediate aliases. Do not duplicate the same root's
        # decay factor, persist another authority, or change evidence confidence.
        ceilings={}
        for memory in records.values():
            own=1.0 if memory.retrieval_weight is None else memory.retrieval_weight
            if memory.lifecycle in (MemoryLifecycle.INACTIVE,MemoryLifecycle.ARCHIVED,MemoryLifecycle.DELETED):
                own=0.0
            if own<1.0:
                for root in memory.root_evidence_ids:
                    ceilings[root]=min(ceilings.get(root,1.0),own)
        for memory in records.values():
            memory.consumption_weight=min((ceilings.get(root,1.0) for root in memory.root_evidence_ids),default=1.0)

    @staticmethod
    def _summary_weight_in(records,summary):
        JsonMemoryRepository._project_consumption_weights(records)
        if not all(JsonMemoryRepository._usable_in(records,x) for x in summary.source_memory_ids): return 0.0
        return min(records[x].effective_weight for x in summary.source_memory_ids)

    @_write_transaction
    def apply_lifecycle(self, command, evaluate):
        """Reuse the one Memory document and lineage; no separate request ledger."""
        subject_id=command.subject_id
        self._require_boundary(subject_id,command.environment)
        data=self._load_or_empty(subject_id)
        memories=[MemoryRecord.from_dict(x) for x in data['memory_records']]
        current=self._latest_memory(memories,command.memory_id)
        if current is None: raise MemoryNotFoundError(command.memory_id)
        lineage=[MemoryLineageRecord.from_dict(x) for x in data['lineage_records']]
        prior=next((r for r in lineage if r.lineage_id==command.command_id),None)
        if prior is not None:
            if (prior.signal is not MemoryLifecycleSignal.COMMAND
                    or prior.command['input_hash']!=command.canonical_hash()):
                raise MemoryIdentityConflictError('lifecycle command identity conflict')
            # Historical receipt only, with CURRENT material (never old active payload).
            evaluate(current, replay=True)
            if self._load_or_empty(subject_id)!=data:
                raise MemoryValidationError('memory changed during lifecycle replay callback')
            return current, True
        updated,now=evaluate(current,replay=False)
        # RLock permits a callback to commit another legitimate command. Keep that
        # committed fact and reject this stale outer attempt before any write.
        if self._load_or_empty(subject_id)!=data:
            raise MemoryValidationError('memory changed during lifecycle callback; outer command not committed')
        self._append_memory(memories,updated)
        affected={current.memory_id}
        if command.action.value in ('deactivate','archive','delete','restore'):
            affected.update(m.memory_id for m in memories
                            if set(m.root_evidence_ids).intersection(current.root_evidence_ids))
        changed=True
        while changed:
            next_ids={m.memory_id for m in memories if affected.intersection(m.source_memory_ids)}
            changed=not next_ids.issubset(affected)
            affected.update(next_ids)
        summaries=[DerivedSummary.from_dict(x) for x in data['derived_summaries']]
        latest={s.summary_id:s for s in summaries}
        for s in latest.values():
            if s.status is DerivedSummaryStatus.ACTIVE and affected.intersection(s.source_memory_ids):
                payload=s.to_dict()
                payload.update(summary_version=s.summary_version+1,supersedes_version=s.summary_version,
                               status=DerivedSummaryStatus.INVALIDATED.value,
                               invalidation_reason='MEMORY_LIFECYCLE_CHANGED',generated_at=now.isoformat())
                self._append_summary(summaries,DerivedSummary.from_dict(payload),memories)
        lineage.append(MemoryLineageRecord(command.command_id,subject_id,command.environment,
            current.memory_id,MemoryLifecycleSignal.COMMAND,None,list(current.root_evidence_ids),now,
            command={'input':command.to_dict(),'input_hash':command.canonical_hash(),'result_hash':updated.canonical_hash()}))
        data.update(memory_records=[m.to_dict() for m in memories],
                    derived_summaries=[s.to_dict() for s in summaries],lineage_records=[r.to_dict() for r in lineage])
        self._write_document(self._path(subject_id),data)
        return updated,False

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
