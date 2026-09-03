from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from .errors import ContextRoutingValidationError
from .events import JsonValue


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class ContextPartition(str, Enum):
    SUBJECT_STATE = "subject_state"
    MEMORY = "memory"
    DERIVED_SUMMARY = "derived_summary"
    TIMELINE = "timeline"
    LOCAL_FACT = "local_fact"
    ATTENTION = "attention"
    DESIRE = "desire"
    CONFLICT = "conflict"
    SOMATIC = "somatic"
    EXPRESSION = "expression"


class ContextRouteStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    FEATURE_GATED = "FEATURE_GATED"


class PartitionDecisionStatus(str, Enum):
    OPENED = "OPENED"
    NOT_OPENED = "NOT_OPENED"
    UNAVAILABLE = "UNAVAILABLE"
    FEATURE_GATED = "FEATURE_GATED"
    REJECTED = "REJECTED"


class CandidateDecisionStatus(str, Enum):
    RETAINED = "RETAINED"
    REJECTED = "REJECTED"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextRoutingValidationError(f"{name} must be a non-empty string")
    return value


def _identifier(value: Any, name: str) -> str:
    normalized = _text(value, name)
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise ContextRoutingValidationError(f"{name} contains unsupported characters")
    return normalized


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContextRoutingValidationError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _utc(value, "datetime").isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ContextRoutingValidationError(f"{name} must be an ISO-8601 string")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), name)
    except ValueError as exc:
        raise ContextRoutingValidationError(f"{name} is not valid ISO-8601") from exc


def _ratio(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContextRoutingValidationError(f"{name} must be a number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ContextRoutingValidationError(f"{name} must be between zero and one")
    return normalized


def _unique_texts(values: Iterable[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContextRoutingValidationError(f"{name} must be a sequence")
    result = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ContextRoutingValidationError(f"{name} contains an empty value")
    if len(result) != len(set(result)):
        raise ContextRoutingValidationError(f"{name} contains duplicates")
    return result


def _hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def hash_signal(value: str) -> str:
    """Hash a routing signal so Context Trace never needs its sensitive text."""

    return _hash(_text(value, "routing signal"))


@dataclass(frozen=True, slots=True)
class RetrievalBudget:
    """P05 candidate-count budget, separate from storage and P06 context budgets."""

    total_candidate_limit: int = 50
    per_source_limits: tuple[tuple[str, int], ...] = ()
    context_budget_hint: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.total_candidate_limit, int)
            or isinstance(self.total_candidate_limit, bool)
            or not 30 <= self.total_candidate_limit <= 80
        ):
            raise ContextRoutingValidationError(
                "total_candidate_limit must be between 30 and 80"
            )
        normalized: list[tuple[str, int]] = []
        seen: set[str] = set()
        for source_id, limit in self.per_source_limits:
            source = _identifier(source_id, "per-source source_id")
            if source in seen:
                raise ContextRoutingValidationError("per-source limits contain duplicates")
            if (
                not isinstance(limit, int)
                or isinstance(limit, bool)
                or limit < 1
                or limit > self.total_candidate_limit
            ):
                raise ContextRoutingValidationError("per-source limit is invalid")
            seen.add(source)
            normalized.append((source, limit))
        object.__setattr__(self, "per_source_limits", tuple(sorted(normalized)))
        if self.context_budget_hint is not None and (
            not isinstance(self.context_budget_hint, int)
            or isinstance(self.context_budget_hint, bool)
            or self.context_budget_hint < 1
        ):
            raise ContextRoutingValidationError("context_budget_hint must be positive")

    def limit_for(self, source_id: str) -> int:
        return dict(self.per_source_limits).get(source_id, self.total_candidate_limit)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "total_candidate_limit": self.total_candidate_limit,
            "per_source_limits": {
                source_id: limit for source_id, limit in self.per_source_limits
            },
            "context_budget_hint": self.context_budget_hint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RetrievalBudget:
        if not isinstance(value, dict) or not isinstance(
            value.get("per_source_limits", {}), dict
        ):
            raise ContextRoutingValidationError("retrieval budget must be an object")
        return cls(
            total_candidate_limit=value.get("total_candidate_limit", 50),
            per_source_limits=tuple(value.get("per_source_limits", {}).items()),
            context_budget_hint=value.get("context_budget_hint"),
        )


@dataclass(frozen=True, slots=True)
class RoutingSignal:
    signal_id: str
    signal_kind: str
    value_hash: str
    weight: float

    def __post_init__(self) -> None:
        _identifier(self.signal_id, "signal_id")
        _identifier(self.signal_kind, "signal_kind")
        if _SHA256.fullmatch(self.value_hash) is None:
            raise ContextRoutingValidationError("signal value_hash must be SHA-256")
        object.__setattr__(self, "weight", _ratio(self.weight, "signal weight"))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "signal_id": self.signal_id,
            "signal_kind": self.signal_kind,
            "value_hash": self.value_hash,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RoutingSignal:
        if not isinstance(value, dict):
            raise ContextRoutingValidationError("routing signal must be an object")
        return cls(
            value.get("signal_id"),
            value.get("signal_kind"),
            value.get("value_hash"),
            value.get("weight"),
        )


@dataclass(frozen=True, slots=True)
class ContextRoutingRequest:
    request_id: str
    perception_id: str
    subject_id: str
    environment: str
    source_revision: int
    routed_at: datetime
    purpose: tuple[str, ...]
    budget: RetrievalBudget = field(default_factory=RetrievalBudget)

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "routing request_id"),
            (self.perception_id, "routing perception_id"),
            (self.subject_id, "routing subject_id"),
        ):
            _identifier(value, name)
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextRoutingValidationError("routing environment is unsupported")
        if (
            not isinstance(self.source_revision, int)
            or isinstance(self.source_revision, bool)
            or self.source_revision < 0
        ):
            raise ContextRoutingValidationError("source_revision must be non-negative")
        object.__setattr__(self, "routed_at", _utc(self.routed_at, "routed_at"))
        object.__setattr__(self, "purpose", _unique_texts(self.purpose, "purpose"))
        if not self.purpose:
            raise ContextRoutingValidationError("routing purpose cannot be empty")
        if not isinstance(self.budget, RetrievalBudget):
            raise ContextRoutingValidationError("budget must be RetrievalBudget")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "perception_id": self.perception_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "source_revision": self.source_revision,
            "routed_at": _format_time(self.routed_at),
            "purpose": list(self.purpose),
            "budget": self.budget.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextRoutingRequest:
        if not isinstance(value, dict) or not isinstance(value.get("purpose"), list):
            raise ContextRoutingValidationError("routing request must be an object")
        return cls(
            request_id=value.get("request_id"),
            perception_id=value.get("perception_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            source_revision=value.get("source_revision"),
            routed_at=_parse_time(value.get("routed_at"), "routed_at"),
            purpose=tuple(value["purpose"]),
            budget=RetrievalBudget.from_dict(value.get("budget")),
        )


@dataclass(frozen=True, slots=True)
class ContextPartitionRequest:
    partition: ContextPartition
    required: bool
    source_ids: tuple[str, ...]
    candidate_limit: int
    reason_code: str
    selected: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        if not isinstance(self.required, bool):
            raise ContextRoutingValidationError("partition required must be boolean")
        if not isinstance(self.selected, bool):
            raise ContextRoutingValidationError("partition selected must be boolean")
        object.__setattr__(
            self, "source_ids", _unique_texts(self.source_ids, "partition source_ids")
        )
        if not isinstance(self.candidate_limit, int) or self.candidate_limit < 0:
            raise ContextRoutingValidationError(
                "partition candidate_limit must be non-negative"
            )
        if not self.selected and self.candidate_limit != 0:
            raise ContextRoutingValidationError(
                "an unopened partition cannot reserve retrieval budget"
            )
        _identifier(self.reason_code, "partition reason_code")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "partition": self.partition.value,
            "required": self.required,
            "source_ids": list(self.source_ids),
            "candidate_limit": self.candidate_limit,
            "reason_code": self.reason_code,
            "selected": self.selected,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextPartitionRequest:
        if not isinstance(value, dict) or not isinstance(value.get("source_ids"), list):
            raise ContextRoutingValidationError("partition request must be an object")
        return cls(
            value.get("partition"),
            value.get("required"),
            tuple(value["source_ids"]),
            value.get("candidate_limit"),
            value.get("reason_code"),
            value.get("selected", True),
        )


@dataclass(frozen=True, slots=True)
class RoutePlan:
    request: ContextRoutingRequest
    signals: tuple[RoutingSignal, ...]
    partitions: tuple[ContextPartitionRequest, ...]
    feature_gate_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, ContextRoutingRequest):
            raise ContextRoutingValidationError("route plan request is invalid")
        if any(not isinstance(item, RoutingSignal) for item in self.signals):
            raise ContextRoutingValidationError("route plan signals are invalid")
        if any(not isinstance(item, ContextPartitionRequest) for item in self.partitions):
            raise ContextRoutingValidationError("route plan partitions are invalid")
        identities = [item.partition for item in self.partitions]
        if len(identities) != len(set(identities)):
            raise ContextRoutingValidationError("route plan repeats a partition")
        _identifier(self.feature_gate_version, "feature_gate_version")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request": self.request.to_dict(),
            "signals": [item.to_dict() for item in self.signals],
            "partitions": [item.to_dict() for item in self.partitions],
            "feature_gate_version": self.feature_gate_version,
        }

    def canonical_hash(self) -> str:
        return _hash(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> RoutePlan:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("signals"), list)
            or not isinstance(value.get("partitions"), list)
        ):
            raise ContextRoutingValidationError("route plan must be an object")
        return cls(
            ContextRoutingRequest.from_dict(value.get("request")),
            tuple(RoutingSignal.from_dict(item) for item in value["signals"]),
            tuple(
                ContextPartitionRequest.from_dict(item)
                for item in value["partitions"]
            ),
            value.get("feature_gate_version"),
        )


@dataclass(frozen=True, slots=True)
class ContextSourceCandidate:
    source_id: str
    partition: ContextPartition
    stable_id: str
    subject_id: str
    environment: str
    version: str
    content_hash: str
    occurred_at: datetime
    permission_scope: str
    authority_label: str
    relevance: float
    importance: float = 0.0
    activation: float = 0.0
    tags: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    status: str = "ACTIVE"
    eligible: bool = True
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.source_id, "candidate source_id"),
            (self.stable_id, "candidate stable_id"),
            (self.subject_id, "candidate subject_id"),
            (self.version, "candidate version"),
            (self.permission_scope, "candidate permission_scope"),
            (self.authority_label, "candidate authority_label"),
            (self.status, "candidate status"),
        ):
            _identifier(value, name)
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        if self.environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContextRoutingValidationError("candidate environment is unsupported")
        if _SHA256.fullmatch(self.content_hash) is None:
            raise ContextRoutingValidationError("candidate content_hash must be SHA-256")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "relevance", _ratio(self.relevance, "relevance"))
        object.__setattr__(self, "importance", _ratio(self.importance, "importance"))
        object.__setattr__(self, "activation", _ratio(self.activation, "activation"))
        object.__setattr__(self, "tags", _unique_texts(self.tags, "candidate tags"))
        object.__setattr__(self, "scopes", _unique_texts(self.scopes, "candidate scopes"))
        if not isinstance(self.eligible, bool):
            raise ContextRoutingValidationError("candidate eligible must be boolean")
        if self.invalid_reason is not None:
            _identifier(self.invalid_reason, "candidate invalid_reason")
        if not self.eligible and self.invalid_reason is None:
            raise ContextRoutingValidationError("ineligible candidate requires a reason")


@dataclass(frozen=True, slots=True)
class ContextSourceBatch:
    source_id: str
    partition: ContextPartition
    source_version: str
    candidates: tuple[ContextSourceCandidate, ...]

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source batch source_id")
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        _identifier(self.source_version, "source_version")
        if any(not isinstance(item, ContextSourceCandidate) for item in self.candidates):
            raise ContextRoutingValidationError("source candidates are invalid")
        if any(
            item.source_id != self.source_id or item.partition is not self.partition
            for item in self.candidates
        ):
            raise ContextRoutingValidationError("source batch candidate boundary mismatch")
        identities = [item.stable_id for item in self.candidates]
        if len(identities) != len(set(identities)):
            raise ContextRoutingValidationError("source batch contains duplicate identities")


@dataclass(frozen=True, slots=True)
class ContextCandidateReference:
    source_id: str
    partition: ContextPartition
    stable_id: str
    subject_id: str
    environment: str
    version: str
    content_hash: str
    authority_label: str
    rank: int
    score: float
    occurred_at: datetime
    explanation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        candidate = ContextSourceCandidate(
            source_id=self.source_id,
            partition=self.partition,
            stable_id=self.stable_id,
            subject_id=self.subject_id,
            environment=self.environment,
            version=self.version,
            content_hash=self.content_hash,
            occurred_at=self.occurred_at,
            permission_scope="REFERENCE_ONLY",
            authority_label=self.authority_label,
            relevance=0.0,
        )
        object.__setattr__(self, "partition", candidate.partition)
        object.__setattr__(self, "occurred_at", candidate.occurred_at)
        if not isinstance(self.rank, int) or self.rank < 1:
            raise ContextRoutingValidationError("candidate rank must be positive")
        object.__setattr__(self, "score", _ratio(self.score, "candidate score"))
        object.__setattr__(
            self,
            "explanation_codes",
            _unique_texts(self.explanation_codes, "candidate explanation_codes"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "partition": self.partition.value,
            "stable_id": self.stable_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "version": self.version,
            "content_hash": self.content_hash,
            "authority_label": self.authority_label,
            "rank": self.rank,
            "score": self.score,
            "occurred_at": _format_time(self.occurred_at),
            "explanation_codes": list(self.explanation_codes),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextCandidateReference:
        if not isinstance(value, dict):
            raise ContextRoutingValidationError("candidate reference must be an object")
        return cls(
            source_id=value.get("source_id"),
            partition=value.get("partition"),
            stable_id=value.get("stable_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            version=value.get("version"),
            content_hash=value.get("content_hash"),
            authority_label=value.get("authority_label"),
            rank=value.get("rank"),
            score=value.get("score"),
            occurred_at=_parse_time(value.get("occurred_at"), "candidate occurred_at"),
            explanation_codes=tuple(value.get("explanation_codes", [])),
        )


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    source_id: str
    partition: ContextPartition
    stable_id: str
    status: CandidateDecisionStatus
    reason_code: str
    score: float | None = None

    def __post_init__(self) -> None:
        _identifier(self.source_id, "decision source_id")
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        _identifier(self.stable_id, "decision stable_id")
        object.__setattr__(self, "status", CandidateDecisionStatus(self.status))
        _identifier(self.reason_code, "decision reason_code")
        if self.score is not None:
            object.__setattr__(self, "score", _ratio(self.score, "decision score"))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "partition": self.partition.value,
            "stable_id": self.stable_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CandidateDecision:
        if not isinstance(value, dict):
            raise ContextRoutingValidationError("candidate decision must be an object")
        return cls(
            value.get("source_id"),
            value.get("partition"),
            value.get("stable_id"),
            value.get("status"),
            value.get("reason_code"),
            value.get("score"),
        )


@dataclass(frozen=True, slots=True)
class SourceTrace:
    source_id: str
    partition: ContextPartition
    status: PartitionDecisionStatus
    reason_code: str
    requested_limit: int
    source_version: str | None
    permission_policy_version: str
    candidate_count: int = 0
    retained_count: int = 0
    rejected_count: int = 0
    evaluated_count: int = 0

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source trace source_id")
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        object.__setattr__(self, "status", PartitionDecisionStatus(self.status))
        _identifier(self.reason_code, "source trace reason_code")
        if self.source_version is not None:
            _identifier(self.source_version, "source trace source_version")
        _identifier(self.permission_policy_version, "permission_policy_version")
        for value, name in (
            (self.requested_limit, "source requested_limit"),
            (self.candidate_count, "source candidate_count"),
            (self.retained_count, "source retained_count"),
            (self.rejected_count, "source rejected_count"),
            (self.evaluated_count, "source evaluated_count"),
        ):
            if not isinstance(value, int) or value < 0:
                raise ContextRoutingValidationError(f"{name} must be non-negative")
        if self.evaluated_count > self.candidate_count:
            raise ContextRoutingValidationError(
                "source evaluated_count cannot exceed retrieved candidates"
            )

    @property
    def retrieved_count(self) -> int:
        return self.candidate_count

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "partition": self.partition.value,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "requested_limit": self.requested_limit,
            "source_version": self.source_version,
            "permission_policy_version": self.permission_policy_version,
            "candidate_count": self.candidate_count,
            "retrieved_count": self.candidate_count,
            "evaluated_count": self.evaluated_count,
            "retained_count": self.retained_count,
            "rejected_count": self.rejected_count,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SourceTrace:
        if not isinstance(value, dict):
            raise ContextRoutingValidationError("source trace must be an object")
        candidate_count = value.get(
            "retrieved_count", value.get("candidate_count", 0)
        )
        if (
            "candidate_count" in value
            and "retrieved_count" in value
            and value["candidate_count"] != value["retrieved_count"]
        ):
            raise ContextRoutingValidationError(
                "source trace retrieved count fields disagree"
            )
        return cls(
            value.get("source_id"),
            value.get("partition"),
            value.get("status"),
            value.get("reason_code"),
            value.get("requested_limit"),
            value.get("source_version"),
            value.get("permission_policy_version"),
            candidate_count,
            value.get("retained_count", 0),
            value.get("rejected_count", 0),
            value.get("evaluated_count", candidate_count),
        )


@dataclass(frozen=True, slots=True)
class PartitionTrace:
    partition: ContextPartition
    status: PartitionDecisionStatus
    reason_code: str
    requested_limit: int
    source_ids: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...] = ()
    candidate_count: int = 0
    retained_count: int = 0
    rejected_count: int = 0
    evaluated_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "partition", ContextPartition(self.partition))
        object.__setattr__(self, "status", PartitionDecisionStatus(self.status))
        _identifier(self.reason_code, "partition trace reason_code")
        object.__setattr__(self, "source_ids", _unique_texts(self.source_ids, "trace source_ids"))
        if len(self.source_versions) != len({item[0] for item in self.source_versions}):
            raise ContextRoutingValidationError("trace source versions contain duplicates")
        for source_id, version in self.source_versions:
            _identifier(source_id, "trace source_id")
            _identifier(version, "trace source_version")
        for value, name in (
            (self.requested_limit, "requested_limit"),
            (self.candidate_count, "candidate_count"),
            (self.retained_count, "retained_count"),
            (self.rejected_count, "rejected_count"),
            (self.evaluated_count, "evaluated_count"),
        ):
            if not isinstance(value, int) or value < 0:
                raise ContextRoutingValidationError(f"{name} must be non-negative")
        if self.evaluated_count > self.candidate_count:
            raise ContextRoutingValidationError(
                "partition evaluated_count cannot exceed retrieved candidates"
            )

    @property
    def retrieved_count(self) -> int:
        return self.candidate_count

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "partition": self.partition.value,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "requested_limit": self.requested_limit,
            "source_ids": list(self.source_ids),
            "source_versions": {
                source_id: version for source_id, version in self.source_versions
            },
            "candidate_count": self.candidate_count,
            "retrieved_count": self.candidate_count,
            "evaluated_count": self.evaluated_count,
            "retained_count": self.retained_count,
            "rejected_count": self.rejected_count,
        }

    @classmethod
    def from_dict(cls, value: Any) -> PartitionTrace:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("source_ids"), list)
            or not isinstance(value.get("source_versions", {}), dict)
        ):
            raise ContextRoutingValidationError("partition trace must be an object")
        candidate_count = value.get(
            "retrieved_count", value.get("candidate_count", 0)
        )
        if (
            "candidate_count" in value
            and "retrieved_count" in value
            and value["candidate_count"] != value["retrieved_count"]
        ):
            raise ContextRoutingValidationError(
                "partition trace retrieved count fields disagree"
            )
        return cls(
            value.get("partition"),
            value.get("status"),
            value.get("reason_code"),
            value.get("requested_limit"),
            tuple(value["source_ids"]),
            tuple(value.get("source_versions", {}).items()),
            candidate_count,
            value.get("retained_count", 0),
            value.get("rejected_count", 0),
            value.get("evaluated_count", candidate_count),
        )


@dataclass(frozen=True, slots=True)
class CandidateManifest:
    request_id: str
    route_plan_hash: str
    candidates: tuple[ContextCandidateReference, ...]
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.request_id, "manifest request_id")
        if _SHA256.fullmatch(self.route_plan_hash) is None:
            raise ContextRoutingValidationError("route_plan_hash must be SHA-256")
        if any(not isinstance(item, ContextCandidateReference) for item in self.candidates):
            raise ContextRoutingValidationError("manifest candidates are invalid")
        if tuple(item.rank for item in self.candidates) != tuple(
            range(1, len(self.candidates) + 1)
        ):
            raise ContextRoutingValidationError("manifest ranks must be contiguous")
        identities = [(item.source_id, item.stable_id) for item in self.candidates]
        if len(identities) != len(set(identities)):
            raise ContextRoutingValidationError("manifest contains duplicate candidates")
        expected = _hash(self.canonical_dict())
        if self.manifest_hash is None:
            object.__setattr__(self, "manifest_hash", expected)
        elif self.manifest_hash != expected:
            raise ContextRoutingValidationError("candidate manifest integrity check failed")

    def canonical_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "route_plan_hash": self.route_plan_hash,
            "candidates": [item.to_dict() for item in self.candidates],
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.canonical_dict(), "manifest_hash": self.manifest_hash}

    @classmethod
    def from_dict(cls, value: Any) -> CandidateManifest:
        if not isinstance(value, dict) or not isinstance(value.get("candidates"), list):
            raise ContextRoutingValidationError("candidate manifest must be an object")
        return cls(
            request_id=value.get("request_id"),
            route_plan_hash=value.get("route_plan_hash"),
            candidates=tuple(
                ContextCandidateReference.from_dict(item) for item in value["candidates"]
            ),
            manifest_hash=value.get("manifest_hash"),
        )


@dataclass(frozen=True, slots=True)
class ContextTrace:
    trace_id: str
    request_id: str
    perception_id: str
    subject_id: str
    source_revision: int
    routed_at: datetime
    purpose: tuple[str, ...]
    route_plan_hash: str
    manifest_hash: str
    route_status: ContextRouteStatus
    feature_gate_version: str
    partition_traces: tuple[PartitionTrace, ...]
    source_traces: tuple[SourceTrace, ...]
    candidate_decisions: tuple[CandidateDecision, ...]
    budget_limit: int
    budget_used: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.trace_id, "trace_id"),
            (self.request_id, "trace request_id"),
            (self.perception_id, "trace perception_id"),
            (self.subject_id, "trace subject_id"),
            (self.feature_gate_version, "trace feature_gate_version"),
        ):
            _identifier(value, name)
        object.__setattr__(self, "routed_at", _utc(self.routed_at, "trace routed_at"))
        object.__setattr__(self, "purpose", _unique_texts(self.purpose, "trace purpose"))
        for value, name in (
            (self.route_plan_hash, "trace route_plan_hash"),
            (self.manifest_hash, "trace manifest_hash"),
        ):
            if _SHA256.fullmatch(value) is None:
                raise ContextRoutingValidationError(f"{name} must be SHA-256")
        object.__setattr__(self, "route_status", ContextRouteStatus(self.route_status))
        if any(not isinstance(item, SourceTrace) for item in self.source_traces):
            raise ContextRoutingValidationError("trace source_traces are invalid")
        if not isinstance(self.source_revision, int) or self.source_revision < 0:
            raise ContextRoutingValidationError("trace source_revision is invalid")
        if not isinstance(self.budget_limit, int) or not isinstance(self.budget_used, int):
            raise ContextRoutingValidationError("trace budget values must be integers")
        if self.budget_limit < 0 or self.budget_used < 0:
            raise ContextRoutingValidationError(
                "trace budget values must be non-negative"
            )
        if (
            self.budget_used > self.budget_limit
            and self.route_status is ContextRouteStatus.COMPLETE
        ):
            raise ContextRoutingValidationError(
                "a complete trace cannot exceed its retrieval budget"
            )
        for source in self.source_traces:
            if source.retained_count + source.rejected_count != source.candidate_count:
                raise ContextRoutingValidationError(
                    "source trace outcomes do not cover retrieved candidates"
                )
        for partition in self.partition_traces:
            if (
                partition.retained_count + partition.rejected_count
                != partition.candidate_count
            ):
                raise ContextRoutingValidationError(
                    "partition trace outcomes do not cover retrieved candidates"
                )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "perception_id": self.perception_id,
            "subject_id": self.subject_id,
            "source_revision": self.source_revision,
            "routed_at": _format_time(self.routed_at),
            "purpose": list(self.purpose),
            "route_plan_hash": self.route_plan_hash,
            "manifest_hash": self.manifest_hash,
            "route_status": self.route_status.value,
            "feature_gate_version": self.feature_gate_version,
            "partition_traces": [item.to_dict() for item in self.partition_traces],
            "source_traces": [item.to_dict() for item in self.source_traces],
            "candidate_decisions": [item.to_dict() for item in self.candidate_decisions],
            "budget_limit": self.budget_limit,
            "budget_used": self.budget_used,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextTrace:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("purpose"), list)
            or not isinstance(value.get("partition_traces"), list)
            or not isinstance(value.get("source_traces"), list)
            or not isinstance(value.get("candidate_decisions"), list)
        ):
            raise ContextRoutingValidationError("context trace must be an object")
        return cls(
            trace_id=value.get("trace_id"),
            request_id=value.get("request_id"),
            perception_id=value.get("perception_id"),
            subject_id=value.get("subject_id"),
            source_revision=value.get("source_revision"),
            routed_at=_parse_time(value.get("routed_at"), "trace routed_at"),
            purpose=tuple(value["purpose"]),
            route_plan_hash=value.get("route_plan_hash"),
            manifest_hash=value.get("manifest_hash"),
            route_status=value.get("route_status"),
            feature_gate_version=value.get("feature_gate_version"),
            partition_traces=tuple(
                PartitionTrace.from_dict(item) for item in value["partition_traces"]
            ),
            source_traces=tuple(
                SourceTrace.from_dict(item) for item in value["source_traces"]
            ),
            candidate_decisions=tuple(
                CandidateDecision.from_dict(item)
                for item in value["candidate_decisions"]
            ),
            budget_limit=value.get("budget_limit"),
            budget_used=value.get("budget_used"),
        )


@dataclass(frozen=True, slots=True)
class ContextRouteResult:
    plan: RoutePlan
    manifest: CandidateManifest
    trace: ContextTrace

    def __post_init__(self) -> None:
        if self.manifest.request_id != self.plan.request.request_id:
            raise ContextRoutingValidationError("manifest does not belong to route plan")
        if self.manifest.route_plan_hash != self.plan.canonical_hash():
            raise ContextRoutingValidationError("manifest route plan hash mismatch")
        if self.trace.request_id != self.plan.request.request_id:
            raise ContextRoutingValidationError("trace does not belong to route plan")
        if self.trace.route_plan_hash != self.plan.canonical_hash():
            raise ContextRoutingValidationError("trace route plan hash mismatch")
        if self.trace.manifest_hash != self.manifest.manifest_hash:
            raise ContextRoutingValidationError("trace manifest hash mismatch")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "plan": self.plan.to_dict(),
            "manifest": self.manifest.to_dict(),
            "trace": self.trace.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContextRouteResult:
        if not isinstance(value, dict):
            raise ContextRoutingValidationError("context route result must be an object")
        return cls(
            RoutePlan.from_dict(value.get("plan")),
            CandidateManifest.from_dict(value.get("manifest")),
            ContextTrace.from_dict(value.get("trace")),
        )

    def canonical_hash(self) -> str:
        return _hash(self.to_dict())
