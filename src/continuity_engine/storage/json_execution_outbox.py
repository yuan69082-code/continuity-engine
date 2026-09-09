"""Bounded delivery index only; E5-A owns all requests/results.

Nonblocking OS lock protects the entire local transaction across processes.
There is no background worker, polling, duplicate request body, or receipt body.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from threading import Lock, RLock

from continuity_engine.domain.action_planning import digest, exact, hash_value, identifier
from continuity_engine.domain.execution import DELIVERY_STATES, ROUTES, ExecutionError

_GUARD = Lock()
_LOCKS = {}


class JsonExecutionOutbox:
    def __init__(self, root, *, subject_id, environment):
        identifier(subject_id)
        if environment not in ('TEST','RESEARCH'):
            raise ExecutionError('EXECUTION_STORE_BOUNDARY')
        self.subject_id, self.environment = subject_id, environment
        self.path = Path(root)/'execution-outbox'/environment.lower()/digest(subject_id)[7:]/'delivery.v1.json'
        with _GUARD:
            self.lock = _LOCKS.setdefault(os.path.normcase(str(self.path.resolve())), RLock())

    def _safe(self):
        for path in (self.path, *self.path.parents):
            if path.is_symlink() or (path.exists() and getattr(path.lstat(),'st_file_attributes',0) & 0x400):
                raise ExecutionError('EXECUTION_STORE_LINK_FORBIDDEN')

    def empty(self):
        return dict(version='p17-outbox-v1',subject_id=self.subject_id,environment=self.environment,revision=0,entries=[])

    def load(self):
        self._safe()
        if not self.path.exists():
            return self.empty()
        try:
            envelope=exact(json.loads(self.path.read_text(encoding='utf-8')),{'document','hash'})
            d=exact(envelope['document'],set(self.empty()))
            if envelope['hash'] != digest(d) or any(d[k]!=self.empty()[k] for k in ('version','subject_id','environment')):
                raise ValueError()
            if type(d['revision']) is not int or d['revision']<0 or not isinstance(d['entries'],list) or len(d['entries'])>256:
                raise ValueError()
            seen=set()
            for e in d['entries']:
                exact(e,{'request_id','request_hash','route_hash','state','attempts','receipt_hash','reason','links'})
                identifier(e['request_id']);hash_value(e['request_hash']);hash_value(e['route_hash'])
                if e['request_id'] in seen or e['state'] not in DELIVERY_STATES or type(e['attempts']) is not int or not 0<=e['attempts']<=3:
                    raise ValueError()
                seen.add(e['request_id'])
                if e['receipt_hash'] is not None:hash_value(e['receipt_hash'])
                if e['state']=='DELIVERED' and e['receipt_hash'] is None:raise ValueError()
                if e['state']!='DELIVERED' and e['receipt_hash'] is not None:raise ValueError()
                if e['reason'] not in {'PENDING','DISPATCHING','UNKNOWN','VERIFIED','CANCELLED','NETWORK_FAILED','MATERIAL_REJECTED'}:raise ValueError()
                if not isinstance(e['links'],list) or len(e['links'])>16:raise ValueError()
                for link in e['links']:
                    exact(link,{'kind','request_id'})
                    if link['kind'] not in ROUTES|{'COMPENSATION'}:raise ValueError()
                    if link['request_id'] is not None:identifier(link['request_id'])
            return d
        except Exception:
            raise ExecutionError('EXECUTION_OUTBOX_CORRUPT') from None

    @contextmanager
    def transaction(self):
        self._safe()
        with self.lock:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            lock_path=self.path.with_suffix('.lock')
            if lock_path.is_symlink() or (lock_path.exists() and getattr(lock_path.lstat(),'st_file_attributes',0)&0x400):
                raise ExecutionError('EXECUTION_STORE_LINK_FORBIDDEN')
            with lock_path.open('a+b') as handle:
                if handle.tell()==0:
                    handle.write(b'0');handle.flush()
                handle.seek(0)
                try:
                    if os.name=='nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:
                    raise ExecutionError('EXECUTION_BUSY') from None
                try:
                    yield self.load()
                finally:
                    handle.seek(0)
                    if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                    else:fcntl.flock(handle,fcntl.LOCK_UN)

    def save(self, document):
        """Caller holds transaction lock; replace once, no partial queue writes."""
        self._safe()
        document['revision']+=1
        fd,name=tempfile.mkstemp(prefix='.delivery-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
                json.dump({'document':document,'hash':digest(document)},stream,ensure_ascii=False,sort_keys=True)
                stream.write('\n');stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
