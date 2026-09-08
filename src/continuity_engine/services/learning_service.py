from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any
from uuid import uuid4

from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    JsonValue,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.learning import (
    LEARNABLE_FIELD_PATHS,
    LearningCandidateResult,
    LearningChangeResult,
    LearningContext,
    LearningEvent,
    LearningRecord,
    LearningRecordType,
    LearningResult,
    LearningValidationStatus,
    PersonalityTrait,
)
from continuity_engine.domain.models import SubjectState, utc_now
from continuity_engine.storage.base import LearningRepository

from .resource_manager import ResourceManager


MINIMUM_EVIDENCE_COUNT = 3
VALIDATION_CONFIDENCE = 0.75


class LearningService:
    """Manage controlled personality learning without mutating SubjectState."""

    def __init__(
        self,
        repository: LearningRepository,
        *,
        resource_manager: ResourceManager | None = None,
        clock: Callable[[], datetime] = utc_now,
        current_source_verifier=None,
    ) -> None:
        self._repository = repository
        self._resource_manager = resource_manager
        self._clock = clock
        self._current_source_verifier = current_source_verifier

    def extract_candidates(self, context: LearningContext) -> LearningResult:
        """Extract only explicitly annotated learning evidence.

        This deliberately does not infer preferences from ordinary user behavior.
        An upstream component must provide the structured ``learning_*`` metadata.
        """

        resource_decision = None
        if self._resource_manager is not None:
            allocation = self._resource_manager.request_learning(
                context.subject_id,
                context.context_id,
                reason="Evaluate explicit experiences for controlled learning value.",
            )
            resource_decision = allocation.decision
            if resource_decision.defer:
                return LearningResult(
                    candidates=[],
                    suggested_changes=[],
                    confidence=0.0,
                    resource_decision=resource_decision,
                )

        candidates: list[LearningEvent] = []
        for event in context.recent_events:
            candidate = self._candidate_from_metadata(
                subject_id=context.subject_id,
                related_state_revision=context.subject_state.revision,
                metadata=event.metadata,
                source_event_id=event.event_id,
                source_memory_id=None,
                original_experience=event.to_dict(),
                default_source=event.source,
            )
            if candidate is not None:
                candidates.append(candidate)

        for influence in context.memory_influences:
            candidate = self._candidate_from_metadata(
                subject_id=context.subject_id,
                related_state_revision=context.subject_state.revision,
                metadata=influence.metadata,
                source_event_id=None,
                source_memory_id=influence.memory_id,
                original_experience=influence.to_dict(),
                default_source="memory_influence",
            )
            if candidate is not None:
                candidates.append(candidate)

        unique = {item.learning_id: item for item in candidates}
        ordered = list(unique.values())
        confidence = max((item.confidence for item in ordered), default=0.0)
        return LearningResult(
            candidates=ordered,
            suggested_changes=[item.proposed_change for item in ordered],
            confidence=confidence,
            resource_decision=resource_decision,
        )

    def create_candidate(
        self,
        subject_id: str,
        *,
        source_event_id: str | None,
        source_memory_id: str | None,
        related_state_revision: int,
        observation: str,
        hypothesis: str,
        proposed_change: StateMutation,
        confidence: float,
        original_experience: JsonValue,
        reason: str,
        source: str,
        learning_id: str | None = None,
        root_evidence_ids: Iterable[str] = (),
    ) -> LearningCandidateResult:
        now = self._clock()
        root_evidence_ids=list(root_evidence_ids)
        if source_memory_id is not None:
            resolver=getattr(self._repository,'memory_support_snapshot',None)
            metadata=(original_experience.get('metadata',{}) if isinstance(original_experience,dict) else {})
            binding=resolver(subject_id,source_memory_id,metadata.get('memory_environment')) if resolver else None
            if metadata.get('memory_hash') is not None:
                if binding is None or binding['hash']!=metadata['memory_hash'] or binding['revision']!=metadata.get('memory_revision'):
                    raise LearningValidationError('memory influence source version/hash drift')
            if binding is not None:
                if set(root_evidence_ids)!=set(binding['root_evidence_ids']):
                    raise LearningValidationError('memory support root evidence mismatch')
                original_experience={'experience':original_experience,'p12_memory_binding':binding}
        candidate = LearningEvent(
            learning_id=learning_id or str(uuid4()),
            subject_id=subject_id,
            source_event_id=source_event_id,
            source_memory_id=source_memory_id,
            related_state_revision=related_state_revision,
            observation=observation,
            hypothesis=hypothesis,
            proposed_change=proposed_change,
            confidence=confidence,
            validation_status=LearningValidationStatus.PENDING,
            created_at=now,
            root_evidence_ids=list(root_evidence_ids),
        )
        record = LearningRecord(
            record_id=str(uuid4()),
            learning_id=candidate.learning_id,
            subject_id=subject_id,
            record_type=LearningRecordType.CANDIDATE_CREATED,
            original_experience=original_experience,
            observation=observation,
            hypothesis=hypothesis,
            validation_status=LearningValidationStatus.PENDING,
            permanently_consolidated=False,
            field_path=proposed_change.field_path,
            before_value=None,
            after_value=proposed_change.value,
            reason=reason,
            source=source,
            created_at=now,
            evidence_learning_ids=[candidate.learning_id],
            root_evidence_ids=list(candidate.root_evidence_ids),
        )
        self._repository.save_change(subject_id, candidate, record)
        return LearningCandidateResult(learning_event=candidate, record=record)

    def adjust_confidence(
        self,
        subject_id: str,
        learning_id: str,
        delta: float,
        *,
        reason: str,
        source: str,
    ) -> LearningChangeResult:
        current = self._repository.load_learning_event(subject_id, learning_id)
        self._require_mutable_candidate(subject_id, current)
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise LearningValidationError("confidence delta must be a number")
        updated = LearningEvent.from_dict(current.to_dict())
        updated.confidence = max(0.0, min(1.0, current.confidence + float(delta)))
        if (
            updated.validation_status is LearningValidationStatus.VALIDATED
            and updated.confidence < VALIDATION_CONFIDENCE
        ):
            updated.validation_status = LearningValidationStatus.PENDING
        updated.revision += 1
        updated.__post_init__()
        record = self._record_for(
            updated,
            record_type=LearningRecordType.CONFIDENCE_ADJUSTED,
            validation_status=updated.validation_status,
            permanently_consolidated=False,
            before_value=current.confidence,
            after_value=updated.confidence,
            reason=reason,
            source=source,
        )
        self._repository.save_change(subject_id, updated, record)
        return LearningChangeResult(learning_event=updated, record=record)

    def validate_learning(
        self,
        subject_id: str,
        learning_id: str,
        corroborating_learning_ids: Iterable[str],
        *,
        reason: str,
        source: str,
    ) -> LearningChangeResult:
        target = self._repository.load_learning_event(subject_id, learning_id)
        self._require_mutable_candidate(subject_id, target)
        evidence_ids = list(dict.fromkeys([learning_id, *corroborating_learning_ids]))
        if len(evidence_ids) < MINIMUM_EVIDENCE_COUNT:
            raise LearningValidationError(
                f"validation requires at least {MINIMUM_EVIDENCE_COUNT} consistent experiences"
            )
        evidence = [
            self._repository.load_learning_event(subject_id, identifier)
            for identifier in evidence_ids
        ]
        if any(
            item.validation_status
            in (LearningValidationStatus.REJECTED, LearningValidationStatus.REVOKED)
            for item in evidence
        ):
            raise LearningValidationError("rejected or revoked evidence cannot validate learning")
        seen_roots: set[str] = set()
        for item in evidence:
            self._verify_memory_support(subject_id,item)
            roots = set(item.root_evidence_ids)
            if seen_roots.intersection(roots):
                raise LearningValidationError(
                    "validation evidence must use distinct root experiences"
                )
            seen_roots.update(roots)
        signature = self._mutation_signature(target.proposed_change)
        if any(self._mutation_signature(item.proposed_change) != signature for item in evidence):
            raise LearningValidationError("validation evidence proposes inconsistent changes")

        updated = LearningEvent.from_dict(target.to_dict())
        updated.confidence = self._validation_confidence(
            target.confidence, [item.confidence for item in evidence]
        )
        updated.evidence_learning_ids = evidence_ids
        updated.root_evidence_ids = sorted(seen_roots)
        updated.validation_status = (
            LearningValidationStatus.VALIDATED
            if updated.confidence >= VALIDATION_CONFIDENCE
            else LearningValidationStatus.PENDING
        )
        updated.revision += 1
        updated.__post_init__()
        record_type = (
            LearningRecordType.VALIDATED
            if updated.validation_status is LearningValidationStatus.VALIDATED
            else LearningRecordType.CONFIDENCE_ADJUSTED
        )
        record = self._record_for(
            updated,
            record_type=record_type,
            validation_status=updated.validation_status,
            permanently_consolidated=False,
            before_value=target.confidence,
            after_value=updated.confidence,
            reason=reason,
            source=source,
        )
        self._repository.save_change(subject_id, updated, record)
        return LearningChangeResult(learning_event=updated, record=record)

    def reject_learning(
        self,
        subject_id: str,
        learning_id: str,
        *,
        reason: str,
        source: str,
    ) -> LearningChangeResult:
        current = self._repository.load_learning_event(subject_id, learning_id)
        self._require_mutable_candidate(subject_id, current)
        updated = LearningEvent.from_dict(current.to_dict())
        updated.validation_status = LearningValidationStatus.REJECTED
        updated.revision += 1
        updated.__post_init__()
        record = self._record_for(
            updated,
            record_type=LearningRecordType.REJECTED,
            validation_status=LearningValidationStatus.REJECTED,
            permanently_consolidated=False,
            before_value=current.validation_status.value,
            after_value=LearningValidationStatus.REJECTED.value,
            reason=reason,
            source=source,
        )
        self._repository.save_change(subject_id, updated, record)
        return LearningChangeResult(learning_event=updated, record=record)

    def solidify_learning(
        self,
        subject_id: str,
        learning_id: str,
        current_state: SubjectState,
        *,
        trait_name: str,
        trait_description: str,
        reason: str,
        source: str,
        confirmed: bool,
        expected_revision: int,
        trait_id: str | None = None,
        growth_operation: dict | None = None,
    ) -> LearningChangeResult:
        self._require_confirmation(confirmed)
        self._check_state(subject_id, current_state, expected_revision)
        current = self._repository.load_learning_event(subject_id, learning_id)
        if current.validation_status is not LearningValidationStatus.VALIDATED:
            raise LearningValidationError("only validated learning may be consolidated")
        if (
            len(current.root_evidence_ids) < MINIMUM_EVIDENCE_COUNT
            or current.confidence < VALIDATION_CONFIDENCE
        ):
            raise LearningValidationError("validated learning lacks sufficient evidence")
        current.confidence = min(current.confidence, self._verify_current_support(subject_id, current))
        if self._has_active_consolidation(subject_id, learning_id):
            raise LearningValidationError("learning is already consolidated")

        before = self._field_value(current_state, current.proposed_change.field_path)
        if current.proposed_change.value in before:
            raise LearningValidationError("proposed personality value already exists")
        after = [*before, current.proposed_change.value]
        now = self._clock()
        personality_trait = PersonalityTrait(
            trait_id=trait_id or str(uuid4()),
            subject_id=subject_id,
            name=trait_name,
            description=trait_description,
            field_path=current.proposed_change.field_path,
            current_value=str(current.proposed_change.value),
            confidence=current.confidence,
            created_at=now,
            last_updated_at=now,
            evidence_count=len(current.root_evidence_ids),
        )
        state_event = Event.create(
            event_id=('p15-growth:' + str(growth_operation['command']['command_id']) if growth_operation else None),
            occurred_at=now,
            source=source,
            event_type="learning_consolidation",
            content=f"Validated learning proposed long-term trait: {trait_name}",
            impact_scope=[self._section(current.proposed_change.field_path)],
            mutations=[current.proposed_change],
            reason=reason,
            metadata={
                "learning_id": learning_id,
                "trait_id": personality_trait.trait_id,
                "evidence_count": personality_trait.evidence_count,
                "learning_confidence": current.confidence,
                "explicitly_confirmed": True,
                **({'p15_growth_operation':growth_operation} if growth_operation is not None else {}),
            },
        )
        updated = LearningEvent.from_dict(current.to_dict())
        updated.revision += 1
        updated.__post_init__()
        record = self._record_for(
            updated,
            record_type=LearningRecordType.CONSOLIDATED,
            validation_status=LearningValidationStatus.VALIDATED,
            permanently_consolidated=True,
            before_value=before,
            after_value=after,
            reason=reason,
            source=source,
            trait_id=personality_trait.trait_id,
            state_event_id=state_event.event_id,
        )
        if growth_operation is not None:
            record.pending_state_event = state_event.to_dict()
            record.growth_operation = dict(growth_operation)
            record.record_type = LearningRecordType.GROWTH_PREPARED
            record.permanently_consolidated = False
            personality_trait.active = False  # Proposal, not an already committed Trait.
        self._repository.save_change(
            subject_id,
            updated,
            record,
            trait=personality_trait,
        )
        return LearningChangeResult(
            learning_event=updated,
            record=record,
            trait=personality_trait,
            event=state_event,
        )

    def _verify_current_support(self, subject_id: str, target: LearningEvent) -> float:
        """Recheck the recorded validation against current supporting records.

        The target's roots/confidence were aggregated by validation. Recover
        its own roots and pre-validation confidence from existing history so
        that the validation cannot corroborate itself a second time.
        """
        self._verify_memory_support(subject_id,target)
        history = self._repository.history(subject_id, target.learning_id)
        origins = [r for r in history if r.record_type is LearningRecordType.CANDIDATE_CREATED]
        validations = [r for r in history if r.record_type is LearningRecordType.VALIDATED]
        ids = target.evidence_learning_ids
        if (len(origins) != 1 or not validations or target.learning_id not in ids
                or len(set(ids)) != len(ids) or len(ids) < MINIMUM_EVIDENCE_COUNT):
            raise LearningValidationError("current validation has insufficient traceable evidence")
        roots = set(origins[0].root_evidence_ids or [target.source_identity])
        own_confidence = min(target.confidence, float(validations[-1].before_value))
        confidences = [own_confidence]
        signature = self._mutation_signature(target.proposed_change)
        for identifier in ids:
            if identifier == target.learning_id:
                continue
            support = self._repository.load_learning_event(subject_id, identifier)
            self._verify_memory_support(subject_id,support)
            if (support.validation_status in (LearningValidationStatus.REJECTED,
                                              LearningValidationStatus.REVOKED)
                    or self._mutation_signature(support.proposed_change) != signature):
                raise LearningValidationError("supporting learning is no longer valid")
            incoming = set(support.root_evidence_ids)
            if roots.intersection(incoming):
                raise LearningValidationError("current support is not independent root evidence")
            roots.update(incoming)
            confidences.append(support.confidence)
        confidence = self._validation_confidence(own_confidence, confidences)
        if (roots != set(target.root_evidence_ids) or len(roots) < MINIMUM_EVIDENCE_COUNT
                or confidence < VALIDATION_CONFIDENCE):
            raise LearningValidationError("current support no longer meets validation requirements")
        return confidence

    def _verify_memory_support(self, subject_id, candidate):
        origins = [r for r in self._repository.history(subject_id,candidate.learning_id)
                   if r.record_type is LearningRecordType.CANDIDATE_CREATED]
        binding = (origins[0].original_experience.get('p15_source_binding')
                   if len(origins)==1 and isinstance(origins[0].original_experience,dict) else None)
        if binding is None and (candidate.learning_id.startswith('p15-learning:') or
                any(r.source=='p15-c1-experience' for r in origins)):
            raise LearningValidationError('P15 captured source binding missing; cannot downgrade to legacy')
        if binding is not None:
            if self._current_source_verifier is None:
                raise LearningValidationError('P15 current source verifier required')
            self._current_source_verifier(candidate, binding)
        if candidate.source_memory_id is None: return
        origins=[r for r in self._repository.history(subject_id,candidate.learning_id)
                 if r.record_type is LearningRecordType.CANDIDATE_CREATED]
        if len(origins)!=1: raise LearningValidationError('memory support lacks origin')
        origin=origins[0].original_experience
        binding=origin.get('p12_memory_binding') if isinstance(origin,dict) else None
        resolver=getattr(self._repository,'memory_support_snapshot',None)
        actual=resolver(subject_id,candidate.source_memory_id,binding['environment'] if binding else None) if resolver else None
        if binding is not None and actual!=binding:
            raise LearningValidationError('memory support was removed or its version/hash changed')
        # Genuinely old unversioned ports retain compatibility. A locally present
        # Memory is still checked above; missing captured P12 bindings fail closed.

    @staticmethod
    def _validation_confidence(own_confidence: float, confidences: list[float]) -> float:
        """Use the established policy at validation and current-support review.

        The target's own contribution and the aggregate are distinct: the
        aggregate must not become its own corroborating evidence at solidify.
        """
        average = sum(confidences) / len(confidences)
        learned_confidence = min(1.0, average + 0.1 * (len(confidences) - 1))
        return round(max(own_confidence, learned_confidence), 6)

    def rollback_learning(
        self,
        subject_id: str,
        learning_id: str,
        trait_id: str,
        current_state: SubjectState,
        *,
        reason: str,
        source: str,
        confirmed: bool,
        expected_revision: int,
        growth_operation: dict | None = None,
    ) -> LearningChangeResult:
        self._require_confirmation(confirmed)
        self._check_state(subject_id, current_state, expected_revision)
        current = self._repository.load_learning_event(subject_id, learning_id)
        trait = self._repository.load_trait(subject_id, trait_id)
        if not trait.active:
            raise LearningValidationError("personality trait is already inactive")
        history = self._repository.history(subject_id, learning_id)
        if not any(
            item.record_type is LearningRecordType.CONSOLIDATED
            and item.trait_id == trait_id
            for item in history
        ):
            raise LearningValidationError("trait was not consolidated by this learning")

        before = self._field_value(current_state, trait.field_path)
        if trait.current_value not in before:
            raise LearningValidationError("trait value is absent from current SubjectState")
        after = [item for item in before if item != trait.current_value]
        now = self._clock()
        rollback_mutation = StateMutation(
            field_path=trait.field_path,
            operation=ChangeOperation.REMOVE,
            value=trait.current_value,
            reason=reason,
        )
        state_event = Event.create(
            occurred_at=now,
            source=source,
            event_type="learning_rollback",
            content=f"Previously consolidated trait was withdrawn: {trait.name}",
            impact_scope=[self._section(trait.field_path)],
            mutations=[rollback_mutation],
            reason=reason,
            metadata={
                "learning_id": learning_id,
                "trait_id": trait_id,
                "explicitly_confirmed": True,
            },
        )
        if growth_operation is not None:
            state_event.event_id = 'p15-growth:' + str(growth_operation['command']['command_id'])
            state_event.metadata['p15_growth_operation'] = growth_operation
        updated_learning = LearningEvent.from_dict(current.to_dict())
        updated_learning.validation_status = LearningValidationStatus.REVOKED
        updated_learning.revision += 1
        updated_learning.__post_init__()
        updated_trait = PersonalityTrait.from_dict(trait.to_dict())
        updated_trait.active = False
        updated_trait.last_updated_at = now
        updated_trait.revision += 1
        updated_trait.__post_init__()
        record = self._record_for(
            updated_learning,
            record_type=LearningRecordType.ROLLED_BACK,
            validation_status=LearningValidationStatus.REVOKED,
            permanently_consolidated=False,
            before_value=before,
            after_value=after,
            reason=reason,
            source=source,
            trait_id=trait_id,
            state_event_id=state_event.event_id,
        )
        if growth_operation is not None:
            record.pending_state_event = state_event.to_dict()
            record.growth_operation = dict(growth_operation)
            record.record_type = LearningRecordType.GROWTH_PREPARED
            updated_learning.validation_status = current.validation_status
            record.validation_status = current.validation_status
            updated_trait.active = trait.active  # Original contribution remains until Evolution.
        self._repository.save_change(
            subject_id,
            updated_learning,
            record,
            trait=updated_trait,
        )
        return LearningChangeResult(
            learning_event=updated_learning,
            record=record,
            trait=updated_trait,
            event=state_event,
        )

    def get_learning_event(self, subject_id: str, learning_id: str) -> LearningEvent:
        return self._repository.load_learning_event(subject_id, learning_id)

    def list_learning_events(self, subject_id: str) -> list[LearningEvent]:
        return self._repository.list_learning_events(subject_id)

    def get_trait(self, subject_id: str, trait_id: str) -> PersonalityTrait:
        return self._repository.load_trait(subject_id, trait_id)

    def list_traits(
        self,
        subject_id: str,
        *,
        include_inactive: bool = True,
    ) -> list[PersonalityTrait]:
        return self._repository.list_traits(subject_id, include_inactive)

    def get_history(
        self,
        subject_id: str,
        learning_id: str | None = None,
    ) -> list[LearningRecord]:
        return self._repository.history(subject_id, learning_id)

    def _candidate_from_metadata(
        self,
        *,
        subject_id: str,
        related_state_revision: int,
        metadata: dict[str, JsonValue],
        source_event_id: str | None,
        source_memory_id: str | None,
        original_experience: JsonValue,
        default_source: str,
    ) -> LearningEvent | None:
        required = (
            "learning_observation",
            "learning_hypothesis",
            "learning_field_path",
            "learning_value",
        )
        if not all(key in metadata for key in required):
            return None
        existing = self._find_by_source(
            subject_id,
            source_event_id=source_event_id,
            source_memory_id=source_memory_id,
        )
        if existing is not None:
            return existing
        confidence = metadata.get("learning_confidence", 0.5)
        result = self.create_candidate(
            subject_id,
            source_event_id=source_event_id,
            source_memory_id=source_memory_id,
            related_state_revision=related_state_revision,
            observation=metadata["learning_observation"],
            hypothesis=metadata["learning_hypothesis"],
            proposed_change=StateMutation(
                field_path=metadata["learning_field_path"],
                operation=ChangeOperation.APPEND,
                value=metadata["learning_value"],
                reason=str(metadata.get("learning_reason", metadata["learning_hypothesis"])),
            ),
            confidence=confidence,
            original_experience=original_experience,
            reason=str(metadata.get("learning_reason", "Explicit learning evidence was supplied.")),
            source=str(metadata.get("learning_source", default_source)),
            root_evidence_ids=(
                metadata.get("root_evidence_ids", [])
                if isinstance(metadata.get("root_evidence_ids", []), list)
                else []
            ),
        )
        return result.learning_event

    def _find_by_source(
        self,
        subject_id: str,
        *,
        source_event_id: str | None,
        source_memory_id: str | None,
    ) -> LearningEvent | None:
        for candidate in self._repository.list_learning_events(subject_id):
            if source_event_id is not None and candidate.source_event_id == source_event_id:
                return candidate
            if source_memory_id is not None and candidate.source_memory_id == source_memory_id:
                return candidate
        return None

    def _require_mutable_candidate(
        self,
        subject_id: str,
        candidate: LearningEvent,
    ) -> None:
        if candidate.validation_status in (
            LearningValidationStatus.REJECTED,
            LearningValidationStatus.REVOKED,
        ):
            raise LearningValidationError("rejected or revoked learning cannot be changed")
        if self._has_active_consolidation(subject_id, candidate.learning_id):
            raise LearningValidationError("consolidated learning must be rolled back first")

    def _has_active_consolidation(self, subject_id: str, learning_id: str) -> bool:
        trait_ids = {
            item.trait_id
            for item in self._repository.history(subject_id, learning_id)
            if item.record_type is LearningRecordType.CONSOLIDATED
            and item.trait_id is not None
        }
        active_ids = {
            item.trait_id
            for item in self._repository.list_traits(subject_id, include_inactive=False)
        }
        return bool(trait_ids & active_ids)

    def _record_for(
        self,
        learning: LearningEvent,
        *,
        record_type: LearningRecordType,
        validation_status: LearningValidationStatus,
        permanently_consolidated: bool,
        before_value: JsonValue,
        after_value: JsonValue,
        reason: str,
        source: str,
        trait_id: str | None = None,
        state_event_id: str | None = None,
        growth_resolution: dict | None = None,
    ) -> LearningRecord:
        return LearningRecord(
            record_id=str(uuid4()),
            learning_id=learning.learning_id,
            subject_id=learning.subject_id,
            record_type=record_type,
            original_experience=self._original_experience(
                learning.subject_id, learning.learning_id
            ),
            observation=learning.observation,
            hypothesis=learning.hypothesis,
            validation_status=validation_status,
            permanently_consolidated=permanently_consolidated,
            field_path=learning.proposed_change.field_path,
            before_value=before_value,
            after_value=after_value,
            reason=reason,
            source=source,
            created_at=self._clock(),
            evidence_learning_ids=(
                list(learning.evidence_learning_ids)
                if learning.evidence_learning_ids
                else [learning.learning_id]
            ),
            root_evidence_ids=list(learning.root_evidence_ids),
            trait_id=trait_id,
            state_event_id=state_event_id,
            growth_resolution=growth_resolution,
        )

    def _original_experience(self, subject_id: str, learning_id: str) -> JsonValue:
        history = self._repository.history(subject_id, learning_id)
        for item in history:
            if item.record_type is LearningRecordType.CANDIDATE_CREATED:
                return item.original_experience
        raise LearningValidationError("learning candidate has no originating experience")

    @staticmethod
    def _mutation_signature(mutation: StateMutation) -> str:
        return json.dumps(
            {
                "field_path": mutation.field_path,
                "operation": mutation.operation.value,
                "value": mutation.value,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _check_state(
        subject_id: str,
        current_state: SubjectState,
        expected_revision: int,
    ) -> None:
        if not isinstance(current_state, SubjectState) or current_state.subject_id != subject_id:
            raise LearningValidationError("SubjectState does not match learning subject")
        if current_state.revision != expected_revision:
            raise LearningValidationError(
                "SubjectState revision does not match expected_revision"
            )

    @staticmethod
    def _require_confirmation(confirmed: bool) -> None:
        if confirmed is not True:
            raise LearningValidationError(
                "permanent personality changes require explicit confirmation"
            )

    @staticmethod
    def _field_value(state: SubjectState, field_path: str) -> list[str]:
        if field_path not in LEARNABLE_FIELD_PATHS:
            raise LearningValidationError("field is outside the learning boundary")
        section_name, attribute_name = field_path.split(".", 1)
        value = getattr(getattr(state, section_name), attribute_name)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise LearningValidationError("learnable SubjectState field must be a string list")
        return list(value)

    @staticmethod
    def _section(field_path: str) -> StateSection:
        return StateSection(field_path.split(".", 1)[0])
