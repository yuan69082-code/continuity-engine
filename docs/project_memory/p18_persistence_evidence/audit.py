"""Read-only terminal audit; writes only new evidence/manifest, never Git state."""
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

OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=DOC.parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.persistence import tree_inventory_hash

CODE={'src/continuity_engine/storage/json_repository.py',
      'src/continuity_engine/services/wake_perception_thinking_action_service.py',
      'src/continuity_engine/testing/p18_runtime_fixture.py',
      'src/continuity_engine/testing/p18_persistence_diagnostics.py','tests/test_p18_persistence.py'}

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,
    encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    assert re.fullmatch('[a-z0-9-]+',label)
    target=OUT/(label+'.audit.json');listing=OUT/(label+'.pending-files.md')
    assert not target.exists() and not listing.exists()
    target.touch(exist_ok=False);listing.touch(exist_ok=False)
    b=read(OUT/'before.json');current=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
    cfg=runpy.run_path(str(DOC/'p18_evidence/prepare.py'))
    docs={'README.md',*['docs/project_memory/'+n for n in cfg['TOP']+cfg['STAGE_FILES']]}
    errors=[]
    a={'at':datetime.now(timezone.utc).isoformat(),'stage':'P18 persistence investigation/repair',
       'status':'IMPLEMENTED_NOT_ACCEPTED','planningConflict':'NONE','evidenceConflict':'PRESENT',
       'F2':'controlled sharing conflict reproduced and repaired; historical exact OS code/holder unknown',
       'F1':'UNKNOWN','H1':'UNKNOWN','gitWrites':False,'CI':'NOT_RUN','testsRunByAudit':False,
       'sourceTest':current,'sourceCount':len(current),'errors':errors}
    a['sourceHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['sourceChanged']=sorted(p for p in set(b['sourceTest'])|set(current) if b['sourceTest'].get(p)!=current.get(p))
    if set(a['sourceChanged'])!=CODE or set(b['sourceTest'])-set(current):errors.append('source scope')
    a['sourceMatchesFrozen']=current==read(OUT/'frozen-source.json')['sourceTest']
    if not a['sourceMatchesFrozen']:errors.append('source freeze')
    a['originalTestFilesChanged']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and current.get(p)!=h]
    if a['originalTestFilesChanged']:errors.append('original assertions/file changed')
    a['previousP18Changed']=[p for p,h in b['existingPending'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    a['historyDrift']=[p for p in a['previousP18Changed'] if p not in docs|CODE]
    a['originalEvidenceDrift']=[p for p,h in b['originalEvidence'].items() if sha(ROOT/p)!=h]
    if a['historyDrift'] or a['originalEvidenceDrift']:errors.append('old evidence drift')
    a['archive']={}
    for name,row in b['archive'].items():
        a['archive'][name]={'copyMatches':sha(ROOT/row['copy'])==row['sha256'],
                          'initialSourceHashMatches':b['sourceTest'].get(name,b['originalEvidence'].get(name))==row['sha256']}
    if any(not r['copyMatches'] or not r['initialSourceHashMatches'] for r in a['archive'].values()):errors.append('archive hash')
    a['protection']={kind:{'count':len(values),'changed':[p for p,h in values.items() if sha(ROOT/p)!=h]}
                     for kind,values in b['protected'].items()}
    if any(r['changed'] for r in a['protection'].values()):errors.append('protected identity')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
    if a['formalTreeHash']!=b['formalTreeHash'] or a['pyprojectHash']!=b['pyproject'] or a['version']!='0.1.0':errors.append('formal/version')
    a['pythonAST']=0
    for path in [ROOT/p for p in current if p.endswith('.py')]+list(OUT.rglob('*.py')):
        ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path));a['pythonAST']+=1
    selected=read(OUT/'selected-runs.json');a['tests']={}
    full=read(OUT/(selected['full']+'.json'));ids=set(full['testIdentities'])
    for key,label_run in selected.items():
        r=read(OUT/(label_run+'.json'))
        a['tests'][key]={k:r.get(k) for k in ('command','status','run','passed','skips','seconds','exitCode')}
        a['tests'][key].update(failures=len(r['failures']),errors=len(r['errors']),sourceMatches=r['sourceBefore']==r['sourceAfter']==current,
            includedInFull=set(r['testIdentities'])<=ids,hashes={suffix:sha(OUT/(label_run+suffix)) for suffix in ('.json','.stdout.log','.stderr.log')})
        if r['status']!='FINISHED' or r['exitCode']!=0 or not a['tests'][key]['sourceMatches'] or not a['tests'][key]['includedInFull']:errors.append('test coverage/result '+key)
    a['missingOriginalIdentities']=sorted(set(b['testIdentities'])-ids)
    a['newIdentities']=sorted(ids-set(b['testIdentities']))
    a['frozenTestIdentitiesMatch']=ids==set(read(OUT/'frozen-source.json')['testIdentities'])
    oldskip=read(DOC/'p18_r2_evidence/full-resume-01.json')['skips']
    a['newSkips']=[r for r in full['skips'] if r not in oldskip]
    if a['missingOriginalIdentities'] or a['newSkips'] or not a['frozenTestIdentitiesMatch']:errors.append('tests/skip inventory')
    a['processCheck']=read(OUT/'process-check.json')
    if a['processCheck']['matchingCount']:errors.append('live test process')
    a['processEvidence']={}
    for key,label_run in selected.items():
        rows=[]
        for line in (OUT/(label_run+'.stdout.log')).read_text(encoding='utf8').splitlines():
            try:row=json.loads(line)
            except ValueError:continue
            if isinstance(row,dict) and 'childrenReaped' in row:rows.append(row)
        forced=[r for r in rows if r.get('forcedCleanup') or any(e.get('forcedCleanup') for e in r.get('processEvidence',[]))]
        a['processEvidence'][key]={'records':len(rows),'allReaped':all(r['childrenReaped'] for r in rows),'forced':forced}
        if not a['processEvidence'][key]['allReaped']:errors.append('unreaped children '+key)
        # Deliberate crash/termination tests are retained as such, never normal STOP.
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    pending=sorted(set(tracked+untracked)-set(b['excluded']))
    a.update(pending=pending,pendingCount=len(pending),excluded=b['excluded'],excludedCount=len(b['excluded']))
    a['addedPendingThisInvestigation']=sorted(set(pending)-set(b['existingPending']))
    a['scopeErrors']=[p for p in pending if p not in b['existingPending'] and p not in CODE|docs and not p.startswith('docs/project_memory/p18_persistence_evidence/')]
    a['excludedMissingOrTracked']=[p for p in b['excluded'] if p not in untracked or p in tracked]
    if a['scopeErrors'] or a['excludedMissingOrTracked']:errors.append('pending scope')
    a['forbiddenArtifacts']=[p for p in pending if set(Path(p).parts)&{'.continuity-data','__pycache__','build','dist','.git'} or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('forbidden artifact')
    checker=runpy.run_path(str(DOC/'p14_evidence/audit.py'))['links']
    a['linksChecked']=0;a['brokenLinks']=[]
    for name in docs|{p.relative_to(ROOT).as_posix() for p in OUT.rglob('*.md')}:
        path=ROOT/name;count,bad=checker(path,path.read_text(encoding='utf8'),expected=((OUT/'final.audit.json').resolve(),(OUT/'final.pending-files.md').resolve()))
        a['linksChecked']+=count
        if bad:a['brokenLinks'].append({'file':name,'targets':bad})
    if a['brokenLinks']:errors.append('links')
    a['sensitiveCandidates']=[];a['newEditableWhitespace']=[];a['preservedEvidenceWhitespace']=[];a['diffContextWhitespace']=[]
    for name in pending:
        path=ROOT/name
        if path in (target,listing):continue
        text=path.read_text(encoding='utf8',errors='replace')
        for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'sk-proj-[A-Za-z0-9_-]{40,}'):
            if re.search(pattern,text):a['sensitiveCandidates'].append(name)
        if name in a['addedPendingThisInvestigation'] or name in a['previousP18Changed']:
            bad=[i for i,line in enumerate(text.splitlines(),1) if line.rstrip()!=line]
            if bad:
                bucket='diffContextWhitespace' if name.endswith('.patch') else 'preservedEvidenceWhitespace' if name.endswith('.log') or '/archive/' in name or '/source-before/' in name else 'newEditableWhitespace'
                a[bucket].append({'file':name,'lines':bad})
    if a['sensitiveCandidates'] or a['newEditableWhitespace']:errors.append('new content warning')
    a['historicalWarnings']=read(DOC/'p18_r2_evidence/final.audit.json').get('priorFormatWarnings')
    a['oldP18RawWhitespace']={'file':'docs/project_memory/p18_r2_evidence/full-final-01.stderr.log','line':721,'preserved':True}
    result=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    a['diffCheck']={'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    if result.returncode:errors.append('diff check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
              'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
              'tracked':tracked,'untracked':untracked,'fullStatus':git('status','--short','--untracked-files=all'),'remoteQueried':False}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['branch']!='main' or a['git']['staged']:errors.append('git baseline')
    a['currentDocsConsistent']=all('IMPLEMENTED_NOT_ACCEPTED' in (ROOT/p).read_text(encoding='utf8')[:1000] and
                                    'EVIDENCE_CONFLICT=PRESENT' in (ROOT/p).read_text(encoding='utf8')[:1000] for p in docs)
    a['D073Created']=bool(re.search(r'^## D-073[：:]',(DOC/'04_决策记录.md').read_text(encoding='utf8'),re.M))
    if not a['currentDocsConsistent'] or a['D073Created']:errors.append('stage/decision')
    listing.write_text('# P18全部成果与本次持久化返修精确清单\n\n'+f'全部P18待提交 {len(pending)} 项（含之前未提交成果），排除 {len(b["excluded"])} 项；仅列清单，无暂存/提交。\n\n## 本次新增或修改源码\n\n'+'\n'.join('- '+p for p in sorted(CODE))+'\n\n## 本次修改既有成果\n\n'+'\n'.join('- '+p for p in a['previousP18Changed'])+'\n\n## 本次新增待提交路径\n\n'+'\n'.join('- '+p for p in a['addedPendingThisInvestigation'])+'\n\n## 全部P18成果\n\n'+'\n'.join('- '+p for p in pending)+'\n\n## 原样排除\n\n'+'\n'.join('- '+p for p in b['excluded'])+'\n',encoding='utf8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if ROOT/p!=target}
    a['checksPassed']=not errors
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'errors':errors,'files':len(current),'pending':len(pending),'excluded':len(b['excluded']),
                      'tracked':len(tracked),'untracked':len(untracked),'sourceHash':a['sourceHash']},ensure_ascii=False))
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())
