"""Read-only repository inspection; writes only this batch's named audit files."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from run import source_hashes

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode('utf8')

def main():
    label=sys.argv[1]
    if not re.fullmatch('[a-z0-9-]+',label):raise ValueError('audit label')
    destination=OUT/(label+'.audit.json')
    if destination.exists():raise ValueError('audit label occupied')
    baseline=json.loads((OUT/'before.json').read_text(encoding='utf8'))
    source=source_hashes()
    checks={}
    for group,entries in baseline['protected'].items():
        checks[group]={'count':len(entries),'mismatches':[name for name,h in entries.items()
            if not (ROOT/name).is_file() or sha(ROOT/name)!=h]}
    actual_formal={p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
    checks['formalFiles']['actualCount']=len(actual_formal)
    checks['formalFiles']['pathDifferences']=sorted(actual_formal ^ set(baseline['protected']['formalFiles']))
    from continuity_engine.testing.persistence import tree_inventory_hash
    measured_formal_tree=tree_inventory_hash(ROOT/'.continuity-data')
    checks['independentOriginals']={'count':len(baseline['independentOriginals']),
        'mismatches':[name for name,h in baseline['independentOriginals'].items()
                      if not Path(name).is_file() or sha(Path(name))!=h]}
    archived=json.loads((OUT/'archives.json').read_text(encoding='utf8'))
    checks['archiveCopies']={'count':len(archived),'mismatches':[r['copy'] for r in archived
        if sha(Path(r['original']))!=r['sha256'] or sha(ROOT/r['copy'])!=r['sha256']]}
    parse_errors=[]
    for name in source:
        if name.endswith('.py'):
            try:ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)
            except SyntaxError as exc:parse_errors.append({'path':name,'line':exc.lineno})
    tracked=git('diff','--name-only','-z').split('\0');new=git('ls-files','--others','--exclude-standard','-z').split('\0')
    paths=sorted(set(filter(None,tracked+new)))
    excluded=baseline['excluded']
    pending=[p for p in paths if p not in excluded]
    hashes={p:sha(ROOT/p) for p in pending}
    changed_source=[p for p,h in source.items() if baseline['source'].get(p)!=h]
    allowed_services={'action_evaluators.py','continuity_core_service.py','continuity_interaction_service.py',
        'dynamic_mind_service.py','execution_service.py','runtime_cognition.py','wake_perception_thinking_action_service.py'}
    unexpected_source=[p for p in changed_source if not (p in {'tests/test_action.py','tests/test_p18_runtime_recovery.py'}
        or p.startswith('tests/test_pre_p19_autonomy_')
        or p.startswith('src/continuity_engine/services/') and Path(p).name in allowed_services)]
    secret_hits=[];format_notices=[]
    for name in pending:
        if (ROOT/name).suffix not in {'.py','.md','.json','.log'}:continue
        body=(ROOT/name).read_text(encoding='utf8')
        for number,line in enumerate(body.splitlines(),1):
            if line.rstrip(' \t')!=line:
                format_notices.append({'path':name,'line':number,'kind':'trailing-space',
                    'rawEvidence':name.endswith('.log') or '/independent/' in name})
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',body):
            secret_hits.append(name)
    unknown=[p for p in pending if p not in source and not (p.startswith('docs/project_memory/') or p in {'README.md','CHANGELOG.md'})]
    bad_links=[];link_count=0
    for name in pending:
        if not name.endswith('.md') or '/independent/' in name:continue
        text=(ROOT/name).read_text(encoding='utf8')
        for target in re.findall(r'\]\(([^\n]+?)\)',text):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^(https?://|mailto:|app:)',target):continue
            if ':/' in target and not re.match(r'^[A-Za-z]:/',target):continue
            target=re.sub(r':\d+$','',target)
            from urllib.parse import unquote
            path=Path(unquote(target));path=path if path.is_absolute() else ROOT/name/ '..'/path
            link_count+=1
            if not path.resolve().exists():bad_links.append({'document':name,'target':target,'resolvedPath':str(path.resolve())})
    whitespace=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    (OUT/(label+'.diff-check.log')).write_text(whitespace.stdout+whitespace.stderr,encoding='utf8')
    # Audit/manifest cover their own paths without pretending a self-referential hash exists.
    if label == 'final':
        manifest=OUT/'final.pending-files.md'
        if manifest.exists():raise ValueError('final manifest already exists')
        paths=sorted(set(filter(None,git('diff','--name-only','-z').split('\0')+
            git('ls-files','--others','--exclude-standard','-z').split('\0'))))
        pending=sorted(set(p for p in paths if p not in excluded)|{
            destination.relative_to(ROOT).as_posix(),manifest.relative_to(ROOT).as_posix()})
        lines=['# P19 前 R1—R4 精确待提交与排除清单','',
            '本清单仅供独立复核，未执行暂存、提交或推送。相对路径基于Engine仓库。',
            '清单自身及最终审计不进行循环哈希；审计记录清单的最终hash，审计自身由复核方读取计算。',
            '',f'待提交 {len(pending)} 项；另有 {len(excluded)} 项原样排除。','',
            '| 路径 | SHA-256 |','|---|---|']
        for name in pending:
            digest=sha(ROOT/name) if ROOT/name not in (destination,manifest) else '自引用审计产物（见上文）'
            lines.append(f'| `{name}` | {digest} |')
        lines += ['', '## 排除清单（原始32项）','','| 路径 | SHA-256 |','|---|---|']
        lines += [f'| `{name}` | {digest} |' for name,digest in sorted(excluded.items())]
        manifest.write_text('\n'.join(lines)+'\n',encoding='utf8')
        hashes={p:sha(ROOT/p) if ROOT/p!=destination else 'SELF_NOT_HASHED' for p in pending}
    run_binding={}
    for result in sorted(OUT.glob('*.json')):
        data=json.loads(result.read_text(encoding='utf8'))
        if isinstance(data,dict) and 'sourceBefore' in data:
            run_binding[result.name]={'status':data.get('status'),
                'beforeEqualsAfter':data.get('sourceBefore')==data.get('sourceAfter'),
                'matchesCurrent':data.get('sourceBefore')==source==data.get('sourceAfter'),
                'run':data.get('run'),'passed':data.get('passed'),'exitCode':data.get('exitCode')}
    selection_path=OUT/'selected-runs.json'
    selection=json.loads(selection_path.read_text(encoding='utf8')) if selection_path.exists() else {}
    full=OUT/(selection.get('full','full-final-01')+'.json')
    ids=json.loads(full.read_text(encoding='utf8')).get('testIdentities',[]) if full.exists() else []
    approved_docs={'README.md',*[f'docs/project_memory/{name}' for name in (
        '01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md',
        'CHANGELOG.md','工程总档案.md')]}
    unknown=[p for p in pending if p not in source and p not in approved_docs
             and not p.startswith('docs/project_memory/pre_p19_autonomy_evidence/')]
    unexpected_tracked=[p for p,h in baseline['tracked'].items()
        if (not (ROOT/p).is_file() or sha(ROOT/p)!=h)
        and p not in changed_source and p not in approved_docs]
    forbidden_artifacts=[p for p in pending if Path(p).suffix in {'.pyc','.whl','.zip','.exe','.dll'}
        or any(part.lower() in {'__pycache__','.continuity-data','.assistant-data','node_modules','build','dist','sandbox'} for part in Path(p).parts)]
    history_path=OUT/'document-history.json'
    history=json.loads(history_path.read_text(encoding='utf8')) if history_path.exists() else {}
    history_changes=[p for p,item in history.items() if hashlib.sha256((ROOT/p).read_bytes()[item['offset']:]).hexdigest()!=item['originalHash']]
    import tomllib
    version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
    record=dict(at=datetime.now(timezone.utc).isoformat(),head=git('rev-parse','HEAD').strip(),
        branch=git('branch','--show-current').strip(),origin=git('rev-parse','origin/main').strip(),
        aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main').strip(),
        staged=git('diff','--cached','--name-only').splitlines(),indexUnchanged=sha(ROOT/'.git/index')==baseline['indexHash'],
        source=source,sourceHash='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        sourceCount=len(source),protection=checks,pyprojectUnchanged=sha(ROOT/'pyproject.toml')==baseline['pyproject'],
        formalTreeHash=measured_formal_tree,formalTreeMatchesBaseline=measured_formal_tree==baseline['formalTreeHash'],
        astFiles=sum(p.endswith('.py') for p in source),astErrors=parse_errors,localLinks=link_count,brokenLinks=bad_links,
        diffCheckExit=whitespace.returncode,unknownPaths=unknown,pending=hashes,excluded=excluded,
        changedSource=changed_source,unexpectedSource=unexpected_source,highConfidenceSecretHits=secret_hits,
        formatNotices=format_notices,
        runBinding=run_binding,baselineTestCount=len(baseline['testIdentities']),
        finalTestCount=len(ids),missingBaselineTests=sorted(set(baseline['testIdentities'])-set(ids)),
        addedTests=sorted(set(ids)-set(baseline['testIdentities'])),unexpectedTracked=unexpected_tracked,
        duplicateTestIdentities=sorted({identity for identity in ids if ids.count(identity)>1}),
        forbiddenPendingArtifacts=forbidden_artifacts,version=version,
        historicalDocumentTailsChecked=len(history),historicalDocumentChanges=history_changes,
        pendingCount=len(pending),excludedCount=len(excluded),
        gitStatus=git('status','--porcelain=v1','--untracked-files=all'))
    with destination.open('x',encoding='utf8') as stream:
        # The manifest and audit are now present; recheck forward links to the
        # artifacts this invocation itself creates, without exempting bad links.
        record['brokenLinks']=[item for item in record['brokenLinks'] if not Path(item['resolvedPath']).exists()]
        record['gitStatus']=git('status','--porcelain=v1','--untracked-files=all')
        json.dump(record,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:record[k] for k in ('head','sourceCount','protection','indexUnchanged','astErrors','brokenLinks','diffCheckExit','unknownPaths')},ensure_ascii=False))

if __name__=='__main__':main()
