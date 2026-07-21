import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.evolution import SubjectStateEvolver
from continuity_engine.domain.models import SubjectState


class SubjectStateEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.started_at = datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc)
        self.state = SubjectState.create("subject-1", now=self.started_at)
        self.state.relationship.current_status = "new"

    def test_event_produces_new_state_and_auditable_differences(self) -> None:
        event = Event.create(
            event_id="event-1",
            occurred_at=self.started_at + timedelta(minutes=5),
            source="user",
            event_type="interaction",
            content="The user confirmed the second phase should begin.",
            impact_scope=[
                StateSection.RELATIONSHIP,
                StateSection.CONTINUITY,
                StateSection.TEMPORAL,
            ],
            mutations=[
                StateMutation(
                    field_path="relationship.current_status",
                    operation=ChangeOperation.SET,
                    value="active collaboration",
                    reason="The user continued the project into a new phase.",
                ),
                StateMutation(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    value="build state evolution",
                    reason="The event established the next active focus.",
                ),
            ],
            reason="The project moved from state storage to state evolution.",
        )

        result = SubjectStateEvolver().evolve(
            self.state,
            event,
            applied_at=self.started_at + timedelta(minutes=6),
        )

        self.assertEqual(self.state.relationship.current_status, "new")
        self.assertEqual(self.state.revision, 0)
        self.assertEqual(result.state.relationship.current_status, "active collaboration")
        self.assertEqual(result.state.continuity.current_focus, ["build state evolution"])
        self.assertEqual(result.state.temporal.last_interaction_at, event.occurred_at)
        self.assertEqual(result.state.revision, 1)
        self.assertEqual(result.update.before_revision, 0)
        self.assertEqual(result.update.after_revision, 1)
        self.assertEqual(result.update.event.event_id, "event-1")
        self.assertEqual(result.update.reason, event.reason)

        changes = {change.field_path: change for change in result.update.changes}
        self.assertEqual(changes["relationship.current_status"].before, "new")
        self.assertEqual(changes["relationship.current_status"].after, "active collaboration")
        self.assertIn("continuity.current_focus", changes)
        self.assertIn("temporal.last_interaction_at", changes)
        self.assertIn("temporal.updated_at", changes)

    def test_event_cannot_change_field_outside_impact_scope(self) -> None:
        event = Event.create(
            event_id="event-2",
            occurred_at=self.started_at,
            source="system",
            event_type="state_update",
            content="Invalid cross-scope update.",
            impact_scope=[StateSection.IDENTITY],
            mutations=[
                StateMutation(
                    field_path="relationship.current_status",
                    operation=ChangeOperation.SET,
                    value="changed",
                    reason="Test invalid scope.",
                )
            ],
            reason="Verify the domain boundary.",
        )

        with self.assertRaises(StateEvolutionError):
            SubjectStateEvolver().evolve(self.state, event, applied_at=self.started_at)


if __name__ == "__main__":
    unittest.main()

