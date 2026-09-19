"""Single local host/control checkpoint. No work result or mental-state ledger."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import tempfile
from threading import Lock, RLock

from continuity_engine.domain.action_planning import digest, identifier
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError, STATES, ACTIVITIES, parse

_GUARD=Lock()
_LOCKS={}


def safe_root(value):
    raw=Path(value).absolute()
    for p in (raw,*raw.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0)&0x400):
            raise RuntimeBoundaryError('RUNTIME_PATH_LINK_FORBIDDEN')
        if os.path.normcase(p.name) in {os.path.normcase('.continuity-data'),os.path.normcase('.assistant-data')}:
            raise RuntimeBoundaryError('RUNTIME_FORMAL_ROOT_FORBIDDEN')
    root=raw.resolve()
    repository=Path(__file__).resolve().parents[3]
    if root==repository or root in repository.parents or repository in root.parents or (root/'.git').exists():
        raise RuntimeBoundaryError('RUNTIME_REPOSITORY_ROOT_FORBIDDEN')
    return root


@contextmanager
def file_lock(path, *, create=True):
    """OS ownership lasts until handle close; crashed processes release it."""
    for p in (path,*path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0)&0x400):
            raise RuntimeBoundaryError('RUNTIME_PATH_LINK_FORBIDDEN')
    if create:path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b' if create else 'r+b') as handle:
        if create and handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RuntimeBoundaryError('RUNTIME_BUSY') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)


class JsonRuntimeRepository:
    def __init__(self, root, *, subject_id, environment):
        identifier(subject_id)
        if environment not in {'TEST','RESEARCH'}:raise RuntimeBoundaryError('RUNTIME_PRODUCTION_NOT_READY')
        self.root=safe_root(root);self.subject_id=subject_id;self.environment=environment
        self.path=self.root/'persistent-runtime'/'runtime.v1.json'
        self.owner_path=self.path.with_name('owner.lock')
        self.root_hash=digest(os.path.normcase(str(self.root)))
        with _GUARD:self.lock=_LOCKS.setdefault(str(self.path),RLock())

    def empty(self):
        return dict(version='p18-runtime-v1',subject_id=self.subject_id,environment=self.environment,root_hash=self.root_hash,
            revision=0,desired='RUNNING',state='START',activity='IDLE',generation=0,owner=None,
            last_time=None,next_check_at=None,last_task=None,reason='INITIALIZED',commands=[],observations=0,
            interruptions=[])

    def load(self):
        safe_root(self.root)
        safe_root(self.path)
        if not self.path.exists():raise RuntimeBoundaryError('RUNTIME_NOT_INITIALIZED')
        try:
            envelope=json.loads(self.path.read_text(encoding='utf-8'));d=envelope['document']
            if set(envelope)!={'document','hash'} or envelope['hash']!=digest(d) or set(d)!=set(self.empty()):raise ValueError()
            if any(d[k]!=self.empty()[k] for k in ('version','subject_id','environment','root_hash')):raise ValueError()
            if d['desired'] not in {'RUNNING','PAUSED','STOPPED'} or d['state'] not in STATES or d['activity'] not in ACTIVITIES:raise ValueError()
            if d['desired']=='STOPPED' and d['state']!='STOP':raise ValueError()
            for k in ('revision','generation','observations'):
                if type(d[k]) is not int or d[k]<0:raise ValueError()
            for k in ('last_time','next_check_at'):
                if d[k] is not None:parse(d[k])
            for k in ('owner','last_task'):
                if d[k] is not None:identifier(d[k])
            if not isinstance(d['reason'],str) or not d['reason'] or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in d['reason']):raise ValueError()
            if not isinstance(d['commands'],list):raise ValueError()
            seen=set()
            previous=0
            for c in d['commands']:
                if set(c)!={'id','hash','operation','revision'} or c['id'] in seen:raise ValueError()
                identifier(c['id']);seen.add(c['id'])
                if not c['id'].startswith('sha256:') or len(c['id'])!=71:raise ValueError()
                if c['operation'] not in {'PAUSE','RESUME','STOP'} or type(c['revision']) is not int or not 1<=c['revision']<=d['revision']:raise ValueError()
                if not isinstance(c['hash'],str) or not c['hash'].startswith('sha256:'):raise ValueError()
                if c['revision']<=previous:raise ValueError()
                previous=c['revision']
            if d['commands']:
                if any(c['operation']=='STOP' for c in d['commands'][:-1]):raise ValueError()
                expected={'PAUSE':'PAUSED','RESUME':'RUNNING','STOP':'STOPPED'}[d['commands'][-1]['operation']]
                if d['desired']!=expected:raise ValueError()
            if not isinstance(d['interruptions'],list) or len(d['interruptions'])>64:raise ValueError()
            for row in d['interruptions']:
                if set(row)!={'generation','reason','last_trusted_time'}:raise ValueError()
                if type(row['generation']) is not int or not 0<=row['generation']<=d['generation']:raise ValueError()
                if row['reason'] not in {'PROCESS_INTERRUPTED','PRIOR_HOST_LOST','HOST_DETACHED'}:raise ValueError()
                if row['last_trusted_time'] is not None:parse(row['last_trusted_time'])
            return d
        except Exception:raise RuntimeBoundaryError('RUNTIME_CHECKPOINT_CORRUPT') from None

    @contextmanager
    def transaction(self):
        safe_root(self.root)
        with self.lock,file_lock(self.path.with_suffix('.lock')):
            yield self.load() if self.path.exists() else None

    def initialize(self):
        with self.transaction() as d:
            if d is None:self.save(self.empty())
        return self.load()

    def save(self,d):
        safe_root(self.root)
        safe_root(self.path)
        if d['root_hash']!=self.root_hash or d['subject_id']!=self.subject_id or d['environment']!=self.environment:
            raise RuntimeBoundaryError('RUNTIME_CHECKPOINT_BINDING')
        current=self.load() if self.path.exists() else None
        if current is not None and d['revision']!=current['revision']:raise RuntimeBoundaryError('RUNTIME_REVISION_CONFLICT')
        d['revision']+=1
        fd,name=tempfile.mkstemp(prefix='.runtime-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
                json.dump({'document':d,'hash':digest(d)},f,ensure_ascii=False,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def host_alive(self):
        if not self.owner_path.exists():return False
        try:
            with file_lock(self.owner_path,create=False):return False
        except RuntimeBoundaryError as exc:
            if str(exc)=='RUNTIME_BUSY':return True
            raise
