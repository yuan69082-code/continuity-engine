"""Capture the unchanged reviewed workspace and copy only acceptance evidence."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
source=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p13-independent-review-20260908')
sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'src'))
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=root,
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True,encoding='utf-8').strip()
assert not (out/'before.json').exists()
audit=read(root/'docs/project_memory/p13_repair_evidence/final.audit.json')
identity=read(source/'repair-identity-check.json')
assert identity['allChecksPass'] and all(identity['checks'].values()) and len(identity['checks'])==21
assert git('branch','--show-current')=='main'
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==audit['head']==identity['head']
assert not git('diff','--cached','--name-only')
assert '## D-063：' not in (root/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8')
for key in ('sourceTest','protected','plans','formalFiles','contentHashes'):
    assert all(sha(root/p)==h for p,h in audit[key].items()),key+' differs from reviewed workspace'
assert tree_inventory_hash(root/'.continuity-data')==audit['formalTreeHash']
evidence={};runs={};workspace=None
for label,count,seconds in [('repair-original-probes-01',7,'3.832'),('repair-p13-01',59,'55.614'),('repair-neighbors-01',5,'3.070')]:
    before=read(source/(label+'.before.json'));after=read(source/(label+'.after.json'))
    result=read(source/(label+'.result.json'));stderr=(source/(label+'.stderr.log')).read_text(encoding='utf-8')
    assert result['exitCode']==0 and result['changed']==[]
    assert before==after and len(before)==result['beforeCount']==result['afterCount']==1364
    assert all(sha(root/p)==h for p,h in before.items()),label+' workspace drift'
    assert f'Ran {count} tests in {seconds}s' in stderr and stderr.rstrip().endswith('OK')
    runs[label]={'count':count,'passed':count,'skips':0,'failures':0,'errors':0,
        'unittestSeconds':seconds,'wrapperSeconds':result['elapsedSeconds'],'beforeCount':len(before),'afterCount':len(after),'changed':[]}
    workspace=after
    for suffix in ('.before.json','.after.json','.result.json','.stdout.log','.stderr.log'):
        evidence[str(source/(label+suffix))]=sha(source/(label+suffix))
tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
excluded=set(audit['excludedP10']);assert len(excluded)==31 and excluded<=set(untracked)
pending=sorted((set(tracked)|set(untracked))-excluded-{p for p in untracked if p.startswith('docs/project_memory/p13_acceptance_evidence/')})
assert pending==sorted(identity['pendingFiles']) and len(pending)==172
copied=['repair-review-report.md','repair-identity-check.json','repair_neighbor_probes.py']
for label in runs:
    copied.extend(label+suffix for suffix in ('.result.json','.stdout.log','.stderr.log'))
copied.extend(('repair-neighbors-01.before.json','repair-neighbors-01.after.json'))
(out/'independent').mkdir()
for name in copied:
    p=source/name;evidence[str(p)]=sha(p)
    (out/'independent'/name).write_bytes(p.read_bytes())
record={'at':datetime.now(timezone.utc).isoformat(),'head':audit['head'],'branch':'main',
 'originMainLocal':git('rev-parse','origin/main'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
 'tracked':tracked,'untrackedAtCapture':untracked,'staged':[],'pendingBeforeAcceptance':pending,
 'sourceTest':audit['sourceTest'],'protected':audit['protected'],'plans':audit['plans'],'formalFiles':audit['formalFiles'],
 'formalTreeHash':audit['formalTreeHash'],'excludedP10':audit['excludedP10'],'workspace':workspace,
 'independentOriginals':evidence,'copiedOriginalNames':copied,'independentRuns':runs,
 'citedFullOnly':audit['full'],'testsExecutedThisTurn':False,'networkChecks':False,'gitWrites':False,
 'copyPolicy':'Three result/log sets plus one unchanged 1364-file inventory pair. All six source inventories verified and hashed; no unrelated old evidence duplicated.'}
(out/'before.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sourceFiles':len(audit['sourceTest']),'protected':len(audit['protected']),
 'reviewedWorkspace':len(workspace),'pending':len(pending),'excluded':len(excluded),'copied':len(copied),'head':audit['head']},ensure_ascii=False))
