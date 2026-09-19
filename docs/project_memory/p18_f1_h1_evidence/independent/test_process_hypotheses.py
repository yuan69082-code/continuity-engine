"""Original process assertions/timeouts with one controlled ordinary read overlap."""
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'src')]
import test_p18_runtime_process as original_tests


def child(root,kind):
    from continuity_engine.testing.p18_runtime_fixture import P18Fixture
    from continuity_engine.testing.p18_persistence_diagnostics import exception_chain
    f=P18Fixture(Path(root),initialize=False);directory=Path(root).resolve();hit=[]
    state_path=f.core.subject_states._repository._path_for(f.state.subject_id)
    replace=os.replace
    def wait_for(name):
        deadline=time.monotonic()+10
        while not (directory/name).exists():
            if time.monotonic()>deadline:raise RuntimeError('TEST_HANDSHAKE_TIMEOUT')
            threading.Event().wait(.01)
    def replacing(src,dst):
        target=Path(dst)
        relevant=(kind=='H1' and target==f.store.path or kind=='F1' and target==state_path)
        if relevant and not hit:
            data=json.loads(Path(src).read_text(encoding='utf8'))
            chosen=(data.get('document',{}).get('activity')=='WAITING_RESOURCES' if kind=='H1'
                else f.state.revision==2)
            if chosen:
                hit.append(True);old=target.read_bytes()
                (directory/'reader-request.json').write_text(json.dumps({'path':target.relative_to(directory).as_posix()}),encoding='utf8')
                (directory/'reader-request-ready').write_text('READY',encoding='utf8')
                wait_for('reader-ready')
                try:return replace(src,dst)
                except OSError as exc:
                    record=dict(operation='replace',relativePath=target.relative_to(directory).as_posix(),
                        pid=os.getpid(),thread=threading.get_ident(),chain=exception_chain(exc),
                        beforeHash=hashlib.sha256(old).hexdigest(),afterHash=hashlib.sha256(target.read_bytes()).hexdigest(),
                        currentRevision=f.state.revision,runtimeRevision=f.store.load()['revision'])
                    (directory/'replace-failure.json').write_text(json.dumps(record),encoding='utf8')
                    wait_for('reader-released')
                    raise
        return replace(src,dst)
    with patch('os.replace',side_effect=replacing):f.host.serve()


class OriginalFlowWithReadOverlap(original_tests.RuntimeProcessTests):
    def setUp(self):
        super().setUp();self.reader_thread=None;self.reader_done=threading.Event();self.reader_errors=[]

    def reader(self):
        deadline=time.monotonic()+30;request=self.root/'reader-request.json'
        try:
            while not (self.root/'reader-request-ready').exists():
                if self.reader_done.is_set():return
                if time.monotonic()>deadline:raise RuntimeError('TEST_READER_REQUEST_TIMEOUT')
                self.reader_done.wait(.01)
            path=self.root/json.loads(request.read_text(encoding='utf8'))['path']
            assert path.resolve().is_relative_to(self.root.resolve())
            with path.open('rb') as handle:
                (self.root/'reader-ready').write_text('READY',encoding='utf8')
                while not (self.root/'replace-failure.json').exists():
                    if self.reader_done.is_set():return
                    if time.monotonic()>deadline:raise RuntimeError('TEST_READER_ERROR_TIMEOUT')
                    self.reader_done.wait(.01)
                handle.read()
            (self.root/'reader-released').write_text('RELEASED',encoding='utf8')
        except BaseException as exc:self.reader_errors.append(type(exc).__name__)

    def start(self,command=None):
        if command is None:
            kind='H1' if 'resource_wait' in self._testMethodName else 'F1'
            command=[sys.executable,str(Path(__file__).resolve()),'child',str(self.root),kind]
            if self.reader_thread is None:
                self.reader_thread=threading.Thread(target=self.reader,daemon=True);self.reader_thread.start()
        return super().start(command)

    def tearDown(self):
        self.reader_done.set()
        if self.reader_thread is not None:self.reader_thread.join(3)
        evidence={}
        for name in ('reader-request.json','replace-failure.json','reader-ready','reader-released'):
            path=self.root/name
            if path.exists():evidence[name]=path.read_text(encoding='utf8')
        print(json.dumps({'test':self.id(),'stage':'read-overlap-before-original-stop-cleanup',
            'evidence':evidence,'readerErrors':self.reader_errors,
            'readerReaped':self.reader_thread is None or not self.reader_thread.is_alive()}))
        super().tearDown()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='child':child(sys.argv[2],sys.argv[3])
