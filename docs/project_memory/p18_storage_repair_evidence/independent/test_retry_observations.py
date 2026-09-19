"""TEST-only evidence for the old refusal constraint, not a runtime patch."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from continuity_engine.storage import json_repository as storage


def delete_access(path):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
    close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
    handle=create(str(path),0x10000,7,None,3,0x80,None)
    if handle==wintypes.HANDLE(-1).value:return {'allowed':False,'winerror':ctypes.get_last_error()}
    close(handle);return {'allowed':True,'winerror':0}


def facts(error,temp,target,old,prepared):
    def bound(value,path):
        return value is not None and os.path.normcase(os.path.abspath(value))==os.path.normcase(str(path.absolute()))
    return dict(errno=error.errno,winerror=getattr(error,'winerror',None),
        sourceBound=bound(error.filename,temp),targetBound=bound(getattr(error,'filename2',None),target),
        targetUnchanged=target.read_bytes()==old,tempUnchanged=temp.read_bytes()==prepared,
        sameParent=temp.parent==target.parent,targetRegular=target.is_file(),tempRegular=temp.is_file(),
        targetReadOnly=bool(target.stat().st_file_attributes&1),tempReadOnly=bool(temp.stat().st_file_attributes&1),
        targetDeleteAccess=delete_access(target),tempDeleteAccess=delete_access(temp),
        currentSharingProbe=storage._replace_contended(error,target))


class RetryObservationTests(unittest.TestCase):
    def test_released_reader_and_bound_injection_have_same_current_facts(self):
        self.assertEqual(os.name,'nt','this probe requires actual Windows observations')
        with tempfile.TemporaryDirectory(prefix='p18-retry-facts-') as name:
            root=Path(name).resolve();target=root/'target.json';temp=root/'.own.tmp'
            old=b'{"revision":1}\n';prepared=b'{"revision":2}\n'
            target.write_bytes(old);temp.write_bytes(prepared)
            native=None
            with target.open('rb'):
                try:os.replace(temp,target)
                except OSError as error:native=error
            self.assertIsNotNone(native)
            real=facts(native,temp,target,old,prepared)
            injected=PermissionError(13,'TEST fixed native-shaped refusal',str(temp),5,str(target))
            synthetic=facts(injected,temp,target,old,prepared)
            self.assertEqual(real,synthetic)
            self.assertEqual(real['winerror'],5)
            self.assertTrue(real['sourceBound'] and real['targetBound'])
            self.assertFalse(real['currentSharingProbe'])
            self.assertTrue(real['targetDeleteAccess']['allowed'] and real['tempDeleteAccess']['allowed'])
            print(json.dumps({'test':self.id(),'nativeReleased':real,'boundSyntheticNoHolder':synthetic,
                'conclusion':'Same present facts do not prove the prior cause.',
                'targetSHA256':hashlib.sha256(old).hexdigest(),'temporarySHA256':hashlib.sha256(prepared).hexdigest()}))

    def test_current_writer_refuses_bound_fixed_error_without_guard_call(self):
        with tempfile.TemporaryDirectory(prefix='p18-retry-refusal-') as name:
            root=Path(name).resolve();target=root/'target.json';temp=root/'.own.tmp'
            old=b'{"revision":1}\n';prepared=b'{"revision":2}\n'
            target.write_bytes(old);temp.write_bytes(prepared);guards=[]
            error=PermissionError(13,'TEST fixed native-shaped refusal',str(temp),5,str(target))
            with storage.state_write_retry_guard(lambda:guards.append(True)),patch.object(os,'replace',side_effect=error) as replaced:
                with self.assertRaises(PermissionError) as caught:storage._replace_payload(temp,target,old)
            self.assertIs(caught.exception,error);self.assertEqual(replaced.call_count,1);self.assertEqual(guards,[])
            self.assertEqual(target.read_bytes(),old);self.assertEqual(temp.read_bytes(),prepared)
            print(json.dumps({'test':self.id(),'replaceCalls':replaced.call_count,'guardCalls':len(guards),
                'facts':facts(error,temp,target,old,prepared),'currentlyRefused':True}))

if __name__=='__main__':unittest.main()
