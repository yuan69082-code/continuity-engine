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
)
from continuity_engine.domain.models import utc_now

from .memory_ports import MemoryInfluenceRecorder, MemoryRetriever


class MemoryService:
    """Coordinate retrieval, relevance decisions, and influence reporting.

    This service never stores long-term memory. Retrieval and influence recording
    are delegated to injected ports that can later be backed by MCP adapters.
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
            metadata=metadata,
        )
        self._influence_recorder.record_influence(record)
        return record
