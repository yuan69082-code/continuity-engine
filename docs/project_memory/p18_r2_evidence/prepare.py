"""Preserve the independently reviewed R1 result before P18 R2 repair."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REVIEW=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p18-repair-review-20260913')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},encoding='utf8').strip()
def main():
    prior=read(OUT.parent/'p18_repair_evidence/final.audit.json')
    baseline=read(OUT.parent/'p18_repair_evidence/before.json')
    current={p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==prior['sourceTest']
    assert all(sha(ROOT/p)==h for p,h in prior['pendingHashes'].items())
    assert all(sha(ROOT/p)==h for v in baseline['protected'].values() for p,h in v.items())
    assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==baseline['head']
    assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
    archive={};(OUT/'independent').mkdir(exist_ok=False)
    names=['review-report.md','identity-check.json','test_independent_resume.py','test_pause_resume_confirmation.py','original-five-01.result.json','targeted-formal-01.result.json']
    names += [stem+ext for stem in ('resume-edges-01','pause-confirmation-01') for ext in ('.stdout.log','.stderr.log','.result.json')]
    for name in names:
        p=REVIEW/name;q=OUT/'independent'/name
        with q.open('xb') as f:f.write(p.read_bytes())
        assert sha(p)==sha(q)
        archive[name]=dict(source=str(p),copy=q.relative_to(ROOT).as_posix(),sha256=sha(p))
    sources=OUT/'source-before';sources.mkdir(exist_ok=False)
    for name in ('domain/thinking.py','services/thinking_service.py','services/runtime_cognition.py','services/wake_perception_thinking_action_service.py','storage/json_thinking_repository.py'):
        p=ROOT/'src/continuity_engine'/name
        with (sources/p.name).open('xb') as f:f.write(p.read_bytes())
    with (sources/'test_p18_runtime_process.py').open('xb') as f:f.write((ROOT/'tests/test_p18_runtime_process.py').read_bytes())
    record=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18 R2 repair; F1/H1 separate UNKNOWN',head=baseline['head'],branch='main',sourceTest=current,
        testIdentities=read(OUT.parent/'p18_repair_evidence/full-final-01.json')['testIdentities'],
        originalP18Files={p:sha(ROOT/p) for p in prior['pending']},protected=baseline['protected'],excluded=baseline['excluded'],
        historicalFiles=baseline['historicalFiles'],formalTreeHash=baseline['formalTreeHash'],pyproject=baseline['pyproject'],archive=archive,
        gitStatus=git('status','--short','--untracked-files=all'),gitWrites=False)
    with (OUT/'before.json').open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(sources=len(current),oldP18=len(prior['pending']),excluded=len(baseline['excluded']),archive=len(archive),protection='UNCHANGED')))
if __name__=='__main__':main()
