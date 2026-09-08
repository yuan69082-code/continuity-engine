"""Independent P15 adversarial tests; disposable fixture data only.

Assertions describe required behavior, not current implementation. No Engine
source, evidence, formal state, or Git metadata is changed by this module.
"""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import StateValidationError, LearningValidationError
from continuity_engine.domain.events import Event, StateSection, StateMutation, ChangeOperation
from continuity_engine.domain.subject_lifecycle import LifecycleError, LifecyclePolicy
from continuity_engine.testing.p15_subject_fixture import P15Fixture, P15GrowthFixture


class LifecyclePersistenceReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rv15-')
        self.addCleanup(self.tmp.cleanup)
        self.f = P15Fixture(Path(self.tmp.name))

    def _activate(self):
        self.f.command('CREATE')
        self.f.command('ACTIVATE')

    def _corrupt_current_only(self, change):
        repository = self.f.states._repository
        path = repository._path_for(self.f.subject_id)
        payload = json.loads(path.read_text(encoding='utf-8'))
        history = deepcopy(payload['updates'])
        change(payload['state'])
        # Simulate a truncated/old serializer output inside disposable TEST.
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(history, json.loads(path.read_text(encoding='utf-8'))['updates'])

    def test_suspended_history_cannot_downgrade_to_legacy_by_missing_field(self):
        self._activate()
        self.f.command('SUSPEND')
        self._corrupt_current_only(lambda state: state['temporal'].pop('subject_lifecycle'))
        with self.assertRaises((StateValidationError, LifecycleError)):
            self.f.states.require_active(self.f.subject_id, 'TEST')

    def test_deleted_history_cannot_be_reopened_by_stale_active_projection(self):
        self._activate()
        active = deepcopy(self.f.state().temporal.subject_lifecycle)
        self.f.policy = LifecyclePolicy(archive_configured=True, delete_retention_seconds=0,
                                       allow_test_logical_delete=True)
        self.f.reopen()
        self.f.command('ARCHIVE')
        self.f.command('DELETE')
        self._corrupt_current_only(lambda state: state['temporal'].__setitem__('subject_lifecycle', active))
        with self.assertRaises((StateValidationError, LifecycleError)):
            self.f.states.require_active(self.f.subject_id, 'TEST')

    def test_unmodified_suspended_state_stays_blocked(self):
        self._activate()
        self.f.command('SUSPEND')
        self.f.reopen()
        with self.assertRaisesRegex(LifecycleError, 'NOT_ACTIVE'):
            self.f.states.require_active(self.f.subject_id, 'TEST')

    def test_genuine_legacy_without_lifecycle_history_stays_compatible(self):
        self.f.states.create(self.f.subject_id)
        state = self.f.states.require_active(self.f.subject_id, 'TEST')
        self.assertIsNone(state.temporal.subject_lifecycle)


class GrowthRecoveryReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rg15-')
        self.addCleanup(self.tmp.cleanup)
        self.f = P15GrowthFixture(Path(self.tmp.name))

    def test_pending_growth_can_be_reauthorized_after_unrelated_revision(self):
        f = self.f
        ids = f.experiences()
        f.growth.validate(ids[0], ids[1:])
        class Interrupted(BaseException):
            pass
        def interrupt(stage):
            if stage == 'after_learning_record':
                raise Interrupted()
        f.growth.fault = interrupt
        with self.assertRaises(Interrupted):
            f.solidify(ids[0], identity='interrupted-command')
        self.assertNotIn('consider evidence', f.state.identity.stable_traits)
        f.reopen()
        event = Event.create(occurred_at=f.runtime.clock.now(), source='authorized-test-control',
            event_type='state_change', content='An unrelated valid judgment arrived',
            impact_scope=[StateSection.IDENTITY], reason='Independent authorized test state change',
            mutations=[StateMutation('identity.stable_traits', ChangeOperation.APPEND,
                                     'unrelated later trait', 'Independent authorized change')])
        f.runtime.subject_states.apply_event(f.state.subject_id, event, expected_revision=f.state.revision)
        with self.assertRaises(LearningValidationError):
            f.replay('interrupted-command')  # An old expected revision must not bypass validation.
        # A fresh command has fresh confirmation and the current revision. The
        # old unfinished record must not permanently poison future legal growth.
        caught = None
        try:
            f.solidify(ids[0], identity='fresh-confirmed-command')
        except LearningValidationError as error:
            caught = str(error)
        print(json.dumps({'probe': 'pending_growth_after_revision', 'fresh_error': caught,
                          'state_traits': f.state.identity.stable_traits,
                          'active_learning_traits': [t.current_value for t in f.growth.learning.list_traits(f.state.subject_id)]}))
        self.assertIsNone(caught, 'fresh authorized recovery is blocked by an uncommitted active consolidation')
        self.assertIn('consider evidence', f.state.identity.stable_traits)
        self.assertIn('unrelated later trait', f.state.identity.stable_traits)


class GrowthVisibilityReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rg15-')
        self.addCleanup(self.tmp.cleanup)
        self.f = P15GrowthFixture(Path(self.tmp.name))
        self.f.affective_event('care', object_id='peer-a', observation='support_received')
        self.f.runtime.clock.advance(timedelta(seconds=1))
        self.f.submit(self.f.request())
        self.assertIsNotNone(self.f.state.relationship.objects, 'fixture must actually form relationship data')
        self.view = self.f.owner_projection()

    def _revoke_after_state_read(self):
        original = self.view.states.load
        subject = self.f.state.subject_id
        triggered = False
        def load(subject_id):
            nonlocal triggered
            state = original(subject_id)
            if not triggered:
                triggered = True
                self.f.view_permissions.revoke_permission(subject, 'p14-test-owner-read',
                    source='independent-test-owner', reason='Revoked while projection was loading')
            return state
        return load

    def test_growth_projection_rechecks_revocation_before_returning_details(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        with patch.object(self.view.states, 'load', side_effect=self._revoke_after_state_read()):
            with self.assertRaises(MindAccessError):
                self.view.read_growth('test-owner-session', allowed_objects=('peer-a',))

    def test_existing_mind_projection_rechecks_same_revocation(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        with patch.object(self.view.states, 'load', side_effect=self._revoke_after_state_read()):
            with self.assertRaises(MindAccessError):
                self.view.read('test-owner-session')

    def test_unchanged_permission_allows_growth_without_state_writes(self):
        before = self.f.inventory()
        value = self.view.read_growth('test-owner-session', allowed_objects=('peer-a',))
        self.assertEqual(value['relationships']['entries'][0]['object_id'], 'peer-a')
        self.assertEqual(before, self.f.inventory())


if __name__ == '__main__':
    unittest.main(verbosity=2)
