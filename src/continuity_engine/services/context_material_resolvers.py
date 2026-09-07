from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from continuity_engine.domain.context_routing import (
    ContextCandidateReference,
    ContextPartition,
)
from continuity_engine.domain.errors import (
    ContextCompositionSourceError,
    MemoryNotFoundError,
    StateNotFoundError,
    TimelineReferenceError,
)
from continuity_engine.domain.memory import (
    DerivedSummaryStatus,
    MemoryStatus,
    MemoryTemperature,
    MemoryVisibility,
)
from continuity_engine.domain.timeline import TimelineEventStatus
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.base import MemoryRepository, SubjectStateRepository


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_content(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ExactContextPayload:
    """Source-owned fields returned by an exact resolver; it carries no Authority."""

    source_id: str
    partition: ContextPartition
    stable_source_id: str
    subject_id: str
    environment: str
    version: str
    content_hash: str
    occurred_at: datetime
    content: str
    confidence: float
    provenance_roots: tuple[str, ...]
    protected: bool = False
    protection_role: str | None = None
    conflict_markers: tuple[str, ...] = ()
    missing_markers: tuple[str, ...] = ()


class ExactContextMaterialResolver(Protocol):
    source_id: str
    partition: ContextPartition

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload: ...


def _require_reference(
    reference: ContextCandidateReference,
    *,
    source_id: str,
    partition: ContextPartition,
    environment: str,
) -> None:
    if reference.source_id != source_id or reference.partition is not partition:
        raise ContextCompositionSourceError("MATERIAL_PROVENANCE_INVALID")
    if reference.environment != environment:
        raise ContextCompositionSourceError("SOURCE_ENVIRONMENT_MISMATCH")


class SubjectStateMaterialResolver:
    source_id = "engine.subject-state"
    partition = ContextPartition.SUBJECT_STATE

    def __init__(self, repository: SubjectStateRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload:
        _require_reference(
            reference,
            source_id=self.source_id,
            partition=self.partition,
            environment=self._environment,
        )
        try:
            state = self._repository.load(reference.subject_id)
        except StateNotFoundError as exc:
            raise ContextCompositionSourceError("SOURCE_MISSING") from exc
        if state.subject_id != reference.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        expected_version = f"revision:{state.revision}"
        section = reference.stable_id.rsplit(":", 1)[-1]
        document = state.to_dict()
        if section not in {
            "identity",
            "relationship",
            "continuity",
            "temporal",
            "intentions",
            "emotion_state",
        } or section not in document:
            raise ContextCompositionSourceError("SOURCE_MISSING")
        content = document[section]
        expected_hash = _canonical_hash(content)
        if reference.version != expected_version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if reference.content_hash != expected_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        protected = section in {"identity", "continuity", "relationship"}
        return ExactContextPayload(
            self.source_id,
            self.partition,
            reference.stable_id,
            state.subject_id,
            self._environment,
            expected_version,
            expected_hash,
            state.temporal.updated_at,
            _canonical_content(content),
            1.0,
            (f"subject-state:{state.subject_id}:revision:{state.revision}:{section}",),
            protected,
            section if protected else None,
        )


class MemoryMaterialResolver:
    source_id = "engine.memory"
    partition = ContextPartition.MEMORY

    def __init__(self, repository: MemoryRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload:
        _require_reference(
            reference,
            source_id=self.source_id,
            partition=self.partition,
            environment=self._environment,
        )
        try:
            memory = self._repository.load_memory(
                reference.subject_id, reference.stable_id
            )
        except MemoryNotFoundError as exc:
            raise ContextCompositionSourceError("SOURCE_MISSING") from exc
        version = f"revision:{memory.revision}"
        if memory.subject_id != reference.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        if memory.environment != self._environment:
            raise ContextCompositionSourceError("SOURCE_ENVIRONMENT_MISMATCH")
        if (
            not memory.is_available
            or not self._repository.current_usable(reference.subject_id,memory.memory_id)
            or (memory.temperature is MemoryTemperature.ARCHIVED and memory.lifecycle is None)
        ):
            raise ContextCompositionSourceError("SOURCE_STATUS_INELIGIBLE")
        if memory.visibility is not MemoryVisibility.ENGINE_PRIVATE:
            raise ContextCompositionSourceError("SOURCE_VISIBILITY_DENIED")
        if version != reference.version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if memory.canonical_hash() != reference.content_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        return ExactContextPayload(
            self.source_id,
            self.partition,
            memory.memory_id,
            memory.subject_id,
            memory.environment,
            version,
            memory.canonical_hash(),
            memory.occurred_at,
            memory.content,
            memory.confidence * memory.effective_weight,
            tuple(memory.root_evidence_ids),
            conflict_markers=(
                ("MEMORY_CONFLICT_PENDING",)
                if "conflict" in {item.casefold() for item in memory.tags}
                else ()
            ),
        )


class DerivedSummaryMaterialResolver:
    source_id = "engine.derived-summary"
    partition = ContextPartition.DERIVED_SUMMARY

    def __init__(self, repository: MemoryRepository, *, environment: str) -> None:
        self._repository = repository
        self._environment = environment

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload:
        _require_reference(
            reference,
            source_id=self.source_id,
            partition=self.partition,
            environment=self._environment,
        )
        try:
            summary = self._repository.load_summary(
                reference.subject_id, reference.stable_id
            )
        except MemoryNotFoundError as exc:
            raise ContextCompositionSourceError("SOURCE_MISSING") from exc
        version = f"version:{summary.summary_version}"
        if summary.subject_id != reference.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        if summary.environment != self._environment:
            raise ContextCompositionSourceError("SOURCE_ENVIRONMENT_MISMATCH")
        if summary.status is not DerivedSummaryStatus.ACTIVE:
            raise ContextCompositionSourceError("SOURCE_STATUS_INELIGIBLE")
        if any(not self._repository.current_usable(reference.subject_id,identifier) for identifier in summary.source_memory_ids):
            raise ContextCompositionSourceError('SUMMARY_SOURCE_INELIGIBLE')
        if version != reference.version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if summary.canonical_hash() != reference.content_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        return ExactContextPayload(
            self.source_id,
            self.partition,
            summary.summary_id,
            summary.subject_id,
            summary.environment,
            version,
            summary.canonical_hash(),
            summary.time_range.end_at,
            summary.content,
            summary.confidence * self._repository.summary_weight(summary),
            tuple(summary.root_evidence_ids),
        )


class TimelineMaterialResolver:
    source_id = "engine.timeline"
    partition = ContextPartition.TIMELINE

    def __init__(self, timeline: TimelineService, *, environment: str, memory_repository=None) -> None:
        self._timeline = timeline
        self._environment = environment
        self._memory = memory_repository

    def resolve(self, reference: ContextCandidateReference) -> ExactContextPayload:
        _require_reference(
            reference,
            source_id=self.source_id,
            partition=self.partition,
            environment=self._environment,
        )
        try:
            entry = self._timeline.load_entry(
                reference.subject_id, reference.stable_id
            )
        except TimelineReferenceError as exc:
            raise ContextCompositionSourceError("SOURCE_MISSING") from exc
        version = f"update:{entry.update_id}"
        if entry.subject_id != reference.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        if entry.status is not TimelineEventStatus.ACTIVE:
            raise ContextCompositionSourceError("SOURCE_STATUS_INELIGIBLE")
        weight=(self._memory.event_recall_weights(reference.subject_id).get(reference.stable_id,1.0)
                if self._memory is not None else 1.0)
        if weight<=0:
            raise ContextCompositionSourceError('SOURCE_MEMORY_LIFECYCLE_EXCLUDED')
        if version != reference.version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if entry.event.canonical_hash() != reference.content_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        roots = tuple(
            dict.fromkeys(
                (f"event:{entry.event.event_id}",)
                + tuple(item.evidence_id for item in entry.event.evidence)
            )
        )
        return ExactContextPayload(
            self.source_id,
            self.partition,
            entry.event.event_id,
            entry.subject_id,
            self._environment,
            version,
            entry.event.canonical_hash(),
            entry.event.occurred_at,
            entry.event.content,
            weight,
            roots,
        )
