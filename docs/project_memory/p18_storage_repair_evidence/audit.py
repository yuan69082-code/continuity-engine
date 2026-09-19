"""Read-only identities plus a new manifest at the specific policy-confirmation pause."""
import ast,datetime,hashlib,json,os,re,runpy,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def paths(*args):return git(*args).stdout.splitlines()
b=read(OUT/'before.json');source=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
changed_docs=['README.md']+['docs/project_memory/'+n for n in ['01_当前状态.md','03_施工日志.md','84_P18_规划施工测试验收矩阵.md','86_P18_测试索引与验收入口.md']]
assert source==b['sourceTest']
assert all(sha(ROOT/p)==h for p,h in b['existingPending'].items() if p not in changed_docs)
assert all(sha(ROOT/p)==h for group in b['protected'].values() for p,h in group.items())
assert set(p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file())==set(b['protected']['formalFiles'])
assert sha(ROOT/'pyproject.toml')==b['pyproject']
for original,a in b['archives'].items():assert sha(ROOT/original)==a['sha256']==sha(ROOT/a['copy'])
assert git('branch','--show-current').stdout.strip()=='main'
assert git('rev-parse','HEAD').stdout.strip()==b['head']==git('rev-parse','origin/main').stdout.strip()
assert not paths('diff','--cached','--name-only')

labels=['prior-boundaries-before-01','retry-observations-01','original-flows-before-01','advancing-clock-before-01']
results={};processes=[]
for label in labels:
    r=read(OUT/(label+'.json'));assert r['status']=='FINISHED' and r['sourceBefore']==source==r['sourceAfter']
    results[label]={k:r[k] for k in ('run','passed','seconds','exitCode','status')}
    results[label].update(failures=len(r['failures']),errors=len(r['errors']),skips=len(r['skips']))
    for line in (OUT/(label+'.stdout.log')).read_text(encoding='utf8').splitlines():
        if not line.startswith('{'):continue
        row=json.loads(line)
        if 'childrenReaped' in row:assert row['childrenReaped'] is True
        if 'readerReaped' in row:assert row['readerReaped'] is True
        for p in row.get('processEvidence',[]):
            if p.get('stage')=='continuous-child':
                assert p['exitCode']==0 and not p['forcedCleanup']
                processes.append(dict(label=label,pid=p['pid'],exitCode=0,forcedCleanup=False))
acl={}
for label in ['acl-access-01','acl-access-01-cleanup','acl-access-02']:
    r=read(OUT/'independent'/(label+'.json'));assert r['sourceBefore']==source==r['sourceAfter']
    acl[label]={k:r[k] for k in ('status','exitCode','seconds')}
    acl[label]['cleanup']=r.get('cleanup',{'ownedRootRemoved':r.get('ownedRootRemoved')})
assert read(OUT/'independent/acl-access-01-cleanup.json')['ownedRootRemoved']
assert read(OUT/'independent/acl-access-02.json')['cleanup']['ownedRootRemoved']

for folder in (ROOT/'src',ROOT/'tests',OUT):
    for p in folder.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
suffix=('-'+sys.argv[1]) if len(sys.argv)>1 else ''
pending_file=OUT/('pending-files'+suffix+'.md');audit_file=OUT/('audit'+suffix+'.json')
assert not pending_file.exists() and not audit_file.exists()
pending=sorted(set(paths('diff','--name-only')+paths('ls-files','--others','--exclude-standard')+
    [p.relative_to(ROOT).as_posix() for p in (pending_file,audit_file)])-set(b['excluded']))
new=[p for p in pending if p not in b['existingPending']]
assert all(p.startswith('docs/project_memory/p18_storage_repair_evidence/') or p in changed_docs for p in new)
excluded_hashes={**b['protected']['excludedP10'],**b['protected']['otherPreserved']}
lines=['# P18精确未提交清单：拒绝行为差异等待确认','',
    f'当前P18成果{len(pending)}项，既有{len(b["existingPending"])}项保留，本轮新增计入清单{len(new)}项，均为本目录新证据/辅助测试/档案。另有32项排除。未执行任何Git写操作。',
    '运行实现和正式测试仍267文件、1480原身份；仅下面5份既有工程档案追加本轮进度。最新audit因自引用不记录自身hash；自身路径仍列入完整清单。首版审计与辅助路径错误记录原样保留。','',
    '## 本轮修改的既有档案','']+['- '+p for p in changed_docs]
lines+=['','## 本轮新增材料','']+['- '+p for p in new]
lines+=['','## 全部P18未提交成果','']+['- '+p for p in pending]
lines+=['','## 原32项排除材料','']+['- '+p+' — '+h for p,h in excluded_hashes.items()]
pending_file.write_text('\n'.join(lines)+'\n',encoding='utf8')

links=[];bad=[]
for p in [ROOT/n for n in changed_docs]+list(OUT.rglob('*.md')):
    for dest in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        if dest.startswith(('https:','http:','#','app:')):continue
        target=dest.split('#')[0].strip('<>')
        if not target:continue
        q=(p.parent/target).resolve()
        if not q.exists() and q!=audit_file.resolve():bad.append({'file':p.relative_to(ROOT).as_posix(),'target':target})
        links.append(dest)
secret=[]
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix in {'.json','.md','.py','.log'}:
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}',p.read_text(encoding='utf-8-sig')):secret.append(p.relative_to(ROOT).as_posix())
diff=git('diff','--check')
a=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='P18',status='IMPLEMENTED_NOT_ACCEPTED',
    evidenceConflict='PRESENT',twoFileScope='AUTHORIZED',refusalBehaviorDifference='WAITING_FOR_EXPLICIT_CONFIRMATION',
    sourceTest=source,sourceHash=b['sourceHash'],formalTestIdentityCount=len(b['testIdentities']),sourceUnchanged=True,
    originalPendingCount=len(b['existingPending']),originalPendingUnchangedExcept=changed_docs,protectedUnchanged=True,
    protectedGroups={k:len(v) for k,v in b['protected'].items()},formalTreeHash=b['formalTreeHash'],pyprojectHash=b['pyproject'],
    archives=b['archives'],results=results,aclExperiments=acl,processes=processes,processObservation=read(OUT/'process-observation.json'),
    pythonAST='PASS',linkCount=len(links),linkWarnings=bad,secretPatternFindings=secret,
    secretScanLimit='Narrow private-key/API-key signatures; synthetic TEST diagnostics only.',
    diffCheck={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr},
    pendingCount=len(pending),newInvestigationCount=len(new),excluded=excluded_hashes,
    pendingHashes={p:sha(ROOT/p) for p in pending if ROOT/p!=audit_file},
    git=dict(head=b['head'],localOrigin=git('rev-parse','origin/main').stdout.strip(),branch='main',
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main').stdout.strip(),staged=[],
        trackedChanges=paths('diff','--name-only'),untracked=sorted(set(paths('ls-files','--others','--exclude-standard')+[audit_file.relative_to(ROOT).as_posix()]))),
    gitWrites=False,fullRegressionThisTurn=False,CI='NOT_RUN')
with audit_file.open('x',encoding='utf8') as f:json.dump(a,f,ensure_ascii=False,indent=2)
print(json.dumps({k:a[k] for k in ('sourceUnchanged','protectedUnchanged','pendingCount','newInvestigationCount','linkCount','linkWarnings','secretPatternFindings')},ensure_ascii=False))
print('diff_check',diff.returncode,diff.stdout[:1800])
