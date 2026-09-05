from __future__ import annotations

from typing import Protocol

from continuity_engine.domain.scheduling import NotificationReceipt, NotificationRequest


class NotificationAdapter(Protocol):
    """Host-neutral delivery/query port for one computation opportunity."""

    def dispatch(self, request: NotificationRequest) -> NotificationReceipt: ...

    def query(self, request: NotificationRequest) -> NotificationReceipt: ...

