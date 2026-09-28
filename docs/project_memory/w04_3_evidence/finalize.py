"""Archive observed results and audit only. No tests, service launch or Git mutation."""
import ast,datetime,hashlib,json,pathlib,re,runpy,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
PREFIX=HERE.relative_to(ROOT).as_posix()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def put(name,value):
    p=HERE/name
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8')
base=read(HERE/'baseline.json');frozen=read(HERE/'frozen-source-03.json')
snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'));source=snap['source']()
assert source==frozen['source'] and not frozen['old_1863_missing'] and not frozen['discovery_errors']
assert not (HERE/'final.audit.json').exists(),'use a new label for a later audit'
assert git('rev-parse','HEAD').stdout.strip()==base['head'] and git('branch','--show-current').stdout.strip()=='main'
assert not git('diff','--cached','--name-only').stdout
protected_changes=[]
for group,files in base['protected'].items():
    for name,h in files.items():
        if not (ROOT/name).is_file() or sha(name)!=h:protected_changes.append([group,name])
for name,h in base['retained'].items():
    if sha(name)!=h:protected_changes.append(['retained',name])
for row in base['planning']:
    if sha(row['archivePath'])!=row['archiveSha256']:protected_changes.append(['current_planning',row['archivePath']])
assert not protected_changes,protected_changes
formal_tree={p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
assert formal_tree==set(base['protected']['formalFiles']),'FORMAL_TREE_CHANGED'
cleanup=read(HERE/'process-cleanup.json')
assert not cleanup['remaining_owned_processes'],'owned test process remains'
labels=['targeted-final-02','special-final-02','compatibility-final-02','full-final-01']
runs=[]
for label in labels:
    d=read(HERE/(label+'.json'));assert d['status']=='COMPLETED' and d['exit_code']==0,label
    assert d['hash_before']==d['hash_after']==frozen['fingerprint'],label
    err=(HERE/(label+'.stderr.log')).read_text(encoding='utf8')
    matches=re.findall(r'Ran (\d+) tests? in ([0-9.]+)s',err);assert matches,label
    n,seconds=matches[-1];counts=dict((k,int(v)) for k,v in re.findall(r'(failures|errors|skipped)=(\d+)',err.split('Ran ')[-1]))
    row=dict(label=label,total=int(n),fail=counts.get('failures',0),error=counts.get('errors',0),skip=counts.get('skipped',0),
             seconds=float(seconds),runner_seconds=d['duration_seconds'],exit_code=d['exit_code'])
    row['pass']=row['total']-row['fail']-row['error']-row['skip'];runs.append(row)
assert runs[-1]['total']==frozen['test_count'] and runs[-1]['skip']==1
table='| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |\n|---|---|---|---|\n'
for row in runs:
    table+=f"| [{row['label']}]({row['label']}.json) | {row['pass']} / {row['fail']} / {row['error']} / {row['skip']} | {row['seconds']} / {row['runner_seconds']} | {row['exit_code']} |\n"
put('selected-runs.json',dict(fingerprint=frozen['fingerprint'],runs=runs,overlap=True,source='施工方本轮实跑'))
index='# W04-3 原始测试索引\n\n全部为施工方本轮实跑，集合交叠不相加。规划窗口尚未独立复核，也没有远端 CI 结果。旧1863项身份和原测试文件字节保持；新增46项。\n\n'+table
for label in labels:
    index+=f'\n- [{label} stdout]({label}.stdout.log)、[stderr]({label}.stderr.log)、[命令/退出码/耗时/前后完整源码]({label}.json)。\n'
index+='''
## 可复跑入口

仓库根使用 E:/Adobe/python.exe，设置 PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1，PYTHONPATH 包含仓库根、src、tests。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine;C:/Users/Administrator/Documents/continuity-engine/src;C:/Users/Administrator/Documents/continuity-engine/tests'
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_tools
& 'E:/Adobe/python.exe' -m unittest discover -s tests -v
```

其他组精确模块及顺序见对应 JSON 的 command。若归档新结果，用 run.py 的新唯一标签；不得覆盖现有标签，也不要重执行 validate-final.py 冒充原实跑。

修前缺口与中间失败见 [调查记录](investigations.md)。其中 before-01 为缺能力取证；observe-before/after 为同一观察到期反例；frozen-source-01 是辅助导入错误，frozen-source-03 才是有效最终身份。旧版本 PASS 仅作为过程证据，不能代替本表。

完整回归唯一 SKIP 是原 Windows 创建符号链接 WinError1314。旧 FAIL/ERROR、诊断错误、中断、cProfile超时及历史 F1/H1/F2 UNKNOWN 全部保留，没有将其改写成 PASS。
'''
    
(HERE/'test-index.md').write_text(index,encoding='utf8')
matrix='''# Planning Item → Code Change → Test → Acceptance Result

全部条目 IMPLEMENTED_NOT_ACCEPTED，待独立复核与用户验收；PLANNING_CONFLICT=NONE（未发现实际规划冲突），EVIDENCE_CONFLICT=PRESENT（本轮证据尚未独立确认）。

代码入口简称：域契约 temporary_tools.py；原 Action 接线 action_planning.py；服务 temporary_tool_service.py；原设备可选门禁 device_operation_service.py；隔离外界 w04_tool_fixture.py。完整路径见 final.pending-files.md。下表测试均位于 tests/test_w04_3_tools.py，正式结果在 test-index.md。

| Planning Item | Code Change / 复用原入口 | Test（test_ 前缀省略） | Acceptance Result |
|---|---|---|---|
|N14/T30 已授权发现、来源/版本/依赖、存在与可用分开|ToolOffer；candidates/offer 验证原 P16/E5-A；未预注册目标可用|discovery_is_real_p16_and_not_current_availability；missing_discovery_and_untrusted_material_are_not_callable；candidate_identity_scope_and_hash_are_checked；registration_alone_does_not_replace_connection_verification|IMPLEMENTED_NOT_ACCEPTED；真实隔离发现至接入链|
|N14/T31 用途/范围/期限与缺项协助|ToolLease；conditions + 原 P08/P17 current；advance|authorized_connect_verify_use_cleanup_and_readonly；missing_login_resumes_same_connection_without_discovery_or_cost_repeat；conditions_identify_new_scope_budget_dependency_without_creating_connection；same_tool_grant_does_not_authorize_send_or_purchase|IMPLEMENTED_NOT_ACCEPTED；缺项等待，资料不授予权限|
|N14/T31 授权内自动推进，不逐步模型/审批|advance + 原可信 Action producer；RuntimeWork 复用 P18/Scheduler/guard|advance_autonomously_finishes_single_task_without_model_steps；p18_wait_resume_pause_stop_use_original_task_and_control；pause_during_wait_does_not_create_cleanup_intent|IMPLEMENTED_NOT_ACCEPTED；任务意图仍来自原主体链|
|N14/T32 单次/限时/持续/续期|单次原回执去重；预算原效果积分；新有效grant/连接|single_use_cannot_run_second_business_action；granted_persistent_connection_survives_task_until_explicit_cancel；timed_task_completes_then_expiry_cleanup_uses_original_connection；explicit_renewal_uses_new_valid_grant_and_new_connection_identity；connection_identity_is_not_reused_for_renewal|IMPLEMENTED_NOT_ACCEPTED；持续连接仍有约定期限|
|N14/T32 当前失效/撤销/取消/断线|require_device/observe 当前资格；原设备观察、动作和消费门禁|expiry_denies_use_but_cleanup_is_separately_authorized；cancel_reserved_before_delivery_fences_future_use；offline_recovery_does_not_reconnect_or_reset_generation；fresh_observation_checks_lease_before_and_after_read；permission_loss_during_observation_refuses_return|IMPLEMENTED_NOT_ACCEPTED；到期观察修前反例已保留|
|N14/T41 退出中断/部分清理/失败/UNKNOWN|query/inspect/advance 投影原事实；有界关联清理|partial_cleanup_is_pending_then_linked_cleanup_preserves_facts；cleanup_unknown_does_not_claim_closed_or_start_another_cleanup；cleanup_failure_then_reopen_preserves_pending_not_false_clean；lost_cleanup_response_recovers_without_duplicate_removal；cleanup_preserves_other_connection_and_subject_files|IMPLEMENTED_NOT_ACCEPTED；待清理不是断净|
|N14/T32/T41 尚未接入的取消与原请求闭合|connect最终提交前核对close；close只对明确未执行/已知事实继续原清理|cancel_before_connection_reopen_and_replay_never_opens_it；cancel_during_connect_before_native_commit_is_fenced；terminal_failed_connection_can_finish_cleanup_without_fake_connection；cancel-before/after-final同探针|IMPLEMENTED_NOT_ACCEPTED；嵌套原锁忙保留待清理，不伪报完成|
|N14/T18 原请求恢复与不重复|原 E5-A 查询、P17 Outbox；不新建账本|return_lost_recovers_original_receipt_without_second_connection；cross_process_lost_connection_recovery_and_replay；unknown_connection_never_replays_or_creates_effect；budget_is_actual_unique_business_receipts_not_number_of_queries|IMPLEMENTED_NOT_ACCEPTED；三进程实际续接|
|N14 合法替代，不绕过拒绝|alternative→P17 CHANGE_ROUTE，仅已证明未执行的技术故障|technical_api_unavailable_may_select_ui_but_denial_and_unknown_do_not；revocation_cannot_switch_route_and_view_permission_is_current|IMPLEMENTED_NOT_ACCEPTED；API/UI均为隔离替身|
|N21 局部历史查询衔接|工具发现/接入后原 device.query 与指定回执 Router/Composer，2048不变|history_query_reuses_original_receipt_router_composer；原W04-2 history_selection 全组|IMPLEMENTED_NOT_ACCEPTED；自然记忆联动归W05|
|共同身份/环境/来源/host/generation|当前根与原 W04-1 绑定；旧host不放行|current_discovery_revocation_prevents_use_but_preserves_historical_fact；expired_discovery_is_not_replaced_by_same_name_new_offer；other_environment_offer_is_rejected_before_connection；migration_fences_old_discovery_before_any_connection；cleanup_after_host_handoff_is_blocked_not_falsely_clean|IMPLEMENTED_NOT_ACCEPTED；生产交接未开放|
|秘密/只读/原事实完整性|原P16/P17材料检查、静态端口异常；inspect前后授权|credential_secret_rejected_before_ledger_write_and_traceback_safe；connection_fact_corruption_refuses_read_and_has_no_effect；view_rechecks_permission_at_return；final_revocation_between_setup_and_native_call_is_zero_effect；failed_verification_does_not_register_usable_tool|IMPLEMENTED_NOT_ACCEPTED；只读不执行业务/模型/学习|
|旧链兼容和保留要求|仅 Action 新tool.*分支、Device可选guard；旧调用默认不变|W04-1/2专项；417公共兼容；最终全量。原1000ms/2048/P18断言不改|原阶段ACCEPTED保持，本批未验收|

主测 T30/T31/T32/T41 与适用 T18、N21 内部链已取证。W04-4 跨入口完整联验、W05、P19页面、P20/21正式恢复、P22真实接入未开工，不以本表替代。
'''
(HERE/'matrix.md').write_text(matrix,encoding='utf8')
report=f'''# W04-3 工具发现与临时接入交付

状态 **IMPLEMENTED_NOT_ACCEPTED**，交规划窗口独立复核和用户验收。D-090仅为开工授权；W04整体IN_PROGRESS，W04-4未启动。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，未自行关闭独立复核门。

## 实际完成

从原P16已授权发现入口取得真实候选回执，验证来源/版本/用途/依赖，通过原P08/P17/E5-A接入、核验、使用及结束。缺登录/新范围/预算/依赖时保留原任务等待；条件补齐后不再发现、不新建主体或第二连接。工具资料不能授权；发送/购买不会从普通工具权限推导。

单次、限时、持续连接各有结束规则。动作及纯观察均检查当前资格，失效不继续使用。清理失败/部分/未知分别保留待清理和原因，恢复先查原事实。技术不可用可走合法API/UI替代，权限拒绝和未知效果不能绕行。N21经原device.query、指定回执Router/Composer回流。P18可选work适配经原Scheduler继续等待任务，暂停/停止有效；不安装服务，不改变引擎寿命。

运行代码新增域契约与服务两文件、隔离Fixture一文件；只修改两处旧运行文件：ActionSpecification增tool.*内部参数核验，DeviceOperationService增可选临时资格门禁。旧调用未接guard时保持旧行为。新增46正式测试，旧正式测试文件和断言无修改。凭据只受控引用，使用事实仍在唯一E5-A，未增加Memory/SubjectState/请求账本。公共影响、恢复细节见[语义说明](recovery-semantics.md)。

## 同版验证

源码/测试/资源 {len(source)} 项，`{frozen['fingerprint']}`。正式身份 {frozen['test_count']}，原1863保留、新增46。以下是施工方本轮实跑，交叠不相加，不是规划窗口实跑或远端CI：

{table}

原命令、stdout/stderr、退出码、耗时、执行前后完整源码分别在[索引](test-index.md)和各JSON。唯一SKIP为原Windows1314，不算PASS。完整回归一次，没有自动反复跑绿。原W02负载与1000ms、指定历史回执2048、P18控制测试在同版集合中保留。

## 失败与局限

新UNKNOWN收集接线、Fixture候选过长、纯观察到期门禁缺口均保留修前结果；探针observe-before/after展示同一反例修复。另有cancel-before真实复现待接入取消后原连接仍能创建：本批connect提交前补原close事实门禁，明确未执行/终态允许原清理闭合；cancel-after-final同探针通过，新增3项覆盖重开、提交交错、失败后清理。嵌套清理原锁EXECUTION_BUSY如实等待，不伪报CLOSED。诊断长路径、初次身份导入环境错误单独记录，不算Engine缺陷。全部过程见[调查记录](investigations.md)，旧历史未覆盖。

本机TEST接入/验证/清理设置成本0，模拟业务动作按原回执实际扣1 TEST credit；三进程返回丢失恢复及重放仍是一次效果、一次扣费、新发现0、新模型0。不是现实价格策略，也不证明真实服务质量或任意负载时延。

有界自动清理最多三份关联清理动作，仍失败则待清理；UNKNOWN先查询、不重发。旧host失权后不允许冒用清理权限，真实生产迁移/清理仍待P20/21。新续期必须有新有效条件及新连接；用户明确暂停/停止不自动复活。可选P18接线的实测聚焦单个待接入事务，每轮提供首个native need和首个工具need，多个同时待接入事务的公平推进尚未取证；不能据此宣称完整跨入口装配通过。真实账号/安装/订阅/设备/凭据/P22、W04-4、W05、P19均未开放。没有完整插件自动编写工程，也不是本批前置。

历史F1/H1/F2仍UNKNOWN，既有cProfile超时及原失败/SKIP照留。保留先前W02/W03/P00—P18、W04-1/2验收，不以本批通过倒改历史。

## 复核入口

[逐项矩阵](matrix.md) · [链路样例](chain-example.md) · [只读状态和恢复](recovery-semantics.md) · [固定源码与身份](frozen-source-03.json) · [精确成果清单](final.pending-files.md) · [70项排除材料](exclusions.json) · [终局审计](final.audit.json) · [进程清理](process-cleanup.json)。

本轮只读远端查询见[remote-read-01](remote-read-01.json)，当时main与本地基线f64fb797一致；不是push结果。无暂存/提交/push，未取得CI run/check，不宣称CI PASS。
'''
(HERE/'final-report.md').write_text(report,encoding='utf8')
summary='；'.join(f"{r['label']} {r['pass']}PASS/{r['fail']}FAIL/{r['error']}ERROR/{r['skip']}SKIP" for r in runs)
section=f'''<!-- W04_3_DELIVERY -->
## W04 第三子批次交付，待独立复核

D-090开工授权内完成N14工具发现、临时接入/等待、验证、使用、清理与恢复，承接N21原指定历史查询；原P08/P16/P17/P18/W04链复用。单次/限时/持续、当前授权及未知结果不盲重放；纯观察资格前后复核。旧Action新增内部tool.*参数分支，旧Device只加可选门禁；其他旧源码/正式测试不改。

施工方同版实跑：{summary}。集合交叠不相加。源码{len(source)}项 `{frozen['fingerprint']}`；1909测试身份，原1863保留、新增46。规划窗口尚待只读复核，没有独立实跑或远端CI结论。新修前失败、辅助错误、旧UNKNOWN、cProfile超时和Windows1314 SKIP保留。

W04-3 IMPLEMENTED_NOT_ACCEPTED；W04整体IN_PROGRESS。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，未自行关闭复核门。63保护、正式7文件、现行3规划和70保留材料按审计核对；未验收、暂存、提交、push，W04-4未启动。生产工具/真实凭据/账号/设备、完整页面及生产恢复仍未开放。

[交付报告](w04_3_evidence/final-report.md) · [矩阵](w04_3_evidence/matrix.md) · [测试](w04_3_evidence/test-index.md) · [精确清单](w04_3_evidence/final.pending-files.md) · [审计](w04_3_evidence/final.audit.json)。下文各历史时点原样保留。

'''
shared=['docs/project_memory/'+x for x in ['01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md']]
for name in shared:
    p=ROOT/name;old=p.read_bytes()
    if b'<!-- W04_3_DELIVERY -->' in old:
        assert old.startswith(section.encode('utf8')),'PARTIAL_DELIVERY_CONTENT_CHANGED'
        continue
    p.write_bytes(section.encode('utf8')+old)
for name in ['README.md','docs/project_memory/CHANGELOG.md']:
    p=ROOT/name;old=p.read_bytes()
    brief='<!-- W04_3_DELIVERY -->\n## W04-3 工具发现与临时接入（待复核）\n\n已实现隔离发现、授权内接入/使用、缺项等待与原事实恢复、清理及N21查询衔接；状态 IMPLEMENTED_NOT_ACCEPTED。原公共链兼容、保护及测试证据见[本批交付](docs/project_memory/w04_3_evidence/final-report.md)。无真实服务接入，无Git写入；W04-4未开工。\n\n'
    if name!='README.md':brief=brief.replace('docs/project_memory/w04_3_evidence/','w04_3_evidence/')
    if b'<!-- W04_3_DELIVERY -->' in old:
        assert old.startswith(brief.encode('utf8')),'PARTIAL_INDEX_CONTENT_CHANGED'
    else:p.write_bytes(brief.encode('utf8')+old)
(HERE/'continuation.md').write_text('W04-3本批施工及同版验证完成，等待独立复核。先读final-report.md、test-index.md、final.audit.json。所有最终测试已结束，不再重启旧session或覆盖标签。D-090仅开工，未验收/暂存/提交/push，不进入W04-4；历史UNKNOWN与失败保留。\n',encoding='utf8')
put('exclusions.json',base['retained'])
runtime={'src/continuity_engine/domain/action_planning.py','src/continuity_engine/services/device_operation_service.py',
         'src/continuity_engine/domain/temporary_tools.py','src/continuity_engine/services/temporary_tool_service.py',
         'src/continuity_engine/testing/w04_tool_fixture.py','tests/test_w04_3_tools.py'}
allowed=runtime|set(shared)|{'README.md','docs/project_memory/CHANGELOG.md'}
artifacts={PREFIX+'/'+x for x in ['final.pending-files.md','final.files.json','final.audit.json','final.git-status.txt','final.diff-check.txt']}
for name in artifacts:(ROOT/name).touch(exist_ok=False)
working=set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
delivery=sorted(working-set(base['retained']))
assert all(p in allowed or p.startswith(PREFIX+'/') for p in delivery),'UNEXPECTED_WORKSPACE_CHANGE'
assert set(base['retained'])<=working and not set(delivery)&set(base['retained'])
assert set(source)-set(base['source'])=={x for x in runtime if x not in base['source']}
assert {x for x in source.keys()&base['source'].keys() if source[x]!=base['source'][x]}=={
    'src/continuity_engine/domain/action_planning.py','src/continuity_engine/services/device_operation_service.py'}
old_changed=[];history_changed=[]
for name,h in base['tracked_baseline'].items():
    if name in allowed:continue
    if not (ROOT/name).is_file() or sha(name)!=h:old_changed.append(name)
for name in shared+['README.md','docs/project_memory/CHANGELOG.md']:
    original=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
    # HEAD newline checkout can differ from raw Git bytes. The original suffix
    # is independently checked against the opening workspace byte fingerprint.
    data=(ROOT/name).read_bytes();marker=data.find(original)
    suffix_ok=marker>=0 and data.endswith(original)
    if not suffix_ok:
        options=[original.replace(b'\n',b'\r\n'),original.replace(b'\r\n',b'\n')]
        suffix_ok=any(data.endswith(o) and hashlib.sha256(o).hexdigest()==base['tracked_baseline'][name] for o in options)
    if not suffix_ok:history_changed.append(name)
assert not old_changed and not history_changed,(old_changed,history_changed)
diff=git('diff','--check');(HERE/'final.diff-check.txt').write_text('exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr,encoding='utf8')
status=git('status','--short','--untracked-files=all');(HERE/'final.git-status.txt').write_text(status.stdout+status.stderr,encoding='utf8')
cyclic={PREFIX+'/'+n for n in ['final.pending-files.md','final.files.json','final.audit.json']}
hashes={p:sha(p) for p in delivery if p not in cyclic}
(HERE/'final.pending-files.md').write_text('# W04-3 精确成果清单（未暂存）\n\n共'+str(len(delivery))+'项。仅本批实现/测试/证据及必要共享档案；前置70项保留见exclusions.json，不夹带。共享档案只在顶部追加本批记录，历史字节保留。三份互相引用的清单/审计避免循环hash；审计另含前两份最终hash。\n\n| 路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+hashes.get(p,'SELF_REFERENTIAL_MANIFEST')+'` |' for p in delivery)+'\n',encoding='utf8')
put('final.files.json',dict(count=len(delivery),paths=delivery,hashes=hashes,self_reference_exclusions=sorted(cyclic)))
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
audit=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='IMPLEMENTED_NOT_ACCEPTED',
    planning_conflict='NONE',evidence_conflict='PRESENT',branch='main',head=base['head'],local_origin=git('rev-parse','origin/main').stdout.strip(),
    live_remote_evidence='remote-read-01.json',ahead_behind=git('rev-list','--left-right','--count','HEAD...origin/main').stdout.strip(),
    source_count=len(source),source_fingerprint=frozen['fingerprint'],source_equals_all_final_runs=True,
    test_count=frozen['test_count'],old_1863_missing=[],old_test_files_changed=[],runs=runs,
    protected_counts={k:len(v) for k,v in base['protected'].items()},current_planning_count=3,protected_changes=protected_changes,formal_tree_count=len(formal_tree),formal_tree_exact=True,
    retained_count=len(base['retained']),retained_changes=[],tracked_historical_changes=old_changed,shared_history_suffix_changes=history_changed,
    syntax_errors=syntax,new_document_broken_links=links,sensitive_pattern_hits=secret,synthetic_markers='Explicit TEST marker in tests and preserved counterexample evidence; not real secrets',
    diff_check_exit=diff.returncode,diff_check_evidence='final.diff-check.txt',historical_warnings='Old logs/format warnings retained; checkout LF-to-CRLF notices recorded, not functional FAIL',
    delivery_count=len(delivery),staged=[],git_mutations=False,ci='No remote CI run/check obtained; no PASS claim',
    processes='process-cleanup.json',pending_files_sha256=sha(PREFIX+'/final.pending-files.md'),files_json_sha256=sha(PREFIX+'/final.files.json'))
put('final.audit.json',audit)
print(json.dumps({k:audit[k] for k in ['delivery_count','source_count','source_fingerprint','test_count','syntax_errors','new_document_broken_links','sensitive_pattern_hits','diff_check_exit']},ensure_ascii=False))
assert not syntax and not links and not secret,'AUDIT_REQUIRES_REVIEW'
