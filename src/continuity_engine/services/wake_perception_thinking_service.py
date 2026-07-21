"""Compatibility facade; all state changes still pass through Action Engine."""

from datetime import datetime, timezone

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    WakePerceptionThinkingResult,
)
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)

from .action_permissions import InMemoryPermissionProvider
from .action_service import ActionService
from .awakening_service import AwakeningService
from .perception_service import PerceptionService
from .thinking_service import ThinkingService
from .wake_perception_thinking_action_service import (
    WakePerceptionThinkingActionService,
)


_INTERNAL_PERMISSIONS = (
    "subject_state:update",
    "memory:request",
    "thinking:request",
)


class WakePerceptionThinkingService:
    """Backward-compatible entry point backed by the stage-seven action gate."""

    def __init__(
        self,
        awakening: AwakeningService,
        perception: PerceptionService,
        thinking: ThinkingService,
        *,
        clock=None,
    ) -> None:
        effective_clock = clock or thinking.clock
        valid_from = datetime.min.replace(tzinfo=timezone.utc)
        permissions = InMemoryPermissionProvider(
            PermissionGrant(
                permission=name,
                subject_id="*",
                valid_from=valid_from,
            )
            for name in _INTERNAL_PERMISSIONS
        )
        action = ActionService(permissions, InMemoryActionRepository())
        self._delegate = WakePerceptionThinkingActionService(
            awakening,
            perception,
            thinking,
            action,
            thinking.subject_states,
            available_permissions=_INTERNAL_PERMISSIONS,
            clock=effective_clock,
        )

    def wake_manual(
        self,
        cycle_id: str,
        *,
        detail: str,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingResult:
        return self._legacy(
            self._delegate.wake_manual(cycle_id, detail=detail, depth=depth)
        )

    def wake_scheduled(
        self,
        cycle_id: str,
        *,
        detail: str = "The scheduled wake time was reached.",
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingResult:
        return self._legacy(
            self._delegate.wake_scheduled(cycle_id, detail=detail, depth=depth)
        )

    def wake_for_event(
        self,
        cycle_id: str,
        *,
        source_event_id: str,
        detail: str,
        depth: ThinkingDepth = ThinkingDepth.NORMAL,
    ) -> WakePerceptionThinkingResult:
        return self._legacy(
            self._delegate.wake_for_event(
                cycle_id,
                source_event_id=source_event_id,
                detail=detail,
                depth=depth,
            )
        )

    @staticmethod
    def _legacy(result) -> WakePerceptionThinkingResult:
        return WakePerceptionThinkingResult(
            awakening=result.awakening,
            perception=result.perception,
            thinking=result.thinking,
        )
