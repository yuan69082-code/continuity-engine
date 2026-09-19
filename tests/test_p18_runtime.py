"""P18 continuous hosting and local control; isolated deterministic Fixtures."""
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError, RuntimePolicy
from continuity_engine.domain.scheduling import SchedulerTaskState


class RuntimeControlTests(unittest.TestCase):
    def fixture(self, **options):
        from continuity_engine.testing.p18_runtime_fixture import P18Fixture
        temp=tempfile.TemporaryDirectory(prefix='p18-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name), **options)

    def test_idle_tick_does_not_stop_host_or_invoke_provider(self):
        f=self.fixture(need_delta=1.0)
        with f.host.running():
            for _ in range(3): f.host.tick()
            self.assertTrue(f.host.query()['host_alive'])
            self.assertEqual(f.host.query()['desired'],'RUNNING')
            self.assertEqual(f.provider.calls,0)

    def test_owner_pause_resume_stop_and_duplicate_controls(self):
        f=self.fixture()
        with f.host.running():
            f.control('PAUSE',command_id='pause-1')
            before=f.store.path.read_bytes()
            f.control('PAUSE',command_id='pause-1')
            self.assertEqual(before,f.store.path.read_bytes())
            f.advance(3600);f.host.tick()
            self.assertEqual(f.provider.calls,0)
            self.assertTrue(f.host.query()['host_alive'])
            f.control('RESUME');f.host.tick()
            f.advance(60);f.host.tick()
            self.assertGreater(f.provider.calls,0)
            f.control('STOP');self.assertFalse(f.host.tick())
        with f.host.running():
            self.assertFalse(f.host.tick())
        self.assertEqual(f.host.query()['desired'],'STOPPED')

    def test_without_messages_native_c1_updates_same_subject(self):
        f=self.fixture(mode='silence')
        initial=f.state
        with f.host.running():
            f.advance(3600);f.host.tick()
            f.advance(60);f.host.tick()
            self.assertGreater(f.state.revision,initial.revision)
            self.assertEqual(f.state.subject_id,initial.subject_id)
            self.assertIsNotNone(f.state.intentions.dynamic_mind)
            self.assertEqual(f.provider.inputs[-1].external_facts,())
            self.assertTrue(f.host.query()['host_alive'])
            self.assertEqual(f.fake.effect_count,0)

    def test_zero_budget_waits_then_resumes_without_message(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            f.advance(3600);f.host.tick()
            f.advance(60);f.host.tick()
            self.assertEqual(f.provider.calls,0)
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            self.assertTrue(f.host.query()['host_alive'])
            f.grant_test_budget(10000)
            f.advance(10);f.host.tick()
            self.assertGreater(f.provider.calls,0)

    def ready(self,f):
        f.advance(3600);f.host.tick();f.advance(60)

    def test_native_contact_expression_execution_and_next_context(self):
        f=self.fixture(mode='contact')
        with f.host.running():
            self.ready(f);f.host.tick()
            self.assertEqual(f.fake.effect_count,1)
            self.assertEqual(f.fake.credits,1)
            self.assertIsNotNone(f.work.expression_trace)
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertGreaterEqual(f.provider.calls,2)
            fragments=f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
            self.assertTrue(any(x.source_type=='execution_result' for x in fragments))
            self.assertEqual(f.provider.inputs[-1].external_facts,())

    def test_local_maintenance_runs_while_model_is_unavailable(self):
        f=self.fixture();f.online=False
        with f.host.running():
            f.advance(3600);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'MAINTENANCE')
            self.assertTrue(f.core.memory.list_memories(f.state.subject_id))
            f.advance(60);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            self.assertEqual(f.provider.calls,0)
            f.online=True;f.advance(5);f.host.tick()
            self.assertEqual(f.provider.calls,1)

    def check_later_maintenance(self,*,tokens=100000,online=True):
        f=self.fixture(tokens=tokens);f.online=online
        with f.host.running():
            self.ready(f);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            cognitive=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST')
                           if t.task_id.startswith('cognition:'))
            f.base.event('later-local-maintenance')
            revision=f.state.revision
            used=f.resources.get_resource_state(f.state.subject_id).token_used
            for _ in range(3):f.advance(5);f.host.tick()
            self.assertTrue(any(m.memory_id=='memory:later-local-maintenance'
                                for m in f.core.memory.list_memories(f.state.subject_id)))
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
            self.assertEqual(f.state.revision,revision)
            saved=f.scheduler.get(cognitive.task_id,subject_id=f.state.subject_id,environment='TEST')
            self.assertEqual(saved.to_dict(),cognitive.to_dict())
            self.assertTrue(f.host.query()['host_alive'])

    def test_later_maintenance_with_zero_model_quota(self):
        self.check_later_maintenance(tokens=0)

    def test_later_maintenance_with_provider_unavailable(self):
        self.check_later_maintenance(online=False)

    def test_resource_scan_is_opt_in_and_budget_restore_remains_legal(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            self.ready(f);f.host.tick();f.base.event('scan-control')
            f.scheduler._resource_scan_limit=1  # Original P11 default.
            f.advance(5);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            self.assertFalse(any(m.memory_id=='memory:scan-control' for m in f.core.memory.list_memories(f.state.subject_id)))
            f.scheduler._resource_scan_limit=128
            f.advance(5);f.host.tick()
            self.assertTrue(any(m.memory_id=='memory:scan-control' for m in f.core.memory.list_memories(f.state.subject_id)))
            self.assertEqual(f.provider.calls,0)
            f.grant_test_budget(100000);f.advance(60);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.fake.effect_count,0)

    def test_invalid_resource_scan_limit_refuses_without_writes(self):
        from continuity_engine.domain.scheduling import SchedulerValidationError
        from continuity_engine.services.scheduler_service import SchedulerService
        f=self.fixture()
        before={p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        for limit in (0,-1,True,1.5,129):
            with self.subTest(limit=limit),self.assertRaises(SchedulerValidationError):
                SchedulerService(f.scheduler._repository,f.work,f.resources,resource_scan_limit=limit)
        self.assertEqual(before,{p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()})
        self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.effect_count,0)

    def test_owner_identity_and_revision_rejection_has_zero_writes(self):
        f=self.fixture();before={p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        with self.assertRaises(RuntimeBoundaryError):f.control('STOP',handle='arbitrary-owner-string')
        with self.assertRaises(RuntimeBoundaryError):
            f.host.control('STOP',command_id='stale',expected_revision=0,handle='p18-test-owner')
        self.assertEqual(before,{p:p.read_bytes() for p in f.root.rglob('*') if p.is_file()})
        self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)

    def test_control_identity_conflict_retains_first_decision(self):
        f=self.fixture();f.control('PAUSE',command_id='same')
        before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.control('RESUME',command_id='same')
        self.assertEqual(before,f.store.path.read_bytes())

    def test_explicit_stop_cannot_be_resumed(self):
        f=self.fixture();f.control('STOP');before=f.store.path.read_bytes()
        with self.assertRaises(RuntimeBoundaryError):f.control('RESUME')
        self.assertEqual(before,f.store.path.read_bytes())
        self.assertEqual(f.state.subject_id,f.app.binding.subject_id)

    def test_pause_after_selection_prevents_wake_and_allocation(self):
        f=self.fixture()
        with f.host.running():
            self.ready(f)
            before=f.resources.get_resource_state(f.state.subject_id).to_dict()
            f.host.hook=lambda stage:f.control('PAUSE') if stage=='before_native_wake' else None
            f.host.tick()
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).to_dict(),before)
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)
            self.assertEqual(f.host.query()['desired'],'PAUSED')

    def test_pause_after_wake_resources_prevents_provider_and_effect(self):
        f=self.fixture(mode='contact')
        with f.host.running():
            self.ready(f)
            f.host.hook=lambda stage:f.control('PAUSE') if stage=='after_wake_resources' else None
            f.host.tick()
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)
            usage=f.resources.get_usage_history(f.state.subject_id)
            self.assertFalse(any(u.session_type.value=='thinking' for u in usage))

    def test_pause_immediately_before_provider_blocks_call(self):
        f=self.fixture(mode='contact')
        with f.host.running():
            self.ready(f)
            f.host.hook=lambda stage:f.control('PAUSE') if stage=='before_provider' else None
            f.host.tick()
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.state.revision,1)

    def test_pause_during_world_capacity_prevents_effect_and_credits(self):
        f=self.fixture(mode='contact')
        with f.host.running():
            self.ready(f);f.boundary.hook=lambda:f.control('PAUSE')
            f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.fake.effect_count,0);self.assertEqual(f.fake.credits,0)
            self.assertEqual(f.state.revision,1)

    def test_subject_suspension_stays_paused_after_resource_restore(self):
        f=self.fixture();f.lifecycle('SUSPEND')
        with f.host.running():
            f.advance(3600);f.host.tick();f.grant_test_budget(200000);f.advance(60);f.host.tick()
            self.assertTrue(f.host.query()['host_alive'])
            self.assertEqual(f.host.query()['subject_lifecycle'],'SUSPENDED')
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)

    def test_canceled_pending_work_is_not_revived_by_budget(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            self.ready(f);f.host.tick()
            task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('cognition:'))
            f.scheduler.cancel(task.task_id,subject_id=f.state.subject_id,environment='TEST')
            f.grant_test_budget(100000);f.advance(3600);f.host.tick()
            self.assertEqual(f.provider.calls,0)
            self.assertEqual(f.scheduler.get(task.task_id,subject_id=f.state.subject_id,environment='TEST').state,SchedulerTaskState.CANCELLED)

    def test_same_time_duplicate_ticks_do_not_repeat_calls_or_state(self):
        f=self.fixture(mode='contact')
        with f.host.running():
            self.ready(f);f.host.tick()
            before=(f.provider.calls,f.fake.credits,f.state.to_dict(),f.resources.get_resource_state(f.state.subject_id).to_dict())
            for _ in range(10):f.host.tick()
            self.assertEqual(before,(f.provider.calls,f.fake.credits,f.state.to_dict(),f.resources.get_resource_state(f.state.subject_id).to_dict()))

    def test_clock_regression_then_recovery_is_not_negative_elapsed(self):
        from continuity_engine.testing.persistence import read_json,atomic_write_json
        f=self.fixture()
        with f.host.running():
            self.ready(f);f.host.tick();before=f.state.to_dict()
            path=f.runtime.clock._path;d=read_json(path)
            original=d.copy()
            # Explicit clock fault, not modification of Event objective times.
            d['currentTime']=(f.clock.now()-timedelta(days=1)).isoformat()
            atomic_write_json(path,d)
            f.host.tick()
            self.assertEqual(f.host.query()['activity'],'CLOCK_WAIT')
            self.assertEqual(f.state.to_dict(),before)
            atomic_write_json(path,original);f.advance(3600);f.host.tick()
            self.assertNotEqual(f.host.query()['activity'],'CLOCK_WAIT')

    def test_long_clock_gap_coalesces_no_catchup_loop(self):
        f=self.fixture()
        with f.host.running():
            self.ready(f);f.host.tick();calls=f.provider.calls
            f.advance(86400*10);f.host.tick()
            self.assertLessEqual(f.provider.calls-calls,1)
            self.assertTrue(f.host.query()['host_alive'])

    def test_provider_failure_is_safe_unknown_with_bounded_queries(self):
        f=self.fixture();secret='synthetic-provider-diagnostic-p18'
        def bad():raise RuntimeError(secret)
        f.provider.hook=bad
        with f.host.running():
            self.ready(f);f.host.tick()
            for _ in range(4):f.advance(30);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.host.query()['activity'],'WAITING_VERIFICATION')
            for path in f.runtime.data_root.rglob('*.json'):
                self.assertNotIn(secret,path.read_text(encoding='utf8'))

    def test_material_boundary_still_accepts_ordinary_psychological_content(self):
        f=self.fixture(mode='contact')
        f.core.validate_input_material({'query':'ordinary emotions, intimacy, psychological conflict, doubt and desire'})
        with f.host.running():
            self.ready(f);f.host.tick()
            self.assertEqual(f.fake.effect_count,1)

    def test_test_root_rejects_repository_and_uppercase_formal_paths_before_write(self):
        from continuity_engine.testing.p18_runtime_fixture import P18Fixture
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='p18-path-') as temp:
            formal=Path(temp)/'.CONTINUITY-DATA';formal.mkdir()
            for path in (repo,repo/'would-be-runtime',formal,formal/'child'):
                before=set(Path(temp).rglob('*'))
                with self.assertRaises(RuntimeBoundaryError):P18Fixture(path)
                self.assertEqual(before,set(Path(temp).rglob('*')))
            self.assertFalse((repo/'would-be-runtime').exists())

    def test_unconfigured_delivery_policy_refuses_effect_not_cognition(self):
        from continuity_engine.domain.persistent_runtime import RuntimeDeliveryPolicy
        f=self.fixture(mode='contact',delivery_policy=RuntimeDeliveryPolicy())
        with f.host.running():
            self.ready(f);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.fake.effect_count,0);self.assertEqual(f.fake.credits,0)
            self.assertTrue(f.host.query()['host_alive'])

    def test_contact_window_and_frequency_are_explicit_test_constraints(self):
        from continuity_engine.domain.persistent_runtime import RuntimeDeliveryPolicy
        f=self.fixture(mode='contact',delivery_policy=RuntimeDeliveryPolicy(configured=True,start_hour_utc=0,end_hour_utc=1))
        with f.host.running():
            self.ready(f);f.host.tick()
            self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.provider.calls,1)
        policy=RuntimeDeliveryPolicy(configured=True,minimum_interval_seconds=60)
        at=f.clock.now()
        self.assertFalse(policy.allows(at,at-timedelta(seconds=59)))
        self.assertTrue(policy.allows(at,at-timedelta(seconds=60)))

    def test_contact_budget_upper_bound_preserves_host_and_receipts(self):
        from continuity_engine.domain.execution import BlastRadius
        f=self.fixture(mode='contact');f.execution.limits=BlastRadius(credits=1,messages=1)
        with f.host.running():
            self.ready(f);f.host.tick();self.assertEqual(f.fake.credits,1)
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.fake.credits,1);self.assertEqual(f.fake.effect_count,1)
            self.assertTrue(f.host.query()['host_alive'])

    def test_resource_deferral_does_not_consume_scheduler_attempts(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            self.ready(f)
            for _ in range(4):f.host.tick();f.advance(10)
            task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('cognition:'))
            self.assertEqual(task.attempt_count,0)
            self.assertEqual(f.provider.calls,0)

    def test_archived_subject_keeps_control_and_cannot_resume_as_runtime(self):
        f=self.fixture();f.lifecycle('ARCHIVE')
        with f.host.running():
            f.advance(3600);f.host.tick()
            self.assertEqual(f.host.query()['state'],'ARCHIVED')
            self.assertTrue(f.host.query()['host_alive'])
            with self.assertRaises(Exception):f.control('RESUME')
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)
            f.control('STOP');self.assertFalse(f.host.tick())

    def test_backpressure_retains_need_and_reports_deferral(self):
        from continuity_engine.domain.scheduling import SchedulerTask
        f=self.fixture();f.scheduler._capacity=1
        f.scheduler.submit(SchedulerTask.create(task_id='existing-future',subject_id=f.state.subject_id,environment='TEST',
            priority=0,due_at=f.clock.now()+timedelta(days=1),created_at=f.clock.now(),
            wake_reason='internal',cycle_id=f.app.binding.cycle_id))
        with f.host.running():
            f.advance(3600);f.host.tick()
            self.assertEqual(f.host.query()['reason'],'QUEUE_BACKPRESSURE')
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.credits,0)
            self.assertTrue(f.work.needs(f.clock.now()))
            f.scheduler.cancel('existing-future',subject_id=f.state.subject_id,environment='TEST')
            f.advance(5);f.host.tick()
            # With one queue slot the first retained cognition need is admitted;
            # normal C1 also consolidates its pending sources before Thinking.
            self.assertEqual(f.host.query()['activity'],'COGNITION')
            self.assertEqual(f.provider.calls,1)
            self.assertTrue(f.core.memory.list_memories(f.state.subject_id))

    def test_proven_not_delivered_retries_are_bounded(self):
        from continuity_engine.domain.scheduling import NotificationStatus
        f=self.fixture()
        with f.host.running():
            self.ready(f)
            f.work.dispatch=lambda request:f.work._receipt(request,NotificationStatus.NOT_DELIVERED)
            for _ in range(6):f.host.tick();f.advance(30)
            task=next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('cognition:'))
            self.assertEqual(task.state,SchedulerTaskState.RETRY_EXHAUSTED)
            self.assertEqual(task.attempt_count,3)
            self.assertEqual(f.provider.calls,0);self.assertTrue(f.host.query()['host_alive'])


if __name__=='__main__':unittest.main()
