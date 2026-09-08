"""P16 read-only checks and exact pending inventory; never changes Git state."""
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
ALLOWED_SOURCE={
    'src/continuity_engine/domain/action_planning.py','src/continuity_engine/domain/external_capabilities.py',
    'src/continuity_engine/services/action_planning_service.py','src/continuity_engine/services/continuity_core_runtime.py',
    'src/continuity_engine/services/continuity_core_service.py','src/continuity_engine/services/external_capability_service.py',
    'src/continuity_engine/services/external_context_source.py','src/continuity_engine/services/external_provider_ports.py',
    'src/continuity_engine/storage/json_external_provider_repository.py','src/continuity_engine/testing/p16_provider_fixture.py',
    'src/continuity_engine/testing/c1_snapshot.py','src/continuity_engine/testing/sandbox.py',
    'tests/test_p16_providers.py','tests/test_p16_context.py','tests/test_p16_recovery.py'}

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    if not re.fullmatch('[a-z0-9-]+',label):raise ValueError('invalid label')
    target=OUT/(label+'.audit.json');pending=OUT/(label+'.pending-files.md')
    if target.exists() or pending.exists():raise ValueError('preserve original evidence; use a unique label')
    b=read(OUT/'before.json');current=source()
    a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],'testsRunByAudit':False,'gitWrites':False,
       'stage':'P16','status':'IMPLEMENTED_NOT_ACCEPTED','acceptanceRegistered':False,'sourceTest':current,
       'sourceTestCount':len(current),'sourceTestInventoryHash':'sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    a['verifiedRuns']={}
    for run_label in ('p16-final','compatibility-final','full-final'):
        r=read(OUT/(run_label+'.json'))
        entry={k:r[k] for k in ('command','run','passed','skips','seconds','exitCode')}
        entry.update(failures=len(r['failures']),errors=len(r['errors']),unchangedDuringRun=r['sourceBefore']==r['sourceAfter'],matchesCurrent=r['sourceAfter']==current)
        a['verifiedRuns'][run_label]=entry
        if entry['exitCode'] or not entry['unchangedDuringRun'] or not entry['matchesCurrent']:a['errors'].append(run_label)
    full=read(OUT/'full-final.json');a['originalTestCount']=len(b['testIdentities'])
    a['missingOriginalTests']=sorted(set(b['testIdentities'])-set(full['testIdentities']))
    a['newTestIdentities']=sorted(set(full['testIdentities'])-set(b['testIdentities']))
    a['changedOriginalTestFiles']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['missingOriginalTests'] or a['changedOriginalTestFiles'] or any(not p.startswith('test_p16_') for p in a['newTestIdentities']):a['errors'].append('original tests')
    a['sourceDelta']=sorted(p for p in set(current)|set(b['sourceTest']) if current.get(p)!=b['sourceTest'].get(p))
    if set(a['sourceDelta'])-ALLOWED_SOURCE:a['errors'].append('source scope')
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]}
        if a[key]['changed']:a['errors'].append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:a['errors'].append('formal tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8-sig'))['project']['version']
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    if a['version']!='0.1.0' or a['pyprojectHash']!=b['trackedHashes']['pyproject.toml']:a['errors'].append('version/pyproject')
    a['astCount']=0
    for path in current:
        if path.endswith('.py'):ast.parse((ROOT/path).read_text(encoding='utf-8-sig'),filename=path);a['astCount']+=1
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=set(b['excludedP10']);other=set(b['otherPreserved'])
    a['unexpectedTrackedChanges']=[p for p,h in b['trackedHashes'].items() if (not (ROOT/p).is_file() or sha(ROOT/p)!=h)
        and p not in ALLOWED_SOURCE and p!='README.md' and not (Path(p).parent==ROOT.relative_to(ROOT)/'docs/project_memory' and p.endswith('.md'))]
    if a['unexpectedTrackedChanges']:a['errors'].append('unexpected tracked changes')
    paths=sorted((set(tracked+untracked)-excluded-other)|{target.relative_to(ROOT).as_posix(),pending.relative_to(ROOT).as_posix()})
    a['pending']=paths;a['excluded']=sorted(excluded);a['otherPreservedHashes']=b['otherPreserved']
    a['unexpectedNewFiles']=[p for p in set(untracked)-excluded-other if p not in ALLOWED_SOURCE and not p.startswith('docs/project_memory/p16_evidence/')
        and not (Path(p).parent==Path('docs/project_memory') and re.match(r'7[5-8]_P16_',Path(p).name))]
    if a['unexpectedNewFiles']:a['errors'].append('unexpected new files')
    if not excluded|other<=set(untracked):a['errors'].append('excluded status')
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build')) or p.endswith(('.whl','.zip','.pyc'))]
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
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    a['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:a['errors'].append('diff check')
    a['baselineFormattingNotes']=['p15_repair_evidence/formal-before.stderr.log:5 trailing whitespace (unchanged historical raw log)',
        'src/continuity_engine/services/subject_lifecycle_ports.py:18 EOF blank line (unchanged accepted source)']
    a['currentStateErrors']=[]
    for path in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md'):
        block=(ROOT/path).read_text(encoding='utf-8-sig').split('<!-- P16_CURRENT_START -->')[1].split('<!-- P16_CURRENT_END -->')[0]
        if not all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','P00—P15 ACCEPTED','P17—P23 NOT_STARTED')):a['currentStateErrors'].append(path)
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-068[：:]',decisions,re.M))!=1 or re.search(r'^## D-069[：:]',decisions,re.M):a['currentStateErrors'].append('decision number')
    matrix=(ROOT/'docs/project_memory/76_P16_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['implementedRows']=re.findall(r'^\| P16-(\d{2}) \|[^\n]*?\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    if a['implementedRows']!=[f'{i:02}' for i in range(1,13)]:a['currentStateErrors'].append('matrix')
    if a['currentStateErrors']:a['errors'].append('current state')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
        'remotes':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows'),'remoteContacted':False}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['originMain'] or a['git']['branch']!='main' or a['git']['staged']:a['errors'].append('Git baseline')
    a['ignoredArtifacts']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    pending.write_text('# P16完整待提交清单（仅清单，本轮无Git写授权）\n\n'+f'P16共 {len(paths)} 文件；实现、测试、当前档案及本轮原始证据。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 原31个P10排除脚本\n\n'+'\n'.join('- `'+p+'`' for p in sorted(excluded))
        +'\n\n## 原样保留的旧P14接续报告\n\n'+'\n'.join('- `'+p+'`' for p in sorted(other))+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix() and (ROOT/p).is_file()}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a['git']['status']=subprocess.check_output(['git','-c','core.quotepath=false','status','--short','--untracked-files=all'],cwd=ROOT,encoding='utf-8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:a[k] for k in ('errors','sourceTestCount','astCount','localLinkCount','formalTreeHash')},ensure_ascii=False))
    print('pending',len(paths),'excluded',len(excluded),'other',len(other))
    return bool(a['errors'])
if __name__=='__main__':raise SystemExit(main())
