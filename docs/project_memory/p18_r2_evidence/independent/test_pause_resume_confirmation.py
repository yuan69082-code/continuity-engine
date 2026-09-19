"""Confirm the definite pre-provider pause liveness gap and preserve true UNKNOWN."""
import json
import unittest

from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from test_independent_resume import IndependentResumeTests
from test_p18_runtime_process import runtime_diagnostic


class PauseResumeConfirmation(unittest.TestCase):
    fixture=IndependentResumeTests.fixture

    def pause_before_call(self,f):
        hit=[]
        def guard(stage):
            if stage=='before_provider' and not hit:
                hit.append(stage);f.control('PAUSE')
        f.host.hook=guard;f.host.tick();f.host.hook=None
        self.assertEqual(hit,['before_provider'])

    def snapshot(self,f,stage):
        print(json.dumps(dict(test=self.id(),stage=stage,revision=f.state.revision,providerCalls=f.provider.calls,
            snapshot=runtime_diagnostic(f),sessions=[dict(id=s.think_id,status=s.status.value,
                errorCode=s.error,completed=s.completed_successfully)
                for s in f.work.thinking.get_sessions(f.state.subject_id)]),ensure_ascii=False))

    def resume_and_assert(self,f,old_revision):
        f.control('RESUME')
        for _ in range(5):f.advance(10);f.host.tick()
        self.snapshot(f,'after-resume-before-stop')
        self.assertTrue(f.store.host_alive())
        self.assertEqual(f.host.query()['desired'],'RUNNING')
        self.assertGreater(f.state.revision,old_revision)

    def test_first_cycle_definitely_not_called_resumes(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            self.pause_before_call(f)
            self.assertEqual(f.provider.calls,0)
            self.resume_and_assert(f,1)

    def test_second_cycle_definitely_not_called_resumes(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.state.revision,2)
            f.control('PAUSE');f.advance(3600);f.host.tick()
            f.control('RESUME');f.host.tick();f.advance(60)
            self.pause_before_call(f)
            self.assertEqual(f.provider.calls,1)
            self.resume_and_assert(f,2)

    def test_reopen_does_not_leave_definite_pre_call_pause_stuck(self):
        f=self.fixture()
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            self.pause_before_call(f);self.assertEqual(f.provider.calls,0)
        reopened=P18Fixture(f.root,initialize=False)
        with reopened.host.running():self.resume_and_assert(reopened,1)

    def test_provider_entered_then_failed_is_not_blindly_repeated(self):
        f=self.fixture()
        def unavailable():raise RuntimeError('isolated TEST provider failed after entry')
        f.provider.hook=unavailable
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            f.provider.hook=None
            f.control('PAUSE');f.control('RESUME')
            for _ in range(5):f.advance(10);f.host.tick()
            self.snapshot(f,'uncertain-provider-positive-control')
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.host.query()['activity'],'WAITING_VERIFICATION')

if __name__=='__main__':unittest.main()
