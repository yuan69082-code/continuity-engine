"""Trusted host-neutral management ports, distinct from frozen external Binding."""
from typing import Protocol


class LifecycleAuthority(Protocol):
    def identify(self, command, credential) -> str:
        """Verify immutable principal/command binding, including historical replay."""
        ...

    def authorize(self, command, credential, *, at) -> str:
        """Recheck current scope, confirmation and expiry for a NEW transition."""
        ...


class SubjectSelectionPort(Protocol):
    def select(self, *, subject_id, environment, principal_id) -> None: ...
    def unbind(self, *, principal_id) -> None: ...

