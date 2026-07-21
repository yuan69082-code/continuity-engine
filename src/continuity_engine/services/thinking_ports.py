from typing import Protocol

from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.resources import TokenUsageRecord
from continuity_engine.domain.thinking import ThinkingResult, TokenBudget, TokenBudgetRequest


class ThinkingProvider(Protocol):
    """Pluggable thinking executor implemented by a future model adapter."""

    @property
    def provider_id(self) -> str: ...

    def think(
        self,
        perception: PerceptionResult,
        budget: TokenBudget,
    ) -> ThinkingResult: ...


class TokenBudgetManager(Protocol):
    """Token allocation and usage accounting boundary."""

    def allocate(self, request: TokenBudgetRequest) -> TokenBudget: ...

    def record_usage(self, think_id: str, actual_tokens: int) -> TokenUsageRecord: ...
