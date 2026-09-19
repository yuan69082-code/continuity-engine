"""P18 source/protection/docs inspection; no tests or Git mutations."""
from pathlib import Path
from datetime import datetime,timezone
import ast
import hashlib
import json
import os
import re
import runpy
import subprocess
import sys
import tomllib

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2];DOC=OUT.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
config=runpy.run_path(str(OUT/'finalize.py'))
links=runpy.run_path(str(DOC/'p14_evidence/audit.py'))['links']

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},encoding='utf8').strip()
def source():
    return {p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    if not re.fullmatch('[a-z0-9-]+',label):raise ValueError('invalid audit label')
    preflight=label.startswith(('preflight-','preclose-'))
    target=OUT/(label+'.audit.json');listing=OUT/(label+'.pending-files.md')
    assert not target.exists() and not listing.exists(),'preserve earlier audit'
    b=read(OUT/'before.json');current=source();errors=[]
    resume=read(OUT/'resume-check-20260912.json')
    supplement=read(OUT/'resource-scan-scope.json')
    source_allowed=set(b['sourceAllowed'])|set(supplement['sourceAllowedAdditions'])
    a=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18',status='IN_PROGRESS' if preflight else 'IMPLEMENTED_NOT_ACCEPTED',
        errors=errors,sourceTest=current,sourceCount=len(current),testsExecutedByAudit=False,gitWrites=False)
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['resumption']=dict(reference='resume-check-20260912.json',testsRerun=False,
        currentSourceMatches=current==resume['sourceTest'],
        originalEvidenceChanged=[p for p,h in resume['existingEvidenceHashes'].items()
            if not (ROOT/p).is_file() or sha(ROOT/p)!=h],
        briefCopyMatches=sha(ROOT/resume['resumeBrief']['copy'])==sha(Path(resume['resumeBrief']['source']))==resume['resumeBrief']['sha256'])
    if not a['resumption']['currentSourceMatches'] or a['resumption']['originalEvidenceChanged'] or not a['resumption']['briefCopyMatches']:
        errors.append('resumption identity/evidence')
    a['oldSourceChanged']=[p for p,h in b['sourceTest'].items() if current.get(p)!=h]
    a['sourceAdded']=sorted(set(current)-set(b['sourceTest']))
    a['oldTestsChanged']=[p for p in a['oldSourceChanged'] if p.startswith('tests/')]
    if a['oldTestsChanged']:errors.append('old test files changed')
    if set(a['oldSourceChanged']+a['sourceAdded'])-source_allowed:errors.append('source scope')
    a['scopeSupplement']=supplement
    a['planningConflict']='NONE'
    a['evidenceConflict']='PRESENT'
    a['unresolvedEvidence']=[{'label':'p18-final-04','test':'test_resource_wait_host_lives_and_restores_without_message','rootCause':'UNKNOWN','laterPassDoesNotClose':True}]
    a['tests']={}
    a['processEvidence']={}
    for name in config['LABELS']:
        p=OUT/(name+'.json')
        if not p.exists():
            if not preflight:errors.append('missing test '+name)
            continue
        r=read(p)
        if r.get('status')!='FINISHED':
            if not preflight:errors.append('unfinished test '+name)
            continue
        a['tests'][name]={k:r[k] for k in ('status','run','passed','seconds','skips','failures','errors','command','exitCode')}
        a['tests'][name]['sourceMatches']=r['sourceBefore']==r['sourceAfter']==current
        delta=sorted(p for p in set(current)|set(r['sourceAfter']) if r['sourceAfter'].get(p)!=current.get(p))
        a['tests'][name]['laterChangedFiles']=delta
        allowed_later=(name=='compatibility-scheduler-final-01' and set(delta)<=config['STOP_CLOSEOUT'])
        a['tests'][name]['legacyCodeMatches']=all(r['sourceAfter'].get(p)==current.get(p) for p in b['sourceTest'])
        if r['exitCode'] or r['sourceBefore']!=r['sourceAfter'] or (delta and not allowed_later):errors.append('test result/identity '+name)
        if name in (config['LABELS'][0],config['FULL_LABEL']):
            records=[]
            for line in (OUT/(name+'.stdout.log')).read_text(encoding='utf8').splitlines():
                try:row=json.loads(line)
                except ValueError:continue
                if isinstance(row,dict) and str(row.get('test','')).startswith('test_p18_runtime_process.'):
                    records.append(row)
            children=[e for row in records for e in row['processEvidence'] if e.get('stage')=='continuous-child']
            a['processEvidence'][name]=dict(testCount=len(records),
                childrenReaped=all(row['childrenReaped'] for row in records),
                childCount=len(children),exitCodes=[e['exitCode'] for e in children],
                forcedCleanup=[e['pid'] for e in children if e['forcedCleanup']],
                testIdentities=[row['test'] for row in records])
            if len(records)!=6 or not all(row['childrenReaped'] for row in records) or any(e['forcedCleanup'] for e in children):
                errors.append('P18 process cleanup '+name)
    a['controlledInterruptionCleanup']=read(OUT/'interrupted-process-cleanup-check.json')
    if any(row['sameTestProcessStillPresent'] for row in a['controlledInterruptionCleanup']['priorOwnedProcessChecks']):
        errors.append('interrupted test process still present')
    a['resumeProcessCheck']=read(OUT/'resume-process-check-20260912.json')
    if a['resumeProcessCheck']['matchingCount']:errors.append('P18 process remains on resumption')
    full_path=OUT/(config['FULL_LABEL']+'.json')
    if full_path.exists() and read(full_path).get('status')=='FINISHED':
        full=read(full_path);old=set(b['testIdentities']);ids=set(full['testIdentities'])
        a['originalTestIdentitiesPreserved']=old<=ids;a['originalTestCount']=len(old)
        a['newTestIdentities']=sorted(ids-old)
        a['newSkips']=sorted({row[0] for row in full['skips']}-{row[0] for row in b['baselineCitedNotRerun']['skips']})
        if not old<=ids or a['newSkips']:errors.append('test identity/SKIP')
        for name in a['tests']:
            a['tests'][name]['identitiesCoveredByFinalFull']=set(read(OUT/(name+'.json'))['testIdentities'])<=ids
            if not a['tests'][name]['identitiesCoveredByFinalFull']:errors.append('test coverage '+name)
        if not preflight:
            matrixmap=read(OUT/'matrix-test-map.json')
            mapped={t for row in matrixmap.values() for t in row['testIdentities']}
            a['matrixTestIdentityCoverage']=dict(rowCount=len(matrixmap),uniqueTests=len(mapped),
                allP18Tests=mapped==set(read(OUT/(config['LABELS'][0]+'.json'))['testIdentities']),
                coveredByFinalFull=mapped<=ids)
            if len(matrixmap)!=12 or not a['matrixTestIdentityCoverage']['allP18Tests'] or not mapped<=ids:
                errors.append('matrix test identity coverage')
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]}
        if a[key]['changed']:errors.append(key+' changed')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
    if a['formalTreeHash']!=b['formalTreeHash'] or a['pyprojectHash']!=b['pyproject'] or a['version']!='0.1.0':errors.append('formal/version')
    a['kickoffCopies']={name:sha(OUT/name)==sha(Path(v['source']))==v['sha256'] for name,v in b['kickoffCopies'].items()}
    if not all(a['kickoffCopies'].values()):errors.append('kickoff originals/copies')
    allowed=source_allowed|set(b['documentsAllowed'])
    a['historicalDrift']=[p for p,h in b['historicalFiles'].items() if p not in allowed and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    if a['historicalDrift']:errors.append('history changed')
    changed=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    finalpaths={(OUT/'final.audit.json').resolve(),(OUT/'final.pending-files.md').resolve(),(OUT/'delivery-report.md').resolve(),(OUT/'final-report.md').resolve()}
    pending=sorted((set(changed+untracked)-set(b['excluded']))|{p.relative_to(ROOT).as_posix() for p in (target,listing)})
    a['pending']=pending;a['pendingFileCount']=len(pending);a['excluded']=b['excluded']
    a['scopeErrors']=[p for p in pending if p not in allowed and not p.startswith('docs/project_memory/p18_evidence/')]
    if a['scopeErrors']:errors.append('pending scope')
    a['forbiddenArtifacts']=[p for p in pending if any(c in Path(p).parts for c in ('.git','.continuity-data','__pycache__','build','dist','node_modules')) or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('forbidden artifact')
    a['parsedPythonFiles']=0
    for name in current:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name);a['parsedPythonFiles']+=1
    for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    a['sensitiveMatches']=[];a['brokenLinks']=[];a['linkCount']=0;a['rawWhitespace']=[];a['editableWhitespace']=[]
    expected={target.resolve(),listing.resolve(),*finalpaths}
    for name in pending:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.json','.log','.py','.txt'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,text,expected);a['linkCount']+=count;a['brokenLinks'].extend((name,v) for v in bad)
        # Byte-exact kickoff archives and prior tracked historical evidence are preserved.
        if p.name in b['kickoffCopies'] or name==resume['resumeBrief']['copy'] or name in b['historicalFiles']:continue
        warnings=[{'path':name,'line':i,'kind':'trailing whitespace'} for i,line in enumerate(text.splitlines(),1) if line.endswith((' ','\t'))]
        if text.endswith('\n\n') and text.strip():warnings.append({'path':name,'line':len(text.splitlines()),'kind':'blank line at EOF'})
        (a['rawWhitespace'] if p.suffix=='.log' else a['editableWhitespace']).extend(warnings)
    if a['sensitiveMatches'] or a['brokenLinks'] or a['editableWhitespace']:errors.append('static/docs')
    a['historicalFormatWarnings']=read(DOC/'p17_acceptance_evidence/final.audit.json').get('preservedPriorEightWarnings')
    a['historicalP17RawWarnings']=read(DOC/'p17_acceptance_evidence/final.audit.json').get('preservedP17RawWarnings')
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf8')
    a['D072Count']=len(re.findall(r'^## D-072[：:]',decisions,re.M))
    a['D073Count']=len(re.findall(r'^## D-073[：:]',decisions,re.M))
    if a['D072Count']!=1 or a['D073Count']:errors.append('decision')
    if not preflight:
        matrix=(DOC/config['STAGE_FILES'][1]).read_text(encoding='utf8')
        a['matrixItems']=re.findall(r'^\| P18-(\d{2}) \|[^\n]*?\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
        if a['matrixItems']!=[f'{i:02}' for i in range(1,13)]:errors.append('matrix')
        for name in ['README.md',*['docs/project_memory/'+p for p in config['TOP']]]:
            text=(ROOT/name).read_text(encoding='utf8').split('<!-- P18_CURRENT_START -->',1)[1].split('<!-- P18_CURRENT_END -->',1)[0]
            if not all(value in text for value in ('IMPLEMENTED_NOT_ACCEPTED','P19—P23 NOT_STARTED','D-073 未创建','EVIDENCE_CONFLICT=PRESENT')):errors.append('current state '+name)
    result=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    a['diffCheck']=dict(exitCode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    if result.returncode:errors.append('git diff --check')
    a['git']=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),originMain=git('rev-parse','origin/main'),
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),staged=git('diff','--cached','--name-only'),
        remote=git('remote','get-url','origin'),remoteQueried=False,trackedChanged=changed)
    if a['git']['branch']!='main' or a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['staged']:errors.append('git baseline')
    if not set(b['excluded'])<=set(untracked):errors.append('excluded missing')
    a['ignoredPaths']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['ci']=dict(trackedWorkflows=git('ls-files','.github/workflows').splitlines(),remoteQueried=False,passClaimed=False)
    a['sourceAuthority']='Original SubjectState/Event/Memory/ThinkSession/Action/E5-A retained; Runtime metadata is infrastructure only.'
    content=['# P18 精确待提交清单（无暂存/提交授权）','',f'P18 工作区成果 {len(pending)} 项；本清单包含自身及对应审计。','',*('- `'+p+'`' for p in pending),'',f'## 原样保留的排除项（{len(b["excluded"])}）','',*('- `'+p+'`' for p in b['excluded'])]
    listing.write_text('\n'.join(content)+'\n',encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if (ROOT/p).is_file() and (ROOT/p)!=target}
    with target.open('x',encoding='utf8') as f:
        a['git']['status']=git('status','--short','--untracked-files=all')
        a['git']['untracked']=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
        json.dump(a,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:a[k] for k in ('errors','sourceCount','parsedPythonFiles','pendingFileCount','linkCount','brokenLinks','rawWhitespace','editableWhitespace')},ensure_ascii=False))
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())
