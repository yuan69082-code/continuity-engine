"""Opt-in TEST-only cross-process lock tracing. No runtime source changes."""
import os
if os.environ.get('W04_LOCK_TRACE_DIR'):
    import atexit, contextlib, hashlib, json, pathlib, threading, time
    from continuity_engine.storage import json_runtime_repository as repo
    from continuity_engine.services import persistent_runtime_service as service
    events=[];overhead=0;dropped=0
    def emit(event,**fields):
        global overhead,dropped
        t=time.perf_counter_ns()
        if len(events)<30000:events.append(dict(ns=t,pid=os.getpid(),thread=threading.get_ident(),event=event,**fields))
        else:dropped+=1
        overhead+=time.perf_counter_ns()-t
    def pathid(path):return hashlib.sha256(str(path).encode()).hexdigest()[:16]
    original_lock=repo.file_lock
    @contextlib.contextmanager
    def lock(path,**kw):
        fields=dict(file=path.name,path_id=pathid(path),wait=kw.get('wait_seconds',0),checkpoint=kw.get('checkpoint',False))
        emit('lock_request',**fields)
        try:
            with original_lock(path,**kw):
                emit('lock_acquired',**fields)
                try:yield
                finally:emit('lock_releasing',**fields)
            emit('lock_released',**fields)
        except BaseException as exc:
            emit('lock_exception',error_type=type(exc).__name__,**fields);raise
    repo.file_lock=service.file_lock=lock
    def fields(d):return {k:d.get(k) for k in ('revision','generation','desired','activity','reason','next_check_at')} if isinstance(d,dict) else {}
    def wrap(obj,name):
        original=getattr(obj,name)
        def traced(self,*args,**kw):
            info=dict(method=name)
            if name=='control':info.update(operation=args[0] if args else None,command_hash=pathid(kw.get('command_id','')))
            if name=='save' and args:info.update(fields(args[0]))
            emit('call',**info)
            try:
                value=original(self,*args,**kw)
                emit('return',**info,result=fields(value));return value
            except BaseException as exc:
                emit('error',**info,error_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None));raise
        setattr(obj,name,traced)
    for name in ('load','save'):wrap(repo.JsonRuntimeRepository,name)
    for name in ('control','tick','_observe','_checkpoint_backoff'):wrap(service.PersistentRuntimeService,name)
    if os.environ.get('W04_LOCK_HOLD_DIAGNOSTIC')=='1':
        original_save=repo.JsonRuntimeRepository.save
        def controlled_save(self,d):
            # TEST diagnostic only: legal transaction remains held throughout.
            if d['reason'] in ('OWNER_STOP','HOST_ATTACHED'):
                emit('injected_hold_start',reason=d['reason'])
                time.sleep(.40)
                emit('injected_hold_end',reason=d['reason'])
            return original_save(self,d)
        repo.JsonRuntimeRepository.save=controlled_save
    @atexit.register
    def finish():
        dest=pathlib.Path(os.environ['W04_LOCK_TRACE_DIR'])/('process-'+str(os.getpid())+'.json')
        with dest.open('x',encoding='utf8') as f:json.dump(dict(events=events,bookkeeping_ns=overhead,dropped=dropped),f,indent=2)
