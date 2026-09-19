"""Capture the existing P18 result without replacing any earlier evidence."""
from pathlib import Path
import hashlib,json,os,subprocess
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REVIEW=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p18-independent-review-20260912')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},encoding='utf8').strip()

def main():
    assert not (OUT/'before.json').exists()
    prior=read(ROOT/'docs/project_memory/p18_evidence/final.audit.json')
    initial=read(ROOT/'docs/project_memory/p18_evidence/before.json')
    current={p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==prior['sourceTest']
    assert all(sha(ROOT/p)==h for p,h in prior['pendingHashes'].items())
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        assert all(sha(ROOT/p)==h for p,h in initial[key].items()),key
    head=git('rev-parse','HEAD');assert head==initial['head']==git('rev-parse','origin/main')
    assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
    archive={}
    names=['review-report.md','test_independent_runtime.py','independent-edges-01.stdout.log','independent-edges-01.stderr.log','independent-edges-01.result.json','identity-check.json','p18-original-01.result.json','p18-original-01.stdout.log','p18-original-01.stderr.log','run_review.py']
    (OUT/'independent').mkdir(exist_ok=False)
    for name in names:
        source=REVIEW/name;target=OUT/'independent'/name
        with target.open('xb') as f:f.write(source.read_bytes())
        assert sha(source)==sha(target)
        archive[name]=dict(source=str(source),copy=target.relative_to(ROOT).as_posix(),sha256=sha(source))
    (OUT/'source-before').mkdir(exist_ok=False)
    for p in ('src/continuity_engine/storage/json_runtime_repository.py','src/continuity_engine/services/persistent_runtime_service.py','tests/test_p18_runtime_process.py'):
        target=OUT/'source-before'/Path(p).name
        with target.open('xb') as f:f.write((ROOT/p).read_bytes())
    existing={p:sha(ROOT/p) for p in prior['pending']}
    record=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18 R1 repair / H1 investigation',head=head,branch='main',aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),staged=[],
        sourceTest=current,testIdentities=read(ROOT/'docs/project_memory/p18_evidence/full-final-03.json')['testIdentities'],originalP18Files=existing,
        protected={k:initial[k] for k in ('protected','plans','formalFiles','excludedP10','otherPreserved')},formalTreeHash=initial['formalTreeHash'],pyproject=initial['pyproject'],excluded=initial['excluded'],
        historicalFiles=initial['historicalFiles'],archive=archive,gitWrites=False,gitStatus=git('status','--short','--untracked-files=all'))
    with (OUT/'before.json').open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(sourceCount=len(current),oldP18Count=len(existing),excluded=len(initial['excluded']),archiveCount=len(archive),head=head),ensure_ascii=False))

if __name__=='__main__':main()
