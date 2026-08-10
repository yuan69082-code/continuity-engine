from __future__ import annotations

from typing import Any

from continuity_engine.domain.capability import CapabilityRequest, CapabilityResult
from continuity_engine.interfaces.capability_schema import (
    CAPABILITY_REQUEST_SCHEMA_ID,
    CAPABILITY_RESULT_SCHEMA_ID,
    DEFAULT_CAPABILITY_SCHEMA_REGISTRY,
    CapabilitySchemaRegistry,
)


class CapabilityContractValidator:
    """Validate untrusted capability documents with a closed schema registry."""

    def __init__(
        self,
        registry: CapabilitySchemaRegistry = DEFAULT_CAPABILITY_SCHEMA_REGISTRY,
    ) -> None:
        self._registry = registry

    @property
    def schema_registry(self) -> CapabilitySchemaRegistry:
        return self._registry

    def validate_request(self, payload: Any) -> CapabilityRequest:
        self._registry.validate(CAPABILITY_REQUEST_SCHEMA_ID, payload)
        return CapabilityRequest.from_dict(payload)

    def validate_result(self, payload: Any) -> CapabilityResult:
        self._registry.validate(CAPABILITY_RESULT_SCHEMA_ID, payload)
        return CapabilityResult.from_dict(payload)
