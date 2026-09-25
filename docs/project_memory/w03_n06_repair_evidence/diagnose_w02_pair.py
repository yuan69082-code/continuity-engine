"""Run one W02 deadline case per source revision in equal-length isolated roots."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=HERE/'w02-paired-diagnostic-01.json'
if OUT.exists():
    raise SystemExit('diagnostic label already exists')

RUNNER='''import json, traceback
from pathlib import Path
from time import perf_counter
from tests.test_w02_integration import W02IntegratedChainTests
case=W02IntegratedChainTests('test_partial_derived_withdrawal_invalidates_integrated_reply_and_support')
case.setUp()
started=perf_counter()
try:
    try:
        case.test_partial_derived_withdrawal_invalidates_integrated_reply_and_support()
        outcome='PASS'; error_type=None; error_code=None; stack=[]
    except Exception as exc:
        outcome='ERROR'; error_type=type(exc).__name__; error_code=str(exc)
        chain=exc
        while chain.__cause__ is not None: chain=chain.__cause__
        stack=[x.name for x in traceback.extract_tb(chain.__traceback__)[-8:]]
    rows=[]
    for path in sorted(case.f.base.runtime.data_root.rglob('operation-journal*.json')):
        value=json.loads(path.read_text(encoding='utf-8'))
        def walk(node):
            if isinstance(node,dict):
                if 'elapsed_ms' in node and 'stop_reason' in node:
                    rec={key:node.get(key) for key in ('status','stop_reason','elapsed_ms','retrieved_count','model_calls','external_calls')}
                    if rec not in rows: rows.append(rec)
                for child in node.values():walk(child)
            elif isinstance(node,list):
                for child in node:walk(child)
        walk(value)
    print(json.dumps({'outcome':outcome,'error_type':error_type,'error_code':error_code,
        'deepest_stack':stack,'test_elapsed_seconds':round(perf_counter()-started,6),
        'recall_records':rows},ensure_ascii=False))
finally:
    case.doCleanups()
'''

with tempfile.TemporaryDirectory(prefix='wp-',dir=tempfile.gettempdir()) as temporary:
    temp=Path(temporary).resolve()
    if not temp.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise SystemExit('unsafe temporary root')
    old,new=temp/'old',temp/'new'
    old.mkdir();new.mkdir()
    archive=temp/'head.tar'
    with archive.open('wb') as handle:
        proc=subprocess.run(['git','archive','--format=tar','HEAD'],cwd=ROOT,stdout=handle,stderr=subprocess.PIPE)
    if proc.returncode:
        raise SystemExit('git archive failed: '+proc.stderr.decode(errors='replace'))
    with tarfile.open(archive) as tar:
        tar.extractall(old,filter='data')
        tar.extractall(new,filter='data')
    changed=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT)
    overlays=[]
    for name in changed.decode('utf-8').split('\0'):
        if not name or not name.startswith(('src/','tests/')):
            continue
        source=ROOT/name
        if not source.is_file():
            continue
        target=new/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        overlays.append({'path':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    results=[]
    for name,path in [('old',old),('new',new)]:
        script=path/'diagnose_case.py'
        script.write_text(RUNNER,encoding='utf-8')
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',
                 PYTHONPATH=os.pathsep.join([str(path/'src'),str(path)]))
        began=time.monotonic()
        child=subprocess.run([sys.executable,str(script)],cwd=path,env=env,
                             capture_output=True,timeout=120)
        duration=time.monotonic()-began
        (HERE/f'w02-paired-{name}-01.stdout.log').write_bytes(child.stdout)
        (HERE/f'w02-paired-{name}-01.stderr.log').write_bytes(child.stderr)
        results.append({'revision':name,'exit_code':child.returncode,
            'process_elapsed_seconds':round(duration,6),'isolated_path':str(path),
            'stdout_sha256':hashlib.sha256(child.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(child.stderr).hexdigest(),
            'result':json.loads(child.stdout.decode('utf-8')) if child.stdout else None})
    result={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'python':sys.executable,'temporary_parent':str(temp.parent),
            'same_length_source_paths':len(str(old))==len(str(new)),
            'overlays':overlays,'runs':results}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'label':OUT.name,'runs':[(r['revision'],r['exit_code'],
        r['result']['outcome'] if r['result'] else None) for r in results]},ensure_ascii=False))
