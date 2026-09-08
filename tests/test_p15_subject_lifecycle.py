from datetime import datetime, timezone
import unittest


class SubjectLifecycleModelTests(unittest.TestCase):
    def test_legacy_state_is_active_without_rewriting_serialization(self):
        from continuity_engine.domain.subject_lifecycle import lifecycle_status
        from continuity_engine.domain.models import SubjectState
        state=SubjectState.create('legacy',datetime(2026,9,8,tzinfo=timezone.utc))
        before=state.to_dict()
        self.assertEqual(lifecycle_status(state),'ACTIVE')
        self.assertEqual(before,state.to_dict())
        self.assertNotIn('subject_lifecycle',before['temporal'])

    def test_transition_table_preserves_terminal_deleted(self):
        from continuity_engine.domain.subject_lifecycle import transition, LifecycleError
        self.assertEqual(transition('CREATE','ACTIVATE'),'ACTIVE')
        self.assertEqual(transition('ACTIVE','SUSPEND'),'SUSPENDED')
        self.assertEqual(transition('SUSPENDED','RESUME'),'ACTIVE')
        self.assertEqual(transition('ACTIVE','ARCHIVE'),'ARCHIVED')
        self.assertEqual(transition('ARCHIVED','RESUME'),'ACTIVE')
        self.assertEqual(transition('ARCHIVED','DELETE'),'DELETED')
        for operation in ('RESUME','ACTIVATE','SUSPEND','ARCHIVE'):
            with self.subTest(operation=operation),self.assertRaises(LifecycleError):
                transition('DELETED',operation)

    def test_subject_intent_is_not_owner_command_or_deletion(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleCommand,LifecycleError
        args=dict(command_id='c',subject_id='s',environment='TEST',expected_revision=1,
                  requested_at=datetime(2026,9,8,tzinfo=timezone.utc),reason='Pause this relationship')
        intent=LifecycleCommand(**args,operation='SUSPEND_INTENT',initiator='SUBJECT')
        self.assertEqual(LifecycleCommand.from_dict(intent.to_dict()),intent)
        for op in ('DELETE','SUSPEND','ARCHIVE'):
            with self.subTest(operation=op),self.assertRaises(LifecycleError):
                LifecycleCommand(**args,operation=op,initiator='SUBJECT')

    def test_policy_is_unconfigured_until_explicit_test_decision(self):
        from continuity_engine.domain.subject_lifecycle import LifecyclePolicy,LifecycleError
        policy=LifecyclePolicy()
        self.assertFalse(policy.archive_configured)
        self.assertIsNone(policy.delete_retention_seconds)
        with self.assertRaises(LifecycleError):LifecyclePolicy(delete_retention_seconds=-1)


class SubjectLifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from continuity_engine.testing.p15_subject_fixture import P15Fixture
        self.temp = tempfile.TemporaryDirectory(prefix='p15-')
        self.addCleanup(self.temp.cleanup)
        self.f = P15Fixture(Path(self.temp.name))

    def test_create_suspend_restart_resume_and_replay(self):
        f = self.f
        f.command('CREATE', identity='create')
        self.assertEqual(f.status(), 'CREATE')
        f.command('ACTIVATE')
        result = f.command('SUSPEND', identity='pause')
        revision = f.state().revision
        f.reopen()
        self.assertEqual(f.status(), 'SUSPENDED')
        replay = f.replay('pause')
        self.assertEqual(replay.update_id, result.update_id)
        self.assertEqual(f.state().revision, revision)
        f.command('RESUME')
        self.assertEqual(f.status(), 'ACTIVE')

    def test_subject_intent_preserves_state_and_owner_identity(self):
        f=self.f; f.command('CREATE'); f.command('ACTIVATE')
        before=f.state().to_dict()
        record=f.command('SUSPEND_INTENT', initiator='SUBJECT')
        self.assertEqual(before,f.state().to_dict())
        self.assertEqual(record.event.metadata['command']['initiator'],'SUBJECT')
        self.assertFalse(record.event.mutations)

    def test_revoked_confirmation_and_stale_command_zero_writes(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        f=self.f; f.command('CREATE'); f.command('ACTIVATE')
        command,token=f.prepare('SUSPEND')
        f.authority.revoked=True
        before=f.inventory()
        with self.assertRaises(LifecycleError): f.lifecycle.submit(command, token)
        self.assertEqual(before,f.inventory())
        f.authority.revoked=False
        f.command('SUSPEND')
        before=f.inventory()
        with self.assertRaises(LifecycleError): f.lifecycle.submit(command, token)
        self.assertEqual(before,f.inventory())

    def test_archive_unconfigured_and_deleted_terminal(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError, LifecyclePolicy
        f=self.f; f.command('CREATE'); f.command('ACTIVATE')
        before=f.inventory()
        with self.assertRaisesRegex(LifecycleError,'NOT_READY'): f.command('ARCHIVE')
        self.assertEqual(before,f.inventory())
        f.policy=LifecyclePolicy(archive_configured=True, delete_retention_seconds=0,
                                 allow_test_logical_delete=True)
        f.reopen(); f.command('ARCHIVE'); f.command('DELETE')
        before=f.inventory()
        with self.assertRaises(LifecycleError): f.command('RESUME')
        with self.assertRaises(LifecycleError): f.command('CREATE')
        self.assertEqual(before,f.inventory())

    def test_paused_state_cannot_be_changed_by_ordinary_event(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        from continuity_engine.domain.events import Event, StateSection
        f=self.f; f.command('CREATE'); f.command('ACTIVATE'); f.command('SUSPEND')
        before=f.inventory()
        event=Event.create(occurred_at=f.clock(), source='test',event_type='interaction',
            content='new input',impact_scope=[StateSection.TEMPORAL],mutations=[],reason='test')
        with self.assertRaises(LifecycleError):f.states.apply_event(f.subject_id,event)
        self.assertEqual(before,f.inventory())

    def test_same_command_identity_different_contents_is_conflict(self):
        from dataclasses import replace
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        f=self.f; f.command('CREATE'); f.command('ACTIVATE'); f.command('SUSPEND', identity='x')
        command,token=f.commands['x']; command=replace(command,reason='different reason')
        before=f.inventory()
        with self.assertRaises(LifecycleError):f.lifecycle.submit(command,token)
        self.assertEqual(before,f.inventory())

    def test_action_gate_denial_is_zero_write(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        f=self.f; f.command('CREATE'); f.command('ACTIVATE'); f.grant.revoked=True
        before=f.inventory()
        with self.assertRaisesRegex(LifecycleError,'ACTION_GATE'):f.command('SUSPEND')
        self.assertEqual(before,f.inventory())

    def test_c1_new_request_paused_zero_journal_provider_or_receipt(self):
        from continuity_engine.testing.p13_expression_fixture import P13Fixture
        from continuity_engine.services.subject_lifecycle_service import SubjectLifecycleService
        f=self.f
        c1=P13Fixture(f.root/'c1')
        f.subject_id=c1.runtime.descriptor.subject_id; f.reopen()
        f.states=c1.runtime.subject_states
        f.clock=c1.runtime.clock.now
        f.lifecycle=SubjectLifecycleService(f.states, environment='TEST',authority=f.authority,
            action_gate=f.gate,clock=f.clock)
        f.command('SUSPEND')
        request=c1.request()
        before=f.inventory(); calls=c1.provider.calls
        with self.assertRaises(Exception):c1.submit(request)
        self.assertEqual(before,f.inventory())
        self.assertEqual(calls,c1.provider.calls)
        self.assertIsNone(c1.app.ledger.load_operation(request['requestId']))
        f.command('RESUME')
        self.assertIsNotNone(c1.submit(c1.request()))

    def test_scheduler_paused_zero_attempt_resource_notification_then_resume(self):
        from continuity_engine.testing.p11_scheduler_fixture import P11SchedulerFixture
        from continuity_engine.services.subject_lifecycle_service import SubjectLifecycleService
        f=self.f
        scheduler=P11SchedulerFixture.create(f.root/'scheduler', frozen_at=f.clock(),enable_awakening=True)
        f.subject_id=scheduler.subject_id; f.reopen()
        f.states=scheduler.awakening_service._subject_states
        f.lifecycle=SubjectLifecycleService(f.states,environment='TEST',authority=f.authority,
            action_gate=f.gate,clock=f.clock)
        scheduler.service.submit(scheduler.create_task(task_id='one'))
        f.command('SUSPEND'); before=f.inventory()
        result=scheduler.service.tick(f.subject_id,'TEST')
        self.assertEqual(result.reason_code,'SUBJECT_NOT_ACTIVE')
        self.assertEqual(before,f.inventory())
        self.assertEqual(scheduler.adapter.dispatch_count,0)
        self.assertEqual(scheduler.wake_count,0)
        f.command('RESUME')
        scheduler.service.tick(f.subject_id,'TEST')
        self.assertEqual(scheduler.wake_count,1)
