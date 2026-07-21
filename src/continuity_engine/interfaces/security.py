from __future__ import annotations

from dataclasses import dataclass

from continuity_engine.domain.models import utc_now
from continuity_engine.domain.permissions import PermissionContext
from continuity_engine.domain.resources import (
    ResourceAllocation,
    ResourceRequest,
    ResourceSessionType,
)
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.resource_manager import ResourceManager

from .models import (
    APIRequest,
    ExternalOperation,
    InterfaceCapability,
)


@dataclass(frozen=True, slots=True)
class EndpointPolicy:
    capability: InterfaceCapability
    scope: str
    session_type: ResourceSessionType
    estimated_tokens: int
    estimated_compute: int
    requires_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class InterfaceAccessGrant:
    permission_context: PermissionContext
    resources: ResourceAllocation


class InterfaceAccessError(Exception):
    def __init__(self, code: str, message: str, *, details=None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


class InterfaceAccessGuard:
    """Apply continuity permission and resource policy to every external call."""

    POLICIES = {
        ExternalOperation.GET_SUBJECT_STATE: EndpointPolicy(
            InterfaceCapability.READ_SUBJECT_STATE,
            "subject_state",
            ResourceSessionType.OTHER,
            1,
            0,
        ),
        ExternalOperation.QUERY_MEMORY: EndpointPolicy(
            InterfaceCapability.QUERY_MEMORY,
            "memory_manager",
            ResourceSessionType.MEMORY,
            32,
            1,
        ),
        ExternalOperation.GET_PERCEPTION: EndpointPolicy(
            InterfaceCapability.READ_PERCEPTION,
            "perception",
            ResourceSessionType.OTHER,
            8,
            1,
        ),
        ExternalOperation.REQUEST_THINKING: EndpointPolicy(
            InterfaceCapability.REQUEST_THINKING,
            "thinking",
            ResourceSessionType.OTHER,
            1,
            0,
        ),
        ExternalOperation.GET_ACTION_PLAN: EndpointPolicy(
            InterfaceCapability.READ_ACTION_PLAN,
            "action",
            ResourceSessionType.OTHER,
            4,
            0,
        ),
        ExternalOperation.TRIGGER_MANUAL_WAKE: EndpointPolicy(
            InterfaceCapability.TRIGGER_WAKE,
            "awakening",
            ResourceSessionType.OTHER,
            64,
            1,
            requires_confirmation=True,
        ),
        ExternalOperation.SUBMIT_MESSAGE: EndpointPolicy(
            InterfaceCapability.SUBMIT_INTERACTION,
            "interaction",
            ResourceSessionType.OTHER,
            64,
            1,
        ),
    }

    def __init__(
        self,
        permissions: PermissionService,
        resources: ResourceManager,
        *,
        clock=utc_now,
    ) -> None:
        self._permissions = permissions
        self._resources = resources
        self._clock = clock

    def authorize(
        self,
        request: APIRequest,
        operation: ExternalOperation,
    ) -> InterfaceAccessGrant:
        policy = self.POLICIES[operation]
        permission_context = self._permissions.get_context(request.subject_id)
        if not permission_context.has_capability(
            policy.capability.value,
            policy.scope,
        ):
            raise InterfaceAccessError(
                "PERMISSION_DENIED",
                f"PermissionContext does not allow {policy.capability.value}.",
                details={
                    "required_capability": policy.capability.value,
                    "required_scope": policy.scope,
                },
            )
        if policy.requires_confirmation and not request.confirmed:
            raise InterfaceAccessError(
                "CONFIRMATION_REQUIRED",
                f"{operation.value} requires explicit confirmation.",
                details={"operation": operation.value},
            )

        allocation = self._resources.request_resources(
            ResourceRequest.create(
                request_id=f"interface:{request.request_id}",
                subject_id=request.subject_id,
                session_id=request.request_id,
                session_type=policy.session_type,
                estimated_tokens=policy.estimated_tokens,
                estimated_compute=policy.estimated_compute,
                model_name="continuity-interface",
                reason=f"Authorize external {operation.value} request.",
                requested_at=self._clock(),
            )
        )
        if not allocation.decision.allowed:
            raise InterfaceAccessError(
                "RESOURCE_DEFERRED",
                allocation.decision.reason,
                details={"resource_decision": allocation.decision.to_dict()},
            )
        return InterfaceAccessGrant(permission_context, allocation)
