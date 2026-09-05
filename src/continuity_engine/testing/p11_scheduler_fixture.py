from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from continuity_engine.domain.awakening import AwakeCycle
from continuity_engine.domain.errors import ResourceNotFoundError, StateNotFoundError
from continuity_engine.domain.scheduling import (
    NotificationReceipt,
    NotificationRequest,
    NotificationStatus,
    QuietHours,
    SchedulerTask,
    SchedulerWakeReason,
)
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.resource_aware_wake_scheduler import ResourceAwareWakeScheduler
from continuity_engine.services.scheduler_service import SchedulerService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_scheduler_repository import JsonSchedulerRepository

from .persistence import (
    SandboxFrozenClock,
    assert_no_link_components,
    atomic_write_json,
    read_json,
)
from .p08_action_fixture import _validate_fixture_root


P11_GOLDEN_SCENARIO_VERSION = "p11-golden-v1"


class SimulatedSchedulerProcessCrash(BaseException):
    """TEST-only hard interruption that ordinary Adapter handling cannot swallow."""


class _EmptyMemoryRetriever:
    def retrieve(self, request: Any) -> list[Any]:
        return []


class _DiscardingInfluenceRecorder:
    def record_influence(self, record: Any) -> None:
        return None


class P11TestResourceRepository(JsonResourceRepository):
    def path_for_test(self, subject_id: str) -> Path:
        return self._path(subject_id)


class FakeNotificationAdapter:
    """Persistent, deterministic TEST receipt authority with zero external I/O."""

    FORMAT_VERSION = 1

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime],
        on_delivered: Callable[[NotificationRequest], None] | None = None,
    ) -> None:
        self.path = path
        self._clock = clock
        self._on_delivered = on_delivered
        self._dispatch_script: list[NotificationStatus] = []
        self._query_script: list[NotificationStatus] = []
        self.dispatch_count = 0
        self.query_count = 0
        self.dispatch_requests: list[NotificationRequest] = []
        self.query_requests: list[NotificationRequest] = []
        self.raise_on_query = False
        self.crash_after_effect_once = False
        self.conflict_on_dispatch = False
        self.conflict_on_query = False

    def queue_dispatch(self, *statuses: NotificationStatus | str) -> None:
        self._dispatch_script.extend(NotificationStatus(item) for item in statuses)

    def queue_query(self, *statuses: NotificationStatus | str) -> None:
        self._query_script.extend(NotificationStatus(item) for item in statuses)

    def dispatch(self, request: NotificationRequest) -> NotificationReceipt:
        self.dispatch_count += 1
        self.dispatch_requests.append(request)
        document = self._load()
        stored = document["attempts"].get(request.attempt_id)
        if stored is not None:
            receipt = self._receipt_from_dict(stored)
            return self._conflict(receipt) if self.conflict_on_dispatch else receipt
        status = self._dispatch_script.pop(0) if self._dispatch_script else NotificationStatus.DELIVERED
        receipt = self._make_receipt(request, status, "FAKE_DISPATCH_RESULT")
        if status is NotificationStatus.DELIVERED and self._on_delivered is not None:
            self._on_delivered(request)
        document["attempts"][request.attempt_id] = self._receipt_to_dict(receipt)
        self._save(document)
        if self.crash_after_effect_once:
            self.crash_after_effect_once = False
            raise SimulatedSchedulerProcessCrash("simulated crash after effect")
        return self._conflict(receipt) if self.conflict_on_dispatch else receipt

    def query(self, request: NotificationRequest) -> NotificationReceipt:
        self.query_count += 1
        self.query_requests.append(request)
        if self.raise_on_query:
            raise RuntimeError("simulated receipt query outage")
        document = self._load()
        stored = document["attempts"].get(request.attempt_id)
        if self._query_script:
            status = self._query_script.pop(0)
            receipt = self._make_receipt(request, status, "FAKE_QUERY_RESULT")
            prior_status = (
                NotificationStatus(stored["status"])
                if isinstance(stored, dict) and "status" in stored
                else None
            )
            if (
                status is NotificationStatus.DELIVERED
                and prior_status is not NotificationStatus.DELIVERED
                and self._on_delivered is not None
            ):
                self._on_delivered(request)
            document["attempts"][request.attempt_id] = self._receipt_to_dict(receipt)
            self._save(document)
        elif stored is not None:
            receipt = self._receipt_from_dict(stored)
        else:
            receipt = self._make_receipt(request, NotificationStatus.UNKNOWN, "FAKE_QUERY_MISSING")
        return self._conflict(receipt) if self.conflict_on_query else receipt

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "formatVersion": self.FORMAT_VERSION,
                "environment": "TEST",
                "synthetic": True,
                "attempts": {},
            }
        value = read_json(self.path)
        if (
            value.get("formatVersion") != self.FORMAT_VERSION
            or value.get("environment") != "TEST"
            or value.get("synthetic") is not True
            or not isinstance(value.get("attempts"), dict)
        ):
            raise RuntimeError("invalid Fake Notification Adapter data")
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_json(self.path, value)

    def _make_receipt(
        self, request: NotificationRequest, status: NotificationStatus, reason_code: str
    ) -> NotificationReceipt:
        raw = f"p11-fake-receipt\0{request.attempt_id}\0{status.value}".encode("utf-8")
        return NotificationReceipt(
            receipt_id="p11-receipt-" + hashlib.sha256(raw).hexdigest(),
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            subject_id=request.subject_id,
            environment=request.environment,
            status=status,
            observed_at=self._clock(),
            reason_code=reason_code,
        )

    @staticmethod
    def _receipt_to_dict(receipt: NotificationReceipt) -> dict[str, Any]:
        return {
            "receipt_id": receipt.receipt_id,
            "task_id": receipt.task_id,
            "attempt_id": receipt.attempt_id,
            "subject_id": receipt.subject_id,
            "environment": receipt.environment,
            "status": receipt.status.value,
            "observed_at": receipt.observed_at.isoformat(),
            "reason_code": receipt.reason_code,
        }

    @staticmethod
    def _receipt_from_dict(value: dict[str, Any]) -> NotificationReceipt:
        return NotificationReceipt(
            receipt_id=value.get("receipt_id"),
            task_id=value.get("task_id"),
            attempt_id=value.get("attempt_id"),
            subject_id=value.get("subject_id"),
            environment=value.get("environment"),
            status=value.get("status"),
            observed_at=datetime.fromisoformat(value.get("observed_at")),
            reason_code=value.get("reason_code"),
        )

    @staticmethod
    def _conflict(receipt: NotificationReceipt) -> NotificationReceipt:
        return NotificationReceipt(
            receipt_id=receipt.receipt_id,
            task_id=receipt.task_id + "-conflict",
            attempt_id=receipt.attempt_id,
            subject_id=receipt.subject_id,
            environment=receipt.environment,
            status=receipt.status,
            observed_at=receipt.observed_at,
            reason_code=receipt.reason_code,
        )


@dataclass(slots=True)
class P11SchedulerFixture:
    root: Path
    subject_id: str
    cycle_id: str
    scheduled_cycle_id: str
    clock: SandboxFrozenClock
    repository: JsonSchedulerRepository
    resource_repository: P11TestResourceRepository
    resource_manager: ResourceManager
    adapter: FakeNotificationAdapter
    service: SchedulerService
    awakening_repository: JsonAwakeningRepository
    awakening_service: AwakeningService | None
    capacity: int
    aging_interval_seconds: int
    retry_base_seconds: int
    quiet_hours: QuietHours | None
    enable_awakening: bool

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        frozen_at: datetime,
        subject_id: str = "p11-subject",
        capacity: int = 128,
        aging_interval_seconds: int = 60,
        retry_base_seconds: int = 30,
        quiet_hours: QuietHours | None = None,
        token_budget: int = 10_000,
        compute_budget: int = 1_000,
        enable_awakening: bool = False,
        formal_data_roots: tuple[Path | str, ...] = (),
        protected_paths: tuple[Path | str, ...] = (),
    ) -> P11SchedulerFixture:
        base = _validate_fixture_root(
            Path(root),
            formal_data_roots=formal_data_roots,
            protected_paths=protected_paths,
        )
        temp_root = Path(tempfile.gettempdir()).resolve()
        for target in (
            base / "test-scheduler",
            base / "scheduler",
            base / "resources",
            base / "awakening",
        ):
            assert_no_link_components(target, stop_at=temp_root)
        base.mkdir(parents=True, exist_ok=True)
        clock_path = base / "test-scheduler" / "clock.v1.json"
        clock = SandboxFrozenClock(clock_path)
        if not clock_path.exists():
            clock = SandboxFrozenClock.create(clock_path, frozen_at)

        resource_repository = P11TestResourceRepository(base)
        resource_manager = ResourceManager(resource_repository, clock=clock.now)
        try:
            resource_manager.get_resource_state(subject_id)
        except ResourceNotFoundError:
            resource_manager.create_resource_state(
                subject_id,
                token_budget=token_budget,
                compute_budget=compute_budget,
            )

        awakening_repository = JsonAwakeningRepository(base)
        awakening_service: AwakeningService | None = None
        cycle_id = "p11-cycle"
        scheduled_cycle_id = "p11-scheduled-cycle"
        if enable_awakening:
            states = SubjectStateService(JsonSubjectStateRepository(base), clock=clock.now)
            try:
                states.load(subject_id)
            except StateNotFoundError:
                states.create(subject_id)
            memory = MemoryService(
                _EmptyMemoryRetriever(), _DiscardingInfluenceRecorder(), clock=clock.now
            )
            awakening_service = AwakeningService(
                states, memory, awakening_repository, clock=clock.now
            )
            try:
                awakening_repository.load_cycle(cycle_id)
            except StateNotFoundError:
                awakening_repository.save_cycle(
                    AwakeCycle.manual(
                        cycle_id=cycle_id, subject_id=subject_id, created_at=clock.now()
                    )
                )
            try:
                awakening_repository.load_cycle(scheduled_cycle_id)
            except StateNotFoundError:
                awakening_repository.save_cycle(
                    AwakeCycle.scheduled(
                        cycle_id=scheduled_cycle_id,
                        subject_id=subject_id,
                        created_at=clock.now(),
                        interval_seconds=300,
                        first_wake_at=clock.now(),
                    )
                )

        def on_delivered(request: NotificationRequest) -> None:
            if awakening_service is None:
                return
            try:
                awakening_repository.load_session(subject_id, request.attempt_id)
                return
            except StateNotFoundError:
                pass
            wake_scheduler = ResourceAwareWakeScheduler(
                awakening_service, resource_manager, clock=clock.now
            )
            if request.wake_reason is SchedulerWakeReason.EVENT:
                result = wake_scheduler.wake_for_event(
                    request.cycle_id,
                    source_event_id=request.source_event_id or "missing-event",
                    detail="P11 scheduled one event computation opportunity.",
                    session_id=request.attempt_id,
                )
            elif request.wake_reason is SchedulerWakeReason.SCHEDULED:
                result = wake_scheduler.wake_scheduled(
                    request.cycle_id,
                    detail="P11 released one due scheduled computation opportunity.",
                    session_id=request.attempt_id,
                )
            else:
                result = wake_scheduler.wake_manual(
                    request.cycle_id,
                    detail="P11 scheduled one internal computation opportunity.",
                    session_id=request.attempt_id,
                )
            if result.deferred:
                raise RuntimeError("resource state changed after scheduler preview")

        repository = JsonSchedulerRepository(base)
        adapter = FakeNotificationAdapter(
            base / "test-scheduler" / "fake-notification-ledger.v1.json",
            clock=clock.now,
            on_delivered=on_delivered,
        )
        service = SchedulerService(
            repository,
            adapter,
            resource_manager,
            clock=clock.now,
            capacity=capacity,
            aging_interval_seconds=aging_interval_seconds,
            retry_base_seconds=retry_base_seconds,
            quiet_hours=quiet_hours,
        )
        return cls(
            root=base,
            subject_id=subject_id,
            cycle_id=cycle_id,
            scheduled_cycle_id=scheduled_cycle_id,
            clock=clock,
            repository=repository,
            resource_repository=resource_repository,
            resource_manager=resource_manager,
            adapter=adapter,
            service=service,
            awakening_repository=awakening_repository,
            awakening_service=awakening_service,
            capacity=capacity,
            aging_interval_seconds=aging_interval_seconds,
            retry_base_seconds=retry_base_seconds,
            quiet_hours=quiet_hours,
            enable_awakening=enable_awakening,
        )

    def restart(self) -> P11SchedulerFixture:
        state = self.resource_manager.get_resource_state(self.subject_id)
        return self.create(
            self.root,
            frozen_at=self.clock.now(),
            subject_id=self.subject_id,
            capacity=self.capacity,
            aging_interval_seconds=self.aging_interval_seconds,
            retry_base_seconds=self.retry_base_seconds,
            quiet_hours=self.quiet_hours,
            token_budget=state.token_budget,
            compute_budget=state.compute_budget,
            enable_awakening=self.enable_awakening,
        )

    def create_task(
        self,
        *,
        task_id: str,
        priority: int = 10,
        due_at: datetime | None = None,
        wake_reason: SchedulerWakeReason | str = SchedulerWakeReason.INTERNAL,
        source_event_id: str | None = None,
        max_attempts: int = 3,
    ) -> SchedulerTask:
        normalized_reason = SchedulerWakeReason(wake_reason)
        return SchedulerTask.create(
            task_id=task_id,
            subject_id=self.subject_id,
            environment="TEST",
            priority=priority,
            due_at=due_at or self.clock.now(),
            wake_reason=normalized_reason,
            cycle_id=(
                self.scheduled_cycle_id
                if normalized_reason is SchedulerWakeReason.SCHEDULED
                else self.cycle_id
            ),
            source_event_id=source_event_id,
            created_at=self.clock.now(),
            max_attempts=max_attempts,
        )

    @property
    def wake_count(self) -> int:
        return len(self.awakening_repository.list_sessions(self.subject_id))


@dataclass(frozen=True, slots=True)
class P11GoldenScenarioResult:
    version: str
    completed_task_ids: tuple[str, ...]
    dispatch_count: int
    wake_session_count: int
    model_call_count: int
    action_call_count: int
    canonical_result_hash: str


def run_p11_golden_scenario(root: Path | str) -> P11GoldenScenarioResult:
    start = datetime.fromisoformat("2026-09-05T08:00:00+00:00")
    fixture = P11SchedulerFixture.create(root, frozen_at=start, enable_awakening=True)
    fixture.service.submit(
        fixture.create_task(
            task_id="event-priority",
            priority=100,
            wake_reason=SchedulerWakeReason.EVENT,
            source_event_id="golden-event",
        )
    )
    fixture.service.submit(
        fixture.create_task(task_id="internal-aged", priority=0)
    )
    first = fixture.service.tick(fixture.subject_id, "TEST")
    fixture.clock.advance(timedelta(seconds=101))
    second = fixture.service.tick(fixture.subject_id, "TEST")
    completed = (first.task.task_id, second.task.task_id)  # type: ignore[union-attr]
    stable = {
        "version": P11_GOLDEN_SCENARIO_VERSION,
        "completedTaskIds": completed,
        "dispatchCount": fixture.adapter.dispatch_count,
        "wakeSessionCount": fixture.wake_count,
        "modelCallCount": 0,
        "actionCallCount": 0,
    }
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return P11GoldenScenarioResult(
        version=P11_GOLDEN_SCENARIO_VERSION,
        completed_task_ids=completed,
        dispatch_count=fixture.adapter.dispatch_count,
        wake_session_count=fixture.wake_count,
        model_call_count=0,
        action_call_count=0,
        canonical_result_hash="sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
