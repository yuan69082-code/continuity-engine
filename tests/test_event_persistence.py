import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    StateMutation,
    StateSection,
)
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


class EventPersistenceTests(unittest.TestCase):
    def test_state_and_causal_update_survive_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            started_at = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
            clock = MutableClock(started_at)
            first_service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=clock,
            )
            first_service.create("subject-1")
            event = Event.create(
                event_id="persisted-event",
                occurred_at=started_at + timedelta(minutes=1),
                source="user",
                event_type="state_update",
                content="A new focus was selected.",
                impact_scope=[StateSection.CONTINUITY],
                mutations=[
                    StateMutation(
                        field_path="continuity.current_focus",
                        operation=ChangeOperation.APPEND,
                        value="second phase",
                        reason="The user explicitly selected the second phase.",
                    )
                ],
                reason="Preserve the new project focus across sessions.",
            )
            clock.current = started_at + timedelta(minutes=2)
            first_service.apply_event("subject-1", event)

            stored_document = json.loads(
                next(Path(directory).glob("*.json")).read_text(encoding="utf-8")
            )
            self.assertIn("state", stored_document)
            self.assertIn("updates", stored_document)

            restarted_service = SubjectStateService(JsonSubjectStateRepository(directory))
            restored = restarted_service.load("subject-1")
            history = restarted_service.get_update_history("subject-1")

            self.assertEqual(restored.continuity.current_focus, ["second phase"])
            self.assertEqual(restored.revision, 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].event.event_id, "persisted-event")
            self.assertEqual(history[0].changes[0].before, [])
            self.assertEqual(history[0].changes[0].after, ["second phase"])
            self.assertEqual(
                history[0].changes[0].reason,
                "The user explicitly selected the second phase.",
            )

    def test_same_event_cannot_be_applied_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now,
            )
            service.create("subject-1")
            event = Event.create(
                event_id="event-once",
                occurred_at=now,
                source="system",
                event_type="state_update",
                content="Set the focus once.",
                impact_scope=[StateSection.CONTINUITY],
                mutations=[
                    StateMutation(
                        field_path="continuity.current_focus",
                        operation=ChangeOperation.APPEND,
                        value="one focus",
                        reason="Test idempotency protection.",
                    )
                ],
                reason="An event must not be recorded twice.",
            )
            service.apply_event("subject-1", event)

            with self.assertRaises(StateEvolutionError):
                service.apply_event("subject-1", event)

    def test_direct_save_cannot_bypass_existing_event_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
            service = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: now,
            )
            service.create("subject-1")
            event = Event.create(
                event_id="audited-event",
                occurred_at=now,
                source="system",
                event_type="state_update",
                content="Create the first audited change.",
                impact_scope=[StateSection.CONTINUITY],
                mutations=[
                    StateMutation(
                        field_path="continuity.current_focus",
                        operation=ChangeOperation.APPEND,
                        value="audited focus",
                        reason="Establish event-backed history.",
                    )
                ],
                reason="Verify the audit boundary.",
            )
            service.apply_event("subject-1", event)
            state = service.load("subject-1")
            state.continuity.current_focus.append("unaudited focus")

            with self.assertRaises(StateEvolutionError):
                service.save(state)


if __name__ == "__main__":
    unittest.main()
