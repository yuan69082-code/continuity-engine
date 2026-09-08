"""P14 confirmed R1/R2 regressions; independent probe assertions preserved.

Source and hash: docs/project_memory/p14_repair_evidence/before.json.
The two unconfirmed exploratory API assumptions are deliberately not imported.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.services.dynamic_mind_service import MindDynamics, MindCognition


class P14ReviewRepairTests(unittest.TestCase):
    def fixture(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from continuity_engine.domain.context_composition import ContextBudget
        temp = tempfile.TemporaryDirectory(prefix='p14i-')
        self.addCleanup(temp.cleanup)
        fixture = P14Fixture(Path(temp.name))
        fixture.core.context_budget = ContextBudget(token_limit=3000)
        return fixture

    def experience(self, fixture, identity, observation):
        fixture.runtime.clock.advance(timedelta(minutes=1))
        fixture.affective_event(identity, object_id='peer', observation=observation)
        fixture.runtime.clock.advance(timedelta(seconds=1))
        request = fixture.request()
        fixture.submit(request)
        return request

    def test_new_harm_is_not_resolved_by_old_pre_harm_support(self):
        f = self.fixture()
        for n in (1, 2):
            self.experience(f, 'old-support-' + str(n), 'expectation_met')
        request = self.experience(f, 'new-harm-after-support', 'boundary_crossed')
        episode = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')
        self.assertNotEqual(episode['status'], 'resolved',
            'A newly appraised harm was resolved using only support predating that harm: ' + repr(episode['resolution']))

    def test_reopened_harm_is_not_resolved_by_previous_repair_evidence(self):
        f = self.fixture()
        self.experience(f, 'harm-first', 'boundary_crossed')
        for n in (1, 2):
            self.experience(f, 'repair-first-' + str(n), 'expectation_met')
        episode = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')
        self.assertEqual(episode['status'], 'resolved', 'Positive control: earlier concern must resolve first')
        self.experience(f, 'harm-again', 'boundary_crossed')
        reopened = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['id'] == episode['id'])
        self.assertEqual(reopened['status'], 'unresolved',
            'Old repair evidence immediately re-resolved a new harm: ' + repr(reopened['resolution']))

    def test_subsequent_independent_support_still_resolves(self):
        f = self.fixture()
        self.experience(f, 'control-harm', 'boundary_crossed')
        for n in (1, 2):
            self.experience(f, 'control-support-' + str(n), 'expectation_met')
        episode = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')
        self.assertEqual(episode['status'], 'resolved')

    def test_projection_mutation_does_not_write_through(self):
        f = self.fixture()
        f.runtime.clock.advance(timedelta(hours=1))
        f.opportunity('projection-origin')
        before = f.state.to_dict()
        view = f.owner_projection()
        result = view.read('test-owner-session')
        result['mind']['thoughts'][0]['content'] = 'A client-side edit is not state authority'
        self.assertEqual(before, f.state.to_dict())

    def test_revocation_during_history_read_prevents_return(self):
        from unittest.mock import patch
        from continuity_engine.services.mind_projection_service import MindAccessError
        f = self.fixture()
        f.runtime.clock.advance(timedelta(hours=1)); f.opportunity('revoke-origin')
        view = f.owner_projection()
        original = view.states.get_update_history
        def revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            f.revoke_owner_view()
            return result
        with patch.object(view.states, 'get_update_history', side_effect=revoke):
            with self.assertRaises(MindAccessError):
                view.read('test-owner-session')

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

    @staticmethod
    def anger(f):
        return next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')

    def test_reopen_reload_repeat_then_new_support_resolves(self):
        f = self.fixture()
        self.experience(f, 'hurt-1', 'boundary_crossed')
        for n in (1, 2):
            self.experience(f, 'support-old-' + str(n), 'expectation_met')
        original = deepcopy(self.anger(f))
        self.assertEqual(original['status'], 'resolved')
        self.experience(f, 'hurt-2', 'boundary_crossed')
        basis = deepcopy(self.anger(f)['concern_basis'])
        f.reopen()
        # Reopen constructs the core again; retain this test's explicit input
        # budget rather than silently returning to the smaller fixture default.
        from continuity_engine.domain.context_composition import ContextBudget
        f.core.context_budget = ContextBudget(token_limit=3000)
        for _ in range(2):
            f.runtime.clock.advance(timedelta(seconds=1))
            f.submit(f.request())
            self.assertEqual(self.anger(f)['status'], 'unresolved')
            self.assertEqual(self.anger(f)['concern_basis'], basis)
        for n in (1, 2):
            self.experience(f, 'support-new-' + str(n), 'expectation_met')
        final = self.anger(f)
        self.assertEqual(final['id'], original['id'])
        self.assertEqual(final['status'], 'resolved')
        self.assertEqual(set(final['resolution']['source_keys']), {'event:support-new-1', 'event:support-new-2'})
        self.assertTrue(set(original['source_keys']) <= set(final['source_keys']))

    def test_batched_composer_uses_event_order_not_fragment_or_processing_order(self):
        f = self.fixture()
        for identity, observation in [('batch-harm', 'boundary_crossed'),
                                      ('batch-support-1', 'expectation_met'),
                                      ('batch-support-2', 'expectation_met')]:
            f.runtime.clock.advance(timedelta(minutes=1))
            f.affective_event(identity, object_id='peer', observation=observation)
        f.runtime.clock.advance(timedelta(seconds=1))
        request = f.request(); f.submit(request)
        self.assertEqual(self.anger(f)['status'], 'resolved')
        context = f.context(request)
        cognition = MindCognition(f.core)
        reversed_composition = SimpleNamespace(snapshot=SimpleNamespace(
            fragments=tuple(reversed(context.composition.snapshot.fragments))))
        reversed_result = cognition.finalize(context.mind, reversed_composition)
        original_result = cognition.finalize(context.mind, context.composition)
        self.assertEqual(reversed_result['proposal'], original_result['proposal'])

    def test_same_root_memory_raw_is_one_support_and_cannot_raise_confidence(self):
        from continuity_engine.domain.context_composition import ContextAuthority
        f = self.fixture()
        self.experience(f, 'dedup-harm', 'boundary_crossed')
        request = self.experience(f, 'dedup-support', 'expectation_met')
        context = f.context(request)
        fragments = context.composition.snapshot.fragments
        one = next(x for x in fragments if 'event:dedup-support' in x.provenance_roots)
        content = one.content.removeprefix('interaction: ')
        raw = replace(one, source_id='engine.timeline', stable_source_id='dedup-support',
                      authority=ContextAuthority.RAW_SOURCE, content=content, confidence=1.0)
        memory = replace(one, source_id='engine.memory', authority=ContextAuthority.CONFIRMED_MEMORY,
                         content='interaction: ' + content, confidence=0.2)
        composed = SimpleNamespace(snapshot=SimpleNamespace(fragments=(raw, memory)))
        result = MindCognition(f.core).finalize(context.mind, composed)
        episode = next(e for e in result['proposal']['episodes'] if e['kind']=='anger')
        self.assertEqual(episode['status'], 'processing')
        self.assertEqual(episode['resolution']['source_keys'], ['event:dedup-support'])
        # Two current roots still cannot resolve when their actual consumed
        # confidence sum is below this concern's intensity.
        other = replace(memory, provenance_roots=('event:independent-low',), stable_source_id='independent-low')
        low = SimpleNamespace(snapshot=SimpleNamespace(fragments=(memory, other)))
        result = MindCognition(f.core).finalize(context.mind, low)
        self.assertEqual(next(e for e in result['proposal']['episodes'] if e['kind']=='anger')['status'], 'processing')

    def test_equal_time_support_is_not_proof_of_subsequent_repair(self):
        f = self.fixture()
        f.runtime.clock.advance(timedelta(minutes=1))
        for identity, observation in [('tie-harm', 'boundary_crossed'),
                                      ('tie-support-1', 'expectation_met'), ('tie-support-2', 'expectation_met')]:
            f.affective_event(identity, object_id='peer', observation=observation)
        f.runtime.clock.advance(timedelta(seconds=1)); f.submit(f.request())
        self.assertEqual(self.anger(f)['status'], 'unresolved')

    def test_legacy_episode_mapping_and_new_basis_validation(self):
        from continuity_engine.domain.dynamic_mind import MindValidationError
        f = self.fixture(); self.experience(f, 'legacy-harm', 'boundary_crossed')
        state = deepcopy(f.state.intentions.dynamic_mind)
        for e in state['episodes']: e.pop('concern_basis', None)
        self.assertEqual(MindState.from_dict(state).to_dict(), state)
        for basis in ({'source_key':'event:unbound','occurred_at':state['updated_at']},
                      {'source_key':'event:legacy-harm','occurred_at':'2099-01-01T00:00:00Z'}):
            changed=deepcopy(state); changed['episodes'][0]['concern_basis']=basis
            with self.assertRaises(MindValidationError): MindState.from_dict(changed)

    def test_transform_list_order_continuous_trajectory_will_and_thought_bindings(self):
        dynamics=MindDynamics(); at=datetime(2026,9,8,tzinfo=timezone.utc)
        first=dynamics.advance(MindState.create('subject','TEST',at),at=at+timedelta(hours=1)).state
        transformed=dynamics.advance(first,at=first.updated_at,outcomes=[{
            'desire_id':'desire:intimacy','phase':'transform','new_drive':'exploration','reason':'Seek understanding'}]).state
        a=MindState.from_dict(transformed.to_dict())
        b=replace(a,desires=list(reversed(deepcopy(a.desires))))
        for hour in (2,3,4):
            a=dynamics.advance(a,at=at+timedelta(hours=hour)).state
            b=dynamics.advance(MindState.from_dict(b.to_dict()),at=at+timedelta(hours=hour)).state
            for name, identity in [('desires','id'),('will','desire_id'),('thoughts','id')]:
                self.assertEqual({v[identity]:v for v in getattr(a,name)}, {v[identity]:v for v in getattr(b,name)})
            for identity in ('desire:intimacy','desire:exploration'):
                desire=next(d for d in a.desires if d['id']==identity)
                self.assertEqual(desire['updated_at'],a.to_dict()['updated_at'])
                self.assertEqual(desire['trajectory'][-1]['at'],a.to_dict()['updated_at'])
                self.assertEqual(desire['strength'],a.drives['exploration'])
                self.assertTrue(any(w['desire_id']==identity for w in a.will))
                thought=next(t for t in a.thoughts if t['desire_ids']==[identity])
                self.assertEqual(thought['last_recurred_at'],a.to_dict()['updated_at'])
            self.assertEqual(len([d for d in a.desires if d['drive']=='exploration']),2)
