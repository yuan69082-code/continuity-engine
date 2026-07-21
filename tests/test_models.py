import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.errors import StateValidationError
from continuity_engine.domain.models import SubjectState


class SubjectStateModelTests(unittest.TestCase):
    def test_round_trip_preserves_all_six_state_sections(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        state = SubjectState.create("subject-1", now=now)
        state.identity.stable_traits.append("curious")
        state.relationship.current_status = "collaborating"
        state.continuity.unfinished_items.append("finish phase one")
        state.temporal.lifecycle_events.append("created")
        state.intentions.action_tendencies.append("verify before acting")
        state.emotion_state.emotions.append("focused")

        restored = SubjectState.from_dict(state.to_dict())

        self.assertEqual(restored.to_dict(), state.to_dict())

    def test_seconds_since_last_interaction_is_derived_from_timestamp(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        state = SubjectState.create("subject-1", now=now)
        state.temporal.last_interaction_at = now

        elapsed = state.temporal.seconds_since_last_interaction(now + timedelta(seconds=45))

        self.assertEqual(elapsed, 45.0)

    def test_subject_id_must_not_be_blank(self) -> None:
        with self.assertRaises(StateValidationError):
            SubjectState.create("   ")


if __name__ == "__main__":
    unittest.main()

