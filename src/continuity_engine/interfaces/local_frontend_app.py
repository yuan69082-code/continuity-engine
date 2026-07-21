from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from continuity_engine.domain.action import ResourceLimits
from continuity_engine.domain.awakening import AwakeCycle
from continuity_engine.domain.errors import (
    PermissionNotFoundError,
    ResourceNotFoundError,
    StateNotFoundError,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.resources import RuntimeMode
from continuity_engine.domain.thinking import ThinkingResult
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.services.user_interaction_service import UserInteractionService
from continuity_engine.services.wake_perception_thinking_action_service import (
    WakePerceptionThinkingActionService,
)
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_awakening_repository import (
    JsonAwakeningRepository,
)
from continuity_engine.storage.json_permission_repository import (
    JsonPermissionRepository,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository

from .api_service import APIService
from .core_views import RepositoryActionSessionProvider
from .models import InterfaceCapability
from .security import InterfaceAccessGuard


class EmptyMemoryRetriever:
    def retrieve(self, request):
        return []


class DiscardingMemoryInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class LocalDeterministicThinkingProvider:
    """Local placeholder proving the pipeline without pretending to be an AI."""

    provider_id = "local-deterministic-frontend-provider"

    def think(self, perception, budget):
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary=perception.summary,
            rationale_summary=(
                "The local frontend runtime mirrors the deterministic perception "
                "summary and does not call an AI model."
            ),
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=budget,
        )


@dataclass(slots=True)
class LocalFrontendApplication:
    api: APIService
    subject_id: str
    cycle_id: str


def create_local_frontend_application(
    data_dir: Path | str,
    *,
    subject_id: str = "demo-subject",
    initialize: bool = False,
    clock=None,
) -> LocalFrontendApplication:
    root = Path(data_dir)
    now = clock or utc_now
    clock_kwargs = {"clock": clock} if clock is not None else {}

    state_repository = JsonSubjectStateRepository(root)
    subject_states = SubjectStateService(state_repository, **clock_kwargs)
    if not state_repository.exists(subject_id):
        if not initialize:
            raise StateNotFoundError(
                "frontend subject is not initialized; start once with initialize=True"
            )
        subject_states.create(subject_id)

    resource_repository = JsonResourceRepository(root)
    resources = ResourceManager(resource_repository, **clock_kwargs)
    try:
        resources.get_resource_state(subject_id)
    except ResourceNotFoundError:
        if not initialize:
            raise
        resources.create_resource_state(
            subject_id,
            token_budget=1_000_000,
            compute_budget=10_000,
            current_mode=RuntimeMode.CONTINUOUS,
            resource_id=f"frontend-resources:{subject_id}",
        )

    permission_repository = JsonPermissionRepository(root)
    permissions = PermissionService(permission_repository, **clock_kwargs)
    permission_id = f"frontend-access:{subject_id}"
    try:
        permissions.get_permission(subject_id, permission_id)
    except PermissionNotFoundError:
        if not initialize:
            raise
        permissions.create_permission(
            subject_id,
            permission_id=permission_id,
            permission_type="frontend_access",
            name="Local frontend access",
            description="Allows the local UI to read state and submit interactions.",
            scope=["subject_state", "interaction"],
            capabilities=[
                InterfaceCapability.READ_SUBJECT_STATE.value,
                InterfaceCapability.SUBMIT_INTERACTION.value,
            ],
            source="local_frontend_bootstrap",
            reason="Enable the explicitly started local frontend entry point.",
        )

    memory = MemoryService(
        EmptyMemoryRetriever(),
        DiscardingMemoryInfluenceRecorder(),
        **clock_kwargs,
    )
    awakening_repository = JsonAwakeningRepository(root)
    awakening = AwakeningService(
        subject_states,
        memory,
        awakening_repository,
        **clock_kwargs,
    )
    cycle_id = f"frontend-cycle:{subject_id}"
    try:
        awakening.get_cycle(cycle_id)
    except StateNotFoundError:
        if not initialize:
            raise
        awakening_repository.save_cycle(
            AwakeCycle.manual(
                subject_id=subject_id,
                created_at=now(),
                cycle_id=cycle_id,
            )
        )

    thinking = ThinkingService(
        LocalDeterministicThinkingProvider(),
        resources,
        subject_states,
        JsonThinkingRepository(root),
        **clock_kwargs,
    )
    action_repository = InMemoryActionRepository()
    action = ActionService(InMemoryPermissionProvider(), action_repository)
    flow = WakePerceptionThinkingActionService(
        awakening,
        PerceptionService(),
        thinking,
        action,
        subject_states,
        permission_service=permissions,
        resource_limits=ResourceLimits(),
        **clock_kwargs,
    )
    interactions = UserInteractionService(
        subject_states,
        awakening,
        flow,
        **clock_kwargs,
    )
    api = APIService(
        subject_states=subject_states,
        memory=memory,
        perceptions=interactions,
        thinking=thinking,
        actions=RepositoryActionSessionProvider(action_repository),
        awakening=awakening,
        access_guard=InterfaceAccessGuard(
            permissions,
            resources,
            **clock_kwargs,
        ),
        interactions=interactions,
        **clock_kwargs,
    )
    return LocalFrontendApplication(api, subject_id, cycle_id)
