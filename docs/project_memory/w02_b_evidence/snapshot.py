"""W02-B read-only identity collection; evidence output is explicit, never overwritten."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def source():
    return {p.relative_to(ROOT).as_posix(): sha(p) for folder in ('src','tests')
            for p in sorted((ROOT/folder).rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}
def fingerprint(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8').strip()
def collect():
    old = read(ROOT/'docs/project_memory/w02_a_evidence/baseline.json')
    exclusions = read(ROOT/'docs/project_memory/w02_a_acceptance_evidence/exclusions.json')['all57']
    protected = {k: {p:sha(p) for p in values} for k,values in old['protected'].items()}
    plans = read(ROOT/'docs/project_memory/w01_planning_v15_20260923/planning-sources.json')
    src = source()
    return dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(), source=src,
        sourceHash=fingerprint(src), protected=protected,
        protectedUnchanged=protected==old['protected'],
        excluded={p:sha(ROOT/p) for p in exclusions},
        excludedUnchanged=all(sha(ROOT/p)==h for p,h in exclusions.items()),
        branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),
        localOrigin=git('rev-parse','origin/main'),origin=git('remote','get-url','origin'),
        status=git('status','--short','--untracked-files=all'),staged=git('diff','--cached','--name-only'),
        tracked=git('diff','--name-only'),plans=plans,indexHash=sha(ROOT/'.git/index'))

if __name__ == '__main__':
    dest=HERE/(sys.argv[1]+'.json')
    data=collect()
    with dest.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2); stream.write('\n')
    print(json.dumps({k:data[k] for k in ('sourceHash','protectedUnchanged','excludedUnchanged','branch','head','staged','tracked')},ensure_ascii=False))
