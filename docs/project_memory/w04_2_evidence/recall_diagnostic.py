"""One predetermined old/current pair, unchanged W02 assertions and 1000ms budget."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NAMES=['test_four_materials_preanswer_with_original_1000ms_policy',
       'test_third_message_sixteen_candidates_and_current_derived_sources']
OVERLAYS=['src/continuity_engine/domain/action_planning.py',
          'src/continuity_engine/domain/device_operation.py',
          'src/continuity_engine/services/execution_service.py',
          'src/continuity_engine/services/execution_context_source.py',
          'src/continuity_engine/services/device_operation_service.py',
          'src/continuity_engine/testing/w04_device_fixture.py',
          'tests/test_w04_2_simulation.py']

def worker(output):
    import unittest
    from unittest.mock import patch
    from tests.test_w02_recall_timeout import W02RecallTimeoutTests
    from tests.test_p18_runtime_contention import RuntimeContentionTests
    from continuity_engine.services.associative_recall_service import AssociativeRecallService
    from continuity_engine.services.execution_service import ExecutionService
    from continuity_engine.services.execution_context_source import ExecutionContextSource
    from continuity_engine.domain.action_planning import ActionSpecification
    from contextlib import ExitStack
    rows=[]; activity=[False]; counts={}; original=AssociativeRecallService._prepare
    def keep(record):
        rows.append({key:record.get(key) for key in ('request_id','status','stop_reason','elapsed_ms',
            'retrieved_count','model_calls','external_calls','policy','snapshot_hash')})
    def prepare(self,perception,operation,save,**kwargs):
        activity[0]=True
        def saved(record):
            keep(record)
            return save(record)
        try:
            result=original(self,perception,operation,saved,**kwargs)
            keep(result[2]);return result
        finally:activity[0]=False
    with ExitStack() as stack:
        stack.enter_context(patch.object(AssociativeRecallService,'_prepare',prepare))
        for cls,name in ((ActionSpecification,'__post_init__'),(ExecutionService,'__init__'),
                         (ExecutionService,'current'),(ExecutionService,'results_for_context'),
                         (ExecutionContextSource,'resolve')):
            if not hasattr(cls,name): continue
            old=getattr(cls,name);key=cls.__name__+'.'+name
            counts[key]={'all':0,'during_recall':0}
            def wrapped(*args,_old=old,_key=key,**kwargs):
                counts[_key]['all']+=1;counts[_key]['during_recall']+=int(activity[0])
                return _old(*args,**kwargs)
            stack.enter_context(patch.object(cls,name,wrapped))
        suite=unittest.TestSuite([
            RuntimeContentionTests('test_long_busy_host_remains_live_and_diagnostic_is_not_flooded'),
            RuntimeContentionTests('test_start_waits_for_checkpoint_without_relaxing_owner_lock'),
            *(W02RecallTimeoutTests(name) for name in NAMES)])
        started=time.perf_counter();result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path(output).write_text(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),skipped=len(result.skipped),seconds=round(time.perf_counter()-started,3),
        recall_records=rows,changed_public_calls=counts,assertions_unchanged=True,
        observation_overhead='one wrapper per preparation; record copy after elapsed_ms capture; no per-byte profiler'),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if result.wasSuccessful() else 1

def parent():
    destination=HERE/'recall-paired-diagnostic-01.json'
    if destination.exists(): raise SystemExit('paired label exists')
    for version in ('baseline','current'):
        if any(HERE.glob('recall-'+version+'-diagnostic-01.*')):
            raise SystemExit('child label exists')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    archive=subprocess.check_output(['git','archive','--format=tar',head,'src','tests'],cwd=ROOT)
    report=dict(head=head,archive_sha256=hashlib.sha256(archive).hexdigest(),
        runs=[],predetermined='one baseline then one current run; original two P18 and two W02 tests; no retry-to-green')
    with tempfile.TemporaryDirectory(prefix='w4d-') as temp:
        parent=Path(temp).resolve()
        assert parent.is_relative_to(Path(tempfile.gettempdir()).resolve()) and parent.name.startswith('w4d-')
        for version in ('baseline','current'):
            work=parent/('old-copy' if version=='baseline' else 'new-copy');work.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tar:
                assert all((work/member.name).resolve().is_relative_to(work.resolve()) and not member.issym()
                           and not member.islnk() for member in tar.getmembers())
                tar.extractall(work)
            if version=='current':
                for path in OVERLAYS:
                    target=work/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
            label='recall-'+version+'-diagnostic-01'
            paths=[HERE/(label+suffix) for suffix in ('.stdout.log','.stderr.log','.trace.json')]
            command=[sys.executable,str(Path(__file__).resolve()),'worker',str(paths[2])]
            env={**os.environ,'PYTHONPATH':os.pathsep.join((str(work),str(work/'src'),str(work/'tests'))),
                 'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'}
            start=time.perf_counter()
            with paths[0].open('x',encoding='utf-8') as out,paths[1].open('x',encoding='utf-8') as err:
                completed=subprocess.run(command,cwd=work,env=env,stdout=out,stderr=err,timeout=300)
            report['runs'].append(dict(version=version,command=command,cwd=str(work),exit_code=completed.returncode,
                seconds=round(time.perf_counter()-start,3),source_hashes={p.relative_to(work).as_posix():
                hashlib.sha256(p.read_bytes()).hexdigest() for top in ('src','tests') for p in (work/top).rglob('*') if p.is_file()},
                trace=paths[2].name,stdout=paths[0].name,stderr=paths[1].name))
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report['temporary_copies_released']=True
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ('version','exit_code','seconds','trace')} for r in report['runs']]))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker': raise SystemExit(worker(sys.argv[2]))
    parent()
