from typing import Protocol, runtime_checkable

from .models import (
    APIResponse,
    ActionPlanAPIRequest,
    MemoryAPIRequest,
    PerceptionAPIRequest,
    SubjectStateAPIRequest,
    ThinkingAPIRequest,
    WakeAPIRequest,
)
from .ports import ContinuityAPI


@runtime_checkable
class SkillAdapter(Protocol):
    """Platform-neutral contract for a future agent skill implementation."""

    @property
    def platform_id(self) -> str: ...

    def get_subject_state(self, request: SubjectStateAPIRequest) -> APIResponse: ...

    def query_memory(self, request: MemoryAPIRequest) -> APIResponse: ...

    def get_perception(self, request: PerceptionAPIRequest) -> APIResponse: ...

    def request_thinking(self, request: ThinkingAPIRequest) -> APIResponse: ...

    def get_action_plan(self, request: ActionPlanAPIRequest) -> APIResponse: ...

    def trigger_manual_wake(self, request: WakeAPIRequest) -> APIResponse: ...


class APIBackedSkillAdapter:
    """Generic delegation base; it contains no platform-specific behavior."""

    def __init__(self, platform_id: str, api: ContinuityAPI) -> None:
        if not isinstance(platform_id, str) or not platform_id.strip():
            raise ValueError("platform_id must be a non-empty string")
        self._platform_id = platform_id
        self._api = api

    @property
    def platform_id(self) -> str:
        return self._platform_id

    def get_subject_state(self, request: SubjectStateAPIRequest) -> APIResponse:
        return self._api.get_subject_state(request)

    def query_memory(self, request: MemoryAPIRequest) -> APIResponse:
        return self._api.query_memory(request)

    def get_perception(self, request: PerceptionAPIRequest) -> APIResponse:
        return self._api.get_perception(request)

    def request_thinking(self, request: ThinkingAPIRequest) -> APIResponse:
        return self._api.request_thinking(request)

    def get_action_plan(self, request: ActionPlanAPIRequest) -> APIResponse:
        return self._api.get_action_plan(request)

    def trigger_manual_wake(self, request: WakeAPIRequest) -> APIResponse:
        return self._api.trigger_manual_wake(request)

