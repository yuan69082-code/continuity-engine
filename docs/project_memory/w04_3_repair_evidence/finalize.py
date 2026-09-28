"""Archive completed repair evidence. No Engine execution or Git mutation."""
import ast,datetime,hashlib,json,os,pathlib,re,runpy,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).parent
PREFIX=HERE.relative_to(ROOT).as_posix()
def read(path):return json.loads(path.read_text(encoding='utf8'))
def put(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def result(label):
    d=read(HERE/(label+'.json'));err=(HERE/(label+'.stderr.log')).read_text(encoding='utf8')
    found=re.findall(r'Ran (\d+) tests? in ([0-9.]+)s',err)
    row=dict(label=label,status=d['status'],exit_code=d.get('exit_code'),runner_seconds=d.get('duration_seconds'),
             fingerprint_before=d['hash_before'],fingerprint_after=d.get('hash_after'))
    if found:
        n,seconds=found[-1];tail=err[err.rfind('Ran '):]
        counts={k:int(v) for k,v in re.findall(r'(failures|errors|skipped)=(\d+)',tail)}
        row.update(total=int(n),seconds=float(seconds),fail=counts.get('failures',0),error=counts.get('errors',0),skip=counts.get('skipped',0))
        row['pass']=row['total']-row['fail']-row['error']-row['skip']
    return row
base=read(HERE/'baseline.json'); frozen=read(HERE/'frozen-source-01.json')
snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'));source=snap['source']()
assert source==frozen['source'] and not frozen['original_1909_missing'] and not frozen['old_test_changes'] and not frozen['errors']
assert not (HERE/'final.audit.json').exists(),'existing final audit must not be overwritten'
assert git('rev-parse','HEAD').stdout.strip()==base['head'] and git('branch','--show-current').stdout.strip()=='main'
assert not git('diff','--cached','--name-only').stdout and sha(ROOT/'.git/index')==base['index_hash']
changed=[p for p,h in base['source'].items() if source.get(p)!=h]
added=sorted(set(source)-set(base['source']))
assert changed==['src/continuity_engine/services/temporary_tool_service.py'],changed
assert added==['tests/test_w04_3_repairs.py'],added
before=read(HERE/'before-02.json');saved=HERE/'before-tests.py.txt';runtime=changed[0]
assert sha(saved)==before['source_before'][added[0]]
assert before['source_before'][runtime]==before['source_after'][runtime]==base['source'][runtime]
def assertions(path):
    return {n.name:[ast.dump(x,include_attributes=False) for x in ast.walk(n)
                   if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr.startswith('assert')]
            for n in ast.walk(ast.parse(path.read_text(encoding='utf8')))
            if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
old_assertions=assertions(saved);new_assertions=assertions(ROOT/added[0])
correspondence={n:dict(original_assertion_count=len(a),all_retained=set(a)<=set(new_assertions[n])) for n,a in old_assertions.items()}
assert all(r['all_retained'] for r in correspondence.values())
put('counterexample-correspondence.json',dict(saved_before_tests_sha256=sha(saved),matches_before_02=True,
    before_runtime_matches_original_delivery=True,original_counterexample_assertions=correspondence))
protection=[]
for group,files in base['protected'].items():
    for name,h in files.items():
        if not (ROOT/name).is_file() or sha(ROOT/name)!=h:protection.append([group,name])
for name,h in base['retained'].items():
    if not (ROOT/name).is_file() or sha(ROOT/name)!=h:protection.append(['retained',name])
for row in base['planning']:
    if sha(ROOT/row['archivePath'])!=row['archiveSha256']:protection.append(['planning',row['archivePath']])
assert not protection,protection
formal={p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
assert formal==set(base['protected']['formalFiles'])
cleanup=read(HERE/'process-cleanup.json');assert not cleanup['remaining_owned_processes']
labels=['targeted-final-01','w04-3-final-01','w04-12-final-01','compatibility-final-01','full-final-01']
runs=[result(label) for label in labels]
for row in runs:
    assert row['status']=='COMPLETED' and row['exit_code']==0 and row['fail']==row['error']==0,row
    assert row['fingerprint_before']==row['fingerprint_after']==frozen['fingerprint'],row
assert runs[-1]['total']==frozen['test_count'] and runs[-1]['skip']==1
table='| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |\n|---|---|---|---|\n'
for row in runs:
    table+=f"| [{row['label']}]({row['label']}.json) | {row['pass']} / {row['fail']} / {row['error']} / {row['skip']} | {row['seconds']} / {row['runner_seconds']} | {row['exit_code']} |\n"
put('selected-runs.json',dict(fingerprint=frozen['fingerprint'],runs=runs,source='施工方本轮实跑',overlap=True))
matrix=(HERE/'matrix.md').read_text(encoding='utf8')
matrix=matrix.replace('各条最终状态待同版验证后由交付报告确认；此表不是验收决定。','各条状态IMPLEMENTED_NOT_ACCEPTED；定点及以下最终同版集合已通过，但不等于正式验收。')
(HERE/'matrix.md').write_text(matrix+'\n## 最终同版验证对应\n\n'+table+'\n上述组均绑定frozen-source-01.json；集合交叠不相加，原初版结果不替代本轮。尚未独立确认，EVIDENCE_CONFLICT继续PRESENT。\n',encoding='utf8')
history=[]
for p in sorted(HERE.glob('*.json')):
    d=read(p)
    if isinstance(d,dict) and 'label' in d and 'command' in d and (HERE/(d['label']+'.stderr.log')).exists():history.append(result(d['label']))
put('test-history.json',history)
index='# W04-3 R1/R2 原始测试索引\n\n以下为施工方本轮实跑，集合交叠不相加；规划窗口此前是静态复核，不是独立实跑。没有远端CI结果。\n\n'+table
index+=f"\n全部最终集合绑定{len(source)}个源码/测试/资源文件 `{frozen['fingerprint']}`；正式身份{frozen['test_count']}=原1909+新增14。原测试文件字节及身份完全保留。\n"
for label in labels:
    index+=f'\n- [{label}命令/退出码/耗时/前后清单]({label}.json)、[stdout]({label}.stdout.log)、[stderr]({label}.stderr.log)。\n'
index+='''
## 历史与复跑

[test-history.json](test-history.json)逐次保留修前、修后、辅助错误及旧版本结果。before-02是两个有效修前FAIL；before-01含辅助夹具ERROR，不冒充同等证据。各次解释见[investigations.md](investigations.md)。这些记录不被最终通过覆盖。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine;C:/Users/Administrator/Documents/continuity-engine/src;C:/Users/Administrator/Documents/continuity-engine/tests'
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_repairs
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_tools tests.test_w04_3_repairs
& 'E:/Adobe/python.exe' -m unittest discover -s tests -v
```

其余组精确模块及顺序见对应JSON.command；保存新复跑时可用run.py加未使用标签，再跟同样参数。不得复用/覆盖本轮标签。最终全量仅运行一次。Windows1314 SKIP仍为SKIP，不算PASS。
'''
(HERE/'test-index.md').write_text(index,encoding='utf8')
rows=[]
for line in (HERE/'targeted-final-01.stdout.log').read_text(encoding='utf8').splitlines():
    try:d=json.loads(line)
    except ValueError:continue
    if d.get('label') in {'R1-native-and-tools','R1-mixed-waits','R2-before-stop','R1-UNKNOWN'}:
        rows.append({k:d[k] for k in ('label','tasks','connections','effects','credits','native_calls','revision','discovery_calls')})
put('chain-example.json',dict(source='targeted-final-01.stdout.log; unchanged selected fields',fingerprint=frozen['fingerprint'],observations=rows))
(HERE/'chain-example.md').write_text('''# 同一宿主的可追溯样例

数据从[targeted-final-01.stdout.log](targeted-final-01.stdout.log)按字段摘录，非预填结果：[请求、任务、步骤及回执hash](chain-example.json)。

- R1-native-and-tools：首工具LOGIN等待；第二工具沿原已接入事实完成一次业务和清理。真实native认知1次、revision=2、原维护任务完成，模拟业务效果1/费用1 TEST credit。新use/close有当前Context，旧connect未重绑。
- R1-mixed-waits：一个连接仍PARTIAL待清理，一个缺依赖，后面可执行连接完成；业务效果1/费用1。等待项仍如实等待，没有将失败改成功。
- R1-UNKNOWN：首连接结果仍UNKNOWN，没有创建其模拟连接；后一连接完成效果1/费用1。未知原请求未盲重放。
- R2-before-stop：原连接保留三份FAILED清理回执，条件恢复后第四份清理CLOSED，旧请求及回执不丢失，模型0、业务效果0、费用0。其他自动PARTIAL/重开与退避验证见正式测试。

本机TEST的连接/验证/清理费用为0，业务动作1 TEST credit；沿原回执/资源核验，不是现实预算或任意Provider成本保证。只读状态可从原inspect查看投影，查看不是Scheduler.query恢复调用，不执行业务。
''',encoding='utf8')
report=f'''# W04-3 R1/R2 定点返修交付

状态 **IMPLEMENTED_NOT_ACCEPTED**。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，等待独立复核与用户决定，未自行关闭阻断。W04整体IN_PROGRESS，W04-4未启动；D-090仍仅开工授权。

## 根因与实际修复

静态复核线索经施工方before-02两个真实宿主反例复现：首个缺登录工具使后项永不入队；三份明确失败清理后自动路径不再续做。修前2 FAIL/0 ERROR，STOP前的任务、原请求、回执、效果和费用保存在原stdout。同反例修后通过，新增14项覆盖同时native工作、重开、UNKNOWN、部分清理、退避、控制和当前权限。

R1删除固定native首项/工具首项截取，读取原Scheduler已拥有身份，只为尚未入队的原需求提供本轮最多两个名额；原Scheduler仍管理既有等待、派发、资源和恢复。R2去掉连接全生命周期三次清理上限，每次advance最多一个清理，用上一份自动清理原回执时间退避，默认复用P18的5秒，可配置；条件变化、原授权和原资源逐次重查。UNKNOWN查询原事实，成功不重复，失败历史不删除。

运行只改temporary_tool_service.py，新增tests/test_w04_3_repairs.py；原测试文件、Scheduler、P18控制、资源/费用及其他运行文件相对本轮开工版无改动。没有第二队列、状态权威、请求或结果账本。原初版142成果全部保留。详细条目见[矩阵](matrix.md)、[恢复语义](recovery-semantics.md)。

## 同版验证

源码/测试/资源{len(source)}项，`{frozen['fingerprint']}`。正式身份{frozen['test_count']}，原1909保留，新增14。以下均为本轮施工方实跑，集合重叠不相加；不是规划窗口独立实跑或远端CI。

{table}

命令、原始stdout/stderr、退出码、时长、运行前后逐文件hash见[测试索引](test-index.md)。修前失败及中间辅助ERROR、正确Context拒绝、未知结果均见[调查记录](investigations.md)，没有被后续PASS覆盖。最终完整回归一次，Windows1314 SKIP不计PASS。

## 保留边界与限制

同时存在native认知、维护与工具的正向场景实际取得认知revision和工具结果；不是关闭native或手工逐个advance冒充调度。旧Context在认知推进后仍正确拒绝。正常新步骤由原Wake/Perception/C1取得当前Context，不能靠本修补自动重绑旧请求。测试新生产器曾选入随后失效的临时结果而正确阻断，这些失败与辅助错误原样保留；任意调用方仍需提供当前有效Context。

等待/退避不会关闭整个主体；PAUSE/STOP、旧host失权与生命周期照旧。没有固定运行寿命或忙循环。原Scheduler容量、预算与当前资格仍可阻断，本机有限组合不证明任意无界任务公平性、生产性能或真实服务质量。

清理失败可在当前条件满足后继续，不代表无条件必能清理或过期使用复活。本机TEST业务效果/费用各一次，清理0成本为明确隔离配置；不替用户制定现实预算。真实账号、设备、生产凭据/服务、W04-4、W05及P19未开放。

历史F1/H1/F2仍UNKNOWN；原cProfile超时、旧失败/中断/格式提示和既有SKIP全部保留。原W02 1000毫秒、指定历史2048预算、P18控制等待未放宽。W04-1/2及其他历史验收不改。

## 复核入口与现场

[精确累计清单](final.pending-files.md) · [hash清单](final.files.json) · [本轮增量](repair-delta.json) · [70项保留](exclusions.json) · [终局审计](final.audit.json) · [进程收尾](process-cleanup.json) · [真实链路](chain-example.md)。

HEAD/main仍为{base['head']}；未验收、未暂存、未提交或push。实际远端只引用初版remote-read-01的当时查询，本返修未取得新的远端/CI结果，不以本地origin/main冒充实时远端，也不宣称CI PASS。下一步仅独立复核。
'''
(HERE/'final-report.md').write_text(report,encoding='utf8')
summary='；'.join(f"{r['label']} {r['pass']} PASS/{r['skip']} SKIP" for r in runs)
section=f'''<!-- W04_3_R1_R2_DELIVERY -->
## 2026-09-29 W04-3 R1/R2返修交付，待独立复核

用户授权范围内完成等待首项入队饥饿与固定三次清理封顶两项定点修复。静态线索经before-02真实P18/Scheduler反例证实2 FAIL；本轮只修改temporary_tool_service.py并新增14项正式回归，原1909测试身份和旧断言保持。原native认知/维护保留，两个need上限、当前权限/Context/host及PAUSE/STOP/资源/E5-A不变。UNKNOWN先查原事实，无重复业务或扣费，清理退避取原回执时间、默认P18的5秒，不是永久关闭主体。

施工方最终同版：{summary}，FAIL/ERROR均0，集合交叠不相加。源码{len(source)}项 `{frozen['fingerprint']}`。规划窗口先前是静态阅读，不冒称独立实跑；无远端CI证据。

W04-3 IMPLEMENTED_NOT_ACCEPTED，W04整体IN_PROGRESS；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，尚待独立复核，不登记用户验收。原142项成果和失败记录保留；新辅助错误、正确旧Context拒绝另列。历史F1/H1/F2 UNKNOWN、原SKIP/中断/cProfile超时照留。63保护、正式7文件、现行3规划、版本及70保留材料按本轮审计核对。未暂存、提交、push；W04-4未启动。

[返修报告](w04_3_repair_evidence/final-report.md) · [矩阵](w04_3_repair_evidence/matrix.md) · [原始测试](w04_3_repair_evidence/test-index.md) · [清单](w04_3_repair_evidence/final.pending-files.md) · [审计](w04_3_repair_evidence/final.audit.json)。下文旧时点记录原样保留，旧状态不代表当前结论。

'''
shared=['docs/project_memory/'+x for x in ['01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md']]
for name in shared:
    p=ROOT/name;b=p.read_bytes();assert b'<!-- W04_3_R1_R2_DELIVERY -->' not in b;p.write_bytes(section.encode('utf8')+b)
for name in ['README.md','docs/project_memory/CHANGELOG.md']:
    p=ROOT/name;b=p.read_bytes();assert b'<!-- W04_3_R1_R2_DELIVERY -->' not in b
    ref='docs/project_memory/w04_3_repair_evidence/final-report.md' if name=='README.md' else 'w04_3_repair_evidence/final-report.md'
    p.write_bytes(f'<!-- W04_3_R1_R2_DELIVERY -->\n## W04-3 R1/R2返修，待复核\n\n等待工具不再固定阻挡后项与原认知/维护；清理按原事实退避，取消累计三次永久封顶。状态IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT，原控制/权限/账本保持。见[本轮报告]({ref})。无验收或Git写入，W04-4未启动。\n\n'.encode('utf8')+b)
(HERE/'continuation.md').write_text('本轮R1/R2施工与最终同版验证已结束，结果以final-report.md、test-index.md、final.audit.json为准。无需恢复旧session或重跑已有标签。保持IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，下一步独立复核；未验收/暂存/提交/push，未启动W04-4。历史及中间失败全部保留。\n',encoding='utf8')
with (HERE/'repair-progress.md').open('a',encoding='utf8') as progress:
    progress.write('\n## 最终完成记录\n\n'+datetime.datetime.now(datetime.timezone.utc).isoformat()+'：上述最终五组均已COMPLETED、exit0、同版，实际计数见test-index.md。finalize.py依据完成记录生成交付，不将早期运行中状态倒改。测试进程收尾见process-cleanup.json；后续只等待独立复核，不再启动测试或下一批。\n')
put('exclusions.json',base['retained'])
allowed_changed=set(shared)|{'README.md','docs/project_memory/CHANGELOG.md','src/continuity_engine/services/temporary_tool_service.py'}
oldchanged=[p for p,h in base['previous_hashes'].items() if sha(ROOT/p)!=h]
assert not set(oldchanged)-allowed_changed,oldchanged
history_bad=[]
for p in shared+['README.md','docs/project_memory/CHANGELOG.md']:
    b=(ROOT/p).read_bytes();where=b.find(b'<!-- W04_3_DELIVERY -->')
    if where<0 or hashlib.sha256(b[where:]).hexdigest()!=base['previous_hashes'][p]:history_bad.append(p)
assert not history_bad,history_bad
artifacts={'final.pending-files.md','final.files.json','final.audit.json','final.git-status.txt','final.diff-check.txt','repair-delta.json'}
for name in artifacts:(HERE/name).touch(exist_ok=False)
working=set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
assert set(base['retained'])<=working
delivery=sorted(working-set(base['retained']))
new=sorted(set(delivery)-set(base['previous_paths']))
assert all(p==added[0] or p.startswith(PREFIX+'/') for p in new),new
assert set(base['previous_paths'])<=set(delivery)
put('repair-delta.json',dict(original_delivery_count=len(base['previous_paths']),original_paths=base['previous_paths'],
    original_modified=oldchanged,new_paths=new,implementation_changed=changed,formal_tests_added=added,
    original_evidence_unchanged=True,original_test_assertions_unchanged=True,shared_historical_suffix_unchanged=True))
diff=git('diff','--check');(HERE/'final.diff-check.txt').write_text('exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr,encoding='utf8')
status=git('status','--short','--untracked-files=all');(HERE/'final.git-status.txt').write_text(status.stdout+status.stderr,encoding='utf8')
syntax=[];links=[];secret=[]
for name in set(source)|{p for p in delivery if p.endswith('.py')}:
    if name.endswith('.py'):
        try:ast.parse((ROOT/name).read_text(encoding='utf-8-sig'))
        except (SyntaxError,UnicodeError) as exc:syntax.append([name,type(exc).__name__])
pattern=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
for name in delivery:
    content=(ROOT/name).read_text(encoding='utf8',errors='replace')
    if pattern.search(content):secret.append(name)
    if name.startswith(PREFIX+'/') and name.endswith('.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',content):
            ref=unquote(ref.split('#',1)[0].strip('<>'))
            if ref and not ref.startswith(('http:','https:','mailto:')) and not (ROOT/name).parent.joinpath(ref).exists():links.append([name,ref])
cyclic={PREFIX+'/'+n for n in ['final.pending-files.md','final.files.json','final.audit.json']}
hashes={p:sha(ROOT/p) for p in delivery if p not in cyclic}
(HERE/'final.pending-files.md').write_text('# W04-3累计精确成果（未暂存）\n\n共'+str(len(delivery))+'项，原142项加本轮必要增量；70保留材料全部排除。共享文档仅顶部新增本轮记录，历史后缀字节不变。逐项归属见repair-delta.json。三份互引审计/清单不做循环hash；audit保存另外两份最终hash。\n\n| 路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+hashes.get(p,'SELF_REFERENTIAL_MANIFEST')+'` |' for p in delivery)+'\n',encoding='utf8')
put('final.files.json',dict(count=len(delivery),paths=delivery,hashes=hashes,self_reference_exclusions=sorted(cyclic)))
audit=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='IMPLEMENTED_NOT_ACCEPTED',planning_conflict='NONE',evidence_conflict='PRESENT',
    branch='main',head=base['head'],local_origin=git('rev-parse','origin/main').stdout.strip(),actual_remote='not queried this repair; initial delivery remote-read-01 remains historical only',
    ahead_behind_local_tracking=git('rev-list','--left-right','--count','HEAD...origin/main').stdout.strip(),index_unchanged=sha(ROOT/'.git/index')==base['index_hash'],staged=[],git_mutations=False,
    source_count=len(source),source_fingerprint=frozen['fingerprint'],source_equals_all_final_runs=True,test_count=frozen['test_count'],old_1909_missing=[],old_test_files_changed=[],new_test_count=len(frozen['new_ids']),
    runtime_changes_from_repair_baseline=changed,new_source_paths=added,runs=runs,
    protected_counts={k:len(v) for k,v in base['protected'].items()},protection_changes=protection,current_plans_count=3,formal_count=len(formal),formal_tree_exact=True,retained_count=len(base['retained']),retained_changes=[],
    original_delivery_count=len(base['previous_paths']),original_evidence_unchanged=True,shared_history_suffix_changes=history_bad,delivery_count=len(delivery),repair_new_count=len(new),
    syntax_errors=syntax,new_document_broken_links=links,sensitive_pattern_hits=secret,sensitive_scan_scope='bounded credential/private-key patterns; explicit TEST markers retained, no claim of universal detection',
    diff_check_exit=diff.returncode,diff_check_evidence='final.diff-check.txt',historical_warnings='Old logs and format warnings preserved; LF/CRLF notices are not functional test failures',
    process_evidence='process-cleanup.json',ci='No remote CI run/check obtained; no PASS claim',
    pending_files_sha256=sha(HERE/'final.pending-files.md'),files_json_sha256=sha(HERE/'final.files.json'))
put('final.audit.json',audit)
print(json.dumps({k:audit[k] for k in ['delivery_count','repair_new_count','source_count','source_fingerprint','test_count','syntax_errors','new_document_broken_links','sensitive_pattern_hits','diff_check_exit']},ensure_ascii=False))
assert not syntax and not links and not secret,'AUDIT_REQUIRES_REVIEW'
