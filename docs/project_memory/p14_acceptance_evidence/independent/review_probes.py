"""Independent P14 adversarial and positive-control probes, isolated TEST only."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.services.dynamic_mind_service import MindDynamics


class P14ReviewProbes(unittest.TestCase):
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

    def test_same_timestamp_regulation_replay_does_not_repeat_effect(self):
        dynamics = MindDynamics()
        at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        first = dynamics.advance(MindState.create('subject', 'TEST', at), at=at + timedelta(minutes=1)).state
        intent = {'strategy': 'suppress', 'desire_id': first.desires[0]['id'], 'reason': 'Same explicit internal attempt'}
        once = dynamics.advance(first, at=first.updated_at, regulation=intent).state
        twice = dynamics.advance(once, at=once.updated_at, regulation=intent).state
        self.assertEqual(once.to_dict(), twice.to_dict(), 'Same internal attempt at the same instant compounded its effect')

    def test_transformed_and_existing_desires_both_continue(self):
        dynamics = MindDynamics()
        at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        first = dynamics.advance(MindState.create('subject', 'TEST', at), at=at + timedelta(hours=1)).state
        existing = next(d for d in first.desires if d['drive'] == 'exploration')
        original = next(d for d in first.desires if d['drive'] == 'intimacy')
        transformed = dynamics.advance(first, at=first.updated_at, outcomes=[{
            'desire_id': original['id'], 'phase': 'transform', 'new_drive': 'exploration',
            'reason': 'Closeness turns into a wish to understand'}]).state
        later = dynamics.advance(transformed, at=transformed.updated_at + timedelta(hours=1)).state
        surviving = next(d for d in later.desires if d['id'] == existing['id'])
        self.assertEqual(surviving['updated_at'], later.to_dict()['updated_at'],
            'Existing exploration desire was starved by another desire transforming into its drive')

    def test_native_completed_replay_checks_current_request_depth(self):
        from continuity_engine.domain.thinking import ThinkingDepth
        from continuity_engine.services.wake_perception_thinking_action_service import WakePerceptionThinkingActionService
        f = self.fixture()
        f.runtime.clock.advance(timedelta(hours=1))
        f.opportunity('depth-bound-session')
        original = f.app.adapter._service
        service = WakePerceptionThinkingActionService(original._awakening, original._perception,
            original._thinking, original._action, original._subject_states,
            available_permissions=original._available_permissions, resource_limits=original._resource_limits,
            clock=f.runtime.clock.now, continuity_core=f.core)
        before = f.state.to_dict()
        with self.assertRaises(ValueError):
            service.wake_manual(f.app.binding.cycle_id, detail='Authorized native P14 computation opportunity.',
                                session_id='depth-bound-session', depth=ThinkingDepth.DEEP)
        self.assertEqual(before, f.state.to_dict())

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


if __name__ == '__main__':
    unittest.main()
