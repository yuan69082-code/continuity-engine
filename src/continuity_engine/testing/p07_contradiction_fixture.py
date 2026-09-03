from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from continuity_engine.domain.contradiction import (
    ClaimDomain,
    ClaimEvidenceType,
    ClaimPolarity,
    ClaimProjection,
    ContradictionCase,
    ContradictionDetectionResult,
    ResolutionBasisKind,
    ResolutionEvidence,
    VerifiedResolutionEvidence,
    contradiction_hash,
)
from continuity_engine.domain.context_composition import ComposedContextFragment
from continuity_engine.services.contradiction_detector_service import (
    ContradictionDetectorService,
)
from continuity_engine.storage.json_contradiction_repository import (
    JsonContradictionRepository,
)

from .p06_context_fixture import P06GoldenScenarioResult, run_p06_golden_scenario


P07_GOLDEN_SCENARIO_VERSION = "p07-contradiction-golden-v1"
P07_TEST_RESOLUTION_VERIFIER_ID = "p07-test-resolution-verifier-v1"
_VERSION_NUMBER = re.compile(r"(?:revision|version):([0-9]+)$")

# Versioned, synthetic evidence targets registered independently of caller projections.
# Do not infer these bindings from the case being verified.
_RESOLUTION_TARGETS = {
    "memory:day2-argument-fact": (
        "engine.memory", "revision:0",
        "sha256:e7087a59919507bed504606f62a404c5b6bab728febbee590e89c0719eb6d47d",
        ("event:day2-argument-fact",), contradiction_hash("conflict"),
    ),
    "memory:day2-reconciliation-fact": (
        "engine.memory", "revision:0",
        "sha256:1ff46deb4fa19f0eb6ac7937acc8cfb06f30740dc1ecfc275329c7c8745c714f",
        ("event:day2-reconciliation-fact",), contradiction_hash("reconciled"),
    ),
}


def _sha(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


class P07StructuredClaimFixtureResolver:
    """Deterministic TEST-only claim projection; no language inference or I/O."""

    def __init__(
        self,
        overrides: dict[str, ClaimProjection | None] | None = None,
        *,
        fail_fragment_id: str | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.fail_fragment_id = fail_fragment_id
        self._mapping = {
            "p03-golden-subject:relationship": ClaimProjection(
                "relationship.current_status",
                "reconciled",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.ANALYTICAL,
                ClaimDomain.COGNITIVE,
                "relationship:current",
            ),
            "memory:day2-argument-fact": ClaimProjection(
                "relationship.current_status",
                "conflict",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.FACTUAL,
                "relationship:current",
            ),
            "memory:day2-reconciliation-fact": ClaimProjection(
                "relationship.current_status",
                "reconciled",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.FACTUAL,
                "relationship:current",
            ),
            "summary:relationship:day2": ClaimProjection(
                "relationship.current_status",
                "mixed",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.ANALYTICAL,
                ClaimDomain.COGNITIVE,
                "relationship:current",
            ),
            "day2-conflict-state-change": ClaimProjection(
                "relationship.current_status",
                "conflict",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.FACTUAL,
                "relationship:current",
            ),
            "day2-reconciled-state-change": ClaimProjection(
                "relationship.current_status",
                "reconciled",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.FACTUAL,
                "relationship:current",
            ),
            "day2-reconciliation-fact": ClaimProjection(
                "relationship.current_status",
                "reconciled",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXTERNAL,
                ClaimDomain.FACTUAL,
                "relationship:current",
            ),
            "fact:relationship:love": ClaimProjection(
                "psychological.affection",
                "love",
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.PSYCHOLOGICAL,
                "psychological:current",
            ),
            "memory:day1-no-noodles-fact": ClaimProjection(
                "meal.actual_noodles",
                False,
                ClaimPolarity.DENIES,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.FACTUAL,
                "day1:evening",
            ),
            "memory:day1-noodle-intention": ClaimProjection(
                "meal.intention_noodles",
                True,
                ClaimPolarity.AFFIRMS,
                ClaimEvidenceType.EXPERIENTIAL,
                ClaimDomain.COGNITIVE,
                "day1:evening",
            ),
        }
        if overrides:
            self._mapping.update(overrides)

    def project(self, fragment: ComposedContextFragment) -> ClaimProjection | None:
        self.calls.append(fragment.fragment_id)
        if fragment.fragment_id == self.fail_fragment_id:
            raise RuntimeError("fixture claim resolver fault")
        return self._mapping.get(fragment.stable_source_id)


@dataclass(frozen=True, slots=True)
class _TrustedResolutionFixtureRecord:
    resolution_id: str
    subject_id: str
    environment: str
    basis: ResolutionBasisKind
    basis_reference_id: str
    basis_reference_version: str
    source_hashes: tuple[str, ...]
    provenance_roots: tuple[str, ...]
    reason_code: str
    resolved_at: datetime
    allowed_actions: tuple[str, ...]
    proposition_id: str = "relationship.current_status"
    scope_id: str = "relationship:current"
    target_stable_source_ids: tuple[str, ...] = (
        "memory:day2-argument-fact", "memory:day2-reconciliation-fact",
    )


def _trusted_resolution_records() -> dict[str, _TrustedResolutionFixtureRecord]:
    subject = "p03-golden-subject"
    records = (
        _TrustedResolutionFixtureRecord(
            "resolution-user-correction-v1",
            subject,
            "TEST",
            ResolutionBasisKind.USER_CORRECTION,
            "user-correction:verified:v1",
            "version:1",
            (_sha("verified-user-correction"),),
            ("event:user-correction:verified:v1",),
            "VERIFIED_USER_CORRECTION",
            datetime(2026, 9, 3, 8, 30, tzinfo=timezone.utc),
            ("RESOLVED",),
        ),
        _TrustedResolutionFixtureRecord(
            "resolution-source-supersession-v2",
            subject,
            "TEST",
            ResolutionBasisKind.SOURCE_SUPERSESSION,
            "source-supersession:verified:v2",
            "version:2",
            (_sha("verified-source-supersession"),),
            ("source:versioned-record:v2",),
            "VERIFIED_SOURCE_SUPERSESSION",
            datetime(2026, 9, 3, 9, 30, tzinfo=timezone.utc),
            ("RESOLVED", "SUPERSEDED"),
        ),
        _TrustedResolutionFixtureRecord(
            "resolution-independent-v1",
            subject,
            "TEST",
            ResolutionBasisKind.INDEPENDENT_CORROBORATION,
            "independent-corroboration:verified:v1",
            "version:1",
            (_sha("verified-independent-corroboration"),),
            ("event:independent-corroboration:verified:v1",),
            "VERIFIED_INDEPENDENT_CORROBORATION",
            datetime(2026, 9, 3, 8, 45, tzinfo=timezone.utc),
            ("RESOLVED",),
        ),
        _TrustedResolutionFixtureRecord(
            "resolution-independent-reopen-v1",
            subject,
            "TEST",
            ResolutionBasisKind.INDEPENDENT_CORROBORATION,
            "independent-corroboration:new:v1",
            "version:1",
            (_sha("new-independent-conflicting-evidence"),),
            ("event:independent-corroboration:new:v1",),
            "VERIFIED_INDEPENDENT_CORROBORATION",
            datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
            ("REOPENED",),
        ),
        _TrustedResolutionFixtureRecord(
            "resolution-evolution-record-v1",
            subject,
            "TEST",
            ResolutionBasisKind.EVOLUTION_RECORD,
            "evolution-record:verified:v1",
            "revision:1",
            (_sha("verified-evolution-record"),),
            ("evolution:verified:v1",),
            "VERIFIED_EVOLUTION_RECORD",
            datetime(2026, 9, 3, 8, 50, tzinfo=timezone.utc),
            ("RESOLVED",),
        ),
        _TrustedResolutionFixtureRecord(
            "resolution-error-proof-v1",
            subject,
            "TEST",
            ResolutionBasisKind.ERROR_SOURCE_PROOF,
            "error-source-proof:verified:v1",
            "version:1",
            (_sha("verified-error-source-proof"),),
            ("audit:error-source-proof:verified:v1",),
            "VERIFIED_ERROR_SOURCE_PROOF",
            datetime(2026, 9, 3, 8, 55, tzinfo=timezone.utc),
            ("RESOLVED",),
        ),
    )
    return {item.basis_reference_id: item for item in records}


def p07_resolution_evidence(reference_id: str) -> ResolutionEvidence:
    record = _trusted_resolution_records()[reference_id]
    return ResolutionEvidence(
        record.resolution_id,
        record.subject_id,
        record.environment,
        record.basis,
        record.basis_reference_id,
        record.source_hashes,
        record.reason_code,
        record.resolved_at,
    )


class P07DeterministicResolutionEvidenceVerifier:
    """TEST-only registry-backed verifier; no network, Provider, Vio, or Store I/O."""

    def __init__(self) -> None:
        self._records = _trusted_resolution_records()

    def verify(
        self,
        case: ContradictionCase,
        evidence: ResolutionEvidence,
        *,
        action,
    ) -> VerifiedResolutionEvidence:
        record = self._records.get(evidence.basis_reference_id)
        if record is None:
            raise ValueError("trusted resolution evidence is missing")
        actual = (
            evidence.resolution_id,
            evidence.subject_id,
            evidence.environment,
            evidence.basis,
            evidence.basis_reference_id,
            evidence.source_hashes,
            evidence.reason_code,
            evidence.resolved_at,
        )
        expected = (
            record.resolution_id,
            record.subject_id,
            record.environment,
            record.basis,
            record.basis_reference_id,
            record.source_hashes,
            record.reason_code,
            record.resolved_at,
        )
        if actual != expected:
            raise ValueError("resolution evidence identity, version, hash, or basis drift")
        if case.subject_id != record.subject_id or case.environment != record.environment:
            raise ValueError("resolution evidence crosses case boundary")
        if action.value not in record.allowed_actions:
            raise ValueError("resolution evidence action is not authorized")
        if case.proposition_id != record.proposition_id or case.scope_id != record.scope_id:
            raise ValueError("resolution evidence does not apply to proposition/scope")
        applicable = tuple(item for item in case.claims
                           if item.stable_source_id in record.target_stable_source_ids)
        if {item.stable_source_id for item in applicable} != set(record.target_stable_source_ids):
            raise ValueError("resolution evidence does not cover the required target sources")
        for claim in applicable:
            if (
                (claim.source_id, claim.source_version, claim.source_content_hash,
                 claim.provenance_roots, claim.canonical_value_hash)
                != _RESOLUTION_TARGETS[claim.stable_source_id]
                or claim.authority.value != "confirmed_memory"
                or claim.polarity is not ClaimPolarity.AFFIRMS
                or claim.evidence_type is not ClaimEvidenceType.EXPERIENTIAL
            ):
                raise ValueError("resolution target source version/hash/provenance/claim drift")
        return VerifiedResolutionEvidence(
            resolution_id=record.resolution_id,
            subject_id=record.subject_id,
            environment=record.environment,
            basis=record.basis,
            basis_reference_id=record.basis_reference_id,
            basis_reference_version=record.basis_reference_version,
            source_hashes=record.source_hashes,
            provenance_roots=record.provenance_roots,
            reason_code=record.reason_code,
            resolved_at=record.resolved_at,
            verifier_id=P07_TEST_RESOLUTION_VERIFIER_ID,
            request_hash=evidence.canonical_hash(),
            target_case_id=case.case_id,
            target_case_revision=case.revision,
            target_case_hash=case.canonical_hash(),
            source_snapshot_hash=case.source_snapshot_hash,
            detector_version=case.detector_version,
            proposition_id=record.proposition_id,
            scope_id=record.scope_id,
            target_claim_hashes=tuple(item.claim_hash for item in case.claims),
            applicable_claim_hashes=tuple(item.claim_hash for item in applicable),
            allowed_action=action,
        )


class P07DeterministicSourceVersionVerifier:
    """TEST-only trusted binding for a monotonic revision/version source pair."""

    def verify(
        self,
        superseder: ComposedContextFragment,
        target: ComposedContextFragment,
    ) -> bool:
        if (
            superseder.subject_id != target.subject_id
            or superseder.environment != target.environment
            or superseder.source_id != target.source_id
            or superseder.stable_source_id != target.stable_source_id
            or superseder.fragment_id == target.fragment_id
        ):
            return False
        new_match = _VERSION_NUMBER.fullmatch(superseder.version)
        old_match = _VERSION_NUMBER.fullmatch(target.version)
        if new_match is None or old_match is None:
            return False
        return (
            int(new_match.group(1)) > int(old_match.group(1))
            and superseder.occurred_at >= target.occurred_at
        )


@dataclass(frozen=True, slots=True)
class P07GoldenScenarioResult:
    version: str
    p06: P06GoldenScenarioResult
    detection: ContradictionDetectionResult
    resolved: ContradictionCase
    reloaded: ContradictionCase
    reopened: ContradictionCase
    resolver_call_count: int
    subject_document_hash_before: str
    subject_document_hash_after: str
    memory_document_hash_before: str
    memory_document_hash_after: str
    p06_hash_before: str
    p06_hash_after: str


def build_p07_detector(
    root: Path | str,
    *,
    resolver: P07StructuredClaimFixtureResolver | None = None,
) -> tuple[
    ContradictionDetectorService,
    JsonContradictionRepository,
    P07StructuredClaimFixtureResolver,
]:
    effective = resolver or P07StructuredClaimFixtureResolver()
    verifier = P07DeterministicResolutionEvidenceVerifier()
    repository = JsonContradictionRepository(
        root, environment="TEST", resolution_evidence_verifier=verifier,
    )
    service = ContradictionDetectorService(
        effective,
        repository,
        clock=lambda: datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
        resolution_evidence_verifier=verifier,
        supersession_verifier=P07DeterministicSourceVersionVerifier(),
    )
    return service, repository, effective


def run_p07_golden_scenario(root: Path | str) -> P07GoldenScenarioResult:
    """Detect, isolate, resolve, reload, and reopen without touching authorities."""

    root_path = Path(root)
    p06 = run_p06_golden_scenario(root_path)
    service, repository, resolver = build_p07_detector(root_path)
    p06_hash_before = p06.composition.canonical_hash()
    detection = service.detect(p06.composition)
    if not detection.cases:
        raise AssertionError("P07 golden scenario did not detect a contradiction")
    case = detection.cases[0]
    resolution = p07_resolution_evidence("user-correction:verified:v1")
    resolved = service.resolve(case.subject_id, case.case_id, resolution)
    restarted, restarted_repository, _ = build_p07_detector(root_path)
    reloaded = restarted_repository.load_case(case.subject_id, case.case_id)
    reopened = restarted.reopen(
        case.subject_id,
        case.case_id,
        p07_resolution_evidence("independent-corroboration:new:v1"),
    )
    return P07GoldenScenarioResult(
        P07_GOLDEN_SCENARIO_VERSION,
        p06,
        detection,
        resolved,
        reloaded,
        reopened,
        len(resolver.calls),
        p06.subject_document_hash_before,
        p06.subject_document_hash_after,
        p06.memory_document_hash_before,
        p06.memory_document_hash_after,
        p06_hash_before,
        p06.composition.canonical_hash(),
    )
