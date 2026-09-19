"""R1 control contention and H1 pre-STOP observations, isolated TEST only."""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError,RuntimePolicy
from continuity_engine.storage.json_runtime_repository import RuntimeCheckpointBusy,file_lock
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from tests import test_p18_runtime_process as diagnostics


HOLDER=r'''
import sys
from pathlib import Path
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
f=P18Fixture(Path(sys.argv[1]),initialize=False)
original=f.store.save
def save(d):
    print('CONTROL_LOCK_HELD',flush=True)
    sys.stdin.readline()
    return original(d)
f.store.save=save
f.host.control(sys.argv[2],command_id=sys.argv[3],expected_revision=None,handle='p18-test-owner')
print('CONTROL_SAVED',flush=True)
'''


class RuntimeContentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rc18-')
        self.root=Path(self.temp.name);self.children=[];self.records=[]

    def fixture(self,**options):
        need_delta=options.pop('need_delta',.02)
        self.f=P18Fixture(self.root,policy=RuntimePolicy(idle_wait_seconds=.1,need_delta=need_delta),**options)
        return self.f

    def launch(self,command):
        p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf8',env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'},
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.children.append((p,command));return p

    def reap(self,p,data=None):
        if getattr(p,'evidence_saved',False):return
        forced=False
        try:out,err=p.communicate(data,timeout=15)
        except subprocess.TimeoutExpired:
            forced=True;p.terminate();out,err=p.communicate(timeout=10)
        command=next(c for child,c in self.children if child is p)
        self.records.append(dict(command=command,pid=p.pid,exitCode=p.returncode,stdout=out,stderr=err,forcedCleanup=forced))
        p.evidence_saved=True
        return out,err,forced

    def until(self,predicate,p=None,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return
            if p is not None:self.assertIsNone(p.poll(),'host exited without STOP')
            threading.Event().wait(.025)
        self.records.append(dict(stage='timeout-before-stop',snapshot=diagnostics.runtime_diagnostic(self.f,[c for c,_ in self.children])))
        self.fail('bounded contention controller timed out')

    @contextlib.contextmanager
    def held_control(self,operation='PAUSE',identity='held-command'):
        p=self.launch([sys.executable,'-c',HOLDER,str(self.root),operation,identity])
        ready=[];reader=threading.Thread(target=lambda:ready.append(p.stdout.readline().strip()),daemon=True)
        reader.start();reader.join(timeout=15)
        try:
            self.assertEqual(ready,['CONTROL_LOCK_HELD'])
            yield p
        finally:
            self.reap(p,'\n');reader.join(timeout=1)
            self.assertEqual(p.returncode,0)

    def start(self):return self.launch([sys.executable,'-m','continuity_engine.runtime','start','--root',str(self.root)])

    def stop(self,p):
        self.f.host.control('STOP',command_id='test-stop',expected_revision=None,handle='p18-test-owner')
        out,err,forced=self.reap(p)
        self.assertFalse(forced);self.assertEqual(p.returncode,0,err)
        return out,err

    def tearDown(self):
        if hasattr(self,'f'):
            self.records.append(dict(stage='before-stop-cleanup',snapshot=diagnostics.runtime_diagnostic(self.f,[p for p,_ in self.children])))
            if any(p.poll() is None for p,_ in self.children):
                try:self.f.host.control('STOP',command_id='fallback-stop',expected_revision=None,handle='p18-test-owner')
                except Exception:self.records.append(dict(stage='cleanup-stop',diagnostic='TEST_STOP_UNAVAILABLE'))
        for p,_ in self.children:self.reap(p,'\n' if p.poll() is None else None)
        print(json.dumps(dict(test=self.id(),processEvidence=self.records,childrenReaped=all(p.poll() is not None for p,_ in self.children))))
        self.temp.cleanup()

    def contention_process(self,mode):
        f=self.fixture(tokens=0 if mode=='RESOURCE_WAIT' else 100000,mode='contact',
                       need_delta=1 if mode=='RUNNING' else .02)
        with f.host.running():f.advance(3600);f.host.tick()
        if mode=='RESOURCE_WAIT':
            f.advance(60)
            with f.host.running():f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
        if mode=='PAUSED':f.control('PAUSE')
        p=self.start();self.until(lambda:f.store.host_alive(),p)
        # Ensure the process attached before the controlled transaction.
        self.until(lambda:f.store.load()['reason']!='HOST_DETACHED',p)
        resources=f.resources.get_resource_state(f.state.subject_id)
        used=resources.token_used;revision=f.state.revision
        with self.held_control():
            # Force a due observation while the control really owns the lock.
            # Waiting before next_check_at alone would not exercise R1.
            f.advance(60)
            before=f.store.path.read_bytes()
            threading.Event().wait(.9)
            self.assertIsNone(p.poll());self.assertTrue(f.host.query()['checkpoint_busy'])
            self.assertEqual(before,f.store.path.read_bytes())
            self.assertEqual(f.state.revision,revision);self.assertEqual(f.fake.effect_count,0)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
        self.until(lambda:f.store.load()['desired']=='PAUSED',p)
        f.advance(120);threading.Event().wait(.3)
        self.assertEqual(f.state.revision,revision);self.assertEqual(f.fake.effect_count,0)
        if mode=='RESOURCE_WAIT':f.grant_test_budget(100000)
        f.host.control('RESUME',command_id='resume',expected_revision=None,handle='p18-test-owner')
        if mode=='RUNNING':
            self.until(lambda:f.store.load()['reason']=='NO_CURRENT_NEED',p)
            self.assertEqual(f.state.revision,revision);self.assertEqual(f.fake.effect_count,0)
            _,err=self.stop(p);self.assertIn('RUNTIME_CHECKPOINT_BUSY',err)
            return
        self.until(lambda:f.state.revision==2,p)
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)
        used=f.resources.get_resource_state(f.state.subject_id).token_used
        sessions=f.work.thinking.get_sessions(f.state.subject_id)
        self.assertEqual(len(sessions),1)
        threading.Event().wait(.3)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
        self.assertEqual(f.fake.effect_count,1)
        _,err=self.stop(p);self.assertIn('RUNTIME_CHECKPOINT_BUSY',err)
        again=self.start();_,err,_=self.reap(again)
        self.assertEqual(again.returncode,0,err);self.assertEqual(f.store.load()['desired'],'STOPPED')
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)

    def test_running_process_control_competition(self):self.contention_process('RUNNING')
    def test_paused_process_control_competition(self):self.contention_process('PAUSED')
    def test_resource_wait_process_control_competition(self):self.contention_process('RESOURCE_WAIT')

    def test_idle_tick_busy_is_bounded_read_only_and_resumes(self):
        f=self.fixture(need_delta=1)
        with f.host.running():
            f.host.tick();f.advance(60)
            with self.held_control():
                before=f.store.path.read_bytes();start=time.monotonic()
                self.assertTrue(f.host.tick())
                self.assertLess(time.monotonic()-start,1.5)
                self.assertEqual(before,f.store.path.read_bytes());self.assertEqual(f.provider.calls,0)
            self.assertTrue(f.host.tick());self.assertEqual(f.host.query()['activity'],'PAUSED')
            self.assertEqual(f.provider.calls,0)

    def test_long_busy_control_rejects_without_record_and_same_identity_retries(self):
        f=self.fixture()
        with self.held_control():
            before=f.store.path.read_bytes();start=time.monotonic()
            with self.assertRaisesRegex(RuntimeCheckpointBusy,'RUNTIME_CHECKPOINT_BUSY'):
                f.host.control('STOP',command_id='not-yet-committed',expected_revision=None,handle='p18-test-owner')
            self.assertLess(time.monotonic()-start,1.5);self.assertEqual(before,f.store.path.read_bytes())
        f.host.control('STOP',command_id='not-yet-committed',expected_revision=None,handle='p18-test-owner')
        stopped=f.store.path.read_bytes()
        f.host.control('STOP',command_id='not-yet-committed',expected_revision=None,handle='p18-test-owner')
        self.assertEqual(stopped,f.store.path.read_bytes())

    def test_thread_transaction_also_has_bounded_wait(self):
        f=self.fixture();held=threading.Event();release=threading.Event()
        def hold():
            with f.store.transaction():held.set();release.wait(10)
        t=threading.Thread(target=hold);t.start();self.assertTrue(held.wait(5))
        try:
            before=f.store.path.read_bytes();start=time.monotonic()
            with self.assertRaises(RuntimeCheckpointBusy):f.control('PAUSE')
            self.assertLess(time.monotonic()-start,1.5);self.assertEqual(before,f.store.path.read_bytes())
        finally:release.set();t.join(timeout=5)
        self.assertFalse(t.is_alive());f.control('PAUSE');self.assertEqual(f.store.load()['desired'],'PAUSED')

    def test_short_lock_serializes_control_before_deadline(self):
        f=self.fixture();held=threading.Event();release=threading.Event()
        def hold():
            with f.store.transaction():held.set();release.wait(5)
        t=threading.Thread(target=hold);t.start();self.assertTrue(held.wait(5))
        timer=threading.Timer(.05,release.set);timer.start()
        try:f.control('PAUSE')
        finally:release.set();t.join(timeout=5);timer.join(timeout=5)
        self.assertEqual(f.store.load()['desired'],'PAUSED')

    def test_stale_cas_and_conflicting_identity_still_fail_closed(self):
        f=self.fixture();revision=f.store.load()['revision']
        with self.held_control():pass
        before=f.store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeBoundaryError,'REVISION_CONFLICT'):
            f.host.control('RESUME',command_id='stale',expected_revision=revision,handle='p18-test-owner')
        with self.assertRaisesRegex(RuntimeBoundaryError,'IDENTITY_CONFLICT'):
            f.host.control('RESUME',command_id='held-command',expected_revision=None,handle='p18-test-owner')
        self.assertEqual(before,f.store.path.read_bytes())

    def test_waiting_old_observation_does_not_overwrite_new_resume(self):
        f=self.fixture();f.control('PAUSE')
        with f.host.running():
            with self.held_control('RESUME') as p:
                def release():p.stdin.write('\n');p.stdin.flush()
                timer=threading.Timer(.05,release);timer.start()
                try:self.assertTrue(f.host.tick())
                finally:timer.join(timeout=5)
            current=f.store.load()
            self.assertEqual(current['desired'],'RUNNING')
            self.assertEqual(current['state'],'RESUME')
            self.assertEqual(current['reason'],'OWNER_RESUME')
            self.assertEqual(f.provider.calls,0)

    def test_second_host_still_immediately_rejected(self):
        f=self.fixture()
        with f.host.running():
            p=self.start();_,err,forced=self.reap(p)
            self.assertFalse(forced);self.assertEqual(p.returncode,2);self.assertEqual(err.strip(),'RUNTIME_BUSY')
            self.assertEqual(f.provider.calls,0);self.assertEqual(f.fake.effect_count,0)

    def test_corrupt_checkpoint_and_generation_fence_not_swallowed(self):
        f=self.fixture()
        with f.host.running():
            with f.store.transaction() as d:d['generation']+=1;f.store.save(d)
            before=f.store.path.read_bytes()
            with self.assertRaisesRegex(RuntimeBoundaryError,'STALE_OWNER'):f.host.tick()
            self.assertEqual(before,f.store.path.read_bytes())
        f.store.path.write_text('{}',encoding='utf8')
        with self.assertRaisesRegex(RuntimeBoundaryError,'CHECKPOINT_CORRUPT'):f.host.tick()
        with self.assertRaisesRegex(RuntimeBoundaryError,'CHECKPOINT_CORRUPT'):f.host.serve()
        self.assertEqual(f.store.path.read_text(encoding='utf8'),'{}')

    def test_owner_permission_rejection_not_treated_as_busy(self):
        f=self.fixture();f.identities.allowed=False
        before=f.store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeBoundaryError,'CONTROL_DENIED'):f.control('PAUSE')
        self.assertEqual(before,f.store.path.read_bytes())

    def test_original_exception_recorded_when_exit_checkpoint_available(self):
        f=self.fixture();diagnostic=io.StringIO()
        with contextlib.redirect_stderr(diagnostic):
            with self.assertRaisesRegex(RuntimeBoundaryError,'RUNTIME_TEST_FAILURE'):
                with f.host.running():
                    raise RuntimeBoundaryError('RUNTIME_TEST_FAILURE')
        self.assertFalse(f.store.host_alive())
        self.assertTrue(any(r['reason']=='PROCESS_INTERRUPTED' for r in f.store.load()['interruptions']))

    def test_long_busy_host_remains_live_and_diagnostic_is_not_flooded(self):
        f=self.fixture();f.control('PAUSE');p=self.start()
        self.until(lambda:f.store.host_alive(),p)
        self.until(lambda:f.store.load()['owner'] is not None,p)
        with self.held_control():
            before=f.store.path.read_bytes();end=time.monotonic()+2.2
            while time.monotonic()<end:
                self.assertIsNone(p.poll());threading.Event().wait(.1)
            self.assertEqual(before,f.store.path.read_bytes())
            self.assertTrue(f.host.query()['checkpoint_busy'])
        self.until(lambda:f.store.load()['reason']=='OWNER_PAUSE',p)
        _,err=self.stop(p)
        self.assertEqual(err.count('RUNTIME_CHECKPOINT_BUSY'),1)
        self.assertIn('RUNTIME_CHECKPOINT_AVAILABLE',err)
        self.assertEqual(f.state.revision,1);self.assertEqual(f.fake.credits,0)

    def test_effect_before_busy_observation_is_not_dispatched_again(self):
        f=self.fixture(mode='contact');holder=None
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60)
            def fault(stage):
                nonlocal holder
                if stage=='after_scheduler_completed' and holder is None:
                    holder=self.held_control();holder.__enter__()
            f.fault=fault
            try:self.assertTrue(f.host.tick())
            finally:
                if holder is not None:holder.__exit__(None,None,None)
            self.assertIsNotNone(holder);f.fault=lambda stage:None
            used=f.resources.get_resource_state(f.state.subject_id).token_used
            self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)
            self.assertEqual(f.provider.calls,1);self.assertEqual(f.state.revision,2)
            f.host.control('RESUME',command_id='resume-fact',expected_revision=None,handle='p18-test-owner')
            for _ in range(3):self.assertTrue(f.host.tick())
            self.assertEqual(f.provider.calls,1);self.assertEqual(f.fake.effect_count,1)
            self.assertEqual(f.fake.credits,1);self.assertEqual(f.state.revision,2)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)

    def test_real_busy_exit_keeps_original_error_and_releases_owner(self):
        f=self.fixture();attachment=f.host.running();attachment.__enter__()
        error=RuntimeBoundaryError('RUNTIME_TEST_FAILURE');diagnostic=io.StringIO()
        with self.held_control():
            before=f.store.path.read_bytes()
            with contextlib.redirect_stderr(diagnostic):
                self.assertFalse(attachment.__exit__(type(error),error,error.__traceback__))
            self.assertEqual(before,f.store.path.read_bytes());self.assertFalse(f.store.host_alive())
        self.assertIn('RUNTIME_EXIT_CHECKPOINT_BUSY',diagnostic.getvalue())
        with f.host.running():self.assertTrue(f.host.tick())
        self.assertTrue(any(r['reason']=='PRIOR_HOST_LOST' for r in f.store.load()['interruptions']))

    def test_non_contention_os_error_not_reclassified(self):
        f=self.fixture()
        target='msvcrt.locking' if os.name=='nt' else 'fcntl.flock'
        with patch(target,side_effect=OSError(errno.EBADF,'private external diagnostic')):
            with self.assertRaisesRegex(RuntimeBoundaryError,'^RUNTIME_LOCK_UNAVAILABLE$'):
                with f.store.transaction():pass

    def test_start_waits_for_checkpoint_without_relaxing_owner_lock(self):
        f=self.fixture()
        with self.held_control():
            p=self.start();threading.Event().wait(.9)
            self.assertIsNone(p.poll());self.assertEqual(f.provider.calls,0)
        self.until(lambda:f.store.host_alive(),p)
        self.stop(p)

    def test_h1_clock_advance_during_maintenance_observation(self):
        f=self.fixture(tokens=0);original=f.store.save;advanced=[]
        def save(d):
            if d['activity']=='MAINTENANCE' and not advanced:
                f.advance(60);advanced.append(True)
            return original(d)
        with f.host.running():
            f.advance(3600)
            with patch.object(f.store,'save',side_effect=save):f.host.tick()
            self.assertEqual(advanced,[True]);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            snapshot=diagnostics.runtime_diagnostic(f)
            self.assertEqual(snapshot['runtime']['resources']['token_used'],0)
            self.assertTrue(all(t['attempt_count']==0 for t in snapshot['tasks'] if t['task_id'].startswith('cognition:')))
            self.records.append(dict(stage='h1-controlled-clock-interleaving',snapshot=snapshot))

    def test_h1_controller_timeout_captures_state_before_stop(self):
        controller=diagnostics.RuntimeProcessTests(methodName='runTest');controller.setUp()
        try:
            f=P18Fixture(controller.root,tokens=0);controller.diagnostic_fixture=f
            p=controller.start()
            with self.assertRaisesRegex(AssertionError,'bounded test controller timed out'):
                controller.until(lambda:False,timeout=.3,process=p)
            snapshot=next(r['snapshot'] for r in controller.records if r['stage']=='controller-timeout-before-stop')
            self.assertIn('trusted_time',snapshot);self.assertIn('next_check_at',snapshot['runtime'])
            self.assertIn('resources',snapshot['runtime']);self.assertIn('tasks',snapshot)
            self.assertTrue(snapshot['processes'][0]['alive'])
            self.assertNotEqual(snapshot['runtime']['desired'],'STOPPED')
        finally:controller.tearDown()


if __name__=='__main__':unittest.main()
