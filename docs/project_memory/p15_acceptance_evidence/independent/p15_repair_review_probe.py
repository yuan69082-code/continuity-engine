"""Additional independent repair controls, entirely disposable TEST fixtures."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import LearningValidationError, StateValidationError
from continuity_engine.domain.events import Event, StateMutation, StateSection, ChangeOperation
from continuity_engine.testing.p15_subject_fixture import P15Fixture, P15GrowthFixture
from continuity_engine.services.mind_projection_service import MindAccessError, MindVisibilityPolicy


class FixtureCase(unittest.TestCase):
    def make(self, cls):
        directory = tempfile.TemporaryDirectory(prefix='rv15-followup-')
        self.addCleanup(directory.cleanup)
        return cls(Path(directory.name))


class LifecycleFollowup(FixtureCase):
    def test_subject_intent_then_pause_resume_replays_without_state_changes(self):
        f = self.make(P15Fixture)
        f.command('CREATE')
        f.command('ACTIVATE')
        intent = f.command('SUSPEND_INTENT', identity='subject-intent', initiator='SUBJECT')
        f.command('SUSPEND')
        f.command('RESUME')
        f.reopen()
        before = f.inventory()
        self.assertEqual(f.replay('subject-intent').update_id, intent.update_id)
        self.assertEqual(f.status(), 'ACTIVE')
        self.assertEqual(f.inventory(), before)

    def test_history_command_revision_drift_rejected_zero_writes(self):
        f = self.make(P15Fixture)
        f.command('CREATE')
        f.command('ACTIVATE')
        path = f.states._repository._path_for(f.subject_id)
        document = json.loads(path.read_text(encoding='utf-8'))
        document['updates'][-1]['event']['metadata']['command']['expected_revision'] += 1
        path.write_text(json.dumps(document), encoding='utf-8')
        before = f.inventory()
        with self.assertRaises(StateValidationError):
            f.states.load(f.subject_id)
        self.assertEqual(f.inventory(), before)


class GrowthFollowup(FixtureCase):
    def setUp(self):
        self.f = self.make(P15GrowthFixture)
        self.ids = self.f.experiences()
        self.f.growth.validate(self.ids[0], self.ids[1:])

    def interrupt(self, call, stage):
        def fault(where):
            if where == stage:
                raise RuntimeError('independent controlled interruption')
        self.f.growth.fault = fault
        with self.assertRaisesRegex(RuntimeError, 'independent controlled interruption'):
            call()
        self.f.reopen()

    def unrelated(self):
        f = self.f
        event = Event.create(occurred_at=f.runtime.clock.now(), source='authorized-TEST',
            event_type='state_change', content='Later unrelated judgment', reason='TEST control',
            impact_scope=[StateSection.IDENTITY], mutations=[StateMutation(
                'identity.stable_traits', ChangeOperation.APPEND, 'later unrelated value', 'TEST control')])
        f.runtime.subject_states.apply_event(f.state.subject_id, event, expected_revision=f.state.revision)

    def test_replay_old_solidify_after_completed_rollback_does_not_reactivate(self):
        f = self.f
        solid = f.solidify(self.ids[0], identity='solid')
        trait = solid.event.metadata['trait_id']
        f.rollback(self.ids[0], trait, identity='rollback')
        f.reopen()
        before = f.inventory()
        self.assertEqual(f.replay('solid').update_id, solid.update_id)
        self.assertNotIn('consider evidence', f.state.identity.stable_traits)
        self.assertFalse(f.growth.learning.get_trait(f.state.subject_id, trait).active)
        self.assertEqual(f.inventory(), before)

    def test_committed_rollback_crash_recovers_after_revocation_once(self):
        f = self.f
        solid = f.solidify(self.ids[0], identity='solid')
        trait = solid.event.metadata['trait_id']
        self.interrupt(lambda: f.rollback(self.ids[0], trait, identity='rollback'), 'after_evolution')
        state_before = f.state.to_dict()
        f.growth_authority.revoked = True
        f.replay('rollback')
        before_second = f.inventory()
        f.replay('rollback')
        self.assertEqual(f.state.to_dict(), state_before)
        self.assertFalse(f.growth.learning.get_trait(f.state.subject_id, trait).active)
        self.assertEqual(f.inventory(), before_second)

    def test_replacement_identity_cannot_change_after_supersession_crash(self):
        f = self.f
        self.interrupt(lambda: f.solidify(self.ids[0], identity='old'), 'after_learning_record')
        self.unrelated()
        self.interrupt(lambda: f.solidify(self.ids[0], identity='replacement'), 'after_pending_superseded')
        command, credential = f.growth_commands['replacement']
        changed = replace(command, reason='Different command under reused identity')
        changed_credential = f.growth_authority.confirm(changed, 'owner', f.runtime.clock.now())
        before = f.inventory()
        with self.assertRaisesRegex(LearningValidationError, 'REPLACEMENT_IDENTITY_CONFLICT'):
            f.growth.submit(changed, changed_credential)
        self.assertEqual(f.inventory(), before)
        f.growth.submit(command, credential)
        self.assertIn('consider evidence', f.state.identity.stable_traits)
        self.assertIn('later unrelated value', f.state.identity.stable_traits)

    def test_revocation_after_preparation_blocks_evolution_until_fresh_confirmation(self):
        f = self.f
        def revoke(where):
            if where == 'after_learning_record':
                f.growth_authority.revoked = True
        f.growth.fault = revoke
        before = f.state.to_dict()
        with self.assertRaises(ValueError):
            f.solidify(self.ids[0], identity='revoked')
        self.assertEqual(f.state.to_dict(), before)
        self.assertFalse(any(t.active for t in f.growth.learning.list_traits(f.state.subject_id)))
        f.reopen()
        f.growth_authority.revoked = False
        f.solidify(self.ids[0], identity='fresh')
        self.assertIn('consider evidence', f.state.identity.stable_traits)
        with self.assertRaisesRegex(LearningValidationError, 'SUPERSEDED'):
            f.replay('revoked')


class ProjectionFollowup(FixtureCase):
    def setUp(self):
        self.f = self.make(P15GrowthFixture)
        self.f.affective_event('care', object_id='peer-a', observation='support_received')
        self.f.runtime.clock.advance(timedelta(seconds=1))
        self.f.submit(self.f.request())
        self.view = self.f.owner_projection()

    def reject_change(self, change):
        original = self.view.states.load
        calls = []
        before = self.f.inventory()
        def load(subject):
            state = original(subject)
            calls.append(subject)
            if len(calls) == 1:
                change()
            return state
        with patch.object(self.view.states, 'load', side_effect=load):
            with self.assertRaises(MindAccessError):
                self.view.read_growth('test-owner-session', allowed_objects=('peer-a',))
        self.assertEqual(self.f.inventory(), before)

    def test_visibility_policy_change_mid_read_rejects_old_details(self):
        self.reject_change(lambda: setattr(self.view, 'policy', MindVisibilityPolicy(mode='SUMMARY')))

    def test_owner_binding_change_mid_read_rejects_old_details(self):
        self.reject_change(lambda: setattr(self.view, 'owner', 'different-owner'))


if __name__ == '__main__':
    unittest.main()
