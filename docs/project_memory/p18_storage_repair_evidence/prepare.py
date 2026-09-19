"""Freeze the user-authorized two-file P18 repair before any implementation edit."""
import hashlib,json,os,runpy,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2];DOC=OUT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
assert not (OUT/'before.json').exists()
prior=read(DOC/'p18_f1_h1_evidence/audit-02.json');baseline=read(DOC/'p18_f1_h1_evidence/before.json')
source=runpy.run_path(str(DOC/'p18_f1_h1_evidence/run.py'))['source_hashes']()
assert source==prior['sourceTest']
assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
assert git('rev-parse','HEAD')==prior['git']['head']==git('rev-parse','origin/main')
pending={**prior['pendingHashes'],'docs/project_memory/p18_f1_h1_evidence/audit-02.json':sha(DOC/'p18_f1_h1_evidence/audit-02.json')}
assert all(sha(ROOT/p)==h for p,h in pending.items())
assert all(sha(ROOT/p)==h for values in baseline['protected'].values() for p,h in values.items())
record=dict(at=datetime.now(timezone.utc).isoformat(),head=git('rev-parse','HEAD'),branch='main',sourceTest=source,
    sourceHash=prior['sourceHash'],testIdentities=baseline['testIdentities'],existingPending=pending,
    protected=baseline['protected'],formalTreeHash=baseline['formalTreeHash'],pyproject=baseline['pyproject'],
    excluded=prior['excluded'],gitWrites=False,allowedRuntimeFiles=[
        'src/continuity_engine/storage/json_repository.py','src/continuity_engine/storage/json_runtime_repository.py'],archives={})
for rel in record['allowedRuntimeFiles']:
    dest=OUT/'source-before'/Path(rel).name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/rel,dest)
    assert sha(dest)==source[rel];record['archives'][rel]={'copy':dest.relative_to(ROOT).as_posix(),'sha256':sha(dest)}
review=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews')
originals=[review/'p18-persistence-review-20260913'/n for n in ['review-report.md','test_independent_persistence.py','identity-check.json']]
originals += [review/'p18-f1-h1-review-20260914'/n for n in ['review-report.md','identity-check-v2.json','process-replay-01.result.json','process-replay-01.stdout.log','process-replay-01.stderr.log']]
for p in originals:
    target=OUT/'independent'/p.parent.name/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert sha(p)==sha(target);record['archives'][str(p)]={'copy':target.relative_to(ROOT).as_posix(),'sha256':sha(target)}
shutil.copyfile(DOC/'p18_f1_h1_evidence/run.py',OUT/'run.py')
with (OUT/'before.json').open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps(dict(source=len(source),tests=len(record['testIdentities']),inherited=len(pending),excluded=len(record['excluded']),hash=record['sourceHash'])))
