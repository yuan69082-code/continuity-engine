"""P17 final read-only checks plus exact, un-staged delivery manifest."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DOC=OUT.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
helpers=runpy.run_path(str(DOC/'p14_evidence/audit.py'))
links=helpers['links']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8').strip()

def main():
    target=OUT/'final.audit.json';listing=OUT/'final.pending-files.md'
    assert not target.exists() and not listing.exists(),'preserve existing audit'
    b=read(OUT/'before.json');errors=[]
    a=dict(at=datetime.now(timezone.utc).isoformat(),stage='P17',status='IMPLEMENTED_NOT_ACCEPTED',errors=errors,
           testsExecutedByAudit=False,gitWrites=False)
    source={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    a['sourceTest']=source;a['sourceCount']=len(source)
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['tests']={}
    config=runpy.run_path(str(OUT/'finalize.py'))
    for label in (config['FINAL_P17'],config['COMPAT'],config['FINAL_FULL']):
        r=read(OUT/(label+'.json'))
        a['tests'][label]={k:r[k] for k in ('status','run','passed','skips','seconds','exitCode','command')}
        if r['status']!='FINISHED' or r['exitCode'] or r['sourceBefore']!=r['sourceAfter']:errors.append('test result '+label)
        if label==config['COMPAT']:
            delta={p for p in set(source)|set(r['sourceAfter']) if source.get(p)!=r['sourceAfter'].get(p)}
            a['tests'][label]['historicalBeforeLateBoundaryRepair']=True
            a['tests'][label]['sourceDelta']=sorted(delta)
            if delta!=config['LATE_FILES']:errors.append('historical compatibility scope')
        elif r['sourceAfter']!=source:errors.append('test identity '+label)
    full=read(OUT/(config['FINAL_FULL']+'.json'));ids=set(full['testIdentities']);old=set(b['testIdentities'])
    a['localBoundaryProbes']={}
    for label in ('storage-probe-after-01','adapter-binding-after-01'):
        r=read(OUT/(label+'.json'))
        a['localBoundaryProbes'][label]={k:r[k] for k in ('command','startedAt','finishedAt','seconds','exitCode')}
        if r['exitCode'] or r['sourceBefore']!=source or r['sourceAfter']!=source:errors.append('boundary probe '+label)
    previous=read(OUT/'full-final-01.json')
    a['lateBoundarySourceArchivesExact']=all(sha(ROOT/v['archive'])==v['sha256']==previous['sourceAfter'][name]
        for name,v in read(OUT/'late-boundary-source-before.json').items())
    if not a['lateBoundarySourceArchivesExact']:errors.append('late boundary source archive')
    a['compatibilityIdentitiesCoveredByFinalFull']=set(read(OUT/(config['COMPAT']+'.json'))['testIdentities'])<=ids
    if not a['compatibilityIdentitiesCoveredByFinalFull']:errors.append('compatibility coverage')
    a['originalIdentitiesPreserved']=old<=ids;a['originalIdentityCount']=len(old);a['newIdentities']=sorted(ids-old)
    a['originalTestHashChanged']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and source.get(p)!=h]
    if not a['originalIdentitiesPreserved'] or a['originalTestHashChanged']:errors.append('original test drift')
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        changed=[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        a[key]={'count':len(b[key]),'changed':changed}
        if changed:errors.append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:errors.append('formal tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if a['version']!='0.1.0':errors.append('version')
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    a['kickoffCopiesExact']=all(sha(OUT/name)==sha(Path(v['source']))==v['sha256'] for name,v in b['kickoff'].items())
    if not a['kickoffCopiesExact']:errors.append('kickoff archive')
    for name in source:
        if name.endswith('.py'):ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)
    for path in OUT.glob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    a['parsedPythonFiles']=sum(p.endswith('.py') for p in source)
    changed=[p for p in git('diff','--name-only','-z').split('\0') if p]
    new=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    prospective={target.relative_to(ROOT).as_posix(),listing.relative_to(ROOT).as_posix()}
    paths=sorted((set(changed+new)-set(b['excluded']))|prospective)
    a['pending']=paths;a['excluded']=b['excluded'];a['pendingFileCount']=len(paths)
    implementation={'src/continuity_engine/services/'+p+'.py' for p in ('action_planning_service','continuity_core_runtime','continuity_core_service','continuity_interaction_service')}
    allowed_new={'src/continuity_engine/'+p for p in ('domain/execution.py','services/execution_ports.py','services/execution_service.py',
        'services/execution_context_source.py','storage/json_execution_outbox.py','testing/p17_execution_fixture.py')}
    allowed_new|={'tests/test_p17_'+p+'.py' for p in ('execution','recovery','boundaries')}
    allowed_docs={'README.md'}|{str(Path('docs/project_memory')/p).replace('\\','/') for p in
        runpy.run_path(str(OUT/'finalize.py'))['TOP']}
    a['unexpectedScope']=[p for p in paths if p not in implementation|allowed_new|allowed_docs and not p.startswith('docs/project_memory/p17_evidence/')
             and not re.match(r'docs/project_memory/(79|80|81|82)_P17_',p)]
    if a['unexpectedScope']:errors.append('scope')
    a['existingModifiedSource']=[p for p,h in b['sourceTest'].items() if source.get(p)!=h]
    if not set(a['existingModifiedSource'])<=implementation:errors.append('source scope')
    a['historicalTrackedDrift']=[p for p,h in b['trackedFiles'].items() if p not in changed and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    if a['historicalTrackedDrift']:errors.append('history drift')
    a['forbiddenArtifacts']=[p for p in paths if any(c in Path(p).parts for c in ('.git','.continuity-data','__pycache__','dist','build','node_modules')) or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('artifact scope')
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    a['sensitiveMatches']=[];a['brokenLinks']=[];a['linkCount']=0;a['newRawEvidenceWhitespace']=[];a['newEditableWhitespace']=[]
    expected={target.resolve(),listing.resolve()}
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.json','.log','.py','.txt'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,text,expected);a['linkCount']+=count;a['brokenLinks'].extend((name,x) for x in bad)
        findings=[dict(path=name,line=i,kind='trailing whitespace') for i,line in enumerate(text.splitlines(),1) if line.endswith((' ','\t'))]
        if text.endswith('\n\n') and text.strip():findings.append(dict(path=name,line=len(text.splitlines()),kind='new blank line at EOF'))
        for finding in findings:
            if name in changed and name in b['trackedFiles']:
                old_text=git('show','HEAD:'+name)
                if text.splitlines()[finding['line']-1] in old_text.splitlines():continue
            (a['newRawEvidenceWhitespace'] if p.suffix=='.log' else a['newEditableWhitespace']).append(finding)
    if a['sensitiveMatches'] or a['brokenLinks'] or a['newEditableWhitespace']:errors.append('static material/docs')
    a['historicalEightWarnings']=read(OUT/'baseline-verification.json')['historicalFormattingWarnings']
    a['rawEvidencePolicy']='Preserve original logs, including synthetic-secret negatives and raw unittest whitespace; list new raw findings separately, never rewrite them.'
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf-8')
    a['D070Count']=len(re.findall(r'^## D-070[：:]',decisions,re.M));a['D071Count']=len(re.findall(r'^## D-071[：:]',decisions,re.M))
    matrix=next(DOC.glob('80_P17_*.md')).read_text(encoding='utf-8')
    a['matrixItems']=re.findall(r'^\| P17-(\d{2}) \|[^\n]*\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    p17=read(OUT/(config['FINAL_P17']+'.json'))
    methods={t.rsplit('.',1)[-1] for t in p17['testIdentities']}
    a['matrixTestMethods']=sorted(set(re.findall(r'\btest_[a-z_]+\b',matrix))-{'test_p17_execution','test_p17_recovery','test_p17_boundaries'})
    a['matrixMethodsMissing']=sorted(set(a['matrixTestMethods'])-methods)
    if a['matrixMethodsMissing']:errors.append('matrix method coverage')
    if a['D070Count']!=1 or a['D071Count']!=0 or a['matrixItems']!=[f'{i:02}' for i in range(1,13)]:errors.append('status/decision')
    for name in allowed_docs:
        text=(ROOT/name).read_text(encoding='utf-8')
        block=text.split('<!-- P17_CURRENT_START -->',1)[1].split('<!-- P17_CURRENT_END -->',1)[0]
        if not all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','P00—P16 ACCEPTED','P18—P23 NOT_STARTED','D-071未创建')):errors.append('current status '+name)
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
        'status':git('-c','core.quotepath=false','status','--short','--untracked-files=all'),'trackedChanged':changed,'untracked':new,
        'remote':git('remote','get-url','origin'),'remoteQueriedThisTurn':False}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['branch']!='main' or a['git']['staged']:errors.append('git')
    if not set(b['excluded'])<=set(new):errors.append('excluded status')
    d=subprocess.run(['git','diff','--check'],cwd=ROOT,text=True,capture_output=True,encoding='utf-8')
    a['diffCheck']={'exitCode':d.returncode,'stdout':d.stdout,'stderr':d.stderr}
    if d.returncode:errors.append('git diff --check')
    a['ignoredPaths']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['testIsolation']='All P17 tests use independently validated TEST Temp roots, OS locks and bounded child processes. No network or production systems. Existing loopback tests retained.'
    a['nonReady']='Production Adapter/credentials/provider choices, Owner recovery (P20/P21), Research-to-Main production promotion and P18 persistent runtime remain NOT_READY.'
    listing.write_text('# P17精确待提交与排除清单\n\n本轮没有Git暂存、提交或push。下列为工作区成果，不是已提交SHA。\n\n## P17成果（'+str(len(paths))+'项）\n\n'+'\n'.join('- `'+p+'`' for p in paths)+
        '\n\n## 原样排除（32项）\n\n'+'\n'.join('- `'+p+'`' for p in b['excluded'])+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix()}
    with target.open('x',encoding='utf-8') as stream:
        # Include this audit and its manifest in the final untracked snapshot.
        a['git']['status']=git('-c','core.quotepath=false','status','--short','--untracked-files=all')
        a['git']['untracked']=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
        a['git']['snapshotIncludesAuditOutputs']=True
        json.dump(a,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:a[k] for k in ('errors','sourceCount','parsedPythonFiles','linkCount','pendingFileCount','newRawEvidenceWhitespace','newEditableWhitespace')},ensure_ascii=False))
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())
