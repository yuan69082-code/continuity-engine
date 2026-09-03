from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Protocol

from continuity_engine.domain.context_composition import (
    ComposedContextFragment,
    CompositionStatus,
    ContextAuthority,
    ContextCompositionResult,
)
from continuity_engine.domain.contradiction import (
    AuditAction,
    ClaimDisposition,
    ClaimDispositionRecord,
    ClaimDomain,
    ClaimEvaluation,
    ClaimEvaluationStatus,
    ClaimEvidenceType,
    ClaimProjection,
    ContradictionAuditEntry,
    ContradictionCase,
    ContradictionDetectionResult,
    ContradictionDetectionStatus,
    ContradictionKind,
    ContradictionStatus,
    ContradictionTrace,
    ResolutionBasisKind,
    ResolutionEvidence,
    StructuredClaim,
    VerifiedResolutionEvidence,
    VerificationStatus,
    VerificationTask,
    contradiction_hash,
    transition_case,
    validate_resolution_binding,
)
from continuity_engine.domain.errors import (
    ContextCompositionError,
    ContradictionNotFoundError,
    ContradictionValidationError,
)
from continuity_engine.storage.base import ContradictionRepository, ResolutionEvidenceVerifier


P07_DETECTOR_VERSION = "p07-contradiction-detector-v1"


class StructuredClaimResolver(Protocol):
    """Trusted semantic projection port; never grants Authority or provenance."""

    def project(self, fragment: ComposedContextFragment) -> ClaimProjection | None: ...


class ClaimSupersessionVerifier(Protocol):
    """Trusted source/version binding; semantic projections cannot grant supersession."""

    def verify(
        self,
        superseder: ComposedContextFragment,
        target: ComposedContextFragment,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class _ConflictGroup:
    proposition_id: str
    scope_id: str
    claims: tuple[StructuredClaim, ...]
    kind: ContradictionKind


class ContradictionDetectorService:
    """Consume one sealed P06 snapshot and emit non-authoritative P07 audits."""

    def __init__(
        self,
        resolver: StructuredClaimResolver,
        repository: ContradictionRepository | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        detector_version: str = P07_DETECTOR_VERSION,
        resolution_evidence_verifier: ResolutionEvidenceVerifier | None = None,
        supersession_verifier: ClaimSupersessionVerifier | None = None,
    ) -> None:
        if not callable(getattr(resolver, "project", None)):
            raise ContradictionValidationError("claim resolver must implement project")
        if not isinstance(detector_version, str) or not detector_version.strip():
            raise ContradictionValidationError("detector_version must be non-empty")
        self._resolver = resolver
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.detector_version = detector_version
        self._resolution_evidence_verifier = resolution_evidence_verifier
        self._supersession_verifier = supersession_verifier

    def detect(
        self, composition: ContextCompositionResult
    ) -> ContradictionDetectionResult:
        sealed = self._seal_composition(composition)
        if sealed is None:
            return ContradictionDetectionResult(
                ContradictionDetectionStatus.REJECTED,
                None,
                error_code="P06_CONTEXT_NOT_CONSUMABLE",
            )
        snapshot = sealed.snapshot
        if snapshot is None:
            raise ContradictionValidationError("sealed complete P06 result lost snapshot")
        # Detection identity is tied to the immutable P06 snapshot, not wall
        # time. Replaying the same sealed snapshot after restart is exact.
        detected_at = snapshot.composed_at
        claims: list[StructuredClaim] = []
        projections: dict[str, ClaimProjection] = {}
        fragments: dict[str, ComposedContextFragment] = {
            item.fragment_id: item for item in snapshot.fragments
        }
        evaluations: list[ClaimEvaluation] = []
        for fragment in snapshot.fragments:
            try:
                projection = self._resolver.project(fragment)
            except Exception as exc:
                raise ContradictionValidationError(
                    f"P07_CLAIM_RESOLVER_FAILED:{fragment.fragment_id}"
                ) from exc
            if projection is None:
                evaluations.append(
                    ClaimEvaluation(
                        fragment.fragment_id,
                        ClaimEvaluationStatus.UNASSESSED,
                        "NO_TRUSTED_STRUCTURED_CLAIM",
                    )
                )
                continue
            if not isinstance(projection, ClaimProjection):
                raise ContradictionValidationError("claim resolver returned an invalid projection")
            if projection.domain is ClaimDomain.PSYCHOLOGICAL:
                evaluations.append(
                    ClaimEvaluation(
                        fragment.fragment_id,
                        ClaimEvaluationStatus.NOT_APPLICABLE,
                        "PSYCHOLOGICAL_CONFLICT_OUT_OF_SCOPE",
                    )
                )
                continue
            claim = self._seal_claim(fragment, projection)
            claims.append(claim)
            projections[fragment.fragment_id] = projection
            evaluations.append(
                ClaimEvaluation(
                    fragment.fragment_id,
                    ClaimEvaluationStatus.EVALUATED,
                    "STRUCTURED_CLAIM_SEALED",
                    claim.claim_id,
                )
            )

        claims = list(self._seal_trusted_supersessions(claims, projections, fragments))
        groups = self._find_conflicts(claims)
        cases = tuple(
            self._persist_or_return(self._build_case(group, snapshot.snapshot_hash, detected_at))
            for group in groups
        )
        cases = tuple(sorted(cases, key=lambda item: item.case_id))
        evaluated_count = sum(
            item.status is ClaimEvaluationStatus.EVALUATED for item in evaluations
        )
        unassessed_count = sum(
            item.status is ClaimEvaluationStatus.UNASSESSED for item in evaluations
        )
        psychological_count = sum(
            item.status is ClaimEvaluationStatus.NOT_APPLICABLE for item in evaluations
        )
        trace_seed = {
            "request_id": snapshot.request_id,
            "snapshot_hash": snapshot.snapshot_hash,
            "detector_version": self.detector_version,
        }
        trace = ContradictionTrace(
            trace_id=f"p07-trace-{self._digest(trace_seed, 24)}",
            request_id=snapshot.request_id,
            subject_id=snapshot.subject_id,
            environment=snapshot.environment,
            source_revision=snapshot.source_revision,
            source_snapshot_hash=snapshot.snapshot_hash,
            detector_version=self.detector_version,
            detected_at=detected_at,
            fragment_count=len(snapshot.fragments),
            evaluated_count=evaluated_count,
            unassessed_count=unassessed_count,
            psychological_excluded_count=psychological_count,
            candidate_missing_count=sealed.trace.missing_count,
            upstream_notice_count=sealed.trace.upstream_notice_count,
            contradiction_count=len(cases),
            evaluations=tuple(evaluations),
            case_ids=tuple(item.case_id for item in cases),
        )
        return ContradictionDetectionResult(
            ContradictionDetectionStatus.COMPLETE,
            trace,
            cases,
        )

    def resolve(
        self,
        subject_id: str,
        case_id: str,
        evidence: ResolutionEvidence,
    ) -> ContradictionCase:
        repository = self._require_repository()
        current = repository.load_case(subject_id, case_id)
        if current.status not in {
            ContradictionStatus.OPEN,
            ContradictionStatus.ISOLATED,
            ContradictionStatus.PENDING_VERIFICATION,
            ContradictionStatus.REOPENED,
        }:
            raise ContradictionValidationError("case is not eligible for resolution")
        verified = self._verify_resolution_evidence(
            current, evidence, action=AuditAction.RESOLVED
        )
        audit = ContradictionAuditEntry(
            audit_id=f"audit-{case_id}-{current.revision + 1}",
            sequence=len(current.audit_history),
            action=AuditAction.RESOLVED,
            occurred_at=verified.resolved_at,
            reason_code=verified.reason_code,
            source_hashes=verified.source_hashes,
            resolution=verified,
        )
        next_case = transition_case(
            current,
            status=ContradictionStatus.RESOLVED,
            audit=audit,
            verification_status=VerificationStatus.COMPLETED,
        )
        return repository.append_transition(next_case)

    def reopen(
        self,
        subject_id: str,
        case_id: str,
        evidence: ResolutionEvidence,
    ) -> ContradictionCase:
        repository = self._require_repository()
        current = repository.load_case(subject_id, case_id)
        if current.status is not ContradictionStatus.RESOLVED:
            raise ContradictionValidationError("only a resolved case can be reopened")
        verified = self._verify_resolution_evidence(
            current, evidence, action=AuditAction.REOPENED
        )
        if verified.basis is not ResolutionBasisKind.INDEPENDENT_CORROBORATION:
            raise ContradictionValidationError(
                "reopen requires verified independent corroboration"
            )
        existing_hashes = {
            source_hash
            for item in current.audit_history
            for source_hash in item.source_hashes
        }
        if set(verified.source_hashes).issubset(existing_hashes):
            raise ContradictionValidationError("reopen requires genuinely new evidence")
        audit = ContradictionAuditEntry(
            audit_id=f"audit-{case_id}-{current.revision + 1}",
            sequence=len(current.audit_history),
            action=AuditAction.REOPENED,
            occurred_at=verified.resolved_at,
            reason_code=verified.reason_code,
            source_hashes=verified.source_hashes,
            resolution=verified,
        )
        next_case = transition_case(
            current,
            status=ContradictionStatus.REOPENED,
            audit=audit,
            verification_status=VerificationStatus.OPEN,
        )
        return repository.append_transition(next_case)

    def supersede(
        self,
        subject_id: str,
        case_id: str,
        evidence: ResolutionEvidence,
    ) -> ContradictionCase:
        repository = self._require_repository()
        current = repository.load_case(subject_id, case_id)
        if current.status not in {ContradictionStatus.RESOLVED, ContradictionStatus.REOPENED}:
            raise ContradictionValidationError("case is not eligible for supersession")
        verified = self._verify_resolution_evidence(
            current, evidence, action=AuditAction.SUPERSEDED
        )
        if verified.basis is not ResolutionBasisKind.SOURCE_SUPERSESSION:
            raise ContradictionValidationError(
                "case supersession requires verified source supersession"
            )
        audit = ContradictionAuditEntry(
            audit_id=f"audit-{case_id}-{current.revision + 1}",
            sequence=len(current.audit_history),
            action=AuditAction.SUPERSEDED,
            occurred_at=verified.resolved_at,
            reason_code=verified.reason_code,
            source_hashes=verified.source_hashes,
            resolution=verified,
        )
        next_case = transition_case(
            current,
            status=ContradictionStatus.SUPERSEDED,
            audit=audit,
            verification_status=VerificationStatus.COMPLETED,
        )
        return repository.append_transition(next_case)

    def _seal_composition(
        self, composition: ContextCompositionResult
    ) -> ContextCompositionResult | None:
        if not isinstance(composition, ContextCompositionResult):
            raise ContradictionValidationError("P07 input must be ContextCompositionResult")
        try:
            sealed = ContextCompositionResult.from_dict(composition.to_dict())
        except ContextCompositionError as exc:
            raise ContradictionValidationError("P06_CONTEXT_INTEGRITY_FAILED") from exc
        if sealed.status is not CompositionStatus.COMPLETE or sealed.snapshot is None:
            return None
        snapshot = sealed.snapshot
        trace = sealed.trace
        if not snapshot.consumable:
            return None
        if (
            snapshot.subject_id != trace.subject_id
            or snapshot.environment != trace.environment
            or snapshot.source_revision != trace.source_revision
            or snapshot.route_result_hash != trace.route_result_hash
            or snapshot.route_plan_hash != trace.route_plan_hash
            or snapshot.manifest_hash != trace.manifest_hash
        ):
            raise ContradictionValidationError("P06_CONTEXT_BINDING_MISMATCH")
        return sealed

    def _seal_claim(
        self,
        fragment: ComposedContextFragment,
        projection: ClaimProjection,
    ) -> StructuredClaim:
        value_hash = contradiction_hash(projection.canonical_value)
        seed = {
            "fragment_id": fragment.fragment_id,
            "proposition_id": projection.proposition_id,
            "canonical_value_hash": value_hash,
            "polarity": projection.polarity.value,
            "evidence_type": projection.evidence_type.value,
            "domain": projection.domain.value,
            "scope_id": projection.scope_id,
            "source_hash": fragment.content_hash,
        }
        return StructuredClaim(
            claim_id=f"claim-{self._digest(seed, 32)}",
            fragment_id=fragment.fragment_id,
            subject_id=fragment.subject_id,
            environment=fragment.environment,
            proposition_id=projection.proposition_id,
            canonical_value_hash=value_hash,
            polarity=projection.polarity,
            evidence_type=projection.evidence_type,
            domain=projection.domain,
            authority=fragment.authority,
            source_id=fragment.source_id,
            stable_source_id=fragment.stable_source_id,
            source_version=fragment.version,
            source_content_hash=fragment.content_hash,
            provenance_roots=fragment.provenance_roots,
            occurred_at=fragment.occurred_at,
            scope_id=projection.scope_id,
            supersedes_fragment_ids=(),
        )

    def _seal_trusted_supersessions(
        self,
        claims: list[StructuredClaim],
        projections: dict[str, ClaimProjection],
        fragments: dict[str, ComposedContextFragment],
    ) -> tuple[StructuredClaim, ...]:
        by_fragment = {item.fragment_id: item for item in claims}
        edges: dict[str, tuple[str, ...]] = {}
        result: list[StructuredClaim] = []
        for claim in claims:
            requested = projections[claim.fragment_id].supersedes_fragment_ids
            if not requested:
                result.append(claim)
                edges[claim.fragment_id] = ()
                continue
            if self._supersession_verifier is None:
                raise ContradictionValidationError(
                    "UNTRUSTED_SOURCE_SUPERSESSION"
                )
            trusted: list[str] = []
            for target_id in requested:
                if target_id == claim.fragment_id:
                    raise ContradictionValidationError(
                        "SOURCE_SUPERSESSION_SELF_REFERENCE"
                    )
                target_claim = by_fragment.get(target_id)
                target_fragment = fragments.get(target_id)
                superseder_fragment = fragments.get(claim.fragment_id)
                if target_claim is None or target_fragment is None or superseder_fragment is None:
                    raise ContradictionValidationError(
                        "SOURCE_SUPERSESSION_TARGET_MISSING"
                    )
                if (
                    target_claim.subject_id != claim.subject_id
                    or target_claim.environment != claim.environment
                    or target_claim.source_id != claim.source_id
                    or target_claim.stable_source_id != claim.stable_source_id
                ):
                    raise ContradictionValidationError(
                        "SOURCE_SUPERSESSION_BOUNDARY_MISMATCH"
                    )
                try:
                    verified = self._supersession_verifier.verify(
                        superseder_fragment, target_fragment
                    )
                except Exception as exc:
                    raise ContradictionValidationError(
                        "SOURCE_SUPERSESSION_VERIFIER_FAILED"
                    ) from exc
                if verified is not True:
                    raise ContradictionValidationError(
                        "SOURCE_SUPERSESSION_DIRECTION_UNVERIFIED"
                    )
                trusted.append(target_id)
            edges[claim.fragment_id] = tuple(trusted)
            result.append(
                replace(
                    claim,
                    supersedes_fragment_ids=tuple(trusted),
                    claim_hash=None,
                )
            )
        self._reject_supersession_cycles(edges)
        return tuple(result)

    @staticmethod
    def _reject_supersession_cycles(edges: dict[str, tuple[str, ...]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ContradictionValidationError("SOURCE_SUPERSESSION_CYCLE")
            if node in visited:
                return
            visiting.add(node)
            for target in edges.get(node, ()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(edges):
            visit(node)

    def _find_conflicts(self, claims: list[StructuredClaim]) -> tuple[_ConflictGroup, ...]:
        buckets: dict[tuple[str, str, str, str], list[StructuredClaim]] = {}
        for claim in claims:
            key = (
                claim.subject_id,
                claim.environment,
                claim.proposition_id,
                claim.scope_id,
            )
            buckets.setdefault(key, []).append(claim)
        result: list[_ConflictGroup] = []
        for (_, _, proposition_id, scope_id), group in sorted(buckets.items()):
            involved: dict[str, StructuredClaim] = {}
            kinds: list[ContradictionKind] = []
            ordered = sorted(group, key=lambda item: item.claim_id)
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    if not self._incompatible(left, right):
                        continue
                    involved[left.claim_id] = left
                    involved[right.claim_id] = right
                    kinds.append(self._kind_for(left, right))
            if involved:
                kind = (
                    ContradictionKind.COGNITIVE
                    if ContradictionKind.COGNITIVE in kinds
                    else ContradictionKind.EVIDENTIAL
                    if ContradictionKind.EVIDENTIAL in kinds
                    else ContradictionKind.EPISTEMIC
                )
                result.append(
                    _ConflictGroup(
                        proposition_id,
                        scope_id,
                        tuple(sorted(involved.values(), key=lambda item: item.claim_id)),
                        kind,
                    )
                )
        return tuple(result)

    @staticmethod
    def _incompatible(left: StructuredClaim, right: StructuredClaim) -> bool:
        if (
            left.source_id == right.source_id
            and left.stable_source_id == right.stable_source_id
            and (
                left.fragment_id in right.supersedes_fragment_ids
                or right.fragment_id in left.supersedes_fragment_ids
            )
        ):
            return False
        return (
            left.polarity is not right.polarity
            or left.canonical_value_hash != right.canonical_value_hash
        )

    def _verify_resolution_evidence(
        self,
        case: ContradictionCase,
        evidence: ResolutionEvidence,
        *,
        action: AuditAction,
    ) -> VerifiedResolutionEvidence:
        if not isinstance(evidence, ResolutionEvidence):
            raise ContradictionValidationError("resolution evidence is invalid")
        if evidence.subject_id != case.subject_id or evidence.environment != case.environment:
            raise ContradictionValidationError("resolution evidence crosses case boundary")
        verifier = self._resolution_evidence_verifier
        if verifier is None:
            raise ContradictionValidationError(
                "TRUSTED_RESOLUTION_EVIDENCE_VERIFIER_REQUIRED"
            )
        try:
            verified = verifier.verify(case, evidence, action=action)
        except ContradictionValidationError:
            raise
        except Exception as exc:
            raise ContradictionValidationError(
                "RESOLUTION_EVIDENCE_VERIFICATION_FAILED"
            ) from exc
        if not isinstance(verified, VerifiedResolutionEvidence):
            raise ContradictionValidationError(
                "resolution verifier returned invalid evidence"
            )
        validate_resolution_binding(case, verified, action)
        if (
            verified.resolution_id != evidence.resolution_id
            or verified.subject_id != case.subject_id
            or verified.environment != case.environment
            or verified.basis is not evidence.basis
            or verified.basis_reference_id != evidence.basis_reference_id
            or verified.source_hashes != evidence.source_hashes
            or verified.reason_code != evidence.reason_code
            or verified.resolved_at != evidence.resolved_at
            or verified.request_hash != evidence.canonical_hash()
        ):
            raise ContradictionValidationError(
                "verified resolution evidence binding mismatch"
            )
        expected_reasons = {
            ResolutionBasisKind.USER_CORRECTION: "VERIFIED_USER_CORRECTION",
            ResolutionBasisKind.SOURCE_SUPERSESSION: "VERIFIED_SOURCE_SUPERSESSION",
            ResolutionBasisKind.INDEPENDENT_CORROBORATION: "VERIFIED_INDEPENDENT_CORROBORATION",
            ResolutionBasisKind.EVOLUTION_RECORD: "VERIFIED_EVOLUTION_RECORD",
            ResolutionBasisKind.ERROR_SOURCE_PROOF: "VERIFIED_ERROR_SOURCE_PROOF",
        }
        if verified.reason_code != expected_reasons[verified.basis]:
            raise ContradictionValidationError(
                "resolution basis and reason code do not match"
            )
        return verified

    @staticmethod
    def _kind_for(left: StructuredClaim, right: StructuredClaim) -> ContradictionKind:
        authorities = {left.authority, right.authority}
        evidence = {left.evidence_type, right.evidence_type}
        if authorities.intersection(
            {ContextAuthority.CONFIRMED_STATE, ContextAuthority.CONFIRMED_MEMORY}
        ) and authorities.intersection(
            {ContextAuthority.RAW_SOURCE, ContextAuthority.RETRIEVED_CANDIDATE}
        ):
            return ContradictionKind.COGNITIVE
        if ClaimEvidenceType.ANALYTICAL in evidence and ClaimEvidenceType.EXTERNAL in evidence:
            return ContradictionKind.EVIDENTIAL
        return ContradictionKind.EPISTEMIC

    def _build_case(
        self,
        group: _ConflictGroup,
        snapshot_hash: str,
        detected_at: datetime,
    ) -> ContradictionCase:
        identity_seed = {
            "snapshot_hash": snapshot_hash,
            "claim_hashes": [item.claim_hash for item in group.claims],
            "detector_version": self.detector_version,
            "proposition_id": group.proposition_id,
            "scope_id": group.scope_id,
        }
        case_id = f"contradiction-{self._digest(identity_seed, 32)}"
        claim_hashes = tuple(item.claim_hash for item in group.claims)
        dispositions = tuple(
            ClaimDispositionRecord(
                item.claim_id,
                (
                    ClaimDisposition.RETAINED_DISPUTED
                    if item.authority
                    in {ContextAuthority.CONFIRMED_STATE, ContextAuthority.CONFIRMED_MEMORY}
                    else ClaimDisposition.ISOLATED
                    if item.authority
                    in {ContextAuthority.DERIVED_SUMMARY, ContextAuthority.RETRIEVED_CANDIDATE}
                    else ClaimDisposition.CONTESTED
                ),
                "CONFLICT_REQUIRES_VERIFICATION",
            )
            for item in group.claims
        )
        task = VerificationTask(
            task_id=f"verify-{self._digest({'case_id': case_id}, 24)}",
            required_claim_ids=tuple(item.claim_id for item in group.claims),
            conditions=(
                "VALID_CORRECTION_OR_REVOCATION",
                "VERIFIED_SOURCE_SUPERSESSION",
                "INDEPENDENT_CORROBORATION",
                "LEGAL_EVOLUTION_OR_ERROR_PROOF",
            ),
        )
        audit = (
            ContradictionAuditEntry(
                f"audit-{case_id}-0",
                0,
                AuditAction.DETECTED,
                detected_at,
                "INCOMPATIBLE_STRUCTURED_CLAIMS",
                claim_hashes,
            ),
            ContradictionAuditEntry(
                f"audit-{case_id}-1",
                1,
                AuditAction.ISOLATED,
                detected_at,
                "NO_AUTOMATIC_WINNER",
                claim_hashes,
            ),
        )
        first = group.claims[0]
        return ContradictionCase(
            case_id=case_id,
            kind=group.kind,
            subject_id=first.subject_id,
            environment=first.environment,
            proposition_id=group.proposition_id,
            scope_id=group.scope_id,
            claims=group.claims,
            dispositions=dispositions,
            impact_scope=("CONTEXT_MATERIAL_CONTESTED", "COGNITION_REVIEW_REQUIRED"),
            status=ContradictionStatus.PENDING_VERIFICATION,
            verification_task=task,
            audit_history=audit,
            source_snapshot_hash=snapshot_hash,
            detector_version=self.detector_version,
        )

    def _persist_or_return(self, case: ContradictionCase) -> ContradictionCase:
        if self._repository is None:
            return case
        return self._repository.save_detected(case)

    def _require_repository(self) -> ContradictionRepository:
        if self._repository is None:
            raise ContradictionNotFoundError("P07 repository is required for lifecycle transition")
        return self._repository

    def _read_clock(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ContradictionValidationError("P07 clock must return timezone-aware datetime")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _digest(value: object, length: int) -> str:
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:length]
