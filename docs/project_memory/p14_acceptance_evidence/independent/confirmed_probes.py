"""Narrow review findings and controls; exclude two unproven API assumptions."""
from datetime import datetime, timedelta, timezone
import json
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.services.dynamic_mind_service import MindDynamics
from review_probes import P14ReviewProbes


class P14ConfirmedProbes(unittest.TestCase):
    fixture = P14ReviewProbes.fixture
    experience = P14ReviewProbes.experience
    test_new_harm_is_not_resolved_by_old_pre_harm_support = P14ReviewProbes.test_new_harm_is_not_resolved_by_old_pre_harm_support
    test_reopened_harm_is_not_resolved_by_previous_repair_evidence = P14ReviewProbes.test_reopened_harm_is_not_resolved_by_previous_repair_evidence
    test_subsequent_independent_support_still_resolves = P14ReviewProbes.test_subsequent_independent_support_still_resolves
    test_projection_mutation_does_not_write_through = P14ReviewProbes.test_projection_mutation_does_not_write_through
    test_revocation_during_history_read_prevents_return = P14ReviewProbes.test_revocation_during_history_read_prevents_return

    def test_transform_keeps_both_desires_evolving_after_reload(self):
        dynamics = MindDynamics()
        at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        first = dynamics.advance(MindState.create('subject', 'TEST', at), at=at + timedelta(hours=1)).state
        before = {d['drive']: d for d in first.desires}
        transformed = dynamics.advance(first, at=first.updated_at, outcomes=[{
            'desire_id': before['intimacy']['id'], 'phase': 'transform',
            'new_drive': 'exploration', 'reason': 'Closeness turns into a wish to understand'}]).state
        reloaded = MindState.from_dict(transformed.to_dict())
        later = dynamics.advance(reloaded, at=at + timedelta(hours=2)).state
        later = dynamics.advance(later, at=at + timedelta(hours=3)).state
        matched = {d['id']: d for d in later.desires if d['drive'] == 'exploration'}
        self.assertEqual(len(matched), 2, 'Both stable identities must remain represented')
        print(json.dumps({'probe': 'transform-after-reload', 'at': later.to_dict()['updated_at'],
                          'drive': later.drives['exploration'], 'desires': matched}, ensure_ascii=False))
        original = matched[before['exploration']['id']]
        self.assertNotEqual(original['strength'], before['exploration']['strength'],
                            'A still-active desire remained numerically frozen across two elapsed opportunities')
        self.assertEqual(original['updated_at'], later.to_dict()['updated_at'])

    def test_control_without_transform_updates_all_active_desires(self):
        dynamics = MindDynamics()
        at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        first = dynamics.advance(MindState.create('subject', 'TEST', at), at=at + timedelta(hours=1)).state
        later = dynamics.advance(MindState.from_dict(first.to_dict()), at=at + timedelta(hours=3)).state
        old = {d['id']: d for d in first.desires}
        for desire in later.desires:
            with self.subTest(desire=desire['id']):
                self.assertEqual(desire['updated_at'], later.to_dict()['updated_at'])
                self.assertNotEqual(desire['strength'], old[desire['id']]['strength'])


def load_tests(loader, tests, pattern):
    # Imported exploratory TestCase is a helper, not part of this final matrix.
    return loader.loadTestsFromTestCase(P14ConfirmedProbes)


if __name__ == '__main__':
    unittest.main()
