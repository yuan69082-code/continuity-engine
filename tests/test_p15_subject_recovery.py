from pathlib import Path
from datetime import timedelta
import tempfile
import unittest


class P15RecoveryTests(unittest.TestCase):
    def setUp(self):
        from continuity_engine.testing.p15_subject_fixture import P15Fixture
        self.temp=tempfile.TemporaryDirectory(prefix='r15-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.f=P15Fixture(self.root/'a',subject_id='subject-a')

    def test_concurrent_lifecycle_commands_preserve_one_transition(self):
        from concurrent.futures import ThreadPoolExecutor
        from continuity_engine.domain.errors import StateEvolutionError
        f=self.f; f.command('CREATE');f.command('ACTIVATE')
        a=f.prepare('SUSPEND',identity='a'); b=f.prepare('SUSPEND',identity='b')
        before=f.state().revision
        def submit(value):
            try:return f.lifecycle.submit(*value)
            except (ValueError,StateEvolutionError):return None
        with ThreadPoolExecutor(2) as executor:results=list(executor.map(submit,[a,b]))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(f.state().revision,before+1)
        self.assertEqual(f.status(),'SUSPENDED')

    def test_atomic_creation_failure_does_not_leave_active_subject(self):
        from unittest.mock import patch
        f=self.f
        with patch('continuity_engine.storage.json_repository.os.replace',side_effect=OSError('controlled atomic failure')):
            with self.assertRaises(OSError):f.command('CREATE')
        self.assertFalse(f.states._repository.exists(f.subject_id))
        self.assertEqual(f.inventory(),{})
        f.command('CREATE');self.assertEqual(f.status(),'CREATE')

    def test_cross_subject_environment_and_direct_lifecycle_mutation_rejected(self):
        from dataclasses import replace
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        from continuity_engine.domain.events import Event,StateSection,StateMutation,ChangeOperation
        f=self.f;f.command('CREATE');f.command('ACTIVATE'); command,token=f.prepare('SUSPEND')
        before=f.inventory()
        for bad in (replace(command,subject_id='subject-b'),replace(command,environment='RESEARCH')):
            with self.assertRaises(LifecycleError):f.lifecycle.submit(bad,token)
        value=dict(f.state().temporal.subject_lifecycle,status='DELETED')
        event=Event.create(occurred_at=f.clock(),source='model',event_type='forged',content='forged',
            impact_scope=[StateSection.TEMPORAL],reason='forged',
            mutations=[StateMutation('temporal.subject_lifecycle',ChangeOperation.SET,value,'forged')])
        with self.assertRaises(LifecycleError):f.states.apply_event(f.subject_id,event)
        self.assertEqual(before,f.inventory())

    def test_host_binding_switch_and_unbind_do_not_change_subject_revision(self):
        from continuity_engine.testing.p15_subject_fixture import P15Fixture, TestSubjectSelection
        a=self.f;b=P15Fixture(self.root/'b',subject_id='subject-b')
        for f in (a,b):f.command('CREATE');f.command('ACTIVATE')
        host=TestSubjectSelection(self.root/'host',{'subject-a':a.states,'subject-b':b.states},owner='owner')
        before=(a.inventory(),b.inventory())
        host.select(subject_id='subject-a',environment='TEST',principal_id='owner')
        host.select(subject_id='subject-b',environment='TEST',principal_id='owner')
        self.assertEqual(host.selected(),'subject-b')
        host.unbind(principal_id='owner');self.assertIsNone(host.selected())
        self.assertEqual(before,(a.inventory(),b.inventory()))

    def test_public_test_migration_requires_exact_confirmation_and_never_copies_personality(self):
        from continuity_engine.testing.p15_subject_fixture import P15Fixture
        from continuity_engine.domain.events import Event,StateSection,EventClassification
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        a=self.f;b=P15Fixture(self.root/'b',subject_id='subject-b')
        for f in (a,b):f.command('CREATE');f.command('ACTIVATE')
        event=Event.create(event_id='public',occurred_at=a.clock(),source='test',event_type='public-note',
            content='Synthetic public observation',classification=EventClassification.OBSERVATION,
            impact_scope=[StateSection.CONTINUITY],mutations=[],reason='test',metadata={'visibility':'PUBLIC'})
        a.states.apply_event(a.subject_id,event)
        before=b.inventory()
        with self.assertRaises(LifecycleError):b.import_observation(a,event,confirmed=False)
        self.assertEqual(before,b.inventory())
        result=b.import_observation(a,event,confirmed=True)
        self.assertEqual(result.event.classification,EventClassification.OBSERVATION)
        self.assertEqual(result.event.metadata['source_hash'],event.canonical_hash())
        self.assertEqual(b.state().identity.stable_traits,[])
        self.assertIsNone(b.state().relationship.objects)
        self.assertFalse(result.event.mutations)

    def test_new_genesis_isolated_from_old_learning_mind_relationships(self):
        from continuity_engine.testing.p15_subject_fixture import P15GrowthFixture
        a=P15GrowthFixture(self.root)
        a.affective_event('care',object_id='old-peer',observation='support_received')
        a.runtime.clock.advance(timedelta(seconds=1));a.submit(a.request())
        other=a.manager.create_sandbox(frozen_at=a.runtime.clock.now())
        state=other.subject_state()
        self.assertNotEqual(state.subject_id,a.state.subject_id)
        self.assertIsNone(state.identity.self_narrative)
        self.assertIsNone(state.relationship.objects)
        self.assertIsNone(state.intentions.dynamic_mind)
        self.assertEqual(other.learning.list_learning_events(state.subject_id),[])
        self.assertEqual(other.subject_states.get_update_history(state.subject_id),[])

    def test_protected_fixture_root_rejects_before_any_write(self):
        from continuity_engine.testing.p15_subject_fixture import P15Fixture
        from continuity_engine.testing.models import SandboxOperationError
        protected=self.root/'.CONTINUITY-DATA';protected.mkdir()
        before=list(protected.rglob('*'))
        with self.assertRaises(SandboxOperationError):P15Fixture(protected/'child')
        self.assertEqual(before,list(protected.rglob('*')))

    def test_cross_process_golden(self):
        from continuity_engine.testing.p15_subject_fixture import run_p15_golden
        result=run_p15_golden(self.root)
        self.assertEqual(len(set(result['process_ids'])),2)
        self.assertTrue(result['retained_trait'])
        self.assertTrue(result['retained_will_ids'])
        self.assertEqual(result['duplicate_revision_delta'],0)

    def test_paused_pending_not_executed_model_cannot_dispatch(self):
        from tests.test_p02_model_capability import P02ModelCapabilityFixture,p02_request
        from tests.test_p02_model_recovery import FailOnceAt
        from continuity_engine.services.subject_lifecycle_service import SubjectLifecycleService
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        fixture=P02ModelCapabilityFixture();fixture.setUp();self.addCleanup(fixture.tearDown)
        app,provider=fixture.app()
        app.models._fault_injector=FailOnceAt('after_provider_dispatch_reserved')
        request=p02_request(1)
        with self.assertRaises(RuntimeError):app.models.submit(request)
        f=self.f;f.subject_id='subject-001';f.reopen()
        f.states=app.integration.adapter.service._subject_states
        f.now=f.state().temporal.updated_at+timedelta(seconds=1)
        f.lifecycle=SubjectLifecycleService(f.states,environment='TEST',authority=f.authority,
            action_gate=f.gate,clock=f.clock)
        f.command('SUSPEND')
        count=len(provider.facts())
        caught=None
        try:app.models.recover(request['requestId'])
        except Exception as exc:caught=exc
        print({'scenario':'paused-model-not-executed','facts_before':count,'facts_after':len(provider.facts()),
               'exception':type(caught).__name__ if caught else None})
        self.assertEqual(len(provider.facts()),count,'paused subject must not call Provider')
        self.assertIsInstance(caught,LifecycleError)

    def test_p01_snapshot_branch_keeps_growth_and_does_not_pollute_original(self):
        from continuity_engine.testing.p15_subject_fixture import P15GrowthFixture
        f=P15GrowthFixture(self.root)
        ids=f.experiences();f.growth.validate(ids[0],ids[1:]);f.solidify(ids[0])
        original=f.state.to_dict()
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id)
        other=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
        self.assertEqual(other.subject_state().to_dict(),original)
        self.assertEqual(len(other.learning.get_history(original['subject_id'])),len(f.growth.learning.get_history(original['subject_id'])))
        self.assertEqual(f.state.to_dict(),original)
