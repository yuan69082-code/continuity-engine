from continuity_engine.storage.base import ActionRepository


class RepositoryActionSessionProvider:
    """Expose the latest ActionSession through the interface read port."""

    def __init__(self, repository: ActionRepository) -> None:
        self._repository = repository

    def get_latest_action_session(self, subject_id: str):
        sessions = self._repository.list_action_sessions(subject_id, limit=1)
        return sessions[0] if sessions else None

