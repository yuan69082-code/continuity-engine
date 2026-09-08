"""Verify the reviewed worktree before P16 acceptance; no tests or Git writes."""
import json,hashlib,subprocess,datetime,re
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
REPAIR=ROOT/'docs/project_memory/p16_repair_evidence'
REVIEW=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p16-independent-review-20260909')
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8').strip()
def main():
    a=read(REPAIR/'final.audit.json');b=read(REPAIR/'before.json');i=read(REVIEW/'repair-identity-check.json')
    assert i['allIdentityChecksPass'] and len(i['checks'])==22 and all(i['checks'].values())
    assert git('branch','--show-current')=='main' and git('rev-parse','HEAD')==git('rev-parse','origin/main')==i['head']
    assert not git('diff','--cached','--name-only')
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==a['sourceTest']
    assert all(sha(ROOT/p)==h for p,h in a['pendingHashes'].items())
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    # Only this newly created acceptance helper is additional to the independently reviewed tree.
    assert set(tracked+untracked)==set(a['pending'])|set(a['excluded'])|{Path(__file__).relative_to(ROOT).as_posix()}
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        assert all(sha(ROOT/p)==h for p,h in b[k].items()),k
    assert tree_inventory_hash(ROOT/'.continuity-data')==b['formalTreeHash']
    runs={};snapshots={}
    for label,expected in [('repair-independent-01',9),('repair-p16-01',78),('repair-controls-01',4),('repair-identity-01',None)]:
        r=read(REVIEW/(label+'.result.json'));raw=(REVIEW/(label+'.stderr.log')).read_text(encoding='utf-8')
        assert r['exitCode']==0
        if expected:assert f'Ran {expected} tests' in raw and '\nOK' in raw and 'FAILED (' not in raw
        before=read(REVIEW/(label+'.before.json'));after=read(REVIEW/(label+'.after.json'));assert before==after
        drift=[p for p,h in before.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h];assert not drift,drift
        snapshots[label]={'count':len(before),'changed':drift};runs[label]=r
        print(label,'exit',r['exitCode'],'seconds',r['elapsedSeconds'],'snapshot',len(before),'unchanged')
    for label in ('independent-after-01','p16-final-01','compatibility-final-01','full-final-01'):
        r=read(REPAIR/(label+'.json'));assert r['sourceBefore']==r['sourceAfter']==current and r['exitCode']==0
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    assert not re.search(r'^## D-069[：:]',decisions,re.M),'D-069 already occupied'
    assert not (OUT/'before.json').exists()
    history={p.relative_to(ROOT).as_posix():sha(p) for folder in ('p16_evidence','p16_repair_evidence') for p in (ROOT/'docs/project_memory'/folder).rglob('*') if p.is_file()}
    archive=REPAIR/'independent';manifest={}
    files=[p for p in REVIEW.iterdir() if p.is_file() and (p.name.startswith('repair-') or p.name in ('test_repair_independent_controls.py','verify_repair_evidence.py'))]
    for p in sorted(files):
        dest=archive/p.name
        with dest.open('xb') as stream:stream.write(p.read_bytes())
        assert sha(dest)==sha(p)
        manifest[p.name]={'source':str(p),'destination':dest.relative_to(ROOT).as_posix(),'sha256':sha(p)}
    record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'remoteMainAtStart':'a41a733635b0f5978c19b287274b4c63925b8979','remoteCheckCommand':['git','ls-remote','--exit-code','origin','refs/heads/main'],
        'sourceTest':current,'approvedPriorPending':a['pending'],'priorPendingHashes':{p:sha(ROOT/p) for p in a['pending']},
        'excluded':a['excluded'],'trackedAtStart':tracked,'untrackedAtStartWithoutAcceptanceHelper':[p for p in untracked if p!=Path(__file__).relative_to(ROOT).as_posix()],
        'formalTreeHash':b['formalTreeHash'],**{k:b[k] for k in ('protected','plans','formalFiles','excludedP10','otherPreserved')},
        'reviewRuns':runs,'reviewSnapshots':snapshots,'reviewArchive':manifest,'historicalEvidence':history,
        'citedFull':{k:read(REPAIR/'full-final-01.json')[k] for k in ('command','run','passed','seconds','skips','exitCode')},'testsRerun':False,
        'auxiliaryError':'Read-only initial inline verifier used exit_code instead of actual exitCode, raising KeyError before any write. Corrected after inspecting the original JSON; no Engine behavior failure or evidence drift.',
        'gitStatus':git('status','--short','--untracked-files=all')}
    with (OUT/'before.json').open('x',encoding='utf-8') as stream:json.dump(record,stream,ensure_ascii=False,indent=2);stream.write('\n')
    (OUT/'baseline-auxiliary-error.log').write_text('Initial read-only inline verifier, exit 1; before any archive write:\nTraceback (most recent call last):\n  File "<stdin>", line 25, in <module>\nKeyError: \'exit_code\'\n\nActual original JSON uses exitCode. This is verifier metadata handling, not an Engine test failure.\n',encoding='utf-8')
    print('VERIFIED',len(current),'source files;',len(a['pending']),'prior P16 files;',len(a['excluded']),'excluded;',len(manifest),'new independent archive files; D-069 available')
if __name__=='__main__':main()
