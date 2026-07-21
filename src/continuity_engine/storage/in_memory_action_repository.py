from continuity_engine.domain.action import ActionSession
from continuity_engine.domain.errors import ActionValidationError, StateNotFoundError


class InMemoryActionRepository:
    """Process-local ActionSession store for tests; no external database is used."""

    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], ActionSession] = {}

    def save_action_session(self, session: ActionSession) -> None:
        key = (session.subject_id, session.action_session_id)
        snapshot = ActionSession.from_dict(session.to_dict())
        previous = self._sessions.get(key)
        if previous is not None and previous.to_dict() != snapshot.to_dict():
            raise ActionValidationError(
                "a deterministic ActionSession cannot be overwritten with different data"
            )
        self._sessions[key] = snapshot

    def load_action_session(
        self,
        subject_id: str,
        action_session_id: str,
    ) -> ActionSession:
        session = self._sessions.get((subject_id, action_session_id))
        if session is None:
            raise StateNotFoundError(f"ActionSession not found: {action_session_id}")
        return ActionSession.from_dict(session.to_dict())

    def list_action_sessions(
        self,
        subject_id: str,
        limit: int | None = None,
    ) -> list[ActionSession]:
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ActionValidationError("ActionSession limit must be positive")
        sessions = [
            ActionSession.from_dict(item.to_dict())
            for (stored_subject_id, _), item in self._sessions.items()
            if stored_subject_id == subject_id
        ]
        sessions.sort(
            key=lambda item: (item.created_at, item.action_session_id),
            reverse=True,
        )
        return sessions[:limit] if limit is not None else sessions
