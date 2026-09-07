from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from continuity_engine.domain.errors import MemoryInfluenceError, MemoryValidationError
from continuity_engine.domain.events import JsonValue, StateUpdateRecord
from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryInfluenceRecord,
    MemoryRelevancePolicy,
    MemoryRetrievalRequest,
    MemoryRetrievalResult,
    MemoryTemperature,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.storage.base import MemoryRepository

from .memory_ports import MemoryInfluenceRecorder, MemoryRetriever


_FORMAL_PROVENANCE_FIELDS = frozenset(
    {
        "memory_kind",
        "evidence_type",
        "root_evidence_ids",
        "source_event_ids",
        "source_memory_ids",
        "source_message_ids",
        "visibility",
        "memory_status",
        "memory_temperature",
        "memory_revision",
        "memory_version",
        "memory_environment", "memory_hash", "memory_lifecycle", "memory_weight",
    }
)


class MemoryService:
    """Coordinate retrieval, relevance decisions, and influence reporting.

    This compatibility service has no write authority over formal P04 Memory.
    Retrieval and influence recording remain delegated to injected ports.
    """

    def __init__(
        self,
        retriever: MemoryRetriever,
        influence_recorder: MemoryInfluenceRecorder,
        *,
        relevance_policy: MemoryRelevancePolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._retriever = retriever
        self._influence_recorder = influence_recorder
        self._relevance_policy = relevance_policy or MemoryRelevancePolicy()
        self._clock = clock

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalResult:
        raw_candidates = list(self._retriever.retrieve(request))
        if any(not isinstance(candidate, MemoryCandidate) for candidate in raw_candidates):
            raise MemoryValidationError("memory retriever returned an invalid candidate")

        seen_ids: set[str] = set()
        for candidate in raw_candidates:
            if candidate.memory_id in seen_ids:
                raise MemoryValidationError(
                    f"memory retriever returned a duplicate memory_id: {candidate.memory_id}"
                )
            seen_ids.add(candidate.memory_id)

        decisions = [
            self._relevance_policy.evaluate(request, candidate)
            for candidate in raw_candidates
        ]
        ranked = sorted(
            (decision for decision in decisions if decision.relevant),
            key=lambda decision: (
                decision.relevance_score,
                decision.candidate.occurred_at or request.requested_at,
                decision.candidate.memory_id,
            ),
            reverse=True,
        )
        for decision in ranked[: request.limit]:
            decision.selected = True

        return MemoryRetrievalResult(
            request=request,
            evaluated_at=self._clock(),
            decisions=decisions,
        )

    def record_influence(
        self,
        result: MemoryRetrievalResult,
        *,
        memory_id: str,
        influence_type: str,
        summary: str,
        reason: str,
        affected_fields: Iterable[str] = (),
        state_update: StateUpdateRecord | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> MemoryInfluenceRecord:
        selected = {
            candidate.memory_id: candidate for candidate in result.selected_memories
        }
        if memory_id not in selected:
            raise MemoryInfluenceError(
                "memory influence can only be recorded for a selected relevant memory"
            )

        fields = list(affected_fields)
        related_event_id: str | None = None
        related_update_id: str | None = None
        if state_update is not None:
            if state_update.subject_id != result.request.subject_id:
                raise MemoryInfluenceError(
                    "state update subject does not match the memory retrieval subject"
                )
            fields.extend(change.field_path for change in state_update.changes)
            related_event_id = state_update.event.event_id
            related_update_id = state_update.update_id

        formal_metadata = dict(selected[memory_id].metadata)
        record_metadata = dict(formal_metadata)
        for key, value in (metadata or {}).items():
            if key in _FORMAL_PROVENANCE_FIELDS:
                if key not in formal_metadata or formal_metadata[key] != value:
                    raise MemoryInfluenceError(
                        f"caller metadata conflicts with sealed memory provenance: {key}"
                    )
                continue
            record_metadata[key] = value
        record = MemoryInfluenceRecord.create(
            request_id=result.request.request_id,
            subject_id=result.request.subject_id,
            memory_id=memory_id,
            recorded_at=self._clock(),
            influence_type=influence_type,
            summary=summary,
            reason=reason,
            affected_fields=fields,
            related_event_id=related_event_id,
            related_update_id=related_update_id,
            metadata=record_metadata,
        )
        self._influence_recorder.record_influence(record)
        return record


class RepositoryMemoryRetriever:
    """Read-only adapter from the formal P04 Memory authority to the legacy port."""

    def __init__(self, repository: MemoryRepository, *, enabled: bool = True) -> None:
        self._repository = repository
        self._enabled = enabled

    def retrieve(self, request: MemoryRetrievalRequest) -> list[MemoryCandidate]:
        if not self._enabled:
            return []
        query_terms = {
            item.casefold() for item in request.query.split() if item.strip()
        }
        candidates: list[MemoryCandidate] = []
        for memory in self._repository.list_memories(request.subject_id):
            if not memory.is_available:
                continue
            if memory.temperature is MemoryTemperature.ARCHIVED and memory.lifecycle is None:
                continue
            searchable = {item.casefold() for item in memory.content.split()}
            searchable.update(item.casefold() for item in memory.tags)
            overlap = len(query_terms.intersection(searchable))
            lexical = min(1.0, overlap / max(1, len(query_terms)))
            relevance = round(max(memory.activation, lexical) * memory.effective_weight, 6)
            candidates.append(
                MemoryCandidate(
                    memory_id=memory.memory_id,
                    subject_id=memory.subject_id,
                    content=memory.content,
                    source="engine-memory-store",
                    occurred_at=memory.occurred_at,
                    provider_relevance=relevance,
                    related_scope=[],
                    tags=list(memory.tags),
                    metadata={
                        "memory_kind": memory.kind.value,
                        "evidence_type": memory.evidence_type.value,
                        "root_evidence_ids": list(memory.root_evidence_ids),
                        "source_event_ids": list(memory.source_event_ids),
                        "source_memory_ids": list(memory.source_memory_ids),
                        "source_message_ids": list(memory.source_message_ids),
                        "visibility": memory.visibility.value,
                        "memory_status": memory.status.value,
                        "memory_temperature": memory.temperature.value,
                        "memory_revision": memory.revision,
                        "memory_version": memory.memory_version,
                        "memory_environment": memory.environment,
                        "memory_hash": memory.canonical_hash(),
                        "memory_lifecycle": memory.effective_lifecycle.value,
                        "memory_weight": memory.effective_weight,
                    },
                )
            )
        return candidates
