"""P15 read-only boundary/source checks and exact pending manifest; no Git writes."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.persistence import tree_inventory_hash
helpers=runpy.run_path(str(ROOT/'docs/project_memory/p14_evidence/audit.py'))
sha,git,links=helpers['sha'],helpers['git'],helpers['links']


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def git_status():
    return subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=all'],
        cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},encoding='utf-8').rstrip('\r\n')


def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    if not re.fullmatch('[a-z0-9-]+',label):raise ValueError('invalid audit label')
    target=OUT/(label+'.audit.json');pending=OUT/(label+'.pending-files.md')
    if target.exists() or pending.exists():raise ValueError('preserve prior audit; use a new label')
    b=read(OUT/'before.json');a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],
        'testsRunByAudit':False,'gitWrites':False,'remoteNetworkCheck':False}
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests')
        for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    a['sourceTest']=current
    a['sourceTestCount']=len(current)
    a['sourceTestInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()
    a['verifiedRuns']={}
    for name in ('p15-final-2','compatibility-final-2','full-final-2'):
        run=read(OUT/(name+'.json'))
        entry={k:run[k] for k in ('command','run','passed','skips','seconds','exitCode')}
        entry.update(failures=len(run.get('failures',[])),errors=len(run.get('errors',[])),
            unchangedDuringRun=run['sourceBefore']==run['sourceAfter'],matchesCurrent=run['sourceAfter']==current)
        a['verifiedRuns'][name]=entry
        if run['exitCode'] or not entry['unchangedDuringRun'] or not entry['matchesCurrent']:a['errors'].append(name)
    full=read(OUT/'full-final-2.json')
    golden=read(OUT/'golden-cli.json')
    a['golden']={k:golden[k] for k in ('command','seconds','status','exitCode')}
    a['golden']['matchesCurrent']=golden['sourceBefore']==golden['sourceAfter']==current
    if golden['exitCode'] or not a['golden']['matchesCurrent']:a['errors'].append('golden CLI')
    else:
        a['golden']['result']=read(OUT/'golden-cli.stdout.log')
        value=a['golden']['result']
        if (not value['retained_trait'] or not value['retained_will_ids']
                or value['duplicate_revision_delta'] or len(set(value['process_ids']))!=2
                or value['production_adapter_calls']):a['errors'].append('golden invariants')
    a['missingOriginalTestIdentities']=sorted(set(b['testIdentities'])-set(full['testIdentities']))
    a['originalTestCount']=len(b['testIdentities'])
    a['newTestIdentities']=sorted(set(full['testIdentities'])-set(b['testIdentities']))
    a['duplicateFinalTestIdentities']=len(full['testIdentities'])!=len(set(full['testIdentities']))
    if a['duplicateFinalTestIdentities']:a['errors'].append('duplicate final test identities')
    a['changedOriginalTests']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['missingOriginalTestIdentities'] or a['changedOriginalTests']:a['errors'].append('original tests changed/missing')
    for key in ('protected','plans','formalFiles','excludedP10'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]}
        if a[key]['changed']:a['errors'].append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:a['errors'].append('formal tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8-sig'))['project']['version']
    a['pyprojectSha256']=sha(ROOT/'pyproject.toml')
    if a['version']!='0.1.0':a['errors'].append('version')
    a['astCount']=0
    for path in current:
        if path.endswith('.py'):ast.parse((ROOT/path).read_text(encoding='utf-8-sig'),filename=path);a['astCount']+=1
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=set(b['excludedP10'])
    other={'docs/project_memory/p14_evidence/handoff-discrepancy-20260908.json'}
    a['otherPreserved']={p:sha(ROOT/p) for p in other if (ROOT/p).exists()}
    if not excluded<=set(untracked):a['errors'].append('excluded P10 inventory')
    paths=sorted((set(tracked+untracked)-excluded-other)|{target.relative_to(ROOT).as_posix(),pending.relative_to(ROOT).as_posix()})
    a['pending']=paths;a['excluded']=sorted(excluded)
    brief=(ROOT/'docs/project_memory/71_P15_人格关系学习与主体生命周期架构边界.md').read_text(encoding='utf-8-sig')
    allowed=set(re.findall(r'`((?:src|tests)/[^`]+\.py)`',brief))
    allowed|={'README.md'}|{p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/project_memory').glob('*.md')
        if re.match(r'^(?:00_|01_|02_|03_|04_|05_|06_|07_|10_|11_|12_|13_|71_|72_|73_|74_|CHANGELOG\.md|工程总档案\.md)',p.name)}
    a['outsideScope']=[p for p in paths if p not in allowed and not p.startswith('docs/project_memory/p15_evidence/')]
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build'))
                            or p.endswith(('.whl','.zip','.pyc'))]
    if a['outsideScope'] or a['forbiddenArtifacts']:a['errors'].append('scope/artifact')
    a['localLinkCount']=0;a['newBrokenLinks']=[];a['historicalBrokenLinks']=[];a['sensitiveMatches']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in paths:
        path=ROOT/name
        if not path.is_file() or path.suffix not in {'.md','.py','.json','.log'}:continue
        content=path.read_text(encoding='utf-8-sig')
        if secret.search(content):a['sensitiveMatches'].append(name)
        if path.suffix=='.md':
            count,bad=links(path,content,{target.resolve(),pending.resolve()});a['localLinkCount']+=count
            oldbad=links(path,git('show','HEAD:'+name))[1] if name in tracked else []
            a['historicalBrokenLinks'].extend((name,x) for x in bad if x in oldbad)
            a['newBrokenLinks'].extend((name,x) for x in bad if x not in oldbad)
    if a['newBrokenLinks'] or a['sensitiveMatches']:a['errors'].append('links/secrets')
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf-8')
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:a['errors'].append('diff check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),
        'originMain':git('rev-parse','origin/main'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
        'staged':git('diff','--cached','--name-only'),'status':git_status(),
        'remotes':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows')}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['originMain'] or a['git']['staged'] or a['git']['branch']!='main':
        a['errors'].append('Git baseline')
    a['ignoredArtifacts']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['currentStateErrors']=[]
    for name in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md'):
        block=(ROOT/name).read_text(encoding='utf-8-sig').split('<!-- P15_CURRENT_START -->')[-1].split('<!-- P15_CURRENT_END -->')[0]
        if not all(x in block for x in ('P00—P14 ACCEPTED','IMPLEMENTED_NOT_ACCEPTED','P16—P23 NOT_STARTED','D-066')):
            a['currentStateErrors'].append(name)
    matrix=(ROOT/'docs/project_memory/72_P15_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['implementedRows']=re.findall(r'^\| P15-(\d{2}) \|[^\n]*?\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    if a['implementedRows']!=[f'{i:02}' for i in range(1,13)]:a['currentStateErrors'].append('P15 matrix')
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-066[：:]',decisions,re.M))!=1 or re.search(r'^## D-067[：:]',decisions,re.M):
        a['currentStateErrors'].append('decision number')
    if a['currentStateErrors']:a['errors'].append('current state')
    pending.write_text('# P15 精确待提交清单（仅工作区，未授权Git写操作）\n\n'
        +f'P15成果 {len(paths)} 个文件；31个P10辅助脚本原样排除。另任务接续只读报告单列保留。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 原31个P10脚本\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(excluded))+'\n\n## 其他保留项\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(a['otherPreserved']))+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix() and (ROOT/p).is_file()}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Include this invocation's own two new files in the final Git snapshot.
    # This completes the current audit construction; an earlier audit is never opened.
    a['git']['statusBeforeAuditOutputs']=a['git']['status']
    a['git']['status']=git_status()
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:a[k] for k in ('errors','sourceTestCount','astCount','formalTreeHash','localLinkCount','implementedRows')},ensure_ascii=False))
    print('pending',len(paths),'excluded',len(excluded),'other',len(a['otherPreserved']))
    return bool(a['errors'])


if __name__=='__main__':raise SystemExit(main())
