"""P16 R1/R2/R3 baseline and immutable independent source archive."""
import hashlib,json,subprocess,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
OLD=ROOT/'docs/project_memory/p16_evidence'
REVIEW=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p16-independent-review-20260909')
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8').strip()
def flatten(s):
    for t in s:
        if isinstance(t,unittest.TestSuite):yield from flatten(t)
        else:yield t
def main():
    a=read(OLD/'final.audit.json');b=read(OLD/'before.json')
    assert git('rev-parse','HEAD')==git('rev-parse','origin/main')=='a41a733635b0f5978c19b287274b4c63925b8979'
    assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==a['sourceTest']
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        for p,h in b[k].items():assert sha(ROOT/p)==h,p
    for p,h in a['pendingHashes'].items():assert sha(ROOT/p)==h,p
    snapshot=read(REVIEW/'independent-edges-03.before.json')
    assert snapshot==read(REVIEW/'independent-edges-03.after.json')
    changed=[p for p,h in snapshot.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    assert not changed,changed
    loader=unittest.TestLoader();ids=[t.id() for t in flatten(loader.discover(str(ROOT/'tests')))];assert not loader.errors
    assert ids==read(OLD/'full-final.json')['testIdentities']
    archived={};(OUT/'independent').mkdir(exist_ok=True)
    for p in sorted(REVIEW.iterdir()):
        if not p.is_file():continue
        target=OUT/'independent'/p.name
        with target.open('xb') as f:f.write(p.read_bytes())
        assert sha(target)==sha(p)
        archived[p.name]={'source':str(p),'sha256':sha(p)}
    data={'at':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
          'sourceTest':current,'testIdentities':ids,'reviewSnapshotCount':len(snapshot),'reviewSnapshotDifferences':changed,
          'reviewArchive':archived,'previousPending':a['pending'],'previousPendingHashes':a['pendingHashes'],
          'formalTreeHash':tree_inventory_hash(ROOT/'.continuity-data'),
          **{k:b[k] for k in ('protected','plans','formalFiles','excludedP10','otherPreserved')},
          'historicalEvidence':{p.relative_to(ROOT).as_posix():sha(p) for p in OLD.rglob('*') if p.is_file()},
          'gitStatus':git('status','--short','--untracked-files=all'),'gitWrites':False,'baselineFullRerun':False,
          'auxiliaryErrors':['Read-only summary accidentally printed all snapshot keys; output truncated. No evidence file changed.']}
    with (OUT/'before.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
    runner=(OLD/'run.py').read_text(encoding='utf-8')
    runner=runner.replace('One durable P15','One durable P16 repair').replace("'p15_review_probe'","'test_independent_edges'").replace('independent/p15_review_probe.py','independent/test_independent_edges.py')
    with (OUT/'run.py').open('x',encoding='utf-8') as f:f.write(runner)
    print('Verified',len(current),'source/resource files;',len(ids),'test identities;',len(snapshot),'review files; protected and 32 exclusions unchanged.')
if __name__=='__main__':main()
