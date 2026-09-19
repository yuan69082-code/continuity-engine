"""Bounded real-handle and post-effect persistence probes for P18 (TEST only)."""
import hashlib
import contextlib
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

from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage import json_repository
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from continuity_engine.testing.p18_persistence_diagnostics import install


READER = r'''
import hashlib,io,json,sys
from pathlib import Path
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
root=Path(sys.argv[1]); subject=sys.argv[2]; repo=JsonSubjectStateRepository(root)
target=repo._path_for(subject).resolve(); original=io.open
class HeldReader:
    def __init__(self,handle):self.handle=handle
    def __enter__(self):return self
    def __exit__(self,*args):return self.handle.__exit__(*args)
    def read(self,*args,**kw):
        print('READ_HANDLE_HELD',flush=True)
        if sys.stdin.readline().strip()!='release':raise RuntimeError('TEST_RELEASE_REQUIRED')
        data=self.handle.read(*args,**kw)
        print(json.dumps({'readHash':hashlib.sha256(data.encode('utf8')).hexdigest()}),flush=True)
        return data
    def __getattr__(self,key):return getattr(self.handle,key)
def opened(file,*args,**kw):
    handle=original(file,*args,**kw)
    if not isinstance(file,int) and Path(file).resolve()==target:return HeldReader(handle)
    return handle
io.open=opened
state=repo.load(subject)
print(json.dumps({'revision':state.revision}),flush=True)
'''


def error_identity(exc):
    return {'type':type(exc).__name__ if type(exc).__module__=='builtins' else 'ENGINE_EXCEPTION',
            'errno':exc.errno if isinstance(exc,OSError) else None,
            'winerror':getattr(exc,'winerror',None)}


class PersistenceTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='ps18-');self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name),mode='contact')

    def ready(self,f):f.advance(3600);f.host.tick();f.advance(60)

    def state_path(self,f):return f.core.subject_states._repository._path_for(f.state.subject_id)

    def unchanged_effect(self,f,expected_revision=2):
        self.assertEqual(f.state.revision,expected_revision)
        self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,1,1))
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,320)

    def test_post_effect_replace_error_recovers_original_fact_after_due_time(self):
        f=self.fixture();target=self.state_path(f);original=os.replace;hits=[];diagnostic=io.StringIO()
        def replace(src,dst):
            if Path(dst)==target and f.fake.effect_count==1 and not hits:
                hits.append(True);raise PermissionError(13,'synthetic private error text')
            return original(src,dst)
        with f.host.running():
            self.ready(f);before=target.read_bytes()
            with contextlib.redirect_stderr(diagnostic),patch('os.replace',side_effect=replace):f.host.tick()
            self.assertEqual(hits,[True]);self.assertEqual(target.read_bytes(),before)
            self.assertEqual(f.state.revision,1);self.assertEqual(f.fake.effect_count,1)
            session=f.work._session(next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id,environment='TEST') if t.task_id.startswith('cognition:')))
            self.assertTrue(session.completed_successfully);self.assertIsNone(session.state_update_id)
            # No trusted time advance: verification is not yet due, not a new dispatch.
            f.host.tick();self.assertEqual(f.state.revision,1)
            print(json.dumps({'test':self.id(),'stage':'before-recovery','diagnostics':diagnostic.getvalue()}))
            self.assertNotIn('synthetic private error text',diagnostic.getvalue())
            f.advance(5);f.host.tick();self.unchanged_effect(f)
            for _ in range(2):f.host.tick()
            self.unchanged_effect(f)
            self.assertEqual(list(target.parent.glob('*.tmp')),[])

    def test_post_commit_return_loss_restores_without_second_revision(self):
        f=self.fixture();hits=[]
        def fault(stage):
            if stage=='after_native_evolution' and not hits:
                hits.append(True);raise RuntimeError('TEST_RETURN_LOST')
        with f.host.running():
            self.ready(f);f.fault=fault;f.host.tick();f.fault=lambda stage:None
            self.assertEqual(hits,[True]);self.unchanged_effect(f)
            f.advance(5);f.host.tick();self.unchanged_effect(f)

    def test_real_reader_blocks_no_new_effect_or_revision_after_release(self):
        f=self.fixture();target=self.state_path(f);child=None;ready=[];thread=None;released=[]
        original_check=json_repository._replace_contended
        def contention(error,path):
            answer=original_check(error,path)
            if answer and child is not None and not released:
                released.append(True);child.stdin.write('release\n');child.stdin.flush()
            return answer
        def fault(stage):
            nonlocal child,thread
            if stage=='after_native_effect' and child is None:
                child=subprocess.Popen([sys.executable,'-c',READER,str(target.parent),f.state.subject_id],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                thread=threading.Thread(target=lambda:ready.append(child.stdout.readline().strip()),daemon=True)
                thread.start();thread.join(5);self.assertEqual(ready,['READ_HANDLE_HELD'])
        with f.host.running():
            self.ready(f);f.fault=fault;diagnostic=io.StringIO()
            try:
                with contextlib.redirect_stderr(diagnostic),patch.object(json_repository,'_replace_contended',side_effect=contention):f.host.tick()
                print(json.dumps({'test':self.id(),'stage':'held-real-reader-before-stop',
                    'revision':f.state.revision,'effects':f.fake.effect_count,'credits':f.fake.credits,
                    'diagnostics':diagnostic.getvalue()}))
                held_revision=f.state.revision
            finally:
                f.fault=lambda stage:None
                if child is not None:
                    out,err=child.communicate(None if released else 'release\n',timeout=5);thread.join(1)
                    print(json.dumps({'test':self.id(),'childrenReaped':child.poll() is not None,
                        'exitCode':child.returncode,'forcedCleanup':False,'stdout':out,'stderr':err}))
                    self.assertEqual(child.returncode,0,err)
            f.advance(5);f.host.tick();self.unchanged_effect(f)
            self.assertEqual(held_revision,2,'released short reader must permit original Evolution replacement')

    def test_actual_repository_reader_does_not_prevent_atomic_transition(self):
        with tempfile.TemporaryDirectory(prefix='p18-persistence-') as root:
            repo=JsonSubjectStateRepository(root); service=SubjectStateService(repo); service.create('test-subject')
            target=repo._path_for('test-subject'); before=target.read_bytes()
            child=subprocess.Popen([sys.executable,'-c',READER,root,'test-subject'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            ready=[];reader=threading.Thread(target=lambda:ready.append(child.stdout.readline().strip()),daemon=True)
            reader.start();reader.join(5);failure=None;out=err='';forced=False;released=[]
            original_check=json_repository._replace_contended
            def contention(error,path):
                answer=original_check(error,path)
                if answer and not released:
                    released.append(True);child.stdin.write('release\n');child.stdin.flush()
                return answer
            try:
                self.assertEqual(ready,['READ_HANDLE_HELD'])
                try:
                    with json_repository.state_write_retry_guard(lambda:None),patch.object(json_repository,'_replace_contended',side_effect=contention):
                        service.record_interaction('test-subject')
                except OSError as exc:failure=error_identity(exc)
                after=target.read_bytes()
                print(json.dumps({'test':self.id(),'stage':'writer-before-reader-release','operation':'state-transition',
                    'file':target.name,'beforeHash':hashlib.sha256(before).hexdigest(),
                    'afterHash':hashlib.sha256(after).hexdigest(),'exception':failure,
                    'pid':os.getpid(),'thread':threading.get_ident(),'readerPid':child.pid,
                    'temporaryFiles':[p.name for p in Path(root).glob('*.tmp')]}))
            finally:
                try:out,err=child.communicate(None if released else 'release\n',timeout=5)
                except subprocess.TimeoutExpired:
                    forced=True;child.terminate();out,err=child.communicate(timeout=5)
                reader.join(1)
                print(json.dumps({'test':self.id(),'childrenReaped':child.poll() is not None,
                    'exitCode':child.returncode,'forcedCleanup':forced,'stdout':out,'stderr':err}))
            self.assertFalse(forced);self.assertEqual(child.returncode,0,err)
            self.assertIsNone(failure,'real repository reader blocked atomic state replacement')
            self.assertNotEqual(before,after)
            self.assertEqual(json.loads(out.splitlines()[0])['readHash'],hashlib.sha256(before).hexdigest())
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_normal_transition_without_overlapping_reader(self):
        with tempfile.TemporaryDirectory(prefix='p18-persistence-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            before=repo._path_for('test-subject').read_bytes()
            service.record_interaction('test-subject')
            self.assertNotEqual(before,repo._path_for('test-subject').read_bytes())
            self.assertEqual(len(service.get_update_history('test-subject')),1)
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_stop_during_replace_wait_prevents_new_evolution(self):
        f=self.fixture();target=self.state_path(f);held=[];original=json_repository._replace_contended;stopped=[]
        def fault(stage):
            if stage=='after_native_effect' and not held:held.append(target.open('rb'))
        def contention(error,path):
            answer=original(error,path)
            if answer and not stopped:
                stopped.append(True);f.control('STOP');held[0].close()
            return answer
        with f.host.running():
            self.ready(f);f.fault=fault
            try:
                with patch.object(json_repository,'_replace_contended',side_effect=contention):f.host.tick()
            finally:
                for handle in held:handle.close()
                f.fault=lambda stage:None
            self.assertEqual(stopped,[True]);self.assertEqual(f.state.revision,1)
            self.assertFalse(f.host.tick());self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
            self.assertEqual(list(target.parent.glob('*.tmp')),[])

    def test_long_sharing_failure_is_bounded_preserves_old_record(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            path=repo._path_for('test-subject');before=path.read_bytes();started=time.monotonic()
            with json_repository.state_write_retry_guard(lambda:None),path.open('rb'):
                if os.name=='nt':
                    with self.assertRaises(PermissionError) as error:service.record_interaction('test-subject')
                    print(json.dumps({'test':self.id(),'exception':error_identity(error.exception)}))
                else:service.record_interaction('test-subject')
            self.assertLess(time.monotonic()-started,1.5)
            if os.name=='nt':self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_nonsharing_errors_are_not_retried_or_half_written(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            path=repo._path_for('test-subject');before=path.read_bytes()
            for error in (PermissionError(13,'private'),FileNotFoundError(2,'private'),OSError(28,'private')):
                with self.subTest(errno=error.errno),json_repository.state_write_retry_guard(lambda:None),patch('os.replace',side_effect=error) as replace:
                    with self.assertRaises(type(error)):service.record_interaction('test-subject')
                    self.assertEqual(replace.call_count,1)
                self.assertEqual(path.read_bytes(),before);self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_partial_save_steps_cleanup_and_keep_system_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            path=repo._path_for('test-subject');before=path.read_bytes();rows=[];install(repo,root=root,sink=rows.append)
            original=tempfile.NamedTemporaryFile
            class Partial:
                def __init__(self,base,step):self.base=base;self.step=step
                def __enter__(self):self.base.__enter__();return self
                def __exit__(self,*args):return self.base.__exit__(*args)
                def __getattr__(self,key):return getattr(self.base,key)
                def write(self,data):
                    if self.step=='write':raise OSError(28,'private disk detail')
                    return self.base.write(data)
                def flush(self):
                    if self.step=='flush':raise OSError(28,'private disk detail')
                    return self.base.flush()
            for step in ('create_temporary','write','flush','fsync'):
                with self.subTest(step=step):
                    prior_files=set(Path(root).glob('*.tmp'))
                    def factory(*args,**kw):
                        if step=='create_temporary':raise OSError(28,'private disk detail')
                        return Partial(original(*args,**kw),step)
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(patch('tempfile.NamedTemporaryFile',side_effect=factory))
                        if step=='fsync':stack.enter_context(patch('os.fsync',side_effect=OSError(28,'private disk detail')))
                        with self.assertRaises(OSError):service.record_interaction('test-subject')
                    print(json.dumps({'test':self.id(),'step':step,'diagnostic':rows[-1],
                        'temporaryFiles':[p.name for p in Path(root).glob('*.tmp')]}))
                    self.assertEqual(rows[-1]['chain'][0]['errno'],28)
                    self.assertEqual(rows[-1]['chain'][0]['operation'],step)
                    self.assertNotIn('private disk detail',json.dumps(rows[-1]))
                    self.assertEqual(path.read_bytes(),before)
                    self.assertEqual(set(Path(root).glob('*.tmp')),prior_files)

    def test_diagnostic_sink_failure_does_not_replace_primary_error(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            primary=OSError(28,'private primary');output=io.StringIO();calls=[]
            def sink(record):calls.append(True);raise RuntimeError('private diagnostic failure')
            install(repo,root=root,sink=sink)
            with contextlib.redirect_stderr(output),patch('os.replace',side_effect=primary):
                with self.assertRaises(OSError) as error:service.record_interaction('test-subject')
            self.assertIs(error.exception,primary);self.assertEqual(calls,[True])
            self.assertEqual(output.getvalue().strip(),'TEST_PERSISTENCE_DIAGNOSTIC_UNAVAILABLE')
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_cleanup_failure_keeps_primary_and_secondary_system_errors(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            before=repo._path_for('test-subject').read_bytes();rows=[];install(repo,root=root,sink=rows.append)
            primary=OSError(28,'private primary');cleanup=PermissionError(13,'private cleanup')
            with patch('os.replace',side_effect=primary),patch.object(Path,'unlink',side_effect=cleanup):
                with self.assertRaises(OSError) as caught:service.record_interaction('test-subject')
            print(json.dumps({'test':self.id(),'diagnostic':rows[-1],
                'temporaryFiles':[p.name for p in Path(root).glob('*.tmp')]}))
            self.assertIs(caught.exception,primary)
            self.assertEqual([x['errno'] for x in rows[-1]['chain']],[28,13])
            self.assertEqual(repo._path_for('test-subject').read_bytes(),before)
            self.assertEqual(len(list(Path(root).glob('*.tmp'))),1)

    def test_changed_revision_during_wait_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='ps18-') as root:
            repo=JsonSubjectStateRepository(root);service=SubjectStateService(repo);service.create('test-subject')
            path=repo._path_for('test-subject');held=path.open('rb');changed=[]
            original=json_repository._replace_contended
            def contention(error,target):
                answer=original(error,target)
                if answer and not changed:
                    held.close()
                    service.record_interaction('test-subject')
                    changed.append(path.read_bytes())
                return answer
            try:
                with json_repository.state_write_retry_guard(lambda:None),patch.object(json_repository,'_replace_contended',side_effect=contention):
                    with self.assertRaises(StateEvolutionError):service.record_interaction('test-subject')
            finally:held.close()
            self.assertEqual(len(changed),1);self.assertEqual(path.read_bytes(),changed[0])
            self.assertEqual(len(service.get_update_history('test-subject')),1)
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_pause_and_permission_change_during_wait_block_new_state(self):
        for mode in ('pause','permission'):
            with self.subTest(mode=mode):
                f=self.fixture();target=self.state_path(f);held=[];changed=[]
                original=json_repository._replace_contended
                def fault(stage):
                    if stage=='after_native_effect' and not held:held.append(target.open('rb'))
                def contention(error,path):
                    answer=original(error,path)
                    if answer and not changed:
                        changed.append(True)
                        if mode=='pause':f.control('PAUSE')
                        else:f.base.permission.references_allowed=False
                        held[0].close()
                    return answer
                with f.host.running():
                    self.ready(f);f.fault=fault
                    try:
                        with patch.object(json_repository,'_replace_contended',side_effect=contention):f.host.tick()
                    finally:
                        for handle in held:handle.close()
                        f.fault=lambda stage:None
                    self.assertEqual(changed,[True]);self.assertEqual(f.state.revision,1)
                    self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,1,1))
                    if mode=='pause':f.control('RESUME')
                    else:f.base.permission.references_allowed=True
                    f.advance(5);f.host.tick();self.unchanged_effect(f)
                    self.assertEqual(list(target.parent.glob('*.tmp')),[])

    def test_reopened_post_effect_failure_recovers_without_provider_or_new_charge(self):
        f=self.fixture();target=self.state_path(f);original=os.replace;hits=[]
        def replace(src,dst):
            if Path(dst)==target and f.fake.effect_count==1 and not hits:
                hits.append(True);raise OSError(28,'TEST disk unavailable')
            return original(src,dst)
        with f.host.running():
            self.ready(f)
            with patch('os.replace',side_effect=replace):f.host.tick()
            old=f.work.thinking.get_sessions(f.state.subject_id)[0]
            original_usage=[u.to_dict() for u in f.resources.get_usage_history(f.state.subject_id)]
            self.assertEqual(f.state.revision,1);self.assertTrue(old.completed_successfully)
        reopened=P18Fixture(f.root,initialize=False)
        with reopened.host.running():
            reopened.advance(5);reopened.host.tick()
            self.assertEqual(reopened.state.revision,2)
            self.assertEqual((reopened.provider.calls,reopened.fake.effect_count,reopened.fake.credits),(0,1,1))
            restored=reopened.work.thinking.get_sessions(reopened.state.subject_id)[0]
            self.assertEqual(restored.think_id,old.think_id);self.assertIsNotNone(restored.state_update_id)
            self.assertEqual(reopened.resources.get_resource_state(reopened.state.subject_id).token_used,320)
            current_usage=[u.to_dict() for u in reopened.resources.get_usage_history(reopened.state.subject_id)]
            self.assertEqual([u['usage_id'] for u in current_usage],[u['usage_id'] for u in original_usage])
            self.assertEqual([u['estimated_tokens'] for u in current_usage],[u['estimated_tokens'] for u in original_usage])
            original_thinking=next(u for u in original_usage if u['session_id']==old.think_id)
            recovered_thinking=next(u for u in current_usage if u['session_id']==old.think_id)
            self.assertIsNone(original_thinking['actual_tokens'])
            self.assertEqual(recovered_thinking['actual_tokens'],256)
            reopened.host.tick();self.assertEqual(reopened.state.revision,2)
