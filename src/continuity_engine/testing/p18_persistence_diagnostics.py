"""Bounded TEST-only persistence telemetry; no body, exception text or repr."""
import hashlib
import json
import linecache
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from continuity_engine.storage import json_repository


def exception_chain(exc):
    root=Path(__file__).resolve().parents[1];rows=[];seen=set()
    while exc is not None and id(exc) not in seen and len(rows)<4:
        seen.add(id(exc));frames=[];operation='other'
        for frame in traceback.extract_tb(exc.__traceback__)[-24:]:
            path=Path(frame.filename).resolve()
            if path.is_relative_to(root):
                frames.append({'file':path.relative_to(root).as_posix(),'line':frame.lineno,'function':frame.name})
                if frame.name=='_replace_payload':operation='replace'
                if frame.name=='_write_payload':
                    line=linecache.getline(frame.filename,frame.lineno).strip()
                    for token,step in [('mkdir','create_directory'),('NamedTemporaryFile','create_temporary'),
                            ('temporary.write','write'),('temporary.flush','flush'),('fsync','fsync'),
                            ('_replace_payload','replace'),('os.replace','replace'),('unlink','cleanup')]:
                        if token in line:operation=step;break
        kind=type(exc).__name__ if type(exc).__module__=='builtins' else 'ENGINE_EXCEPTION'
        row={'type':kind,'operation':operation,'frames':frames,'errno':None,'winerror':None}
        if isinstance(exc,OSError):
            for key in ('errno','winerror'):
                value=getattr(exc,key,None)
                if type(value) is int:row[key]=value
        rows.append(row)
        exc=exc.__cause__ if exc.__suppress_context__ else exc.__cause__ or exc.__context__
    return rows


def emit(record,sink=None):
    """One independent stderr fallback; telemetry never replaces the error."""
    try:
        if sink is not None:sink(record)
        else:print(json.dumps(record),file=sys.stderr,flush=True)
    except Exception:
        try:print('TEST_PERSISTENCE_DIAGNOSTIC_UNAVAILABLE',file=sys.stderr,flush=True)
        except Exception:pass


def lock_owned():
    return json_repository._STATE_WRITE_LOCK._is_owned()


def install(repository,*,root,context=lambda:{},sink=None):
    """Observe this TEST repository instance only; original writes are untouched."""
    original=repository._write_payload;root=Path(root).resolve()
    def snapshot(path):
        try:
            data=path.read_bytes();value=json.loads(data)
            return {'hash':hashlib.sha256(data).hexdigest(),
                    'revision':value.get('state',value).get('revision')}
        except (OSError,ValueError,TypeError,AttributeError):return {'hash':None,'revision':None}
    def write(path,data):
        path=Path(path).resolve()
        if not path.is_relative_to(root):return original(path,data)
        before=snapshot(path);started=time.monotonic();owned=lock_owned()
        try:return original(path,data)
        except BaseException as exc:
            try:
                updates=data.get('updates') or [];last=updates[-1] if updates else {}
                metadata=last.get('event',{}).get('metadata',{})
                # Stable internal identifiers only. Unknown values are hashed.
                identities={k:hashlib.sha256(str(v).encode()).hexdigest() for k,v in metadata.items()
                            if k in {'action_session_id','action_decision_id','action_plan_id','think_id',
                                     'wake_session_id','perception_id','thinking_result_id'}}
                record={'stage':'persistence-failure-before-unwind','code':'TEST_STATE_SAVE_FAILED',
                    'file':path.relative_to(root).as_posix(),'before':before,'after':snapshot(path),
                    'expectedRevision':last.get('before_revision'),
                    'targetRevision':data.get('state',data).get('revision'),
                    'updateIdentityHash':hashlib.sha256(str(last.get('update_id')).encode()).hexdigest(),
                    'eventIdentityHash':hashlib.sha256(str(last.get('event',{}).get('event_id')).encode()).hexdigest(),
                    'identityHashes':identities,'pid':os.getpid(),'thread':threading.get_ident(),
                    'lockOwnedAtWrite':owned,'lockOwnedAtException':lock_owned(),
                    'elapsedSeconds':round(time.monotonic()-started,6),'chain':exception_chain(exc),
                    'context':context()}
                emit(record,sink)
            except Exception:emit({'code':'TEST_PERSISTENCE_DIAGNOSTIC_UNAVAILABLE'},sink)
            raise
    repository._write_payload=write
    return original
