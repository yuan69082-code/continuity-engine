from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from .context_routing import ContextPartition
from .errors import ContextCompositionValidationError
from .events import JsonValue


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class ContextAuthority(str, Enum):
    CONFIRMED_STATE = "confirmed_state"
    CONFIRMED_MEMORY = "confirmed_memory"
    DERIVED_SUMMARY = "derived_summary"
    RETRIEVED_CANDIDATE = "retrieved_candidate"
    RAW_SOURCE = "raw_source"


class CompositionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    FEATURE_GATED = "FEATURE_GATED"
    INSUFFICIENT_CONTEXT_BUDGET = "INSUFFICIENT_CONTEXT_BUDGET"


class CompositionDecisionStatus(str, Enum):
    RETAINED = "RETAINED"
    DEDUPLICATED = "DEDUPLICATED"
    EXCLUDED = "EXCLUDED"
    MISSING = "MISSING"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextCompositionValidationError(f"{name} must be a non-empty string")
    return value


def _identifier(value: Any, name: str) -> str:
    result = _text(value, name)
    if _IDENTIFIER.fullmatch(result) is None:
        raise ContextCompositionValidationError(f"{name} contains unsupported characters")
    return result


def _reason(value: Any, name: str) -> str:
    result = _text(value, name)
    if _REASON.fullmatch(result) is None:
        raise ContextCompositionValidationError(f"{name} is not a stable reason code")
    return result


def _sha(value: Any, name: str) -> str:
    result = _text(value, name)
    if _SHA256.fullmatch(result) is None:
        raise ContextCompositionValidationError(f"{name} must be SHA-256")
    return result


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def composition_hash(value: Any) -> str:
    """Return the stable P06 canonical JSON hash used by snapshots and traces."""

    return _hash(value)


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContextCompositionValidationError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _utc(value, "datetime").isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ContextCompositionValidationError(f"{name} must be ISO-8601")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), name)
    except ValueError as exc:
        raise ContextCompositionValidationError(f"{name} is not valid ISO-8601") from exc


def _ratio(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContextCompositionValidationError(f"{name} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ContextCompositionValidationError(f"{name} must be between zero and one")
    return result


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContextCompositionValidationError(f"{name} must be at least {minimum}")
    return value


def _unique(values: Iterable[str], name: str, *, required: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContextCompositionValidationError(f"{name} must be a sequence")
    result = tuple(values)
    if required and not result:
        raise ContextCompositionValidationError(f"{name} cannot be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ContextCompositionValidationError(f"{name} contains an empty value")
    if len(result) != len(set(result)):
        raise ContextCompositionValidationError(f"{name} contains duplicates")
    return result


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """P06-only budget, separate from P05 retrieval and model token budgets."""

    core_fragment_limit: int = 10
    token_limit: int = 2048

    def __post_init__(self) -> None:
        if not 6 <= _integer(
            self.core_fragment_limit, "core_fragment_limit", minimum=1
        ) <= 15:
            raise ContextCompositionValidationError(
                "core_fragment_limit must be between 6 and 15"
            )
        _integer(self.token_limit, "context token_limit", minimum=1)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "core_fragment_limit": self.core_fragment_limit,
            "token_limit": self.token_limit,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextBudget:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("context budget must be an object")
        return cls(value.get("core_fragment_limit"), value.get("token_limit"))


@dataclass(frozen=True, slots=True)
class ResolvedContextMaterial:
    """Exact material resolved from one P05 reference under a trusted binding."""

    reference_id: str
    source_id: str
    partition: ContextPartition
    stable_source_id: str
    subject_id: str
    environment: str
    version: str
    content_hash: str
    source_type: str
    authority: ContextAuthority
    occurred_at: datetime
    relevance: float
    confidence: float
    provenance_roots: tuple[str, ...]
    content: str
    required: bool = False
    protected: bool = False
    protection_role: str | None = None
    conflict_markers: tuple[str, ...] = ()
    missing_markers: tuple[str, ...] = ()
    direct_state_write_allowed: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.reference_id, "material reference_id"),
            (self.source_id, "material source_id"),
            (self.stable_source_id, "material stable_source_id"),
            (self.subject_id, "material subject_id"),
            (self.version, "material version"),
            (self.source_type, "material source_type"),
        ):
            _identifier(value, name)
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextCompositionValidationError("material environment is unsupported")
        _sha(self.content_hash, "material content_hash")
        object.__setattr__(self, "authority", ContextAuthority(self.authority))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "material occurred_at"))
        object.__setattr__(self, "relevance", _ratio(self.relevance, "material relevance"))
        object.__setattr__(self, "confidence", _ratio(self.confidence, "material confidence"))
        object.__setattr__(
            self,
            "provenance_roots",
            _unique(self.provenance_roots, "material provenance_roots", required=True),
        )
        _text(self.content, "material content")
        if not isinstance(self.required, bool) or not isinstance(self.protected, bool):
            raise ContextCompositionValidationError("material gates must be boolean")
        if self.protected and self.authority is not ContextAuthority.CONFIRMED_STATE:
            raise ContextCompositionValidationError(
                "only confirmed_state material may be budget-protected"
            )
        if self.protected:
            _identifier(self.protection_role, "material protection_role")
        elif self.protection_role is not None:
            raise ContextCompositionValidationError(
                "an unprotected material cannot declare a protection_role"
            )
        object.__setattr__(
            self,
            "conflict_markers",
            _unique(self.conflict_markers, "material conflict_markers"),
        )
        object.__setattr__(
            self,
            "missing_markers",
            _unique(self.missing_markers, "material missing_markers"),
        )
        if self.direct_state_write_allowed is not False:
            raise ContextCompositionValidationError(
                "context material can never write SubjectState directly"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "reference_id": self.reference_id,
            "source_id": self.source_id,
            "partition": self.partition.value,
            "stable_source_id": self.stable_source_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "version": self.version,
            "content_hash": self.content_hash,
            "source_type": self.source_type,
            "authority": self.authority.value,
            "occurred_at": _format_time(self.occurred_at),
            "relevance": self.relevance,
            "confidence": self.confidence,
            "provenance_roots": list(self.provenance_roots),
            "content": self.content,
            "required": self.required,
            "protected": self.protected,
            "protection_role": self.protection_role,
            "conflict_markers": list(self.conflict_markers),
            "missing_markers": list(self.missing_markers),
            "direct_state_write_allowed": False,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResolvedContextMaterial:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("resolved material must be an object")
        return cls(
            reference_id=value.get("reference_id"),
            source_id=value.get("source_id"),
            partition=value.get("partition"),
            stable_source_id=value.get("stable_source_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            version=value.get("version"),
            content_hash=value.get("content_hash"),
            source_type=value.get("source_type"),
            authority=value.get("authority"),
            occurred_at=_parse_time(value.get("occurred_at"), "material occurred_at"),
            relevance=value.get("relevance"),
            confidence=value.get("confidence"),
            provenance_roots=tuple(value.get("provenance_roots", [])),
            content=value.get("content"),
            required=value.get("required", False),
            protected=value.get("protected", False),
            protection_role=value.get("protection_role"),
            conflict_markers=tuple(value.get("conflict_markers", [])),
            missing_markers=tuple(value.get("missing_markers", [])),
            direct_state_write_allowed=value.get("direct_state_write_allowed", False),
        )


@dataclass(frozen=True, slots=True)
class ComposedContextFragment:
    fragment_id: str
    reference_id: str
    subject_id: str
    environment: str
    authority: ContextAuthority
    source_id: str
    source_type: str
    stable_source_id: str
    version: str
    content_hash: str
    occurred_at: datetime
    relevance: float
    confidence: float
    provenance_roots: tuple[str, ...]
    conflict_markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    estimated_tokens: int
    rank: int
    retained_reason: str
    content: str
    protected: bool = False
    protection_role: str | None = None
    direct_state_write_allowed: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.fragment_id, "fragment_id"),
            (self.reference_id, "fragment reference_id"),
            (self.subject_id, "fragment subject_id"),
            (self.source_id, "fragment source_id"),
            (self.source_type, "fragment source_type"),
            (self.stable_source_id, "fragment stable_source_id"),
            (self.version, "fragment version"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextCompositionValidationError("fragment environment is unsupported")
        object.__setattr__(self, "authority", ContextAuthority(self.authority))
        _sha(self.content_hash, "fragment content_hash")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "fragment occurred_at"))
        object.__setattr__(self, "relevance", _ratio(self.relevance, "fragment relevance"))
        object.__setattr__(self, "confidence", _ratio(self.confidence, "fragment confidence"))
        object.__setattr__(
            self,
            "provenance_roots",
            _unique(self.provenance_roots, "fragment provenance_roots", required=True),
        )
        object.__setattr__(
            self,
            "conflict_markers",
            _unique(self.conflict_markers, "fragment conflict_markers"),
        )
        object.__setattr__(
            self,
            "missing_markers",
            _unique(self.missing_markers, "fragment missing_markers"),
        )
        _integer(self.estimated_tokens, "fragment estimated_tokens", minimum=1)
        _integer(self.rank, "fragment rank", minimum=1)
        _reason(self.retained_reason, "fragment retained_reason")
        _text(self.content, "fragment content")
        if not isinstance(self.protected, bool):
            raise ContextCompositionValidationError("fragment protected must be boolean")
        if self.protected:
            _identifier(self.protection_role, "fragment protection_role")
        elif self.protection_role is not None:
            raise ContextCompositionValidationError(
                "an unprotected fragment cannot declare a protection_role"
            )
        if self.direct_state_write_allowed is not False:
            raise ContextCompositionValidationError(
                "a composed fragment can never write SubjectState directly"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "fragment_id": self.fragment_id,
            "reference_id": self.reference_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "authority": self.authority.value,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "stable_source_id": self.stable_source_id,
            "version": self.version,
            "content_hash": self.content_hash,
            "occurred_at": _format_time(self.occurred_at),
            "relevance": self.relevance,
            "confidence": self.confidence,
            "provenance_roots": list(self.provenance_roots),
            "conflict_markers": list(self.conflict_markers),
            "missing_markers": list(self.missing_markers),
            "estimated_tokens": self.estimated_tokens,
            "rank": self.rank,
            "retained_reason": self.retained_reason,
            "content": self.content,
            "protected": self.protected,
            "protection_role": self.protection_role,
            "direct_state_write_allowed": False,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ComposedContextFragment:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("context fragment must be an object")
        return cls(
            fragment_id=value.get("fragment_id"),
            reference_id=value.get("reference_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            authority=value.get("authority"),
            source_id=value.get("source_id"),
            source_type=value.get("source_type"),
            stable_source_id=value.get("stable_source_id"),
            version=value.get("version"),
            content_hash=value.get("content_hash"),
            occurred_at=_parse_time(value.get("occurred_at"), "fragment occurred_at"),
            relevance=value.get("relevance"),
            confidence=value.get("confidence"),
            provenance_roots=tuple(value.get("provenance_roots", [])),
            conflict_markers=tuple(value.get("conflict_markers", [])),
            missing_markers=tuple(value.get("missing_markers", [])),
            estimated_tokens=value.get("estimated_tokens"),
            rank=value.get("rank"),
            retained_reason=value.get("retained_reason"),
            content=value.get("content"),
            protected=value.get("protected", False),
            protection_role=value.get("protection_role"),
            direct_state_write_allowed=value.get("direct_state_write_allowed", False),
        )

    def canonical_hash(self) -> str:
        return _hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class MissingContextNotice:
    reference_id: str
    source_id: str
    stable_source_id: str
    required: bool
    reason_code: str

    def __post_init__(self) -> None:
        _identifier(self.reference_id, "missing reference_id")
        _identifier(self.source_id, "missing source_id")
        _identifier(self.stable_source_id, "missing stable_source_id")
        if not isinstance(self.required, bool):
            raise ContextCompositionValidationError("missing required must be boolean")
        _reason(self.reason_code, "missing reason_code")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "reference_id": self.reference_id,
            "source_id": self.source_id,
            "stable_source_id": self.stable_source_id,
            "required": self.required,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, value: Any) -> MissingContextNotice:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("missing notice must be an object")
        return cls(
            value.get("reference_id"),
            value.get("source_id"),
            value.get("stable_source_id"),
            value.get("required"),
            value.get("reason_code"),
        )


@dataclass(frozen=True, slots=True)
class CompositionDecision:
    reference_id: str
    source_id: str
    stable_source_id: str
    status: CompositionDecisionStatus
    reason_code: str
    authority: ContextAuthority | None = None
    estimated_tokens: int = 0

    def __post_init__(self) -> None:
        _identifier(self.reference_id, "decision reference_id")
        _identifier(self.source_id, "decision source_id")
        _identifier(self.stable_source_id, "decision stable_source_id")
        object.__setattr__(self, "status", CompositionDecisionStatus(self.status))
        _reason(self.reason_code, "decision reason_code")
        if self.authority is not None:
            object.__setattr__(self, "authority", ContextAuthority(self.authority))
        _integer(self.estimated_tokens, "decision estimated_tokens")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "reference_id": self.reference_id,
            "source_id": self.source_id,
            "stable_source_id": self.stable_source_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "authority": self.authority.value if self.authority is not None else None,
            "estimated_tokens": self.estimated_tokens,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CompositionDecision:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("composition decision must be an object")
        return cls(
            value.get("reference_id"),
            value.get("source_id"),
            value.get("stable_source_id"),
            value.get("status"),
            value.get("reason_code"),
            value.get("authority"),
            value.get("estimated_tokens", 0),
        )


@dataclass(frozen=True, slots=True)
class ResolverReadCount:
    """Composer-owned exact resolver read count for one stable source binding."""

    source_id: str
    read_count: int

    def __post_init__(self) -> None:
        _identifier(self.source_id, "resolver read source_id")
        _integer(self.read_count, "resolver read_count")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "read_count": self.read_count,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResolverReadCount:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError(
                "resolver read count must be an object"
            )
        return cls(value.get("source_id"), value.get("read_count"))


@dataclass(frozen=True, slots=True)
class CompositionTrace:
    trace_id: str
    request_id: str
    subject_id: str
    environment: str
    source_revision: int
    composed_at: datetime
    status: CompositionStatus
    route_result_hash: str
    route_plan_hash: str
    manifest_hash: str
    p05_trace_hash: str
    feature_gate_version: str
    budget: ContextBudget
    candidate_count: int
    resolved_count: int
    retained_count: int
    deduplicated_count: int
    excluded_count: int
    missing_count: int
    upstream_notice_count: int
    resolver_read_count: int
    resolver_read_counts: tuple[ResolverReadCount, ...]
    tokens_used: int
    decisions: tuple[CompositionDecision, ...]
    upstream_notices: tuple[MissingContextNotice, ...]
    trace_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.trace_id, "composition trace_id"),
            (self.request_id, "composition request_id"),
            (self.subject_id, "composition subject_id"),
            (self.feature_gate_version, "composition feature_gate_version"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextCompositionValidationError("trace environment is unsupported")
        _integer(self.source_revision, "trace source_revision")
        object.__setattr__(self, "composed_at", _utc(self.composed_at, "trace composed_at"))
        object.__setattr__(self, "status", CompositionStatus(self.status))
        for value, name in (
            (self.route_result_hash, "trace route_result_hash"),
            (self.route_plan_hash, "trace route_plan_hash"),
            (self.manifest_hash, "trace manifest_hash"),
            (self.p05_trace_hash, "trace p05_trace_hash"),
        ):
            _sha(value, name)
        if not isinstance(self.budget, ContextBudget):
            raise ContextCompositionValidationError("trace budget is invalid")
        for value, name in (
            (self.candidate_count, "candidate_count"),
            (self.resolved_count, "resolved_count"),
            (self.retained_count, "retained_count"),
            (self.deduplicated_count, "deduplicated_count"),
            (self.excluded_count, "excluded_count"),
            (self.missing_count, "missing_count"),
            (self.upstream_notice_count, "upstream_notice_count"),
            (self.resolver_read_count, "resolver_read_count"),
            (self.tokens_used, "tokens_used"),
        ):
            _integer(value, name)
        if self.resolved_count + self.missing_count != self.candidate_count:
            raise ContextCompositionValidationError(
                "trace resolved and candidate-missing counts must cover candidates"
            )
        if (
            self.retained_count + self.deduplicated_count + self.excluded_count
            != self.resolved_count
        ):
            raise ContextCompositionValidationError(
                "trace resolved outcomes do not cover resolved material"
            )
        if self.tokens_used > self.budget.token_limit and self.status is CompositionStatus.COMPLETE:
            raise ContextCompositionValidationError("complete context exceeds token budget")
        if self.retained_count > self.budget.core_fragment_limit:
            raise ContextCompositionValidationError("context exceeds fragment budget")
        if any(not isinstance(item, CompositionDecision) for item in self.decisions):
            raise ContextCompositionValidationError("trace decisions are invalid")
        if any(
            not isinstance(item, MissingContextNotice)
            for item in self.upstream_notices
        ):
            raise ContextCompositionValidationError("trace upstream notices are invalid")
        if len(self.upstream_notices) != self.upstream_notice_count:
            raise ContextCompositionValidationError(
                "trace upstream notice count mismatch"
            )
        if any(
            not isinstance(item, ResolverReadCount)
            for item in self.resolver_read_counts
        ):
            raise ContextCompositionValidationError(
                "trace resolver read counts are invalid"
            )
        resolver_source_ids = tuple(
            item.source_id for item in self.resolver_read_counts
        )
        if resolver_source_ids != tuple(sorted(resolver_source_ids)):
            raise ContextCompositionValidationError(
                "trace resolver read counts must use stable source order"
            )
        if len(resolver_source_ids) != len(set(resolver_source_ids)):
            raise ContextCompositionValidationError(
                "trace resolver read counts contain duplicate sources"
            )
        if sum(item.read_count for item in self.resolver_read_counts) != self.resolver_read_count:
            raise ContextCompositionValidationError(
                "trace resolver read total does not match per-source counts"
            )
        if len(self.decisions) != self.candidate_count:
            raise ContextCompositionValidationError("trace requires one decision per candidate")
        expected = _hash(self.canonical_dict())
        if self.trace_hash is None:
            object.__setattr__(self, "trace_hash", expected)
        elif self.trace_hash != expected:
            raise ContextCompositionValidationError("composition trace integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "source_revision": self.source_revision,
            "composed_at": _format_time(self.composed_at),
            "status": self.status.value,
            "route_result_hash": self.route_result_hash,
            "route_plan_hash": self.route_plan_hash,
            "manifest_hash": self.manifest_hash,
            "p05_trace_hash": self.p05_trace_hash,
            "feature_gate_version": self.feature_gate_version,
            "budget": self.budget.to_dict(),
            "candidate_count": self.candidate_count,
            "resolved_count": self.resolved_count,
            "retained_count": self.retained_count,
            "deduplicated_count": self.deduplicated_count,
            "excluded_count": self.excluded_count,
            "missing_count": self.missing_count,
            "upstream_notice_count": self.upstream_notice_count,
            "resolver_read_count": self.resolver_read_count,
            "resolver_read_counts": [
                item.to_dict() for item in self.resolver_read_counts
            ],
            "tokens_used": self.tokens_used,
            "decisions": [item.to_dict() for item in self.decisions],
            "upstream_notices": [item.to_dict() for item in self.upstream_notices],
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "trace_hash": self.trace_hash}

    @classmethod
    def from_dict(cls, value: Any) -> CompositionTrace:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("decisions"), list)
            or not isinstance(value.get("upstream_notices", []), list)
            or not isinstance(value.get("resolver_read_counts"), list)
        ):
            raise ContextCompositionValidationError("composition trace must be an object")
        return cls(
            trace_id=value.get("trace_id"),
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            source_revision=value.get("source_revision"),
            composed_at=_parse_time(value.get("composed_at"), "trace composed_at"),
            status=value.get("status"),
            route_result_hash=value.get("route_result_hash"),
            route_plan_hash=value.get("route_plan_hash"),
            manifest_hash=value.get("manifest_hash"),
            p05_trace_hash=value.get("p05_trace_hash"),
            feature_gate_version=value.get("feature_gate_version"),
            budget=ContextBudget.from_dict(value.get("budget")),
            candidate_count=value.get("candidate_count"),
            resolved_count=value.get("resolved_count"),
            retained_count=value.get("retained_count"),
            deduplicated_count=value.get("deduplicated_count"),
            excluded_count=value.get("excluded_count"),
            missing_count=value.get("missing_count"),
            upstream_notice_count=value.get("upstream_notice_count", 0),
            resolver_read_count=value.get("resolver_read_count"),
            resolver_read_counts=tuple(
                ResolverReadCount.from_dict(item)
                for item in value["resolver_read_counts"]
            ),
            tokens_used=value.get("tokens_used"),
            decisions=tuple(CompositionDecision.from_dict(item) for item in value["decisions"]),
            upstream_notices=tuple(
                MissingContextNotice.from_dict(item)
                for item in value.get("upstream_notices", [])
            ),
            trace_hash=value.get("trace_hash"),
        )


@dataclass(frozen=True, slots=True)
class ComposedContextSnapshot:
    snapshot_id: str
    request_id: str
    subject_id: str
    environment: str
    source_revision: int
    composed_at: datetime
    route_result_hash: str
    route_plan_hash: str
    manifest_hash: str
    budget: ContextBudget
    fragments: tuple[ComposedContextFragment, ...]
    missing_notices: tuple[MissingContextNotice, ...] = ()
    consumable: bool = True
    snapshot_hash: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.snapshot_id, "snapshot_id"),
            (self.request_id, "snapshot request_id"),
            (self.subject_id, "snapshot subject_id"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextCompositionValidationError("snapshot environment is unsupported")
        _integer(self.source_revision, "snapshot source_revision")
        object.__setattr__(self, "composed_at", _utc(self.composed_at, "snapshot composed_at"))
        for value, name in (
            (self.route_result_hash, "snapshot route_result_hash"),
            (self.route_plan_hash, "snapshot route_plan_hash"),
            (self.manifest_hash, "snapshot manifest_hash"),
        ):
            _sha(value, name)
        if not isinstance(self.budget, ContextBudget):
            raise ContextCompositionValidationError("snapshot budget is invalid")
        if any(not isinstance(item, ComposedContextFragment) for item in self.fragments):
            raise ContextCompositionValidationError("snapshot fragments are invalid")
        if tuple(item.rank for item in self.fragments) != tuple(
            range(1, len(self.fragments) + 1)
        ):
            raise ContextCompositionValidationError("snapshot fragment ranks are not contiguous")
        if len({item.fragment_id for item in self.fragments}) != len(self.fragments):
            raise ContextCompositionValidationError("snapshot repeats a fragment identity")
        if any(
            item.subject_id != self.subject_id or item.environment != self.environment
            for item in self.fragments
        ):
            raise ContextCompositionValidationError("snapshot fragment boundary mismatch")
        if any(not isinstance(item, MissingContextNotice) for item in self.missing_notices):
            raise ContextCompositionValidationError("snapshot missing notices are invalid")
        if self.consumable is not True:
            raise ContextCompositionValidationError("a persisted snapshot must be consumable")
        if len(self.fragments) > self.budget.core_fragment_limit:
            raise ContextCompositionValidationError("snapshot exceeds fragment budget")
        if sum(item.estimated_tokens for item in self.fragments) > self.budget.token_limit:
            raise ContextCompositionValidationError("snapshot exceeds token budget")
        expected = _hash(self.canonical_dict())
        if self.snapshot_hash is None:
            object.__setattr__(self, "snapshot_hash", expected)
        elif self.snapshot_hash != expected:
            raise ContextCompositionValidationError("snapshot integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "snapshot_id": self.snapshot_id,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "source_revision": self.source_revision,
            "composed_at": _format_time(self.composed_at),
            "route_result_hash": self.route_result_hash,
            "route_plan_hash": self.route_plan_hash,
            "manifest_hash": self.manifest_hash,
            "budget": self.budget.to_dict(),
            "fragments": [item.to_dict() for item in self.fragments],
            "missing_notices": [item.to_dict() for item in self.missing_notices],
            "consumable": True,
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "snapshot_hash": self.snapshot_hash}

    @classmethod
    def from_dict(cls, value: Any) -> ComposedContextSnapshot:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("fragments"), list)
            or not isinstance(value.get("missing_notices", []), list)
        ):
            raise ContextCompositionValidationError("context snapshot must be an object")
        return cls(
            snapshot_id=value.get("snapshot_id"),
            request_id=value.get("request_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            source_revision=value.get("source_revision"),
            composed_at=_parse_time(value.get("composed_at"), "snapshot composed_at"),
            route_result_hash=value.get("route_result_hash"),
            route_plan_hash=value.get("route_plan_hash"),
            manifest_hash=value.get("manifest_hash"),
            budget=ContextBudget.from_dict(value.get("budget")),
            fragments=tuple(ComposedContextFragment.from_dict(item) for item in value["fragments"]),
            missing_notices=tuple(
                MissingContextNotice.from_dict(item)
                for item in value.get("missing_notices", [])
            ),
            consumable=value.get("consumable"),
            snapshot_hash=value.get("snapshot_hash"),
        )


@dataclass(frozen=True, slots=True)
class ContextCompositionResult:
    status: CompositionStatus
    trace: CompositionTrace
    snapshot: ComposedContextSnapshot | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", CompositionStatus(self.status))
        if not isinstance(self.trace, CompositionTrace) or self.trace.status is not self.status:
            raise ContextCompositionValidationError("result trace status mismatch")
        if self.status is CompositionStatus.COMPLETE:
            if not isinstance(self.snapshot, ComposedContextSnapshot):
                raise ContextCompositionValidationError("complete result requires snapshot")
            if self.error_code is not None:
                raise ContextCompositionValidationError("complete result cannot have error_code")
            if self.snapshot.request_id != self.trace.request_id:
                raise ContextCompositionValidationError("snapshot and trace request mismatch")
            if self.snapshot.route_result_hash != self.trace.route_result_hash:
                raise ContextCompositionValidationError("snapshot and trace route mismatch")
        else:
            if self.snapshot is not None:
                raise ContextCompositionValidationError(
                    "a failed composition cannot expose a consumable snapshot"
                )
            _reason(self.error_code, "composition error_code")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": self.status.value,
            "trace": self.trace.to_dict(),
            "snapshot": self.snapshot.to_dict() if self.snapshot is not None else None,
            "error_code": self.error_code,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextCompositionResult:
        if not isinstance(value, dict):
            raise ContextCompositionValidationError("composition result must be an object")
        snapshot = value.get("snapshot")
        return cls(
            status=value.get("status"),
            trace=CompositionTrace.from_dict(value.get("trace")),
            snapshot=(
                ComposedContextSnapshot.from_dict(snapshot)
                if snapshot is not None
                else None
            ),
            error_code=value.get("error_code"),
        )

    def canonical_hash(self) -> str:
        return _hash(self.to_dict())
