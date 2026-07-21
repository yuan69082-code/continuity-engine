from typing import Protocol

from continuity_engine.domain.action import (
    ActionIntent,
    ActionType,
    PermissionCheck,
    ResourceAssessment,
    ResourceLimits,
    RiskAssessment,
)
from datetime import datetime


class PermissionProvider(Protocol):
    """Pluggable permission inspection boundary; it never changes permissions."""

    def check(
        self,
        permission: str,
        *,
        subject_id: str,
        action_type: ActionType,
        target: str,
        at: datetime,
    ) -> PermissionCheck: ...


class RiskEvaluatorPort(Protocol):
    def evaluate(
        self,
        intent: ActionIntent,
        permission_checks: list[PermissionCheck],
    ) -> RiskAssessment: ...


class ResourceEvaluatorPort(Protocol):
    def evaluate(
        self,
        intent: ActionIntent,
        limits: ResourceLimits,
    ) -> ResourceAssessment: ...
