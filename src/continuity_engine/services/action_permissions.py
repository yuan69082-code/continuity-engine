from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from continuity_engine.domain.action import (
    ActionType,
    PermissionCheck,
    PermissionGrant,
)


class InMemoryPermissionProvider:
    """Read-only deterministic permission provider for tests and local composition."""

    def __init__(self, grants: Iterable[PermissionGrant] = ()) -> None:
        self._grants = list(grants)

    def check(
        self,
        permission: str,
        *,
        subject_id: str,
        action_type: ActionType,
        target: str,
        at: datetime,
    ) -> PermissionCheck:
        grants = [
            item
            for item in self._grants
            if item.permission == permission
            and item.subject_id in (subject_id, "*")
        ]
        if not grants:
            return PermissionCheck.missing(
                permission,
                "The required permission does not exist for this subject.",
            )
        grant = max(
            grants,
            key=lambda item: (
                item.subject_id == subject_id,
                not item.revoked,
                item.expires_at is None or at < item.expires_at,
                item.valid_from,
            ),
        )
        expired = grant.expires_at is not None and at >= grant.expires_at
        not_yet_valid = at < grant.valid_from
        within_scope = any(
            scope in ("*", target, action_type.value)
            for scope in grant.scopes
        )
        valid = not grant.revoked and not expired and not not_yet_valid and within_scope
        if grant.revoked:
            reason = "The required permission has been revoked."
        elif expired:
            reason = "The required permission has expired."
        elif not_yet_valid:
            reason = "The required permission is not yet valid."
        elif not within_scope:
            reason = "The action target is outside the granted permission scope."
        elif grant.requires_confirmation:
            reason = "The permission is valid but requires renewed user confirmation."
        else:
            reason = "The permission exists, is valid, and covers this action."
        return PermissionCheck(
            permission=permission,
            exists=True,
            valid=valid,
            revoked=grant.revoked,
            expired=expired,
            requires_confirmation=grant.requires_confirmation,
            within_scope=within_scope,
            reason=reason,
        )


DeterministicPermissionProvider = InMemoryPermissionProvider
