"""Independent Windows sharing probes; native replace/probe/retry are unpatched."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage import json_repository as storage
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class IndependentPersistenceTests(unittest.TestCase):
    def root(self):
        temp=tempfile.TemporaryDirectory(prefix='ip18-')
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def fixture(self):
        return P18Fixture(self.root(),mode='contact')

    def prepare(self,f):
        f.advance(3600);f.host.tick();f.advance(60)

    def hold_after_effect(self,f):
        held=[]
        target=f.core.subject_states._repository._path_for(f.state.subject_id)
        def hold(stage):
            if stage=='after_native_effect' and not held:
                handle=target.open('rb');held.append(handle);self.addCleanup(handle.close)
        f.fault=hold
        return held,target

    def completed(self,f,calls=1):
        self.assertEqual(f.state.revision,2)
        self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(calls,1,1))
        sessions=f.work.thinking.get_sessions(f.state.subject_id)
        self.assertEqual(len(sessions),1)
        self.assertTrue(sessions[0].completed_successfully)
        self.assertIsNotNone(sessions[0].state_update_id)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,320)
        return sessions[0].think_id

    def native_retry_case(self,operation=None):
        f=self.fixture();held,target=self.hold_after_effect(f);stages=[]
        def hook(stage):
            if stage=='before_native_evolution':
                stages.append(stage)
                if len(stages)==2:
                    if operation:f.control(operation)
                    held[0].close()
        with f.host.running():
            self.prepare(f);f.host.hook=hook
            try:f.host.tick()
            finally:
                for handle in held:handle.close()
                f.host.hook=None;f.fault=lambda stage:None
            self.assertEqual(len(stages),2)
            self.assertEqual(list(target.parent.glob('*.tmp')),[])
            if operation:
                self.assertEqual(f.state.revision,1)
                self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,1,1))
                original=f.work.thinking.get_sessions(f.state.subject_id)[0].think_id
                if operation=='STOP':self.assertFalse(f.host.tick())
                else:
                    self.assertTrue(f.host.tick());self.assertEqual(f.state.revision,1)
                    f.control('RESUME');f.advance(5);f.host.tick()
                    self.assertEqual(self.completed(f),original)
            else:self.completed(f)
            print(json.dumps(dict(test=self.id(),retryControl=operation,guardCalls=len(stages),
                revision=f.state.revision,providerCalls=f.provider.calls,effects=f.fake.effect_count,credits=f.fake.credits)))

    def test_real_handle_release_allows_native_retry(self):self.native_retry_case()

    def test_stop_at_native_retry_guard_prevents_state_commit(self):self.native_retry_case('STOP')

    def test_pause_at_native_retry_guard_then_resume_same_fact(self):self.native_retry_case('PAUSE')

    def long_hold_case(self,reopen):
        f=self.fixture();held,target=self.hold_after_effect(f)
        with f.host.running():
            self.prepare(f)
            try:
                self.assertTrue(f.host.tick())
                self.assertEqual(f.state.revision,1)
                self.assertTrue(f.store.host_alive())
                self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,1,1))
                self.assertEqual(list(target.parent.glob('*.tmp')),[])
                original=f.work.thinking.get_sessions(f.state.subject_id)[0]
                self.assertTrue(original.completed_successfully)
                self.assertIsNone(original.state_update_id)
                f.control('PAUSE');self.assertTrue(f.host.tick())
                self.assertEqual(f.host.query()['desired'],'PAUSED')
            finally:
                for handle in held:handle.close()
                f.fault=lambda stage:None
            if not reopen:
                f.control('RESUME');f.advance(5);f.host.tick()
                self.assertEqual(self.completed(f),original.think_id)
                f.host.tick();self.completed(f)
        if reopen:
            restored=P18Fixture(f.root,initialize=False)
            with restored.host.running():
                self.assertEqual(restored.host.query()['desired'],'PAUSED')
                restored.control('RESUME');restored.advance(5);restored.host.tick()
                self.assertEqual(self.completed(restored,calls=0),original.think_id)
                restored.host.tick();self.completed(restored,calls=0)

    def test_real_long_handle_wait_recovers_without_duplicate_effect(self):self.long_hold_case(False)

    def test_real_long_handle_wait_recovers_after_reopen(self):self.long_hold_case(True)

    def repository(self):
        repo=storage.JsonSubjectStateRepository(self.root())
        service=SubjectStateService(repo);service.create('independent-test-subject')
        return repo,service,repo._path_for('independent-test-subject')

    def test_retry_guard_does_not_leak_to_another_thread(self):
        repo,service,path=self.repository();calls=[];before=path.read_bytes()
        with path.open('rb'),storage.state_write_retry_guard(lambda:calls.append(True)):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(service.record_interaction,'independent-test-subject')
                with self.assertRaises(PermissionError):future.result(timeout=3)
        self.assertEqual(calls,[]);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(list(repo.root.glob('*.tmp')),[])

    def test_nested_guard_restores_outer_guard_after_exception(self):
        repo,service,path=self.repository();calls=[];held=path.open('rb')
        self.addCleanup(held.close)
        def outer():calls.append('outer');held.close()
        with storage.state_write_retry_guard(outer):
            try:
                with storage.state_write_retry_guard(lambda:calls.append('inner')):
                    raise RuntimeError('TEST scope unwind')
            except RuntimeError:pass
            service.record_interaction('independent-test-subject')
        self.assertEqual(calls,['outer'])
        self.assertIsNone(storage._RETRY_GUARD.get())
        self.assertEqual(list(repo.root.glob('*.tmp')),[])

    def test_winerror5_without_actual_handle_conflict_is_not_retried(self):
        repo,service,path=self.repository();calls=[];before=path.read_bytes()
        error=PermissionError(13,'TEST access denied');error.winerror=5
        with storage.state_write_retry_guard(lambda:calls.append(True)),patch.object(os,'replace',side_effect=error) as replaced:
            with self.assertRaises(PermissionError) as caught:
                service.record_interaction('independent-test-subject')
        self.assertIs(caught.exception,error);self.assertEqual(replaced.call_count,1)
        self.assertEqual(calls,[]);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(list(repo.root.glob('*.tmp')),[])


if __name__=='__main__':unittest.main()
