"""Read-only final identity audit and precise evidence manifest, no Git writes."""
import ast,datetime,hashlib,json,os,pathlib,re,runpy,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent
BASE=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
FROZEN=json.loads((HERE/('frozen-source-'+(sys.argv[2] if len(sys.argv)>2 else 'final-02')+'.json')).read_text(encoding='utf8'))
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT).decode('utf8')
def put(name,value):
    with (HERE/name).open('x',encoding='utf8',newline='\n') as out:
        out.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')
label=sys.argv[1]; assert re.fullmatch('[a-z0-9-]+',label)
prefix=HERE.relative_to(ROOT).as_posix()+'/'
source=SNAP['source'](); tracked=list(filter(None,git('diff','--name-only','-z').split('\0')))
untracked=list(filter(None,git('ls-files','--others','--exclude-standard','-z').split('\0')))
staged=git('diff','--cached','--name-only'); head=git('rev-parse','HEAD').strip()
retained={p:sha(ROOT/p) for p in BASE['retained']}
protected={k:{p:sha(ROOT/p) for p in rows} for k,rows in BASE['protected'].items()}
plans={row['archivePath']:sha(ROOT/row['archivePath']) for row in BASE['planning']}
allowed_runtime={'src/continuity_engine/services/cross_entry_service.py',
                 'src/continuity_engine/services/device_operation_service.py',
                 'src/continuity_engine/services/entry_context_source.py'}
source_changed={p:h for p,h in source.items() if BASE['source'].get(p)!=h}
old_tests={p:source.get(p)==h for p,h in BASE['source'].items() if p.startswith('tests/')}
old_evidence_changed=[p for p,h in BASE['previous_hashes'].items()
    if p not in BASE['shared_hashes'] and p not in allowed_runtime and sha(ROOT/p)!=h]
history={}
for p,h in BASE['shared_hashes'].items():
    raw=(ROOT/p).read_bytes(); start=raw.find(b'<!-- W04_4_FINAL_D092_20261001 -->')
    history[p]=hashlib.sha256(raw[start:]).hexdigest()==h if start>=0 else sha(ROOT/p)==h
unexpected=[p for p in tracked+untracked if p not in BASE['previous_paths'] and p not in retained
            and p not in BASE['shared_hashes'] and p!='tests/test_w04_4_review_repairs.py' and not p.startswith(prefix)]
syntax=[]
for p in source:
    if p.endswith('.py'):
        try:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p)
        except SyntaxError as exc:syntax.append({'path':p,'line':exc.lineno})
checks=dict(source_frozen=source==FROZEN['source'],head=head==BASE['head'],
    branch=git('branch','--show-current').strip()=='main',staging_empty=not staged.strip(),
    index_unchanged=sha(ROOT/'.git/index')==BASE['index_hash'],
    retained=retained==BASE['retained'],protected=protected==BASE['protected'],
    planning=all(plans[row['archivePath']]==row['archiveSha256'] for row in BASE['planning']),
    previous_evidence=not old_evidence_changed,historical_shared_suffix=all(history.values()),
    original_tests=all(old_tests.values()),original_test_ids=not set(BASE['test_ids'])-set(FROZEN['test_ids']),
    source_scope=set(source_changed)<=allowed_runtime|{'tests/test_w04_4_review_repairs.py'},
    workspace_scope=not unexpected,source_syntax=not syntax,
    independent_original_copy=sha(BASE['review_original'])==sha(HERE/'independent-readonly-review.json')==BASE['review_original_sha256'])
audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,
    branch='main',head=head,local_origin=git('rev-parse','origin/main').strip(),
    actual_remote='NOT_QUERIED_IN_THIS_REPAIR; previous W04-4 evidence is historical only',ci='NOT_VERIFIED',
    source_fingerprint=SNAP['fingerprint'](source),source_count=len(source),source_changed=source_changed,
    source=source,original_test_count=len(BASE['test_ids']),test_count=len(FROZEN['test_ids']),
    new_tests=FROZEN['new_tests'],old_test_files=old_tests,protected=protected,planning=plans,
    retained=retained,history=history,old_evidence_changed=old_evidence_changed,
    tracked=tracked,untracked=untracked,staged=staged,unexpected=unexpected,syntax_errors=syntax,
    git_writes=False,acceptance=False,evidence_conflict='PRESENT',historical_unknown=['F1','H1','F2'])
if label=='final':
    extra=[prefix+n for n in ['final.audit.json','final.files.json','final.pending-files.md',
                             'final.diff-check.stdout.log','final.diff-check.stderr.log']]
    paths=sorted((set(tracked+untracked)-set(retained))|set(extra))
    diff=subprocess.run(['git','-c','core.quotepath=false','diff','--check'],cwd=ROOT,capture_output=True)
    put('final.diff-check.stdout.log',diff.stdout.decode('utf8',errors='replace'))
    put('final.diff-check.stderr.log',diff.stderr.decode('utf8',errors='replace'))
    entries=['# D-092 本轮累计交付清单（不是提交授权）','',f'累计{len(paths)}项；另70项保留材料排除。',
        '旧402项与本轮增量分列；共享历史原字节后缀保持；原始测试日志不规范化、不清除历史空格。',
        f'源码332项：`{FROZEN["fingerprint"]}`。','', '|路径|归属|','|---|---|']
    for p in paths:
        category=('共享档案顶部增量，历史后缀保持' if p in BASE['shared_hashes'] else
                  '本轮来源/派发最小修补' if p in allowed_runtime else
                  '旧402项保持' if p in BASE['previous_paths'] else '本轮新增测试/证据/档案')
        entries.append(f'|`{p}`|{category}|')
    entries+=['','排除逐路径及hash：[exclusions.json](exclusions.json)。清单自身不递归计算hash。','']
    put('final.pending-files.md','\n'.join(entries))
    selected=json.loads((HERE/'selected-runs.json').read_text(encoding='utf8'))
    runs=[json.loads((HERE/(name+'.json')).read_text(encoding='utf8')) for name in selected['final']]
    checks['final_runs_complete_same_source']=all(r['status']=='COMPLETED' and r['exit_code']==0
        and r['hash_before']==r['hash_after']==FROZEN['fingerprint'] for r in runs)
    links=[]; secrets=[]; temporary=[]
    for p in paths:
        file=ROOT/p
        if not file.exists():continue
        if file.suffix in {'.pyc','.whl','.zip'} or '__pycache__' in file.parts:temporary.append(p)
        if p in BASE['previous_paths'] and p not in BASE['shared_hashes'] and p not in allowed_runtime:continue
        if file.suffix not in {'.py','.md','.json','.log'}:continue
        text=file.read_text(encoding='utf8',errors='replace')
        if p in BASE['shared_hashes']:text=text.split('<!-- W04_4_FINAL_D092_20261001 -->',1)[0]
        for pattern in [r'gh[pousr]_[A-Za-z0-9]{30,}',r'AKIA[A-Z0-9]{16}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']:
            for m in re.finditer(pattern,text):secrets.append({'path':p,'line':text.count('\n',0,m.start())+1,'pattern':pattern})
        if file.suffix=='.md':
            for target in re.findall(r'\[[^\]\n]+\]\(([^)]+)\)',text):
                target=target.strip('<>').split('#',1)[0]
                if not target or re.match(r'^(https?:|app:|codex:|mailto:)',target):continue
                dest=pathlib.Path(target) if pathlib.Path(target).is_absolute() else file.parent/target
                if not dest.exists() and dest.resolve() not in {(ROOT/v).resolve() for v in paths}:links.append({'path':p,'target':target})
    process=json.loads((HERE/'process-final.json').read_text(encoding='utf-8-sig'))
    checks['owned_processes_finished']=process['owned_python_count']==0
    checks['new_links']=not links; checks['new_secret_scan']=not secrets; checks['temporary_artifacts']=not temporary
    audit.update(pending_count=len(paths),pending_paths=paths,retained_count=len(retained),
        new_paths=sorted(set(paths)-set(BASE['previous_paths'])),final_runs=runs,
        process=process,diff_check_exit=diff.returncode,link_errors=links,secret_findings=secrets,
        temporary_artifacts=temporary,logs_original_bytes_preserved=True,
        stage='W04-4 and W04 package IMPLEMENTED_NOT_ACCEPTED')
put(label+'.audit.json',audit)
if label=='final':
    put('final.files.json',dict(paths=paths,hashes={p:sha(ROOT/p) for p in paths if p!=prefix+'final.files.json'},
        self_hash_omitted=prefix+'final.files.json',retained=retained,source_fingerprint=FROZEN['fingerprint'],
        not_commit_authorization=True))
print(json.dumps({'checks':checks,'source_count':len(source),'test_count':len(FROZEN['test_ids']),
                  'tracked':len(tracked),'untracked':len(untracked),'retained':len(retained)}))
if not all(checks.values()):raise SystemExit(1)
