from .models import (
    APIResponse,
    ActionPlanAPIRequest,
    MemoryAPIRequest,
    PerceptionAPIRequest,
    SubjectStateAPIRequest,
    ThinkingAPIRequest,
)
from .ports import ContinuityAPI


class ContinuityMCPAdapter:
    """MCP-shaped tool facade without an MCP transport or SDK dependency."""

    TOOL_NAMES = (
        "get_subject_state",
        "query_memory",
        "get_perception",
        "request_thinking",
        "get_action_plan",
    )

    def __init__(self, api: ContinuityAPI) -> None:
        self._api = api

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

