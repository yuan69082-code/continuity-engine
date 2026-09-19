"""Freeze the inherited worktree before targeted F1/H1 investigation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,runpy,shutil,subprocess
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2];DOC=OUT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
def main():
    target=OUT/'before.json';assert not target.exists()
    prior=read(DOC/'p18_persistence_evidence/final.audit.json')
    current=runpy.run_path(str(DOC/'p18_persistence_evidence/run.py'))['source_hashes']()
    assert current==prior['sourceTest']
    assert not git('diff','--cached','--name-only') and git('branch','--show-current')=='main'
    assert git('rev-parse','HEAD')==prior['git']['head']==git('rev-parse','origin/main')
    baseline=read(DOC/'p18_persistence_evidence/before.json')
    for values in baseline['protected'].values():
        assert all(sha(ROOT/p)==h for p,h in values.items())
    inherited={**prior['pendingHashes'],'docs/project_memory/p18_persistence_evidence/final.audit.json':sha(DOC/'p18_persistence_evidence/final.audit.json')}
    assert all(sha(ROOT/p)==h for p,h in inherited.items())
    before=dict(at=datetime.now(timezone.utc).isoformat(),head=git('rev-parse','HEAD'),branch='main',
        sourceTest=current,sourceHash=prior['sourceHash'],testIdentities=read(DOC/'p18_persistence_evidence/frozen-source.json')['testIdentities'],
        protected=baseline['protected'],formalTreeHash=prior['formalTreeHash'],pyproject=prior['pyprojectHash'],
        existingPending=inherited,excluded=prior['excluded'],gitWrites=False,archives={})
    originals=['docs/project_memory/p18_repair_evidence/full-timeout-investigation.json',
        'docs/project_memory/p18_repair_evidence/full-final-01.json',
        'docs/project_memory/p18_repair_evidence/full-final-01.stdout.log',
        'docs/project_memory/p18_repair_evidence/full-final-01.stderr.log',
        'docs/project_memory/p18_evidence/p18-final-04.json',
        'docs/project_memory/p18_evidence/p18-final-04.stdout.log',
        'docs/project_memory/p18_evidence/p18-final-04.stderr.log',
        'docs/project_memory/p18_r2_evidence/f1-h1-investigation.json']
    before['historicalOriginals']={p:sha(ROOT/p) for p in originals}
    for p in ['src/continuity_engine/services/persistent_runtime_service.py','src/continuity_engine/services/runtime_cognition.py',
        'src/continuity_engine/services/scheduler_service.py','src/continuity_engine/services/wake_perception_thinking_action_service.py',
        'src/continuity_engine/services/thinking_service.py','tests/test_p18_runtime_process.py',
        'src/continuity_engine/testing/p18_runtime_fixture.py']:
        dest=OUT/'source-before'/Path(p).name;dest.parent.mkdir(exist_ok=True);assert not dest.exists();shutil.copyfile(ROOT/p,dest)
        before['archives'][p]={'copy':dest.relative_to(ROOT).as_posix(),'sha256':sha(dest)}
        assert sha(dest)==current[p]
    target.write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    shutil.copyfile(DOC/'p18_persistence_evidence/run.py',OUT/'run.py')
    print(json.dumps(dict(source=len(current),tests=len(before['testIdentities']),inherited=len(inherited),excluded=len(before['excluded']),hash=before['sourceHash'])))
if __name__=='__main__':main()
