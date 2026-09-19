"""Snapshot the investigation pause for the required shared-code approval."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf8',capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def paths(*args):return git(*args).stdout.splitlines()

b=read(OUT/'before.json');source=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
allowed_docs=['docs/project_memory/'+p for p in ['01_当前状态.md','03_施工日志.md','84_P18_规划施工测试验收矩阵.md','86_P18_测试索引与验收入口.md']]
assert source==b['sourceTest']
assert all(sha(ROOT/p)==h for p,h in b['existingPending'].items() if p not in allowed_docs)
excluded_hashes={**b['protected']['excludedP10'],**b['protected']['otherPreserved']}
assert set(excluded_hashes)==set(b['excluded'])
assert all(sha(ROOT/p)==h for p,h in excluded_hashes.items())
assert all(sha(ROOT/p)==h for group in b['protected'].values() for p,h in group.items())
assert all(sha(ROOT/p)==h for p,h in b['historicalOriginals'].items())
assert not paths('diff','--cached','--name-only')
assert git('branch','--show-current').stdout.strip()=='main'
assert git('rev-parse','HEAD').stdout.strip()==b['head']==git('rev-parse','origin/main').stdout.strip()

labels=['hypotheses-before-01','f1-classification-before-01','h1-original-process-before-01',
        'h1-original-process-before-02','f1-original-process-before-01','original-process-controls-01',
        'h1-original-process-before-03','f1-original-process-before-02']
results={}
for label in labels:
    r=read(OUT/(label+'.json'));assert r['status']=='FINISHED' and r['sourceBefore']==source==r['sourceAfter']
    results[label]={k:r[k] for k in ('run','passed','seconds','exitCode','status')}
    results[label].update(failures=len(r['failures']),errors=len(r['errors']),skips=len(r['skips']))
    results[label]['hashes']={s:sha(OUT/(label+s)) for s in ('.json','.stdout.log','.stderr.log')}

processes=[]
for label in labels:
    for line in (OUT/(label+'.stdout.log')).read_text(encoding='utf8').splitlines():
        if not line.startswith('{'):continue
        row=json.loads(line)
        for p in row.get('processEvidence',[]):
            if p.get('stage')=='continuous-child':processes.append(dict(label=label,pid=p['pid'],exitCode=p['exitCode'],forcedCleanup=p['forcedCleanup']))
        if 'childrenReaped' in row:assert row['childrenReaped'] is True
        if 'readerReaped' in row:assert row['readerReaped'] is True
assert all(not p['forcedCleanup'] for p in processes)

for p in (ROOT/'src').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
for p in (ROOT/'tests').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
for p in OUT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))

suffix=('-'+sys.argv[1]) if len(sys.argv)>1 else ''
pending_path=OUT/('pending-files'+suffix+'.md');audit_path=OUT/('audit'+suffix+'.json')
assert not pending_path.exists() and not audit_path.exists()
all_changes=sorted(set(paths('diff','--name-only')+paths('ls-files','--others','--exclude-standard')+
                      [p.relative_to(ROOT).as_posix() for p in (pending_path,audit_path)]))
pending=[p for p in all_changes if p not in b['excluded']]
new=[p for p in pending if p not in b['existingPending']]
assert all(p.startswith('docs/project_memory/p18_f1_h1_evidence/') for p in new)
lines=['# P18未提交成果精确清单（调查暂停待公共实现修改确认）','',
       f'共{len(pending)}项P18成果；其中原{len(b["existingPending"])}项保留，本轮新增{len(new)}项调查材料；另有32项排除。没有暂存或提交。',
       '本轮只修改4份导航/日志档案，其余既有成果逐文件hash不变；src/tests仍267文件、1480原身份。audit.json因自引用不在自身hash映射中，路径仍明确列入清单。','',
       '## 本轮修改的既有档案','']
lines += ['- '+p for p in allowed_docs]
lines += ['','## 本轮新增调查材料','']+['- '+p for p in new]
lines += ['','## 完整P18待提交路径（未执行Git写）','']+['- '+p for p in pending]
lines += ['','## 原32项排除（未改动）','']+['- '+p+' — '+h for p,h in excluded_hashes.items()]
pending_path.write_text('\n'.join(lines)+'\n',encoding='utf8')

links=[];bad=[]
for p in [ROOT/n for n in allowed_docs]+list(OUT.rglob('*.md')):
    for dest in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        if dest.startswith(('http:','https:','#','app:')):continue
        target=dest.split('#')[0].strip('<>')
        if not target:continue
        q=(p.parent/target).resolve()
        # Future audit is being written below; it is explicitly in the manifest.
        if not q.exists() and q!=audit_path.resolve():bad.append(dict(file=str(p.relative_to(ROOT)),target=target))
        links.append(dict(file=str(p.relative_to(ROOT)),target=target))

diff=git('diff','--check')
secret_findings=[]
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix in {'.md','.json','.log','.py'}:
        data=p.read_text(encoding='utf-8-sig')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}',data):
            secret_findings.append(p.relative_to(ROOT).as_posix())
report=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='P18',status='IMPLEMENTED_NOT_ACCEPTED',
    evidenceConflict='PRESENT',approval='WAITING_FOR_SHARED_IMPLEMENTATION_CHANGE_CONFIRMATION',
    sourceHash=b['sourceHash'],sourceTest=source,formalTestIdentityCount=len(b['testIdentities']),
    sourceUnchanged=True,originalPendingUnchangedExcept=allowed_docs,originalPendingCount=len(b['existingPending']),
    protectedGroups={k:len(v) for k,v in b['protected'].items()},protectedUnchanged=True,
    formalTreeHash=b['formalTreeHash'],pyprojectHash=b['pyproject'],excluded=b['excluded'],
    historyUnchanged=True,results=results,processes=processes,processObservation=read(OUT/'process-observation.json'),
    pythonAST='PASS',linkCount=len(links),linkWarnings=bad,secretPatternFindings=secret_findings,
    secretScanLimit='Narrow private-key/API-key patterns; TEST-only diagnostics contain identities and structured state, not input bodies.',
    diffCheck=dict(exitCode=diff.returncode,stdout=diff.stdout,stderr=diff.stderr),
    git=dict(head=b['head'],localOrigin=git('rev-parse','origin/main').stdout.strip(),branch='main',
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main').stdout.strip(),
        staged=[],trackedChanges=paths('diff','--name-only'),untracked=sorted(set(paths('ls-files','--others','--exclude-standard')+[audit_path.relative_to(ROOT).as_posix()])),
        status=git('status','--short','--untracked-files=all').stdout),
    pendingCount=len(pending),newInvestigationCount=len(new),
    pendingHashes={p:sha(ROOT/p) for p in pending if ROOT/p!=audit_path},
    gitWrites=False,fullRegressionThisTurn=False,CI='NOT_RUN',formalDataWrites=False)
with audit_path.open('x',encoding='utf8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print(json.dumps({k:report[k] for k in ('sourceHash','sourceUnchanged','protectedGroups','protectedUnchanged','pendingCount','newInvestigationCount','linkCount','linkWarnings')},ensure_ascii=False))
print('diff_check',diff.returncode,diff.stdout[:2000])
