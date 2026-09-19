"""Faults stay in TEST roots; original authorities prove every resumed fact."""
import json
from pathlib import Path
import tempfile
import unittest
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError,RuntimeDeferred
from continuity_engine.domain.scheduling import SchedulerTaskState,NotificationStatus
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class InjectedCrash(BaseException):pass


class RuntimeRecoveryTests(unittest.TestCase):
    def test_later_pause_after_stop_rejects_without_writes(self):
        f=self.fixture();f.control('STOP','stop-first')
        before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.control('PAUSE','later-pause')
        self.assertEqual(before,f.store.path.read_bytes())
        self.assertEqual(f.host.query()['desired'],'STOPPED')

    def test_later_stop_identity_is_read_only_and_remains_queryable(self):
        f=self.fixture();f.control('STOP','stop-first')
        before=f.store.path.read_bytes();f.control('STOP','stop-second')
        self.assertEqual(before,f.store.path.read_bytes())
        self.assertEqual(f.host.query()['desired'],'STOPPED')

    def fixture(self,**options):
        temp=tempfile.TemporaryDirectory(prefix='p18-recover-');self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name),**options)

    def prepare(self,f):
        f.advance(3600);f.host.tick();f.advance(60)

    def recover_at(self,point):
        f=self.fixture(mode='contact');initial=f.state.revision
        def crash(stage):
            if stage==point:raise InjectedCrash(point)
        with self.assertRaises(InjectedCrash):
            with f.host.running():
                self.prepare(f);f.fault=crash;f.host.tick()
        credits=f.fake.credits;used=f.resources.get_resource_state(f.state.subject_id).token_used
        subject=f.state.subject_id
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            # One query/tick may complete historical work; it must not create a
            # second provider session or repeat a world effect/reservation.
            f.host.tick()
            self.assertEqual(f.state.subject_id,subject)
            self.assertEqual(f.state.revision,initial+1)
            self.assertEqual(f.fake.effect_count,1)
            self.assertEqual(f.fake.credits,1)
            self.assertEqual(f.provider.calls,0)
            self.assertEqual(f.resources.get_resource_state(subject).token_used,used)
            if credits:self.assertEqual(f.fake.execute_calls,0)
            f.control('STOP')
        self.assertTrue(any(row['reason']=='PRIOR_HOST_LOST' for row in f.host.query()['interruptions']))

    def test_after_thinking_restarts_without_second_model_call(self):self.recover_at('after_native_thinking')
    def test_after_action_checkpoint_restarts_without_duplicate_action(self):self.recover_at('after_native_action_checkpoint')
    def test_after_effect_restarts_without_duplicate_effect(self):self.recover_at('after_native_effect')
    def test_after_evolution_restarts_without_duplicate_revision(self):self.recover_at('after_native_evolution')
    def test_before_receipt_reconciles_original_evolution_and_effect(self):self.recover_at('before_runtime_receipt')
    def test_after_queue_completion_restarts_without_duplicate_work(self):self.recover_at('after_scheduler_completed')

    def test_actual_fact_can_recover_when_context_has_expired(self):
        f=self.fixture(mode='contact')
        def crash(stage):
            if stage=='after_native_evolution':raise InjectedCrash()
        with self.assertRaises(InjectedCrash):
            with f.host.running():self.prepare(f);f.fault=crash;f.host.tick()
        before=f.state.to_dict();f.advance(900);f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick()
            self.assertEqual(f.state.to_dict(),before)
            self.assertEqual(f.fake.credits,1);self.assertEqual(f.fake.execute_calls,0)
            self.assertEqual(f.provider.calls,0)

    def test_old_context_cannot_authorize_new_effect_after_crash(self):
        f=self.fixture(mode='contact')
        def crash(stage):
            if stage=='after_native_thinking':raise InjectedCrash()
        with self.assertRaises(InjectedCrash):
            with f.host.running():self.prepare(f);f.fault=crash;f.host.tick()
        before=f.state.to_dict();f.advance(900);f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick()
            self.assertEqual(f.state.to_dict(),before)
            self.assertEqual(f.fake.credits,0);self.assertEqual(f.provider.calls,0)

    def test_stop_after_crash_survives_reopen(self):
        f=self.fixture();f.control('STOP');before=f.state.to_dict()
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():self.assertFalse(f.host.tick())
        self.assertEqual(f.state.to_dict(),before)
        self.assertEqual(f.provider.calls,0)

    def test_missing_host_checkpoint_does_not_reinitialize_stopped_subject(self):
        f=self.fixture();f.control('STOP');f.store.path.unlink()  # isolated corruption injection
        before={p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        with self.assertRaises(RuntimeBoundaryError):P18Fixture(f.root,initialize=False)
        self.assertEqual(before,{p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

    def test_corrupt_checkpoint_refuses_start_without_changes(self):
        f=self.fixture();f.store.path.write_text('{corrupt',encoding='utf8')
        before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.host.query()
        with self.assertRaises(RuntimeBoundaryError):
            with f.host.running():f.host.tick()
        self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.fake.credits,0)

    def test_self_consistent_cross_subject_checkpoint_rejected(self):
        f=self.fixture();d=json.loads(f.store.path.read_text(encoding='utf8'))
        d['document']['subject_id']='another-subject';d['hash']=digest(d['document'])
        f.store.path.write_text(json.dumps(d),encoding='utf8');before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.host.query()
        self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.provider.calls,0)

    def test_stop_history_cannot_be_overlaid_with_running_checkpoint(self):
        f=self.fixture();f.control('STOP');d=json.loads(f.store.path.read_text(encoding='utf8'))
        d['document'].update(desired='RUNNING',state='RUNNING',activity='IDLE')
        d['hash']=digest(d['document']);f.store.path.write_text(json.dumps(d),encoding='utf8')
        before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.host.query()
        self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.fake.credits,0)

    def test_cross_environment_checkpoint_rejected_without_effect(self):
        f=self.fixture();d=json.loads(f.store.path.read_text(encoding='utf8'))
        d['document']['environment']='RESEARCH';d['hash']=digest(d['document'])
        f.store.path.write_text(json.dumps(d),encoding='utf8');before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.host.query()
        self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.provider.calls,0)

    def test_receipt_conflict_cannot_reconcile_completed_native_fact(self):
        from dataclasses import replace
        f=self.fixture(mode='contact')
        def crash(stage):
            if stage=='after_native_evolution':raise InjectedCrash()
        with self.assertRaises(InjectedCrash):
            with f.host.running():self.prepare(f);f.fault=crash;f.host.tick()
        f=P18Fixture(f.root,initialize=False);f.fake.receipt_hook=lambda r:replace(r,receipt_id='different-receipt')
        before=f.state.to_dict()
        with f.host.running():
            f.host.tick()
            task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('cognition:'))
            self.assertEqual(task.state,SchedulerTaskState.UNKNOWN)
            self.assertEqual(f.state.to_dict(),before);self.assertEqual(f.fake.credits,1)

    def test_stale_owner_fence_and_second_host_rejected(self):
        f=self.fixture();other=P18Fixture(f.root,initialize=False)
        with f.host.running():
            with self.assertRaises(RuntimeBoundaryError):
                with other.host.running():other.host.tick()
            with self.assertRaises(RuntimeDeferred):other.host.guard()
            self.assertEqual(other.provider.calls,0);self.assertEqual(f.fake.credits,0)

    def test_budget_is_not_reset_on_reopen(self):
        f=self.fixture(tokens=0);before=f.resources.get_resource_state(f.state.subject_id).to_dict()
        f=P18Fixture(f.root,initialize=False,tokens=900000)
        self.assertEqual(before,f.resources.get_resource_state(f.state.subject_id).to_dict())

    def test_view_query_is_read_only_and_has_separate_resource_state(self):
        f=self.fixture(tokens=0)
        before={p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        value=f.host.query()
        self.assertEqual(value['resources']['token_remaining'],0)
        self.assertFalse(value['host_alive'])
        self.assertEqual(before,{p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

    def test_old_owner_control_remains_idempotent_after_130_new_commands(self):
        f=self.fixture()
        def control(operation,identity):
            return f.host.control(operation,command_id=identity,expected_revision=None,handle='p18-test-owner')
        control('PAUSE','original-pause')
        for i in range(130):control('PAUSE' if i%2==0 else 'RESUME','later-'+str(i))
        before=f.store.path.read_bytes();self.assertEqual(f.host.query()['desired'],'RUNNING')
        control('PAUSE','original-pause')
        self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.host.query()['desired'],'RUNNING')

    def test_control_opaque_identity_is_digest_only_in_storage_and_query(self):
        f=self.fixture();material='synthetic-opaque-control-material-18'
        f.host.control('PAUSE',command_id=material,expected_revision=None,handle='p18-test-owner')
        self.assertNotIn(material,json.dumps(f.host.query()))
        for path in f.runtime.data_root.rglob('*.json'):self.assertNotIn(material,path.read_text(encoding='utf8'))

    def test_advancing_clock_silence_and_lifecycle_share_the_same_time_port(self):
        f=self.fixture(test_clock_rate=1)
        with f.host.running():
            self.prepare(f);f.host.tick();self.assertEqual(f.state.revision,2)
            f.lifecycle('SUSPEND');f.host.tick()
            self.assertEqual(f.host.query()['subject_lifecycle'],'SUSPENDED')
            self.assertEqual(f.provider.calls,1);self.assertEqual(f.fake.effect_count,0)

    def test_unknown_execution_never_replays_unverified_effect(self):
        f=self.fixture(mode='contact');f.fake.mode='lost_response'
        with f.host.running():
            self.prepare(f);f.host.tick()
            self.assertEqual(f.fake.effect_count,1)
            f.fake.mode='unknown';before=f.state.revision
            for _ in range(4):f.advance(30);f.host.tick()
            self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.execute_calls,1)
            self.assertEqual(f.fake.credits,1);self.assertEqual(f.state.revision,before)
            f.fake.mode='success';f.advance(5);f.host.tick()
            self.assertEqual(f.fake.effect_count,1)
            self.assertEqual(f.state.revision,before+1)

    def test_cancel_uncommitted_cognition_does_not_create_new_effect_on_query(self):
        f=self.fixture(mode='contact')
        def crash(stage):
            if stage=='after_native_thinking':raise InjectedCrash()
        with self.assertRaises(InjectedCrash):
            with f.host.running():self.prepare(f);f.fault=crash;f.host.tick()
        task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.state is SchedulerTaskState.UNKNOWN)
        f.scheduler.cancel(task.task_id,subject_id=f.state.subject_id,environment='TEST')
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick()
            self.assertEqual(f.fake.effect_count,0);self.assertEqual(f.state.revision,1)

    def test_maintenance_query_requires_real_source_and_memory_fact(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick()
            task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('maintenance:'))
            request=f.scheduler._request(task,f.clock.now())
            self.assertEqual(f.work.query(request).status,NotificationStatus.DELIVERED)
            original=f.core.memory.list_memories
            f.core.memory.list_memories=lambda *a,**k:[]
            self.assertEqual(f.work.query(request).status,NotificationStatus.NOT_DELIVERED)
            f.core.memory.list_memories=original


if __name__=='__main__':unittest.main()
