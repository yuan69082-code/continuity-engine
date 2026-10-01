"""D-093 pre-staging audit and exact manifest; never writes Git or runs Engine tests."""
import datetime, hashlib, json, os, pathlib, re, runpy, subprocess

ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent
BASE=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
PREFIX=HERE.relative_to(ROOT).as_posix()+'/'
os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT).decode('utf8')
def put(name,value):
    with (HERE/name).open('x',encoding='utf8',newline='\n') as out:
        out.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')

source_tools=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
source=source_tools['source']()
tracked=set(filter(None,git('diff','--name-only','-z').split('\0')))
untracked=set(filter(None,git('ls-files','--others','--exclude-standard','-z').split('\0')))
old_changed=[p for p,h in BASE['reviewed_hashes'].items() if p not in BASE['shared_hashes'] and sha(ROOT/p)!=h]
history={}
for p,h in BASE['shared_hashes'].items():
    raw=(ROOT/p).read_bytes(); offset=raw.find(b'<!-- W04_4_REVIEW_REPAIR_FINAL_20261001 -->')
    history[p]=offset>=0 and hashlib.sha256(raw[offset:]).hexdigest()==h
protected={group:[p for p,h in rows.items() if sha(ROOT/p)!=h] for group,rows in BASE['protected'].items()}
plan_mismatches=[p for p,h in BASE['planning'].items() if sha(ROOT/p)!=h]
retained_mismatches=[p for p,h in BASE['retained'].items() if sha(ROOT/p)!=h]
formal={p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
unexpected=[p for p in tracked|untracked if p not in BASE['reviewed_paths'] and p not in BASE['retained'] and not p.startswith(PREFIX)]
extra=[PREFIX+name for name in ('final.audit.json','final.files.json','final.pending-files.md','diff-check.stdout.log','diff-check.stderr.log')]
paths=sorted(((tracked|untracked)-set(BASE['retained']))|set(extra))
assert set(BASE['reviewed_paths'])<=set(paths)
assert not set(paths)&set(BASE['retained'])
diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True)
with (HERE/'diff-check.stdout.log').open('xb') as out:out.write(diff.stdout)
with (HERE/'diff-check.stderr.log').open('xb') as out:out.write(diff.stderr)

entries=['# D-093 最终精确提交清单','',f'共{len(paths)}项：原496项交付 + 本次{len(set(paths)-set(BASE["reviewed_paths"]))}项验收归档。另70份保留材料全部排除。',
    '八份共享档案仅顶部验收增量，旧正文原字节后缀保留；D-085独有规划/现行索引仍仅本地保留，不声称已提交。',
    '逐文件SHA-256见[final.files.json](final.files.json)。该JSON自身不递归计算自己的hash，Git暂存时仍逐字节核验；其余全部路径含本清单及审计均有hash。',
    '按明确路径暂存，命令级core.autocrlf=false，不改变全局配置或原始日志。', '', '|路径|归属|','|---|---|']
for p in paths:
    category='共享验收顶部增量；历史后缀保持' if p in BASE['shared_hashes'] else '已复核496项交付，原字节保持' if p in BASE['reviewed_paths'] else '本次验收新增'
    entries.append(f'|`{p}`|{category}|')
entries+=['','[70项排除清单与hash](exclusions.json) · [验收报告](acceptance-report.md)。推送后的记录另存，不预先冒称已推送。','']
put('final.pending-files.md','\n'.join(entries))

links=[]; secrets=[]; artifacts=[]
future={(ROOT/p).resolve() for p in paths}
for p in paths:
    file=ROOT/p
    if file.suffix in {'.pyc','.whl','.zip'} or any(part in {'__pycache__','Temp','temp'} for part in file.parts):artifacts.append(p)
    if p.startswith('.continuity-data/') or p in {q for rows in BASE['protected'].values() for q in rows}:artifacts.append(p)
    if not file.exists() or file.suffix not in {'.md','.json','.py','.log','.txt'}:continue
    text=file.read_text(encoding='utf8',errors='replace')
    for pattern in [r'gh[pousr]_[A-Za-z0-9]{30,}',r'AKIA[A-Z0-9]{16}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']:
        for m in re.finditer(pattern,text):secrets.append({'path':p,'line':text.count('\n',0,m.start())+1,'pattern':pattern})
    if file.suffix=='.md' and (p.startswith(PREFIX) or p in BASE['shared_hashes']):
        if p in BASE['shared_hashes']:text=text.split('<!-- W04_4_REVIEW_REPAIR_FINAL_20261001 -->',1)[0]
        for target in re.findall(r'\[[^\]\n]+\]\(([^)]+)\)',text):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^(https?:|codex:|mailto:)',target):continue
            destination=pathlib.Path(target) if pathlib.Path(target).is_absolute() else file.parent/target
            if not destination.exists() and destination.resolve() not in future:links.append({'path':p,'target':target})

refs=json.loads((HERE/'test-references.json').read_text(encoding='utf8'))
evidence_ok=True
for row in refs['results']:
    for suffix,h in row['evidence'].items():
        evidence_ok &= sha(ROOT/('docs/project_memory/w04_4_review_repair_evidence/'+row['label']+suffix))==h
    evidence_ok &= row['hash_before']==row['hash_after']==BASE['source_fingerprint'] and row['exit_code']==0
decision_text=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf8')
checks=dict(source_unchanged=source==BASE['source'],branch_main=git('branch','--show-current').strip()=='main',
    head_unchanged=git('rev-parse','HEAD').strip()==BASE['head'],staging_empty=not git('diff','--cached','--name-only').strip(),
    index_unchanged=sha(ROOT/'.git/index')==BASE['index_hash'],reviewed_evidence_unchanged=not old_changed,
    shared_history_preserved=all(history.values()),protected=not any(protected.values()),planning=not plan_mismatches,
    formal_tree_exact=formal==set(BASE['protected']['formalFiles']),retained_70=not retained_mismatches and len(BASE['retained'])==70,
    workspace_scope=not unexpected,precise_range=set(paths)==set(BASE['reviewed_paths'])|{p for p in paths if p.startswith(PREFIX)},
    review_original_copy=sha(BASE['review_original'])==sha(HERE/'independent-readonly-review.json')==BASE['review_original_sha256'],
    source_bound_test_references=evidence_ok,decision_registered_once=decision_text.count('## D-093：')==1,
    document_links=not links,bounded_secret_scan=not secrets,no_sensitive_or_temporary_artifacts=not artifacts)
audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision='D-093',
    stage='W04-4 ACCEPTED; W04 ACCEPTED; W05 NOT_STARTED',checks=checks,
    source_count=len(source),source_fingerprint=source_tools['fingerprint'](source),source=source,
    parent_expected=BASE['head'],branch='main',head=git('rev-parse','HEAD').strip(),local_origin=git('rev-parse','origin/main').strip(),
    actual_remote_before='remote-before.json; must requery before commit/push and after push',
    paths=paths,path_count=len(paths),old_delivery_count=496,new_paths=sorted(set(paths)-set(BASE['reviewed_paths'])),
    original_delivery_changes_outside_shared=old_changed,shared_history_suffix=history,
    protected_counts={g:len(v) for g,v in BASE['protected'].items()},protected_mismatches=protected,
    planning_mismatches=plan_mismatches,retained_count=70,retained_mismatches=retained_mismatches,
    tracked=sorted(tracked),untracked=sorted(untracked),unexpected=unexpected,
    test_results_referenced=refs['results'],tests_executed_this_turn=False,ci='NOT_VERIFIED',
    conflict_scope='Current W04 reviewed acceptance blockers only: NONE; old PRESENT and F1/H1/F2 UNKNOWN retained',
    missing_links=links,secret_findings=secrets,suspect_artifacts=artifacts,
    sensitive_scan_scope='Bounded credential/private-key patterns, not an exhaustive guarantee; synthetic TEST evidence preserved.',
    diff_check_exit=diff.returncode,diff_check_evidence=['diff-check.stdout.log','diff-check.stderr.log'],
    text_line_endings='No normalization performed. Exact index blob comparison required; command-level core.autocrlf=false.',
    git_operations_pending=True,push_result_not_preclaimed=True,
    post_push_record='If saved, outside the repository and explicitly not part of this commit.')
put('final.audit.json',audit)
hashes={p:sha(ROOT/p) for p in paths if p!=PREFIX+'final.files.json'}
put('final.files.json',dict(paths=paths,hashes=hashes,self_hash_omitted=PREFIX+'final.files.json',
    retained=BASE['retained'],source_fingerprint=BASE['source_fingerprint'],decision='D-093',
    content_manifest_fingerprint='sha256:'+hashlib.sha256(json.dumps(hashes,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')).hexdigest()))
print(json.dumps({'checks':checks,'path_count':len(paths),'new_paths':len(set(paths)-set(BASE['reviewed_paths'])),
                  'retained':70,'diff_check_exit':diff.returncode,'source':audit['source_fingerprint']}))
if not all(checks.values()):raise SystemExit(1)
