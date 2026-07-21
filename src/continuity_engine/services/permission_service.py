from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from uuid import uuid4

from continuity_engine.domain.errors import (
    PermissionAlreadyExistsError,
    PermissionNotFoundError,
    PermissionValidationError,
)
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.models import utc_now
from continuity_engine.domain.permissions import (
    PermissionChangeRecord,
    PermissionChangeResult,
    PermissionChangeType,
    PermissionContext,
    PermissionState,
    PermissionStatus,
)
from continuity_engine.storage.base import PermissionRepository


class PermissionService:
    """Manage permission continuity state and history without external actions."""

    def __init__(
        self,
        repository: PermissionRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create_permission(
        self,
        subject_id: str,
        *,
        permission_type: str,
        name: str,
        description: str,
        scope: Iterable[str],
        capabilities: Iterable[str],
        source: str,
        reason: str,
        permission_id: str | None = None,
    ) -> PermissionChangeResult:
        created_at = self._clock()
        identifier = permission_id or str(uuid4())
        try:
            self._repository.load(subject_id, identifier)
        except PermissionNotFoundError:
            pass
        else:
            raise PermissionAlreadyExistsError(
                f"permission already exists: {identifier}"
            )
        permission = PermissionState(
            permission_id=identifier,
            subject_id=subject_id,
            permission_type=permission_type,
            name=name,
            description=description,
            scope=list(scope),
            capabilities=list(capabilities),
            status=PermissionStatus.ACTIVE,
            granted_at=created_at,
            revoked_at=None,
            source=source,
            revision=0,
        )
        record = PermissionChangeRecord(
            record_id=str(uuid4()),
            permission_id=identifier,
            change_type=PermissionChangeType.GRANTED,
            before_state=None,
            after_state=permission.to_dict(),
            reason=reason,
            source=source,
            created_at=created_at,
        )
        self._repository.save(permission, record)
        return self._result(permission, record)

    def get_permission(self, subject_id: str, permission_id: str) -> PermissionState:
        return self._repository.load(subject_id, permission_id)

    def list_permissions(
        self,
        subject_id: str,
        *,
        include_unavailable: bool = True,
    ) -> list[PermissionState]:
        permissions = self._repository.list(subject_id)
        return (
            permissions
            if include_unavailable
            else [item for item in permissions if item.is_available]
        )

    def get_history(
        self,
        subject_id: str,
        permission_id: str | None = None,
    ) -> list[PermissionChangeRecord]:
        return self._repository.history(subject_id, permission_id)

    def update_status(
        self,
        subject_id: str,
        permission_id: str,
        status: PermissionStatus,
        *,
        reason: str,
        source: str,
        expected_revision: int | None = None,
    ) -> PermissionChangeResult:
        current = self._repository.load(subject_id, permission_id)
        self._check_revision(current, expected_revision)
        try:
            next_status = status if isinstance(status, PermissionStatus) else PermissionStatus(status)
        except ValueError as exc:
            raise PermissionValidationError("unsupported permission status") from exc
        if current.status is next_status:
            raise PermissionValidationError(
                f"permission already has status {next_status.value}"
            )
        updated = PermissionState.from_dict(current.to_dict())
        updated.status = next_status
        updated.revoked_at = (
            self._clock() if next_status is PermissionStatus.REVOKED else None
        )
        updated.source = source
        updated.revision += 1
        updated.__post_init__()
        change_type = {
            PermissionStatus.REVOKED: PermissionChangeType.REVOKED,
            PermissionStatus.LIMITED: PermissionChangeType.LIMITED,
            PermissionStatus.EXPIRED: PermissionChangeType.EXPIRED,
            PermissionStatus.ACTIVE: PermissionChangeType.STATUS_CHANGED,
        }[next_status]
        return self._save_change(current, updated, change_type, reason, source)

    def restrict_permission(
        self,
        subject_id: str,
        permission_id: str,
        *,
        reason: str,
        source: str,
        scope: Iterable[str] | None = None,
        capabilities: Iterable[str] | None = None,
        expected_revision: int | None = None,
    ) -> PermissionChangeResult:
        current = self._repository.load(subject_id, permission_id)
        self._check_revision(current, expected_revision)
        updated = PermissionState.from_dict(current.to_dict())
        next_scope = list(scope) if scope is not None else list(updated.scope)
        next_capabilities = (
            list(capabilities)
            if capabilities is not None
            else list(updated.capabilities)
        )
        if (
            current.status is PermissionStatus.LIMITED
            and next_scope == current.scope
            and next_capabilities == current.capabilities
        ):
            raise PermissionValidationError("permission restriction has no changes")
        updated.status = PermissionStatus.LIMITED
        updated.scope = next_scope
        updated.capabilities = next_capabilities
        updated.revoked_at = None
        updated.source = source
        updated.revision += 1
        updated.__post_init__()
        return self._save_change(
            current,
            updated,
            PermissionChangeType.LIMITED,
            reason,
            source,
        )

    def revoke_permission(
        self,
        subject_id: str,
        permission_id: str,
        *,
        reason: str,
        source: str,
        expected_revision: int | None = None,
    ) -> PermissionChangeResult:
        return self.update_status(
            subject_id,
            permission_id,
            PermissionStatus.REVOKED,
            reason=reason,
            source=source,
            expected_revision=expected_revision,
        )

    def check_capability(
        self,
        subject_id: str,
        capability: str,
        *,
        scope: str | None = None,
    ) -> bool:
        return self.get_context(subject_id).has_capability(capability, scope)

    def get_context(
        self,
        subject_id: str,
        *,
        recent_change_limit: int = 20,
    ) -> PermissionContext:
        if not isinstance(recent_change_limit, int) or recent_change_limit <= 0:
            raise PermissionValidationError(
                "recent_change_limit must be a positive integer"
            )
        current = [
            item for item in self._repository.list(subject_id) if item.is_available
        ]
        capabilities = list(
            dict.fromkeys(
                capability
                for permission in current
                for capability in permission.capabilities
            )
        )
        restrictions = [
            (
                f"{permission.name} is LIMITED to scopes "
                f"{', '.join(permission.scope) or '(none)'} and capabilities "
                f"{', '.join(permission.capabilities) or '(none)'}."
            )
            for permission in current
            if permission.status is PermissionStatus.LIMITED
        ]
        history = self._repository.history(subject_id)
        recent = sorted(
            history,
            key=lambda item: (item.created_at, item.record_id),
            reverse=True,
        )[:recent_change_limit]
        return PermissionContext(
            subject_id=subject_id,
            current_permissions=current,
            available_capabilities=capabilities,
            restrictions=restrictions,
            recent_changes=recent,
            created_at=self._clock(),
        )

    def _save_change(
        self,
        before: PermissionState,
        after: PermissionState,
        change_type: PermissionChangeType,
        reason: str,
        source: str,
    ) -> PermissionChangeResult:
        created_at = self._clock()
        record = PermissionChangeRecord(
            record_id=str(uuid4()),
            permission_id=after.permission_id,
            change_type=change_type,
            before_state=before.to_dict(),
            after_state=after.to_dict(),
            reason=reason,
            source=source,
            created_at=created_at,
        )
        self._repository.save(after, record)
        return self._result(after, record)

    @staticmethod
    def _check_revision(
        permission: PermissionState,
        expected_revision: int | None,
    ) -> None:
        if expected_revision is not None and permission.revision != expected_revision:
            raise PermissionValidationError(
                "permission revision does not match expected_revision"
            )

    @staticmethod
    def _result(
        permission: PermissionState,
        record: PermissionChangeRecord,
    ) -> PermissionChangeResult:
        summary = {
            PermissionChangeType.GRANTED: "Permission was granted.",
            PermissionChangeType.REVOKED: "Permission was revoked.",
            PermissionChangeType.LIMITED: "Permission was limited.",
            PermissionChangeType.EXPIRED: "Permission expired.",
            PermissionChangeType.STATUS_CHANGED: "Permission status changed.",
            PermissionChangeType.SCOPE_CHANGED: "Permission scope changed.",
            PermissionChangeType.CAPABILITIES_CHANGED: "Permission capabilities changed.",
        }[record.change_type]
        event = Event.create(
            occurred_at=record.created_at,
            source=record.source,
            event_type="permission_change",
            content=f"{summary} {permission.name}",
            impact_scope=[StateSection.CONTINUITY],
            mutations=[
                StateMutation(
                    field_path="continuity.recent_changes",
                    operation=ChangeOperation.APPEND,
                    value=(
                        f"Permission {permission.name}: {record.change_type.value} "
                        f"at revision {permission.revision}"
                    ),
                    reason=record.reason,
                )
            ],
            reason=record.reason,
            metadata={
                "permission_id": permission.permission_id,
                "permission_revision": permission.revision,
                "permission_change_record_id": record.record_id,
                "permission_change_type": record.change_type.value,
            },
        )
        return PermissionChangeResult(permission=permission, record=record, event=event)
