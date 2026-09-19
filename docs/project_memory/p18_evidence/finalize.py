"""P18 current documentation from completed evidence, without running tests."""
from pathlib import Path
import json
import runpy
import hashlib

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
DOC=OUT.parent
config=runpy.run_path(str(OUT/'prepare.py'))
TOP=config['TOP'];STAGE_FILES=config['STAGE_FILES']
FULL_LABEL='full-final-03'
LABELS=('p18-final-07','compatibility-scheduler-final-01',FULL_LABEL)
STOP_CLOSEOUT={'src/continuity_engine/services/persistent_runtime_service.py','tests/test_p18_runtime_recovery.py'}
CONTROL_CLOSEOUT={
 'src/continuity_engine/services/persistent_runtime_service.py',
 'src/continuity_engine/storage/json_runtime_repository.py',
 'src/continuity_engine/testing/p18_runtime_fixture.py',
 'tests/test_p18_runtime_recovery.py','tests/test_p18_runtime_process.py'}
STATE='P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072 开工；D-073 未创建/未使用。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（资源等待进程用例曾超时，根因尚未证实；后续通过不关闭该待复核项，不构成验收）。'

def read(p):return json.loads(p.read_text(encoding='utf8'))

def write(p,text):p.write_text(text.rstrip()+'\n',encoding='utf8')

def main():
    assert not (OUT/'final-report.md').exists() and not (OUT/'delivery-report.md').exists(),'preserve an earlier closeout report'
    runs={label:read(OUT/(label+'.json')) for label in LABELS}
    current={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==runs[FULL_LABEL]['sourceAfter']==read(OUT/'resume-check-20260912.json')['sourceTest'],'current source identity drift'
    for label,r in runs.items():
        assert r['status']=='FINISHED' and r['exitCode']==0,label
        assert r['sourceBefore']==r['sourceAfter'],label
        delta={p for p,h in runs[LABELS[-1]]['sourceAfter'].items() if r['sourceAfter'].get(p)!=h}
        if label=='compatibility-scheduler-final-01':assert delta<=STOP_CLOSEOUT,label
        else:assert not delta,label
    tests='\n'.join(f"| {label} | {r['run']} | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']:.3f} | [记录](p18_evidence/{label}.json) · [stdout](p18_evidence/{label}.stdout.log) · [stderr](p18_evidence/{label}.stderr.log) |" for label,r in runs.items())
    testtable='| 本轮验证 | RUN | PASS | SKIP | FAIL/ERROR | 秒 | 原始证据 |\n|---|---|---|---|---|---|---|\n'+tests+'\n\n专项与最终全量对应最终源码。110项Scheduler/Resources/pre-P12兼容运行后只改P18宿主STOP边界及其新测试，所测旧链源码不变，该P18增量由最终专项与全量覆盖。更早的宽兼容组 compatibility-final-01 为738项=737PASS+1既有SKIP，1077.849秒，早于P18控制/TEST时钟及Scheduler资源扫描补强，作为历史保留。full-final-01为资源扫描补强前的真实历史结果；full-final-02为发现STOP缺口后的受控中断，无完整回归结论。所有源码清单、首次失败和工具错误原样保存。'
    base=read(OUT/'before.json');full=runs[FULL_LABEL]
    newids=sorted(set(full['testIdentities'])-set(base['testIdentities']))
    shared=f'''{STATE}

已接通持续宿主、P11/Wake/原生 C1/P14/Expression/P17 与资源等待。正常 `start` 不设总时长或总轮数限制；测试控制器明确 STOP 并回收子进程。正式联系政策、生产控制身份和恢复/Adapter 仍 NOT_READY。

本轮专项 {runs[LABELS[0]]['passed']} PASS；相关兼容 {runs[LABELS[1]]['passed']} PASS；全量 {full['run']} 项={full['passed']} PASS、{len(full['skips'])} 个既有 1314 SKIP，0 FAIL/ERROR。原 1360 身份/旧测试断言保留，新增 {len(newids)} 项单列。见 [P18 入口]({STAGE_FILES[3]}) 与 [交付报告](p18_evidence/delivery-report.md)。下方旧阶段、开工和失败记录为历史。

上述测试于2026-09-10实际完成；2026-09-12续接只核验身份与原始结果并归档，没有重新运行测试。110项兼容早于最后STOP修补的两文件差异已明确记录，全部身份已包含在最终全量中。
'''
    for p in [ROOT/'README.md',*[DOC/n for n in TOP]]:
        text=p.read_text(encoding='utf8')
        block=shared
        if p.name=='README.md':
            block=block.replace(']('+STAGE_FILES[3]+')','](docs/project_memory/'+STAGE_FILES[3]+')').replace('](p18_evidence/','](docs/project_memory/p18_evidence/')
        start='<!-- P18_CURRENT_START -->';end='<!-- P18_CURRENT_END -->'
        before,tail=text.split(start,1);_,after=tail.split(end,1)
        write(p,before+start+'\n'+block+end+after)
    brief=DOC/STAGE_FILES[0]
    with brief.open('a',encoding='utf8') as f:
        f.write('\n## 施工完成后的现行状态\n\n'+STATE+'\n\n全部实现文件仍在上列授权范围。Subject 的意向记录不冒充已落地生命周期；仅原 P15 已合法形成的 SUSPENDED/ARCHIVED/DELETED 限制后续工作，不改变 SubjectState Authority。具体结果见 [测试入口]('+STAGE_FILES[3]+')。\n')
    rows=[
        ('运行身份/状态/控制','persistent_runtime.py、json_runtime_repository.py、persistent_runtime_service.py','owner_identity、control_identity、owner_pause_resume、explicit_stop、view_query、control_opaque、old_owner_control','静态身份 Port；生产控制身份未开放'),
        ('默认持续入口/等待','runtime.py、PersistentRuntimeService.serve','idle_tick、idle_and_subject_silence、continuous_golden','start 无生命周期截止；测试控制器有观察期限'),
        ('可信 UTC/时间异常','RuntimePolicy、PersistentRuntimeService.tick','clock_regression、long_clock_gap、advancing_clock_silence','回拨不派发；跃进合并，测试时钟倍率明确隔离'),
        ('内部需要与 Scheduler/Wake','RuntimeCognition.needs/dispatch、原 ResourceAwareWakeScheduler','without_messages、same_time_duplicate、resource_deferral','纯 P14 内部需要投影；不固定间隔调用模型'),
        ('C1/跨会话连续性/整理','原 WakePerceptionThinkingActionService、RuntimeCognition','native_contact、maintenance_query、continuous_golden','同一 Subject/原 Event、Memory；不重读聊天'),
        ('资源/背压/有界重试','RuntimeBudgets、RuntimeSchedulerResources、原 ResourceManager/P11','zero_budget、local_maintenance、later_maintenance、resource_scan、backpressure、proven_not_delivered、canceled_pending、budget_is_not_reset','预计预留与实际 TEST 回执分开；不重启清额度'),
        ('Owner/Subject 暂停停止','PersistentRuntimeService.guard、原 P15 生命周期','pause_after_selection、pause_after_wake、pause_immediately、pause_during_world、subject_suspension、archived_subject、later_pause、later_stop、stop_after_crash','停止只控制运行，不删除或重新定义主体'),
        ('双进程/损坏/恢复','JsonRuntimeRepository OS lock、fencing、interruptions','two_real_processes、stale_owner、corrupt_checkpoint、stop_history、missing_host_checkpoint','本机 OS 锁；保留最近64条中断诊断，不承诺软件永不中断'),
        ('唯一请求/历史事实/UNKNOWN','原 ThinkSession/Action/Evolution/E5-A/P17；RuntimeCognition.query','after_thinking、after_action、after_effect、after_evolution、after_queue_completion、before_receipt、actual_fact、old_context、unknown_execution、receipt_conflict、cancel_uncommitted','不完整模型会话保持待核实，不盲目再调；新执行重验当前上下文'),
        ('联系/沉默/现实效果约束','原 ExpressionPolicy/P17、RuntimeWorldBoundary','native_contact、unconfigured_delivery、contact_window、contact_budget','TEST 时段/频率策略；实际费用仍由 P17 独立回执核实'),
        ('隔离/材料/静态诊断','safe_root、RuntimeThinkingBoundary、原 P16/P17 材料口','test_root、cross_subject、cross_environment、provider_failure、ordinary_psychological','正式根/重解析点拒绝；不扩展为心理内容审查'),
        ('真实进程 Golden/兼容','test_p18_runtime_process.py、p18_evidence/run.py','全部6个真实进程用例、compatibility-scheduler-final-01、full-final-03','仅本地 Fake 假设；保留资源等待历史超时待复核；生产恢复/P22不在本阶段')]
    table='# P18 规划施工测试验收矩阵\n\n'+STATE+'\n\n工程验收分解，不冒充原规划编号；所有下列测试名片段可在三个正式 P18 测试文件定位。\n\n| 项目 | 语义 | 现行状态 | 实现位置 | 测试及结果 | 限制 |\n|---|---|---|---|---|---|\n'
    testmap={}
    for i,(name,implementation,methods,limit) in enumerate(rows,1):
        ids=[t for t in runs[LABELS[0]]['testIdentities'] if any(s in t for s in methods.split('、'))] if i!=12 else [t for t in runs[LABELS[0]]['testIdentities'] if t.startswith('test_p18_runtime_process.')]
        assert ids,('unmapped matrix row',i)
        testmap[f'P18-{i:02}']=dict(semantics=name,implementation=implementation,testIdentities=ids,
            evidence=[LABELS[0],FULL_LABEL],status='IMPLEMENTED_NOT_ACCEPTED',limitation=limit)
        table+=f'| P18-{i:02} | {name} | IMPLEMENTED_NOT_ACCEPTED | {implementation} | {methods}；本轮专项与全量 PASS | {limit} |\n'
    mapped={t for row in testmap.values() for t in row['testIdentities']}
    assert mapped==set(runs[LABELS[0]]['testIdentities']),('unmapped formal tests',set(runs[LABELS[0]]['testIdentities'])-mapped)
    write(OUT/'matrix-test-map.json',json.dumps(testmap,ensure_ascii=False,indent=2))
    table+='\n'+testtable+'\n\n[逐项完整测试身份](p18_evidence/matrix-test-map.json)覆盖全部64项，交叉归属不重复计数。[正式控制测试](../../tests/test_p18_runtime.py) · [正式恢复测试](../../tests/test_p18_runtime_recovery.py) · [真实进程测试](../../tests/test_p18_runtime_process.py) · [精确清单](p18_evidence/final.pending-files.md)。\n'
    write(DOC/STAGE_FILES[1],table)
    semantics=f'''# P18 持续运行、控制、资源等待与恢复语义

{STATE}

运行宿主独立于 UI、Vio、聊天及 Adapter。`serve()` 持有当前数据根的 OS 运行锁，反复执行有界 `tick()` 并用可中断 Event 等待；没有 max ticks、总时长、随机存活或每次 tick 强制 think。默认检查频率属于 CPU/控制响应间隔，不能解释为模型调用间隔。

纯 P14 Dynamics 根据原 MindState 与 elapsed time 判断内部需要是否发生足够变化；既有待整理 Event 形成有界维护工作。Scheduler 只收到稳定 identity、kind、dueAt、priority 和 cycle，不收到要编造的思想或行动目的。C1 Composer 当前材料真正传入原 Thinking，原 P14 Processor 形成认知结果；Expression 保持原意，原 Action/E5-A/P17 核实 TEST 效果，原 Evolution 写回心智。下一次 Composer 消费原执行 Result Observation，不将它升级为状态权威。

| 状态 | 持续进程及行为 |
|---|---|
| START/RUNNING/RESUME | 可执行当前有效任务，空闲或沉默仍存活 |
| PAUSED | Owner 显式暂停；保留查询/恢复/停止控制，禁止新派发 |
| SUSPENDED | 原 P15 主体暂停、时钟异常或进程中断；具体原因单列 |
| RECOVER | OS 锁重新取得后核实旧 work/ThinkSession/Evolution/回执；不创建新主体 |
| STOP | 持久 Owner STOP，正常循环结束；重启不会改成 RUNNING，RESUME 被拒绝 |
| ARCHIVED | 原 P15 已落地归档/删除不派发；控制宿主仍能接收 STOP |

主体提出的 P15 SUSPEND_INTENT/ARCHIVE_INTENT 不等同于已发生的行政状态变化；本阶段保留其原职责。真正落地的生命周期由原 SubjectState 与 Event 校验，Runtime 不自行执行主体归档/删除，也不把 Owner 暂停写成人格或心理变化。

资源不足时显示 WAITING_RESOURCES，未知工作显示 WAITING_VERIFICATION，队列满显示 QUEUE_BACKPRESSURE。资源恢复后定期重新评估仍有效工作，无需新聊天；本地记忆整理可在无模型额度时继续。原 ResourceManager 保存预留/结算，旧 session 只复用原分配；不修改总额度或抹除 usage。TEST Provider 以所获预算作保守实际 token 结算，Fake 世界积分依据 P17 独立原子回执，并非真实供应商账单。

为避免缺额的首个候选挡住后来可执行的维护，原 Scheduler 增加内部可选 resource_scan_limit，默认1保留既有行为；P18显式设置128且不超过队列容量。沿原 priority/aging/dueAt 排序做只读资源预检，每个tick仍最多派发一个任务；被拒候选不新增attempt、预算或回执，全部不可用时如实返回资源等待，不新建资源或工作账本。

Runtime checkpoint 仅存控制命令、owner/generation、水位、最近活动和最近64条中断诊断；工作状态仍是 P11，模型结果/行动/演化仍是原记录。单个中断未提交的新动作必须重验当前 Context、权限、资源、确认和生命周期；已发生的 Evolution/效果则按原身份核实恢复。UNKNOWN、丢失或冲突回执不能作为未执行证明。取消中的未完成认知不通过 query 偷偷执行动作。已停止、取消或失效任务不会因恢复额度复活。

控制事务提供幂等命令和可选 revision CAS；本地 OS 锁与 generation 阻止同根第二进程。资源准备后再次检查控制，P17 最终 sweep 后的 runtime guard 是本地同步派发边界；已经开始的调用以原 receipt/query 核实，不能承诺任意外部执行的实时撤销。进程崩溃可能失去当时尚未写盘的诊断；下一运行者记录 PRIOR_HOST_LOST，并保留最后可信时间，不虚构断电精确时间或原因。

时间回拨停止新派发并保留控制；跃进只产生一个当前机会，不无限追赶错过的轮次。测试倍率时间是明确 TEST 配置，正常宿主端口接收可信 UTC；不修改历史 Event 时间戳。

RuntimeDeliveryPolicy 默认未配置。只有隔离 init-test 的明确配置才开启测试联系时段与最小间隔，费用/消息上限继续由 P17 BlastRadius 核实。历史回执查询不依赖新联系许可，重新消费与新执行仍需要当前授权。正式联系时段、频率、费用、身份认证、P20/P21恢复、P22生产Adapter均 NOT_READY。

[矩阵]({STAGE_FILES[1]}) · [原始证据入口]({STAGE_FILES[3]})。
'''
    write(DOC/STAGE_FILES[2],semantics)
    entry=f'''# P18 测试索引与可运行入口

{STATE}

在 Engine 仓库 PowerShell 中运行：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
# 使用全新、独立、明确保留的 TEST 目录；不能位于引擎仓库/正式数据根内。
python -m continuity_engine.runtime init-test --root C:/continuity-p18-test --test-mode silence
python -m continuity_engine.runtime start --root C:/continuity-p18-test
```

`start` 在前台持续运行，没有自动限时；用另一个终端查询/控制：

```powershell
python -m continuity_engine.runtime query --root C:/continuity-p18-test
python -m continuity_engine.runtime pause --root C:/continuity-p18-test
python -m continuity_engine.runtime resume --root C:/continuity-p18-test
python -m continuity_engine.runtime stop --root C:/continuity-p18-test
```

STOP 持久且不能通过 resume/start 偷偷复活；需要新的 TEST 实验时显式指定全新独立目录。本轮未自动运行这些长期部署命令、安装服务/自启或留下无限实例。`--test-mode contact` 是明确的本地 Fake 联系配置，不是对外通知。`--test-clock-rate` 只在 init-test 配置测试时间倍率，start 不重置已有配置。生产根入口未开放。

Windows TEST组合继承已有存储的路径长度限制，建议使用上述短独立根。长Temp前缀的辅助失败已保留，不将路径限制伪装为状态恢复成功，也不修改旧存储或正式数据。

独立复核：

```powershell
python -m unittest tests.test_p18_runtime tests.test_p18_runtime_recovery tests.test_p18_runtime_process -v
python docs/project_memory/p18_evidence/run.py independent-p18-01 test_p18_
python docs/project_memory/p18_evidence/run.py independent-full-01
```

第二、三条保存唯一标签的原始 stdout/stderr、身份与时长；标签已存在即拒绝覆盖。真实进程用例由外部控制器限时观察并明确 STOP；故障进程预期退出73，其余正常退出0，竞争者拒绝退出2。所有子进程在临时根清理前保存输出到父测试 stdout，再由证据 harness 持久化。

{testtable}

以上三行是本轮施工实跑；原开工 1360/1359 PASS+1 SKIP、1171.401秒是 hash 一致后引用的历史结果，未重跑。全量保留原1360身份与断言；新增{len(newids)}项，既有WinError1314不计PASS。当前没有远端CI结果，不声明CI PASS。

历史过程和首次失败见 [交付报告](p18_evidence/delivery-report.md)，全部结果未被后续PASS覆盖。[最终审计](p18_evidence/final.audit.json) · [逐文件清单](p18_evidence/final.pending-files.md) · [开工身份](p18_evidence/before.json)。
'''
    write(DOC/STAGE_FILES[3],entry)
    history=[]
    for p in sorted(OUT.glob('*.json')):
        r=read(p)
        if 'sourceBefore' in r and 'run' in r:
            history.append(f"| {p.stem} | {r['run']} | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']} |")
    report=f'''# P18 施工交付与独立复核入口

{STATE}

已完成默认持续宿主、独立控制、原 P11/Wake/C1/P14/Expression/P17 接线、资源局部等待恢复、幂等与中断恢复。产品 start 无测试期限；本轮实测为隔离本地 Fake，未开放生产供应商、凭据、部署服务或正式联系政策。

本报告于2026-09-12续接生成。下列行为结果均来自2026-09-10已完成的施工实跑，本次只重新核对源码/测试/保护身份、原始stdout/stderr、进程和档案，没有重跑专项或全量。规划侧续接检查也没有重跑行为测试；不能冒称已独立验收。见 [续接要求](resume-brief-20260912.md) 与 [续接身份核对](resume-check-20260912.json)。

实现文件及逐项语义见 [Stage Brief](../{STAGE_FILES[0]})、[十二项矩阵](../{STAGE_FILES[1]})、[恢复语义](../{STAGE_FILES[2]})、[运行与复核命令](../{STAGE_FILES[3]})。仅局部改动四个旧运行文件，其余实现/测试均新增；旧测试不改。原Scheduler资源候选检查的追加范围见 [接线范围](resource-scan-scope.json)，原开工清单不倒改。完整工作区归属见 [精确清单](final.pending-files.md)，32个既有排除项原样保留。

## 真实测试证据

| 唯一标签 | RUN | PASS | SKIP | FAIL/ERROR | 秒 |
|---|---|---|---|---|---|
'''+ '\n'.join(history)+f'''

每个标签对应同目录 `.json`、`.stdout.log`、`.stderr.log` 三个原始文件。最终有效三轮次是 {', '.join(LABELS)}；历史轮次的源码身份各自保存，不能当作最终版本结果。开工全量仅引用，未新跑。新增{len(newids)}项与原1360身份分别保留；全量{full['run']}={full['passed']}PASS+{len(full['skips'])}SKIP。1314是既有Windows符号链接创建权限不足，未改为PASS。

## 失败与修复记录

- control-before-01：4个新测试因Fixture尚不存在报ERROR，属于新能力缺失，不是P17代码失败。
- control-after-01：3个新断言误假设一个tick完成整理及认知，实际首个tick合法维护Memory；改用有界控制器推进下个时点，保留认知及资源断言。
- control-after-02：空external_facts是tuple，测试误写list；修正类型断言，仍严格要求零外部Observation。
- process-01：冻结测试时钟在resume后没有推进维护后的下一调度时点，控制器超时；保留该输出，修正显式时间推进。真正按时间自动运行的contact Golden当时已通过。
- pressure-before-01：队列满时需求未丢失，但诊断误报NO_CURRENT_NEED。已补本次Runtime admission结果处理，明确QUEUE_BACKPRESSURE。
- p18-final-02：容量仅1时优先入队的认知工作通过正常C1同时整理来源，测试误要求独立MAINTENANCE状态；修正为明确COGNITION、一次Provider和实际Memory存在，没有弱化背压拒绝/保留需求断言。
- control-edges-before-01/02：收口自查确认控制历史淘汰会使旧命令重新生效、原控制标识写入检查点，以及推进时钟下静默回执仍引用冻结时钟导致认知停在待核实。现保留所有显式控制的摘要身份，不保存原始标识；统一静默Fake与P15生命周期的可信TEST时钟。修后control-edges-after-01三项通过，且纳入正式回归，另增真实静默进程多轮验证。
- clock-debug-01：调试使用的Temp前缀过长，原Awakening JSON临时文件碰到Windows路径限制；这是辅助布局失败，未修改已验收存储。缩短测试根后的clock-debug-02定位到上述真实时钟接线缺口。首版探针副本control_edge_probe_first.py及两次原始输出保留。
- p18-final-04：58项中57PASS、1FAIL，资源等待真实进程用例在冻结TEST时间推进后未观察到WAITING_RESOURCES并超时。已保存子进程输出确认宿主仍活、token_used=0、控制器STOP成功、无强制清理；但清理前活动被STOP状态覆盖，原原因未被捕获，根因UNKNOWN。随后只在该测试控制器增加结构化状态观察，不修改运行代码或原断言。process-resource-diagnostic-01单项PASS、p18-diagnostic-05全部58PASS，但这不能倒推原超时只是测试时序或已被修复。该项保持待独立复核，EVIDENCE_CONFLICT=PRESENT。
- fairness-before-01：两项真实反例均FAIL；额度为零或Provider不可用时，较旧的认知任务在资源门禁被拒后，原Scheduler直接返回，挡住后来有资源的记忆整理。新内部可选扫描仍由原Scheduler执行，默认一项保留旧行为，P18在队列容量内有界检查后续候选；被拒任务不消耗attempt、不收费、不删除。修后证据及正式正向/拒绝对照单列，原失败保留。本反例在full-final-01运行时使用另一个隔离Fixture核实，期间未修改源码；因此该全量保留为补强前历史，应用修复后才进行必要的新全量。
- stop-before-01：STOP后新身份的PAUSE或重复STOP会追加矛盾控制历史，两项均FAIL。现先检查持久终态，PAUSE/RESUME拒绝，重复STOP只读满足；stop-after-01两项PASS，stop-formal-01两项PASS，新增正式回归保留。已开始的full-final-02因此受控中断，原started快照、stdout/stderr、sourceBefore/After及controller-interruption记录保留，不能计作全量PASS/FAIL。首次Stop-Process工具报空对象错误，之后重新核对命令身份才控制终止；统一执行通道退出码1，单个被终止进程ExitCode未提供则保留null。P09隔离中断根的位置已记录，不清理无关临时材料。相关代码固定后才运行full-final-03。
- 首次工具ACL启动错误、误用不存在的p09文件名及Windows rg通配路径错误均见 [辅助记录](auxiliary-errors.log) 和 [接续记录](continuation.md)，不计作引擎测试失败。

独立进程测试完整stdout保存子命令、PID、退出码、观察时间、效果/积分/ThinkSession数量、原始输出和清理情况。多轮无聊天认知、同主体连续性、回流消费、暂停/恢复、预算恢复、两进程竞争及实际os._exit后的恢复均由正式测试检查。有限观察不能证明软件永不故障；只声明本地OS锁与原子Fake回执条件下的幂等。

## 尚未开放及限制

正式身份认证、联系时段/频率/额度、生产Adapter、真实模型、恢复/灾备和开机部署仍NOT_READY。TEST配置不是用户正式政策。Runtime只识别原P15已落地生命周期，未将主体意向直接升级为行政写权限。未完整的旧ThinkSession保持待核实，不盲目再调用模型。STOP终态不能自动重置；不会复活旧取消/失效请求。

尚存一项测试证据限制：资源等待进程用例的原超时根因UNKNOWN。新增观察只提高证据完整度，未宣称修复了未知原因；请独立复核重点检查该入口及跨进程状态观察。最新通过与历史失败同时保留。

本地同步派发边界重查暂停/权限，但已经开始的调用须以独立回执核实，不承诺任意生产系统 exactly-once 或瞬时撤销。历史FAIL/ERROR/SKIP及P09 segment10 UNKNOWN全部保留。无Git写、无远端CI实跑、无Assistant/Vio改动、无P19开工。

真实进程清理依据分别在最终专项/全量stdout与最终审计的processEvidence字段；受控中断的旧全量进程另见 [退出核查](interrupted-process-cleanup-check.json)。该次隔离P09临时根留作中断证据，不位于仓库、未加入Git清单；不清理不相关临时目录。

本轮最终身份、保护63项、三规划、正式七文件及树指纹、版本、旧32项、文档/敏感/静态/Git检查见 [final.audit.json](final.audit.json)。保持IMPLEMENTED_NOT_ACCEPTED，等待独立复核和用户正式验收。
'''
    write(OUT/'final-report.md',report)
    write(OUT/'delivery-report.md','# P18 交付报告入口\n\n'+STATE+'\n\n完整报告见 [final-report.md](final-report.md)，包括实现、历史失败、测试引用、已知UNKNOWN、启动/控制方法及独立复核入口。')
    for name,title in (('03_施工日志.md','P18施工完成与测试收口'),('04_决策记录.md','D-072施工结果追加（非验收）'),('10_档案修订记录.md','P18档案同步'),('CHANGELOG.md','P18 persistent runtime（0.1.0不变）'),('工程总档案.md','P18当前交付')):
        with (DOC/name).open('a',encoding='utf8') as f:
            f.write('\n## '+title+'\n\n'+STATE+'\n\n本轮结果与失败过程：[交付报告](p18_evidence/delivery-report.md)。正常持续入口不设自动寿命；测试控制器负责STOP和进程回收。独立复核未进行、未验收、未提交/push。\n')
    with (OUT/'continuation.md').open('a',encoding='utf8') as f:
        f.write('\n## 当前收口\n\n'+STATE+'\n\n专项和一次全量对应最终源码；相关兼容保留其完整历史源码清单，旧链字节一致，后续P18增量已在最终专项及全量中覆盖。剩余终局审计与交付，历史资源等待超时根因UNKNOWN，交回独立复核。勿退回P17。\n')
    print(json.dumps({'stage':'P18','status':'IMPLEMENTED_NOT_ACCEPTED','formalNewTests':len(newids),'fullRun':full['run']},ensure_ascii=False))

if __name__=='__main__':main()
