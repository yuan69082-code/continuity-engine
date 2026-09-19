"""Read-only code/protection checks and a new immutable P18 repair inventory."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,os,re,runpy,subprocess,sys,tomllib

OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=DOC.parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
def source():return {p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
CODE={'src/continuity_engine/storage/json_runtime_repository.py','src/continuity_engine/services/persistent_runtime_service.py','tests/test_p18_runtime_process.py','tests/test_p18_runtime_contention.py'}

def assertions(text):
    tree=ast.parse(text);result={}
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef):
            result[node.name]=[ast.dump(c,include_attributes=False) for c in ast.walk(node)
                if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and (c.func.attr.startswith('assert') or c.func.attr=='fail')]
    return result

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    assert re.fullmatch('[a-z0-9-]+',label)
    final=not label.startswith('preflight-')
    target=OUT/(label+'.audit.json');listing=OUT/(label+'.pending-files.md')
    assert not target.exists() and not listing.exists(),'keep earlier audit'
    b=read(OUT/'before.json');current=source();errors=[]
    config=runpy.run_path(str(DOC/'p18_evidence/finalize.py'))
    docs={'README.md',*['docs/project_memory/'+p for p in config['TOP']],*['docs/project_memory/'+p for p in config['STAGE_FILES']]}
    a=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18 repair',status='IMPLEMENTED_NOT_ACCEPTED',
        planningConflict='NONE',evidenceConflict='PRESENT',R1='implemented; pending independent confirmation',H1='UNKNOWN',
        errors=errors,behavioralBlockers=[],testsExecutedByAudit=False,gitWrites=False,sourceTest=current,sourceCount=len(current))
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['sourceChanged']=sorted(p for p in set(b['sourceTest'])|set(current) if current.get(p)!=b['sourceTest'].get(p))
    if set(a['sourceChanged'])-CODE:errors.append('repair source scope')
    a['sourceDeleted']=sorted(set(b['sourceTest'])-set(current))
    if a['sourceDeleted']:errors.append('source deleted')
    a['oldP18OriginalsChanged']=[p for p,h in b['originalP18Files'].items() if p not in CODE|docs and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    if a['oldP18OriginalsChanged']:errors.append('old P18 evidence drift')
    a['earlierHistoryChanged']=[p for p,h in b['historicalFiles'].items() if p not in b['originalP18Files'] and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    if a['earlierHistoryChanged']:errors.append('earlier history drift')
    a['archiveChecks']={name:sha(Path(row['source']))==sha(ROOT/row['copy'])==row['sha256'] for name,row in b['archive'].items()}
    if not all(a['archiveChecks'].values()):errors.append('independent originals/copies')
    a['sourceBeforeCopies']={p:sha(OUT/'source-before'/Path(p).name)==b['sourceTest'][p]
        for p in CODE if p in b['sourceTest']}
    if not all(a['sourceBeforeCopies'].values()):errors.append('pre-repair source copies')
    a['protection']={k:dict(count=len(v),changed=[p for p,h in v.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]) for k,v in b['protected'].items()}
    if any(r['changed'] for r in a['protection'].values()):errors.append('protected identity')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    if a['formalTreeHash']!=b['formalTreeHash'] or a['version']!='0.1.0' or a['pyprojectHash']!=b['pyproject']:errors.append('formal/version')
    old=assertions((OUT/'source-before/test_p18_runtime_process.py').read_text(encoding='utf8'))
    new=assertions((ROOT/'tests/test_p18_runtime_process.py').read_text(encoding='utf8'))
    a['originalProcessAssertionsPreserved']=all(new.get(k)==v for k,v in old.items())
    def arguments(text):return {n.name:ast.dump(n.args,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef)}
    oldargs=arguments((OUT/'source-before/test_p18_runtime_process.py').read_text(encoding='utf8'))
    newargs=arguments((ROOT/'tests/test_p18_runtime_process.py').read_text(encoding='utf8'))
    a['originalProcessTimeoutDefaultsPreserved']=all(newargs.get(k)==v for k,v in oldargs.items())
    a['otherOriginalTestsChanged']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and p!='tests/test_p18_runtime_process.py' and current.get(p)!=h]
    if not a['originalProcessAssertionsPreserved'] or not a['originalProcessTimeoutDefaultsPreserved'] or a['otherOriginalTestsChanged']:errors.append('original tests altered')
    a['parsedPythonFiles']=0
    for p in current:
        if p.endswith('.py'):ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p);a['parsedPythonFiles']+=1
    for p in OUT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    a['tests']={}
    if final:
        selected=read(OUT/'selected-runs.json')
        for kind,label_ in selected.items():
            r=read(OUT/(label_+'.json'))
            a['tests'][kind]={k:r.get(k) for k in ('status','command','run','passed','seconds','exitCode','skips','failures','errors')}
            a['tests'][kind]['label']=label_;a['tests'][kind]['sourceMatches']=r['sourceBefore']==r['sourceAfter']==current
            if r['status']!='FINISHED' or not a['tests'][kind]['sourceMatches']:errors.append('final test identity/result '+kind)
            if r.get('exitCode')!=0:
                a['behavioralBlockers'].append(dict(kind=kind,label=label_,exitCode=r.get('exitCode'),failures=r.get('failures'),errors=r.get('errors')))
        full=read(OUT/(selected['full']+'.json'));ids=set(full['testIdentities'])
        if full['failures'] or full['errors']:
            a['newFullObservation']=read(OUT/'full-timeout-investigation.json')
        a['original1424IdentitiesPreserved']=set(b['testIdentities'])<=ids
        a['newTestIdentities']=sorted(ids-set(b['testIdentities']))
        a['finalGroupsCoveredByFull']={k:set(read(OUT/(v+'.json'))['testIdentities'])<=ids for k,v in selected.items() if k!='independent'}
        if not a['original1424IdentitiesPreserved'] or not all(a['finalGroupsCoveredByFull'].values()):errors.append('test identity coverage')
        prior=read(DOC/'p18_evidence/full-final-03.json')
        a['newSkips']=[r for r in full['skips'] if r not in prior['skips']]
        if a['newSkips']:errors.append('new SKIP')
        matrix=read(OUT/'matrix-test-map.json');mapped={t for row in matrix.values() for t in row['testIdentities']}
        p18=read(OUT/(selected['p18']+'.json'))
        failed_ids={t for t,_ in full['failures']+full['errors']}
        a['matrix']=dict(rows=len(matrix),uniqueTests=len(mapped),allP18=mapped==set(p18['testIdentities']),
            rowsWithFullFailure=[key for key,row in matrix.items() if set(row['testIdentities'])&failed_ids])
        if len(matrix)!=12 or not a['matrix']['allP18']:errors.append('matrix coverage')
        a['processEvidence']={}
        for kind in ('formal','p18','full'):
            rows=[]
            for line in (OUT/(selected[kind]+'.stdout.log')).read_text(encoding='utf8').splitlines():
                try:r=json.loads(line)
                except ValueError:continue
                if 'childrenReaped' in r:rows.append(r)
            children=[e for r in rows for e in r['processEvidence'] if 'forcedCleanup' in e]
            a['processEvidence'][kind]=dict(recordCount=len(rows),allChildrenReaped=bool(rows) and all(r['childrenReaped'] for r in rows),
                childCount=len(children),forcedCleanup=[c for c in children if c['forcedCleanup']],exitCodes=[c['exitCode'] for c in children])
            if not a['processEvidence'][kind]['allChildrenReaped'] or a['processEvidence'][kind]['forcedCleanup']:errors.append('process cleanup '+kind)
        a['processCheck']=read(OUT/'process-check.json')
        if a['processCheck']['matchingCount']:errors.append('live P18 process')
        for name in docs:
            text=(ROOT/name).read_text(encoding='utf8')
            if 'IMPLEMENTED_NOT_ACCEPTED' not in text[:1000] or 'EVIDENCE_CONFLICT=PRESENT' not in text[:1000]:errors.append('current status '+name)
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf8')
    a['D072Count']=len(re.findall(r'^## D-072[：:]',decisions,re.M));a['D073Count']=len(re.findall(r'^## D-073[：:]',decisions,re.M))
    if a['D072Count']!=1 or a['D073Count']:errors.append('decision')
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    pending=sorted((set(tracked+untracked)-set(b['excluded']))|{p.relative_to(ROOT).as_posix() for p in (target,listing)})
    a['pending']=pending;a['pendingFileCount']=len(pending);a['excluded']=b['excluded']
    a['repairAdded']=sorted(set(pending)-set(b['originalP18Files']))
    a['repairChanged']=sorted(p for p,h in b['originalP18Files'].items() if sha(ROOT/p)!=h)
    a['scopeErrors']=[p for p in pending if p not in b['originalP18Files'] and p not in CODE and not p.startswith('docs/project_memory/p18_repair_evidence/')]
    if a['scopeErrors']:errors.append('file scope')
    a['forbiddenArtifacts']=[p for p in pending if set(Path(p).parts)&{'.git','.continuity-data','__pycache__','build','dist','node_modules'} or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('forbidden artifacts')
    links=runpy.run_path(str(DOC/'p14_evidence/audit.py'))['links']
    expected={p.resolve() for p in (target,listing,OUT/'final.audit.json',OUT/'final.pending-files.md',OUT/'final-report.md')}
    a['sensitiveMatches']=[];a['brokenLinks']=[];a['linkCount']=0;a['newEditableWhitespace']=[];a['preservedRawWhitespace']=[]
    pattern=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in pending:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.json','.log','.py','.txt'):continue
        text=p.read_text(encoding='utf-8-sig')
        if pattern.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,text,expected);a['linkCount']+=count;a['brokenLinks'].extend((name,v) for v in bad)
        if name in b['originalP18Files'] or '/independent/' in name or '/source-before/' in name:continue
        warnings=[dict(path=name,line=i,kind='trailing whitespace') for i,s in enumerate(text.splitlines(),1) if s.endswith((' ','\t'))]
        if text.endswith('\n\n'):warnings.append(dict(path=name,line=len(text.splitlines()),kind='blank line at EOF'))
        (a['preservedRawWhitespace'] if p.suffix=='.log' else a['newEditableWhitespace']).extend(warnings)
    if a['sensitiveMatches'] or a['brokenLinks'] or a['newEditableWhitespace']:errors.append('docs/static')
    a['priorFormatWarnings']={k:read(DOC/'p18_evidence/final.audit.json')[k] for k in ('rawWhitespace','historicalFormatWarnings','historicalP17RawWarnings')}
    check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    a['diffCheck']=dict(exitCode=check.returncode,stdout=check.stdout,stderr=check.stderr)
    if check.returncode:errors.append('diff check')
    a['git']=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),originMain=git('rev-parse','origin/main'),
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),staged=git('diff','--cached','--name-only'),trackedModified=tracked,
        remote=git('remote','get-url','origin'),remoteQueried=False)
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['branch']!='main' or a['git']['staged']:errors.append('git baseline')
    if not set(b['excluded'])<=set(untracked):errors.append('excluded material missing')
    a['ignoredPaths']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['ci']=dict(trackedWorkflows=git('ls-files','.github/workflows').splitlines(),remoteQueried=False,passClaimed=False)
    content=['# P18完整待提交及排除清单（本轮无Git写授权）','',f'当前完整P18成果{len(pending)}项；原复核164项保留，本轮新增{len(a["repairAdded"])}项。此清单含自身及对应审计。','',
        '## 完整P18成果','',*('- `'+p+'`' for p in pending),'','## 本轮新增（其余为原P18成果）','',*('- `'+p+'`' for p in a['repairAdded']),
        '','## 本轮修改的原P18文件','',*('- `'+p+'`' for p in a['repairChanged']),'','## 原样保留的32项排除','',*('- `'+p+'`' for p in b['excluded'])]
    listing.write_text('\n'.join(content)+'\n',encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if (ROOT/p).is_file() and ROOT/p!=target}
    with target.open('x',encoding='utf8') as f:
        a['git']['status']=git('status','--short','--untracked-files=all')
        a['git']['untracked']=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
        json.dump(a,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:a[k] for k in ('errors','behavioralBlockers','sourceCount','sourceChanged','pendingFileCount','linkCount','brokenLinks','newEditableWhitespace','preservedRawWhitespace')},ensure_ascii=False))
    return bool(errors or a['behavioralBlockers'])

if __name__=='__main__':raise SystemExit(main())
