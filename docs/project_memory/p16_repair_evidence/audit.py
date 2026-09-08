"""Read-only P16 repair identity, protection, documentation and Git audit."""
import ast,hashlib,json,os,re,runpy,subprocess,sys,tomllib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
helpers=runpy.run_path(str(ROOT/'docs/project_memory/p14_evidence/audit.py'))
sha,git,links=helpers['sha'],helpers['git'],helpers['links']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def source():
    return {p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
ALLOWED_SOURCE={'src/continuity_engine/services/external_capability_service.py',
                'src/continuity_engine/services/continuity_interaction_service.py',
                'src/continuity_engine/services/thinking_service.py',
                'tests/test_p16_repair_edges.py','tests/test_p16_review_regressions.py'}
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    assert re.fullmatch('[a-z0-9-]+',label)
    target=OUT/(label+'.audit.json');pending=OUT/(label+'.pending-files.md')
    assert not target.exists() and not pending.exists(), 'unique audit label required'
    b=read(OUT/'before.json');current=source();errors=[]
    a={'at':datetime.now(timezone.utc).isoformat(),'stage':'P16','status':'IMPLEMENTED_NOT_ACCEPTED',
       'PLANNING_CONFLICT':'NONE','EVIDENCE_CONFLICT':'PRESENT','errors':errors,'gitWrites':False,'testsRunByAudit':False,
       'sourceTest':current,'sourceTestCount':len(current),
       'sourceTestInventoryHash':'sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    a['repairSourceDelta']=sorted(p for p in current.keys()|b['sourceTest'].keys() if current.get(p)!=b['sourceTest'].get(p))
    if set(a['repairSourceDelta'])!=ALLOWED_SOURCE:errors.append('repair source scope')
    a['originalTestFileChanges']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['originalTestFileChanges']:errors.append('original test changes')
    a['verifiedRuns']={}
    for name in ('independent-after-01','p16-final-01','compatibility-final-01','full-final-01'):
        r=read(OUT/(name+'.json'))
        v={k:r.get(k) for k in ('command','status','run','passed','seconds','exitCode','skips')}
        v.update(failures=len(r['failures']),errors=len(r['errors']),unchangedDuringRun=r['sourceBefore']==r['sourceAfter'],matchesCurrent=r['sourceAfter']==current)
        a['verifiedRuns'][name]=v
        if v['status']!='FINISHED' or v['exitCode'] or not v['unchangedDuringRun'] or not v['matchesCurrent']:errors.append('run '+name)
    full=read(OUT/'full-final-01.json');a['originalTestCount']=len(b['testIdentities'])
    a['missingOriginalTests']=sorted(set(b['testIdentities'])-set(full['testIdentities']))
    a['newTestIdentities']=sorted(set(full['testIdentities'])-set(b['testIdentities']))
    if a['missingOriginalTests'] or len(a['newTestIdentities'])!=25:errors.append('test identities')
    a['unchangedProbeCopy']=sha(ROOT/'tests/test_p16_review_regressions.py')==b['reviewArchive']['test_independent_edges.py']['sha256']
    if not a['unchangedProbeCopy']:errors.append('probe copy')
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved','historicalEvidence'):
        changed=[p for p,h in b[k].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        a[k]={'count':len(b[k]),'changed':changed}
        if changed:errors.append(k)
    a['independentArchiveChanged']=[name for name,row in b['reviewArchive'].items()
        if sha(OUT/'independent'/name)!=row['sha256'] or sha(Path(row['source']))!=row['sha256']]
    if a['independentArchiveChanged']:errors.append('independent evidence modified')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    a['formalFileCount']=sum(p.is_file() for p in (ROOT/'.continuity-data').rglob('*'))
    a['formalFileHashes']={p:sha(ROOT/p) for p in b['formalFiles']}
    if a['formalTreeHash']!=b['formalTreeHash'] or a['formalFileCount']!=len(b['formalFiles']):errors.append('formal data tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    if a['version']!='0.1.0':errors.append('version')
    python=[p for p in current if p.endswith('.py')]
    for p in python:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p)
    for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    a['astCount']=len(python)
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=set(b['excludedP10'])|set(b['otherPreserved'])
    paths=sorted((set(tracked+untracked)-excluded)|{target.relative_to(ROOT).as_posix(),pending.relative_to(ROOT).as_posix()})
    a['pending']=paths;a['excluded']=sorted(excluded)
    a['missingPriorPending']=sorted(set(b['previousPending'])-set(paths))
    if a['missingPriorPending'] or not excluded<=set(untracked):errors.append('preserved workspace')
    a['repairChangedExisting']=[p for p,h in b['previousPendingHashes'].items() if sha(ROOT/p)!=h]
    a['unexpectedRepairChanges']=[p for p in a['repairChangedExisting'] if p not in ALLOWED_SOURCE and p!='README.md'
        and not (Path(p).parent==Path('docs/project_memory') and p.endswith('.md'))]
    a['unexpectedNewFiles']=[p for p in paths if p not in b['previousPending'] and p not in ALLOWED_SOURCE
        and not p.startswith('docs/project_memory/p16_repair_evidence/') and p!='docs/project_memory/P16_独立复核返修_R1-R3.md']
    if a['unexpectedRepairChanges'] or a['unexpectedNewFiles']:errors.append('file scope')
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build')) or p.endswith(('.whl','.zip','.pyc'))]
    if a['forbiddenArtifacts']:errors.append('forbidden artifacts')
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    a['localLinkCount']=0;a['newBrokenLinks']=[];a['historicalBrokenLinks']=[];a['sensitiveMatches']=[]
    expected={target.resolve(),pending.resolve()}
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.py','.json','.log'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            n,bad=links(p,text,expected);a['localLinkCount']+=n
            oldbad=links(p,git('show','HEAD:'+name))[1] if name in tracked else []
            a['newBrokenLinks'].extend((name,v) for v in bad if v not in oldbad)
            a['historicalBrokenLinks'].extend((name,v) for v in bad if v in oldbad)
    if a['newBrokenLinks'] or a['sensitiveMatches']:errors.append('links/secrets')
    a['runtimeSecretChecks']='Independent nine + formal runtime file, exception message, standard traceback and redirected stdout/stderr assertions passed; raw negative evidence explicitly contains synthetic marker.'
    a['hardcodedSecretInRepairRuntime']=[p for p in a['repairSourceDelta'] if p.startswith('src/') and 'P16_SYNTHETIC_SECRET_DO_NOT_PERSIST' in (ROOT/p).read_text(encoding='utf-8')]
    if a['hardcodedSecretInRepairRuntime']:errors.append('synthetic marker in runtime')
    a['currentStateErrors']=[]
    for name in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md','docs/project_memory/76_P16_规划施工测试验收矩阵.md'):
        text=(ROOT/name).read_text(encoding='utf-8-sig');block=text.split('<!-- P16_REPAIR_CURRENT_START -->')[1].split('<!-- P16_REPAIR_CURRENT_END -->')[0]
        if not all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','P00—P15 ACCEPTED','P17—P23 NOT_STARTED','EVIDENCE_CONFLICT = PRESENT')):a['currentStateErrors'].append(name)
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-068[：:]',decisions,re.M))!=1 or re.search(r'^## D-069[：:]',decisions,re.M):a['currentStateErrors'].append('decision number')
    matrix=(ROOT/'docs/project_memory/76_P16_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['implementedRows']=re.findall(r'^\| P16-(\d{2}) \|[^\n]*?\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    if a['implementedRows']!=[f'{i:02}' for i in range(1,13)]:a['currentStateErrors'].append('matrix')
    if a['currentStateErrors']:errors.append('state')
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:errors.append('diff check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
              'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
              'remotes':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows'),'remoteContacted':False,
              'trackedModified':tracked,'untracked':untracked}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['originMain'] or a['git']['branch']!='main' or a['git']['staged']:errors.append('git identity')
    a['ignoredArtifacts']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    previous_ignored=read(ROOT/'docs/project_memory/p16_evidence/final.audit.json')['ignoredArtifacts']
    a['newIgnoredArtifacts']=sorted(set(a['ignoredArtifacts'])-set(previous_ignored))
    a['removedIgnoredArtifacts']=sorted(set(previous_ignored)-set(a['ignoredArtifacts']))
    a['historicalFormattingNotes']=['p15_repair_evidence/formal-before.stderr.log:5 trailing whitespace, unchanged raw evidence',
        'src/continuity_engine/services/subject_lifecycle_ports.py:18 EOF blank line, unchanged accepted source']
    pending.write_text('# P16 全部现有成果与本次返修精确待提交清单\n\n'+f'共 {len(paths)} 个 P16 文件（包含已有成果，不是本轮全新增）。当前无 Git 写操作授权。原 32 排除项原样保留。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 本轮源码/测试增量（相对已复核 P16）\n\n'
        +'\n'.join('- `'+p+'`' for p in a['repairSourceDelta'])+'\n\n## 明确排除：原31 P10脚本及1 P14报告\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(excluded))+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix() and (ROOT/p).is_file()}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a['git']['status']=git('status','--short','--untracked-files=all')
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:a[k] for k in ('errors','sourceTestCount','astCount','localLinkCount','formalTreeHash')},ensure_ascii=False))
    print('pending',len(paths),'excluded',len(excluded),'tracked modified',len(tracked))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
