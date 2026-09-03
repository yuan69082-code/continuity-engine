from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from .context_composition import ContextAuthority
from .errors import ContradictionValidationError
from .events import JsonValue


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def contradiction_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContradictionValidationError(f"{name} must be a non-empty string")
    return value


def _identifier(value: Any, name: str) -> str:
    result = _text(value, name)
    if _IDENTIFIER.fullmatch(result) is None:
        raise ContradictionValidationError(f"{name} contains unsupported characters")
    return result


def _reason(value: Any, name: str) -> str:
    result = _text(value, name)
    if _REASON.fullmatch(result) is None:
        raise ContradictionValidationError(f"{name} must be a stable reason code")
    return result


def _sha(value: Any, name: str) -> str:
    result = _text(value, name)
    if _SHA256.fullmatch(result) is None:
        raise ContradictionValidationError(f"{name} must be SHA-256")
    return result


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContradictionValidationError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _utc(value, "datetime").isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ContradictionValidationError(f"{name} must be ISO-8601")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), name)
    except ValueError as exc:
        raise ContradictionValidationError(f"{name} is not valid ISO-8601") from exc


def _unique(values: Iterable[str], name: str, *, required: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContradictionValidationError(f"{name} must be a sequence")
    result = tuple(values)
    if required and not result:
        raise ContradictionValidationError(f"{name} cannot be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ContradictionValidationError(f"{name} contains an empty value")
    if len(result) != len(set(result)):
        raise ContradictionValidationError(f"{name} contains duplicates")
    return result


def _json_scalar(value: Any, name: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ContradictionValidationError(f"{name} must be a JSON scalar")


class ContradictionKind(str, Enum):
    EPISTEMIC = "EPISTEMIC"
    EVIDENTIAL = "EVIDENTIAL"
    COGNITIVE = "COGNITIVE"


class ClaimDomain(str, Enum):
    FACTUAL = "FACTUAL"
    COGNITIVE = "COGNITIVE"
    PSYCHOLOGICAL = "PSYCHOLOGICAL"


class ClaimEvidenceType(str, Enum):
    EXPERIENTIAL = "experiential"
    ANALYTICAL = "analytical"
    EXTERNAL = "external"


class ClaimPolarity(str, Enum):
    AFFIRMS = "AFFIRMS"
    DENIES = "DENIES"


class ClaimEvaluationStatus(str, Enum):
    EVALUATED = "EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNASSESSED = "UNASSESSED"


class ClaimDisposition(str, Enum):
    CONTESTED = "CONTESTED"
    DOWNGRADED = "DOWNGRADED"
    ISOLATED = "ISOLATED"
    RETAINED_DISPUTED = "RETAINED_DISPUTED"


class ContradictionStatus(str, Enum):
    OPEN = "OPEN"
    ISOLATED = "ISOLATED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class VerificationStatus(str, Enum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"


class AuditAction(str, Enum):
    DETECTED = "DETECTED"
    ISOLATED = "ISOLATED"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class ResolutionBasisKind(str, Enum):
    USER_CORRECTION = "USER_CORRECTION"
    SOURCE_SUPERSESSION = "SOURCE_SUPERSESSION"
    INDEPENDENT_CORROBORATION = "INDEPENDENT_CORROBORATION"
    EVOLUTION_RECORD = "EVOLUTION_RECORD"
    ERROR_SOURCE_PROOF = "ERROR_SOURCE_PROOF"


class ContradictionDetectionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ClaimProjection:
    """Semantic-only output from a trusted deterministic claim adapter.

    Source authority, provenance, identity, version, time and content hash are
    deliberately absent: the detector seals them from the P06 fragment.
    """

    proposition_id: str
    canonical_value: JsonValue
    polarity: ClaimPolarity
    evidence_type: ClaimEvidenceType
    domain: ClaimDomain
    scope_id: str
    supersedes_fragment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.proposition_id, "projection proposition_id")
        _json_scalar(self.canonical_value, "projection canonical_value")
        object.__setattr__(self, "polarity", ClaimPolarity(self.polarity))
        object.__setattr__(self, "evidence_type", ClaimEvidenceType(self.evidence_type))
        object.__setattr__(self, "domain", ClaimDomain(self.domain))
        _identifier(self.scope_id, "projection scope_id")
        object.__setattr__(
            self,
            "supersedes_fragment_ids",
            _unique(self.supersedes_fragment_ids, "projection supersedes_fragment_ids"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "proposition_id": self.proposition_id,
            "canonical_value": self.canonical_value,
            "polarity": self.polarity.value,
            "evidence_type": self.evidence_type.value,
            "domain": self.domain.value,
            "scope_id": self.scope_id,
            "supersedes_fragment_ids": list(self.supersedes_fragment_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ClaimProjection:
        if not isinstance(value, dict):
            raise ContradictionValidationError("claim projection must be an object")
        return cls(
            value.get("proposition_id"),
            value.get("canonical_value"),
            value.get("polarity"),
            value.get("evidence_type"),
            value.get("domain"),
            value.get("scope_id"),
            tuple(value.get("supersedes_fragment_ids", [])),
        )


@dataclass(frozen=True, slots=True)
class StructuredClaim:
    claim_id: str
    fragment_id: str
    subject_id: str
    environment: str
    proposition_id: str
    canonical_value_hash: str
    polarity: ClaimPolarity
    evidence_type: ClaimEvidenceType
    domain: ClaimDomain
    authority: ContextAuthority
    source_id: str
    stable_source_id: str
    source_version: str
    source_content_hash: str
    provenance_roots: tuple[str, ...]
    occurred_at: datetime
    scope_id: str
    supersedes_fragment_ids: tuple[str, ...] = ()
    claim_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.claim_id, "claim_id"),
            (self.fragment_id, "claim fragment_id"),
            (self.subject_id, "claim subject_id"),
            (self.proposition_id, "claim proposition_id"),
            (self.source_id, "claim source_id"),
            (self.stable_source_id, "claim stable_source_id"),
            (self.source_version, "claim source_version"),
            (self.scope_id, "claim scope_id"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError("claim environment is unsupported")
        _sha(self.canonical_value_hash, "claim canonical_value_hash")
        object.__setattr__(self, "polarity", ClaimPolarity(self.polarity))
        object.__setattr__(self, "evidence_type", ClaimEvidenceType(self.evidence_type))
        object.__setattr__(self, "domain", ClaimDomain(self.domain))
        object.__setattr__(self, "authority", ContextAuthority(self.authority))
        _sha(self.source_content_hash, "claim source_content_hash")
        object.__setattr__(
            self,
            "provenance_roots",
            _unique(self.provenance_roots, "claim provenance_roots", required=True),
        )
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "claim occurred_at"))
        object.__setattr__(
            self,
            "supersedes_fragment_ids",
            _unique(self.supersedes_fragment_ids, "claim supersedes_fragment_ids"),
        )
        expected = contradiction_hash(self.canonical_dict())
        if self.claim_hash is None:
            object.__setattr__(self, "claim_hash", expected)
        elif self.claim_hash != expected:
            raise ContradictionValidationError("claim integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "claim_id": self.claim_id,
            "fragment_id": self.fragment_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "proposition_id": self.proposition_id,
            "canonical_value_hash": self.canonical_value_hash,
            "polarity": self.polarity.value,
            "evidence_type": self.evidence_type.value,
            "domain": self.domain.value,
            "authority": self.authority.value,
            "source_id": self.source_id,
            "stable_source_id": self.stable_source_id,
            "source_version": self.source_version,
            "source_content_hash": self.source_content_hash,
            "provenance_roots": list(self.provenance_roots),
            "occurred_at": _format_time(self.occurred_at),
            "scope_id": self.scope_id,
            "supersedes_fragment_ids": list(self.supersedes_fragment_ids),
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "claim_hash": self.claim_hash}

    @classmethod
    def from_dict(cls, value: Any) -> StructuredClaim:
        if not isinstance(value, dict):
            raise ContradictionValidationError("structured claim must be an object")
        return cls(
            claim_id=value.get("claim_id"),
            fragment_id=value.get("fragment_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            proposition_id=value.get("proposition_id"),
            canonical_value_hash=value.get("canonical_value_hash"),
            polarity=value.get("polarity"),
            evidence_type=value.get("evidence_type"),
            domain=value.get("domain"),
            authority=value.get("authority"),
            source_id=value.get("source_id"),
            stable_source_id=value.get("stable_source_id"),
            source_version=value.get("source_version"),
            source_content_hash=value.get("source_content_hash"),
            provenance_roots=tuple(value.get("provenance_roots", [])),
            occurred_at=_parse_time(value.get("occurred_at"), "claim occurred_at"),
            scope_id=value.get("scope_id"),
            supersedes_fragment_ids=tuple(value.get("supersedes_fragment_ids", [])),
            claim_hash=value.get("claim_hash"),
        )


@dataclass(frozen=True, slots=True)
class ClaimEvaluation:
    fragment_id: str
    status: ClaimEvaluationStatus
    reason_code: str
    claim_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.fragment_id, "evaluation fragment_id")
        object.__setattr__(self, "status", ClaimEvaluationStatus(self.status))
        _reason(self.reason_code, "evaluation reason_code")
        if self.claim_id is not None:
            _identifier(self.claim_id, "evaluation claim_id")
        if self.status is ClaimEvaluationStatus.EVALUATED and self.claim_id is None:
            raise ContradictionValidationError("evaluated material requires claim_id")
        if self.status is not ClaimEvaluationStatus.EVALUATED and self.claim_id is not None:
            raise ContradictionValidationError("non-evaluated material cannot expose claim_id")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "fragment_id": self.fragment_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "claim_id": self.claim_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ClaimEvaluation:
        if not isinstance(value, dict):
            raise ContradictionValidationError("claim evaluation must be an object")
        return cls(
            value.get("fragment_id"),
            value.get("status"),
            value.get("reason_code"),
            value.get("claim_id"),
        )


@dataclass(frozen=True, slots=True)
class ClaimDispositionRecord:
    claim_id: str
    disposition: ClaimDisposition
    reason_code: str

    def __post_init__(self) -> None:
        _identifier(self.claim_id, "disposition claim_id")
        object.__setattr__(self, "disposition", ClaimDisposition(self.disposition))
        _reason(self.reason_code, "disposition reason_code")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "claim_id": self.claim_id,
            "disposition": self.disposition.value,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ClaimDispositionRecord:
        if not isinstance(value, dict):
            raise ContradictionValidationError("claim disposition must be an object")
        return cls(value.get("claim_id"), value.get("disposition"), value.get("reason_code"))


@dataclass(frozen=True, slots=True)
class VerificationTask:
    task_id: str
    required_claim_ids: tuple[str, ...]
    conditions: tuple[str, ...]
    status: VerificationStatus = VerificationStatus.OPEN

    def __post_init__(self) -> None:
        _identifier(self.task_id, "verification task_id")
        object.__setattr__(
            self,
            "required_claim_ids",
            _unique(self.required_claim_ids, "verification required_claim_ids", required=True),
        )
        object.__setattr__(
            self,
            "conditions",
            _unique(self.conditions, "verification conditions", required=True),
        )
        for condition in self.conditions:
            _reason(condition, "verification condition")
        object.__setattr__(self, "status", VerificationStatus(self.status))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "task_id": self.task_id,
            "required_claim_ids": list(self.required_claim_ids),
            "conditions": list(self.conditions),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> VerificationTask:
        if not isinstance(value, dict):
            raise ContradictionValidationError("verification task must be an object")
        return cls(
            value.get("task_id"),
            tuple(value.get("required_claim_ids", [])),
            tuple(value.get("conditions", [])),
            value.get("status", VerificationStatus.OPEN.value),
        )


@dataclass(frozen=True, slots=True)
class ResolutionEvidence:
    resolution_id: str
    subject_id: str
    environment: str
    basis: ResolutionBasisKind
    basis_reference_id: str
    source_hashes: tuple[str, ...]
    reason_code: str
    resolved_at: datetime
    verified: bool = False

    def __post_init__(self) -> None:
        _identifier(self.resolution_id, "resolution_id")
        _identifier(self.subject_id, "resolution subject_id")
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError("resolution environment is unsupported")
        object.__setattr__(self, "basis", ResolutionBasisKind(self.basis))
        _identifier(self.basis_reference_id, "resolution basis_reference_id")
        object.__setattr__(
            self, "source_hashes", _unique(self.source_hashes, "resolution source_hashes", required=True)
        )
        for item in self.source_hashes:
            _sha(item, "resolution source hash")
        _reason(self.reason_code, "resolution reason_code")
        object.__setattr__(self, "resolved_at", _utc(self.resolved_at, "resolution resolved_at"))
        if not isinstance(self.verified, bool):
            raise ContradictionValidationError("resolution verified claim must be boolean")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "resolution_id": self.resolution_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "basis": self.basis.value,
            "basis_reference_id": self.basis_reference_id,
            "source_hashes": list(self.source_hashes),
            "reason_code": self.reason_code,
            "resolved_at": _format_time(self.resolved_at),
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResolutionEvidence:
        if not isinstance(value, dict):
            raise ContradictionValidationError("resolution evidence must be an object")
        return cls(
            value.get("resolution_id"),
            value.get("subject_id"),
            value.get("environment"),
            value.get("basis"),
            value.get("basis_reference_id"),
            tuple(value.get("source_hashes", [])),
            value.get("reason_code"),
            _parse_time(value.get("resolved_at"), "resolution resolved_at"),
            value.get("verified"),
        )

    def canonical_hash(self) -> str:
        """Hash the request fields; the caller's self-attested flag grants no trust."""

        value = self.to_dict()
        value.pop("verified")
        return contradiction_hash(value)


@dataclass(frozen=True, slots=True)
class VerifiedResolutionEvidence:
    """Evidence sealed by a configured trusted verifier, never by its caller."""

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
    verifier_id: str
    request_hash: str
    target_case_id: str
    target_case_revision: int
    target_case_hash: str
    source_snapshot_hash: str
    detector_version: str
    proposition_id: str
    scope_id: str
    target_claim_hashes: tuple[str, ...]
    applicable_claim_hashes: tuple[str, ...]
    allowed_action: AuditAction
    verification_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.resolution_id, "verified resolution_id"),
            (self.subject_id, "verified resolution subject_id"),
            (self.basis_reference_id, "verified resolution basis_reference_id"),
            (self.basis_reference_version, "verified resolution basis_reference_version"),
            (self.verifier_id, "verified resolution verifier_id"),
            (self.target_case_id, "verified target case_id"),
            (self.detector_version, "verified detector_version"),
            (self.proposition_id, "verified proposition_id"),
            (self.scope_id, "verified scope_id"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError(
                "verified resolution environment is unsupported"
            )
        object.__setattr__(self, "basis", ResolutionBasisKind(self.basis))
        object.__setattr__(
            self,
            "source_hashes",
            _unique(self.source_hashes, "verified resolution source_hashes", required=True),
        )
        for item in self.source_hashes:
            _sha(item, "verified resolution source hash")
        object.__setattr__(
            self,
            "provenance_roots",
            _unique(
                self.provenance_roots,
                "verified resolution provenance_roots",
                required=True,
            ),
        )
        for item in self.provenance_roots:
            _identifier(item, "verified resolution provenance root")
        _reason(self.reason_code, "verified resolution reason_code")
        object.__setattr__(
            self,
            "resolved_at",
            _utc(self.resolved_at, "verified resolution resolved_at"),
        )
        _sha(self.request_hash, "verified resolution request_hash")
        _sha(self.target_case_hash, "verified target case_hash")
        _sha(self.source_snapshot_hash, "verified source_snapshot_hash")
        if (isinstance(self.target_case_revision, bool)
                or not isinstance(self.target_case_revision, int)
                or self.target_case_revision < 0):
            raise ContradictionValidationError("verified target revision is invalid")
        for name in ("target_claim_hashes", "applicable_claim_hashes"):
            values = _unique(getattr(self, name), name, required=True)
            for item in values:
                _sha(item, name)
            object.__setattr__(self, name, values)
        if not set(self.applicable_claim_hashes).issubset(self.target_claim_hashes):
            raise ContradictionValidationError("verified evidence has unrelated target claims")
        object.__setattr__(self, "allowed_action", AuditAction(self.allowed_action))
        if self.allowed_action not in {AuditAction.RESOLVED, AuditAction.REOPENED, AuditAction.SUPERSEDED}:
            raise ContradictionValidationError("verified evidence action is invalid")
        if self.reason_code != resolution_reason(self.basis):
            raise ContradictionValidationError("resolution basis/reason mismatch")
        if self.allowed_action is AuditAction.REOPENED and self.basis is not ResolutionBasisKind.INDEPENDENT_CORROBORATION:
            raise ContradictionValidationError("reopen requires independent evidence")
        if self.allowed_action is AuditAction.SUPERSEDED and self.basis is not ResolutionBasisKind.SOURCE_SUPERSESSION:
            raise ContradictionValidationError("supersede requires source supersession")
        if self.request_hash != self.as_request().canonical_hash():
            raise ContradictionValidationError("verified resolution request binding mismatch")
        expected = contradiction_hash(self.canonical_dict())
        if self.verification_hash is None:
            object.__setattr__(self, "verification_hash", expected)
        elif self.verification_hash != expected:
            raise ContradictionValidationError(
                "verified resolution integrity check failed"
            )

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "resolution_id": self.resolution_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "basis": self.basis.value,
            "basis_reference_id": self.basis_reference_id,
            "basis_reference_version": self.basis_reference_version,
            "source_hashes": list(self.source_hashes),
            "provenance_roots": list(self.provenance_roots),
            "reason_code": self.reason_code,
            "resolved_at": _format_time(self.resolved_at),
            "verifier_id": self.verifier_id,
            "request_hash": self.request_hash,
            "target_case_id": self.target_case_id,
            "target_case_revision": self.target_case_revision,
            "target_case_hash": self.target_case_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
            "detector_version": self.detector_version,
            "proposition_id": self.proposition_id,
            "scope_id": self.scope_id,
            "target_claim_hashes": list(self.target_claim_hashes),
            "applicable_claim_hashes": list(self.applicable_claim_hashes),
            "allowed_action": self.allowed_action.value,
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "verification_hash": self.verification_hash}

    @classmethod
    def from_dict(cls, value: Any) -> VerifiedResolutionEvidence:
        if not isinstance(value, dict):
            raise ContradictionValidationError(
                "verified resolution evidence must be an object"
            )
        return cls(
            resolution_id=value.get("resolution_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            basis=value.get("basis"),
            basis_reference_id=value.get("basis_reference_id"),
            basis_reference_version=value.get("basis_reference_version"),
            source_hashes=tuple(value.get("source_hashes", [])),
            provenance_roots=tuple(value.get("provenance_roots", [])),
            reason_code=value.get("reason_code"),
            resolved_at=_parse_time(
                value.get("resolved_at"), "verified resolution resolved_at"
            ),
            verifier_id=value.get("verifier_id"),
            request_hash=value.get("request_hash"),
            target_case_id=value.get("target_case_id"),
            target_case_revision=value.get("target_case_revision"),
            target_case_hash=value.get("target_case_hash"),
            source_snapshot_hash=value.get("source_snapshot_hash"),
            detector_version=value.get("detector_version"),
            proposition_id=value.get("proposition_id"),
            scope_id=value.get("scope_id"),
            target_claim_hashes=tuple(value.get("target_claim_hashes", [])),
            applicable_claim_hashes=tuple(value.get("applicable_claim_hashes", [])),
            allowed_action=value.get("allowed_action"),
            verification_hash=value.get("verification_hash"),
        )

    def as_request(self) -> ResolutionEvidence:
        return ResolutionEvidence(
            self.resolution_id, self.subject_id, self.environment, self.basis,
            self.basis_reference_id, self.source_hashes, self.reason_code, self.resolved_at,
        )


def resolution_reason(basis: ResolutionBasisKind) -> str:
    return {
        ResolutionBasisKind.USER_CORRECTION: "VERIFIED_USER_CORRECTION",
        ResolutionBasisKind.SOURCE_SUPERSESSION: "VERIFIED_SOURCE_SUPERSESSION",
        ResolutionBasisKind.INDEPENDENT_CORROBORATION: "VERIFIED_INDEPENDENT_CORROBORATION",
        ResolutionBasisKind.EVOLUTION_RECORD: "VERIFIED_EVOLUTION_RECORD",
        ResolutionBasisKind.ERROR_SOURCE_PROOF: "VERIFIED_ERROR_SOURCE_PROOF",
    }[basis]


@dataclass(frozen=True, slots=True)
class ContradictionAuditEntry:
    audit_id: str
    sequence: int
    action: AuditAction
    occurred_at: datetime
    reason_code: str
    source_hashes: tuple[str, ...]
    resolution: VerifiedResolutionEvidence | None = None

    def __post_init__(self) -> None:
        _identifier(self.audit_id, "audit_id")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ContradictionValidationError("audit sequence must be non-negative")
        object.__setattr__(self, "action", AuditAction(self.action))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "audit occurred_at"))
        _reason(self.reason_code, "audit reason_code")
        object.__setattr__(
            self, "source_hashes", _unique(self.source_hashes, "audit source_hashes", required=True)
        )
        for item in self.source_hashes:
            _sha(item, "audit source hash")
        evidence_actions = {
            AuditAction.RESOLVED,
            AuditAction.REOPENED,
            AuditAction.SUPERSEDED,
        }
        if self.action in evidence_actions and not isinstance(
            self.resolution, VerifiedResolutionEvidence
        ):
            raise ContradictionValidationError(
                "resolution, reopen, and supersession audits require verified evidence"
            )
        if self.action not in evidence_actions and self.resolution is not None:
            raise ContradictionValidationError(
                "this audit action cannot carry verified resolution evidence"
            )
        if self.resolution is not None and (
            self.action is not self.resolution.allowed_action
            or self.reason_code != self.resolution.reason_code
            or self.source_hashes != self.resolution.source_hashes
            or self.occurred_at != self.resolution.resolved_at
        ):
            raise ContradictionValidationError("audit differs from verified action/reason/hashes/time")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "audit_id": self.audit_id,
            "sequence": self.sequence,
            "action": self.action.value,
            "occurred_at": _format_time(self.occurred_at),
            "reason_code": self.reason_code,
            "source_hashes": list(self.source_hashes),
            "resolution": self.resolution.to_dict() if self.resolution else None,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContradictionAuditEntry:
        if not isinstance(value, dict):
            raise ContradictionValidationError("audit entry must be an object")
        resolution = value.get("resolution")
        return cls(
            value.get("audit_id"),
            value.get("sequence"),
            value.get("action"),
            _parse_time(value.get("occurred_at"), "audit occurred_at"),
            value.get("reason_code"),
            tuple(value.get("source_hashes", [])),
            VerifiedResolutionEvidence.from_dict(resolution)
            if resolution is not None
            else None,
        )


@dataclass(frozen=True, slots=True)
class ContradictionCase:
    case_id: str
    kind: ContradictionKind
    subject_id: str
    environment: str
    proposition_id: str
    scope_id: str
    claims: tuple[StructuredClaim, ...]
    dispositions: tuple[ClaimDispositionRecord, ...]
    impact_scope: tuple[str, ...]
    status: ContradictionStatus
    verification_task: VerificationTask
    audit_history: tuple[ContradictionAuditEntry, ...]
    source_snapshot_hash: str
    detector_version: str
    revision: int = 0
    direct_state_write_allowed: bool = False
    evolution_commit_allowed: bool = False
    case_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.case_id, "case_id"),
            (self.subject_id, "case subject_id"),
            (self.proposition_id, "case proposition_id"),
            (self.scope_id, "case scope_id"),
            (self.detector_version, "case detector_version"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError("case environment is unsupported")
        object.__setattr__(self, "kind", ContradictionKind(self.kind))
        object.__setattr__(self, "status", ContradictionStatus(self.status))
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ContradictionValidationError("case revision must be non-negative")
        if len(self.claims) < 2 or any(not isinstance(item, StructuredClaim) for item in self.claims):
            raise ContradictionValidationError("case requires at least two structured claims")
        if tuple(item.claim_id for item in self.claims) != tuple(
            sorted(item.claim_id for item in self.claims)
        ):
            raise ContradictionValidationError("case claims must use stable identity order")
        if len({item.claim_id for item in self.claims}) != len(self.claims):
            raise ContradictionValidationError("case contains duplicate claims")
        if any(
            item.subject_id != self.subject_id
            or item.environment != self.environment
            or item.proposition_id != self.proposition_id
            or item.scope_id != self.scope_id
            or item.domain is ClaimDomain.PSYCHOLOGICAL
            for item in self.claims
        ):
            raise ContradictionValidationError("case claim boundary mismatch")
        if any(not isinstance(item, ClaimDispositionRecord) for item in self.dispositions):
            raise ContradictionValidationError("case dispositions are invalid")
        if {item.claim_id for item in self.dispositions} != {item.claim_id for item in self.claims}:
            raise ContradictionValidationError("case dispositions must cover every claim")
        object.__setattr__(
            self, "impact_scope", _unique(self.impact_scope, "case impact_scope", required=True)
        )
        for item in self.impact_scope:
            _reason(item, "case impact scope")
        if not isinstance(self.verification_task, VerificationTask):
            raise ContradictionValidationError("case verification task is invalid")
        if set(self.verification_task.required_claim_ids) != {item.claim_id for item in self.claims}:
            raise ContradictionValidationError("verification task must bind every case claim")
        if not self.audit_history or any(
            not isinstance(item, ContradictionAuditEntry) for item in self.audit_history
        ):
            raise ContradictionValidationError("case requires audit history")
        if tuple(item.sequence for item in self.audit_history) != tuple(range(len(self.audit_history))):
            raise ContradictionValidationError("case audit sequence is not contiguous")
        if tuple(item.occurred_at for item in self.audit_history) != tuple(
            sorted(item.occurred_at for item in self.audit_history)
        ):
            raise ContradictionValidationError("case audit time is not monotonic")
        _sha(self.source_snapshot_hash, "case source_snapshot_hash")
        for audit in self.audit_history:
            if audit.resolution is None:
                continue
            evidence = audit.resolution
            if (
                evidence.subject_id != self.subject_id
                or evidence.environment != self.environment
                or evidence.target_case_id != self.case_id
                or evidence.source_snapshot_hash != self.source_snapshot_hash
                or evidence.detector_version != self.detector_version
                or evidence.proposition_id != self.proposition_id
                or evidence.scope_id != self.scope_id
                or evidence.target_claim_hashes != tuple(item.claim_hash for item in self.claims)
                or evidence.target_case_revision != audit.sequence - 2
            ):
                raise ContradictionValidationError("resolution audit crosses its target case boundary")
            # Reconstruct the exact pre-transition canonical body, not the latest case.
            prefix = self.audit_history[:audit.sequence]
            prior_status = {
                AuditAction.ISOLATED: ContradictionStatus.PENDING_VERIFICATION,
                AuditAction.RESOLVED: ContradictionStatus.RESOLVED,
                AuditAction.REOPENED: ContradictionStatus.REOPENED,
            }.get(prefix[-1].action) if prefix else None
            if prior_status is None:
                raise ContradictionValidationError("resolution audit has invalid predecessor")
            prior_body = self.canonical_dict()
            prior_body.update(
                audit_history=[item.to_dict() for item in prefix],
                status=prior_status.value, revision=evidence.target_case_revision,
                verification_task={**self.verification_task.to_dict(), "status": (
                    VerificationStatus.COMPLETED.value if prior_status is ContradictionStatus.RESOLVED
                    else VerificationStatus.OPEN.value)},
            )
            if evidence.target_case_hash != contradiction_hash(prior_body):
                raise ContradictionValidationError("resolution audit target history hash mismatch")
        if self.direct_state_write_allowed is not False or self.evolution_commit_allowed is not False:
            raise ContradictionValidationError("P07 cases cannot write state or commit Evolution")
        if self.status in {ContradictionStatus.RESOLVED, ContradictionStatus.SUPERSEDED}:
            if self.verification_task.status is not VerificationStatus.COMPLETED:
                raise ContradictionValidationError("terminal case requires completed verification")
            expected_action = (
                AuditAction.RESOLVED
                if self.status is ContradictionStatus.RESOLVED
                else AuditAction.SUPERSEDED
            )
            if self.audit_history[-1].action is not expected_action:
                raise ContradictionValidationError("terminal case audit tail is invalid")
        elif self.verification_task.status is VerificationStatus.COMPLETED:
            raise ContradictionValidationError("unresolved case cannot complete verification")
        expected = contradiction_hash(self.canonical_dict())
        if self.case_hash is None:
            object.__setattr__(self, "case_hash", expected)
        elif self.case_hash != expected:
            raise ContradictionValidationError("contradiction case integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "case_id": self.case_id,
            "kind": self.kind.value,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "proposition_id": self.proposition_id,
            "scope_id": self.scope_id,
            "claims": [item.to_dict() for item in self.claims],
            "dispositions": [item.to_dict() for item in self.dispositions],
            "impact_scope": list(self.impact_scope),
            "status": self.status.value,
            "verification_task": self.verification_task.to_dict(),
            "audit_history": [item.to_dict() for item in self.audit_history],
            "source_snapshot_hash": self.source_snapshot_hash,
            "detector_version": self.detector_version,
            "revision": self.revision,
            "direct_state_write_allowed": False,
            "evolution_commit_allowed": False,
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "case_hash": self.case_hash}

    @classmethod
    def from_dict(cls, value: Any) -> ContradictionCase:
        if not isinstance(value, dict):
            raise ContradictionValidationError("contradiction case must be an object")
        return cls(
            case_id=value.get("case_id"),
            kind=value.get("kind"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            proposition_id=value.get("proposition_id"),
            scope_id=value.get("scope_id"),
            claims=tuple(StructuredClaim.from_dict(item) for item in value.get("claims", [])),
            dispositions=tuple(
                ClaimDispositionRecord.from_dict(item) for item in value.get("dispositions", [])
            ),
            impact_scope=tuple(value.get("impact_scope", [])),
            status=value.get("status"),
            verification_task=VerificationTask.from_dict(value.get("verification_task")),
            audit_history=tuple(
                ContradictionAuditEntry.from_dict(item) for item in value.get("audit_history", [])
            ),
            source_snapshot_hash=value.get("source_snapshot_hash"),
            detector_version=value.get("detector_version"),
            revision=value.get("revision", 0),
            direct_state_write_allowed=value.get("direct_state_write_allowed", False),
            evolution_commit_allowed=value.get("evolution_commit_allowed", False),
            case_hash=value.get("case_hash"),
        )

    def canonical_hash(self) -> str:
        return self.case_hash or contradiction_hash(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ContradictionTrace:
    trace_id: str
    request_id: str
    subject_id: str
    environment: str
    source_revision: int
    source_snapshot_hash: str
    detector_version: str
    detected_at: datetime
    fragment_count: int
    evaluated_count: int
    unassessed_count: int
    psychological_excluded_count: int
    candidate_missing_count: int
    upstream_notice_count: int
    contradiction_count: int
    evaluations: tuple[ClaimEvaluation, ...]
    case_ids: tuple[str, ...]
    trace_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.trace_id, "contradiction trace_id"),
            (self.request_id, "contradiction request_id"),
            (self.subject_id, "contradiction trace subject_id"),
            (self.detector_version, "contradiction detector_version"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError("trace environment is unsupported")
        if isinstance(self.source_revision, bool) or not isinstance(self.source_revision, int) or self.source_revision < 0:
            raise ContradictionValidationError("trace source_revision must be non-negative")
        _sha(self.source_snapshot_hash, "trace source_snapshot_hash")
        object.__setattr__(self, "detected_at", _utc(self.detected_at, "trace detected_at"))
        counts = (
            self.fragment_count,
            self.evaluated_count,
            self.unassessed_count,
            self.psychological_excluded_count,
            self.candidate_missing_count,
            self.upstream_notice_count,
            self.contradiction_count,
        )
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
            raise ContradictionValidationError("trace counts must be non-negative integers")
        if self.evaluated_count + self.unassessed_count + self.psychological_excluded_count != self.fragment_count:
            raise ContradictionValidationError("trace evaluations do not cover source fragments")
        if len(self.evaluations) != self.fragment_count:
            raise ContradictionValidationError("trace requires one evaluation per fragment")
        if len({item.fragment_id for item in self.evaluations}) != len(self.evaluations):
            raise ContradictionValidationError("trace repeats fragment evaluation")
        if tuple(self.case_ids) != tuple(sorted(self.case_ids)) or len(set(self.case_ids)) != len(self.case_ids):
            raise ContradictionValidationError("trace case identities must be unique and sorted")
        if len(self.case_ids) != self.contradiction_count:
            raise ContradictionValidationError("trace contradiction count mismatch")
        expected = contradiction_hash(self.canonical_dict())
        if self.trace_hash is None:
            object.__setattr__(self, "trace_hash", expected)
        elif self.trace_hash != expected:
            raise ContradictionValidationError("contradiction trace integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "source_revision": self.source_revision,
            "source_snapshot_hash": self.source_snapshot_hash,
            "detector_version": self.detector_version,
            "detected_at": _format_time(self.detected_at),
            "fragment_count": self.fragment_count,
            "evaluated_count": self.evaluated_count,
            "unassessed_count": self.unassessed_count,
            "psychological_excluded_count": self.psychological_excluded_count,
            "candidate_missing_count": self.candidate_missing_count,
            "upstream_notice_count": self.upstream_notice_count,
            "contradiction_count": self.contradiction_count,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "case_ids": list(self.case_ids),
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "trace_hash": self.trace_hash}

    @classmethod
    def from_dict(cls, value: Any) -> ContradictionTrace:
        if not isinstance(value, dict):
            raise ContradictionValidationError("contradiction trace must be an object")
        return cls(
            value.get("trace_id"),
            value.get("request_id"),
            value.get("subject_id"),
            value.get("environment"),
            value.get("source_revision"),
            value.get("source_snapshot_hash"),
            value.get("detector_version"),
            _parse_time(value.get("detected_at"), "trace detected_at"),
            value.get("fragment_count"),
            value.get("evaluated_count"),
            value.get("unassessed_count"),
            value.get("psychological_excluded_count"),
            value.get("candidate_missing_count"),
            value.get("upstream_notice_count"),
            value.get("contradiction_count"),
            tuple(ClaimEvaluation.from_dict(item) for item in value.get("evaluations", [])),
            tuple(value.get("case_ids", [])),
            value.get("trace_hash"),
        )


@dataclass(frozen=True, slots=True)
class ContradictionDetectionResult:
    status: ContradictionDetectionStatus
    trace: ContradictionTrace | None
    cases: tuple[ContradictionCase, ...] = ()
    error_code: str | None = None
    direct_state_write_allowed: bool = False
    evolution_commit_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ContradictionDetectionStatus(self.status))
        if self.direct_state_write_allowed is not False or self.evolution_commit_allowed is not False:
            raise ContradictionValidationError("P07 result cannot write state or commit Evolution")
        if self.status is ContradictionDetectionStatus.COMPLETE:
            if not isinstance(self.trace, ContradictionTrace):
                raise ContradictionValidationError("complete detection requires trace")
            if self.error_code is not None:
                raise ContradictionValidationError("complete detection cannot have error_code")
            if tuple(item.case_id for item in self.cases) != self.trace.case_ids:
                raise ContradictionValidationError("detection cases do not match trace")
            for case in self.cases:
                if (
                    case.subject_id != self.trace.subject_id
                    or case.environment != self.trace.environment
                    or case.source_snapshot_hash != self.trace.source_snapshot_hash
                    or case.detector_version != self.trace.detector_version
                ):
                    raise ContradictionValidationError(
                        "detection case crosses sealed trace boundary"
                    )
        else:
            if self.trace is not None or self.cases:
                raise ContradictionValidationError("rejected detection cannot expose consumable output")
            _reason(self.error_code, "detection error_code")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": self.status.value,
            "trace": self.trace.to_dict() if self.trace else None,
            "cases": [item.to_dict() for item in self.cases],
            "error_code": self.error_code,
            "direct_state_write_allowed": False,
            "evolution_commit_allowed": False,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContradictionDetectionResult:
        if not isinstance(value, dict):
            raise ContradictionValidationError("contradiction result must be an object")
        trace = value.get("trace")
        return cls(
            value.get("status"),
            ContradictionTrace.from_dict(trace) if trace is not None else None,
            tuple(ContradictionCase.from_dict(item) for item in value.get("cases", [])),
            value.get("error_code"),
            value.get("direct_state_write_allowed", False),
            value.get("evolution_commit_allowed", False),
        )

    def canonical_hash(self) -> str:
        return contradiction_hash(self.to_dict())


def transition_case(
    case: ContradictionCase,
    *,
    status: ContradictionStatus,
    audit: ContradictionAuditEntry,
    verification_status: VerificationStatus,
) -> ContradictionCase:
    """Build one immutable next revision; repository validates legal transitions."""

    if audit.resolution is not None:
        validate_resolution_binding(case, audit.resolution, audit.action)

    return replace(
        case,
        status=status,
        verification_task=replace(case.verification_task, status=verification_status),
        audit_history=case.audit_history + (audit,),
        revision=case.revision + 1,
        case_hash=None,
    )


def validate_resolution_binding(
    case: ContradictionCase, evidence: VerifiedResolutionEvidence, action: AuditAction
) -> None:
    """Common semantic gate for service, domain transition and repository replay."""
    if (
        evidence.subject_id != case.subject_id or evidence.environment != case.environment
        or evidence.target_case_id != case.case_id
        or evidence.target_case_revision != case.revision
        or evidence.target_case_hash != case.canonical_hash()
        or evidence.source_snapshot_hash != case.source_snapshot_hash
        or evidence.detector_version != case.detector_version
        or evidence.proposition_id != case.proposition_id or evidence.scope_id != case.scope_id
        or evidence.target_claim_hashes != tuple(item.claim_hash for item in case.claims)
        or evidence.allowed_action is not action
        or evidence.resolved_at < case.audit_history[-1].occurred_at
    ):
        raise ContradictionValidationError("verified resolution target/action boundary mismatch")
