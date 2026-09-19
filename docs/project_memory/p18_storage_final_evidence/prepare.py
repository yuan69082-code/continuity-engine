"""Freeze the approved bounded-attempt repair; never replace prior evidence."""
import datetime, hashlib, json, os, runpy, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
OLD=OUT.with_name('p18_storage_repair_evidence')
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode('utf8').splitlines()
b=read(OLD/'before.json');a=read(OLD/'audit-02.json')
source=runpy.run_path(str(OLD/'run.py'))['source_hashes']()
assert source==a['sourceTest']==b['sourceTest']
assert all(sha(ROOT/p)==h for p,h in a['pendingHashes'].items())
assert all(sha(ROOT/p)==h for group in b['protected'].values() for p,h in group.items())
assert git('rev-parse','HEAD')==[b['head']]==git('rev-parse','origin/main')
assert git('branch','--show-current')==['main'] and not git('diff','--cached','--name-only')
excluded=b['excluded']
pending=sorted(set(git('diff','--name-only')+git('ls-files','--others','--exclude-standard'))-set(excluded))
prior={p:sha(ROOT/p) for p in pending if not p.startswith(OUT.relative_to(ROOT).as_posix()+'/')}
record={**b,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existingPending':prior,
 'approval':'Bounded current-condition attempts accepted, including correctly bound fixed WinError5; no inference of past sharing.',
 'previousAuditHash':sha(OLD/'audit-02.json'),'relatedProcessObservation':'No matching Python Engine/P18 process at fresh read-only inspection before this freeze.'}
with (OUT/'before.json').open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
for name in ['run.py']:
 with (OUT/name).open('xb') as f:f.write((OLD/name).read_bytes())
(OUT/'source-before').mkdir()
for name in ['json_repository.py','json_runtime_repository.py']:
 with (OUT/'source-before'/name).open('xb') as f:f.write((ROOT/'src/continuity_engine/storage'/name).read_bytes())
print(json.dumps({'source':len(source),'originalTests':len(b['testIdentities']),'existingPending':len(prior),'excluded':len(excluded),'head':b['head']}))
