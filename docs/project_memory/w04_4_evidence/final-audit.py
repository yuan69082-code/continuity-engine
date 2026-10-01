"""Read-only repository audit plus newly labelled audit artifacts; never tests/Git writes."""
import ast,datetime,hashlib,json,os,pathlib,re,runpy,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
os.environ['GIT_OPTIONAL_LOCKS']='0'
BASE=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
FROZEN=json.loads((HERE/'frozen-source-final-01.json').read_text(encoding='utf8'))
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,stderr=subprocess.DEVNULL)
def put(p,value):
    with p.open('x',encoding='utf8',newline='\n') as out:
        out.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n' if not isinstance(value,str) else value)
label=sys.argv[1]
assert re.fullmatch(r'[a-z0-9-]+',label)
assert not (HERE/(label+'.audit.json')).exists()
source=SNAP['source']()
protected={group:{p:sha(ROOT/p) for p in items} for group,items in BASE['protected'].items()}
plans={p['archivePath']:sha(ROOT/p['archivePath']) for p in BASE['planning']}
retained={p:sha(ROOT/p) for p in BASE['retained']}
history={p:(ROOT/p).read_bytes().endswith(git('show','HEAD:'+p)) for p in BASE['shared_hashes']}
raw=json.loads((HERE/'completed-raw-preservation-20261001.json').read_text(encoding='utf8'))['hashes']
raw_changes=[p for p,h in raw.items() if sha(HERE/p)!=h]
old_tests={p:source.get(p)==h for p,h in BASE['source'].items() if p.startswith('tests/')}
syntax={}
for p in source:
    if p.endswith('.py'):
        try:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p)
        except Exception as e:syntax[p]={'type':type(e).__name__,'line':getattr(e,'lineno',None)}
tracked=[p for p in git('diff','--name-only','-z').decode('utf8').split('\0') if p]
untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0') if p]
staged=git('diff','--cached','--name-only').decode().strip()
checks=dict(source_frozen=source==FROZEN['source'],protected=protected==BASE['protected'],
    plans=all(plans[p['archivePath']]==p['archiveSha256'] for p in BASE['planning']),
    retained=retained==BASE['retained'],old_tests=all(old_tests.values()),
    history=all(history.values()),raw=not raw_changes,syntax=not syntax,
    staged_empty=not staged,index=sha(ROOT/'.git/index')==BASE['index_hash'],
    head=git('rev-parse','HEAD').decode().strip()==BASE['head'],
    branch=git('branch','--show-current').decode().strip()=='main')
scope_prefix=HERE.relative_to(ROOT).as_posix()+'/'
unexpected=[p for p in tracked+untracked if p not in retained and p not in BASE['shared_hashes']
    and p not in source and not p.startswith(scope_prefix)]
checks['worktree_scope']=not unexpected
checks['origin_repository']=git('remote','get-url','origin').decode('utf8').strip()=='https://github.com/yuan69082-code/continuity-engine.git'
audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,
    source_count=len(source),source_fingerprint=SNAP['fingerprint'](source),source=source,
    protected_counts={k:len(v) for k,v in protected.items()},plans=plans,retained=retained,
    historical_shared_byte_suffix=history,old_test_files_unchanged=old_tests,
    original_test_count=len(BASE['test_ids']),final_test_count=len(FROZEN['test_ids']),
    new_tests=FROZEN['new_tests'],missing_original_tests=sorted(set(BASE['test_ids'])-set(FROZEN['test_ids'])),
    raw_changes=raw_changes,syntax_errors=syntax,tracked=tracked,untracked=untracked,
    head=git('rev-parse','HEAD').decode().strip(),local_origin=git('rev-parse','origin/main').decode().strip(),
    actual_remote={'not_queried_this_audit':True,'historical_evidence':'baseline.json#/actual_remote'},
    staged=staged,ci='NOT_VERIFIED',git_writes=False,acceptance=False,unexpected_paths=unexpected)
remote=HERE/'remote-readonly-20261001.json'
if remote.exists():
    value=json.loads(remote.read_text(encoding='utf8'))
    audit['actual_remote']={'record':remote.name,**value}
    checks['actual_remote_matches_baseline']=value['exit_code']==0 and value['stdout'].split()[0]==BASE['head']
if label=='final':
    # No circular hashes: the manifest hashes the audit and the path list; its
    # own hash is explicitly omitted. It is never a source of product facts.
    report=HERE/'final-report.md'
    assert report.exists()
    prefix=HERE.relative_to(ROOT).as_posix()+'/'
    paths=sorted((set(tracked+untracked)-set(retained))|{
        prefix+'final.audit.json',prefix+'final.files.json',prefix+'final.pending-files.md',
        prefix+'final.diff-check.stdout.log',prefix+'final.diff-check.stderr.log'})
    diff=subprocess.run(['git','-c','core.quotepath=false','diff','--check'],cwd=ROOT,capture_output=True)
    put(HERE/'final.diff-check.stdout.log',diff.stdout.decode('utf8',errors='replace'))
    put(HERE/'final.diff-check.stderr.log',diff.stderr.decode('utf8',errors='replace'))
    pending=['# W04-4 与包级精确成果清单（非提交授权）','',
        f'本批累计 {len(paths)} 项，另70份保留材料排除；未暂存、提交或push。',
        f'源码/测试/资源331项，`{FROZEN["fingerprint"]}`。',
        '逐文件hash见 final.files.json；该清单不递归计算自己的hash，审计由清单计算。',
        '', '| 路径 | 归属 |','|---|---|']
    for p in paths:
        kind='共享档案；新记录在前，HEAD历史原字节后缀保持' if p in BASE['shared_hashes'] else '实现/测试' if p.startswith(('src/','tests/')) else '本批文档/原始证据/审计工具'
        pending.append(f'|`{p}`|{kind}|')
    pending+=['','排除70项逐路径/hash见[exclusions.json](exclusions.json)及final.files.json retained；D-085本地材料仍未提交。','']
    put(HERE/'final.pending-files.md','\n'.join(pending))
    links=[];secrets=[];temporary=[];new_code_whitespace=[]
    credential_patterns=[r'AKIA[A-Z0-9]{16}',r'gh[pousr]_[A-Za-z0-9]{30,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    for relative in paths:
        p=ROOT/relative
        if not p.exists():continue
        if p.suffix in {'.pyc','.whl','.zip'} or any(part in {'__pycache__','.pytest_cache'} for part in p.parts):temporary.append(relative)
        if p.suffix not in {'.py','.md','.json','.log'}:continue
        text=p.read_text(encoding='utf8',errors='replace')
        for pattern in credential_patterns:
            for match in re.finditer(pattern,text):secrets.append({'path':relative,'line':text.count('\n',0,match.start())+1,'pattern':pattern})
        if relative.startswith(('src/','tests/')):
            for number,line in enumerate(text.splitlines(),1):
                if line.rstrip(' \t')!=line:new_code_whitespace.append({'path':relative,'line':number})
        if p.suffix!='.md':continue
        if relative in BASE['shared_hashes']:
            old=git('show','HEAD:'+relative)
            text=p.read_bytes()[:-len(old)].decode('utf8')
        for target in re.findall(r'\[[^\]\n]+\]\(([^)]+)\)',text):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^(https?:|app:|codex:|mailto:)',target):continue
            target=re.sub(r':\d+$','',target)
            destination=pathlib.Path(target) if pathlib.Path(target).is_absolute() else p.parent/target
            if not destination.exists() and destination.resolve() not in {(ROOT/x).resolve() for x in paths}:
                links.append({'path':relative,'target':target})
    process=json.loads((HERE/'process-final-01.json').read_text(encoding='utf-8-sig'))
    runs=[json.loads((HERE/(name+'.json')).read_text(encoding='utf8')) for name in
          ['targeted-final-01','w04-final-01','public-final-01','full-final-01']]
    checks['completed_final_source_runs']=all(r.get('exit_code')==0 and r.get('status')=='COMPLETED' and
        r['hash_before']==r['hash_after']==FROZEN['fingerprint'] for r in runs)
    checks['new_links']=not links;checks['credential_scan']=not secrets;checks['temporary_artifacts']=not temporary
    checks['owned_test_processes_finished']=process['python_count']==0
    audit.update(stage='W04-4 and W04 package IMPLEMENTED_NOT_ACCEPTED',evidence_conflict='PRESENT',
        planning_conflict='NONE',planning_conflict_basis='P13/C1 correction explicitly approved; no new proven planning conflict in this scope; independent review still required',
        pending_paths=paths,pending_count=len(paths),retained_count=len(retained),
        process=process,completed_runs=[{k:r.get(k) for k in ('label','exit_code','duration_seconds','hash_before','hash_after')} for r in runs],
        diff_check={'exit_code':diff.returncode,'stdout':'final.diff-check.stdout.log','stderr':'final.diff-check.stderr.log'},
        link_errors=links,high_confidence_secret_findings=secrets,temporary_artifacts=temporary,
        source_trailing_whitespace=new_code_whitespace,raw_logs_not_normalized=True,
        historical_unknown=['F1','H1','F2'],git_state='main original HEAD; empty staging; authorized unstaged work and retained files',
        source_changes={p:h for p,h in source.items() if BASE['source'].get(p)!=h})
put(HERE/(label+'.audit.json'),audit)
if label=='final':
    put(HERE/'final.files.json',dict(paths=paths,hashes={p:sha(ROOT/p) for p in paths if p!=prefix+'final.files.json'},
        self_hash_omitted=prefix+'final.files.json',retained=retained,source_fingerprint=FROZEN['fingerprint'],not_commit_authorization=True))
print(json.dumps({'label':label,'checks':checks,'source_count':len(source),
    'tracked':len(tracked),'untracked':len(untracked),'retained':len(retained),'tests':len(FROZEN['test_ids'])}))
if not all(checks.values()) or audit['missing_original_tests']:raise SystemExit(1)
