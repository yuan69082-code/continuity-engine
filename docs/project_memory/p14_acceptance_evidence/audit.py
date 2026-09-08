"""P14 acceptance-only audit; no tests, runtime writes or Git mutations."""
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
sha=helper['sha'];git=helper['git'];links=helper['links']
def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
    out=OUT/'final.audit.json';pending_file=OUT/'final.pending-files.md'
    assert not out.exists() and not pending_file.exists(), 'preserve existing audit'
    b=read(OUT/'before.json');a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],'testsRunThisTurn':False,'gitWrites':False}
    current={p.relative_to(ROOT).as_posix():sha(p) for dr in ('src','tests') for p in sorted((ROOT/dr).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    full=read(ROOT/'docs/project_memory/p14_repair_evidence/full-final.json')
    a['sourceTest']=current;a['sourceTestCount']=len(current)
    a['sourceIdentityUnchanged']=current==b['sourceTest']==full['sourceBefore']==full['sourceAfter']
    if not a['sourceIdentityUnchanged']:a['errors'].append('source identity')
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for key in ('protected','plans','formalFiles','excludedP10'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]}
        if a[key]['changed']:a['errors'].append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:a['errors'].append('formal tree')
    a['independentCopyDrift']=[p for p,v in b['independentSources'].items() if sha(ROOT/p)!=v['sha256'] or sha(Path(v['source']))!=v['sha256']]
    if a['independentCopyDrift']:a['errors'].append('independent original/copy')
    a['oldEvidenceDrift']=[p for p,h in b['previousPendingHashes'].items() if p.startswith(('docs/project_memory/p14_evidence/','docs/project_memory/p14_repair_evidence/')) and sha(ROOT/p)!=h]
    if a['oldEvidenceDrift']:a['errors'].append('old evidence')
    a['independentRuns']={}
    for label,count,seconds in [('repair-confirmed-01',7,'20.694'),('repair-p14-01',67,'113.783'),('repair-adjacent-01',4,'12.558')]:
        run=read(OUT/'independent'/(label+'.result.json'))
        stderr=(OUT/'independent'/(label+'.stderr.log')).read_text(encoding='utf8')
        valid=run['exitCode']==0 and not run['changed'] and ('Ran '+str(count)+' tests in '+seconds+'s') in stderr and stderr.rstrip().endswith('OK')
        a['independentRuns'][label]={'verified':valid,'pass':count,'skip':0,'fail':0,'error':0,'unittestSeconds':float(seconds),'runnerSeconds':run['elapsedSeconds']}
        if not valid:a['errors'].append(label)
    a['fullCitedOnly']={k:full[k] for k in ('run','passed','skips','seconds','exitCode')}
    old=read(ROOT/'docs/project_memory/p14_repair_evidence/before.json')
    a['missing1124Identities']=sorted(set(old['testIdentities'])-set(full['testIdentities']))
    if a['missing1124Identities']:a['errors'].append('test identities')
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=set(b['excludedP10'])
    if not excluded<=set(untracked):a['errors'].append('excluded set')
    pending=sorted((set(tracked+untracked)-excluded)|{out.relative_to(ROOT).as_posix(),pending_file.relative_to(ROOT).as_posix()})
    a['pending']=pending;a['excluded']=sorted(excluded)
    a['acceptanceNewFiles']=sorted(set(pending)-set(b['previousPending']))
    a['acceptanceModifiedFiles']=sorted(p for p,h in b['previousPendingHashes'].items() if sha(ROOT/p)!=h)
    allowed_names={'README.md','docs/project_memory/P14_用户正式验收_20260908.md'}|set('docs/project_memory/'+n for n in ['00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md','05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md','11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md','13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md','67_P14_ContinuousDynamicMind架构边界.md','68_P14_规划施工测试验收矩阵.md','69_P14_心智连续演化恢复与实验观察语义.md','70_P14_测试索引与验收入口.md','P14_独立复核返修_R1-R2.md'])
    delta=a['acceptanceNewFiles']+a['acceptanceModifiedFiles']
    a['outsideScope']=[p for p in delta if p not in allowed_names and not p.startswith('docs/project_memory/p14_acceptance_evidence/')]
    if a['outsideScope']:a['errors'].append('scope')
    a['currentStateErrors']=[]
    for name in allowed_names-{'docs/project_memory/P14_用户正式验收_20260908.md'}:
        content=(ROOT/name).read_text(encoding='utf8')
        block=content.split('<!-- P14_ACCEPTED_START -->')[-1].split('<!-- P14_ACCEPTED_END -->')[0]
        if not all(t in block for t in ('D-065','P00—P14 ACCEPTED','P14-01—P14-12 ACCEPTED','P15—P23 NOT_STARTED','PLANNING_CONFLICT=NONE','EVIDENCE_CONFLICT=NONE')):a['currentStateErrors'].append(name)
    matrix=(ROOT/'docs/project_memory/68_P14_规划施工测试验收矩阵.md').read_text(encoding='utf8')
    rows=re.findall(r'^\| P14-(\d{2}) \|[^\n]*?\| (ACCEPTED) \|',matrix,re.M)
    a['acceptedMatrixRows']=[p for p,s in rows]
    if a['acceptedMatrixRows']!=[f'{i:02}' for i in range(1,13)]:a['currentStateErrors'].append('matrix')
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf8')
    if len(re.findall(r'^## D-065[：:]',decisions,re.M))!=1:a['currentStateErrors'].append('D065 count')
    if a['currentStateErrors']:a['errors'].append('current state')
    a['astCount']=0
    for p in current:
        if p.endswith('.py'):ast.parse((ROOT/p).read_text(encoding='utf-8-sig'));a['astCount']+=1
    a['localLinks']=0;a['brokenLinks']=[];a['sensitiveMatches']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in pending:
        p=ROOT/name
        if not p.exists():continue
        if p.suffix in {'.py','.md','.json','.log'}:
            text=p.read_text(encoding='utf-8-sig')
            if secret.search(text):a['sensitiveMatches'].append(name)
            if p.suffix=='.md':
                n,bad=links(p,text,{out.resolve(),pending_file.resolve()});a['localLinks']+=n
                a['brokenLinks'].extend((name,v) for v in bad)
    if a['brokenLinks'] or a['sensitiveMatches']:a['errors'].append('links/secrets')
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf8')
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:a['errors'].append('diff check')
    a['git']={'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),'branch':git('branch','--show-current'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),'status':subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=all']).decode('utf8'),'remote':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows')}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['originMain'] or a['git']['staged'] or a['git']['branch']!='main':a['errors'].append('git')
    a['gitSnapshotNote']='Before generation of these final audit and pending files. No remote network check.'
    pending_file.write_text('# P14验收后精确待提交清单（尚未提交）\n\n完整P14成果'+str(len(pending))+'个文件；本次归档新增'+str(len(a['acceptanceNewFiles']))+'个、更新'+str(len(a['acceptanceModifiedFiles']))+'个。另31个P10脚本排除并原样保留。没有Git写操作。\n\n## 本次验收更新\n\n'+'\n'.join('- `'+p+'`' for p in a['acceptanceModifiedFiles'])+'\n\n## 本次验收新增（含独立原字节证据）\n\n'+'\n'.join('- `'+p+'`' for p in a['acceptanceNewFiles'])+'\n\n## 全部P14成果\n\n'+'\n'.join('- `'+p+'`' for p in pending)+'\n\n## 31个原样排除项\n\n'+'\n'.join('- `'+p+'`' for p in sorted(excluded))+'\n',encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if (ROOT/p).exists()}
    out.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:a[k] for k in ('errors','sourceTestCount','sourceIdentityUnchanged','astCount','localLinks','acceptedMatrixRows','formalTreeHash')},ensure_ascii=False))
    print('pending',len(pending),'new',len(a['acceptanceNewFiles']),'modified',len(a['acceptanceModifiedFiles']),'excluded',len(excluded))
    return bool(a['errors'])
if __name__=='__main__':raise SystemExit(main())
