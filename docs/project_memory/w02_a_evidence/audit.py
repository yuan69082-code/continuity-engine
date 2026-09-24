"""Read-only repository audit; writes only W02 evidence, never runs tests/Git writes."""
import ast
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PREFIX = HERE.relative_to(ROOT).as_posix() + '/'
os.chdir(ROOT)
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], encoding='utf-8')


def write(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def current_source():
    return {p.relative_to(ROOT).as_posix(): digest(p)
            for folder in ('src', 'tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


RUNTIME = [
    'src/continuity_engine/domain/continuity_core.py',
    'src/continuity_engine/domain/integration_results.py',
    'src/continuity_engine/services/continuity_core_runtime.py',
    'src/continuity_engine/services/continuity_core_service.py',
    'src/continuity_engine/services/continuity_interaction_service.py',
    'src/continuity_engine/storage/json_integration_repository.py',
]
NEW_SOURCE = [
    'src/continuity_engine/domain/input_processing.py',
    'src/continuity_engine/services/input_processing_service.py',
    'src/continuity_engine/services/input_context_source.py',
    'src/continuity_engine/testing/w02_input_fixture.py',
    'tests/test_w02_input_processing.py', 'tests/test_w02_input_recovery.py',
    'tests/test_w02_input_integration.py',
]
DOCS = ['README.md'] + ['docs/project_memory/'+p for p in (
    '01_当前状态.md', '03_施工日志.md', '04_决策记录.md', '06_未完成事项.md',
    'CHANGELOG.md', '工程总档案.md')]
SELF_OUTPUTS = [PREFIX+p for p in ('final.audit.json', 'final.pending-files.md', 'final.inventory.json')]


def main():
    baseline = read('baseline.json')
    frozen = read('frozen-source-03.json')['source']
    selected = read('selected-runs.json')
    src = current_source()
    errors = []
    if src != frozen:
        errors.append('SOURCE_CHANGED_FROM_FROZEN')
    runs = {}
    for group in ('special', 'compatibility', 'full'):
        label = selected.get(group)
        if not label:
            raise RuntimeError('FINAL_RESULT_MISSING:'+group)
        run = read(label+'.json')
        valid = run.get('status') == 'FINISHED' and run.get('exitCode') == 0 and not run.get('loaderErrors')
        identity = run.get('sourceBefore') == src == run.get('sourceAfter')
        if not valid or not identity:
            errors.append('RUN_NOT_VALID:'+label)
        runs[group] = dict(label=label, valid=valid, sourceMatches=identity,
            run=run.get('run'), passed=run.get('passed'), seconds=run.get('seconds'),
            failures=len(run.get('failures', [])), errors=len(run.get('errors', [])), skips=run.get('skips'),
            exitCode=run.get('exitCode'), command=run.get('command'))
    full = read(selected['full']+'.json')
    normalize = lambda s: s.removeprefix('tests.')
    old_ids = Counter(map(normalize, baseline['testIdentities']))
    now_ids = Counter(map(normalize, full['testIdentities']))
    removed = list((old_ids-now_ids).elements())
    added = list((now_ids-old_ids).elements())
    if removed or any(not i.startswith('test_w02_input_') for i in added):
        errors.append('TEST_IDENTITIES_CHANGED_OUTSIDE_W02')
    protected = {}
    for group, paths in baseline['protected'].items():
        protected[group] = {p: {'expected': h, 'actual': digest(p), 'equal': h == digest(p)}
                            for p, h in paths.items()}
        if not all(x['equal'] for x in protected[group].values()):
            errors.append('PROTECTION_CHANGED:'+group)
    old_untracked = baseline['existingUntracked']
    preserved = {p: {'sha256': digest(p), 'equal': h == digest(p)} for p,h in old_untracked.items()}
    if not all(x['equal'] for x in preserved.values()):
        errors.append('EXISTING_UNTRACKED_CHANGED')
    current_plans = []
    plan_index = ROOT/'docs/project_memory/w01_planning_v15_20260923/planning-sources.json'
    for entry in json.loads(plan_index.read_text(encoding='utf-8')):
        original = Path(entry['original'])
        expected = entry['sha256'].removeprefix('sha256:')
        actual = digest(original)
        current_plans.append(dict(path=str(original), expected=expected, actual=actual, equal=expected==actual))
    if not all(p['equal'] for p in current_plans):
        errors.append('CURRENT_PLAN_SOURCE_CHANGED')
    formal = [{'relativePath':p.relative_to(ROOT/'.continuity-data').as_posix(), 'fileHash':'sha256:'+digest(p)}
              for p in sorted((ROOT/'.continuity-data').rglob('*')) if p.is_file()]
    formal_hash = 'sha256:'+hashlib.sha256(json.dumps(formal,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if formal_hash != baseline['formalTreeHash']:
        errors.append('FORMAL_DATA_CHANGED')
    source_changes = [p for p,h in baseline['source'].items() if src.get(p) != h]
    if set(source_changes)-set(RUNTIME):
        errors.append('UNAUTHORIZED_EXISTING_SOURCE_CHANGE')
    status = git('status','--porcelain=v1','-uall')
    tracked = git('diff','--name-only','-z').split('\0')[:-1]
    untracked = git('ls-files','--others','--exclude-standard','-z').split('\0')[:-1]
    staged = git('diff','--cached','--name-only','-z').split('\0')[:-1]
    w02_new = [p for p in untracked if p not in old_untracked]
    unexpected = [p for p in tracked if p not in RUNTIME+DOCS]
    unexpected += [p for p in w02_new if p not in NEW_SOURCE and not p.startswith(PREFIX)]
    if unexpected or staged:
        errors.append('UNEXPECTED_GIT_PATHS_OR_STAGING')
    pending = sorted(set(tracked+w02_new+SELF_OUTPUTS))
    ast_errors=[]
    py = [p for p in src if p.endswith('.py')]
    for path in py:
        try: ast.parse((ROOT/path).read_text(encoding='utf-8-sig'),filename=path)
        except Exception as exc: ast_errors.append(dict(path=path,type=type(exc).__name__))
    if ast_errors: errors.append('AST_ERROR')
    links=[]; broken=[]
    # Only new document content is evaluated; historic reports are not rewritten.
    for path in pending:
        if not path.endswith('.md') or not (ROOT/path).exists(): continue
        text=(ROOT/path).read_text(encoding='utf-8')
        if path in DOCS:
            if path.endswith('04_决策记录.md'):
                text=text[text.index('## D-075：'):]
            else:
                text=text.split('<!-- PRE_P19_ACCEPTED_D074_20260920 -->')[0]
        text=re.sub(r'```.*?```','',text,flags=re.S)
        for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^\n]+?)\)',text):
            dest=match.group(1).strip().strip('<>')
            if re.match(r'^(https?://|mailto:|#)',dest):continue
            dest=unquote(dest.split('#')[0])
            target=(ROOT/path).parent/dest
            generated=any(target.resolve()==(ROOT/p).resolve() for p in SELF_OUTPUTS)
            entry=dict(file=path,target=dest,exists=target.exists(),generatedByThisAudit=generated)
            links.append(entry)
            if not entry['exists'] and not generated:broken.append(entry)
    if broken: errors.append('NEW_DOCUMENT_LINK_MISSING')
    whitespace=[]; artifact_risks=[]; secret_hits=[]
    patterns={'privateKey':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              'awsKey':r'\bAKIA[A-Z0-9]{16}\b', 'githubToken':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'}
    for path in pending:
        if path in SELF_OUTPUTS:continue
        p=ROOT/path
        if not p.is_file():continue
        if any(x in p.parts for x in ('__pycache__','node_modules','build','dist','.continuity-data')) or p.suffix in ('.pyc','.whl','.zip','.exe'):
            artifact_risks.append(path)
        content=p.read_text(encoding='utf-8',errors='replace')
        for rule,pattern in patterns.items():
            if re.search(pattern,content):secret_hits.append({'file':path,'rule':rule})
        if path.startswith(PREFIX):
            lines=[n for n,line in enumerate(content.splitlines(),1) if line.endswith((' ','\t'))]
            if lines:whitespace.append({'file':path,'lines':lines,'rawEvidence':path.endswith('.log')})
    if artifact_risks or secret_hits: errors.append('ARTIFACT_OR_SENSITIVE_REVIEW_NEEDED')
    diff = subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf-8')
    if diff.returncode: errors.append('TRACKED_DIFF_CHECK_WARNING')
    head=git('rev-parse','HEAD').strip(); index_hash=digest(ROOT/'.git/index')
    branch=git('branch','--show-current').strip()
    if head != baseline['head'] or index_hash != baseline['indexHash'] or branch != baseline['branch']:
        errors.append('GIT_BASELINE_CHANGED')
    exclusions={p:h for p,h in old_untracked.items() if '/p10_evidence/' in p or '/p14_evidence/' in p}
    inventory={p:(digest(ROOT/p) if p not in SELF_OUTPUTS else None) for p in pending}
    # The three mutually-referencing audit outputs are deliberately not self-hashed.
    write('final.inventory.json',dict(files=inventory, selfHashExcluded=SELF_OUTPUTS, exclusions=exclusions,
        preservedW01={p:h for p,h in old_untracked.items() if p not in exclusions}))
    md=['# W02-A 精确工作区清单','','仅用于独立复核；本轮不暂存、不提交、不 push。',
        f'本批 {len(pending)} 文件；原有 {len(old_untracked)} 未跟踪材料分开保留，其中 32 排除项、25 份 W01/规划材料。',
        '逐文件 SHA-256 见 [final.inventory.json](final.inventory.json)。三个互相引用的审计输出不自填循环 hash。','',
        '## 本批文件','','| 路径 | 类别 |','|---|---|']
    for p in pending:
        kind='原运行文件局部接线' if p in RUNTIME else '新增实现/Fixture/正式测试' if p in NEW_SOURCE else '直接工程档案' if p in DOCS else '本批证据/审计/报告'
        md.append(f'| `{p}` | {kind} |')
    md += ['','## 原 32 项排除材料','','全部保持原 hash，不归入 W02-A。','']+[f'- `{p}`' for p in exclusions]
    md += ['','## 原 W01 / 规划材料','','原样保留，不归入本批新增。','']+[f'- `{p}`' for p in old_untracked if p not in exclusions]
    (HERE/'final.pending-files.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    audit=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),errors=errors,
        sourceCount=len(src),sourceHash='sha256:'+hashlib.sha256(json.dumps(src,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        sourceFrozenEqual=src==frozen,sourceChanges=source_changes,sourceNew=sorted(set(src)-set(baseline['source'])),
        runs=runs,testIdentity=dict(oldCount=sum(old_ids.values()),fullCount=sum(now_ids.values()),removed=removed,added=added),
        protected=protected,currentPlanningSources=current_plans,existingUntracked=preserved,formalFiles=formal,
        formalTreeHash=formal_hash,version='0.1.0 (pyproject byte identity verified)',
        ast=dict(count=len(py),errors=ast_errors),links=dict(count=len(links),broken=broken),
        sensitiveScan=dict(rules=list(patterns),hits=secret_hits,limitation='Pattern scan plus scoped diff review, not proof of absence of every possible secret'),
        artifactRisks=artifact_risks,newWhitespaceWarnings=whitespace,diffCheck=dict(exitCode=diff.returncode,stdout=diff.stdout,stderr=diff.stderr),
        pendingCount=len(pending),pendingFiles=pending,excludedCount=len(exclusions),preservedPlanningCount=len(old_untracked)-len(exclusions),
        git=dict(branch=branch,head=head,localOrigin=git('rev-parse','origin/main').strip(),
            aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main').strip(),
            origin=git('remote','get-url','origin').strip(),indexHash=index_hash,staged=staged,
            tracked=tracked,untracked=untracked,status=status,unexpected=unexpected,
            writesPerformed=False,actualRemoteQueried=False,ciQueried=False),
        selfHashExcluded=SELF_OUTPUTS)
    write('final.audit.json',audit)
    print(json.dumps({k:audit[k] for k in ('errors','sourceCount','sourceHash','pendingCount','excludedCount')},ensure_ascii=False))


if __name__=='__main__':main()
