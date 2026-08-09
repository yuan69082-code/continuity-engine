from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .errors import AwakeningValidationError
from .events import Event, JsonValue, StateUpdateRecord
from .memory import MemoryRetrievalResult
from .models import SubjectState


class AwakeMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class WakeReason(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"


class WakeAction(str, Enum):
    SLEEP = "SLEEP"
    THINK = "THINK"
    CHECK_MEMORY = "CHECK_MEMORY"
    READY = "READY"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AwakeningValidationError(f"{field_name} must be a non-empty string")
    return value


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise AwakeningValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise AwakeningValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AwakeningValidationError(f"{field_name} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise AwakeningValidationError(f"{field_name} must include a timezone")
    return parsed


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise AwakeningValidationError(f"{field_name} must be a list of non-empty strings")
    return list(value)


@dataclass(slots=True)
class AwakeCycle:
    cycle_id: str
    subject_id: str
    mode: AwakeMode
    created_at: datetime
    enabled: bool = True
    interval_seconds: int | None = None
    next_wake_at: datetime | None = None
    last_wake_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.cycle_id, "cycle_id")
        _require_text(self.subject_id, "cycle.subject_id")
        if not isinstance(self.mode, AwakeMode):
            try:
                self.mode = AwakeMode(self.mode)
            except ValueError as exc:
                raise AwakeningValidationError("unsupported awake cycle mode") from exc
        if self.created_at.tzinfo is None:
            raise AwakeningValidationError("cycle.created_at must include a timezone")
        if not isinstance(self.enabled, bool):
            raise AwakeningValidationError("cycle.enabled must be a boolean")
        for value, name in (
            (self.next_wake_at, "next_wake_at"),
            (self.last_wake_at, "last_wake_at"),
        ):
            if value is not None and value.tzinfo is None:
                raise AwakeningValidationError(f"cycle.{name} must include a timezone")

        if self.mode is AwakeMode.SCHEDULED:
            if not isinstance(self.interval_seconds, int) or self.interval_seconds <= 0:
                raise AwakeningValidationError(
                    "scheduled cycles require a positive interval_seconds"
                )
            if self.next_wake_at is None:
                raise AwakeningValidationError("scheduled cycles require next_wake_at")
        elif self.interval_seconds is not None or self.next_wake_at is not None:
            raise AwakeningValidationError(
                "manual cycles cannot define interval_seconds or next_wake_at"
            )

    @classmethod
    def manual(
        cls,
        *,
        subject_id: str,
        created_at: datetime,
        cycle_id: str | None = None,
    ) -> AwakeCycle:
        return cls(
            cycle_id=cycle_id or str(uuid4()),
            subject_id=subject_id,
            mode=AwakeMode.MANUAL,
            created_at=created_at,
        )

    @classmethod
    def scheduled(
        cls,
        *,
        subject_id: str,
        created_at: datetime,
        interval_seconds: int,
        first_wake_at: datetime,
        cycle_id: str | None = None,
    ) -> AwakeCycle:
        return cls(
            cycle_id=cycle_id or str(uuid4()),
            subject_id=subject_id,
            mode=AwakeMode.SCHEDULED,
            created_at=created_at,
            interval_seconds=interval_seconds,
            next_wake_at=first_wake_at,
        )

    def is_due(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise AwakeningValidationError("now must include a timezone")
        return (
            self.enabled
            and self.mode is AwakeMode.SCHEDULED
            and self.next_wake_at is not None
            and now >= self.next_wake_at
        )

    def mark_woken(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise AwakeningValidationError("wake time must include a timezone")
        self.last_wake_at = at
        if self.mode is AwakeMode.SCHEDULED:
            assert self.interval_seconds is not None
            assert self.next_wake_at is not None
            if at < self.next_wake_at:
                return
            overdue_seconds = (at - self.next_wake_at).total_seconds()
            intervals = int(overdue_seconds // self.interval_seconds) + 1
            self.next_wake_at += timedelta(seconds=intervals * self.interval_seconds)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "cycle_id": self.cycle_id,
            "subject_id": self.subject_id,
            "mode": self.mode.value,
            "created_at": _format_datetime(self.created_at),
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "next_wake_at": _format_datetime(self.next_wake_at),
            "last_wake_at": _format_datetime(self.last_wake_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> AwakeCycle:
        if not isinstance(value, dict):
            raise AwakeningValidationError("awake cycle must be an object")
        created_at = _parse_datetime(value.get("created_at"), "cycle.created_at")
        assert created_at is not None
        return cls(
            cycle_id=value.get("cycle_id"),
            subject_id=value.get("subject_id"),
            mode=value.get("mode"),
            created_at=created_at,
            enabled=value.get("enabled", True),
            interval_seconds=value.get("interval_seconds"),
            next_wake_at=_parse_datetime(
                value.get("next_wake_at"), "cycle.next_wake_at", optional=True
            ),
            last_wake_at=_parse_datetime(
                value.get("last_wake_at"), "cycle.last_wake_at", optional=True
            ),
        )


@dataclass(slots=True)
class WakeTrigger:
    reason: WakeReason
    detail: str
    triggered_at: datetime
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, WakeReason):
            try:
                self.reason = WakeReason(self.reason)
            except ValueError as exc:
                raise AwakeningValidationError("unsupported wake reason") from exc
        _require_text(self.detail, "wake trigger detail")
        if self.triggered_at.tzinfo is None:
            raise AwakeningValidationError("triggered_at must include a timezone")
        if self.reason is WakeReason.EVENT:
            _require_text(self.source_event_id, "source_event_id")
        elif self.source_event_id is not None:
            raise AwakeningValidationError(
                "source_event_id is only valid for event-triggered wakes"
            )

    @classmethod
    def manual(cls, *, triggered_at: datetime, detail: str) -> WakeTrigger:
        return cls(WakeReason.MANUAL, detail, triggered_at)

    @classmethod
    def scheduled(cls, *, triggered_at: datetime, detail: str) -> WakeTrigger:
        return cls(WakeReason.SCHEDULED, detail, triggered_at)

    @classmethod
    def event(
        cls,
        *,
        triggered_at: datetime,
        detail: str,
        source_event_id: str,
    ) -> WakeTrigger:
        return cls(WakeReason.EVENT, detail, triggered_at, source_event_id)


@dataclass(slots=True)
class WakeTimeInfo:
    current_time: datetime
    last_interaction_at: datetime | None
    seconds_since_last_interaction: float | None

    def __post_init__(self) -> None:
        if self.current_time.tzinfo is None:
            raise AwakeningValidationError("current_time must include a timezone")
        if self.last_interaction_at is not None and self.last_interaction_at.tzinfo is None:
            raise AwakeningValidationError("last_interaction_at must include a timezone")
        if self.seconds_since_last_interaction is not None and (
            not isinstance(self.seconds_since_last_interaction, (int, float))
            or self.seconds_since_last_interaction < 0
        ):
            raise AwakeningValidationError(
                "seconds_since_last_interaction must be non-negative or null"
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "current_time": _format_datetime(self.current_time),
            "last_interaction_at": _format_datetime(self.last_interaction_at),
            "seconds_since_last_interaction": self.seconds_since_last_interaction,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WakeTimeInfo:
        if not isinstance(value, dict):
            raise AwakeningValidationError("wake time info must be an object")
        current_time = _parse_datetime(value.get("current_time"), "current_time")
        assert current_time is not None
        elapsed = value.get("seconds_since_last_interaction")
        if elapsed is not None and not isinstance(elapsed, (int, float)):
            raise AwakeningValidationError(
                "seconds_since_last_interaction must be numeric or null"
            )
        return cls(
            current_time=current_time,
            last_interaction_at=_parse_datetime(
                value.get("last_interaction_at"), "last_interaction_at", optional=True
            ),
            seconds_since_last_interaction=float(elapsed) if elapsed is not None else None,
        )


@dataclass(slots=True)
class WakeContext:
    context_id: str
    subject_state: SubjectState
    recent_events: list[Event]
    recent_updates: list[StateUpdateRecord]
    memory_result: MemoryRetrievalResult
    time_info: WakeTimeInfo
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.context_id, "context_id")
        if self.created_at.tzinfo is None:
            raise AwakeningValidationError("wake context created_at must include a timezone")
        if self.memory_result.request.subject_id != self.subject_state.subject_id:
            raise AwakeningValidationError(
                "memory result subject does not match WakeContext subject"
            )
        if any(
            update.subject_id != self.subject_state.subject_id
            for update in self.recent_updates
        ):
            raise AwakeningValidationError("recent update belongs to a different subject")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "context_id": self.context_id,
            "subject_state": self.subject_state.to_dict(),
            "recent_events": [event.to_dict() for event in self.recent_events],
            "recent_updates": [update.to_dict() for update in self.recent_updates],
            "memory_result": self.memory_result.to_dict(),
            "time_info": self.time_info.to_dict(),
            "created_at": _format_datetime(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Any) -> WakeContext:
        if not isinstance(value, dict):
            raise AwakeningValidationError("wake context must be an object")
        raw_events = value.get("recent_events")
        raw_updates = value.get("recent_updates")
        if not isinstance(raw_events, list) or not isinstance(raw_updates, list):
            raise AwakeningValidationError("recent events and updates must be lists")
        created_at = _parse_datetime(value.get("created_at"), "context.created_at")
        assert created_at is not None
        return cls(
            context_id=value.get("context_id"),
            subject_state=SubjectState.from_dict(value.get("subject_state")),
            recent_events=[Event.from_dict(item) for item in raw_events],
            recent_updates=[StateUpdateRecord.from_dict(item) for item in raw_updates],
            memory_result=MemoryRetrievalResult.from_dict(value.get("memory_result")),
            time_info=WakeTimeInfo.from_dict(value.get("time_info")),
            created_at=created_at,
        )


@dataclass(slots=True)
class WakeDecision:
    action: WakeAction
    reason: str
    decided_at: datetime
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.action, WakeAction):
            try:
                self.action = WakeAction(self.action)
            except ValueError as exc:
                raise AwakeningValidationError("unsupported wake action") from exc
        _require_text(self.reason, "wake decision reason")
        if self.decided_at.tzinfo is None:
            raise AwakeningValidationError("decided_at must include a timezone")
        self.evidence = _text_list(self.evidence, "wake decision evidence")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "decided_at": _format_datetime(self.decided_at),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: Any) -> WakeDecision:
        if not isinstance(value, dict):
            raise AwakeningValidationError("wake decision must be an object")
        decided_at = _parse_datetime(value.get("decided_at"), "decision.decided_at")
        assert decided_at is not None
        return cls(
            action=value.get("action"),
            reason=value.get("reason"),
            decided_at=decided_at,
            evidence=_text_list(value.get("evidence", []), "wake decision evidence"),
        )


@dataclass(slots=True)
class WakeObservationLog:
    context_id: str | None = None
    state_revision: int | None = None
    event_ids: list[str] = field(default_factory=list)
    update_ids: list[str] = field(default_factory=list)
    memory_request_id: str | None = None
    viewed_memory_ids: list[str] = field(default_factory=list)
    selected_memory_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_context(cls, context: WakeContext) -> WakeObservationLog:
        return cls(
            context_id=context.context_id,
            state_revision=context.subject_state.revision,
            event_ids=[event.event_id for event in context.recent_events],
            update_ids=[update.update_id for update in context.recent_updates],
            memory_request_id=context.memory_result.request.request_id,
            viewed_memory_ids=[
                decision.candidate.memory_id for decision in context.memory_result.decisions
            ],
            selected_memory_ids=[
                candidate.memory_id for candidate in context.memory_result.selected_memories
            ],
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "context_id": self.context_id,
            "state_revision": self.state_revision,
            "event_ids": list(self.event_ids),
            "update_ids": list(self.update_ids),
            "memory_request_id": self.memory_request_id,
            "viewed_memory_ids": list(self.viewed_memory_ids),
            "selected_memory_ids": list(self.selected_memory_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> WakeObservationLog:
        if not isinstance(value, dict):
            raise AwakeningValidationError("wake observation log must be an object")
        revision = value.get("state_revision")
        if revision is not None and (not isinstance(revision, int) or revision < 0):
            raise AwakeningValidationError("observation state_revision is invalid")
        return cls(
            context_id=value.get("context_id"),
            state_revision=revision,
            event_ids=_text_list(value.get("event_ids", []), "observation event_ids"),
            update_ids=_text_list(value.get("update_ids", []), "observation update_ids"),
            memory_request_id=value.get("memory_request_id"),
            viewed_memory_ids=_text_list(
                value.get("viewed_memory_ids", []), "observation viewed_memory_ids"
            ),
            selected_memory_ids=_text_list(
                value.get("selected_memory_ids", []), "observation selected_memory_ids"
            ),
        )


@dataclass(slots=True)
class WakeSession:
    session_id: str
    cycle_id: str
    subject_id: str
    wake_reason: WakeReason
    wake_reason_detail: str
    wake_time: datetime
    source_event_id: str | None = None
    subject_revision: int | None = None
    completed_at: datetime | None = None
    completed_successfully: bool | None = None
    decision: WakeDecision | None = None
    observation: WakeObservationLog = field(default_factory=WakeObservationLog)
    error: str | None = None
    recovery_context: WakeContext | None = None

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")
        _require_text(self.cycle_id, "session.cycle_id")
        _require_text(self.subject_id, "session.subject_id")
        if not isinstance(self.wake_reason, WakeReason):
            self.wake_reason = WakeReason(self.wake_reason)
        _require_text(self.wake_reason_detail, "wake_reason_detail")
        if self.wake_time.tzinfo is None:
            raise AwakeningValidationError("wake_time must include a timezone")
        if self.subject_revision is not None and self.subject_revision < 0:
            raise AwakeningValidationError("subject_revision cannot be negative")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise AwakeningValidationError("completed_at must include a timezone")
        if self.completed_successfully is not None and not isinstance(
            self.completed_successfully, bool
        ):
            raise AwakeningValidationError("completed_successfully must be boolean or null")
        if self.completed_successfully is None:
            if (
                self.completed_at is not None
                or self.decision is not None
                or self.recovery_context is not None
                or self.error is not None
            ):
                raise AwakeningValidationError(
                    "a running wake session cannot contain completion fields"
                )
        else:
            if self.completed_at is None or self.decision is None:
                raise AwakeningValidationError(
                    "a finalized wake session requires completed_at and decision"
                )
            if self.completed_successfully and self.error is not None:
                raise AwakeningValidationError("a successful wake session cannot contain an error")
            if not self.completed_successfully and self.recovery_context is not None:
                raise AwakeningValidationError(
                    "a failed wake session cannot contain a recovery context"
                )
            if not self.completed_successfully:
                _require_text(self.error, "wake session error")
        if self.recovery_context is not None:
            if self.recovery_context.subject_state.subject_id != self.subject_id:
                raise AwakeningValidationError(
                    "wake recovery context belongs to a different subject"
                )
            if self.recovery_context.context_id != self.observation.context_id:
                raise AwakeningValidationError(
                    "wake recovery context does not match the observation log"
                )

    @classmethod
    def start(
        cls,
        cycle: AwakeCycle,
        trigger: WakeTrigger,
        *,
        session_id: str | None = None,
    ) -> WakeSession:
        return cls(
            session_id=session_id or str(uuid4()),
            cycle_id=cycle.cycle_id,
            subject_id=cycle.subject_id,
            wake_reason=trigger.reason,
            wake_reason_detail=trigger.detail,
            wake_time=trigger.triggered_at,
            source_event_id=trigger.source_event_id,
        )

    def complete(
        self,
        *,
        context: WakeContext,
        decision: WakeDecision,
        completed_at: datetime,
        retain_recovery_context: bool = False,
    ) -> None:
        if context.subject_state.subject_id != self.subject_id:
            raise AwakeningValidationError("WakeContext subject does not match WakeSession")
        if completed_at.tzinfo is None:
            raise AwakeningValidationError("completed_at must include a timezone")
        self.subject_revision = context.subject_state.revision
        self.observation = WakeObservationLog.from_context(context)
        self.recovery_context = (
            WakeContext.from_dict(context.to_dict())
            if retain_recovery_context
            else None
        )
        self.decision = decision
        self.completed_at = completed_at
        self.completed_successfully = True
        self.error = None

    def fail(
        self,
        *,
        decision: WakeDecision,
        completed_at: datetime,
        error: str,
        subject_revision: int | None = None,
        observation: WakeObservationLog | None = None,
    ) -> None:
        if completed_at.tzinfo is None:
            raise AwakeningValidationError("completed_at must include a timezone")
        self.subject_revision = subject_revision
        if observation is not None:
            self.observation = observation
        self.decision = decision
        self.completed_at = completed_at
        self.completed_successfully = False
        self.recovery_context = None
        self.error = _require_text(error, "wake session error")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "session_id": self.session_id,
            "cycle_id": self.cycle_id,
            "subject_id": self.subject_id,
            "wake_reason": self.wake_reason.value,
            "wake_reason_detail": self.wake_reason_detail,
            "wake_time": _format_datetime(self.wake_time),
            "source_event_id": self.source_event_id,
            "subject_revision": self.subject_revision,
            "completed_at": _format_datetime(self.completed_at),
            "completed_successfully": self.completed_successfully,
            "decision": self.decision.to_dict() if self.decision else None,
            "observation": self.observation.to_dict(),
            "recovery_context": (
                self.recovery_context.to_dict()
                if self.recovery_context is not None
                else None
            ),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WakeSession:
        if not isinstance(value, dict):
            raise AwakeningValidationError("wake session must be an object")
        wake_time = _parse_datetime(value.get("wake_time"), "session.wake_time")
        assert wake_time is not None
        decision = value.get("decision")
        recovery_context = value.get("recovery_context")
        return cls(
            session_id=value.get("session_id"),
            cycle_id=value.get("cycle_id"),
            subject_id=value.get("subject_id"),
            wake_reason=value.get("wake_reason"),
            wake_reason_detail=value.get("wake_reason_detail"),
            wake_time=wake_time,
            source_event_id=value.get("source_event_id"),
            subject_revision=value.get("subject_revision"),
            completed_at=_parse_datetime(
                value.get("completed_at"), "session.completed_at", optional=True
            ),
            completed_successfully=value.get("completed_successfully"),
            decision=WakeDecision.from_dict(decision) if decision is not None else None,
            observation=WakeObservationLog.from_dict(value.get("observation", {})),
            recovery_context=(
                WakeContext.from_dict(recovery_context)
                if recovery_context is not None
                else None
            ),
            error=value.get("error"),
        )


@dataclass(slots=True)
class AwakeningResult:
    context: WakeContext
    session: WakeSession
