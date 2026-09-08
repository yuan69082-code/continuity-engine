"""P15-R1/R2/R3 adjacent contracts; only disposable isolated data."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import StateValidationError, StateEvolutionError, LearningValidationError
from continuity_engine.domain.events import Event, StateMutation, StateSection, ChangeOperation
from continuity_engine.domain.subject_lifecycle import LifecycleError
from continuity_engine.testing.p15_subject_fixture import P15Fixture, P15GrowthFixture


class LifecycleArchiveRepairTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='lr15-');self.addCleanup(temp.cleanup)
        self.f=P15Fixture(Path(temp.name));self.f.command('CREATE');self.f.command('ACTIVATE')

    def corrupt_and_reject(self,edit):
        f=self.f;path=f.states._repository._path_for(f.subject_id)
        document=json.loads(path.read_text(encoding='utf-8'));edit(document)
        path.write_text(json.dumps(document),encoding='utf-8');before=f.inventory()
        with self.assertRaises((LifecycleError,StateValidationError)):f.states.load(f.subject_id)
        with self.assertRaises((LifecycleError,StateValidationError)):f.states.get_update_history(f.subject_id)
        self.assertEqual(before,f.inventory())

    def test_current_owner_environment_and_subject_tampering_rejected_without_writes(self):
        path=self.f.states._repository._path_for(self.f.subject_id);original=path.read_bytes()
        for key,value in [('owner_principal_id','other'),('environment','RESEARCH'),('subject_id','other')]:
            with self.subTest(key=key):
                path.write_bytes(original)
                self.corrupt_and_reject(lambda d:d['state']['temporal']['subject_lifecycle'].__setitem__(key,value))

    def test_event_and_change_lifecycle_disagreement_rejected(self):
        self.corrupt_and_reject(lambda d:d['updates'][-1]['changes'][0]['after'].__setitem__('status','SUSPENDED'))

    def test_lifecycle_change_before_value_must_follow_original_history(self):
        self.f.command('SUSPEND')
        self.corrupt_and_reject(lambda d:d['updates'][-1]['changes'][0]['before'].__setitem__('owner_principal_id','other'))

    def test_history_command_identity_cannot_rebind_owner(self):
        self.corrupt_and_reject(lambda d:d['updates'][-1]['event']['metadata'].__setitem__('principal_id','other'))

    def test_direct_save_rejects_current_snapshot_with_missing_lifecycle(self):
        f=self.f;f.command('SUSPEND');state=f.state();before=f.inventory()
        state.temporal.subject_lifecycle=None
        with self.assertRaises((StateValidationError,StateEvolutionError)):f.states._repository.save(state)
        self.assertEqual(before,f.inventory())

    def test_true_legacy_can_introduce_lifecycle_and_replay_after_resume(self):
        f=self.f
        temp=tempfile.TemporaryDirectory(prefix='old15-');self.addCleanup(temp.cleanup)
        f=P15Fixture(Path(temp.name));f.states.create(f.subject_id)
        suspended=f.command('SUSPEND',identity='pause');f.reopen();f.command('RESUME')
        revision=f.state().revision
        self.assertEqual(f.replay('pause').update_id,suspended.update_id)
        self.assertEqual(f.state().revision,revision);self.assertEqual(f.status(),'ACTIVE')

    def test_ordinary_legacy_event_type_name_is_not_lifecycle_authority(self):
        temp=tempfile.TemporaryDirectory(prefix='old15-');self.addCleanup(temp.cleanup)
        f=P15Fixture(Path(temp.name));f.states.create(f.subject_id)
        event=Event.create(occurred_at=f.clock(),source='legacy-observation',event_type='subject_lifecycle',
            content='Ordinary legacy description, not a management command',reason='legacy control',
            impact_scope=[StateSection.CONTINUITY],mutations=[])
        f.states.apply_event(f.subject_id,event);before=f.inventory();f.reopen()
        self.assertIsNone(f.states.require_active(f.subject_id).temporal.subject_lifecycle)
        self.assertEqual(before,f.inventory())


class PendingGrowthRepairTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='pr15-');self.addCleanup(temp.cleanup)
        self.f=P15GrowthFixture(Path(temp.name));self.ids=self.f.experiences()
        self.f.growth.validate(self.ids[0],self.ids[1:])

    def interrupt(self,operation,identity='pending',trait=None,stage='after_learning_record'):
        f=self.f
        def fault(where):
            if where==stage:raise RuntimeError('controlled P15 interruption '+stage)
        f.growth.fault=fault
        with self.assertRaisesRegex(RuntimeError,'controlled P15 interruption'):
            if operation=='SOLIDIFY':f.solidify(self.ids[0],identity=identity)
            else:f.rollback(self.ids[0],trait,identity=identity)
        f.reopen()

    def unrelated(self):
        f=self.f
        event=Event.create(occurred_at=f.runtime.clock.now(),source='authorized-TEST',event_type='state_change',
            content='Unrelated later judgment',reason='Explicit positive control',impact_scope=[StateSection.IDENTITY],
            mutations=[StateMutation('identity.stable_traits',ChangeOperation.APPEND,'unrelated later trait','control')])
        f.runtime.subject_states.apply_event(f.state.subject_id,event,expected_revision=f.state.revision)

    def test_prepare_solidify_is_not_active_or_completed_before_evolution(self):
        self.interrupt('SOLIDIFY');f=self.f
        record=f.growth.learning.get_history(f.state.subject_id,self.ids[0])[-1]
        self.assertEqual(record.record_type.value,'GROWTH_PREPARED')
        self.assertFalse(record.permanently_consolidated)
        self.assertFalse(f.growth.learning.get_trait(f.state.subject_id,record.trait_id).active)
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)
        f.replay('pending');self.assertIn('consider evidence',f.state.identity.stable_traits)

    def test_prepare_rollback_retains_actual_trait_until_evolution(self):
        f=self.f;first=f.solidify(self.ids[0]);trait=first.event.metadata['trait_id']
        self.interrupt('ROLLBACK',trait=trait)
        self.assertTrue(f.growth.learning.get_trait(f.state.subject_id,trait).active)
        self.assertEqual(f.growth.learning.get_learning_event(f.state.subject_id,self.ids[0]).validation_status.value,'VALIDATED')
        self.assertIn('consider evidence',f.state.identity.stable_traits)
        f.replay('pending');self.assertNotIn('consider evidence',f.state.identity.stable_traits)

    def test_rollback_can_be_reconfirmed_after_unrelated_revision(self):
        f=self.f;first=f.solidify(self.ids[0]);trait=first.event.metadata['trait_id']
        self.interrupt('ROLLBACK',trait=trait);self.unrelated()
        with self.assertRaises(LearningValidationError):f.replay('pending')
        before=f.state.revision;f.rollback(self.ids[0],trait,identity='fresh-rollback')
        self.assertEqual(f.state.revision,before+1)
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)
        self.assertIn('unrelated later trait',f.state.identity.stable_traits)
        f.replay('fresh-rollback');self.assertEqual(f.state.revision,before+1)

    def test_superseded_original_command_stays_terminal_and_auditable(self):
        f=self.f;self.interrupt('SOLIDIFY');old=f.growth.learning.get_history(f.state.subject_id,self.ids[0])[-1].to_dict()
        self.unrelated();f.solidify(self.ids[0],identity='fresh');before=f.inventory()
        with self.assertRaisesRegex(LearningValidationError,'SUPERSEDED'):f.replay('pending')
        self.assertEqual(before,f.inventory())
        records=f.growth.learning.get_history(f.state.subject_id,self.ids[0])
        self.assertIn(old,[r.to_dict() for r in records])
        self.assertTrue(any(r.record_type.value=='GROWTH_SUPERSEDED' for r in records))

    def test_new_confirmation_does_not_bypass_current_source_revocation(self):
        f=self.f;self.interrupt('SOLIDIFY');self.unrelated();f.permission.references_allowed=False
        before=f.inventory()
        with self.assertRaises(LearningValidationError):f.solidify(self.ids[0],identity='fresh')
        self.assertEqual(before,f.inventory())

    def test_new_confirmation_does_not_bypass_revoked_owner(self):
        f=self.f;self.interrupt('SOLIDIFY');self.unrelated();f.growth_authority.revoked=True
        before=f.inventory()
        with self.assertRaises(LifecycleError):f.solidify(self.ids[0],identity='fresh')
        self.assertEqual(before,f.inventory())

    def test_supersession_interruption_can_continue_with_original_fresh_identity(self):
        f=self.f;self.interrupt('SOLIDIFY');self.unrelated()
        self.interrupt('SOLIDIFY',identity='fresh',stage='after_pending_superseded')
        before=f.state.revision;f.replay('fresh');f.replay('fresh')
        self.assertEqual(f.state.revision,before+1)
        self.assertIn('unrelated later trait',f.state.identity.stable_traits)

    def test_committed_evolution_finalizes_after_crash_without_current_confirmation(self):
        f=self.f;self.interrupt('SOLIDIFY',stage='after_evolution');before=f.state.to_dict()
        f.growth_authority.revoked=True;f.replay('pending');f.replay('pending')
        self.assertEqual(before,f.state.to_dict())
        self.assertTrue(any(t.active and t.current_value=='consider evidence' for t in f.growth.learning.list_traits(f.state.subject_id)))

    def legacy_pending(self,operation):
        """Model the pre-repair P15 encoding inside this disposable Fixture only."""
        f=self.f;path=f.growth.repository._path(f.state.subject_id)
        document=json.loads(path.read_text(encoding='utf-8'))
        document['records']=[r for r in document['records'] if 'growth_resolution' not in r]
        for record in document['records']:
            if record.get('growth_operation'):
                solid=record['growth_operation']['command']['operation']=='SOLIDIFY'
                record['record_type']='CONSOLIDATED' if solid else 'ROLLED_BACK'
                record['permanently_consolidated']=solid
                record['validation_status']='VALIDATED' if solid else 'REVOKED'
        last=document['records'][-1]
        for trait in document['traits']:
            if trait['trait_id']==last['trait_id']:trait['active']=operation=='SOLIDIFY'
        for candidate in document['learning_events']:
            if candidate['learning_id']==self.ids[0]:candidate['validation_status']='VALIDATED' if operation=='SOLIDIFY' else 'REVOKED'
        path.write_text(json.dumps(document),encoding='utf-8');f.reopen()

    def test_old_format_pending_solidify_can_be_reconfirmed(self):
        f=self.f;self.interrupt('SOLIDIFY');self.legacy_pending('SOLIDIFY');self.unrelated()
        f.solidify(self.ids[0],identity='fresh')
        self.assertIn('consider evidence',f.state.identity.stable_traits)
        self.assertIn('unrelated later trait',f.state.identity.stable_traits)

    def test_old_format_pending_rollback_can_be_reconfirmed(self):
        f=self.f;original=f.solidify(self.ids[0]);trait=original.event.metadata['trait_id']
        self.interrupt('ROLLBACK',trait=trait);self.legacy_pending('ROLLBACK');self.unrelated()
        f.rollback(self.ids[0],trait,identity='fresh')
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)
        self.assertIn('unrelated later trait',f.state.identity.stable_traits)

    def test_committed_resolution_without_actual_evolution_is_not_replayed(self):
        f=self.f;result=f.solidify(self.ids[0],identity='committed');before=f.inventory()
        original=f.growth.core.subject_states.get_update_history
        def history(subject):return [r for r in original(subject) if r.event.event_id!=result.event.event_id]
        with patch.object(f.growth.core.subject_states,'get_update_history',side_effect=history):
            with self.assertRaisesRegex(LearningValidationError,'FACT_MISSING'):f.replay('committed')
        self.assertEqual(before,f.inventory())


class GrowthProjectionRepairTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='vr15-');self.addCleanup(temp.cleanup)
        self.f=P15GrowthFixture(Path(temp.name))
        self.f.affective_event('care',object_id='peer-a',observation='support_received')
        self.f.runtime.clock.advance(timedelta(seconds=1));self.f.submit(self.f.request())
        self.view=self.f.owner_projection()

    def test_permission_expiration_during_read_denies_without_observer_writes(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        from continuity_engine.domain.permissions import PermissionStatus
        f=self.f;original=self.view.states.load;after=[]
        def load(subject):
            state=original(subject)
            if not after:
                f.view_permissions.update_status(subject,'p14-test-owner-read',PermissionStatus.EXPIRED,
                    reason='Explicit test expiry during read',source='TEST')
                after.append(f.inventory())
            return state
        with patch.object(self.view.states,'load',side_effect=load):
            with self.assertRaises(MindAccessError):self.view.read_growth('test-owner-session',allowed_objects=('peer-a',))
        self.assertEqual(after[0],f.inventory())

    def test_state_revision_change_during_read_denies_without_writes(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        original=self.view.states.load;calls=[];before=self.f.inventory()
        def load(subject):
            state=original(subject);calls.append(subject)
            if len(calls)>1:state.revision+=1
            return state
        with patch.object(self.view.states,'load',side_effect=load):
            with self.assertRaises(MindAccessError):self.view.read_growth('test-owner-session',allowed_objects=('peer-a',))
        self.assertEqual(before,self.f.inventory())

    def test_wrong_subject_from_state_port_denied_without_writes(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        state=self.f.state;state.subject_id='other';before=self.f.inventory()
        with patch.object(self.view.states,'load',return_value=state):
            with self.assertRaises(MindAccessError):self.view.read_growth('test-owner-session',allowed_objects=('peer-a',))
        self.assertEqual(before,self.f.inventory())

    def test_export_requires_both_explicit_policy_and_current_permission(self):
        from continuity_engine.services.mind_projection_service import MindAccessError,MindVisibilityPolicy
        before=self.f.inventory()
        with self.assertRaises(MindAccessError):self.view.read_growth('test-owner-session',allowed_objects=('peer-a',),export=True)
        view=self.view.with_policy(MindVisibilityPolicy(export_allowed=True))
        with self.assertRaises(MindAccessError):view.read_growth('test-owner-session',allowed_objects=('peer-a',),export=True)
        self.assertEqual(before,self.f.inventory())
        self.f.view_permissions.create_permission(self.f.state.subject_id,permission_id='test-export',
            permission_type='TEST',name='Explicit TEST export',description='No production privacy policy',
            scope=['mind:TEST:'+self.f.state.subject_id+':test-owner'],capabilities=['mind:export'],source='TEST',reason='control')
        before=self.f.inventory()
        result=view.read_growth('test-owner-session',allowed_objects=('peer-a',),export=True)
        self.assertTrue(result['read_only']);self.assertEqual(before,self.f.inventory())

    def test_export_permission_revoked_during_read_is_rechecked(self):
        from continuity_engine.services.mind_projection_service import MindAccessError,MindVisibilityPolicy
        f=self.f;subject=f.state.subject_id
        f.view_permissions.create_permission(subject,permission_id='test-export',permission_type='TEST',
            name='TEST export',description='Explicit TEST permission',scope=['mind:TEST:'+subject+':test-owner'],
            capabilities=['mind:export'],source='TEST',reason='control')
        view=self.view.with_policy(MindVisibilityPolicy(export_allowed=True));original=view.states.load;after=[]
        def load(identifier):
            state=original(identifier)
            if not after:
                f.view_permissions.revoke_permission(subject,'test-export',source='TEST',reason='mid-read revoke')
                after.append(f.inventory())
            return state
        with patch.object(view.states,'load',side_effect=load):
            with self.assertRaises(MindAccessError):view.read_growth('test-owner-session',allowed_objects=('peer-a',),export=True)
        self.assertEqual(after[0],f.inventory())

    def test_same_revision_growth_content_change_is_rechecked(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        original=self.view.states.load;calls=[];before=self.f.inventory()
        def load(identifier):
            state=original(identifier);calls.append(identifier)
            if len(calls)>1:state.identity.self_narrative['entries'][0]['interpretation']+=' changed'
            return state
        with patch.object(self.view.states,'load',side_effect=load):
            with self.assertRaises(MindAccessError):self.view.read_growth('test-owner-session',allowed_objects=('peer-a',))
        self.assertEqual(before,self.f.inventory())
