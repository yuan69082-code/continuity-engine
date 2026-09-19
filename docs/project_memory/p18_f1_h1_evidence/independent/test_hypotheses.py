"""Bounded TEST experiments. No shared implementation is modified."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from continuity_engine.testing.p18_persistence_diagnostics import exception_chain

READER = r'''
import io,json,sys
from pathlib import Path
from continuity_engine.storage.json_runtime_repository import JsonRuntimeRepository
root=Path(sys.argv[1]);repo=JsonRuntimeRepository(root,subject_id=sys.argv[2],environment='TEST')
target=repo.path.resolve();original=io.open
class Held:
 def __init__(self,h):self.h=h
 def __enter__(self):return self
 def __exit__(self,*args):return self.h.__exit__(*args)
 def read(self,*args,**kw):
  print('READ_HELD',flush=True)
  if sys.stdin.readline().strip()!='release':raise RuntimeError('TEST_RELEASE_REQUIRED')
  return self.h.read(*args,**kw)
 def __getattr__(self,k):return getattr(self.h,k)
def opened(file,*args,**kw):
 h=original(file,*args,**kw)
 return Held(h) if not isinstance(file,int) and Path(file).resolve()==target else h
io.open=opened
d=repo.load();print(json.dumps({'revision':d['revision'],'activity':d['activity']}),flush=True)
'''

def snapshot(f):
    tasks=f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST')
    sessions=f.work.thinking.get_sessions(f.state.subject_id)
    return dict(clock=f.clock.now().isoformat(),runtime=f.host.query(),stateRevision=f.state.revision,
        tasks=[{k:t.to_dict()[k] for k in ('task_id','state','attempt_count','last_attempt_id','next_attempt_at','due_at','last_receipt_status')} for t in tasks],
        sessions=[dict(id=s.think_id,status=s.status.value,completed=s.completed_successfully,
            providerExecution=s.provider_execution,stateUpdate=s.state_update_id) for s in sessions],
        providerCalls=f.provider.calls,effects=f.fake.effect_count,credits=f.fake.credits)

class Hypotheses(unittest.TestCase):
    def fixture(self,**kwargs):
        temp=tempfile.TemporaryDirectory(prefix='p18-f1-h1-');self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name),**kwargs)

    def test_h1_without_contention_waits_and_recovers(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            f.advance(3600);f.host.tick();self.assertEqual(f.store.load()['activity'],'MAINTENANCE')
            f.advance(60);f.host.tick()
            print(json.dumps({'test':self.id(),'beforeStop':snapshot(f)},default=str))
            self.assertEqual(f.store.load()['activity'],'WAITING_RESOURCES')
            self.assertEqual((f.provider.calls,f.fake.credits),(0,0))
            f.grant_test_budget(100000);f.advance(5);f.host.tick();self.assertEqual(f.state.revision,2)
            f.control('STOP');self.assertFalse(f.host.tick())

    def test_h1_short_real_query_reader_keeps_resource_wait_observable(self):
        f=self.fixture(tokens=0);original=os.replace;failures=[];released=[];child=None;reader=None;ready=[]
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            before=f.store.path.read_bytes()
            child=subprocess.Popen([sys.executable,'-c',READER,str(f.runtime.data_root),f.state.subject_id],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            reader=threading.Thread(target=lambda:ready.append(child.stdout.readline().strip()),daemon=True)
            reader.start();reader.join(5)
            def replace(src,dst):
                try:return original(src,dst)
                except OSError as exc:
                    if Path(dst)==f.store.path and not failures:
                        failures.append(dict(operation='replace',path='persistent-runtime/runtime.v1.json',
                            chain=exception_chain(exc),oldHash=hashlib.sha256(before).hexdigest(),
                            unchanged=f.store.path.read_bytes()==before,readerPid=child.pid,writerPid=os.getpid(),
                            pendingActivity=json.loads(Path(src).read_text(encoding='utf8'))['document']['activity']))
                        child.stdin.write('release\n');child.stdin.flush();released.append(True)
                        child.wait(timeout=5)
                    raise
            try:
                self.assertEqual(ready,['READ_HELD'])
                with patch('os.replace',side_effect=replace):f.host.tick()
                d=snapshot(f)
                # No further trusted time advance: matches the historical observer.
                for _ in range(3):f.host.tick()
                print(json.dumps({'test':self.id(),'failureEvidence':failures,'beforeStop':d,
                    'afterThreeTicks':snapshot(f)},default=str))
                self.assertEqual(f.store.load()['activity'],'WAITING_RESOURCES',
                    'short legal query read must not replace resource waiting with frozen BACKOFF')
            finally:
                out,err=child.communicate(None if released else 'release\n',timeout=5);reader.join(1)
                print(json.dumps({'test':self.id(),'childExit':child.returncode,'childrenReaped':child.poll() is not None,
                    'forcedCleanup':False,'stdout':out,'stderr':err}))
                f.control('STOP');self.assertFalse(f.host.tick())

    def test_f1_time_advances_at_each_native_handoff(self):
        for stage in ('before_native_perception','before_provider','after_native_thinking',
                      'after_native_action_checkpoint','after_native_effect','after_native_evolution'):
            with self.subTest(stage=stage):
                f=self.fixture(mode='silence');hits=[]
                with f.host.running():
                    f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
                    self.assertEqual(f.state.revision,2)
                    f.control('PAUSE');f.advance(3600);f.host.tick();self.assertEqual(f.state.revision,2)
                    f.control('RESUME');f.host.tick();self.assertEqual(f.store.load()['activity'],'MAINTENANCE')
                    f.advance(60)
                    def handoff(at):
                        if at==stage and not hits:hits.append(at);f.advance(60)
                    f.host.hook=handoff;f.fault=handoff
                    f.host.tick();f.host.hook=None;f.fault=lambda _:None
                    print(json.dumps({'test':self.id(),'handoff':stage,'hits':hits,'beforeStop':snapshot(f)},default=str))
                    self.assertEqual(hits,[stage]);self.assertEqual(f.state.revision,3)
                    self.assertEqual(f.provider.calls,2);self.assertEqual(f.fake.credits,0)
                    f.control('STOP');self.assertFalse(f.host.tick())

    def test_f1_reader_released_before_classification_does_not_stall_second_cycle(self):
        from test_p18_persistence import READER as SUBJECT_READER
        from continuity_engine.storage import json_repository
        f=self.fixture(mode='silence');original=os.replace;errors=[];ready=[];child=None;thread=None;probes=[]
        target=f.core.subject_states._repository._path_for(f.state.subject_id)
        check=json_repository._replace_contended
        def classify(error,path):
            result=check(error,path);probes.append(result);return result
        def handoff(stage):
            nonlocal child,thread
            if stage=='after_native_effect' and child is None:
                child=subprocess.Popen([sys.executable,'-c',SUBJECT_READER,str(target.parent),f.state.subject_id],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                thread=threading.Thread(target=lambda:ready.append(child.stdout.readline().strip()),daemon=True)
                thread.start();thread.join(5);self.assertEqual(ready,['READ_HANDLE_HELD'])
        def replace(src,dst):
            try:return original(src,dst)
            except OSError as exc:
                if Path(dst)==target and child is not None and not errors:
                    errors.append(dict(chain=exception_chain(exc),operation='replace',unchanged=target.read_bytes()==before,
                        beforeHash=hashlib.sha256(before).hexdigest(),readerPid=child.pid,writerPid=os.getpid()))
                    child.stdin.write('release\n');child.stdin.flush();child.wait(timeout=5)
                raise
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick();self.assertEqual(f.state.revision,2)
            f.control('PAUSE');f.advance(3600);f.host.tick();f.control('RESUME');f.host.tick();f.advance(60)
            before=target.read_bytes();f.fault=handoff
            try:
                with patch('os.replace',side_effect=replace),patch.object(json_repository,'_replace_contended',side_effect=classify):f.host.tick()
                observed=f.state.revision
                print(json.dumps({'test':self.id(),'osErrors':errors,'classification':probes,'beforeStop':snapshot(f)},default=str))
                for _ in range(3):f.host.tick()
                self.assertEqual(f.state.revision,observed)
                f.fault=lambda _:None;f.advance(5);f.host.tick()
                print(json.dumps({'test':self.id(),'afterDueRecovery':snapshot(f)},default=str))
                self.assertEqual(f.state.revision,3);self.assertEqual(f.provider.calls,2)
                self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,640)
                self.assertEqual(f.fake.credits,0)
                self.assertEqual(observed,3,'reader already released; second cycle should not stall until another clock advance')
            finally:
                f.fault=lambda _:None
                if child is not None:
                    out,err=child.communicate(None if errors else 'release\n',timeout=5);thread.join(1)
                    print(json.dumps({'test':self.id(),'childExit':child.returncode,'childrenReaped':child.poll() is not None,
                        'forcedCleanup':False,'stdout':out,'stderr':err}))
                f.control('STOP');self.assertFalse(f.host.tick())

if __name__=='__main__':unittest.main()
