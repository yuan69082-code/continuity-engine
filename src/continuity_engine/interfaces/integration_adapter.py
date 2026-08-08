from __future__ import annotations

from typing import Any

from continuity_engine.domain.integration_results import (
    FirstRoundErrorEnvelope,
    FirstRoundSuccessResult,
    IntegrationRequestQueryResult,
)
from continuity_engine.services.continuity_interaction_service import (
    ContinuityInteractionService,
)


class IntegrationAdapter:
    """Formal in-process boundary; HTTP concerns deliberately stay outside."""

    def __init__(self, service: ContinuityInteractionService) -> None:
        self._service = service

    @property
    def service(self) -> ContinuityInteractionService:
        return self._service

    def submit(self, payload: Any) -> FirstRoundSuccessResult | FirstRoundErrorEnvelope:
        return self._service.submit(payload)

    def query_request(self, request_id: str) -> IntegrationRequestQueryResult | None:
        return self._service.query_request(request_id)
