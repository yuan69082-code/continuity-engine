"""Independent, isolated P18 probes; no Engine source or formal data writes."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from continuity_engine.testing.p18_runtime_fixture import P18Fixture


# Hold a real authorized control transaction immediately before its save.
# The host must tolerate overlap, without permitting another host/owner.
CONTROL_HOLDER = r'''
import sys
from pathlib import Path
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
f=P18Fixture(Path(sys.argv[1]),initialize=False)
original=f.store.save
def delayed_save(d):
    print('CONTROL_LOCK_HELD',flush=True)
    sys.stdin.readline()
    return original(d)
f.store.save=delayed_save
f.host.control('PAUSE',command_id='independent-overlap',expected_revision=None,handle='p18-test-owner')
print('CONTROL_SAVED',flush=True)
'''


class IndependentRuntimeTests(unittest.TestCase):
    def fixture(self, **options):
        temp=tempfile.TemporaryDirectory(prefix='ir18-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name), **options)

    def launch(self, command):
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8',
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONUTF8':'1'},
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    @contextlib.contextmanager
    def held_control(self, f):
        p=self.launch([sys.executable,'-c',CONTROL_HOLDER,str(f.root)])
        ready=[]
        reader=threading.Thread(target=lambda:ready.append(p.stdout.readline().strip()),daemon=True)
        reader.start();reader.join(timeout=15)
        try:
            self.assertEqual(ready,['CONTROL_LOCK_HELD'])
            yield
        finally:
            try:out,err=p.communicate('\n',timeout=15)
            except subprocess.TimeoutExpired:
                p.terminate();out,err=p.communicate(timeout=10)
            reader.join(timeout=1)
            print(json.dumps({'test':self.id(),'controlPid':p.pid,'controlExit':p.returncode,
                              'controlStdout':out,'controlStderr':err},ensure_ascii=False))
            self.assertEqual(p.returncode,0,err)

    def test_idle_tick_survives_overlapping_owner_control(self):
        f=self.fixture(need_delta=1.0)
        error=None
        with f.host.running():
            f.host.tick()  # Complete initial maintenance before the overlap.
            f.advance(60)
            with self.held_control(f):
                try:f.host.tick()
                except Exception as exc:error=(type(exc).__name__,str(exc))
            self.assertEqual(f.store.load()['desired'],'PAUSED')
            print(json.dumps({'test':self.id(),'tickEscaped':error,'providerCalls':f.provider.calls}))
            self.assertIsNone(error,'A short legitimate control transaction escaped tick()')

    def test_paused_process_survives_overlapping_owner_control(self):
        f=self.fixture(need_delta=1.0)
        f.control('PAUSE')
        p=self.launch([sys.executable,'-m','continuity_engine.runtime','start','--root',str(f.root)])
        premature=None
        try:
            end=time.monotonic()+15
            while time.monotonic()<end:
                if f.store.load()['owner'] and f.store.host_alive():break
                if p.poll() is not None:self.fail('host failed before contention')
                threading.Event().wait(.05)
            self.assertIsNotNone(f.store.load()['owner'])
            with self.held_control(f):
                # Bounded diagnostic controller, not a product lifetime limit.
                end=time.monotonic()+2.5
                while p.poll() is None and time.monotonic()<end:threading.Event().wait(.05)
                premature=p.poll()
            self.assertIsNone(premature,'The continuous host exited without any STOP')
        finally:
            f.host.control('STOP',command_id='probe-cleanup',expected_revision=None,handle='p18-test-owner')
            forced=False
            try:out,err=p.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                forced=True;p.terminate();out,err=p.communicate(timeout=10)
            print(json.dumps({'test':self.id(),'hostPid':p.pid,'exitBeforeStop':premature,
                'exitCode':p.returncode,'forcedCleanup':forced,'stdout':out,'stderr':err},ensure_ascii=False))

    def test_uncontended_controls_and_host_continue(self):
        f=self.fixture(need_delta=1.0)
        with f.host.running():
            self.assertTrue(f.host.tick())
            f.control('PAUSE');self.assertTrue(f.host.tick())
            f.control('RESUME');f.advance(60);self.assertTrue(f.host.tick())
            self.assertEqual(f.provider.calls,0)
            f.control('STOP');self.assertFalse(f.host.tick())

    def test_reopen_query_has_no_persistent_writes(self):
        f=self.fixture()
        before={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        reopened=P18Fixture(f.root,initialize=False)
        q=reopened.host.query()
        after={p.relative_to(f.root).as_posix():p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(q['desired'],'RUNNING')

    def test_ordinary_wait_recovers_without_new_message(self):
        f=self.fixture(tokens=0)
        with f.host.running():
            f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            self.assertEqual(f.provider.calls,0)
            f.grant_test_budget(100000);f.advance(5);f.host.tick()
            self.assertEqual(f.provider.calls,1)
            self.assertEqual(f.state.revision,2)


if __name__=='__main__':unittest.main()
