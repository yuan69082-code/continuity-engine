from __future__ import annotations

from typing import Protocol

from continuity_engine.domain.capability import (
    CapabilityAttempt,
    CapabilityRequest,
    CapabilityResult,
)
from continuity_engine.domain.action_capability import (
    InternalActionRequest, InternalActionResult, InternalActionAttempt,
)


class CapabilityRepository(Protocol):
    """Persistence port tied to the integration operation journal."""

    def save_capability_request(self, request: CapabilityRequest | InternalActionRequest) -> None: ...

    def load_capability_request(
        self,
        capability_request_id: str,
    ) -> CapabilityRequest | InternalActionRequest | None: ...

    def find_capability_request_by_operation(
        self,
        operation_id: str,
    ) -> CapabilityRequest | InternalActionRequest | None: ...

    def save_capability_result(
        self,
        result: CapabilityResult | InternalActionResult,
        *,
        received_at: str,
    ) -> CapabilityAttempt | InternalActionAttempt: ...

    def list_capability_attempts(
        self,
        capability_request_id: str,
    ) -> list[CapabilityAttempt | InternalActionAttempt]: ...
