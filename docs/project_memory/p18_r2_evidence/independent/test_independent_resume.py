"""Predetermined pause/resume and clock-interleaving probes in isolated TEST roots."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import traceback
import unittest

from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from test_p18_runtime_process import runtime_diagnostic


class IndependentResumeTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='rr18-');self.addCleanup(temp.cleanup)
        f=P18Fixture(Path(temp.name),mode='silence')
        events=[];original=f.work._continue
        def traced(request):
            try:return original(request)
            except Exception as exc:
                errors=[];seen=set();cursor=exc
                while cursor is not None and id(cursor) not in seen:
                    seen.add(id(cursor));message=str(cursor)
                    errors.append(dict(type=type(cursor).__name__,
                        code=message if re.fullmatch('[A-Z][A-Z_0-9]+',message) else None,
                        messageHash=hashlib.sha256(message.encode()).hexdigest(),
                        frames=[dict(file=Path(t.filename).name,line=t.lineno,function=t.name)
                                for t in traceback.extract_tb(cursor.__traceback__)]))
                    cursor=cursor.__cause__ or cursor.__context__
                events.append(errors);raise
        f.work._continue=traced
        def evidence():
            sessions=[dict(id=s.think_id,status=s.status.value,completed=s.completed_successfully,
                error=s.error if s.error and re.fullmatch('[A-Z][A-Z_0-9]+',s.error) else None,
                stateWritten=s.state_written_back,updateId=s.state_update_id)
                for s in f.work.thinking.get_sessions(f.state.subject_id)]
            print(json.dumps(dict(test=self.id(),revision=f.state.revision,providerCalls=f.provider.calls,
                effects=f.fake.effect_count,credits=f.fake.credits,sessions=sessions,
                exceptions=events,snapshot=runtime_diagnostic(f)),ensure_ascii=False))
        self.addCleanup(evidence)
        return f

    def initial(self,f):
        f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
        self.assertEqual(f.state.revision,2)

    def second_ready(self,f):
        self.initial(f)
        f.control('PAUSE');f.advance(3600);f.host.tick()
        f.control('RESUME');f.host.tick();f.advance(60)

    def test_normal_pause_resume_two_cycles(self):
        f=self.fixture()
        with f.host.running():
            self.second_ready(f);f.host.tick()
            self.assertEqual(f.state.revision,3)
            self.assertEqual(f.provider.calls,2)

    def test_pause_before_provider_then_resume_makes_progress(self):
        f=self.fixture();hit=[]
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            def pause(stage):
                if stage=='before_provider' and not hit:
                    hit.append(stage);f.control('PAUSE')
            f.host.hook=pause;f.host.tick()
            self.assertEqual(hit,['before_provider']);self.assertEqual(f.provider.calls,0)
            f.host.hook=None;f.control('RESUME')
            for _ in range(4):f.advance(10);f.host.tick()
            self.assertGreater(f.state.revision,1,'A definite pre-provider pause must not permanently poison future cognition')

    def test_pause_after_budget_before_session_then_resume_makes_progress(self):
        f=self.fixture();hit=[]
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            def pause(stage):
                if stage=='after_thinking_resources' and not hit:
                    hit.append(stage);f.control('PAUSE')
            f.host.hook=pause;f.host.tick()
            self.assertEqual(hit,['after_thinking_resources']);self.assertEqual(f.provider.calls,0)
            f.host.hook=None;f.control('RESUME')
            for _ in range(4):f.advance(10);f.host.tick()
            self.assertGreater(f.state.revision,1)

    def clock_interleaving(self,stage):
        f=self.fixture();hit=[]
        with f.host.running():
            self.second_ready(f)
            def advance(observed):
                if observed==stage and not hit:hit.append(observed);f.advance(60)
            f.host.hook=advance;f.host.tick();f.host.hook=None
            self.assertEqual(hit,[stage])
            # Bounded extra ticks distinguish a deferred step from lost liveness.
            for _ in range(3):f.advance(10);f.host.tick()
            self.assertGreaterEqual(f.state.revision,3)


for _stage in ('before_native_wake','after_wake_resources','before_native_perception',
               'before_thinking_resources','after_thinking_resources','before_provider',
               'before_native_action','before_native_expression','before_native_evolution'):
    setattr(IndependentResumeTests,'test_clock_advances_at_'+_stage,
            lambda self,stage=_stage:self.clock_interleaving(stage))

if __name__=='__main__':unittest.main()
