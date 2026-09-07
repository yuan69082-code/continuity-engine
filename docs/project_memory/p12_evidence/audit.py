"""Read-only Engine audit; reports and manifests are the only writes."""
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

root=Path(__file__).resolve().parents[3]
os.chdir(root); sys.path.insert(0,str(root/'src'))
directory=Path(__file__).resolve().parent
label=sys.argv[1]
if not re.fullmatch('[a-z0-9-]+',label): raise ValueError('label')
out=directory/(label+'.json')
if out.exists(): raise FileExistsError(out)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    r=subprocess.run(['git',*args],capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    return r.returncode,r.stdout.decode('utf-8').strip(),r.stderr.decode('utf-8').strip()
before=json.loads((directory/'before.json').read_text(encoding='utf-8'))
protected={p:sha(root/p) for p in before['protected']}
source={str(p.relative_to(root)).replace('\\','/'):sha(p) for folder in ('src','tests')
        for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
stable=json.loads((directory/'p12-final-code.tests.json').read_text(encoding='utf-8'))
protected_drift=[p for p,h in protected.items() if h!=before['protected'][p]]
source_drift=[p for p in set(stable['sourceTest'])|set(source) if stable['sourceTest'].get(p)!=source.get(p)]
old_tests_drift=[p for p,h in before['sourceTest'].items() if p.startswith('tests/') and source.get(p)!=h]
plans=json.loads((directory/'planning-source.json').read_text(encoding='utf-8'))
plan_drift=[p['source'] for p in plans.values() if sha(p['source'])!=p['sha256']]
from continuity_engine.testing.persistence import tree_inventory_hash
formal_hash=tree_inventory_hash(root/'.continuity-data')
formal={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in (root/'.continuity-data').rglob('*') if p.is_file()}
ast_errors=[]
for p in source:
    if p.endswith('.py'):
        try: ast.parse((root/p).read_text(encoding='utf-8-sig'),filename=p)
        except (SyntaxError,UnicodeError) as e: ast_errors.append([p,str(e)])
tracked=git('diff','--name-only','-z')[1].split('\0')
untracked=git('ls-files','--others','--exclude-standard','-z')[1].split('\0')
tracked=[x for x in tracked if x]; untracked=[x for x in untracked if x]
p10={p:sha(p) for p in untracked if p in before['p10Untracked']}
phase=[*tracked,*[p for p in untracked if p not in before['p10Untracked']]]
old_evidence_drift=[p for p,h in before['trackedFiles'].items()
                    if '_evidence/' in p and sha(p)!=h]
allowed_source={'src/continuity_engine/'+x for x in (
    'domain/memory.py','domain/memory_lifecycle.py','services/memory_lifecycle_service.py',
    'services/memory_consolidation_service.py','services/memory_service.py','services/context_router_service.py',
    'services/context_material_resolvers.py','services/learning_service.py','services/continuity_core_service.py',
    'services/continuity_core_runtime.py','storage/json_memory_repository.py','storage/json_learning_repository.py',
    'storage/base.py','testing/p12_memory_fixture.py')}
allowed_tests={'tests/test_p12_memory_lifecycle.py','tests/test_p12_memory_integration.py'}
allowed_docs={'README.md',*{'docs/project_memory/'+x for x in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
    '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md','59_P12_IntentionalForgetting架构边界.md',
    '60_P12_规划施工测试验收矩阵.md','61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md')}}
scope_errors=[p for p in phase if p not in allowed_source|allowed_tests|allowed_docs and not p.startswith('docs/project_memory/p12_evidence/')]
markdown=[root/'README.md',*sorted((root/'docs/project_memory').glob('*.md'))]
links=[]; broken=[]
for p in markdown:
    text=p.read_text(encoding='utf-8')
    for target in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^\n]+?)\)',text):
        target=unquote(target.strip().strip('<>')).split('#',1)[0]
        if not target or re.match(r'^(?:https?|mailto|app|codex|data):',target): continue
        target=target.replace('\\_','_').replace('\\ ',' ')
        resolved=(p.parent/target).resolve()
        links.append((str(p.relative_to(root)),target))
        # This report is written after the read-only checks complete; its own
        # linked output is the only path allowed to be pending during the scan.
        if not resolved.exists() and resolved != out.resolve(): broken.append((str(p.relative_to(root)),target))
secret_pattern=re.compile(rb'(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
sensitive=[p for p in phase if secret_pattern.search((root/p).read_bytes())]
cache=[str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*.pyc') if '.git' not in p.parts]
cutoff=datetime.fromisoformat(before['capturedAt']).timestamp()
new_cache=[p for p in cache if (root/p).stat().st_mtime>cutoff]
diff=git('diff','--check')
full_path=directory/'full-final.tests.json'
full=json.loads(full_path.read_text(encoding='utf-8')) if full_path.exists() else {}
complete=full.get('status')=='FINISHED'
test_ids=full.get('testIdentities',stable['testIdentities'])
retained=set(before['testIdentities']).issubset(test_ids)
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
report={'capturedAt':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD')[1],
    'branch':git('branch','--show-current')[1],'originMain':git('rev-parse','origin/main')[1],
    'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main')[1],
    'staged':git('diff','--cached','--name-only')[1],'trackedChanges':tracked,'newP12Files':[p for p in untracked if p not in p10],
    'p10Untracked':p10,'otherScopeErrors':scope_errors,'protected':protected,'protectedDrift':protected_drift,
    'sourceTest':source,'sourceSinceFinalTargetDrift':source_drift,'originalTestFilesDrift':old_tests_drift,
    'originalEvidenceDrift':old_evidence_drift,'originalTestIdentityCount':len(before['testIdentities']),
    'retainedOriginalTests':retained,'currentTestIdentityCount':len(test_ids),'addedTestIdentities':sorted(set(test_ids)-set(before['testIdentities'])),
    'formalFiles':formal,'formalTreeHash':formal_hash,'formalDrift':formal!=before['formalFiles'],
    'planDrift':plan_drift,'version':version,'astFiles':sum(p.endswith('.py') for p in source),'astErrors':ast_errors,
    'markdownFiles':len(markdown),'localLinks':len(links),'brokenLinks':broken,'sensitiveMatches':sensitive,
    'cacheFilesObserved':cache,'cacheFilesNewSinceBaseline':new_cache,
    'diffCheck':{'exitCode':diff[0],'stdout':diff[1],'stderr':diff[2]},
    'fullFinished':complete,'fullSourceMatches':full.get('sourceTest')==source if complete else None,
    'fullResult':{k:full.get(k) for k in ('run','passed','skips','failures','errors','seconds')} if complete else 'RUNNING',
    'engineActionsWorkflows':sorted(str(x.relative_to(root)) for x in (root/'.github/workflows').glob('*')),
    'gitWriteOperationsExecuted':False}
errors=protected_drift or source_drift or old_tests_drift or old_evidence_drift or scope_errors or ast_errors or broken or sensitive or new_cache or plan_drift
report['status']='FAIL' if (errors or report['formalDrift'] or diff[0] or report['staged'] or not retained or version!='0.1.0'
    or p10!=before['p10Untracked'] or report['head']!=before['head'] or (complete and (full.get('errors') or full.get('failures') or full['sourceTest']!=source))) else 'PASS'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('status','astFiles','astErrors','markdownFiles','localLinks','brokenLinks',
    'sensitiveMatches','protectedDrift','sourceSinceFinalTargetDrift','formalTreeHash','planDrift','fullFinished','otherScopeErrors')},ensure_ascii=False))
raise SystemExit(0 if report['status']=='PASS' else 1)
