from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from continuity_engine.domain.errors import (
    MemoryEvidenceConflictError,
    MemoryIdentityConflictError,
    MemoryLineageError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from continuity_engine.domain.memory import (
    DerivedSummary,
    DerivedSummaryStatus,
    MemoryActivationPolicy,
    MemoryConsolidationOperation,
    MemoryLineageRecord,
    MemoryLineageType,
    MemoryRecord,
    MemoryStatus,
    MemoryTemperature,
    MemoryLifecycle,
    MemoryTimeRange,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.storage.base import MemoryRepository

from .memory_ports import DerivedSummaryGenerator


@dataclass(slots=True, frozen=True)
class MemoryConsolidationResult:
    memory: MemoryRecord
    idempotent_replay: bool
    unique_evidence_added: int


@dataclass(slots=True, frozen=True)
class MemoryPropagationResult:
    memory: MemoryRecord
    lineage: MemoryLineageRecord
    invalidated_summaries: tuple[DerivedSummary, ...]
    idempotent_replay: bool


class DeterministicDerivedSummaryGenerator:
    """P04-local deterministic generator; it performs no network or model call."""

    def generate(self, memories: Sequence[MemoryRecord]) -> str:
        ordered = sorted(memories, key=lambda item: (item.occurred_at, item.memory_id))
        if not ordered:
            raise MemoryValidationError("a derived summary requires active source memory")
        return " | ".join(
            f"{item.kind.value}/{item.evidence_type.value}: {item.content}"
            for item in ordered
        )


class MemoryConsolidationService:
    """P04 Memory-internal consolidation, lifecycle, and summary operations."""

    def __init__(
        self,
        repository: MemoryRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
        activation_policy: MemoryActivationPolicy | None = None,
        summary_generator: DerivedSummaryGenerator | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._activation_policy = activation_policy or MemoryActivationPolicy()
        self._summary_generator = summary_generator or DeterministicDerivedSummaryGenerator()

    def consolidate(self, candidate: MemoryRecord) -> MemoryConsolidationResult:
        if candidate.historical_only:
            raise MemoryValidationError('historical receipt cannot be consolidated as new material')
        if any(x is not None for x in (candidate.lifecycle,candidate.retrieval_weight,candidate.lifecycle_command_id)):
            raise MemoryValidationError('Consolidation cannot inject lifecycle history')
        candidate_hash = candidate.consolidation_hash()
        existing_operation = self._repository.load_consolidation_operation(
            candidate.subject_id, candidate.consolidation_id
        )
        deleted_roots={r for memory in self._repository.list_memories(candidate.subject_id,include_inactive=True)
                       if memory.effective_lifecycle is MemoryLifecycle.DELETED for r in memory.root_evidence_ids}
        if deleted_roots.intersection(candidate.root_evidence_ids):
            raise MemoryValidationError('deleted memory evidence cannot be reintroduced by consolidation')
        if existing_operation is None:
            suppressed={r for m in self._repository.list_memories(candidate.subject_id,include_inactive=True)
                        if not m.is_available for r in m.root_evidence_ids}
            if suppressed.intersection(candidate.root_evidence_ids):
                raise MemoryValidationError('inactive evidence requires explicit current restoration, not a new alias')
        if existing_operation is not None:
            if existing_operation.canonical_input_hash != candidate_hash:
                raise MemoryIdentityConflictError(
                    f"consolidation identity conflict: {candidate.consolidation_id}"
                )
            current = self._load_operation_result(
                candidate.subject_id, existing_operation
            )
            return MemoryConsolidationResult(current, True, 0)

        active = self._repository.list_memories(candidate.subject_id)
        compatible = [
            item
            for item in active
            if item.kind is candidate.kind
            and item.evidence_type is candidate.evidence_type
            and item.scope == candidate.scope
        ]
        duplicate_roots = set(candidate.root_evidence_ids).intersection(
            {root for item in compatible for root in item.root_evidence_ids}
        )
        same_content = [item for item in compatible if item.content == candidate.content]
        if duplicate_roots:
            if same_content and set(candidate.root_evidence_ids).issubset(same_content[0].root_evidence_ids):
                current = same_content[0]
                operation = self._consolidation_operation(
                    candidate,
                    current,
                    candidate_hash,
                    self._clock(),
                )
                self._repository.save_consolidation(current, operation)
                return MemoryConsolidationResult(self._load_operation_result(candidate.subject_id,operation), True, 0)
            if any(item.content != candidate.content
                   and set(item.root_evidence_ids).intersection(candidate.root_evidence_ids)
                   for item in compatible):
                raise MemoryEvidenceConflictError(
                    "the same root evidence cannot support conflicting memory content"
                )
        if compatible and not same_content:
            raise MemoryEvidenceConflictError(
                "conflicting evidence remains unresolved until the P07 boundary"
            )

        now = self._clock()
        if same_content:
            current = same_content[0]
            payload = current.to_dict()
            payload.update(
                {
                    "root_evidence_ids": list(
                        dict.fromkeys([*current.root_evidence_ids, *candidate.root_evidence_ids])
                    ),
                    "source_event_ids": list(
                        dict.fromkeys([*current.source_event_ids, *candidate.source_event_ids])
                    ),
                    "source_memory_ids": list(
                        # The candidate may legitimately cite the old revision
                        # of this result. Its original chain stays in the
                        # operation and is checked against pre-merge history;
                        # it must not become a self-edge on the new revision.
                        dict.fromkeys(identifier for identifier in
                                      [*current.source_memory_ids, *candidate.source_memory_ids]
                                      if identifier != current.memory_id)
                    ),
                    "source_message_ids": list(
                        dict.fromkeys([*current.source_message_ids, *candidate.source_message_ids])
                    ),
                    "occurred_at": min(current.occurred_at, candidate.occurred_at)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "observed_at": max(current.observed_at, candidate.observed_at)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "recorded_at": max(current.recorded_at, candidate.recorded_at)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "consolidated_at": max(
                        current.consolidated_at, candidate.consolidated_at, now
                    )
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "confidence": max(current.confidence, candidate.confidence),
                    "importance": max(current.importance, candidate.importance),
                    "relation_relevance": max(
                        current.relation_relevance, candidate.relation_relevance
                    ),
                    "emotional_weight": max(
                        current.emotional_weight, candidate.emotional_weight
                    ),
                    "time_range": MemoryTimeRange(
                        min(current.time_range.start_at, candidate.time_range.start_at),
                        max(current.time_range.end_at, candidate.time_range.end_at),
                    ).to_dict(),
                    "tags": list(dict.fromkeys([*current.tags, *candidate.tags])),
                    "consolidation_id": candidate.consolidation_id,
                    "consolidation_input_hash": candidate.consolidation_hash(),
                    "revision": current.revision + 1,
                    "memory_version": current.memory_version + 1,
                }
            )
            if payload.get('source_memory_bindings') is not None:
                payload['source_memory_bindings']={identifier:self._repository.load_memory(candidate.subject_id,identifier).canonical_hash()
                                                   for identifier in payload['source_memory_ids']}
            updated = MemoryRecord.from_dict(payload)
            decision = self._activation_policy.evaluate(updated, now)
            payload = updated.to_dict()
            payload["activation"] = decision.activation
            payload["temperature"] = decision.temperature.value
            payload["activation_explanation"] = list(decision.explanation)
            updated = MemoryRecord.from_dict(payload)
            operation = self._consolidation_operation(
                candidate, updated, candidate_hash, now
            )
            self._repository.save_consolidation(updated, operation)
            return MemoryConsolidationResult(
                self._load_operation_result(candidate.subject_id,operation), False,
                len(set(candidate.root_evidence_ids) - set(current.root_evidence_ids))
            )

        decision = self._activation_policy.evaluate(candidate, now)
        payload = candidate.to_dict()
        payload["activation"] = decision.activation
        payload["temperature"] = decision.temperature.value
        payload["activation_explanation"] = list(decision.explanation)
        created = MemoryRecord.from_dict(payload)
        if created.source_memory_ids:
            payload=created.to_dict()
            payload['source_memory_bindings']={identifier:self._repository.load_memory(candidate.subject_id,identifier).canonical_hash()
                                               for identifier in created.source_memory_ids}
            created=MemoryRecord.from_dict(payload)
        operation = self._consolidation_operation(candidate, created, candidate_hash, now)
        self._repository.save_consolidation(created, operation)
        return MemoryConsolidationResult(self._load_operation_result(candidate.subject_id,operation), False, len(created.root_evidence_ids))

    @staticmethod
    def _consolidation_operation(
        candidate: MemoryRecord,
        result: MemoryRecord,
        candidate_hash: str,
        recorded_at: datetime,
    ) -> MemoryConsolidationOperation:
        return MemoryConsolidationOperation(
            consolidation_id=candidate.consolidation_id,
            subject_id=candidate.subject_id,
            environment=candidate.environment,
            canonical_input_hash=candidate_hash,
            canonical_input=candidate.to_dict(),
            result_memory_id=result.memory_id,
            result_memory_revision=result.revision,
            result_memory_canonical_hash=result.canonical_hash(),
            recorded_at=max(
                recorded_at, candidate.consolidated_at, result.consolidated_at
            ),
        )

    def _load_operation_result(
        self,
        subject_id: str,
        operation: MemoryConsolidationOperation,
    ) -> MemoryRecord:
        matches = [
            item
            for item in self._repository.memory_history(
                subject_id, operation.result_memory_id
            )
            if item.revision == operation.result_memory_revision
        ]
        if len(matches) != 1:
            raise MemoryIdentityConflictError(
                "consolidation operation result revision is unavailable"
            )
        result = matches[0]
        if result.canonical_hash() != operation.result_memory_canonical_hash:
            raise MemoryIdentityConflictError(
                "consolidation operation result hash does not match history"
            )
        current = self._repository.load_memory(subject_id, operation.result_memory_id)
        if current.effective_lifecycle is MemoryLifecycle.DELETED or (
                current.lifecycle is not None and not current.is_available):
            raise MemoryValidationError('consolidation replay source is no longer available')
        # Preserve P04's exact historical revision receipt. It is not a fresh
        # material grant when the current version differs or is unavailable.
        result.historical_only=(current.canonical_hash()!=result.canonical_hash()
                                or not self._repository.current_usable(subject_id,current.memory_id))
        result.consumption_weight=current.effective_weight
        return result

    def recalculate_activation(self, subject_id: str) -> list[MemoryRecord]:
        """Explicit maintenance entry; no scheduler and no physical deletion."""

        now = self._clock()
        current = self._repository.list_memories(subject_id)
        decisions = {
            item.memory_id: self._activation_policy.evaluate(item, now) for item in current
        }
        ordered = sorted(
            current,
            key=lambda item: (decisions[item.memory_id].activation, item.memory_id),
            reverse=True,
        )
        capacities = self._activation_policy.config
        counts = {temperature: 0 for temperature in MemoryTemperature}
        migrated: list[MemoryRecord] = []
        for item in ordered:
            decision = decisions[item.memory_id]
            temperature = decision.temperature
            if temperature is MemoryTemperature.HOT:
                counts[temperature] += 1
                if counts[temperature] > capacities.hot_capacity:
                    temperature = MemoryTemperature.WARM
            if temperature is MemoryTemperature.WARM:
                counts[temperature] += 1
                if counts[temperature] > capacities.warm_capacity:
                    temperature = MemoryTemperature.COLD
            if temperature is MemoryTemperature.COLD:
                counts[temperature] += 1
                if counts[temperature] > capacities.cold_capacity:
                    temperature = MemoryTemperature.ARCHIVED
            counts[temperature] += 1 if temperature is MemoryTemperature.ARCHIVED else 0
            if (
                item.activation == decision.activation
                and item.temperature is temperature
                and tuple(item.activation_explanation) == decision.explanation
            ):
                continue
            payload = item.to_dict()
            payload.update(
                {
                    "activation": decision.activation,
                    "temperature": temperature.value,
                    "activation_explanation": list(decision.explanation),
                    "revision": item.revision + 1,
                    "memory_version": item.memory_version + 1,
                }
            )
            updated = MemoryRecord.from_dict(payload)
            self._repository.save_memory(updated)
            migrated.append(updated)
        return migrated

    def generate_summary(
        self,
        subject_id: str,
        *,
        summary_id: str,
        summary_type: str,
        scope: str,
        source_memory_ids: Sequence[str],
        confidence: float,
    ) -> DerivedSummary:
        identifiers = list(source_memory_ids)
        if len(set(identifiers)) != len(identifiers) or not identifiers:
            raise MemoryValidationError("summary source memories must be unique and non-empty")
        sources = [self._repository.load_memory(subject_id, item) for item in identifiers]
        if any(not item.is_available or not self._repository.current_usable(subject_id,item.memory_id) for item in sources):
            raise MemoryValidationError("summary generation requires current active memory")
        sources.sort(key=lambda item: (item.occurred_at, item.memory_id))
        content = self._summary_generator.generate(sources)
        root_ids = list(
            dict.fromkeys(identifier for item in sources for identifier in item.root_evidence_ids)
        )
        event_ids = list(
            dict.fromkeys(identifier for item in sources for identifier in item.source_event_ids)
        )
        message_ids = list(
            dict.fromkeys(identifier for item in sources for identifier in item.source_message_ids)
        )
        start = min(item.time_range.start_at for item in sources)
        end = max(item.time_range.end_at for item in sources)
        now = self._clock()
        history = self._repository.summary_history(subject_id, summary_id)
        current = history[-1] if history else None
        if any(
            item.summary_type != summary_type or item.scope != scope for item in history
        ):
            raise MemoryIdentityConflictError(
                f"summary stable identity conflict: {summary_id}"
            )
        if (
            current is not None
            and current.status is DerivedSummaryStatus.ACTIVE
            and current.summary_type == summary_type
            and current.scope == scope
            and current.content == content
            and current.source_event_ids == event_ids
            and current.source_memory_ids == [item.memory_id for item in sources]
            and current.source_message_ids == message_ids
            and current.root_evidence_ids == root_ids
            and current.time_range == MemoryTimeRange(start, end)
            and current.confidence == confidence
        ):
            return current
        version = 1
        if current is not None:
            if current.status is DerivedSummaryStatus.ACTIVE:
                superseded_payload = current.to_dict()
                superseded_payload.update(
                    {
                        "summary_version": current.summary_version + 1,
                        "status": DerivedSummaryStatus.SUPERSEDED.value,
                        "invalidation_reason": "A newer deterministic source view was generated.",
                        "supersedes_version": current.summary_version,
                        "generated_at": now.isoformat().replace("+00:00", "Z"),
                    }
                )
                superseded = DerivedSummary.from_dict(superseded_payload)
                self._repository.save_summary(superseded)
                version = superseded.summary_version + 1
            else:
                version = current.summary_version + 1
        summary = DerivedSummary(
            summary_id=summary_id,
            subject_id=subject_id,
            environment=sources[0].environment,
            summary_type=summary_type,
            scope=scope,
            time_range=MemoryTimeRange(start, end),
            generated_at=now,
            summary_version=version,
            source_event_ids=event_ids,
            source_memory_ids=[item.memory_id for item in sources],
            source_message_ids=message_ids,
            root_evidence_ids=root_ids,
            confidence=confidence,
            content=content,
            status=DerivedSummaryStatus.ACTIVE,
            supersedes_version=version - 1 if version > 1 else None,
        )
        self._repository.save_summary(summary)
        return summary

    def trace_summary(
        self,
        subject_id: str,
        summary_id: str,
    ) -> tuple[DerivedSummary, tuple[MemoryRecord, ...]]:
        summary = self._repository.load_summary(subject_id, summary_id)
        sources = tuple(
            self._repository.load_memory(subject_id, item)
            for item in summary.source_memory_ids
        )
        return summary, sources

    def propagate_signal(
        self,
        subject_id: str,
        *,
        lineage_id: str,
        target_memory_id: str,
        signal: MemoryLineageType,
        source_event_id: str,
        root_evidence_ids: Sequence[str],
        replacement_memory_id: str | None = None,
    ) -> MemoryPropagationResult:
        try:
            signal = signal if isinstance(signal, MemoryLineageType) else MemoryLineageType(signal)
        except ValueError as exc:
            raise MemoryLineageError("unsupported memory lineage signal") from exc
        target = self._repository.load_memory(subject_id, target_memory_id)
        replacement = None
        if replacement_memory_id is not None:
            replacement = self._repository.load_memory(subject_id, replacement_memory_id)
        source_root = (
            source_event_id
            if source_event_id.startswith("event:")
            else f"event:{source_event_id}"
        )
        supplied_roots = list(root_evidence_ids)
        allowed_roots = {source_root, *target.root_evidence_ids}
        if replacement is not None:
            allowed_roots.update(replacement.root_evidence_ids)
        if source_root not in supplied_roots:
            raise MemoryLineageError(
                "memory lineage roots must include its source event identity"
            )
        if not set(supplied_roots).issubset(allowed_roots):
            raise MemoryLineageError(
                "memory lineage roots are not traceable to target or replacement memory"
            )
        existing_lineage = next(
            (
                item
                for item in self._repository.list_lineage(subject_id)
                if item.lineage_id == lineage_id
            ),
            None,
        )
        if existing_lineage is not None:
            if (
                existing_lineage.target_memory_id != target_memory_id
                or existing_lineage.signal is not signal
                or existing_lineage.source_event_id != source_event_id
                or existing_lineage.root_evidence_ids != supplied_roots
                or existing_lineage.replacement_memory_id != replacement_memory_id
            ):
                raise MemoryIdentityConflictError(
                    f"memory lineage identity conflict: {lineage_id}"
                )
            return MemoryPropagationResult(target, existing_lineage, (), True)
        lineage = MemoryLineageRecord(
            lineage_id=lineage_id,
            subject_id=subject_id,
            environment=target.environment,
            target_memory_id=target_memory_id,
            signal=signal,
            source_event_id=source_event_id,
            root_evidence_ids=supplied_roots,
            recorded_at=self._clock(),
            replacement_memory_id=replacement_memory_id,
        )
        if target.status is not MemoryStatus.ACTIVE:
            raise MemoryLineageError("only active memory can receive a new lineage signal")
        if replacement is not None:
            if replacement.status is not MemoryStatus.ACTIVE:
                raise MemoryLineageError("replacement memory must be active")
        status = {
            MemoryLineageType.CORRECTION: MemoryStatus.CORRECTED,
            MemoryLineageType.REVOCATION: MemoryStatus.REVOKED,
            MemoryLineageType.DELETION: MemoryStatus.DELETED,
        }[signal]
        payload = target.to_dict()
        payload.update(
            {
                "status": status.value,
                "lineage_event_id": source_event_id,
                "revision": target.revision + 1,
                "memory_version": target.memory_version + 1,
            }
        )
        inactive = MemoryRecord.from_dict(payload)
        invalidated: list[DerivedSummary] = []
        for summary in self._repository.list_summaries(subject_id):
            if target_memory_id not in summary.source_memory_ids:
                continue
            summary_payload = summary.to_dict()
            summary_payload.update(
                {
                    "summary_version": summary.summary_version + 1,
                    "status": DerivedSummaryStatus.INVALIDATED.value,
                    "invalidation_reason": (
                        f"Source memory {target_memory_id} received {signal.value.lower()}."
                    ),
                    "supersedes_version": summary.summary_version,
                    "generated_at": self._clock().isoformat().replace("+00:00", "Z"),
                }
            )
            invalidated.append(DerivedSummary.from_dict(summary_payload))
        self._repository.apply_propagation(inactive, lineage, invalidated)
        return MemoryPropagationResult(inactive, lineage, tuple(invalidated), False)
