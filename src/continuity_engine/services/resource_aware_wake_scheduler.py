from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from continuity_engine.domain.awakening import (
    AwakeMode,
    AwakeningResult,
)
from continuity_engine.domain.errors import (
    AwakeningValidationError,
    WakeNotDueError,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.resources import ResourceAllocation

from .awakening_service import AwakeningService
from .resource_manager import ResourceManager


@dataclass(slots=True)
class WakeScheduleResult:
    resources: ResourceAllocation
    awakening: AwakeningResult | None

    @property
    def deferred(self) -> bool:
        return self.resources.decision.defer


class ResourceAwareWakeScheduler:
    """Attempt one wake only after ResourceManager approval.

    It intentionally does not create a background loop or continuous runner.
    """

    def __init__(
        self,
        awakening: AwakeningService,
        resources: ResourceManager,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._awakening = awakening
        self._resources = resources
        self._clock = clock

    def wake_scheduled(
        self,
        cycle_id: str,
        *,
        detail: str = "The scheduled wake time was reached.",
    ) -> WakeScheduleResult:
        cycle = self._awakening.get_cycle(cycle_id)
        now = self._clock()
        if cycle.mode is not AwakeMode.SCHEDULED:
            raise AwakeningValidationError(
                "resource-aware scheduled wake requires a scheduled cycle"
            )
        if not cycle.is_due(now):
            raise WakeNotDueError(f"awake cycle is not due: {cycle_id}")
        session_id = str(uuid4())
        allocation = self._resources.request_wake(
            cycle.subject_id,
            session_id,
            reason=f"Evaluate scheduled wake cycle {cycle_id}.",
        )
        if allocation.decision.defer:
            return WakeScheduleResult(resources=allocation, awakening=None)
        awakening = self._awakening.wake_scheduled(
            cycle_id,
            detail=detail,
            session_id=session_id,
        )
        return WakeScheduleResult(resources=allocation, awakening=awakening)

    def wake_manual(self, cycle_id: str, *, detail: str) -> WakeScheduleResult:
        cycle = self._awakening.get_cycle(cycle_id)
        if cycle.mode is not AwakeMode.MANUAL:
            raise AwakeningValidationError(
                "resource-aware manual wake requires a manual cycle"
            )
        if not cycle.enabled:
            raise AwakeningValidationError("awake cycle is disabled")
        session_id = str(uuid4())
        allocation = self._resources.request_wake(
            cycle.subject_id,
            session_id,
            reason=f"Evaluate manual wake cycle {cycle_id}.",
        )
        if allocation.decision.defer:
            return WakeScheduleResult(resources=allocation, awakening=None)
        awakening = self._awakening.wake_manual(
            cycle_id,
            detail=detail,
            session_id=session_id,
        )
        return WakeScheduleResult(resources=allocation, awakening=awakening)


WakeScheduler = ResourceAwareWakeScheduler
