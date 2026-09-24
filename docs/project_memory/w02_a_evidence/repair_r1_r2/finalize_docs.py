"""Write repair closeout docs only after all fixed-source runs really finish."""
from pathlib import Path
import datetime
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def write(name, text):
    (HERE/name).write_text(text, encoding='utf-8')


def main():
    assert load('integrity-check-outcome.json')['closedLocally'], 'Pending R1 integrity check must be resolved first'
    selected = load('selected-runs.json')
    frozen = load(selected['source'])
    source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('src', 'tests') for p in sorted((ROOT/folder).rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert source == frozen['source']
    runs = {k: load(selected[k]+'.json') for k in ('formal', 'special', 'compatibility', 'full')}
    for run in runs.values():
        assert run['status'] == 'FINISHED' and run['exitCode'] == 0 and not run['loaderErrors']
        assert run['sourceBefore'] == run['sourceAfter'] == source
    table = ['| 本轮实跑（集合有交集，不相加） | 结果 | 墙钟秒 / 退出码 | 原始证据 |', '|---|---|---|---|']
    names = dict(formal='新增正式定点', special='W02-A 专项', compatibility='受影响兼容', full='最终完整回归')
    for group, run in runs.items():
        label = selected[group]
        table.append(f"| {names[group]} | {run['run']}项：{run['passed']} PASS、{len(run['skips'])} SKIP、{len(run['failures'])} FAIL、{len(run['errors'])} ERROR | {run['seconds']:.3f} / {run['exitCode']} | [{label}]({label}.json) · [stdout]({label}.stdout.log) · [stderr]({label}.stderr.log) |")
    table = '\n'.join(table)
    summary = '；'.join(f"{names[k]} {v['run']}项（{v['passed']} PASS、{len(v['skips'])} SKIP），{v['seconds']:.3f}秒" for k,v in runs.items())
    write('final-report.md', f'''# W02-A R1/R2 定向补修交付

本轮只完成 R1/R2 及必要验证。W02-A = IMPLEMENTED_NOT_ACCEPTED，W02 整体仍 IN_PROGRESS；W02-B/C、W03、P19 未开工。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（已知反例已在施工方关闭，尚待独立确认）。没有用户验收登记或 Git 写操作。

## 用大白话说明

现在一条消息处理中某一站失败，正式查询仍能告诉你哪些站已经处理、哪站失败、为什么等待、从哪里继续；重开同一数据根仍能查。查询不会偷偷继续业务。恢复时只补未完成站，不重复已成功的模型调用、效果、扣费或主体版本。

“我不喜欢苹果”会识别到否定，“我喜欢其他颜色”不会因为词里的“他”变成转述别人。引用、双重否定或不清楚的范围继续标明不确定；不是把有限规则冒充全能语言理解，也不是把输入直接变成记忆或主体事实。

## R1：原因与实际修改

原站点回执先于完整 Perception 保存；Core 遇到已捕获的站点错误仍会抛出，完成感知快照没有落盘。公开 input_outcome 因此提前返回 PENDING_PERCEPTION，临时输入材料也随调用结束丢失。回执存在并不等于可安全公开：旧查询确实缺少可重开验证的材料。

本次在原 operation journal 的 domainProgress 内增加可选 inputPreparation，保存原感知准备快照及已形成的 Context；不把它当作完整感知，不跳过失败站，也不新建账本。它与原请求/操作/主体/环境/观察/版本/原文 hash 绑定，原始输入不能改写；Context 只可从缺失补入一次，此后准备材料不可删除或替换。

查询先后核验当前许可，检查原来源/解释版本、回执与原 Context/Memory 事实、当前版本及完整性，返回前再次检查当前状态与日志没有变化。只输出结构记录，不输出准备快照正文；发现完成表有记录时，即使 domain 检查点缺失，也必须走原完成结果绑定核验，不能让孤立或错配结果冒称完成；待完成仍是 PENDING，并列 resume_stations。失败记录只表示这次处理失败，不能冒称记忆、事实或整轮完成。

旧完整记录继续回放；旧部分记录如果没有可核验的准备快照，仍只给 PENDING_PERCEPTION/record=None，不能凭旧日志自证。明确重提原请求时才允许从原材料补齐，而不是查询时写入。新流程的局部失败、重开及真实独立进程查询已经覆盖。

## R2：原因与实际修改

旧规则没有覆盖普通“不+谓词”，并将任意位置单字“他”视为他人。新 v2 规则先区分引用范围，使用有界主语位置和词法组合；记录否定片段及范围（偏移以去掉首尾空白的解释文本为坐标，原文仍完整保存），遇到双重否定、未闭合引用或不可靠转述范围返回不确定，不扫描心理内容作许可决定。

已存 v1 解释仍按保留的 v1 规则核验，恢复不重写旧 manifest、来源或回执；新消息使用 v2。本文不声称已经实现通用中文 NLU；复杂句、未覆盖词法和语用仍有边界，需要后续按正式规划独立验证，不能自动升级为事实。

## 文件及公共调用方

| 实现文件 | 最小责任 |
|---|---|
| [integration_results.py](../../../../src/continuity_engine/domain/integration_results.py) | 原内部进度增加可选准备快照、原身份/版本绑定及旧格式兼容 |
| [json_integration_repository.py](../../../../src/continuity_engine/storage/json_integration_repository.py) | 同一原日志内的准备记录单调性，禁止删除、改写 |
| [continuity_core_service.py](../../../../src/continuity_engine/services/continuity_core_service.py) | Context 成形时与原站点回执一道保存可核验准备材料 |
| [continuity_interaction_service.py](../../../../src/continuity_engine/services/continuity_interaction_service.py) | 原入站回调保存；正式只读查询部分进度与返回前复核 |
| [input_context_source.py](../../../../src/continuity_engine/services/input_context_source.py) | 重开后解析原准备快照，仍走原权限端口 |
| [input_processing_service.py](../../../../src/continuity_engine/services/input_processing_service.py) | 完整/部分回执区分验证；有界中文 v2 与旧解释恢复 |

正式测试只向原 [processing](../../../../tests/test_w02_input_processing.py)、[recovery](../../../../tests/test_w02_input_recovery.py) 增加测试类；第三份既有 integration 测试未改。原两份测试可移除新增类后重建为修前精确字节 hash，原断言未动。

公共影响限启用 W02 输入门的 C1 入站、恢复、进度查询与当前输入源，以及原日志可选字段验证。关闭开关的旧 native/C1、Thinking/Action/Evolution、表达、能力恢复、资源和 Runtime 由兼容与全量覆盖。没有修改公共权限政策、Scheduler、主体生命周期、有限重试或计费实现。正常持续运行、局部等待、PAUSE/STOP、现实边界及内部自主成长职责不变。

## 本轮实际运行

{table}

原1621项身份全部保留，本轮新增{len(frozen['addedTests'])}项，最终{runs['full']['run']}项。既有 Windows symlink 创建权限 WinError1314 SKIP 仍单列，不计 PASS。JSON seconds 是墙钟时长，stderr 的 unittest 时长另行保留。无独立复核新结论、无远端 CI 运行或 CI PASS 声明。

最终282份源码/测试/资源指纹：`{frozen['sourceHash']}`。上述四组的前后清单均一致，见 [最终冻结清单]({selected['source']})。此前原 W02-A 41/813/1621 结果只作历史引用。本轮此前686项兼容全部通过、full-final-01的1645项为1644PASS/1SKIP（1649.505秒）；它们是真实实跑，但只覆盖 frozen-source.json 前一版。随后1行查询守卫及1个正式反例的增量使源码身份变化，故最终重跑定点、完整W02-A、查询/原日志/C1/表达及自主性兼容组合，再跑一次全量。前版结果不能冒充最终覆盖，也不是反复重跑取代解释失败。

## 失败历史与剩余事项

修前 [4项反例](reproduction-before-01.json) 全部真实 FAIL（3.069秒），不把静态线索冒称既往独立复现。修后第一组4PASS。后续 [45项组合](w02-intermediate-01.json) 出现本轮规则引入的1个真实回归：无主语的普通问句被额外送去核实站。未改旧断言，收窄规则后原问句以及最终完整专项/全量覆盖通过。详见 [运行历史](test-history.md)。

一次 PowerShell 花括号路径读取报 ParserError 属辅助工具问题，未写入源码；原始事实另记 [开工与矩阵计划](plan.md)。末轮核查又证实 R1 的完成表交叉绑定漏口：有效 [result-binding-before-02](result-binding-before-02.json) 为1 FAIL，最小查询条件补齐后 [result-binding-after-02](result-binding-after-02.json) 为1 PASS。前两次该探针在嵌套 TEST 路径创建临时文件时分别出现1个辅助 ERROR，尚未到达目标断言；改用独立短 Temp 根后才得到有效反例，未改断言。两份ERROR原件照存，不能当作Engine行为缺陷。详情 [核查结论](integrity-check-outcome.json)。本轮没有测试中断或新增SKIP。

历史 F1/H1/F2 仍 UNKNOWN，本轮问题不并入旧案。W02-A 仍待规划窗口独立复核及用户确认；自动回忆、外部资料完整可信吸收与最终贯通仍在 W02 后续子批次。尚未部署生产、接入真实服务或开放任何正式删除/隐私/外部能力。

## 复核入口与审计

[逐项对应矩阵](matrix.md) · [可运行复核命令](review-entry.md) · [施工日志](../../03_施工日志.md) · [终局审计](final.audit.json) · [累计及补修清单](final.pending-files.md) · [逐文件hash及排除清单](final.inventory.json) · [子进程核查](process-cleanup.json)。

审计将核对六Schema/25冻结边界/63保护、正式7文件、旧及现行规划、版本0.1.0、32排除材料与25份原W01规划；本轮未修改它们。真实结果以审计文件为准，历史格式告警单列保留，不删除旧日志。源码固定后仅补档案，不机械重跑全量。停止在独立复核交付处，不暂存、提交、push，不进入后续批次。
''')
    write('matrix.md', '''# W02-A 补修后逐项对应矩阵

本表补充原矩阵，不覆盖其发生时结论。所有行最多 IMPLEMENTED_NOT_ACCEPTED；施工方验证通过不等于正式验收。原始运行及源码绑定见 [最终报告](final-report.md)，精确测试身份见 JSON。

| Planning Item | Code Change / 当前入口 | Test（现有 test_w02_input_* 模块） | Acceptance Result |
|---|---|---|---|
|A01/N01/T01/T02/R2 原始理解|interpret v2，旧v1核验|InputLanguageRepairTests：negation、other_colors、quote、scope、v1_pending|本轮反例已补，待独立复核|
|A02/N01 来源/时刻|inputPreparation与原manifest/operation绑定|PartialInputQueryTests：corruption、subject_and_environment、version；原current_material|当前核验及原时刻保留|
|A03/N01/T05 相关站|_stations，普通问句不误送核实|原question_routes；report_friend；引用/歧义实际入站|本轮过度分流回归已补；不全模块强制参与|
|A04 接收≠记住|原Memory事实核验，候选不升级|原plain_claim/existing_event/same_event_name；repair quote_and_scope|原职责不变|
|A05 临时Context|当前输入候选与权限来源|新增plain_negation/other_colors真实Thinking材料；原预算/模型能力测试|不是W02-B自动回忆|
|A06 合法内部提交|原Thinking/Action/Evolution未改|原internal_evolution_survives_expression_refusal；表达/心智兼容|不由分流器修改主体|
|A07/T18/R1 部分恢复|原日志inputPreparation+失败/成功回执|partial_public_query、composition_failure、repeat_read_and_resume|同请求只补未完成站|
|A08 原事实恢复|原Memory/ThinkSession/E5-A|原saved_memory/thinking_saved/restart_completed/real_process_restart；新v1_pending|不重复调用/效果/扣费/revision|
|A09 完整性/并发|准备快照不可改写；原admission|partial_preparation、forged_success、unbound_completed_result；原concurrent/cross_process_busy|无第二账本；不宣称生产exactly-once|
|A10 当前门禁|当前来源许可、版本/Context、返回前重查|revoked_permission/revoked_during_query/rechecks_revision/expired_context；原材料门禁|拒绝且只读零副作用|
|A11 旧调用/隔离|可选内部字段，旧请求保守查询|legacy_partial、v1_pending；原disabled/native/snapshot/protected_fixture|冻结契约/Authority不变|
|A12/T24/R1 公开只读出口|input_outcome经可信材料核验|partial_public_query_after_local_failure/after_reopen/in_separate_process；重复查询|可信逐站进度可读，PENDING不假报COMPLETED|

原始4FAIL与中间1FAIL均保留。测试集合有交集，不相加。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，下一步仅独立复核。
''')
    history = ['# 本轮运行记录（全部唯一标签保留）', '', '| 标签 | 状态 | 总数 / PASS / FAIL / ERROR / SKIP | 墙钟秒 / 退出码 |', '|---|---|---|---|']
    for path in sorted(HERE.glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or 'sourceBefore' not in record:
            continue
        label = path.stem
        history.append(f"| [{label}]({label}.json) · [out]({label}.stdout.log) · [err]({label}.stderr.log) | {record['status']} | {record.get('run','未确认')} / {record.get('passed','未确认')} / {len(record.get('failures',[]))} / {len(record.get('errors',[]))} / {len(record.get('skips',[]))} | {record.get('seconds','未确认')} / {record.get('exitCode','UNKNOWN')} |")
    history += ['', '修前4FAIL对应本轮R1/R2；45项组合的1FAIL是普通问句过度分流。本轮末尾完成表绑定核查含2次辅助ERROR及1次有效FAIL，随后最小修补并用新冻结版本验证。其他中间通过（包括早先full-final-01）只覆盖当时源码。最终四组身份一致，不能把它们相加。旧W02顶层证据逐字节保留，历史F1/H1/F2仍UNKNOWN。']
    write('test-history.md', '\n'.join(history)+'\n')
    write('review-entry.md', '''# 独立复核入口

从 Engine 根目录运行，隔离 TEST/Fake，禁止操作正式数据；每次新证据标签必须未占用。run.py 不重试、不覆盖标签，保存命令、stdout/stderr、退出码、准确PASS/SKIP、源码前后清单。独立复核不是用户验收。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH="$PWD/src"
& E:/Adobe/python.exe -B docs/project_memory/w02_a_evidence/repair_r1_r2/run.py review-r1-r2-01 tests.test_w02_input_recovery.PartialInputQueryTests tests.test_w02_input_processing.InputLanguageRepairTests
& E:/Adobe/python.exe -B docs/project_memory/w02_a_evidence/repair_r1_r2/run.py review-w02-01 tests.test_w02_input_processing tests.test_w02_input_recovery tests.test_w02_input_integration
```

兼容精确模块列表及原命令见 [compatibility-scope-02.json](compatibility-scope-02.json)。完整回归：上述 runner 后仅传一个未占用标签（例如 review-full-01），不传测试名即 discover tests。不要并发跑这些集合，不因重复运行而覆盖首次失败。

R1通过正式 f.app.adapter.service.input_outcome 查询。局部失败注入发生在正常 C1，覆盖本进程、reopen和真实新进程；查询前后比全树hash及模型/效果/费用；明确重提原请求才恢复。R2通过正常入站直达Provider的Context，检查原文、解释、候选权威和各站处置，原有正向测试断言未改。

[报告](final-report.md) · [矩阵](matrix.md) · [源码身份](frozen-source-02.json) · [首次失败](reproduction-before-01.json) · [最终清单](final.pending-files.md)。
''')
    status = 'W02-A = IMPLEMENTED_NOT_ACCEPTED；W02整体仍IN_PROGRESS；W02-B/C、W03、P19未开工。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（待独立确认）。'
    marker = '<!-- W02_A_REPAIR_R1_R2_CURRENT -->'
    docs = ['README.md'] + ['docs/project_memory/'+f for f in ('01_当前状态.md','03_施工日志.md','06_未完成事项.md','CHANGELOG.md','工程总档案.md')]
    for path in docs:
        p = ROOT/path
        original = p.read_text(encoding='utf-8')
        assert marker not in original, 'Do not overwrite a previous closeout'
        link = 'docs/project_memory/' if path == 'README.md' else ''
        block = f'''{marker}
## W02-A R1/R2 定向补修交付（2026-09-24）

{status}用户授权范围为部分失败只读进度与普通中文否定/指代补修；依据现行总规划v1.5、最终新增v1.5、长期v6.9及已批准W02-A说明。

R1通过原operation journal内准备快照与当前权限/身份/版本/事实复核，公开入口可读部分失败及重开后的逐站状态，恢复不重复成功站。R2补有界词法及引用范围，不确定性保留，旧v1解释和原请求历史不改写。公共影响仅正常C1入站、恢复、当前输入源和查询；权限政策、Subject Authority、持续运行/PAUSE/STOP、资源计费及现实边界不变。

本轮真实修前4FAIL；中间45项组合44PASS/1FAIL（普通问句过度分流）；末轮R1错配完成记录反例1FAIL，并单列2次临时路径辅助ERROR。原断言未改，修补与首次输出都保留。最终本轮实跑：{summary}，均0FAIL/ERROR。原1621身份及断言保留，新增25项；既有Windows1314 SKIP不算PASS。旧41/813/1621结果仅作为历史引用；本轮前版686项兼容及1645项完整运行也不能代替最后守卫补修后的最终覆盖；无远程CI PASS声明。

最终源码/测试/资源282项：`{frozen['sourceHash']}`。详见[补修报告与复核入口]({link}w02_a_evidence/repair_r1_r2/final-report.md)、[逐项矩阵]({link}w02_a_evidence/repair_r1_r2/matrix.md)、[精确成果/排除清单]({link}w02_a_evidence/repair_r1_r2/final.pending-files.md)。保护项与正式数据核对结果见终局审计；原32排除材料、25份W01规划、历史F1/H1/F2 UNKNOWN及P00—P18验收保持。

剩余：本轮只交独立复核；复杂中文边界不冒充完整NLU，缺准备证据的旧部分记录不公开未经核验内容。W02后续自动回忆/完整可信吸收/最终贯通仍未施工。不自行验收、暂存、提交、push或进入下一批。以下均保留为发生时的历史记录。

'''
        p.write_text(block+original, encoding='utf-8')
    decision = ROOT/'docs/project_memory/04_决策记录.md'
    text = decision.read_text(encoding='utf-8')
    assert '### D-075 补充：R1/R2' not in text
    decision.write_text(text+'''\n### D-075 补充：R1/R2 定向补修事实（2026-09-24）

用户明确授权仅补部分失败查询及普通中文否定/指代，不授权验收或Git写操作。静态线索经真实入站4项反例复现后修补；普通问句过度分流及完成表交叉绑定漏口另行保留并修正，两次TEST辅助路径ERROR照存。当前W02-A仍IMPLEMENTED_NOT_ACCEPTED，已完成施工方验证，等待独立复核；无新验收决定。详见[补修报告](w02_a_evidence/repair_r1_r2/final-report.md)。现行PLANNING_CONFLICT=NONE/EVIDENCE_CONFLICT=PRESENT，旧验收与UNKNOWN不改写。
''', encoding='utf-8')
    write('continuation.md', f'''# W02-A R1/R2 接续记录

完成施工与测试，已写最终报告、矩阵及施工日志。{status}

最终四组均真实完成并绑定 frozen-source-02.json：{summary}。本轮最终全量不是引用旧结果。下一步只读终局保护、链接、敏感信息、Git差异与进程检查，生成 final.audit.json / final.inventory.json / final.pending-files.md 后交独立复核。没有源码或测试的后续变动需求，不要重跑已有完整测试。

原证据目录及32排除项保留；历史F1/H1/F2 UNKNOWN。禁止验收、Git写操作、W02-B/C、W03或P19。若任务恢复，先读实际审计和进程记录，不因本记录落后而重复运行。
''')
    print(summary)


if __name__ == '__main__':
    main()
