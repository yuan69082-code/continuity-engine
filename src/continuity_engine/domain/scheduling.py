from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any


SCHEDULER_FORMAT_VERSION = 1


class SchedulerError(Exception):
    """Base error for the P11 scheduling boundary."""


class SchedulerValidationError(SchedulerError):
    pass


class SchedulerPersistenceError(SchedulerError):
    pass


class SchedulerIdentityConflictError(SchedulerError):
    pass


class SchedulerTaskState(str, Enum):
    QUEUED = "QUEUED"
    UNKNOWN = "UNKNOWN"
    RETRY_WAIT = "RETRY_WAIT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


class SchedulerWakeReason(str, Enum):
    EVENT = "event"
    SCHEDULED = "scheduled"
    INTERNAL = "internal"
    RUNTIME_RECOVERY = "runtime_recovery"


class NotificationStatus(str, Enum):
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_DELIVERED = "NOT_DELIVERED"


class SchedulerAdmissionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    BACKPRESSURE = "BACKPRESSURE"


class SchedulerTickStatus(str, Enum):
    IDLE = "IDLE"
    NOT_DUE = "NOT_DUE"
    QUIET_HOURS = "QUIET_HOURS"
    RESOURCE_DEFERRED = "RESOURCE_DEFERRED"
    COMPLETED = "COMPLETED"
    RECONCILED_COMPLETED = "RECONCILED_COMPLETED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    CANCELLED = "CANCELLED"


class SchedulerCancelStatus(str, Enum):
    CANCELLED = "CANCELLED"
    ALREADY_CANCELLED = "ALREADY_CANCELLED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    TERMINAL = "TERMINAL"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchedulerValidationError(f"{field_name} must be a non-empty string")
    return value


def _utc(value: Any, field_name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchedulerValidationError(f"{field_name} must be timezone-aware")
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise SchedulerValidationError(f"{field_name} must use trusted UTC")
    return value.astimezone(timezone.utc)


def _format(value: datetime | None) -> str | None:
    if value is None:
        return None
    parsed = _utc(value, "datetime")
    assert parsed is not None
    return parsed.isoformat().replace("+00:00", "Z")


def _parse(value: Any, field_name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise SchedulerValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchedulerValidationError(f"{field_name} is not a valid datetime") from exc
    return _utc(parsed, field_name)


def _enum(enum_type: type[Enum], value: Any, field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        raise SchedulerValidationError(f"unsupported {field_name}") from exc


def _non_negative(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchedulerValidationError(f"{field_name} must be a non-negative integer")
    return value


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class QuietHours:
    start: time
    end: time

    def __post_init__(self) -> None:
        if not isinstance(self.start, time) or not isinstance(self.end, time):
            raise SchedulerValidationError("quiet hours require time values")
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise SchedulerValidationError("quiet hours are expressed in trusted UTC")
        if self.start == self.end:
            raise SchedulerValidationError("quiet hours start and end must differ")

    def contains(self, current: datetime) -> bool:
        current_utc = _utc(current, "quiet-hours current time")
        assert current_utc is not None
        value = current_utc.time().replace(tzinfo=None)
        if self.start < self.end:
            return self.start <= value < self.end
        return value >= self.start or value < self.end


@dataclass(slots=True)
class SchedulerTask:
    task_id: str
    subject_id: str
    environment: str
    priority: int
    due_at: datetime
    wake_reason: SchedulerWakeReason
    cycle_id: str
    created_at: datetime
    source_event_id: str | None = None
    max_attempts: int = 3
    state: SchedulerTaskState = SchedulerTaskState.QUEUED
    sequence: int = 0
    revision: int = 0
    attempt_count: int = 0
    next_attempt_at: datetime | None = None
    last_attempt_id: str | None = None
    last_receipt_id: str | None = None
    last_receipt_hash: str | None = None
    last_receipt_status: NotificationStatus | None = None
    cancel_requested_at: datetime | None = None
    completed_at: datetime | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.task_id = _text(self.task_id, "task_id")
        self.subject_id = _text(self.subject_id, "subject_id")
        self.environment = _text(self.environment, "environment")
        self.cycle_id = _text(self.cycle_id, "cycle_id")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int) or not 0 <= self.priority <= 100:
            raise SchedulerValidationError("priority must be an integer from 0 through 100")
        self.due_at = _utc(self.due_at, "due_at")  # type: ignore[assignment]
        self.created_at = _utc(self.created_at, "created_at")  # type: ignore[assignment]
        self.wake_reason = _enum(SchedulerWakeReason, self.wake_reason, "wake_reason")
        self.state = _enum(SchedulerTaskState, self.state, "task state")
        if self.wake_reason is SchedulerWakeReason.EVENT:
            self.source_event_id = _text(self.source_event_id, "source_event_id")
        elif self.source_event_id is not None:
            self.source_event_id = _text(self.source_event_id, "source_event_id")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 10:
            raise SchedulerValidationError("max_attempts must be an integer from 1 through 10")
        self.sequence = _non_negative(self.sequence, "sequence")
        self.revision = _non_negative(self.revision, "task revision")
        self.attempt_count = _non_negative(self.attempt_count, "attempt_count")
        if self.attempt_count > self.max_attempts:
            raise SchedulerValidationError("attempt_count exceeds max_attempts")
        self.next_attempt_at = _utc(self.next_attempt_at, "next_attempt_at", optional=True)
        self.cancel_requested_at = _utc(
            self.cancel_requested_at, "cancel_requested_at", optional=True
        )
        self.completed_at = _utc(self.completed_at, "completed_at", optional=True)
        for value, name in (
            (self.last_attempt_id, "last_attempt_id"),
            (self.last_receipt_id, "last_receipt_id"),
            (self.last_receipt_hash, "last_receipt_hash"),
        ):
            if value is not None:
                _text(value, name)
        if self.last_receipt_status is not None:
            self.last_receipt_status = _enum(
                NotificationStatus, self.last_receipt_status, "receipt status"
            )
        if not isinstance(self.reason_codes, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.reason_codes
        ):
            raise SchedulerValidationError("reason_codes must be a tuple of non-empty strings")
        if self.state in (SchedulerTaskState.UNKNOWN, SchedulerTaskState.RETRY_WAIT) and (
            self.attempt_count == 0 or self.last_attempt_id is None
        ):
            raise SchedulerValidationError("attempt state requires a stable attempt identity")
        if self.state is SchedulerTaskState.RETRY_WAIT and self.next_attempt_at is None:
            raise SchedulerValidationError("retry wait requires next_attempt_at")
        if self.state is SchedulerTaskState.COMPLETED:
            if (
                self.completed_at is None
                or self.last_receipt_status is not NotificationStatus.DELIVERED
                or self.last_receipt_id is None
                or self.last_receipt_hash is None
            ):
                raise SchedulerValidationError("completed task requires a bound delivered receipt")
        elif self.completed_at is not None:
            raise SchedulerValidationError("only completed tasks may contain completed_at")

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        subject_id: str,
        environment: str,
        priority: int,
        due_at: datetime,
        wake_reason: SchedulerWakeReason | str,
        cycle_id: str,
        created_at: datetime,
        source_event_id: str | None = None,
        max_attempts: int = 3,
    ) -> SchedulerTask:
        return cls(
            task_id=task_id,
            subject_id=subject_id,
            environment=environment,
            priority=priority,
            due_at=due_at,
            wake_reason=wake_reason,  # type: ignore[arg-type]
            cycle_id=cycle_id,
            created_at=created_at,
            source_event_id=source_event_id,
            max_attempts=max_attempts,
        )

    @property
    def identity_hash(self) -> str:
        return _canonical_hash(
            {
                "cycle_id": self.cycle_id,
                "created_at": _format(self.created_at),
                "due_at": _format(self.due_at),
                "environment": self.environment,
                "max_attempts": self.max_attempts,
                "priority": self.priority,
                "source_event_id": self.source_event_id,
                "subject_id": self.subject_id,
                "task_id": self.task_id,
                "wake_reason": self.wake_reason.value,
            }
        )

    def effective_priority(self, now: datetime, aging_interval_seconds: int) -> int:
        current = _utc(now, "priority time")
        assert current is not None
        if isinstance(aging_interval_seconds, bool) or not isinstance(aging_interval_seconds, int) or aging_interval_seconds <= 0:
            raise SchedulerValidationError("aging_interval_seconds must be positive")
        eligible_at = max(self.created_at, self.due_at)
        age_seconds = max(0, int((current - eligible_at).total_seconds()))
        return self.priority + age_seconds // aging_interval_seconds

    def clone(self) -> SchedulerTask:
        return SchedulerTask.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        value = {
            "task_id": self.task_id,
            "subject_id": self.subject_id,
            "environment": self.environment,
            "priority": self.priority,
            "due_at": _format(self.due_at),
            "wake_reason": self.wake_reason.value,
            "cycle_id": self.cycle_id,
            "source_event_id": self.source_event_id,
            "created_at": _format(self.created_at),
            "max_attempts": self.max_attempts,
            "identity_hash": self.identity_hash,
            "state": self.state.value,
            "sequence": self.sequence,
            "revision": self.revision,
            "attempt_count": self.attempt_count,
            "next_attempt_at": _format(self.next_attempt_at),
            "last_attempt_id": self.last_attempt_id,
            "last_receipt_id": self.last_receipt_id,
            "last_receipt_hash": self.last_receipt_hash,
            "last_receipt_status": (
                self.last_receipt_status.value if self.last_receipt_status is not None else None
            ),
            "cancel_requested_at": _format(self.cancel_requested_at),
            "completed_at": _format(self.completed_at),
            "reason_codes": list(self.reason_codes),
        }
        value["record_hash"] = _canonical_hash(value)
        return value

    @classmethod
    def from_dict(cls, value: Any) -> SchedulerTask:
        if not isinstance(value, dict):
            raise SchedulerValidationError("scheduler task must be an object")
        expected = {
            "task_id", "subject_id", "environment", "priority", "due_at", "wake_reason",
            "cycle_id", "source_event_id", "created_at", "max_attempts", "identity_hash",
            "state", "sequence", "revision", "attempt_count", "next_attempt_at",
            "last_attempt_id", "last_receipt_id", "last_receipt_hash",
            "last_receipt_status", "cancel_requested_at", "completed_at", "reason_codes",
            "record_hash",
        }
        if set(value) != expected:
            raise SchedulerValidationError("scheduler task fields are incomplete or unsupported")
        reason_codes = value.get("reason_codes")
        if not isinstance(reason_codes, list):
            raise SchedulerValidationError("reason_codes must be a list")
        task = cls(
            task_id=value.get("task_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            priority=value.get("priority"),
            due_at=_parse(value.get("due_at"), "due_at"),  # type: ignore[arg-type]
            wake_reason=value.get("wake_reason"),
            cycle_id=value.get("cycle_id"),
            source_event_id=value.get("source_event_id"),
            created_at=_parse(value.get("created_at"), "created_at"),  # type: ignore[arg-type]
            max_attempts=value.get("max_attempts"),
            state=value.get("state"),
            sequence=value.get("sequence"),
            revision=value.get("revision"),
            attempt_count=value.get("attempt_count"),
            next_attempt_at=_parse(value.get("next_attempt_at"), "next_attempt_at", optional=True),
            last_attempt_id=value.get("last_attempt_id"),
            last_receipt_id=value.get("last_receipt_id"),
            last_receipt_hash=value.get("last_receipt_hash"),
            last_receipt_status=value.get("last_receipt_status"),
            cancel_requested_at=_parse(value.get("cancel_requested_at"), "cancel_requested_at", optional=True),
            completed_at=_parse(value.get("completed_at"), "completed_at", optional=True),
            reason_codes=tuple(reason_codes),
        )
        if value.get("identity_hash") != task.identity_hash:
            raise SchedulerValidationError("scheduler task identity hash does not match")
        if value.get("record_hash") != task.to_dict()["record_hash"]:
            raise SchedulerValidationError("scheduler task record hash does not match")
        return task


@dataclass(slots=True)
class SchedulerQueue:
    revision: int = 0
    next_sequence: int = 1
    tasks: list[SchedulerTask] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.revision = _non_negative(self.revision, "queue revision")
        if isinstance(self.next_sequence, bool) or not isinstance(self.next_sequence, int) or self.next_sequence <= 0:
            raise SchedulerValidationError("next_sequence must be positive")
        if not isinstance(self.tasks, list) or any(not isinstance(item, SchedulerTask) for item in self.tasks):
            raise SchedulerValidationError("tasks must contain SchedulerTask values")
        if len({item.task_id for item in self.tasks}) != len(self.tasks):
            raise SchedulerValidationError("scheduler task identities must be unique")
        assigned = [item.sequence for item in self.tasks if item.sequence > 0]
        if len(set(assigned)) != len(assigned):
            raise SchedulerValidationError("scheduler task sequences must be unique")
        if assigned and self.next_sequence <= max(assigned):
            raise SchedulerValidationError("next_sequence must exceed assigned sequences")

    def clone(self) -> SchedulerQueue:
        return SchedulerQueue.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheduler_format_version": SCHEDULER_FORMAT_VERSION,
            "revision": self.revision,
            "next_sequence": self.next_sequence,
            "tasks": [item.to_dict() for item in self.tasks],
        }

    @classmethod
    def from_dict(cls, value: Any) -> SchedulerQueue:
        if not isinstance(value, dict) or set(value) != {
            "scheduler_format_version", "revision", "next_sequence", "tasks"
        }:
            raise SchedulerValidationError("scheduler queue fields are incomplete or unsupported")
        if value.get("scheduler_format_version") != SCHEDULER_FORMAT_VERSION:
            raise SchedulerValidationError("unsupported scheduler persistence format")
        raw_tasks = value.get("tasks")
        if not isinstance(raw_tasks, list):
            raise SchedulerValidationError("scheduler tasks must be a list")
        return cls(
            revision=value.get("revision"),
            next_sequence=value.get("next_sequence"),
            tasks=[SchedulerTask.from_dict(item) for item in raw_tasks],
        )


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    task_id: str
    attempt_id: str
    subject_id: str
    environment: str
    cycle_id: str
    wake_reason: SchedulerWakeReason
    source_event_id: str | None
    requested_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.task_id, "notification task_id"),
            (self.attempt_id, "notification attempt_id"),
            (self.subject_id, "notification subject_id"),
            (self.environment, "notification environment"),
            (self.cycle_id, "notification cycle_id"),
        ):
            _text(value, name)
        object.__setattr__(self, "wake_reason", _enum(SchedulerWakeReason, self.wake_reason, "wake_reason"))
        object.__setattr__(self, "requested_at", _utc(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class NotificationReceipt:
    receipt_id: str
    task_id: str
    attempt_id: str
    subject_id: str
    environment: str
    status: NotificationStatus
    observed_at: datetime
    reason_code: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.receipt_id, "receipt_id"),
            (self.task_id, "receipt task_id"),
            (self.attempt_id, "receipt attempt_id"),
            (self.subject_id, "receipt subject_id"),
            (self.environment, "receipt environment"),
            (self.reason_code, "receipt reason_code"),
        ):
            _text(value, name)
        object.__setattr__(self, "status", _enum(NotificationStatus, self.status, "notification status"))
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "receipt observed_at"))

    @property
    def receipt_hash(self) -> str:
        return _canonical_hash(
            {
                "attempt_id": self.attempt_id,
                "environment": self.environment,
                "observed_at": _format(self.observed_at),
                "reason_code": self.reason_code,
                "receipt_id": self.receipt_id,
                "status": self.status.value,
                "subject_id": self.subject_id,
                "task_id": self.task_id,
            }
        )


@dataclass(frozen=True, slots=True)
class SchedulerAdmissionResult:
    status: SchedulerAdmissionStatus
    task: SchedulerTask | None
    queue_revision: int
    reason_code: str


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    status: SchedulerTickStatus
    task: SchedulerTask | None
    queue_revision: int
    reason_code: str
    receipt: NotificationReceipt | None = None


@dataclass(frozen=True, slots=True)
class SchedulerCancelResult:
    status: SchedulerCancelStatus
    task: SchedulerTask
    queue_revision: int
    reason_code: str


TERMINAL_STATES = frozenset(
    {
        SchedulerTaskState.COMPLETED,
        SchedulerTaskState.CANCELLED,
        SchedulerTaskState.RETRY_EXHAUSTED,
    }
)


def stable_attempt_id(task_id: str, attempt_number: int) -> str:
    _text(task_id, "task_id")
    if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number <= 0:
        raise SchedulerValidationError("attempt_number must be positive")
    raw = f"p11-scheduler-attempt\0{task_id}\0{attempt_number}".encode("utf-8")
    return "p11-attempt-" + hashlib.sha256(raw).hexdigest()
