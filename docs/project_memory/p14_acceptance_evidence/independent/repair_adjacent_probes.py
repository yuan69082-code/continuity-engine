"""Additional independent temporal and identity checks around P14 R1/R2."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
import unittest

from continuity_engine.domain.dynamic_mind import MindState, timestamp
from continuity_engine.services.dynamic_mind_service import MindDynamics, MindCognition
from review_probes import P14ReviewProbes


class P14RepairAdjacentProbes(unittest.TestCase):
    fixture = P14ReviewProbes.fixture
    experience = P14ReviewProbes.experience

    def delayed_event(self, f, identity, observation, occurred_at):
        from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, StateSection
        now = f.runtime.clock.now()
        event = Event.create(event_id=identity, occurred_at=occurred_at, observed_at=now, recorded_at=now,
                             source='p14.independent-review', source_kind=EventSourceKind.TEST,
                             event_type='experienced_interaction', classification=EventClassification.INTERACTION,
                             impact_scope=[StateSection.RELATIONSHIP, StateSection.CONTINUITY], mutations=[],
                             reason='TEST experience arriving later than it occurred.',
                             content=json.dumps({'experienced': {'object': 'peer', 'observation': observation,
                                                                 'expectation': 'mutual respect', 'consequence': observation,
                                                                 'impact': 0.7}}))
        f.runtime.subject_states.apply_event(f.state.subject_id, event)

    @staticmethod
    def anger(f):
        return next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')

    def test_late_arriving_old_support_does_not_become_new_repair(self):
        f = self.fixture()
        old_time = f.runtime.clock.now()
        self.experience(f, 'latest-harm', 'boundary_crossed')
        basis = deepcopy(self.anger(f)['concern_basis'])
        for n in (1, 2):
            f.runtime.clock.advance(timedelta(minutes=1))
            self.delayed_event(f, 'late-old-support-' + str(n), 'expectation_met', old_time)
            f.runtime.clock.advance(timedelta(seconds=1))
            f.submit(f.request())
        self.assertEqual(self.anger(f)['status'], 'unresolved')
        self.assertEqual(self.anger(f)['concern_basis'], basis)

    def test_late_older_harm_does_not_regress_latest_concern_basis(self):
        f = self.fixture()
        old_time = f.runtime.clock.now()
        self.experience(f, 'anchor-harm', 'boundary_crossed')
        basis = deepcopy(self.anger(f)['concern_basis'])
        f.runtime.clock.advance(timedelta(minutes=1))
        self.delayed_event(f, 'late-older-harm', 'boundary_crossed', old_time)
        f.runtime.clock.advance(timedelta(seconds=1))
        f.submit(f.request())
        self.assertIn('event:late-older-harm', self.anger(f)['source_keys'])
        self.assertEqual(self.anger(f)['concern_basis'], basis)

    def test_legacy_without_basis_still_allows_new_support(self):
        f = self.fixture()
        self.experience(f, 'legacy-negative', 'boundary_crossed')
        self.experience(f, 'legacy-fresh-1', 'expectation_met')
        request = self.experience(f, 'legacy-fresh-2', 'expectation_met')
        context = f.context(request)
        captured = deepcopy(context.mind)
        for episode in captured['base']['episodes']:
            episode.pop('concern_basis', None)
        legacy = MindState.from_dict(captured['base'])
        self.assertEqual(legacy.to_dict(), captured['base'], 'Reading must not fabricate missing history')
        before = f.state.to_dict()
        result = MindCognition(f.core).finalize(captured, context.composition)
        anger = next(e for e in result['proposal']['episodes'] if e['kind'] == 'anger')
        self.assertEqual(anger['status'], 'resolved')
        self.assertEqual(set(anger['resolution']['source_keys']), {'event:legacy-fresh-1', 'event:legacy-fresh-2'})
        self.assertEqual(before, f.state.to_dict(), 'Pure candidate computation cannot commit state')

    def test_three_distinct_desires_survive_transform_reload_and_order_change(self):
        dynamics = MindDynamics()
        at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        first = dynamics.advance(MindState.create('subject', 'TEST', at), at=at + timedelta(hours=1)).state
        changed = dynamics.advance(first, at=first.updated_at, outcomes=[
            {'desire_id': 'desire:intimacy', 'phase': 'transform', 'new_drive': 'exploration', 'reason': 'Understand connection'},
            {'desire_id': 'desire:solitude', 'phase': 'transform', 'new_drive': 'exploration', 'reason': 'Explore independently'}]).state
        left = MindState.from_dict(changed.to_dict())
        right = replace(left, desires=list(reversed(deepcopy(left.desires))))
        for hour in (2, 3):
            left = dynamics.advance(left, at=at + timedelta(hours=hour)).state
            right = dynamics.advance(MindState.from_dict(right.to_dict()), at=at + timedelta(hours=hour)).state
            self.assertEqual({d['id']: d for d in left.desires}, {d['id']: d for d in right.desires})
            peers = [d for d in left.desires if d['drive'] == 'exploration']
            self.assertEqual({d['id'] for d in peers}, {'desire:intimacy', 'desire:exploration', 'desire:solitude'})
            for desire in peers:
                self.assertEqual(desire['updated_at'], timestamp(left.updated_at))
                self.assertEqual(desire['strength'], left.drives['exploration'])


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(P14RepairAdjacentProbes)


if __name__ == '__main__':
    unittest.main()
