import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.errors import StateAlreadyExistsError
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


class SubjectStateServiceTests(unittest.TestCase):
    def test_create_save_load_and_record_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            start = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
            clock = MutableClock(start)
            service = SubjectStateService(JsonSubjectStateRepository(directory), clock=clock)

            state = service.create("subject-1")
            state.continuity.current_focus.append("phase one")
            clock.current = start + timedelta(minutes=5)
            service.save(state)
            clock.current = start + timedelta(minutes=10)
            service.record_interaction("subject-1")
            restored = service.load("subject-1")

            self.assertEqual(restored.continuity.current_focus, ["phase one"])
            self.assertEqual(restored.temporal.updated_at, clock.current)
            self.assertEqual(restored.temporal.last_interaction_at, clock.current)

    def test_create_rejects_duplicate_subject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SubjectStateService(JsonSubjectStateRepository(directory))
            service.create("subject-1")

            with self.assertRaises(StateAlreadyExistsError):
                service.create("subject-1")


if __name__ == "__main__":
    unittest.main()

