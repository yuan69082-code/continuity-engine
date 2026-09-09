"""Read-only P17 R1/R2 verification and exact un-staged change manifest."""
from pathlib import Path
from datetime import datetime,timezone
import ast
import hashlib
import json
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
config=runpy.run_path(str(OUT/'finalize.py'))
links=runpy.run_path(str(DOC/'p14_evidence/audit.py'))['links']

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,encoding='utf-8').strip()

def main():
    target=OUT/'final.audit.json';listing=OUT/'final.pending-files.md'
    assert not target.exists() and not listing.exists(),'preserve any prior audit'
    b=read(OUT/'before.json');errors=[]
    a=dict(at=datetime.now(timezone.utc).isoformat(),stage='P17 R1/R2',status='IMPLEMENTED_NOT_ACCEPTED',
           planningConflict='NONE',evidenceConflict='PRESENT',gitWrites=False,errors=errors,testsExecutedByAudit=False)
    source=config['source']();a['sourceTest']=source;a['sourceCount']=len(source)
    a['sourceInventoryHash']='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a['tests']={}
    for label in config['LABELS']:
        r=read(OUT/(label+'.json'))
        a['tests'][label]={k:r[k] for k in ('status','run','passed','skips','failures','errors','seconds','exitCode','command')}
        if r['status']!='FINISHED' or r['exitCode'] or r['sourceBefore']!=source or r['sourceAfter']!=source:errors.append('test identity/result '+label)
    full=read(OUT/'full-final-01.json');ids=set(full['testIdentities']);old=set(b['testIdentities'])
    prior_skips={x[0] for x in read(DOC/'p17_evidence/full-final-02.json')['skips']}
    a['newSkipIdentities']=sorted({x[0] for x in full['skips']}-prior_skips)
    if a['newSkipIdentities']:errors.append('new skip')
    a['originalIdentityCount']=len(old);a['originalIdentitiesPreserved']=old<=ids;a['newIdentities']=sorted(ids-old)
    a['originalTestHashChanged']=[p for p,h in b['sourceTest'].items() if p.startswith('tests/') and source.get(p)!=h]
    a['sourceChangedSinceReview']=[p for p,h in b['sourceTest'].items() if source.get(p)!=h]
    a['sourceAddedSinceReview']=sorted(set(source)-set(b['sourceTest']))
    if not a['originalIdentitiesPreserved'] or a['originalTestHashChanged']:errors.append('original tests changed')
    if set(a['sourceChangedSinceReview'])!=config['IMPLEMENTATION'] or a['sourceAddedSinceReview']!=[config['NEW_TEST']]:errors.append('source scope')
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        a[key]={'count':len(b[key]),'changed':[p for p,h in b[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]}
        if a[key]['changed']:errors.append(key)
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    a['pyprojectHash']=sha(ROOT/'pyproject.toml');a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if a['formalTreeHash']!=b['formalTreeHash'] or a['pyprojectHash']!=b['pyproject'] or a['version']!='0.1.0':errors.append('formal/version')
    a['independentCopyChecks']={name:sha(OUT/'independent'/name)==sha(Path(v['source']))==v['sha256'] for name,v in b['independentCopies'].items()}
    if not all(a['independentCopyChecks'].values()):errors.append('independent originals/archive')
    a['parsedPythonFiles']=0
    for name in source:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name);a['parsedPythonFiles']+=1
    for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    changed=[p for p in git('diff','--name-only','-z').split('\0') if p]
    new=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    pending=sorted((set(changed+new)-set(b['excluded']))|{target.relative_to(ROOT).as_posix(),listing.relative_to(ROOT).as_posix()})
    a['pending']=pending;a['pendingFileCount']=len(pending);a['excluded']=b['excluded']
    a['originalP17Pending']=b['originalPending']
    a['repairModifiedExisting']=[p for p,h in b['originalPendingHashes'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    a['repairAdded']=sorted(set(pending)-set(b['originalPending']))
    a['originalP17Unchanged']=sorted(set(b['originalPending'])-set(a['repairModifiedExisting']))
    allowed_docs={'README.md'}|{'docs/project_memory/'+name for name in config['TOP']}
    allowed_docs|={p.relative_to(ROOT).as_posix() for num in ('79','80','81','82') for p in DOC.glob(num+'_P17_*.md')}
    a['scopeErrors']=[p for p in a['repairModifiedExisting'] if p not in allowed_docs|config['IMPLEMENTATION']]
    a['scopeErrors'] += [p for p in a['repairAdded'] if p!=config['NEW_TEST'] and not p.startswith('docs/project_memory/p17_repair_evidence/')]
    if not set(b['originalPending'])<=set(pending):a['scopeErrors'].append('original P17 path lost')
    snapshot=read(OUT/'independent/independent-edges-02.after.json')
    a['historicalDriftOutsideRepair']=[p for p,h in snapshot.items() if p not in allowed_docs|config['IMPLEMENTATION'] and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    if a['scopeErrors'] or a['historicalDriftOutsideRepair']:errors.append('scope/history')
    a['forbiddenArtifacts']=[p for p in pending if any(c in Path(p).parts for c in ('.git','.continuity-data','__pycache__','build','dist','node_modules')) or p.endswith(('.pyc','.whl','.zip','.tmp'))]
    if a['forbiddenArtifacts']:errors.append('artifact')
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    a['sensitiveMatches']=[];a['brokenLinks']=[];a['linkCount']=0;a['newRawWhitespace']=[];a['newEditableWhitespace']=[]
    expected={target.resolve(),listing.resolve()}
    for name in pending:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.json','.log','.py','.txt'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,text,expected);a['linkCount']+=count;a['brokenLinks'].extend((name,x) for x in bad)
        # Historical files and byte-exact independent copies retain their formatting.
        if '/independent/' in name:continue
        modified_untracked=name in a['repairModifiedExisting'] and name in new
        if name not in a['repairAdded'] and not modified_untracked:continue
        findings=[{'path':name,'line':i,'kind':'trailing whitespace'} for i,line in enumerate(text.splitlines(),1) if line.endswith((' ','\t'))]
        if text.endswith('\n\n') and text.strip():findings.append({'path':name,'line':len(text.splitlines()),'kind':'new blank line at EOF'})
        (a['newRawWhitespace'] if p.suffix=='.log' else a['newEditableWhitespace']).extend(findings)
    if a['sensitiveMatches'] or a['brokenLinks'] or a['newEditableWhitespace']:errors.append('static material/docs')
    a['preservedPriorFormattingWarnings']={k:v for k,v in read(DOC/'p17_evidence/final.audit.json').items() if k in ('historicalEightWarnings','newRawEvidenceWhitespace')}
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf-8')
    a['D071Count']=len(re.findall(r'^## D-071[：:]',decisions,re.M))
    if a['D071Count']:errors.append('acceptance decision')
    matrix=next(DOC.glob('80_P17_*.md')).read_text(encoding='utf-8')
    a['matrixItems']=re.findall(r'^\| P17-(\d{2}) \|[^\n]*\| IMPLEMENTED_NOT_ACCEPTED \|',matrix,re.M)
    if a['matrixItems']!=[f'{i:02}' for i in range(1,13)]:errors.append('matrix state')
    for name in allowed_docs-{'docs/project_memory/'+p.name for n in ('79','80','81','82') for p in DOC.glob(n+'_P17_*.md')}:
        text=(ROOT/name).read_text(encoding='utf-8');block=text.split('<!-- P17_REPAIR_CURRENT_START -->',1)[1].split('<!-- P17_REPAIR_CURRENT_END -->',1)[0]
        if not all(s in block for s in ('IMPLEMENTED_NOT_ACCEPTED','EVIDENCE_CONFLICT=PRESENT','P18—P23 NOT_STARTED','D-071未创建')):errors.append('current status '+name)
    d=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8');a['diffCheck']={'exitCode':d.returncode,'stdout':d.stdout,'stderr':d.stderr}
    if d.returncode:errors.append('git diff --check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
              'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),
              'remote':git('remote','get-url','origin'),'remoteQueried':False,'trackedChanged':changed}
    if a['git']['branch']!='main' or a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['staged']:errors.append('git baseline')
    if not set(b['excluded'])<=set(new):errors.append('excluded paths')
    a['ignoredPaths']=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    a['ci']={'trackedWorkflows':git('ls-files','.github/workflows').splitlines(),
             'remoteChecksQueried':False,'runPerformedThisRepair':False,'passClaimed':False}
    a['isolation']='Validated independent TEST Temp roots only; no formal data writes or production services. Original snapshot and excluded materials retained.'
    sections=[('# P17全量工作区成果与R1/R2精确增量',[]),('完整P17成果（'+str(len(pending))+'项；未暂存）',pending),
        ('其中既有P17成果被本次返修修改',a['repairModifiedExisting']),('本次新增文件',a['repairAdded']),('原样保留的既有P17成果',a['originalP17Unchanged']),('排除且原样保留（32项）',b['excluded'])]
    content=[]
    for title,paths in sections:content.extend([title if title.startswith('# ') else '## '+title,'',*('- `'+p+'`' for p in paths),''])
    listing.write_text('\n'.join(content).rstrip()+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in pending if p!=target.relative_to(ROOT).as_posix()}
    with target.open('x',encoding='utf-8') as f:
        a['git']['status']=git('-c','core.quotepath=false','status','--short','--untracked-files=all')
        a['git']['untracked']=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
        json.dump(a,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:a[k] for k in ('errors','sourceCount','parsedPythonFiles','linkCount','pendingFileCount','newRawWhitespace','newEditableWhitespace')},ensure_ascii=False))
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())
