"""Explicit staged validation of one frozen source; stops on any failed group.

No code edits, lifecycle policy changes, retries, or Git writes. Invoke a single
named group; this tool never silently reruns earlier groups.
"""
import datetime,hashlib,json,os,pathlib,runpy,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
os.chdir(ROOT);os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['PYTHONUTF8']='1'
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests')]
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
FROZEN=HERE/'frozen-source-final-01.json'
def ids(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from ids(test)
        else:yield test.id()
modules=sorted(path.stem for path in (ROOT/'tests').glob('test_*.py'))
groups={
 'targeted-final-01':[m for m in modules if m.startswith('test_w04_4') or m=='test_w04_package'],
 'w04-final-01':[m for m in modules if m.startswith('test_w04_')],
 'public-final-01':[m for m in modules if m.startswith(('test_p13','test_p14','test_p15','test_p16','test_p17','test_p18','test_w02','test_w03','test_pre_p19','test_context','test_integration','test_action','test_thinking','test_memory','test_capability','test_subject_state'))],
 'full-final-01':modules,
}
mode=sys.argv[1]
source=SNAP['source']();fingerprint=SNAP['fingerprint'](source)
if mode=='freeze':
    assert not FROZEN.exists()
    baseline=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
    tests=sorted(ids(unittest.defaultTestLoader.discover('tests')))
    missing=sorted(set(baseline['test_ids'])-set(tests))
    changed=[p for p,h in baseline['source'].items() if p.startswith('tests/') and source.get(p)!=h]
    assert not missing and not changed,(missing,changed)
    value=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=source,fingerprint=fingerprint,
        count=len(source),test_ids=tests,original_test_count=len(baseline['test_ids']),new_tests=sorted(set(tests)-set(baseline['test_ids'])),
        original_test_files_changed=changed,groups=groups)
    FROZEN.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('source','test_ids','groups','new_tests')}))
else:
    frozen=json.loads(FROZEN.read_text(encoding='utf8'));assert source==frozen['source']
    names=frozen['groups'][mode]
    cmd=[sys.executable,str(HERE/'run.py'),mode,'-m','unittest','-v',*names]
    print(json.dumps({'group':mode,'modules':names,'frozen':fingerprint}),flush=True)
    raise SystemExit(subprocess.call(cmd,cwd=ROOT))
