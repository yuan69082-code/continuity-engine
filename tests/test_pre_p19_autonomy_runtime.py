"""Persistent internal concerns remain eligible without numerical drive growth."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
import tempfile
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.domain.persistent_runtime import RuntimePolicy
from continuity_engine.services.dynamic_mind_service import MindDynamics
from continuity_engine.services.runtime_cognition import RuntimeCognition
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class AutonomyRuntimeTests(unittest.TestCase):
    def test_hold_has_later_reconsideration_not_per_tick_dispatch(self):
        mind=self.saturated()
        mind=replace(mind,will=[{**w,'stance':'hold','decision':'DEFER'} for w in mind.will])
        self.assertEqual(self.pure(mind,mind.updated_at+timedelta(seconds=60)),())
        self.assertTrue(self.pure(mind,mind.updated_at+timedelta(seconds=240)))

    def test_stable_need_survives_resource_wait_and_resume_without_chat(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.provider.calls,1);before=f.state.revision
            f.grant_test_budget(f.resources.get_resource_state(f.state.subject_id).token_used)
            f.work.policy=replace(f.work.policy,need_delta=1.0)
            for _ in range(2):f.advance(300);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            self.assertTrue(f.host.query()['host_alive'])
            f.grant_test_budget(10000);f.advance(60);f.host.tick()
            self.assertGreater(f.state.revision,before)
            self.assertEqual(f.provider.calls,2)
            f.control('STOP')
    def pure(self,mind,at):
        state=N(revision=3,intentions=N(dynamic_mind=mind.to_dict()))
        core=N(subject_states=N(require_active=lambda *a:state),
            mind=N(dynamics=MindDynamics()),memory=N(list_memories=lambda *a,**kw:[]),
            timeline=N(rebuild=lambda *a:N(entries=[])))
        work=N(core=core,subject_id=mind.subject_id,environment='TEST',policy=RuntimePolicy(),
               scheduler=N(list_tasks=lambda **kw:[]))
        return RuntimeCognition.needs(work,at)

    def saturated(self):
        now=datetime(2026,9,19,tzinfo=timezone.utc)
        return MindDynamics().advance(MindState.create('test','TEST',now),at=now+timedelta(days=365)).state

    def test_saturated_and_near_saturated_concerns_still_request_cognition(self):
        for value in (1.0,0.99999999):
            mind=self.saturated();mind=replace(mind,drives={k:value for k in mind.drives})
            needs=self.pure(mind,mind.updated_at+timedelta(days=1))
            self.assertTrue(any(n.kind=='cognition' for n in needs))

    def test_same_basis_has_same_identity_and_respects_spacing(self):
        mind=self.saturated()
        self.assertEqual(self.pure(mind,mind.updated_at),())
        a=self.pure(mind,mind.updated_at+timedelta(days=1))
        b=self.pure(mind,mind.updated_at+timedelta(days=7))
        self.assertTrue(a);self.assertEqual(a[0].identity,b[0].identity)

    def test_explicit_abandonment_and_empty_concerns_do_not_force_provider(self):
        mind=self.saturated()
        stopped=replace(mind,desires=[{**d,'phase':'abandon'} for d in mind.desires],
            thoughts=[{**t,'unresolved':False} for t in mind.thoughts],
            will=[{**w,'stance':'abandon','decision':'DEFER'} for w in mind.will])
        self.assertEqual(self.pure(stopped,stopped.updated_at+timedelta(days=1)),())
        empty=replace(mind,desires=[],will=[],thoughts=[],episodes=[])
        self.assertEqual(self.pure(empty,empty.updated_at+timedelta(days=1)),())

    def fixture(self,**options):
        temp=tempfile.TemporaryDirectory(prefix='a19r-');self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name),**options)

    def test_gradual_native_cognition_continues_when_delta_gate_cannot_fire(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            initial=f.state.revision;calls=f.provider.calls
            f.work.policy=replace(f.work.policy,need_delta=1.0)
            for _ in range(3):f.advance(300);f.host.tick()
            self.assertGreater(f.state.revision,initial)
            self.assertGreater(f.provider.calls,calls)
            self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.provider.inputs[-1].external_facts,())
            f.control('PAUSE');before=f.provider.calls
            f.advance(300);f.host.tick();self.assertEqual(f.provider.calls,before)
            f.control('STOP');self.assertFalse(f.host.tick())

    def test_world_unknown_does_not_block_next_internal_cognition_or_repeat_effect(self):
        f=self.fixture(mode='contact');f.fake.mode='unknown'
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            revision=f.state.revision
            for _ in range(4):f.advance(300);f.host.tick()
            self.assertGreater(f.state.revision,revision)
            self.assertEqual((f.fake.execute_calls,f.fake.effect_count,f.fake.credits),(0,0,0))
            self.assertTrue(f.host.query()['host_alive'])
            f.control('STOP')


# Reuse the bounded controller/diagnostic helpers, without inheriting or counting
# the unrelated existing tests a second time.
from tests import test_p18_runtime_process as process_support


class AutonomyProcessTests(unittest.TestCase):
    setUp=process_support.RuntimeProcessTests.setUp
    tearDown=process_support.RuntimeProcessTests.tearDown
    command=process_support.RuntimeProcessTests.command
    cli=process_support.RuntimeProcessTests.cli
    start=process_support.RuntimeProcessTests.start
    until=process_support.RuntimeProcessTests.until
    capture_diagnostic=process_support.RuntimeProcessTests.capture_diagnostic

    def test_saturated_internal_state_continues_in_new_real_runtime_process(self):
        f=P18Fixture(self.root,policy=RuntimePolicy(clock_jump_seconds=40000000),test_clock_rate=60)
        # Reach the plateau through the real native Thinking/Evolution path.
        with f.host.running():
            f.advance(365*86400);f.host.tick();f.advance(60);f.host.tick()
            self.assertTrue(all(v==1 for v in f.state.intentions.dynamic_mind['drives'].values()))
        before=f.state.revision;f.advance(300)
        child=self.start()
        self.until(lambda:f.state.revision>before,process=child)
        self.assertIsNone(child.poll())
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
        self.cli('stop');child.wait(timeout=10)
        self.assertEqual(child.returncode,0)
        revision=f.state.revision
        other=self.start();other.wait(timeout=10)
        self.assertEqual(other.returncode,0)
        self.assertEqual(f.state.revision,revision)
