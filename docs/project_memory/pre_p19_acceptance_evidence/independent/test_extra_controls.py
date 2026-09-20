"""Independent adversarial recovery/current-authority controls. TEST fixtures only."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.testing.p18_runtime_fixture import P18Fixture

OUT=Path(__file__).resolve().parent


class Crash(BaseException):pass


class ExtraControls(unittest.TestCase):
    def fixture(self, mode='contact'):
        temp=tempfile.TemporaryDirectory(prefix='pc-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name),mode=mode)

    def step(self,f):
        f.advance(3600);f.host.tick();f.advance(60);f.host.tick()

    def observe(self,f,**extra):
        record=dict(test=self.id(),revision=f.state.revision,providerCalls=f.provider.calls,
            effects=f.fake.effect_count,credits=f.fake.credits,focus=f.state.continuity.current_focus,
            host=f.host.query(),**extra)
        with (OUT/'extra-observations.jsonl').open('a',encoding='utf8') as out:
            out.write(json.dumps(record,ensure_ascii=False,default=str)+'\n')

    def stop(self,f):
        f.control('STOP')
        self.assertFalse(f.host.tick())

    def test_denial_before_evolution_crash_recovers_same_thinking_once(self):
        f=self.fixture();f.constraints.confirmation_allowed=False
        def fault(stage):
            if stage=='after_native_effect':raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():f.fault=fault;self.step(f)
        self.assertEqual(f.state.revision,1)
        self.assertEqual(f.provider.calls,1)
        f=P18Fixture(f.root,initialize=False);f.constraints.confirmation_allowed=False
        with f.host.running():
            f.host.tick();self.observe(f)
            self.assertEqual((f.provider.calls,f.state.revision,f.fake.effect_count,f.fake.credits),(0,2,0,0))
            self.assertEqual(f.host.query()['unconfirmed_tasks'],0)
            self.stop(f)

    def test_denial_after_evolution_recovery_does_not_dispatch_when_permission_returns(self):
        f=self.fixture();f.constraints.confirmation_allowed=False
        def fault(stage):
            if stage=='after_native_evolution':raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():f.fault=fault;self.step(f)
        self.assertEqual(f.state.revision,2)
        f=P18Fixture(f.root,initialize=False)
        self.assertTrue(f.constraints.confirmation_allowed)
        with f.host.running():
            f.host.tick();self.observe(f)
            self.assertEqual((f.provider.calls,f.state.revision,f.fake.effect_count,f.fake.credits),(0,2,0,0))
            self.assertEqual(f.host.query()['unconfirmed_tasks'],0)
            self.stop(f)

    def test_restoring_existing_denied_fact_never_creates_a_new_write_after_permission_withdrawal(self):
        f=self.fixture();f.constraints.reality_ready=False
        def fault(stage):
            if stage=='after_native_evolution':raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():f.fault=fault;self.step(f)
        before=f.state.to_dict()
        f=P18Fixture(f.root,initialize=False)
        f.work.native._available_permissions=tuple(p for p in f.work.native._available_permissions if p!='subject_state:update')
        with f.host.running():
            f.host.tick();self.observe(f)
            self.assertEqual(f.state.to_dict(),before)
            self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(0,0,0))
            self.stop(f)

    def test_presentation_generator_failure_is_not_converted_into_permission_denial(self):
        f=self.fixture()
        def fail(*args):raise RuntimeError('isolated presentation generation fault')
        f.core.expression_policy.presentation.present=fail
        with f.host.running():
            self.step(f);self.observe(f)
            self.assertEqual(f.state.revision,1)
            self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,0,0))
            self.assertIsNone(f.work.expression_trace)
            self.assertGreater(f.host.query()['unconfirmed_tasks'],0)
            self.stop(f)

    def test_context_invalidated_during_presentation_cannot_commit_internal_state(self):
        f=self.fixture();present=f.core.expression_policy.presentation.present
        def invalidate(*args):
            result=present(*args);f.base.permission.references_allowed=False;return result
        f.core.expression_policy.presentation.present=invalidate
        with f.host.running():
            self.step(f);self.observe(f)
            self.assertEqual(f.state.revision,1)
            self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            self.stop(f)

    def test_internal_permission_withdrawn_after_expression_denial_prevents_commit(self):
        f=self.fixture();f.constraints.confirmation_allowed=False
        def revoke(stage):
            if stage=='after_native_effect':
                f.work.native._available_permissions=tuple(p for p in f.work.native._available_permissions if p!='subject_state:update')
        f.fault=revoke
        with f.host.running():
            self.step(f);self.observe(f)
            self.assertEqual(f.state.revision,1)
            self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            self.stop(f)

    def routed_crash(self,outcome):
        f=self.fixture('reflect');original=f.provider.think
        if outcome=='denied':f.boundary.allowed=False
        else:f.fake.mode='lost_response'
        def proposal(*args):
            result=original(*args)
            return replace(result,update_subject_state=True,proposed_mutations=[
                StateMutation('continuity.current_focus',ChangeOperation.SET,
                    ['premature routed outcome'],'proposal before receipt')])
        f.provider.think=proposal
        def fault(stage):
            if stage=='after_native_evolution':raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():f.fault=fault;self.step(f)
        before=f.state.to_dict()
        self.assertEqual(before['revision'],2)
        self.assertEqual(f.state.continuity.current_focus,['continuity'])
        count=0 if outcome=='denied' else 1
        self.assertEqual((f.fake.effect_count,f.fake.credits),(count,count))
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick();self.observe(f,outcome=outcome)
            self.assertEqual(f.state.to_dict(),before)
            self.assertEqual((f.provider.calls,f.fake.execute_calls,f.fake.effect_count,f.fake.credits),(0,0,count,count))
            self.assertEqual(f.host.query()['unconfirmed_tasks'],0)
            self.stop(f)

    def test_routed_denial_after_internal_commit_crash_keeps_filtered_state_and_no_effect(self):
        self.routed_crash('denied')

    def test_routed_lost_response_after_internal_commit_crash_recovers_fact_without_reexecuting(self):
        self.routed_crash('lost_response')
