"""P18 R2 final read-only verification, excluding its own hash from its manifest."""
from pathlib import Path
from datetime import datetime, timezone
import ast, hashlib, json, os, re, runpy, subprocess, sys, tomllib

OUT=Path(__file__).resolve().parent; DOC=OUT.parent; ROOT=DOC.parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
def source():return {p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
CODE={'src/continuity_engine/domain/thinking.py','src/continuity_engine/services/thinking_service.py',
      'src/continuity_engine/storage/json_thinking_repository.py','src/continuity_engine/services/runtime_cognition.py',
      'src/continuity_engine/services/wake_perception_thinking_action_service.py',
      'src/continuity_engine/testing/p18_runtime_fixture.py','tests/test_p18_runtime_process.py','tests/test_p18_runtime_resume.py'}
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    assert re.fullmatch('[a-z0-9-]+',label)
    target=OUT/(label+'.audit.json');listing=OUT/(label+'.pending-files.md')
    assert not target.exists() and not listing.exists()
    # Reserve both new evidence paths before collecting the exact Git inventory.
    target.touch(exist_ok=False);listing.touch(exist_ok=False)
    b=read(OUT/'before.json');current=source();errors=[]
    config=runpy.run_path(str(DOC/'p18_evidence/finalize.py'))
    docs={'README.md',*['docs/project_memory/'+p for p in config['TOP']+config['STAGE_FILES']]}
    a=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18 R2 repair',status='IMPLEMENTED_NOT_ACCEPTED',
           evidenceConflict='PRESENT',planningConflict='NONE',R1='independent targeted review confirmed; retained',
           R2='implemented; independent review pending',F1='UNKNOWN',H1='UNKNOWN',F2='new full-resume-01 failure; root cause UNKNOWN; no rerun or code change',errors=errors,
           sourceTest=current,sourceCount=len(current),gitWrites=False,ci='NOT_RUN',testsRunByAudit=False)
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['sourceChanged']=sorted(p for p in set(current)|set(b['sourceTest']) if current.get(p)!=b['sourceTest'].get(p))
    if set(a['sourceChanged'])-CODE or set(b['sourceTest'])-set(current):errors.append('source scope')
    a['previousP18Changed']=sorted(p for p,h in b['originalP18Files'].items() if sha(ROOT/p)!=h)
    a['oldEvidenceDrift']=[p for p in a['previousP18Changed'] if p not in CODE|docs]
    earlier_changes=[p for p,h in b['historicalFiles'].items() if p not in b['originalP18Files'] and sha(ROOT/p)!=h]
    # The inherited inventory also includes live source files. Their approved
    # R2 changes are checked against the frozen source and every selected run;
    # they are not immutable historical evidence files.
    frozen=read(OUT/'frozen-source.json')['sourceTest']
    a['approvedEarlierSourceChanges']={p:dict(before=b['sourceTest'][p],after=current[p]) for p in earlier_changes
        if p in CODE and b['historicalFiles'][p]==b['sourceTest'].get(p) and current.get(p)==frozen.get(p)}
    a['earlierHistoryDrift']=[p for p in earlier_changes if p not in a['approvedEarlierSourceChanges']]
    if a['oldEvidenceDrift'] or a['earlierHistoryDrift']:errors.append('history drift')
    archive={**b['archive'],**read(OUT/'additional-archive.json')}
    a['archive']={p:sha(Path(r['source']))==sha(ROOT/r['copy'])==r['sha256'] for p,r in archive.items()}
    if not all(a['archive'].values()):errors.append('independent original/archive')
    a['protection']={k:dict(count=len(v),changed=[p for p,h in v.items() if sha(ROOT/p)!=h]) for k,v in b['protected'].items()}
    if any(r['changed'] for r in a['protection'].values()):errors.append('protected')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data');a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
    if a['formalTreeHash']!=b['formalTreeHash'] or a['pyprojectHash']!=b['pyproject'] or a['version']!='0.1.0':errors.append('formal/version')
    old_audit=runpy.run_path(str(DOC/'p18_repair_evidence/audit.py'))
    oldtext=(OUT/'source-before/test_p18_runtime_process.py').read_text(encoding='utf8')
    newtext=(ROOT/'tests/test_p18_runtime_process.py').read_text(encoding='utf8')
    def args(text):return {n.name:ast.dump(n.args,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef)}
    oldassert=old_audit['assertions'](oldtext);newassert=old_audit['assertions'](newtext)
    a['originalProcessAssertions']=all(newassert.get(k)==v for k,v in oldassert.items())
    a['originalProcessTimeouts']=all(args(newtext).get(k)==v for k,v in args(oldtext).items())
    a['otherOriginalTestsChanged']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and p!='tests/test_p18_runtime_process.py' and current.get(p)!=h]
    if not a['originalProcessAssertions'] or not a['originalProcessTimeouts'] or a['otherOriginalTestsChanged']:errors.append('old tests')
    a['pythonAST']=0
    for p in [ROOT/n for n in current if n.endswith('.py')]+list(OUT.glob('*.py')):
        ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p));a['pythonAST']+=1
    a['tests']={};selected=read(OUT/'selected-runs.json')
    interruption=read(OUT/'interruption-full-final-01.json')
    a['interruptedFull']=dict(label=interruption['label'],classification=interruption['classification'],
        actualExitCode=interruption['actualExitCode'],actualInterruptionCause=interruption['actualInterruptionCause'],
        originalsUnchanged={p:sha(OUT/p)==v['sha256'] for p,v in interruption['originalFilesUnmodified'].items()},
        sourceAfterAvailable=False,finalCounts='UNKNOWN',notCountedAsPassOrEngineFail=True)
    if not all(a['interruptedFull']['originalsUnchanged'].values()):errors.append('interrupted full evidence drift')
    resume_check=read(OUT/'resume-identity-check.json')
    a['previousCompletedGroupsReused']={k:dict(label=v['label'],
        evidenceUnchanged=sha(OUT/(v['label']+'.json'))==v['evidenceSha256'],
        selectedMatches=selected[k]==v['label'],rerunDuringResume=False)
        for k,v in resume_check['completedGroups'].items()}
    if any(not v['evidenceUnchanged'] or not v['selectedMatches'] for v in a['previousCompletedGroupsReused'].values()):errors.append('reused result drift')
    a['previousCompletedOutputsUnchanged']={p:sha(OUT/p)==h
        for p,h in read(OUT/'resume-reused-output-hashes.json')['files'].items()}
    if not all(a['previousCompletedOutputsUnchanged'].values()):errors.append('reused raw output drift')
    a['onlyNewRegressionDuringResume']=selected['full']
    if selected['full']!=interruption['replacementRun']:errors.append('resume full selection')
    for kind,name in selected.items():
        r=read(OUT/(name+'.json'))
        a['tests'][kind]={k:r.get(k) for k in ('command','status','run','passed','skips','failures','errors','seconds','exitCode')}
        a['tests'][kind]['sourceMatches']=r['sourceBefore']==r['sourceAfter']==current
        if r['status']!='FINISHED' or r['exitCode']!=0 or not a['tests'][kind]['sourceMatches']:errors.append('test identity/result '+kind)
    full=read(OUT/(selected['full']+'.json'));ids=set(full['testIdentities'])
    failure_record=read(OUT/'full-resume-01-failure.json')
    a['newFullFailureEvidenceUnchanged']={p:sha(OUT/p)==h for p,h in failure_record['rawEvidenceHashes'].items()}
    if not all(a['newFullFailureEvidenceUnchanged'].values()):errors.append('new full failure evidence drift')
    a['behaviorValidationPassed']=full['exitCode']==0
    a['frozenTestIdentitiesMatch']=ids==set(read(OUT/'frozen-source.json')['testIdentities'])
    if not a['frozenTestIdentitiesMatch']:errors.append('frozen test identities')
    a['old1444IdentitiesRetained']=set(b['testIdentities'])<=ids
    a['newIdentities']=sorted(ids-set(b['testIdentities']))
    a['groupsCoveredByFull']={k:set(read(OUT/(v+'.json'))['testIdentities'])<=ids for k,v in selected.items() if not k.startswith('independent')}
    if not a['old1444IdentitiesRetained'] or not all(a['groupsCoveredByFull'].values()):errors.append('identity coverage')
    a['newSkips']=[r for r in full['skips'] if r not in read(DOC/'p18_repair_evidence/full-final-01.json')['skips']]
    if a['newSkips']:errors.append('new skips')
    a['processes']={}
    for kind in ('formal','p18','full'):
        records=[]
        for line in (OUT/(selected[kind]+'.stdout.log')).read_text(encoding='utf8').splitlines():
            try:r=json.loads(line)
            except ValueError:continue
            if 'childrenReaped' in r:records.append(r)
        a['processes'][kind]=dict(records=len(records),allReaped=bool(records) and all(r['childrenReaped'] for r in records),
            forced=[r for r in records if r.get('forcedCleanup') or any(e.get('forcedCleanup') for e in r.get('processEvidence',[]))])
        if not a['processes'][kind]['allReaped'] or a['processes'][kind]['forced']:errors.append('child cleanup '+kind)
    a['processCheck']=read(OUT/'process-check.json')
    if a['processCheck']['matchingCount']:errors.append('live runtime process')
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    pending=sorted((set(tracked+untracked)-set(b['excluded']))|{p.relative_to(ROOT).as_posix() for p in (target,listing)})
    a['pending']=pending;a['pendingCount']=len(pending);a['excluded']=b['excluded']
    a['addedThisRepair']=sorted(set(pending)-set(b['originalP18Files']))
    a['scopeErrors']=[p for p in pending if p not in b['originalP18Files'] and p not in CODE|docs and not p.startswith('docs/project_memory/p18_r2_evidence/')]
    if a['scopeErrors']:errors.append('pending scope')
    a['forbiddenArtifacts']=[p for p in pending if set(Path(p).parts)&{'.continuity-data','__pycache__','build','dist','.git'} or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('forbidden artifacts')
    linkcheck=runpy.run_path(str(DOC/'p14_evidence/audit.py'))['links'];a['linksChecked']=0;a['brokenLinks']=[]
    for name in docs|{p.relative_to(ROOT).as_posix() for p in OUT.rglob('*.md')}:
        path=ROOT/name;n,bad=linkcheck(path,path.read_text(encoding='utf8'),
            expected=(target.resolve(),listing.resolve(),(OUT/'final.audit.json').resolve(),(OUT/'final.pending-files.md').resolve()))
        a['linksChecked']+=n
        if bad:a['brokenLinks'].append(dict(path=name,targets=bad))
    if a['brokenLinks']:errors.append('links')
    a['sensitiveMatches']=[]
    for name in pending:
        path=ROOT/name
        if path in (target,listing) or not path.is_file():continue
        text=path.read_text(encoding='utf8',errors='replace')
        for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'sk-proj-[A-Za-z0-9_-]{40,}'):
            if re.search(pattern,text):a['sensitiveMatches'].append(name)
    if a['sensitiveMatches']:errors.append('secret candidate')
    a['newEditableWhitespace']=[];a['preservedEvidenceWhitespace']=[]
    a['priorFormatWarnings']=read(DOC/'p18_repair_evidence/final.audit.json')['priorFormatWarnings']
    for name in a['addedThisRepair']+a['previousP18Changed']:
        path=ROOT/name
        if not path.is_file() or path in (target,listing):continue
        lines=path.read_text(encoding='utf8',errors='replace').splitlines()
        bad=[i for i,line in enumerate(lines,1) if line.rstrip()!=line]
        if bad:
            bucket='preservedEvidenceWhitespace' if name.endswith('.log') or '/independent/' in name or '/source-before/' in name else 'newEditableWhitespace'
            a[bucket].append(dict(path=name,lines=bad))
    if a['newEditableWhitespace']:errors.append('new whitespace')
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    a['diffCheck']=dict(exitCode=diff.returncode,stdout=diff.stdout,stderr=diff.stderr)
    if diff.returncode:errors.append('diff check')
    a['git']=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),originMain=git('rev-parse','origin/main'),
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),staged=git('diff','--cached','--name-only'),
        tracked=tracked,untracked=untracked,fullStatus=git('status','--short','--untracked-files=all'),remoteQueried=False)
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['branch']!='main' or a['git']['staged']:errors.append('git baseline')
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf8')
    a['currentDocsConsistent']=all('IMPLEMENTED_NOT_ACCEPTED' in (ROOT/p).read_text(encoding='utf8')[:1000]
        and 'EVIDENCE_CONFLICT=PRESENT' in (ROOT/p).read_text(encoding='utf8')[:1000] for p in docs)
    if not a['currentDocsConsistent']:errors.append('current status')
    a['D073Created']=bool(re.search(r'^## D-073[：:]',decisions,re.M))
    if a['D073Created']:errors.append('acceptance created')
    a['staticChecksPassed']=not [e for e in errors if e!='test identity/result full']
    text='# P18 R2 最终逐文件清单（不暂存/提交）\n\n'+f'全部 P18 成果 {len(pending)} 项；原排除 {len(b["excluded"])} 项。\n\n## P18 完整成果\n\n'+'\n'.join('- '+p for p in pending)+'\n\n## 本轮新增\n\n'+'\n'.join('- '+p for p in a['addedThisRepair'])+'\n\n## 本轮修改既有成果\n\n'+'\n'.join('- '+p for p in a['previousP18Changed'])+'\n\n## 排除并原样保留\n\n'+'\n'.join('- '+p for p in b['excluded'])+'\n'
    listing.write_text(text,encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if ROOT/p!=target}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(errors=errors,sourceCount=len(current),sourceHash=a['sourceInventoryHash'],pending=len(pending),excluded=len(b['excluded']),tracked=len(tracked),untracked=len(untracked)),ensure_ascii=False))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
