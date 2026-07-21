from typing import Protocol

from continuity_engine.domain.action import ActionSession
from continuity_engine.domain.perception import PerceptionResult

from .models import (
    APIResponse,
    ActionPlanAPIRequest,
    ChatAPIRequest,
    MemoryAPIRequest,
    PerceptionAPIRequest,
    SubjectStateAPIRequest,
    ThinkingAPIRequest,
    WakeAPIRequest,
)


class PerceptionResultProvider(Protocol):
    """Read-only port supplying the latest assembled perception snapshot."""

    def get_current_perception(self, subject_id: str) -> PerceptionResult: ...


class ActionSessionProvider(Protocol):
    """Read-only port supplying the latest audited ActionSession."""

    def get_latest_action_session(self, subject_id: str) -> ActionSession | None: ...


class ContinuityAPI(Protocol):
    """Stable facade consumed by protocol and platform adapters."""

    def get_subject_state(self, request: SubjectStateAPIRequest) -> APIResponse: ...

    def submit_message(self, request: ChatAPIRequest) -> APIResponse: ...

    def query_memory(self, request: MemoryAPIRequest) -> APIResponse: ...

    def get_perception(self, request: PerceptionAPIRequest) -> APIResponse: ...

    def request_thinking(self, request: ThinkingAPIRequest) -> APIResponse: ...

    def get_action_plan(self, request: ActionPlanAPIRequest) -> APIResponse: ...

    def trigger_manual_wake(self, request: WakeAPIRequest) -> APIResponse: ...
