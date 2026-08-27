from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.errors import MachineContractValidationError
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import calculate_content_hash
from continuity_engine.domain.integration_hashing import (
    calculate_projection_content_hash,
    calculate_state_hash,
)
from continuity_engine.domain.integration_results import (
    FirstRoundSubjectResponse,
    FirstRoundSuccessResult,
    SubjectStateProjection,
    SubjectStateProjectionSnapshot,
    format_contract_datetime,
)
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.interfaces.integration_adapter import IntegrationAdapter
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.continuity_interaction_service import (
    ContinuityInteractionService,
)
from continuity_engine.services.deterministic_integration_providers import (
    DeterministicContractReplyComposer,
    DeterministicThinkingProvider,
    DeterministicTokenBudgetManager,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_request_hash,
)
from continuity_engine.services.integration_contract_validation import MachineContractValidator
from continuity_engine.services.integration_result_factory import FirstRoundResultFactory
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.thinking_service import ThinkingService


@dataclass(frozen=True, slots=True)
class StandardInteractionExecution:
    request: dict[str, Any]
    result: FirstRoundSuccessResult
    call_log: tuple[str, ...]


class SandboxContractValidator(MachineContractValidator):
    """Keep the formal request schema while allowing a disposable TEST binding."""

    def validate_fixed_subject_binding(
        self,
        payload: Any,
        *,
        binding_fixture_hash: str,
    ) -> SubjectBindingFixture:
        expected = {
            "schemaVersion",
            "bindingId",
            "userId",
            "assistantId",
            "subjectId",
            "bindingVersion",
            "status",
            "createdAt",
            "effectiveAt",
            "replacedBindingId",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise MachineContractValidationError(
                "P01 SubjectBinding fixture has an invalid shape"
            )
        fixture = SubjectBindingFixture(
            schema_version=payload["schemaVersion"],
            binding_id=payload["bindingId"],
            user_id=payload["userId"],
            assistant_id=payload["assistantId"],
            subject_id=payload["subjectId"],
            binding_version=payload["bindingVersion"],
            status=payload["status"],
            created_at=payload["createdAt"],
            effective_at=payload["effectiveAt"],
            replaced_binding_id=payload["replacedBindingId"],
        )
        if calculate_binding_fixture_hash(fixture) != binding_fixture_hash:
            raise MachineContractValidationError("P01 SubjectBinding hash mismatch")
        return fixture


class SandboxFirstRoundResultFactory(FirstRoundResultFactory):
    """Adapt only the fixed production Binding restriction for a TEST subject."""

    def create_completed_result(
        self,
        *,
        request_id: str,
        request_hash: str,
        binding: SubjectBindingFixture,
        response_content: str,
        subject_state: SubjectState,
        previous_revision: int,
        engine_update_id: str | None,
        consumed_observation_ids: Sequence[str],
        operation_id: str | None = None,
        response_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> FirstRoundSuccessResult:
        if subject_state.subject_id != binding.subject_id:
            raise MachineContractValidationError(
                "P01 SubjectState subject_id must match the disposable binding"
            )
        snapshot = SubjectStateProjectionSnapshot(
            subject_id=subject_state.subject_id,
            revision=subject_state.revision,
            state_hash=calculate_state_hash(subject_state),
        )
        projection = SubjectStateProjection(
            subject_id=subject_state.subject_id,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            previous_revision=previous_revision,
            current_revision=subject_state.revision,
            changed=subject_state.revision != previous_revision,
            engine_update_id=engine_update_id,
            snapshot=snapshot,
            content_hash=calculate_projection_content_hash(snapshot),
        )
        return FirstRoundSuccessResult(
            request_id=request_id,
            request_hash=request_hash,
            operation_id=operation_id or _identifier("p01-operation"),
            subject_id=subject_state.subject_id,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            response=FirstRoundSubjectResponse(
                response_id=response_id or _identifier("p01-response"),
                content=response_content,
            ),
            state_projection=projection,
            consumed_observation_ids=tuple(consumed_observation_ids),
            completed_at=format_contract_datetime(
                completed_at or datetime.now(timezone.utc)
            ),
        )


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _build_request(runtime: Any) -> dict[str, Any]:
    binding = runtime.binding_repository.load_active()
    state = runtime.subject_state()
    at = runtime.clock.now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    identity = {
        "userId": binding.user_id,
        "assistantId": binding.assistant_id,
        "subjectId": binding.subject_id,
        "bindingId": binding.binding_id,
        "bindingVersion": binding.binding_version,
    }
    conversation_id = _identifier("p01-conversation")
    message_id = _identifier("p01-message")
    message_version_id = _identifier("p01-message-version")
    observation_id = _identifier("p01-observation")
    conversation = {
        "conversationId": conversation_id,
        "messageId": message_id,
        "messageVersionId": message_version_id,
    }
    content = "remember continuity test focus"
    payload: dict[str, Any] = {
        "contractVersion": "continuity-integration/v1.1",
        "schemaVersion": "continuity-interaction-request/first-round-v1",
        "requestId": _identifier("p01-request"),
        "requestHash": "sha256:" + ("0" * 64),
        "requestType": "user_message",
        "identity": identity,
        "conversation": conversation,
        "expectedEngineRevision": state.revision,
        "platformFactPackage": {
            "schemaVersion": "vio-platform-fact-package/first-round-v1",
            "facts": [
                {
                    "schemaVersion": "vio-platform-fact/message-version-first-round-v1",
                    "factId": _identifier("p01-fact"),
                    "factType": "message_version",
                    "identity": dict(identity),
                    "conversationId": conversation_id,
                    "messageId": message_id,
                    "messageVersionId": message_version_id,
                    "senderType": "user",
                    "content": content,
                    "contentHash": calculate_content_hash(content),
                    "createdAt": at,
                }
            ],
            "observationRefs": [observation_id],
        },
        "observations": [
            {
                "schemaVersion": "vio-platform-observation/message-created-first-round-v1",
                "observationId": observation_id,
                "sourceEventId": _identifier("p01-platform-event"),
                "observationType": "message_created",
                "identity": dict(identity),
                "occurredAt": at,
                "observedAt": at,
                "messageVersionRef": dict(conversation),
            }
        ],
        "constraints": {"purpose": "reply_to_user_message"},
        "createdAt": at,
    }
    payload["requestHash"] = calculate_request_hash(payload)
    return payload


def execute_standard_interaction(runtime: Any) -> StandardInteractionExecution:
    """Execute the existing formal Engine pipeline with test-only durable ports."""

    permission_name = "subject_state:update"
    binding = runtime.binding_repository.load_active()
    trace = lambda stage: runtime.trace.record(
        "standard_interaction_stage",
        runtime.clock.now(),
        {"stage": stage},
    )
    provider = DeterministicThinkingProvider(
        result_id_factory=lambda: _identifier("p01-thinking-result")
    )
    thinking = ThinkingService(
        provider,
        DeterministicTokenBudgetManager(
            clock=runtime.clock.now,
            usage_id_factory=lambda: _identifier("p01-usage"),
        ),
        runtime.subject_states,
        runtime.thinking_repository,
        clock=runtime.clock.now,
    )
    service = ContinuityInteractionService(
        validator=SandboxContractValidator(),
        bindings=runtime.binding_repository,
        ledger=runtime.integration_ledger,
        subject_states=runtime.subject_states,
        awakening=AwakeningService(
            runtime.subject_states,
            runtime.memory_service,
            runtime.awakening,
            clock=runtime.clock.now,
        ),
        perception=PerceptionService(),
        thinking=thinking,
        action=ActionService(
            InMemoryPermissionProvider(
                [
                    PermissionGrant(
                        permission=permission_name,
                        subject_id=binding.subject_id,
                        valid_from=runtime.clock.now() - timedelta(days=1),
                        scopes=["*"],
                    )
                ]
            ),
            runtime.action_repository,
        ),
        action_evolution=ActionEvolutionService(
            runtime.subject_states, clock=runtime.clock.now
        ),
        reply_composer=DeterministicContractReplyComposer(),
        available_permissions=[permission_name],
        clock=runtime.clock.now,
        operation_id_factory=lambda: _identifier("p01-operation"),
        response_id_factory=lambda: _identifier("p01-response"),
        trace=trace,
        result_factory=SandboxFirstRoundResultFactory(),
    )
    request = _build_request(runtime)
    result = IntegrationAdapter(service).submit(request)
    if not isinstance(result, FirstRoundSuccessResult):
        raise RuntimeError(
            "the P01 standard interaction did not return a success result: "
            f"{result.to_dict()}"
        )
    return StandardInteractionExecution(
        request=request,
        result=result,
        call_log=tuple(service.last_call_log),
    )
