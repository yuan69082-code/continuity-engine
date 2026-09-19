"""Native denial controls: permissions changed only by the isolated TEST setup."""
import contextlib,json,os
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'docs/project_memory/p18_storage_repair_evidence/independent')]
from acl_access_probe import Windows,DELETE,DELETE_CHILD
from test_p18_storage_retry import StorageRetryTests
from continuity_engine.storage.json_repository import state_write_retry_guard

class NativeAccessTests(StorageRetryTests):
    def denial(self,kind,mode):
        if kind=='subject':repo,service,target=self.subject()
        else:repo=self.runtime();target=repo.path
        api=Windows();events=[];old=target.read_bytes();native=os.replace;calls=[]
        try:
            with contextlib.ExitStack() as stack:
                if mode=='acl':
                    stack.enter_context(api.deny(target,DELETE,events,'target.json'))
                    stack.enter_context(api.deny(target.parent,DELETE_CHILD,events,'parent'))
                else:
                    attributes=api.attributes(target)
                    api.set_attributes(target,attributes|1)
                    stack.callback(api.set_attributes,target,attributes)
                restricted=api.security_structure(target)
                def replace(source,destination):
                    calls.append(True)
                    return native(source,destination)
                with patch('os.replace',side_effect=replace):
                    with self.assertRaises(PermissionError) as caught:
                        if kind=='subject':
                            with state_write_retry_guard(lambda:None):service.record_interaction('retry-subject')
                        else:
                            with repo.transaction() as document:repo.save(document)
                self.assertEqual(len(calls),1)
                self.assertEqual(target.read_bytes(),old)
                self.assertEqual(api.security_structure(target),restricted)
                self.assertEqual(caught.exception.winerror,5)
                print(json.dumps({'kind':kind,'mode':mode,'type':type(caught.exception).__name__,
                    'errno':caught.exception.errno,'winerror':caught.exception.winerror,'attempts':len(calls),
                    'targetDeleteAccess':api.access(target),'unchanged':target.read_bytes()==old}),flush=True)
        finally:print(json.dumps({'test':self.id(),'ownedTestSetupAndRestoration':events}),flush=True)
        self.no_temporary(target)
    def test_subject_acl(self):self.denial('subject','acl')
    def test_runtime_acl(self):self.denial('runtime','acl')
    def test_subject_readonly(self):self.denial('subject','readonly')
    def test_runtime_readonly(self):self.denial('runtime','readonly')

def native_suite():
    import unittest
    return unittest.TestSuite(NativeAccessTests('test_'+name) for name in (
        'subject_acl','runtime_acl','subject_readonly','runtime_readonly'))
