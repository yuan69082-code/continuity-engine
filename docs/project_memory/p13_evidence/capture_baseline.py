"""Read-only Engine baseline capture before P12 acceptance/P13 implementation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'src'))
sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
out=directory/'before.json'
if out.exists():raise FileExistsError(out)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):
    p=subprocess.run(['git',*args],cwd=root,capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8'))
    return p.stdout.decode('utf-8').strip()
old=json.loads((root/'docs/project_memory/p12_closeout_evidence/before.json').read_text(encoding='utf-8'))
full=json.loads((root/'docs/project_memory/p12_second_repair_evidence/full-final.tests.json').read_text(encoding='utf-8'))
head=git('rev-parse','HEAD')
assert head=='7afceba17635a8d9fd915bf09fa9df68f3ff3974'==git('rev-parse','origin/main')
assert git('branch','--show-current')=='main'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
untracked=[x for x in git('ls-files','--others','--exclude-standard','-z').split('\0') if x]
assert set(untracked)-set(old['excludedP10'])=={'docs/project_memory/p13_evidence/capture_baseline.py'}
protected={p:sha(root/p) for p in old['protected']};assert protected==old['protected']
source={str(p.relative_to(root)).replace('\\','/'):sha(p) for f in ('src','tests') for p in sorted((root/f).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert source==old['sourceTest']==full['sourceTest']
loader=unittest.TestLoader();suite=loader.discover(str(root/'tests'))
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item.id()
identities=list(flatten(suite));assert not loader.errors
assert set(identities)==set(full['testIdentities']) and len(identities)==len(set(identities))
plans=json.loads((root/'docs/project_memory/p12_evidence/planning-source.json').read_text(encoding='utf-8'))
plan_hashes={v['source']:sha(v['source']) for v in plans.values()}
assert all(plan_hashes[v['source']]==v['sha256'] for v in plans.values())
workspace={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in sorted(root.rglob('*'))
    if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc'
    and 'p13_evidence' not in p.parts}
formal={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in (root/'.continuity-data').rglob('*') if p.is_file()}
formal_hash=tree_inventory_hash(root/'.continuity-data')
assert len(formal)==7 and formal_hash=='sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2'
record={'capturedAt':datetime.now(timezone.utc).isoformat(),'head':head,'originMainLocal':git('rev-parse','origin/main'),
    'branch':'main','aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
    'trackedChanges':[],'staged':[],'p10Untracked':old['excludedP10'],'sourceTest':source,'protected':protected,
    'formalFiles':formal,'formalTreeHash':formal_hash,'planningSources':plan_hashes,'workspaceFiles':workspace,
    'testIdentities':identities,'citedFullResult':{'source':'docs/project_memory/p12_second_repair_evidence/full-final.tests.json',
    'run':full['run'],'passed':full['passed'],'skips':full['skips'],'secondsStructured':full['seconds'],
    'secondsStderr':521.632,'rerunThisBaseline':False},'engineActionsWorkflows':git('ls-files','.github/workflows').splitlines()}
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'head':head,'sourceFiles':len(source),'protected':len(protected),'originalTests':len(identities),
    'p10Preserved':len(old['excludedP10']),'formalHash':formal_hash,'workspaceFiles':len(workspace),'newTestsRun':False},ensure_ascii=False))
