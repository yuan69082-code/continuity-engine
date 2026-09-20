"""Read-only final inspection; writes only new final audit and manifest artifacts."""
import ast,hashlib,json,os,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path[:0]=[str(OUT),str(ROOT/'src')]
from run import source_hashes
from continuity_engine.testing.persistence import tree_inventory_hash

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode('utf8')

def main():
    destination=OUT/'final.audit.json';manifest=OUT/'final.pending-files.md'
    assert not destination.exists() and not manifest.exists(),'final output already exists'
    baseline=json.loads((OUT/'before.json').read_text(encoding='utf8'))
    old=json.loads((ROOT/'docs/project_memory/pre_p19_autonomy_evidence/before.json').read_text(encoding='utf8'))
    source=source_hashes();selected=json.loads((OUT/'selected-runs.json').read_text(encoding='utf8'))
    results={k:json.loads((OUT/(v+'.json')).read_text(encoding='utf8')) for k,v in selected.items()}
    full=results['full'];ids=full['testIdentities']
    changed=[p for p,h in source.items() if baseline['source'].get(p)!=h]
    services=['continuity_core_service.py','continuity_interaction_service.py','expression_policy_service.py',
              'runtime_cognition.py','wake_perception_thinking_action_service.py']
    allowed={*[f'src/continuity_engine/services/{n}' for n in services],'tests/test_pre_p19_supplement.py'}
    docs={'README.md',*[f'docs/project_memory/{n}' for n in ('01_当前状态.md','03_施工日志.md',
          '04_决策记录.md','06_未完成事项.md','CHANGELOG.md','工程总档案.md')]}
    protection={group:{'count':len(items),'mismatches':[p for p,h in items.items()
        if not (ROOT/p).is_file() or sha(ROOT/p)!=h]} for group,items in baseline['protected'].items()}
    archives=json.loads((OUT/'archives.json').read_text(encoding='utf8'))
    archive_mismatches=[r['copy'] for r in archives if sha(Path(r['original']))!=r['sha256'] or sha(ROOT/r['copy'])!=r['sha256']]
    # All earlier delivery evidence remains byte-for-byte intact. Only directly
    # authorized running files and current document prefixes may change.
    prior_changes=[p for p,h in baseline['priorPending'].items()
                   if (not (ROOT/p).is_file() or sha(ROOT/p)!=h) and p not in allowed|docs]
    expected_before={**old['tracked'],**baseline['priorPending']}
    unrelated=[p for p,h in expected_before.items() if p not in allowed|docs
               and (not (ROOT/p).is_file() or sha(ROOT/p)!=h)]
    excluded=baseline['excluded']
    def paths():return sorted(set(filter(None,(git('diff','--name-only','-z')+
                                              git('ls-files','--others','--exclude-standard','-z')).split('\0'))))
    all_paths=paths();pending=[p for p in all_paths if p not in excluded]
    new_unknown=[p for p in pending if p not in baseline['priorPending'] and p not in allowed|docs
                 and not p.startswith('docs/project_memory/pre_p19_supplement_evidence/')]
    errors=[]
    for p in source:
        if p.endswith('.py'):
            try:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p)
            except SyntaxError as exc:errors.append({'path':p,'line':exc.lineno})
    links=0;broken=[];secrets=[];format_notes=[]
    for p in pending:
        if Path(p).suffix not in {'.py','.md','.json','.jsonl','.log'}:continue
        body=(ROOT/p).read_text(encoding='utf8')
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',body):secrets.append(p)
        for number,line in enumerate(body.splitlines(),1):
            if line.rstrip(' \t')!=line:format_notes.append({'path':p,'line':number,'rawEvidence':p.endswith('.log') or '/independent/' in p})
        if not p.endswith('.md') or '/independent/' in p:continue
        for target in re.findall(r'\]\(([^\n]+?)\)',body):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^(https?://|mailto:|app:)',target):continue
            if ':/' in target and not re.match(r'^[A-Za-z]:/',target):continue
            target=re.sub(r':\d+$','',target);path=Path(unquote(target))
            path=path if path.is_absolute() else (ROOT/p).parent/path
            links+=1
            if not path.resolve().exists() and path.resolve() not in {destination,manifest}:
                broken.append({'document':p,'target':target})
    check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',
                         env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    with (OUT/'final.diff-check.log').open('x',encoding='utf8') as f:f.write(check.stdout+check.stderr)
    pending=sorted(set(p for p in paths() if p not in excluded)|{destination.relative_to(ROOT).as_posix(),manifest.relative_to(ROOT).as_posix()})
    def hash_pending(p):return 'SELF_NOT_HASHED' if ROOT/p in {destination,manifest} else sha(ROOT/p)
    lines=['# 精确待提交清单：R1—R4成果及A1/A2/A3补修','',
           '只供独立复核；未执行暂存、提交或push。全部路径相对Engine仓库。',
           '清单自身与审计不进行循环hash；审计记录清单的最终hash，审计自身由复核方独立计算。','',
           f'累计本批次待提交 {len(pending)} 项；原32项排除材料另列。原154项成果均保留，后续已授权修改逐项以补修基线核对。','',
           '| 路径 | SHA-256 |','|---|---|']
    lines += [f'| `{p}` | {hash_pending(p)} |' for p in pending]
    lines += ['','## 排除（原32项，未改动）','','| 路径 | SHA-256 |','|---|---|']
    lines += [f'| `{p}` | {h} |' for p,h in sorted(excluded.items())]
    with manifest.open('x',encoding='utf8') as f:f.write('\n'.join(lines)+'\n')
    history=json.loads((OUT/'document-history.json').read_text(encoding='utf8'))
    old_tests_changed=[p for p,h in baseline['source'].items() if p.startswith('tests/') and sha(ROOT/p)!=h]
    formal={p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
    tree=tree_inventory_hash(ROOT/'.continuity-data')
    record={'at':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD').strip(),
        'origin':git('rev-parse','origin/main').strip(),'branch':git('branch','--show-current').strip(),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main').strip(),
        'staged':git('diff','--cached','--name-only').splitlines(),'indexUnchanged':sha(ROOT/'.git/index')==baseline['indexHash'],
        'source':source,'sourceCount':len(source),'sourceHash':'sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'changedFromSupplementBaseline':changed,'unauthorizedSourceChanges':sorted(set(changed)-allowed),
        'oldTestsChanged':old_tests_changed,'baselineTestCount':len(baseline['testIdentities']),'finalTestCount':len(ids),
        'missingBaselineTests':sorted(set(baseline['testIdentities'])-set(ids)),
        'addedTests':sorted(set(ids)-set(baseline['testIdentities'])),'duplicateTests':len(ids)-len(set(ids)),
        'protection':protection,'archiveMismatches':archive_mismatches,'previousEvidenceChanges':prior_changes,
        'unrelatedChanges':unrelated,'newUnknownPaths':new_unknown,
        'formalFilesCount':len(formal),'formalFileSetDifferences':sorted(formal^set(baseline['protected']['formalFiles'])),
        'formalTreeHash':tree,'formalTreeMatches':tree==baseline['formalTreeHash'],
        'pyprojectUnchanged':sha(ROOT/'pyproject.toml')==baseline['pyproject'],
        'version':__import__('tomllib').loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version'],
        'astFiles':sum(p.endswith('.py') for p in source),'astErrors':errors,'localLinks':links,'brokenLinks':broken,
        'highConfidenceSecretHits':secrets,'formatNotices':format_notes,'diffCheckExit':check.returncode,
        'forbiddenPendingArtifacts':[p for p in pending if Path(p).suffix in {'.pyc','.whl','.zip','.exe','.dll'}
             or any(x.lower() in {'__pycache__','.continuity-data','.assistant-data','sandbox','build','dist'} for x in Path(p).parts)],
        'historicalDocumentChanges':[p for p,row in history.items() if hashlib.sha256((ROOT/p).read_bytes()[row['offset']:]).hexdigest()!=row['originalHash']],
        'runBindings':{k:{'label':selected[k],'finished':r['status']=='FINISHED','exitCode':r['exitCode'],
             'matchesCurrent':r['sourceBefore']==source==r['sourceAfter'],'run':r['run'],'passed':r['passed'],
             'skips':r['skips'],'seconds':r['seconds']} for k,r in results.items()},
        'pendingCount':len(pending),'pending':{p:sha(ROOT/p) if ROOT/p!=destination else 'SELF_NOT_HASHED' for p in pending},
        'excluded':excluded,'excludedCount':len(excluded),'remoteCI':'NOT_RUN',
        'gitStatus':git('status','--porcelain=v1','--untracked-files=all')}
    with destination.open('x',encoding='utf8') as f:
        record['gitStatus']=git('status','--porcelain=v1','--untracked-files=all')
        json.dump(record,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:record[k] for k in ('head','sourceCount','sourceHash','pendingCount','excludedCount',
        'protection','archiveMismatches','previousEvidenceChanges','unrelatedChanges','oldTestsChanged',
        'unauthorizedSourceChanges','astErrors','brokenLinks','diffCheckExit')},ensure_ascii=False))

if __name__=='__main__':main()
