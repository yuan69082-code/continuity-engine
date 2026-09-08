"""Read-only R1/R2 final audit. Writes only new evidence, never Git metadata."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.persistence import tree_inventory_hash
helper=runpy.run_path(str(ROOT/'docs/project_memory/p14_evidence/audit.py'))
sha=helper['sha']; git=helper['git']; links=helper['links']

def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    assert re.fullmatch(r'[a-z0-9-]+',label)
    out=OUT/(label+'.audit.json'); manifest=OUT/(label+'.pending-files.md')
    assert not out.exists() and not manifest.exists()
    before=read(OUT/'before.json'); opening=read(ROOT/'docs/project_memory/p14_evidence/before.json')
    current={p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],'sourceTest':current}
    a['sourceTestCount']=len(current)
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for key in ('protected','plans','formalFiles','excludedP10'):
        changed=[p for p,h in before[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        a[key]={'count':len(before[key]),'changed':changed}
        if changed:a['errors'].append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=opening['formalTreeHash']:a['errors'].append('formal tree')
    a['changedSource']=sorted(p for p in set(current)|set(before['sourceTest']) if current.get(p)!=before['sourceTest'].get(p))
    allowed={'src/continuity_engine/domain/dynamic_mind.py','src/continuity_engine/services/dynamic_mind_service.py','tests/test_p14_review_repair.py'}
    if set(a['changedSource'])!=allowed:a['errors'].append('source scope')
    a['oldTestChanges']=[p for p,h in before['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['oldTestChanges']:a['errors'].append('old tests changed')
    a['oldEvidenceChanges']=[p for p,h in before['previousPendingHashes'].items() if p.startswith('docs/project_memory/p14_evidence/') and sha(ROOT/p)!=h]
    if a['oldEvidenceChanges']:a['errors'].append('old evidence changed')
    a['reviewOriginalChanges']=[p for p,h in before['reviewSources'].items() if sha(Path(p))!=h]
    if a['reviewOriginalChanges']:a['errors'].append('review original changed')
    a['runs']={}
    for name in ('targeted-final','confirmed-final','p14-final','compatibility-final','full-final'):
        run=read(OUT/(name+'.json'))
        a['runs'][name]={k:run.get(k) for k in ('command','status','exitCode','run','passed','skips','seconds')}
        a['runs'][name]['failures']=len(run.get('failures',[]))
        a['runs'][name]['errors']=len(run.get('errors',[]))
        a['runs'][name]['sourceMatches']=run['sourceBefore']==run['sourceAfter']==current
        if (run['exitCode'] or run.get('status')!='FINISHED' or run.get('failures') or run.get('errors')
                or not a['runs'][name]['sourceMatches']):a['errors'].append(name)
    full=read(OUT/'full-final.json')
    a['missingOldTestIdentities']=sorted(set(before['testIdentities'])-set(full['testIdentities']))
    a['newTestIdentities']=sorted(set(full['testIdentities'])-set(before['testIdentities']))
    if a['missingOldTestIdentities'] or len(full['testIdentities'])!=len(set(full['testIdentities'])):a['errors'].append('test identities')
    oldfull=read(ROOT/'docs/project_memory/p14_evidence/full-final.json')
    if full['skips']!=oldfull['skips']:a['errors'].append('skip changed')
    a['astCount']=0
    for name in current:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name);a['astCount']+=1
    tracked=[x for x in git('diff','--name-only','-z').split('\0') if x]
    untracked=[x for x in git('ls-files','--others','--exclude-standard','-z').split('\0') if x]
    excluded=set(before['excludedP10'])
    if not excluded<=set(untracked):a['errors'].append('excluded inventory')
    generated=[out.relative_to(ROOT).as_posix(),manifest.relative_to(ROOT).as_posix()]
    pending=sorted(set(tracked+untracked+generated)-excluded)
    a['pending']=pending;a['excluded']=sorted(excluded)
    a['outsideRepairScope']=[p for p in pending if p not in set(before['previousPending']) | allowed |
                            {'docs/project_memory/P14_独立复核返修_R1-R2.md'}
                            and not p.startswith('docs/project_memory/p14_repair_evidence/')]
    if a['outsideRepairScope']:a['errors'].append('pending scope')
    a['newSinceRepairStart']=sorted(set(pending)-set(before['previousPending']))
    a['modifiedSinceRepairStart']=[p for p,h in before['previousPendingHashes'].items() if sha(ROOT/p)!=h]
    a['forbiddenArtifacts']=[p for p in pending if any(t in Path(p).parts for t in ('.git','.continuity-data','__pycache__','build','dist')) or p.endswith(('.pyc','.whl','.zip'))]
    if a['forbiddenArtifacts']:a['errors'].append('artifacts')
    a['sensitiveMatches']=[];a['localLinks']=0;a['brokenLinks']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in pending:
        p=ROOT/name
        if not p.exists():continue
        if p.suffix in {'.md','.json','.py','.log'}:
            content=p.read_text(encoding='utf-8-sig')
            if secret.search(content):a['sensitiveMatches'].append(name)
            if p.suffix=='.md':
                n,bad=links(p,content,{out.resolve(),manifest.resolve()});a['localLinks']+=n
                a['brokenLinks'].extend((name,x) for x in bad)
    if a['sensitiveMatches'] or a['brokenLinks']:a['errors'].append('links/secrets')
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf8')
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:a['errors'].append('diff check')
    a['git']={'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),'branch':git('branch','--show-current'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),'remote':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows'),'status':subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=all']).decode('utf8')}
    if a['git']['head']!=before['head'] or a['git']['originMain']!=before['head'] or a['git']['branch']!='main' or a['git']['staged']:a['errors'].append('git baseline')
    a['gitWrites']=False;a['remoteChecked']=False
    ignored=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['ignoredArtifacts']={'count':len(ignored),'paths':ignored,
                          'action':'read-only inventory, excluded from pending; no cleanup',
                          'baselineLimit':'formal seven files checked separately; no old cache hash baseline'}
    manifest.write_text('# P14 R1/R2 后全部精确待提交清单\n\n本轮没有Git写操作，P14仍IMPLEMENTED_NOT_ACCEPTED。完整P14成果'+str(len(pending))+'个文件；另31个P10脚本原样排除。此前157项保留，返修增量见审计newSinceRepairStart/modifiedSinceRepairStart。\n\n'+'\n'.join('- `'+p+'`' for p in pending)+'\n\n## 排除项\n\n'+'\n'.join('- `'+p+'`' for p in sorted(excluded))+'\n',encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if (ROOT/p).exists()}
    a['gitSnapshotNote']='Git status captured before this invocation creates its two audit/manifest outputs.'
    out.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:a[k] for k in ('errors','astCount','localLinks','changedSource','formalTreeHash')},ensure_ascii=False))
    print('pending',len(pending),'excluded',len(excluded))
    return bool(a['errors'])
if __name__=='__main__':raise SystemExit(main())
