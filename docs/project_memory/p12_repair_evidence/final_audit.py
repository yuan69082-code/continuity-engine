"""Read-only repair audit and exact pending manifest. No Git write operations."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import unquote

root=Path(__file__).resolve().parents[3]; directory=Path(__file__).resolve().parent
os.chdir(root); sys.path.insert(0,str(root/'src'))
out=directory/'final-audit.json'
if out.exists(): raise FileExistsError(out)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    p=subprocess.run(['git',*args],capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    return {'exitCode':p.returncode,'stdout':p.stdout.decode('utf-8').strip(),'stderr':p.stderr.decode('utf-8').strip()}
def gitpaths(*args):
    result=git(*args); assert result['exitCode']==0
    return [x for x in result['stdout'].split('\0') if x]
before=json.loads((directory/'before.json').read_text(encoding='utf-8'))
initial=json.loads((root/'docs/project_memory/p12_evidence/final-audit.json').read_text(encoding='utf-8'))
special=json.loads((directory/'p12-stable-02.tests.json').read_text(encoding='utf-8'))
compat=json.loads((directory/'compatibility-affected-02.tests.json').read_text(encoding='utf-8'))
full=json.loads((directory/'full-stable-02.tests.json').read_text(encoding='utf-8'))
probe_run=json.loads((directory/'original-probes-final-02.json').read_text(encoding='utf-8'))
original=json.loads((root/'docs/project_memory/p12_evidence/full-final.tests.json').read_text(encoding='utf-8'))
source={str(p.relative_to(root)).replace('\\','/'):sha(p) for folder in ('src','tests')
        for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
runtime={'src/continuity_engine/'+x for x in ('domain/memory.py','services/memory_lifecycle_service.py',
    'services/memory_consolidation_service.py','storage/json_memory_repository.py','services/context_router_service.py')}
test_path='tests/test_p12_memory_review_regressions.py'
test_paths={test_path,'tests/test_p12_memory_weight_windows.py'}
docs={'README.md',*{'docs/project_memory/'+x for x in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md','05_已完成模块.md',
    '05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md','13_P00_档案与测试索引.md',
    'CHANGELOG.md','工程总档案.md','59_P12_IntentionalForgetting架构边界.md','60_P12_规划施工测试验收矩阵.md',
    '61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md','P12_独立复核返修_R1-R5.md')}}
drift=[p for p,h in before['workspaceFiles'].items() if not (root/p).is_file() or sha(root/p)!=h]
unexpected_drift=sorted(set(drift)-runtime-docs)
protected={p:sha(root/p) for p in before['protected']}
review={p:sha(p) for p in before['reviewSources']}
plans=json.loads((root/'docs/project_memory/p12_evidence/planning-source.json').read_text(encoding='utf-8'))
plan_drift=[p['source'] for p in plans.values() if sha(p['source'])!=p['sha256']]
from continuity_engine.testing.persistence import tree_inventory_hash
formal_hash=tree_inventory_hash(root/'.continuity-data')
formal={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in (root/'.continuity-data').rglob('*') if p.is_file()}
tracked=gitpaths('diff','--name-only','-z'); untracked=gitpaths('ls-files','--others','--exclude-standard','-z')
excluded=initial['p10Untracked']; owned=sorted((set(tracked+untracked)-set(excluded))|{
    'docs/project_memory/p12_repair_evidence/'+x for x in ('final-audit.json','pending-files.json','pending-files.md')})
repair_new=[p for p in untracked if p not in before['untracked']]
new_scope_errors=[p for p in repair_new if p not in test_paths and p not in docs and not p.startswith('docs/project_memory/p12_repair_evidence/')]
categories={
    '全 P12 源码和测试':[p for p in owned if p.startswith(('src/','tests/'))],
    '全 P12 档案和导航':[p for p in owned if p=='README.md' or (p.endswith('.md') and '_evidence/' not in p)],
    'P12 及返修证据与本地辅助':[p for p in owned if '_evidence/' in p],
}
assert set().union(*map(set,categories.values()))==set(owned)
manifest={'head':git('rev-parse','HEAD')['stdout'],'branch':git('branch','--show-current')['stdout'],
    'originMain':git('rev-parse','origin/main')['stdout'],'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main')['stdout'],
    'staged':git('diff','--cached','--name-only')['stdout'],'trackedChanges':tracked,
    'allP12Paths':owned,'categories':categories,'repairChangedExisting':drift,
    'repairAddedFiles':sorted(set(repair_new)|{str(out.relative_to(root)).replace('\\','/'),
        'docs/project_memory/p12_repair_evidence/pending-files.json','docs/project_memory/p12_repair_evidence/pending-files.md'}),
    'excludedP10':excluded,'gitWrites':False}
(directory/'pending-files.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# P12 返修终局精确工作区清单','','只供独立复核，不构成暂存/提交授权。本轮没有 Git 写操作。',
    f"main / HEAD / 本地 origin/main：`{manifest['head']}`，ahead/behind 0/0，暂存区为空。",
    f"整个未提交 P12 工作区共 {len(owned)} 个路径；分类："+'；'.join(k+' '+str(len(v)) for k,v in categories.items())+'。',
    '初版 pending-files.md/json 保留历史；本清单覆盖初版及返修成果。31 个原有 P10 脚本原样排除，逐文件 hash 见 JSON。',
    '本轮只修改五份运行文件，新增两份正式测试；原测试和原始证据不改。证据与辅助脚本须在未来提交授权时逐项判断，不能无差别暂存。','']
for name,paths in categories.items():
    lines+=['## '+name,'']+['- `'+p+'`' for p in paths]+['']
lines+=['## 本轮相对返修基线实际修改的已有文件','']+['- `'+p+'`' for p in drift]+['']
lines+=['## 原 31 个 P10 排除项（hash 原样保留）','']+['- `'+p+'` — sha256:'+h for p,h in sorted(excluded.items())]+['']
(directory/'pending-files.md').write_text('\n'.join(lines),encoding='utf-8')
markdown=[root/'README.md',*sorted((root/'docs/project_memory').glob('*.md'))]
links=[]; broken=[]
for p in markdown:
    text=p.read_text(encoding='utf-8')
    for target in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^\n]+?)\)',text):
        target=unquote(target.strip().strip('<>')).split('#',1)[0]
        if not target or re.match(r'^(?:https?|mailto|app|codex|data):',target): continue
        target=target.replace('\\_','_').replace('\\ ',' '); resolved=(p.parent/target).resolve()
        links.append([str(p.relative_to(root)),target])
        if not resolved.exists() and resolved!=out.resolve(): broken.append(links[-1])
ast_errors=[]
for p in source:
    if p.endswith('.py'):
        try: ast.parse((root/p).read_text(encoding='utf-8-sig'),filename=p)
        except (SyntaxError,UnicodeError) as e: ast_errors.append([p,str(e)])
probe=next(Path(p) for p in review if p.endswith('/review_probes.py') or p.endswith('\\review_probes.py'))
def original_class(path):
    return next(x for x in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(x,ast.ClassDef) and x.name=='P12IndependentProbes')
probe_preserved=ast.dump(original_class(probe))==ast.dump(original_class(root/test_path))
pattern=re.compile(rb'(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
sensitive=[p for p in owned if (root/p).is_file() and pattern.search((root/p).read_bytes())]
new_cache=[str(p.relative_to(root)) for p in root.rglob('*.pyc') if '.git' not in p.parts
    and p.stat().st_mtime>datetime.fromisoformat(before['capturedAt']).timestamp()]
source_matches=source==special['sourceTest']==compat['sourceTest']==full['sourceTest']==probe_run['sourceTest']
completed=(all(r['status']=='FINISHED' and not r['errors'] and not r['failures'] for r in (special,compat,full))
    and probe_run['exitCode']==0 and not probe_run['interrupted'])
retained=set(original['testIdentities']).issubset(full['testIdentities'])
state_errors=[]
for p in docs-{'docs/project_memory/P12_独立复核返修_R1-R5.md'}:
    text=(root/p).read_text(encoding='utf-8'); block=text.split('<!-- P12_REPAIR_CURRENT_START -->')[-1].split('<!-- P12_REPAIR_CURRENT_END -->')[0]
    if not all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','EVIDENCE_CONFLICT=PRESENT','P13—P23 NOT_STARTED')): state_errors.append(p)
diff=git('diff','--check'); version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
report={'capturedAt':datetime.now(timezone.utc).isoformat(),'git':manifest,'sourceTest':source,
    'allStableSourceMatches':source_matches,'originalTestsRetained':retained,'originalIdentityCount':len(original['testIdentities']),
    'currentIdentityCount':len(full['testIdentities']),'allExpectedRunsCompleted':completed,
    'protected':protected,'protectedDrift':protected!=before['protected'],'formalFiles':formal,'formalTreeHash':formal_hash,
    'formalDrift':formal!=initial['formalFiles'],'reviewSourceDrift':review!=before['reviewSources'],'originalProbeAssertionsPreserved':probe_preserved,
    'planDrift':plan_drift,'unexpectedExistingDrift':unexpected_drift,'newScopeErrors':new_scope_errors,
    'version':version,'pythonAstFiles':sum(p.endswith('.py') for p in source),'astErrors':ast_errors,
    'markdownFiles':len(markdown),'localLinks':len(links),'brokenLinks':broken,'sensitiveMatches':sensitive,
    'newCacheFiles':new_cache,'stateErrors':state_errors,'diffCheck':diff,
    'engineActionsWorkflows':sorted(str(p.relative_to(root)) for p in (root/'.github/workflows').glob('*')),
    'reportCreatedAfterGitSnapshot':str(out.relative_to(root)),
    'evidenceConflict':'PRESENT: independent review closure pending','planningConflict':'NONE'}
errors=(not source_matches or not completed or not retained or not probe_preserved or protected!=before['protected']
    or formal!=initial['formalFiles'] or review!=before['reviewSources'] or plan_drift or unexpected_drift or new_scope_errors
    or ast_errors or broken or sensitive or new_cache or state_errors or diff['exitCode'] or version!='0.1.0'
    or manifest['staged'] or manifest['head']!=before['head'] or manifest['originMain']!=before['originMain']
    or not set(excluded).issubset(untracked))
report['status']='FAIL' if errors else 'PASS'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('status','allStableSourceMatches','originalTestsRetained','currentIdentityCount',
    'protectedDrift','formalTreeHash','reviewSourceDrift','originalProbeAssertionsPreserved','unexpectedExistingDrift',
    'newScopeErrors','pythonAstFiles','markdownFiles','localLinks','brokenLinks','sensitiveMatches','stateErrors')},ensure_ascii=False))
print(json.dumps({'owned':len(owned),'tracked':len(tracked),'newP12':len(owned)-len(tracked),'excludedP10':len(excluded),
    'categories':{k:len(v) for k,v in categories.items()}},ensure_ascii=False))
raise SystemExit(1 if errors else 0)
