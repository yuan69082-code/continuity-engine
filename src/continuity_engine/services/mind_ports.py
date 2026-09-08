"""Host-neutral identity port; no authentication database or credentials here."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerifiedMindReader:
    principal_id: str
    subject_id: str
    environment: str


class MindReaderIdentityPort(Protocol):
    def resolve(self, session_handle: str) -> VerifiedMindReader | None:
        """Resolve an already authenticated host session, never a claimed role."""
        ...
