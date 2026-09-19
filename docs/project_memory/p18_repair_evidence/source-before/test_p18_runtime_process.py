"""The controller is bounded; the actual Runtime start entry has no deadline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from continuity_engine.domain.persistent_runtime import RuntimePolicy
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class RuntimeProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p18-process-')
        self.root=Path(self.temp.name);self.processes=[];self.records=[]

    def command(self,*args):
        return [sys.executable,'-m','continuity_engine.runtime',*args,'--root',str(self.root)]

    def cli(self,operation):
        command=self.command(operation);at=time.monotonic()
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=20,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
        self.records.append(dict(command=command,exitCode=result.returncode,stdout=result.stdout,stderr=result.stderr,seconds=time.monotonic()-at))
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def start(self,custom=None):
        index=len(self.processes)
        # Evidence is read and printed BEFORE the temporary fixture is removed.
        outpath=self.root/f'child-{index}.stdout.log';errpath=self.root/f'child-{index}.stderr.log'
        out=outpath.open('w',encoding='utf8');err=errpath.open('w',encoding='utf8')
        command=custom or self.command('start')
        process=subprocess.Popen(command,stdout=out,stderr=err,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.processes.append((process,command,out,err,outpath,errpath,time.monotonic()))
        return process

    def until(self,predicate,*,timeout=25,process=None):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return
            if hasattr(self,'observer'):
                snapshot=self.observer()
                if snapshot['revision']!=getattr(self,'observed_revision',None):
                    self.records.append(dict(stage='controller-observation',snapshot=snapshot))
                    self.observed_revision=snapshot['revision']
            if process is not None and process.poll() is not None:
                self.fail('continuous process exited before controller STOP')
            threading.Event().wait(.1)
        self.fail('bounded test controller timed out')

    def tearDown(self):
        # Explicit STOP first, even after a failed assertion. The fallback only
        # terminates children owned by this test and is truthfully recorded.
        if any(p.poll() is None for p,*_ in self.processes):
            command=self.command('stop')
            try:
                r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=20)
                self.records.append(dict(stage='controller-stop-cleanup',command=command,exitCode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            except Exception as exc:self.records.append(dict(stage='controller-stop-cleanup',error=type(exc).__name__))
        for p,command,out,err,op,ep,started in self.processes:
            forced=False
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                forced=True;p.terminate();p.wait(timeout=10)
            out.close();err.close()
            self.records.append(dict(stage='continuous-child',command=command,pid=p.pid,exitCode=p.returncode,
                forcedCleanup=forced,seconds=time.monotonic()-started,stdout=op.read_text(encoding='utf8'),stderr=ep.read_text(encoding='utf8')))
        print(json.dumps({'test':self.id(),'processEvidence':self.records,'childrenReaped':all(p.poll() is not None for p,*_ in self.processes)},ensure_ascii=False))
        self.temp.cleanup()

    def test_continuous_golden_contact_then_absorption_without_chat(self):
        f=P18Fixture(self.root,mode='contact',test_clock_rate=120);f.advance(3600)
        subject=f.state.subject_id;p=self.start()
        self.until(lambda:f.state.revision>=3,timeout=35,process=p)
        self.assertEqual(f.state.subject_id,subject)
        self.assertGreaterEqual(f.fake.effect_count,2)
        self.assertEqual(f.fake.credits,f.fake.effect_count)
        self.assertIsNone(p.poll())
        sessions=f.app.adapter._service._thinking.get_sessions(subject)
        self.assertTrue(any(any(x.source_type=='execution_result' for x in s.perception_snapshot.continuity_context.composition.snapshot.fragments)
                            for s in sessions if s.perception_snapshot))
        self.assertTrue(all(not s.perception_snapshot.external_facts for s in sessions if s.perception_snapshot))
        self.records.append(dict(stage='golden-observed',subject=subject,revision=f.state.revision,
            effects=f.fake.effect_count,credits=f.fake.credits,thinkSessions=len(sessions),noChatInputs=True))
        self.cli('stop');p.wait(timeout=10);self.assertEqual(p.returncode,0)

    def test_advancing_silent_process_continues_multiple_native_cycles(self):
        f=P18Fixture(self.root,mode='silence',test_clock_rate=120);f.advance(3600)
        p=self.start();self.until(lambda:f.state.revision>=3,timeout=35,process=p)
        self.assertIsNone(p.poll());self.assertEqual(f.fake.effect_count,0)
        self.assertTrue(self.cli('query')['host_alive'])
        self.cli('stop');p.wait(timeout=10);self.assertEqual(p.returncode,0)

    def test_idle_and_subject_silence_do_not_end_process(self):
        f=P18Fixture(self.root,mode='silence');f.advance(3600)
        p=self.start();self.until(lambda:f.store.load()['activity']=='MAINTENANCE',process=p)
        f.advance(60);self.until(lambda:f.state.revision==2,process=p)
        q=self.cli('query');self.assertTrue(q['host_alive'])
        self.assertEqual(f.fake.effect_count,0)
        self.assertIsNone(p.poll())
        self.cli('pause');revision=f.state.revision;f.advance(3600)
        threading.Event().wait(1.2)
        self.assertIsNone(p.poll());self.assertEqual(f.state.revision,revision)
        self.cli('resume');self.until(lambda:f.store.load()['activity']=='MAINTENANCE',process=p)
        f.advance(60);self.until(lambda:f.state.revision>revision,process=p)
        self.cli('stop');p.wait(timeout=10)
        p2=self.start();p2.wait(timeout=10)
        self.assertEqual(p2.returncode,0)
        self.assertEqual(f.store.load()['desired'],'STOPPED')

    def test_resource_wait_host_lives_and_restores_without_message(self):
        f=P18Fixture(self.root,tokens=0);f.advance(3600)
        self.observer=f.host.query
        p=self.start();self.until(lambda:f.store.load()['activity']=='MAINTENANCE',process=p)
        f.advance(60);self.until(lambda:f.store.load()['activity']=='WAITING_RESOURCES',process=p)
        self.assertTrue(self.cli('query')['host_alive']);self.assertEqual(f.state.revision,1)
        used=f.resources.get_resource_state(f.state.subject_id).token_used
        threading.Event().wait(1.2)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
        f.grant_test_budget(100000);f.advance(5)
        self.until(lambda:f.state.revision==2,process=p)
        self.cli('stop');p.wait(timeout=10)

    def test_two_real_processes_cannot_dispatch_same_subject(self):
        f=P18Fixture(self.root,need_delta=1)
        first=self.start();self.until(lambda:f.store.host_alive(),process=first)
        second=self.start();second.wait(timeout=10)
        self.assertEqual(second.returncode,2)
        self.assertIsNone(first.poll());self.assertEqual(f.fake.credits,0)
        self.cli('stop');first.wait(timeout=10)

    def test_real_process_crash_after_effect_restarts_original_identity(self):
        f=P18Fixture(self.root,mode='contact')
        # Prepare due work through the same host, without introducing a message.
        with f.host.running():f.advance(3600);f.host.tick()
        f.advance(60)
        script=("import os,sys; from pathlib import Path; from continuity_engine.testing.p18_runtime_fixture import P18Fixture; "
                "f=P18Fixture(Path(sys.argv[1]),initialize=False); "
                "f.fault=lambda stage: os._exit(73) if stage=='after_native_effect' else None; f.host.serve()")
        child=self.start([sys.executable,'-c',script,str(self.root)])
        child.wait(timeout=20);self.assertEqual(child.returncode,73)
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.state.revision,1)
        used=f.resources.get_resource_state(f.state.subject_id).token_used
        resumed=self.start();self.until(lambda:f.state.revision==2,process=resumed)
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
        self.cli('stop');resumed.wait(timeout=10)
        self.assertEqual(resumed.returncode,0)


if __name__=='__main__':unittest.main()
