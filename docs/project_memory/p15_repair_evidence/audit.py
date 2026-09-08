"""Read-only P15 repair verification and complete pending inventory; no Git writes."""
import ast
from datetime import datetime,timezone
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


def status():
    return subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=all'],
        cwd=ROOT,encoding='utf-8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).rstrip('\r\n')


def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    if not re.fullmatch('[a-z0-9-]+',label):raise ValueError('invalid label')
    target=OUT/(label+'.audit.json');pending=OUT/(label+'.pending-files.md')
    if target.exists() or pending.exists():raise ValueError('preserve prior evidence; use a new label')
    b=read(OUT/'before.json')
    a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],'testsRunByAudit':False,'gitWrites':False,
       'independentAcceptance':False,'planningConflict':'NONE','evidenceConflict':'PRESENT'}
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests')
        for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    a['sourceTest']=current;a['sourceTestCount']=len(current)
    a['sourceTestInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['verifiedRuns']={}
    for label_run in ('targeted-stable','independent-stable','p15-stable','compatibility-final','full-final'):
        r=read(OUT/(label_run+'.json'))
        a['verifiedRuns'][label_run]={k:r[k] for k in ('command','run','passed','skips','seconds','exitCode')}
        entry=a['verifiedRuns'][label_run]
        entry.update(failures=len(r['failures']),errors=len(r['errors']),
            unchangedDuringRun=r['sourceBefore']==r['sourceAfter'],matchesCurrent=r['sourceAfter']==current)
        if r['exitCode'] or not entry['matchesCurrent'] or not entry['unchangedDuringRun']:a['errors'].append(label_run)
    full=read(OUT/'full-final.json')
    a['originalTestCount']=len(b['testIdentities'])
    a['missingOriginalTests']=sorted(set(b['testIdentities'])-set(full['testIdentities']))
    a['newTestIdentities']=sorted(set(full['testIdentities'])-set(b['testIdentities']))
    a['changedOriginalTestFiles']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['missingOriginalTests'] or a['changedOriginalTestFiles']:a['errors'].append('original tests')
    a['repairSourceDelta']=sorted(p for p in set(current)|set(b['sourceTest']) if current.get(p)!=b['sourceTest'].get(p))
    allowed={'src/continuity_engine/storage/json_repository.py','src/continuity_engine/domain/learning.py',
        'src/continuity_engine/services/learning_service.py','src/continuity_engine/services/subject_growth_service.py',
        'src/continuity_engine/storage/json_learning_repository.py','src/continuity_engine/services/mind_projection_service.py',
        'tests/test_p15_review_regressions.py','tests/test_p15_repair_edges.py'}
    if set(a['repairSourceDelta'])-allowed:a['errors'].append('source scope')
    a['formalProbeMatchesOriginal']=sha(ROOT/'tests/test_p15_review_regressions.py')==sha(OUT/'independent/p15_review_probe.py')
    if not a['formalProbeMatchesOriginal']:a['errors'].append('formal probe changed')
    for key in ('protected','plans','formalFiles','excludedP10','reviewSources'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]}
        if a[key]['changed']:a['errors'].append(key)
    review_root=Path(next(p for p in b['reviewSources'] if p.endswith('review-report.md'))).parent
    a['copiedIndependentEvidence']={p.name:sha(p)==sha(review_root/p.name)
        for p in (OUT/'independent').iterdir() if p.is_file()}
    if not all(a['copiedIndependentEvidence'].values()):a['errors'].append('independent copy identity')
    a['historicalEvidenceChanges']=[p for p,h in b['workspace'].items() if p.startswith((
        'docs/project_memory/p15_evidence/','docs/project_memory/p14_evidence/')) and sha(ROOT/p)!=h]
    if a['historicalEvidenceChanges']:a['errors'].append('historical evidence changed')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:a['errors'].append('formal tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8-sig'))['project']['version']
    if a['version']!='0.1.0':a['errors'].append('version')
    a['astCount']=0
    for name in current:
        if name.endswith('.py'):ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name);a['astCount']+=1
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=set(b['excludedP10']);other={'docs/project_memory/p14_evidence/handoff-discrepancy-20260908.json'}
    paths=sorted((set(tracked+untracked)-excluded-other)|{target.relative_to(ROOT).as_posix(),pending.relative_to(ROOT).as_posix()})
    a['pending']=paths;a['excluded']=sorted(excluded);a['otherPreserved']={p:sha(ROOT/p) for p in other}
    if not excluded<=set(untracked):a['errors'].append('excluded scripts status')
    a['repairChangedExistingFiles']=[p for p,h in b['workspace'].items() if (ROOT/p).is_file() and sha(ROOT/p)!=h]
    a['unexpectedExistingChanges']=[p for p in a['repairChangedExistingFiles'] if p not in allowed and
        p!='README.md' and not (p.startswith('docs/project_memory/') and p.endswith('.md') and '/p15_evidence/' not in p)]
    if a['unexpectedExistingChanges']:a['errors'].append('unexpected change')
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build'))
        or p.endswith(('.whl','.zip','.pyc'))]
    if a['forbiddenArtifacts']:a['errors'].append('artifact scope')
    a['localLinkCount']=0;a['newBrokenLinks']=[];a['historicalBrokenLinks']=[];a['sensitiveMatches']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix not in {'.md','.py','.json','.log'}:continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,text,{target.resolve(),pending.resolve()});a['localLinkCount']+=count
            oldbad=links(p,git('show','HEAD:'+name))[1] if name in tracked else []
            a['newBrokenLinks'].extend((name,x) for x in bad if x not in oldbad)
            a['historicalBrokenLinks'].extend((name,x) for x in bad if x in oldbad)
    if a['newBrokenLinks'] or a['sensitiveMatches']:a['errors'].append('links/secrets')
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf-8')
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:a['errors'].append('diff check')
    a['currentStateErrors']=[]
    for name in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md'):
        block=(ROOT/name).read_text(encoding='utf-8-sig').split('<!-- P15_REPAIR_CURRENT_START -->')[1].split('<!-- P15_REPAIR_CURRENT_END -->')[0]
        if not all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','EVIDENCE_CONFLICT=PRESENT','P16—P23 NOT_STARTED')):
            a['currentStateErrors'].append(name)
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-066[：:]',decisions,re.M))!=1 or re.search(r'^## D-067[：:]',decisions,re.M):
        a['currentStateErrors'].append('decision number')
    matrix=(ROOT/'docs/project_memory/72_P15_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['implementedRows']=re.findall(r'^\| P15-(\d{2}) \|[^\n]*?\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    if a['implementedRows']!=[f'{i:02}' for i in range(1,13)]:a['currentStateErrors'].append('matrix')
    if a['currentStateErrors']:a['errors'].append('current state')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
        'remotes':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows')}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['originMain'] or a['git']['branch']!='main' or a['git']['staged']:
        a['errors'].append('Git baseline')
    a['ignoredArtifacts']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    pending.write_text('# P15含R1/R2/R3完整待提交清单（本轮无Git写授权）\n\n'
        +f'本轮与原P15成果共 {len(paths)} 文件；仅记录清单，不暂存。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 原31个P10排除脚本\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(excluded))+'\n\n## 其他原样保留\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(other))+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix() and (ROOT/p).is_file()}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a['git']['status']=status()
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:a[k] for k in ('errors','sourceTestCount','astCount','localLinkCount','formalTreeHash')},ensure_ascii=False))
    print('pending',len(paths),'excluded',len(excluded),'other',len(other))
    return bool(a['errors'])


if __name__=='__main__':raise SystemExit(main())
