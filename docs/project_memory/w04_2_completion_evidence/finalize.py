"""Document completed runs and exact workspace identity. Never run tests or Git writes."""
import ast,datetime,hashlib,json,pathlib,re,runpy,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
S=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8')
base=read(HERE/'baseline.json');frozen=read(HERE/'frozen-source-01.json')
source=S['source']()
assert source==frozen['source'],'SOURCE_CHANGED'
assert not (HERE/'final.audit.json').exists(),'FINAL_LABEL_EXISTS'
cleanup=read(HERE/'process-cleanup.json')
assert not cleanup['remaining_test_processes'],'PROCESS_STILL_RUNNING'
labels=['targeted-final-01','recall-formal-final-01','recall-load-final-01','special-final-01','compatibility-final-01','full-final-01']
runs=[]
for label in labels:
    value=read(HERE/(label+'.json'));assert value['status']=='COMPLETED'
    assert value['hash_before']==value['hash_after']==frozen['fingerprint']
    err=(HERE/(label+'.stderr.log')).read_text(encoding='utf8')
    n,seconds=re.findall(r'Ran (\d+) tests? in ([0-9.]+)s',err)[-1]
    counts={k:int(v) for k,v in re.findall(r'(failures|errors|skipped)=(\d+)',err.split('Ran ')[-1])}
    row=dict(label=label,total=int(n),fail=counts.get('failures',0),error=counts.get('errors',0),skip=counts.get('skipped',0),seconds=float(seconds),runner_seconds=value['duration_seconds'],exit_code=value['exit_code'])
    row['pass']=row['total']-row['fail']-row['error']-row['skip'];runs.append(row)
    assert value['exit_code']==0,'FAILED_GROUP_REQUIRES_ANALYSIS'
table='| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |\n|---|---|---|---|\n'
for r in runs:
    table+=f"| [{r['label']}]({r['label']}.json) | {r['pass']} / {r['fail']} / {r['error']} / {r['skip']} | {r['seconds']} / {r['runner_seconds']} | {r['exit_code']} |\n"
index='# 同版测试索引\n\n全部为施工方本轮实跑；集合交叠，不相加。规划窗口未运行这些测试，无远端CI结论。正常正式测试没有cProfile或前轮计时包装；原重度插桩超时保留，未增加“所有插桩也必须1秒内”的验收要求。\n\n'+table
for r in runs:
    label=r['label'];index+=f'\n- [{label} stdout]({label}.stdout.log) / [stderr]({label}.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。\n'
index+='''
## 修前与中间记录（不可代替最终版）

- history-before-01：1 ERROR，新增夹具长路径导致setUp临时文件失败，尚未到目标反例。
- history-before-02：1 ERROR，新增测试误用不合法斜线身份，被原契约正确拒绝。
- history-before-03：1个测试、2个子断言ERROR；同一回执正序/反序都被裁掉，真实修前证据，不能写成负PASS。
- targeted-after-01：30项，26 PASS/4 ERROR；四个新增拒绝断言的异常类型错误，实际原消费边界正确返回DEVICE_SOURCE_NOT_CURRENT。随后新测试改为核对确切类型和静态码，产品拒绝未改。
- targeted-after-02：31 PASS；最终优先级改为保留其他候选原评分并新增对应回归，因此此组仅为中间证据。
- 前轮锁受控1FAIL/1ERROR、cProfile修后1PASS/1ERROR、专项业务错误与导入错误均保留在 ../w04_2_public_repair_evidence/；未倒改。

复跑命令：使用各JSON的command，在仓库根设置PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1、PYTHONPATH为根/src/tests。证据runner仅接受未占用标签；不要直接重用已完成标签或validate_fixed.py覆盖记录。全量命令为 E:/Adobe/python.exe -m unittest discover -s tests -v。
'''
(HERE/'test-index.md').write_text(index,encoding='utf8')
report=f'''# W04-2 公共验证定点处理完成报告

状态 IMPLEMENTED_NOT_ACCEPTED，交独立复核。用户本次已授权P18测试同步与历史回执选择修补；此前对应工程选择已解除等待，无新PLANNING_CONFLICT。EVIDENCE_CONFLICT=PRESENT表示本轮证据尚待独立确认，不自行验收或关闭复核门。W04-3未开工。

## 根因、范围与实际变化

1. **W02（保留前轮修补）**：外部注册仓储每次路径安全检查对同一文件/祖先做三次元数据查询；_safe已合为一次当前lstat。当前源码该文件与本轮开工基线完全一致；D-084原读取复用实际有效，未删除授权、来源、版本、损坏检查或复制隔离，原1000ms和材料不变。两种原负载、五个原失败场景在正常正式测试中复核。旧cProfile四份场景超时仍是保留的重度观察结果，不把它算通过，也不新增对所有插桩条件的1秒保证。历史五次瞬时差异不能全部唯一归因到该机制。
2. **P18测试时序**：两个独立占用区间应分别报一次BUSY；owner存活不等于attach事务已完成。只改tests/test_p18_runtime_contention.py获准两项及必要测试辅助，产品实现未改。真实子进程通过原runtime.main启动，TEST hook在原事务释放后发attach标记；两次真实PAUSE/STOP占用分别严格核对一条BUSY及解除后一条AVAILABLE。STOP用同一身份，在原15秒控制观察期限（含退出）内只重试RuntimeCheckpointBusy；每次忙时核对未提交，成功后检查幂等、终态、无效果/费用/revision重复、重启不复活。新增3项稳定覆盖attach持锁STOP拒绝、实际忙后释放再重试、非忙错误立即透传。未改0.25秒、owner、CAS、权限或主体寿命。
3. **W04指定回执**：旧history_context只按对象检索，两个同根回执同分时按ID排序，2048预算保留一个，恰好裁掉目标就正确拒绝返回。正式双目标反例正反序证实。只改device_operation_service.py与execution_context_source.py：用原Router查询身份绑定指定请求的固定长度摘要；来源仍从原E5-A取当前可核验结果，先选指定目标，并只提高其查询候选评分，其他候选评分/冲突/根材料保持；原Router排序及Composer核心保护、去重、裁剪、2048预算继续执行。目标本身装不下仍拒绝；过期、撤权、途中撤权、材料撤回仍返回原静态拒绝。普通未定向查询保持原评分与入口，无跨请求缓存/第二账本。

新9项历史选择测试经过实际query动作回执、DeviceOperationService、Router、Composer入口，包含目标互换和不同合法ID、重开/重复、预算不足、失权/期间失权/过期、同根撤回及原非定向路线。只读检查使用持久树hash、状态revision、效果和费用对照；没有以其他同根回执冒充指定目标。

## 同版结果与来源

固定源码/测试/资源{len(source)}项：`{frozen['fingerprint']}`；{frozen['test_count']}项正式身份，原1851项保留，新增12项（历史9、P18受控3）。原两项测试是本次用户明确批准的同步及区间断言修正；原全文与hash在baseline及before.txt，其他旧正式断言未改。

{table}

这些集合交叠，不相加。完整回归的唯一SKIP为原Windows符号链接权限1314，原始原因见stderr；无新增SKIP。完整回归仅此一次，之前没完成/失败/插桩记录不会升级为PASS。规划窗口只读复核不冒称独立实跑。

## 范围和限制

历史F1/H1/F2根因仍UNKNOWN，原验收不撤回，也不因本次通过唯一归因旧失败。本机隔离TEST证明所覆盖工程链；其他设备、更大负载、真实语言效果、生产性能、真实设备/账号均未验收。W04-3/4、W05、P19及生产恢复/接入按原阶段未开放。没有远端CI证据；本轮没有远端查询或Git写操作，不把本地origin/main当实际远端。

[逐项矩阵](matrix.md) · [原始测试索引](test-index.md) · [固定源码与身份](frozen-source-01.json) · [精确清单](final.pending-files.md) · [终局审计](final.audit.json) · [进程清理](process-cleanup.json)。所有原始失败与辅助错误原样保留。下一步仅为独立复核与用户确认。
'''
(HERE/'final-report.md').write_text(report,encoding='utf8')
(HERE/'matrix.md').write_text('''# Planning Item → Code Change → Test → Acceptance Result

| Planning Item | Code Change | Test | Acceptance Result |
|---|---|---|---|
| P18有限等待/持续宿主/STOP | 两项获准测试同步与BUSY区间修正；新增3受控；产品不变 | targeted-final；compatibility-final；full-final，原锁反例记录保留 | IMPLEMENTED_NOT_ACCEPTED，待独立复核 |
| W04/N21指定历史回执、T66/T67/T72/T18 | 原Router request_id绑定及执行来源目标排序；不扩2048预算 | history-before-03修前；新9项正反及原42项中的同根/撤回/恢复 | IMPLEMENTED_NOT_ACCEPTED |
| N13/N10、T27—T29/T37/T85—T87 | 原W04-2实现保留 | W04-2原42项同版专项及全量 | IMPLEMENTED_NOT_ACCEPTED |
| W02/N02/T03—T06 | 保留_safe单次当前元数据检查优化 | 五原失败场景、原四资料与第三轮16检索；原1000ms | IMPLEMENTED_NOT_ACCEPTED，本机正式链通过，不宣称任意负载 |
| W04-1已验收三处边界 | 无改动 | 专项原29项及全量 | D-087历史ACCEPTED保留 |
| 旧模块/唯一权威/来源/权限/恢复 | 不改公共Router/Composer及P18运行语义 | 公共兼容及完整回归 | 本轮证据待复核，不新增历史验收 |

无新规划冲突；本次用户已批准前轮两项待决定方案。EVIDENCE_CONFLICT继续PRESENT直到独立确认。原矩阵与中间结果不覆盖。
''',encoding='utf8')
shared=['docs/project_memory/'+n for n in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md')]
summary='；'.join(f"{r['label']} {r['pass']}PASS/{r['fail']}FAIL/{r['error']}ERROR/{r['skip']}SKIP" for r in runs)
section=f'''<!-- W04_2_COMPLETION_DELIVERY -->
## W04-2 两项定点处理与公共同版验证完成，等待独立复核

用户批准的P18两项测试已改为attach释放同步、逐忙区间严格计数及同身份有限STOP重试，产品0.25秒/唯一宿主/CAS/权限/终态不变。W04-2指定回执经原Router/Composer获得查询优先级，其他候选与必要核心保留、2048预算不变。W02文件检查优化保留，1000ms/原负载未变。

施工方同版实跑：{summary}。集合交叠不相加；完整回归仅一次，Windows1314原SKIP保留。源码{len(source)}项 `{frozen['fingerprint']}`，原1851身份保留，新增12。新辅助路径/身份/异常类型错误及真实修前反例全部保留；旧cProfile超时与F1/H1/F2 UNKNOWN不倒改。

W04-2 IMPLEMENTED_NOT_ACCEPTED；此前两个工程选择由本次授权明确，现无新PLANNING_CONFLICT；EVIDENCE_CONFLICT=PRESENT，等待独立复核，不自行验收/创建验收决定。70保留、保护/正式数据/规划均按清单核对；无Git写入/远端CI结论/W04-3开工。

[交付报告](w04_2_completion_evidence/final-report.md) · [矩阵](w04_2_completion_evidence/matrix.md) · [测试索引](w04_2_completion_evidence/test-index.md) · [精确清单](w04_2_completion_evidence/final.pending-files.md) · [审计](w04_2_completion_evidence/final.audit.json)。下文保持各时点历史。

'''
for name in shared:
    p=ROOT/name;text=p.read_text(encoding='utf8');assert '<!-- W04_2_COMPLETION_DELIVERY -->' not in text
    p.write_text(section+text,encoding='utf8',newline='')
(HERE/'exclusions.json').write_text(json.dumps(base['retained'],ensure_ascii=False,indent=2),encoding='utf8')
(HERE/'continuation.md').write_text('W04-2本次两项获准定点处理和同版验证已完成，等待独立复核。先读final-report.md、final.audit.json；不得重启已完成测试或覆盖标签。未验收、Git写入或W04-3。历史原始证据在本目录及前轮w04_2_public_repair_evidence中保留。\n',encoding='utf8')
allowed={'src/continuity_engine/services/device_operation_service.py','src/continuity_engine/services/execution_context_source.py','tests/test_p18_runtime_contention.py','tests/test_w04_2_history_selection.py'}|set(shared)
new_prefix=HERE.relative_to(ROOT).as_posix()
artifacts={new_prefix+'/'+n for n in ('final.pending-files.md','final.files.json','final.audit.json','final.git-status.txt','final.diff-check.txt')}
paths=sorted(set(base['previous_delivery'])|allowed|{p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()}|artifacts)
assert not set(paths)&set(base['retained'])
for name in artifacts:
    (ROOT/name).touch(exist_ok=False)
diff=git('diff','--check');(HERE/'final.diff-check.txt').write_text('exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr,encoding='utf8')
status=git('status','--short','--untracked-files=all');(HERE/'final.git-status.txt').write_text(status.stdout+status.stderr,encoding='utf8')
ledger_files={new_prefix+'/'+n for n in ('final.pending-files.md','final.files.json','final.audit.json')}
hashes={p:sha(p) for p in paths if p not in ledger_files}
(HERE/'final.pending-files.md').write_text('# W04-2累计精确交付清单（未暂存）\n\n共'+str(len(paths))+'项；原194项保留并仅修改授权共享档案/接线。本轮增量明确在本目录、两接线文件、一原测试文件及一新测试文件。70项保留另见exclusions.json，不夹带。以下逐路径sha256；三份互相引用的清单/审计文件不作循环hash，final.audit包含前两份的hash。\n\n| 路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+hashes.get(p,'SELF_REFERENTIAL_MANIFEST')+'` |' for p in paths)+'\n',encoding='utf8')
(HERE/'final.files.json').write_text(json.dumps(dict(count=len(paths),paths=paths,hashes=hashes,self_reference_exclusions=sorted(ledger_files)),ensure_ascii=False,indent=2),encoding='utf8')
syntax=[];links=[];secret=[]
for p in [*source,*[v for v in paths if v.startswith(new_prefix) and v.endswith('.py')]]:
    if p.endswith('.py'):
        try:ast.parse((ROOT/p).read_text(encoding='utf8'))
        except (SyntaxError,UnicodeError) as exc:syntax.append([p,type(exc).__name__])
pattern=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
for p in paths:
    text=(ROOT/p).read_text(encoding='utf8',errors='replace')
    if pattern.search(text):secret.append(p)
    if p.startswith(new_prefix) and p.endswith('.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',text):
            ref=unquote(ref.split('#',1)[0].strip('<>'))
            if ref and not ref.startswith(('http:','https:','mailto:')) and not (ROOT/p).parent.joinpath(ref).exists():links.append([p,ref])
working=set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=git('rev-parse','HEAD').stdout.strip(),branch=git('branch','--show-current').stdout.strip(),local_origin=git('rev-parse','origin/main').stdout.strip(),actual_remote='NOT_QUERIED_THIS_TURN',staged=git('diff','--cached','--name-only').stdout.splitlines(),source=source,source_count=len(source),fingerprint=S['fingerprint'](source),test_count=frozen['test_count'],original_test_ids_missing=frozen['old_1851_missing'],source_matches_frozen=source==frozen['source'],
    changed_from_turn_baseline=[p for p,h in base['source'].items() if source.get(p)!=h],new_source_files=sorted(set(source)-set(base['source'])),
    prior_delivery_changed_outside_authorization=[p for p,h in base['previous_delivery'].items() if p not in allowed and sha(p)!=h],
    protected_mismatches={k:[p for p,h in values.items() if sha(p)!=h] for k,values in base['protected'].items()},
    planning_mismatches=[x['archivePath'] for x in base['planning'] if sha(x['archivePath'])!=x['archiveSha256']],retained_count=len(base['retained']),retained_mismatches=[p for p,h in base['retained'].items() if sha(p)!=h],
    history_tails_unchanged={p:(ROOT/p).read_text(encoding='utf8').replace('\r\n','\n').endswith(git('show',base['checks']['head']+':'+p).stdout.replace('\r\n','\n')) for p in shared},
    syntax_errors=syntax,missing_links=links,high_confidence_secret_findings=secret,diff_check_exit=diff.returncode,delivery_count=len(paths),delivery_paths=paths,delivery_hashes_excluding_audit={p:sha(p) for p in paths if p!=new_prefix+'/final.audit.json'},unexpected_working_paths=sorted(working-set(paths)-set(base['retained'])),runs=runs,process_cleanup=cleanup,git_write_operations=False,remote_ci='NOT_VERIFIED')
(HERE/'final.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:audit[k] for k in ('fingerprint','source_count','test_count','delivery_count','staged','changed_from_turn_baseline','new_source_files','prior_delivery_changed_outside_authorization','protected_mismatches','retained_mismatches','syntax_errors','missing_links','unexpected_working_paths')},ensure_ascii=False))
