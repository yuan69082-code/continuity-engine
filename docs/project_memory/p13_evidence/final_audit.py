"""Read-only closing checks and a precise unstaged P12/P13 change manifest."""
from datetime import datetime,timezone
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(root/'src'))
from continuity_engine.testing.persistence import tree_inventory_hash

label=sys.argv[1]
if re.fullmatch(r'[a-z0-9-]+',label) is None:raise ValueError('safe fresh audit label required')
output=directory/(label+'.audit.json')
manifest=directory/(label+'.pending-files.md')
if output.exists():raise FileExistsError(output)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):
    p=subprocess.run(['git','-c','core.quotepath=false',*args],cwd=root,capture_output=True,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8'))
    return p.stdout.decode('utf-8').strip()
before=json.loads((directory/'before.json').read_text(encoding='utf-8'))
full=json.loads((directory/'full-final.tests.json').read_text(encoding='utf-8'))
targeted=json.loads((directory/'p13-stable-final.tests.json').read_text(encoding='utf-8'))
protected={p:sha(root/p) for p in before['protected']}
assert protected==before['protected'],'protected drift'
plans={p:sha(p) for p in before['planningSources']}
assert plans==before['planningSources'],'planning source drift'
formal={p:sha(root/p) for p in before['formalFiles']}
assert formal==before['formalFiles']
assert tree_inventory_hash(root/'.continuity-data')==before['formalTreeHash']
source={str(p.relative_to(root)).replace('\\','/'):sha(p) for folder in ('src','tests')
    for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert full['status']=='FINISHED' and full['sourceTest']==source,'full identity drift or incomplete'
assert not full['errors'] and not full['failures'],'unresolved full failure'
assert len(set(full['testIdentities']))==len(full['testIdentities'])
assert set(before['testIdentities'])<=set(full['testIdentities'])
assert set(targeted['testIdentities'])<=set(full['testIdentities'])
assert set(full['testIdentities'])-set(before['testIdentities'])==set(targeted['testIdentities'])
assert all(source[p]==h for p,h in before['sourceTest'].items() if p.startswith('tests/')),'old test changed'
assert full['skips']==before['citedFullResult']['skips'],'new skip or old skip altered'
assert git('branch','--show-current')=='main'
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==before['head']
assert not git('diff','--cached','--name-only')
tracked=git('diff','--name-only','-z').split('\0')
untracked=git('ls-files','--others','--exclude-standard','-z').split('\0')
tracked=[p for p in tracked if p];untracked=[p for p in untracked if p]
excluded=before['p10Untracked'];assert set(excluded)<=set(untracked)
pending=sorted((set(tracked)|set(untracked))-set(excluded))
allowed_source={
 'src/continuity_engine/domain/expression.py','src/continuity_engine/domain/thinking.py',
 'src/continuity_engine/domain/continuity_core.py','src/continuity_engine/domain/integration_results.py',
 'src/continuity_engine/services/expression_policy_service.py','src/continuity_engine/services/expression_ports.py',
 'src/continuity_engine/services/continuity_core_service.py','src/continuity_engine/services/continuity_interaction_service.py',
 'src/continuity_engine/testing/p13_expression_fixture.py','tests/test_p13_expression_policy.py',
 'tests/test_p13_expression_recovery.py'}
actual_source={p for p in pending if p.startswith(('src/','tests/'))}
assert actual_source==allowed_source
allowed_docs={'README.md'}|{'docs/project_memory/'+name for name in (
 '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
 '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md',
 '10_档案修订记录.md','11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md',
 '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md',
 '59_P12_IntentionalForgetting架构边界.md','60_P12_规划施工测试验收矩阵.md',
 '61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md',
 'P12_用户正式验收_20260908.md','63_P13_ExpressionPolicy架构边界.md',
 '64_P13_规划施工测试验收矩阵.md','65_P13_表达绑定持久化与恢复语义.md',
 '66_P13_测试索引与验收入口.md')}
assert all(p in actual_source or p in allowed_docs or p.startswith('docs/project_memory/p13_evidence/') for p in pending)
assert not git('ls-files','.github/workflows')
legacy_drift=[]
for path,h in before['workspaceFiles'].items():
    if path not in pending and sha(root/path)!=h:legacy_drift.append(path)
assert not legacy_drift,legacy_drift
workspace_files={str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*')
    if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc'}
unexpected_new=sorted(workspace_files-set(before['workspaceFiles'])-set(pending))
assert not unexpected_new,unexpected_new
observed_caches=[str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*.pyc') if '.git' not in p.parts]
parsed=[]
for relative in list(source)+[p for p in pending if p.startswith('docs/') and p.endswith('.py')]:
    p=root/relative
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'),filename=relative);parsed.append(relative)
links=[];broken=[]
for relative in [p for p in pending if p.endswith('.md')]:
    p=root/relative;text=p.read_text(encoding='utf-8')
    text=re.sub(r'```.*?```','',text,flags=re.S)
    for m in re.finditer(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
        target=unquote(m.group(1).strip().strip('<>')).split('#')[0]
        if not target or re.match(r'^(https?://|mailto:|codex:)',target):continue
        resolved=Path(target) if Path(target).is_absolute() else p.parent/target
        row={'file':relative,'target':target}
        links.append(row)
        if not resolved.exists() and resolved.resolve() not in {output.resolve(),manifest.resolve()}:broken.append(row)
assert not broken,broken
secrets=[];whitespace=[]
patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
          r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bsk-[A-Za-z0-9]{30,}',r'\bAKIA[A-Z0-9]{16}\b']
for relative in pending:
    p=root/relative
    assert p.suffix not in {'.pyc','.whl','.zip','.exe','.dll'} and '__pycache__' not in p.parts
    text=p.read_text(encoding='utf-8-sig')
    if any(re.search(pattern,text) for pattern in patterns):secrets.append(relative)
    for n,line in enumerate(text.splitlines(),1):
        if line.rstrip(' \t')!=line:whitespace.append({'file':relative,'line':n,'rawEvidence':p.suffix=='.log'})
assert not secrets,secrets
assert all(x['rawEvidence'] for x in whitespace),'non-evidence formatting issue'
assert git('diff','--check')==''
categories={'P13_source_tests':sorted(actual_source),
 'P12_acceptance_specific':[], 'P12_P13_shared_navigation':[], 'P13_documents':[], 'P13_evidence':[]}
for p in pending:
    if p in actual_source:continue
    if p.startswith('docs/project_memory/p13_evidence/'):category='P13_evidence'
    elif Path(p).name.startswith(('63_','64_','65_','66_')):category='P13_documents'
    elif Path(p).name.startswith(('59_','60_','61_','62_','P12_用户正式验收')):category='P12_acceptance_specific'
    else:category='P12_P13_shared_navigation'
    categories[category].append(p)
for matrix,status in [('60_P12_规划施工测试验收矩阵.md','ACCEPTED'),('64_P13_规划施工测试验收矩阵.md','IMPLEMENTED_NOT_ACCEPTED')]:
    lines=(root/'docs/project_memory'/matrix).read_text(encoding='utf-8').splitlines()
    rows=[x for x in lines if re.match(r'^\| P(?:12|13)-\d\d \|',x) and x.endswith('| '+status+' |')]
    assert len(rows)==12,(matrix,len(rows))
decisions=(root/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8')
assert decisions.count('## D-061：')==1 and decisions.count('## D-062：')==1
record={'at':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD'),'branch':'main',
 'originMainLocal':git('rev-parse','origin/main'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
 'networkChecksThisTurn':False,'gitWrites':False,'actionsWorkflows':[],
 'sourceTest':source,'protected':protected,'plans':plans,'formalFiles':formal,'formalTreeHash':before['formalTreeHash'],
 'originalTestsPreserved':len(before['testIdentities']),'newTests':len(targeted['testIdentities']),
 'full':{k:full[k] for k in ('run','passed','skips','errors','failures','seconds')},
 'AST':len(parsed),'checkedLocalLinks':len(links),'brokenLinks':broken,'secretMatches':secrets,
 'unexpectedNewWorkspaceFiles':unexpected_new,'observedBytecodePreserved':observed_caches,
 'legacyDrift':legacy_drift,'rawWhitespacePreserved':whitespace,'diffCheck':'PASS',
 'tracked':tracked,'staged':[],'untracked':untracked,'excludedP10':excluded,
 'pendingBeforeAuditFiles':pending,'categories':categories,
 'contentHashes':{p:sha(root/p) for p in pending},'auditSelfNotHashed':True}
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# P12 验收档案与 P13 未提交清单','','此清单不构成 Git 授权。当前无暂存、提交或推送。','']
for category,paths in categories.items():
    lines+=['## '+category+' ('+str(len(paths))+')','']+[f'- `{p}`' for p in paths]+['']
lines+=['## 本次审计自身新增','','- `'+str(output.relative_to(root)).replace('\\','/')+'`',
        '- `'+str(manifest.relative_to(root)).replace('\\','/')+'`','','## 原样排除 P10 辅助脚本（31）','']
lines += [f'- `{p}`' for p in excluded]
manifest.write_text('\n'.join(lines)+'\n',encoding='utf-8')
assert output.exists() and manifest.exists()
print(json.dumps({k:v for k,v in record.items() if k in ('head','originalTestsPreserved','newTests','full','AST','checkedLocalLinks','formalTreeHash','diffCheck')},ensure_ascii=False))
print('Pending files including audit pair:',len(pending)+2,'; excluded P10:',len(excluded))
