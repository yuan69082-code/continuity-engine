"""Expanded affected-public verification, planned before its only final run.

The frozen plan remains historical and unchanged. This adds the actual common
P03/P04/P05/P06/P08/P09 callers to its public group; no product or test edits.
"""
import json, os, pathlib, runpy, subprocess, sys

ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['PYTHONUTF8']='1'
snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
frozen=json.loads((HERE/'frozen-source-final-01.json').read_text(encoding='utf8'))
assert snap['source']()==frozen['source']
extra=sorted(p.stem for p in (ROOT/'tests').glob('test_*.py')
    if p.stem.startswith(('test_p03','test_p04','test_p05','test_p06','test_p08','test_p09')))
modules=sorted(set(frozen['groups']['public-final-01'])|set(extra))
plan=HERE/'public-scope-addendum-01.json'
if sys.argv[1]=='plan':
    with plan.open('x',encoding='utf8') as out:
        json.dump(dict(fingerprint=frozen['fingerprint'],label='public-final-01',
            reason='Actual shared storage, provenance, digest and Router/Composer callers',
            modules=modules,added_modules=extra),out,ensure_ascii=False,indent=2)
    print(json.dumps({'modules':len(modules),'added_modules':extra}))
else:
    value=json.loads(plan.read_text(encoding='utf8'))
    assert value['modules']==modules and value['fingerprint']==frozen['fingerprint']
    raise SystemExit(subprocess.call([sys.executable,str(HERE/'run.py'),
        'public-final-01','-m','unittest','-v',*modules],cwd=ROOT))
