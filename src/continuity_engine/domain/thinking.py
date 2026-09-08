from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from .awakening import AwakeningResult
from .errors import ThinkingValidationError
from .events import JsonValue, StateMutation, StateSection, StateUpdateRecord
from .perception import PerceptionResult


class ThinkingDepth(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    DEEP = "DEEP"


class ThinkSessionStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_CAPABILITY = "WAITING_CAPABILITY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


THINKING_WRITEBACK_SECTIONS = {
    StateSection.CONTINUITY,
    StateSection.INTENTIONS,
}


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ThinkingValidationError(f"{field_name} must be a non-empty string")
    return value


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ThinkingValidationError("datetime values must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ThinkingValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThinkingValidationError(f"{field_name} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ThinkingValidationError(f"{field_name} must include a timezone")
    return parsed


def _text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ThinkingValidationError(f"{field_name} must be a list of non-empty strings")
    return list(value)


@dataclass(slots=True)
class TokenBudgetRequest:
    subject_id: str
    wake_session_id: str
    depth: ThinkingDepth
    requested_at: datetime
    session_id: str | None = None
    model_name: str = "unbound-thinking-provider"
    reason: str = "Allocate resources for a thinking session."

    def __post_init__(self) -> None:
        _require_text(self.subject_id, "budget request subject_id")
        _require_text(self.wake_session_id, "budget request wake_session_id")
        if self.session_id is not None:
            _require_text(self.session_id, "budget request session_id")
        _require_text(self.model_name, "budget request model_name")
        _require_text(self.reason, "budget request reason")
        if not isinstance(self.depth, ThinkingDepth):
            try:
                self.depth = ThinkingDepth(self.depth)
            except ValueError as exc:
                raise ThinkingValidationError("unsupported thinking depth") from exc
        if self.requested_at.tzinfo is None:
            raise ThinkingValidationError("budget requested_at must include a timezone")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "subject_id": self.subject_id,
            "wake_session_id": self.wake_session_id,
            "depth": self.depth.value,
            "requested_at": _format_datetime(self.requested_at),
            "session_id": self.session_id,
            "model_name": self.model_name,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TokenBudgetRequest:
        if not isinstance(value, dict):
            raise ThinkingValidationError("token budget request must be an object")
        requested_at = _parse_datetime(
            value.get("requested_at"), "budget requested_at"
        )
        assert requested_at is not None
        return cls(
            subject_id=value.get("subject_id"),
            wake_session_id=value.get("wake_session_id"),
            depth=value.get("depth"),
            requested_at=requested_at,
            session_id=value.get("session_id"),
            model_name=value.get("model_name", "unbound-thinking-provider"),
            reason=value.get(
                "reason", "Allocate resources for a thinking session."
            ),
        )


@dataclass(slots=True)
class TokenBudget:
    maximum_tokens: int
    remaining_tokens: int
    session_tokens: int
    depth: ThinkingDepth

    def __post_init__(self) -> None:
        for value, name in (
            (self.maximum_tokens, "maximum_tokens"),
            (self.remaining_tokens, "remaining_tokens"),
            (self.session_tokens, "session_tokens"),
        ):
            if not isinstance(value, int) or value < 0:
                raise ThinkingValidationError(f"{name} must be a non-negative integer")
        if self.remaining_tokens > self.maximum_tokens:
            raise ThinkingValidationError("remaining_tokens cannot exceed maximum_tokens")
        if self.session_tokens > self.remaining_tokens:
            raise ThinkingValidationError("session_tokens cannot exceed remaining_tokens")
        if not isinstance(self.depth, ThinkingDepth):
            try:
                self.depth = ThinkingDepth(self.depth)
            except ValueError as exc:
                raise ThinkingValidationError("unsupported thinking depth") from exc

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "maximum_tokens": self.maximum_tokens,
            "remaining_tokens": self.remaining_tokens,
            "session_tokens": self.session_tokens,
            "depth": self.depth.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TokenBudget:
        if not isinstance(value, dict):
            raise ThinkingValidationError("token budget must be an object")
        return cls(
            maximum_tokens=value.get("maximum_tokens"),
            remaining_tokens=value.get("remaining_tokens"),
            session_tokens=value.get("session_tokens"),
            depth=value.get("depth"),
        )


@dataclass(slots=True)
class ThinkingResult:
    result_id: str
    provider_id: str
    result_summary: str
    rationale_summary: str
    generated_new_thought: bool
    update_subject_state: bool
    request_more_memory: bool
    should_wait: bool
    suggest_future_user_contact: bool
    token_budget: TokenBudget
    proposed_mutations: list[StateMutation] = field(default_factory=list)
    additional_memory_query: str | None = None
    suggest_tool_use: bool = False
    tool_target: str | None = None
    request_more_thinking: bool = False
    expression_mode: str | None = None

    def __post_init__(self) -> None:
        if self.expression_mode is not None:
            from .expression import ExpressionMode
            if self.expression_mode not in {mode.value for mode in ExpressionMode}:
                raise ThinkingValidationError("unsupported formed expression mode")
        _require_text(self.result_id, "thinking result_id")
        _require_text(self.provider_id, "thinking provider_id")
        _require_text(self.result_summary, "thinking result_summary")
        _require_text(self.rationale_summary, "thinking rationale_summary")
        for value, name in (
            (self.generated_new_thought, "generated_new_thought"),
            (self.update_subject_state, "update_subject_state"),
            (self.request_more_memory, "request_more_memory"),
            (self.should_wait, "should_wait"),
            (self.suggest_future_user_contact, "suggest_future_user_contact"),
            (self.suggest_tool_use, "suggest_tool_use"),
            (self.request_more_thinking, "request_more_thinking"),
        ):
            if not isinstance(value, bool):
                raise ThinkingValidationError(f"{name} must be a boolean")
        if not isinstance(self.token_budget, TokenBudget):
            raise ThinkingValidationError("thinking result requires a TokenBudget")
        if any(not isinstance(item, StateMutation) for item in self.proposed_mutations):
            raise ThinkingValidationError("proposed_mutations must contain StateMutation values")
        if self.update_subject_state and not self.proposed_mutations:
            raise ThinkingValidationError(
                "state writeback requires at least one proposed mutation"
            )
        if not self.update_subject_state and self.proposed_mutations:
            raise ThinkingValidationError(
                "proposed mutations require update_subject_state to be true"
            )
        for mutation in self.proposed_mutations:
            if mutation.field_path in {'identity.self_narrative','relationship.objects'}:
                from .subject_growth import growth_document
                if mutation.operation.value != 'set':
                    raise ThinkingValidationError('internal growth requires a typed SET proposal')
                growth_document(mutation.value,kind='narrative' if mutation.field_path=='identity.self_narrative' else 'relationships')
                continue  # Rejected at Provider ingress; Engine processor only, still Action/Evolution gated.
            section_name = mutation.field_path.split(".", 1)[0]
            try:
                section = StateSection(section_name)
            except ValueError as exc:
                raise ThinkingValidationError("proposed mutation has an invalid state section") from exc
            if section not in THINKING_WRITEBACK_SECTIONS:
                raise ThinkingValidationError(
                    "thinking writeback is limited to continuity and intentions"
                )
        if self.request_more_memory:
            _require_text(self.additional_memory_query, "additional_memory_query")
        elif self.additional_memory_query is not None:
            raise ThinkingValidationError(
                "additional_memory_query requires request_more_memory to be true"
            )
        if self.suggest_tool_use:
            _require_text(self.tool_target, "tool_target")
        elif self.tool_target is not None:
            raise ThinkingValidationError(
                "tool_target requires suggest_tool_use to be true"
            )

    @classmethod
    def create(
        cls,
        *,
        provider_id: str,
        result_summary: str,
        rationale_summary: str,
        generated_new_thought: bool,
        update_subject_state: bool,
        request_more_memory: bool,
        should_wait: bool,
        suggest_future_user_contact: bool,
        token_budget: TokenBudget,
        proposed_mutations: Iterable[StateMutation] = (),
        additional_memory_query: str | None = None,
        suggest_tool_use: bool = False,
        tool_target: str | None = None,
        request_more_thinking: bool = False,
        expression_mode: str | None = None,
        result_id: str | None = None,
    ) -> ThinkingResult:
        return cls(
            result_id=result_id or str(uuid4()),
            provider_id=provider_id,
            result_summary=result_summary,
            rationale_summary=rationale_summary,
            generated_new_thought=generated_new_thought,
            update_subject_state=update_subject_state,
            request_more_memory=request_more_memory,
            should_wait=should_wait,
            suggest_future_user_contact=suggest_future_user_contact,
            token_budget=token_budget,
            proposed_mutations=list(proposed_mutations),
            additional_memory_query=additional_memory_query,
            suggest_tool_use=suggest_tool_use,
            tool_target=tool_target,
            request_more_thinking=request_more_thinking,
            expression_mode=expression_mode,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "result_id": self.result_id,
            "provider_id": self.provider_id,
            "result_summary": self.result_summary,
            "rationale_summary": self.rationale_summary,
            "generated_new_thought": self.generated_new_thought,
            "update_subject_state": self.update_subject_state,
            "request_more_memory": self.request_more_memory,
            "should_wait": self.should_wait,
            "suggest_future_user_contact": self.suggest_future_user_contact,
            "token_budget": self.token_budget.to_dict(),
            "proposed_mutations": [item.to_dict() for item in self.proposed_mutations],
            "additional_memory_query": self.additional_memory_query,
            "suggest_tool_use": self.suggest_tool_use,
            "tool_target": self.tool_target,
            "request_more_thinking": self.request_more_thinking,
            **({"expression_mode": self.expression_mode} if self.expression_mode is not None else {}),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ThinkingResult:
        if not isinstance(value, dict):
            raise ThinkingValidationError("thinking result must be an object")
        raw_mutations = value.get("proposed_mutations", [])
        if not isinstance(raw_mutations, list):
            raise ThinkingValidationError("proposed_mutations must be a list")
        return cls(
            result_id=value.get("result_id"),
            provider_id=value.get("provider_id"),
            result_summary=value.get("result_summary"),
            rationale_summary=value.get("rationale_summary"),
            generated_new_thought=value.get("generated_new_thought"),
            update_subject_state=value.get("update_subject_state"),
            request_more_memory=value.get("request_more_memory"),
            should_wait=value.get("should_wait"),
            suggest_future_user_contact=value.get("suggest_future_user_contact"),
            token_budget=TokenBudget.from_dict(value.get("token_budget")),
            proposed_mutations=[StateMutation.from_dict(item) for item in raw_mutations],
            additional_memory_query=value.get("additional_memory_query"),
            suggest_tool_use=value.get("suggest_tool_use", False),
            tool_target=value.get("tool_target"),
            request_more_thinking=value.get("request_more_thinking", False),
            expression_mode=value.get("expression_mode"),
        )


@dataclass(slots=True)
class ThinkingObservationLog:
    wake_context_id: str
    state_revision: int
    event_ids: list[str]
    update_ids: list[str]
    viewed_memory_ids: list[str]
    selected_memory_ids: list[str]
    perception_id: str | None = None
    perception_summary: str | None = None
    thinking_context_id: str | None = None
    perceived_external_fact_ids: list[str] = field(default_factory=list)
    continuity_context_hash: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.wake_context_id, "wake_context_id")
        if not isinstance(self.state_revision, int) or self.state_revision < 0:
            raise ThinkingValidationError("thinking observation revision is invalid")
        for values, name in (
            (self.event_ids, "thinking event_ids"),
            (self.update_ids, "thinking update_ids"),
            (self.viewed_memory_ids, "thinking viewed_memory_ids"),
            (self.selected_memory_ids, "thinking selected_memory_ids"),
            (
                self.perceived_external_fact_ids,
                "thinking perceived_external_fact_ids",
            ),
        ):
            _text_list(values, name)
        if self.perception_id is not None:
            _require_text(self.perception_id, "perception_id")
        if self.perception_summary is not None:
            _require_text(self.perception_summary, "perception_summary")
        if self.continuity_context_hash is not None and (
            not isinstance(self.continuity_context_hash, str)
            or len(self.continuity_context_hash) != 71
            or not self.continuity_context_hash.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in self.continuity_context_hash[7:])
        ):
            raise ThinkingValidationError("invalid C1 Thinking input binding")
        if self.thinking_context_id is not None:
            _require_text(self.thinking_context_id, "thinking_context_id")
        if self.perception_id is None and self.thinking_context_id is None:
            raise ThinkingValidationError(
                "thinking observation requires a perception or legacy context reference"
            )

    @classmethod
    def from_perception(cls, perception: PerceptionResult) -> ThinkingObservationLog:
        return cls(
            perception_id=perception.perception_id,
            perception_summary=perception.summary,
            wake_context_id=perception.wake_context_id,
            state_revision=perception.source_revision,
            event_ids=list(perception.recent_event_ids),
            update_ids=list(perception.recent_update_ids),
            viewed_memory_ids=list(perception.viewed_memory_ids),
            selected_memory_ids=list(perception.selected_memory_ids),
            perceived_external_fact_ids=[
                item.fact_id for item in perception.external_facts
            ],
            continuity_context_hash=(perception.continuity_context.binding_hash()
                                     if perception.continuity_context is not None else None),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "perception_id": self.perception_id,
            "perception_summary": self.perception_summary,
            "thinking_context_id": self.thinking_context_id,
            "wake_context_id": self.wake_context_id,
            "state_revision": self.state_revision,
            "event_ids": list(self.event_ids),
            "update_ids": list(self.update_ids),
            "viewed_memory_ids": list(self.viewed_memory_ids),
            "selected_memory_ids": list(self.selected_memory_ids),
            "perceived_external_fact_ids": list(
                self.perceived_external_fact_ids
            ),
            **({"continuity_context_hash": self.continuity_context_hash}
               if self.continuity_context_hash is not None else {}),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ThinkingObservationLog:
        if not isinstance(value, dict):
            raise ThinkingValidationError("thinking observation must be an object")
        return cls(
            perception_id=value.get("perception_id"),
            perception_summary=value.get("perception_summary"),
            thinking_context_id=value.get("thinking_context_id"),
            wake_context_id=_require_text(value.get("wake_context_id"), "wake_context_id"),
            state_revision=value.get("state_revision"),
            event_ids=_text_list(value.get("event_ids", []), "thinking event_ids"),
            update_ids=_text_list(value.get("update_ids", []), "thinking update_ids"),
            viewed_memory_ids=_text_list(
                value.get("viewed_memory_ids", []), "thinking viewed_memory_ids"
            ),
            selected_memory_ids=_text_list(
                value.get("selected_memory_ids", []), "thinking selected_memory_ids"
            ),
            perceived_external_fact_ids=_text_list(
                value.get("perceived_external_fact_ids", []),
                "thinking perceived_external_fact_ids",
            ),
            continuity_context_hash=value.get("continuity_context_hash"),
        )


@dataclass(slots=True)
class ThinkSession:
    think_id: str
    wake_session_id: str
    subject_id: str
    provider_id: str
    started_at: datetime
    thinking_reason: str
    token_budget: TokenBudget
    observation: ThinkingObservationLog
    ended_at: datetime | None = None
    actual_token_consumption: int | None = None
    result: ThinkingResult | None = None
    completed_successfully: bool | None = None
    state_written_back: bool | None = None
    state_event_id: str | None = None
    state_update_id: str | None = None
    error: str | None = None
    perception_snapshot: PerceptionResult | None = None
    status: ThinkSessionStatus = ThinkSessionStatus.RUNNING
    capability_request_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.think_id, "think_id")
        _require_text(self.wake_session_id, "wake_session_id")
        _require_text(self.subject_id, "think subject_id")
        _require_text(self.provider_id, "think provider_id")
        _require_text(self.thinking_reason, "thinking_reason")
        if not isinstance(self.status, ThinkSessionStatus):
            raise ThinkingValidationError("ThinkSession status is invalid")
        if self.capability_request_id is not None:
            _require_text(self.capability_request_id, "capability_request_id")
        if self.started_at.tzinfo is None:
            raise ThinkingValidationError("think started_at must include a timezone")
        if self.ended_at is not None and self.ended_at.tzinfo is None:
            raise ThinkingValidationError("think ended_at must include a timezone")
        if self.actual_token_consumption is not None and (
            not isinstance(self.actual_token_consumption, int)
            or self.actual_token_consumption < 0
        ):
            raise ThinkingValidationError(
                "actual_token_consumption must be non-negative or null"
            )
        if self.completed_successfully is None:
            if any(
                value is not None
                for value in (
                    self.ended_at,
                    self.result,
                    self.state_written_back,
                    self.state_event_id,
                    self.state_update_id,
                    self.error,
                )
            ):
                raise ThinkingValidationError(
                    "a running ThinkSession cannot contain completion fields"
                )
            if self.status not in {
                ThinkSessionStatus.RUNNING,
                ThinkSessionStatus.WAITING_CAPABILITY,
            }:
                raise ThinkingValidationError(
                    "an unfinished ThinkSession has an invalid status"
                )
            if (
                self.status is ThinkSessionStatus.WAITING_CAPABILITY
                and self.capability_request_id is None
            ):
                raise ThinkingValidationError(
                    "WAITING_CAPABILITY requires capability_request_id"
                )
        else:
            if self.ended_at is None or self.result is None or self.state_written_back is None:
                raise ThinkingValidationError(
                    "a finalized ThinkSession requires ended_at, result, and writeback status"
                )
            if self.completed_successfully and self.error is not None:
                raise ThinkingValidationError("a successful ThinkSession cannot contain an error")
            if not self.completed_successfully:
                _require_text(self.error, "ThinkSession error")
            if self.result.provider_id != self.provider_id:
                raise ThinkingValidationError(
                    "ThinkSession result provider does not match session provider"
                )
            if self.result.token_budget != self.token_budget:
                raise ThinkingValidationError(
                    "ThinkSession result budget does not match session budget"
                )
            expected_status = (
                ThinkSessionStatus.COMPLETED
                if self.completed_successfully
                else ThinkSessionStatus.FAILED
            )
            if self.status is not expected_status:
                raise ThinkingValidationError(
                    "final ThinkSession status does not match its completion result"
                )
        if self.observation.continuity_context_hash is not None:
            snapshot = self.perception_snapshot
            if (snapshot is None or snapshot.continuity_context is None
                    or snapshot.continuity_context.binding_hash() != self.observation.continuity_context_hash):
                raise ThinkingValidationError("C1 ThinkSession input binding is missing or inconsistent")
        if self.perception_snapshot is not None:
            if self.perception_snapshot.subject_id != self.subject_id:
                raise ThinkingValidationError(
                    "ThinkSession perception snapshot belongs to another subject"
                )
            if self.perception_snapshot.wake_session_id != self.wake_session_id:
                raise ThinkingValidationError(
                    "ThinkSession perception snapshot belongs to another wake"
                )
            if self.perception_snapshot.perception_id != self.observation.perception_id:
                raise ThinkingValidationError(
                    "ThinkSession perception snapshot does not match its observation"
                )

    @classmethod
    def start(
        cls,
        *,
        wake_session_id: str,
        subject_id: str,
        provider_id: str,
        started_at: datetime,
        thinking_reason: str,
        token_budget: TokenBudget,
        perception: PerceptionResult,
        think_id: str | None = None,
        retain_perception_snapshot: bool = False,
    ) -> ThinkSession:
        if subject_id != perception.subject_id:
            raise ThinkingValidationError("ThinkSession subject does not match perception")
        if wake_session_id != perception.wake_session_id:
            raise ThinkingValidationError("ThinkSession wake does not match perception")
        return cls(
            think_id=think_id or str(uuid4()),
            wake_session_id=wake_session_id,
            subject_id=subject_id,
            provider_id=provider_id,
            started_at=started_at,
            thinking_reason=thinking_reason,
            token_budget=token_budget,
            observation=ThinkingObservationLog.from_perception(perception),
            perception_snapshot=(
                PerceptionResult.from_dict(perception.to_dict())
                if retain_perception_snapshot or perception.continuity_context is not None
                else None
            ),
        )

    def complete(
        self,
        *,
        ended_at: datetime,
        result: ThinkingResult,
        state_written_back: bool,
        state_event_id: str | None = None,
        state_update_id: str | None = None,
    ) -> None:
        if ended_at.tzinfo is None:
            raise ThinkingValidationError("think ended_at must include a timezone")
        if result.provider_id != self.provider_id or result.token_budget != self.token_budget:
            raise ThinkingValidationError(
                "ThinkSession completion result does not match its provider or budget"
            )
        self.ended_at = ended_at
        self.result = result
        self.completed_successfully = True
        self.state_written_back = state_written_back
        self.state_event_id = state_event_id
        self.state_update_id = state_update_id
        self.error = None
        self.status = ThinkSessionStatus.COMPLETED

    def fail(
        self,
        *,
        ended_at: datetime,
        result: ThinkingResult,
        error: str,
        state_written_back: bool = False,
        state_event_id: str | None = None,
        state_update_id: str | None = None,
    ) -> None:
        if ended_at.tzinfo is None:
            raise ThinkingValidationError("think ended_at must include a timezone")
        if result.provider_id != self.provider_id or result.token_budget != self.token_budget:
            raise ThinkingValidationError(
                "ThinkSession failure result does not match its provider or budget"
            )
        self.ended_at = ended_at
        self.result = result
        self.completed_successfully = False
        self.state_written_back = state_written_back
        self.state_event_id = state_event_id
        self.state_update_id = state_update_id
        self.error = _require_text(error, "ThinkSession error")
        self.status = ThinkSessionStatus.FAILED

    def wait_for_capability(self, capability_request_id: str) -> None:
        if self.status is not ThinkSessionStatus.RUNNING:
            raise ThinkingValidationError(
                "only a running ThinkSession can wait for capability"
            )
        self.capability_request_id = _require_text(
            capability_request_id,
            "capability_request_id",
        )
        self.status = ThinkSessionStatus.WAITING_CAPABILITY

    def resume_from_capability(self) -> None:
        if self.status is not ThinkSessionStatus.WAITING_CAPABILITY:
            raise ThinkingValidationError(
                "only a waiting ThinkSession can resume from capability"
            )
        if self.capability_request_id is None:
            raise ThinkingValidationError(
                "capability resume requires capability_request_id"
            )
        self.status = ThinkSessionStatus.RUNNING

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "think_id": self.think_id,
            "wake_session_id": self.wake_session_id,
            "subject_id": self.subject_id,
            "provider_id": self.provider_id,
            "started_at": _format_datetime(self.started_at),
            "ended_at": _format_datetime(self.ended_at),
            "thinking_reason": self.thinking_reason,
            "token_budget": self.token_budget.to_dict(),
            "actual_token_consumption": self.actual_token_consumption,
            "result": self.result.to_dict() if self.result else None,
            "completed_successfully": self.completed_successfully,
            "state_written_back": self.state_written_back,
            "state_event_id": self.state_event_id,
            "state_update_id": self.state_update_id,
            "observation": self.observation.to_dict(),
            "perception_snapshot": (
                self.perception_snapshot.to_dict()
                if self.perception_snapshot is not None
                else None
            ),
            "error": self.error,
            "status": self.status.value,
            "capability_request_id": self.capability_request_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ThinkSession:
        if not isinstance(value, dict):
            raise ThinkingValidationError("ThinkSession must be an object")
        started_at = _parse_datetime(value.get("started_at"), "think started_at")
        assert started_at is not None
        raw_result = value.get("result")
        raw_perception = value.get("perception_snapshot")
        raw_status = value.get("status")
        if raw_status is None:
            completed = value.get("completed_successfully")
            raw_status = (
                ThinkSessionStatus.COMPLETED.value
                if completed is True
                else ThinkSessionStatus.FAILED.value
                if completed is False
                else ThinkSessionStatus.RUNNING.value
            )
        try:
            status = ThinkSessionStatus(raw_status)
        except (TypeError, ValueError) as exc:
            raise ThinkingValidationError("ThinkSession status is invalid") from exc
        return cls(
            think_id=value.get("think_id"),
            wake_session_id=value.get("wake_session_id"),
            subject_id=value.get("subject_id"),
            provider_id=value.get("provider_id"),
            started_at=started_at,
            ended_at=_parse_datetime(value.get("ended_at"), "think ended_at", optional=True),
            thinking_reason=value.get("thinking_reason"),
            token_budget=TokenBudget.from_dict(value.get("token_budget")),
            actual_token_consumption=value.get("actual_token_consumption"),
            result=ThinkingResult.from_dict(raw_result) if raw_result is not None else None,
            completed_successfully=value.get("completed_successfully"),
            state_written_back=value.get("state_written_back"),
            state_event_id=value.get("state_event_id"),
            state_update_id=value.get("state_update_id"),
            observation=ThinkingObservationLog.from_dict(value.get("observation")),
            perception_snapshot=(
                PerceptionResult.from_dict(raw_perception)
                if raw_perception is not None
                else None
            ),
            error=value.get("error"),
            status=status,
            capability_request_id=value.get("capability_request_id"),
        )


@dataclass(slots=True)
class ThinkingExecutionResult:
    perception: PerceptionResult
    session: ThinkSession
    state_update: StateUpdateRecord | None = None


@dataclass(slots=True)
class WakePerceptionThinkingResult:
    awakening: AwakeningResult
    perception: PerceptionResult
    thinking: ThinkingExecutionResult | None
