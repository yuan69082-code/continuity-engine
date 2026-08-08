from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from continuity_engine.domain.action import ActionExecutionResult, ActionType
from continuity_engine.domain.events import ChangeOperation, StateMutation, StateSection
from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryInfluenceRecord,
    MemoryRetrievalRequest,
)
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.resources import ResourceSessionType, TokenUsageRecord
from continuity_engine.domain.thinking import (
    ThinkingExecutionResult,
    ThinkingResult,
    TokenBudget,
    TokenBudgetRequest,
)


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeterministicMemoryRetriever:
    """Return fixed local context without external storage or network access."""

    def __init__(self, *, trace: Callable[[str], None] | None = None) -> None:
        self.call_count = 0
        self._trace = trace

    def retrieve(self, request: MemoryRetrievalRequest) -> Sequence[MemoryCandidate]:
        self.call_count += 1
        if self._trace is not None:
            self._trace("memory")
        return (
            MemoryCandidate(
                memory_id="first-round-memory-001",
                subject_id=request.subject_id,
                content="First-round deterministic continuity context.",
                source="deterministic-local-integration-provider",
                occurred_at=request.requested_at,
                provider_relevance=1.0,
                related_scope=[StateSection.CONTINUITY],
                tags=["first-round", "deterministic"],
                metadata={"external_model": False},
            ),
        )


class DeterministicMemoryInfluenceRecorder:
    """In-process recorder satisfying the current Memory influence port."""

    def __init__(self) -> None:
        self.records: list[MemoryInfluenceRecord] = []

    def record_influence(self, record: MemoryInfluenceRecord) -> None:
        self.records.append(MemoryInfluenceRecord.from_dict(record.to_dict()))


class DeterministicTokenBudgetManager:
    """Allocate a fixed non-billing budget for local deterministic Thinking."""

    def __init__(
        self,
        *,
        clock: Clock = _utc_now,
        usage_id_factory: IdFactory = lambda: "first-round-usage-001",
    ) -> None:
        self.call_count = 0
        self.usage_call_count = 0
        self._clock = clock
        self._usage_id_factory = usage_id_factory
        self._requests: dict[str, TokenBudgetRequest] = {}

    def allocate(self, request: TokenBudgetRequest) -> TokenBudget:
        self.call_count += 1
        if request.session_id is not None:
            self._requests[request.session_id] = request
        return TokenBudget(
            maximum_tokens=1024,
            remaining_tokens=1024,
            session_tokens=128,
            depth=request.depth,
        )

    def record_usage(self, think_id: str, actual_tokens: int) -> TokenUsageRecord:
        self.usage_call_count += 1
        request = self._requests[think_id]
        return TokenUsageRecord(
            usage_id=self._usage_id_factory(),
            subject_id=request.subject_id,
            session_id=think_id,
            session_type=ResourceSessionType.THINKING,
            estimated_tokens=128,
            actual_tokens=actual_tokens,
            model_name=request.model_name,
            reason=request.reason,
            created_at=self._clock(),
        )


class DeterministicThinkingProvider:
    """Produce the fixed first-round thought outcomes from Perception only."""

    def __init__(
        self,
        *,
        result_id_factory: IdFactory = lambda: "first-round-thinking-result-001",
        trace: Callable[[str], None] | None = None,
    ) -> None:
        self.call_count = 0
        self.seen_contents: list[str] = []
        self._result_id_factory = result_id_factory
        self._trace = trace

    @property
    def provider_id(self) -> str:
        return "deterministic-first-round-thinking-provider"

    def think(self, perception: PerceptionResult, budget: TokenBudget) -> ThinkingResult:
        self.call_count += 1
        if self._trace is not None:
            self._trace("thinking")
        if not perception.external_facts:
            raise ValueError("the first-round provider requires a perceived external fact")
        content = perception.external_facts[0].content
        self.seen_contents.append(content)
        should_update = content == "remember continuity test focus"
        mutations = (
            [
                StateMutation(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    value="first-round continuity test",
                    reason=(
                        "The explicit E3 test-only fixture requested a bounded "
                        "continuity focus update."
                    ),
                )
            ]
            if should_update
            else []
        )
        return ThinkingResult.create(
            result_id=self._result_id_factory(),
            provider_id=self.provider_id,
            result_summary=(
                "The perceived test fixture supports one bounded continuity update."
                if should_update
                else "The perceived message requires no SubjectState change."
            ),
            rationale_summary=(
                "Only the exact E3 update fixture may propose the fixed mutation."
                if should_update
                else "The message was perceived without a state-changing reason."
            ),
            generated_new_thought=should_update,
            update_subject_state=should_update,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=budget,
            proposed_mutations=mutations,
        )


class DeterministicContractReplyComposer:
    """Compose a stable expression from completed Thinking and Action."""

    def __init__(self, *, trace: Callable[[str], None] | None = None) -> None:
        self.call_count = 0
        self._trace = trace

    def compose(
        self,
        thinking: ThinkingExecutionResult,
        action: ActionExecutionResult,
    ) -> str:
        self.call_count += 1
        if self._trace is not None:
            self._trace("reply")
        result = thinking.session.result
        if result is None or not thinking.session.completed_successfully:
            raise ValueError("reply composition requires completed Thinking")
        if (
            action.decision.selected_action.action_type is ActionType.UPDATE_STATE
            and action.decision.approved
            and not action.decision.requires_confirmation
        ):
            return "The continuity test focus was approved for bounded evolution."
        return "The message was perceived; no continuity state change was approved."
