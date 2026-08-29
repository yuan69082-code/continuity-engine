from __future__ import annotations

from typing import Protocol

from continuity_engine.domain.model_provider import (
    ModelExecutionRecord,
    ModelExecutionRequest,
    ModelUsageEntry,
    ProviderExecutionFact,
    ProviderModelProfile,
    ProviderQueryResult,
)


class ModelProvider(Protocol):
    """Host-neutral execution boundary; it has no SubjectState authority."""

    def execute(self, request: ModelExecutionRequest) -> ProviderExecutionFact: ...

    def query(self, request: ModelExecutionRequest) -> ProviderQueryResult: ...


class ModelProfilePolicy(Protocol):
    """Select one configured provider/model profile without fallback surprises."""

    def select(self) -> ProviderModelProfile: ...


class ModelExecutionRepository(Protocol):
    """Durable P02 execution and synthetic usage/test-credit facts."""

    def ensure_initialized(self) -> None: ...

    def ensure_execution(self, record: ModelExecutionRecord) -> ModelExecutionRecord: ...

    def load_execution(self, capability_request_id: str) -> ModelExecutionRecord | None: ...

    def save_execution(self, record: ModelExecutionRecord) -> None: ...

    def list_executions(self) -> list[ModelExecutionRecord]: ...

    def save_usage(self, entry: ModelUsageEntry) -> None: ...

    def list_usage(self) -> list[ModelUsageEntry]: ...
