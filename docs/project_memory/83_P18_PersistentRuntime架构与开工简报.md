<!-- P18_ACCEPTED_D073_20260919 -->
## 现行状态：P18 用户正式验收（D-073）

P00—P18 = ACCEPTED；P18 / Engine side / P18-01—P18-12 = ACCEPTED；P18 Vio dependency = NONE；P19—P23 = NOT_STARTED。

用户于 2026-09-19 正式验收当前已交付且独立复核通过的 P18 成果，登记 D-073，并明确接受历史 F1/H1/F2 无法唯一归因的遗留不确定性。本次异常原因链缺口依据独立复核关闭。

现行 PLANNING_CONFLICT = NONE、EVIDENCE_CONFLICT = NONE，仅表示本次已知验收阻断经独立复核或用户明确接受遗留不确定性后闭合，不保证不存在其他缺陷。F1/H1/F2 历史原因仍为 UNKNOWN，原 FAIL、ERROR、SKIP、中断及证据缺失记录原样保留；未查明历史唯一根因，也未将旧失败改成通过。

本条同步现行 P18 验收与导航；下方旧状态、阶段边界及证据按发生时点保留。

生产部署、真实外部能力、生产身份/凭据、正式联系时段/频率/费用政策及生产恢复保持原 NOT_READY 边界；本次验收不开放这些能力，不进入 P19。

[验收报告与证据](p18_acceptance_evidence/acceptance-report.md) · [完整待提交/排除清单](p18_acceptance_evidence/final.pending-files.md) · [本轮档案修改清单](p18_acceptance_evidence/documentation-files.json)。

## 以下为此前施工、返修和调查历史

以下保留发生时的状态及结论；其中 IMPLEMENTED_NOT_ACCEPTED、EVIDENCE_CONFLICT=PRESENT、D-073 未创建等均为历史，不代表本次现行状态。

<!-- P18_EXCEPTION_REPAIR_20260914 -->
P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT；D-073未创建/未使用。

本轮新增正式10项，原1507项身份和断言保留。P18 157 PASS；公共兼容 605 PASS；最终全量 1517项：1516 PASS、1既有Windows 1314 SKIP、0 FAIL/ERROR，运行记录耗时1384.364秒，exit 0。各组有交集，不重复相加。

本轮仅修连续异常导致原生原因丢失；原独立六项修前4PASS/2FAIL、当前身份修后6PASS，新增正式10PASS。顶层拒绝/有限重试/持续运行语义不变。F1/H1/F2历史根因仍UNKNOWN，待独立复核；D-072追加本轮返修事实，不创建验收决定。

[本轮完整报告](p18_exception_evidence/final-report.md) · [精确清单/审计](p18_exception_evidence/final.pending-files-resume-20260919.md)。

以下为此前真实阶段/中间结果及当时状态，均作为历史保留，不倒改。

<!-- P18_STORAGE_REPAIR_FINAL_20260914 -->
P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加本次授权/返修事实，D-073未创建/未使用。

新增正式27项，原1480项身份及断言保留。P18 147 PASS；公共兼容 605 PASS；本轮最终全量 1507项=1506 PASS、1既有Windows 1314 SKIP、0 FAIL/ERROR，1319.841秒，exit 0。各组重叠，不相加。

用户已明确授权两个存储文件及完整绑定WinError5的有限尝试变化，本轮补修和验证完成待独立复核。有限尝试只约束同一存档，不改变宿主默认持续运行；不重派动作、不重复扣费。F1/H1/F2历史唯一根因仍未证实。

[完整返修报告、证据与持续运行核对](p18_storage_final_evidence/final-report.md) · [清单/审计](p18_storage_final_evidence/final.pending-files-02.md)。

以下均保留此前阶段/中间结果及当时授权状态，不倒改历史。

<!-- P18_PERSISTENCE_CURRENT -->
P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加调查/返修事实；D-073未创建/未使用。

本轮新增正式14项；P18 120 PASS；兼容 605 PASS；最终全量 1480 项=1479 PASS、1既有1314 SKIP、0 FAIL/ERROR，1284.129秒，exit=0。原1466身份及断言保留，各组有交集，不重复相加。

F2同阶段共享竞争风险已复现并最小修复；历史具体OS码/句柄缺失不补写。F1/H1仍UNKNOWN。当前不自行关闭独立复核阻断。

[本轮调查/完整报告](p18_persistence_evidence/final-report.md) · [终局审计与逐文件清单](p18_persistence_evidence/final.pending-files.md)。

本次用户追加授权限定P18持久化/恢复根因调查与最小修复。FILES ALLOWED增量：src/continuity_engine/storage/json_repository.py、services/wake_perception_thinking_action_service.py、testing/p18_runtime_fixture.py、testing/p18_persistence_diagnostics.py、tests/test_p18_persistence.py及本轮证据/直接档案；services/testing项均在src/continuity_engine下。冻结/正式数据/规划/版本/排除项禁止修改。

## 下方为此前阶段记录与历史证据

<!-- P18_R2_CURRENT_START -->
P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。R1既有独立定点结论保留；R2返修待独立复核；F1/H1分别为UNKNOWN；本次全量新增失败F2，原因UNKNOWN，等待确认，不自行续修。D-072追加事实，D-073未创建/未使用；不验收、不Git写入、不P19。

本轮最终专项 106 PASS；新增正式 R2 22 PASS；原12/4探针各自通过；兼容 490/490 PASS。最终全量 1466项：1464 PASS、1既有1314 SKIP、1 FAIL/0 ERROR，1376.330秒，exit=1。原1444身份保留，新增22项；各组交叉包含，不能相加。

本次验证续接核对并引用前五组完成结果，仅补跑 full-resume-01。旧 full-final-01 未完成，退出码/原因UNKNOWN，原记录保留；不据此记为Engine行为FAIL。

R2通过原ThinkSession内的持久阶段区别未调用控制延后与真正UNKNOWN；同一会话恢复重验条件，过期材料有明确前驱的新评估。R1保留，F1/H1仍缺根因证据；后续PASS不关闭历史失败。正常start默认持续，不启用生产政策。

[本轮完整报告与复核入口](p18_r2_evidence/final-report.md)。下方R1/初版和旧阶段的状态、PASS/FAIL/ERROR/SKIP均为当时历史，不倒改。
<!-- P18_R2_CURRENT_END -->

本轮 Stage Brief 追加：STAGE=P18 R2返修；SOURCE OF TRUTH=用户2026-09-13续修授权及归档独立报告；ORIGINAL REQUIREMENTS/KEEP=默认持续运行、原单一权威及R1修复不变；AMENDMENT=可靠调用前阶段恢复与F1/H1分开调查；NOT READY=旧无阶段依据记录自动恢复、生产部署/联系策略；PLANNING CONFLICT=NONE。

FILES ALLOWED：domain/thinking.py、services/thinking_service.py、services/runtime_cognition.py、services/wake_perception_thinking_action_service.py、storage/json_thinking_repository.py、testing/p18_runtime_fixture.py、tests/test_p18_runtime_process.py、tests/test_p18_runtime_resume.py及直接相关档案/新p18_r2_evidence。FILES FORBIDDEN：63保护项/冻结契约/正式数据/规划/版本/32排除项/Assistant。TESTS REQUIRED：原12/4类、22正式回归、完整P18、兼容、一次最终全量，实际结果见本轮报告。

# P18 R1返修与H1调查：当前交付

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072追加返修事实，D-073未创建/未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，R1待独立确认，H1根因UNKNOWN；本轮全量新增F1超时亦未闭合，不自行关闭。

本轮最终P18 84 PASS；正式返修 20 PASS；原独立探针 5 PASS；兼容 254 PASS；最终全量 1444项=1442 PASS+1既有1314 SKIP，1 FAIL/0 ERROR，退出码1。原1424身份保留，新增20项；各组有包含关系，不重复相加。

R1最小范围：json_runtime_repository.py、persistent_runtime_service.py；新增正式竞争测试，原process测试只追加清理前安全诊断。没有修改Scheduler/Resource/C1业务、冻结契约或正式数据。首次入队和既有任务权威继续复用。

[本轮报告](p18_repair_evidence/final-report.md) · [本轮终局审计](p18_repair_evidence/final.audit.json)。下方原版本文字和结果保留为历史。

---

# P18 Stage Brief：默认持续运行的 Persistent Subject Runtime

| 字段 | 本阶段明确边界 |
|---|---|
| STAGE | P18 Engine 独立施工；启动后默认持续运行；产品没有总轮数/总时长自动退出限制。 |
| SOURCE OF TRUTH | 用户 2026-09-10 整合授权优先；完整简报、已核对的 2026-08-26 三份规划与当前真实代码，见下方原件副本。 |
| ORIGINAL REQUIREMENTS | v1.1 P18 220—227：Engine 托管生命周期、持续宿主、无消息 Wake/认知/整理/内部事务/主动联系、资源与恢复。 |
| V6.7 DETAILS | 同一 Subject 跨计算会话连续心智，P14 内生需要与原 C1/Thinking/Action/Evolution；P15 解释非事实权威。 |
| AMENDMENT OVERRIDES | Runtime Ownership 属 Engine；D1 Scheduler 只安排计算、不创建心理内容；Direct 与 Optional Planner 均保留。用户澄清持续存活不等于固定间隔强制调用模型，局部资源等待不等于整体停止。 |
| KEEP RULES | 唯一 SubjectState/Event/Memory/E5-A Authority；原回执及 UNKNOWN 先查询；P01 仅 TEST/Research；原思想与心理冲突不被基础设施筛查。 |
| DEPENDENCIES | P11 Scheduler、ResourceAwareWakeScheduler/ResourceManager、原生 WakePerceptionThinkingActionService、正常 C1、P12/P14/P15/P16/P17。 |
| NOT READY | 正式联系时段/频率/费用和生产控制策略待用户决定；生产 Adapter/凭据、P20/P21 恢复与 P22 接入未开放；不安装服务或自启。 |
| FILES ALLOWED | 下方精确实现清单、83—86、现行状态及必要工程档案、p18_evidence 下唯一标签证据/辅助验证。 |
| FILES FORBIDDEN | 六份 Schema/冻结契约/63 项保护、三份规划、正式七文件、pyproject/0.1.0、Assistant/Vio、32 排除项和所有旧证据。 |
| TESTS REQUIRED | 先定点反例与正常对照，再专项/兼容，最终源码稳定后一次全量；保留原 1360 身份和断言，SKIP 单列；实际进程由测试控制器明确停止并清理。 |
| PLANNING CONFLICT | NONE；若必须越过上述边界，保留证据并停止对应项，不能默默缩减。 |

## 用户澄清与实现职责

持续入口只有 Owner 明确 STOP、经合法 P15 落地的主体暂停/归档/删除，或不可继续的真实进程故障会终止/限制运行；空队列、单轮结束、沉默、断连、局部资源耗尽不自动停止进程。PAUSE 保留控制宿主；STOP 持久保留，重启不能复活。若整个认知暂不可用，如实表示 WAITING_RESOURCES，不能伪造“仍在思考”。

Runtime 新持久记录仅管 Owner 运行意图、运行者 fencing、调度水位及诊断，不存心理正文、模型结果或竞争请求账本。原 Scheduler Queue 仍管理任务，原 Wake/ThinkSession/Action/E5-A/Event 记录是实际结果依据。单进程运行权采用本机 OS 锁；控制事务和派发前门槛分开，同步控制从明确的线性化点生效。

原生 C1 执行入口按需要最小增加可选当前 Runtime 门禁和原 ActionPlanning/Execution 回流接线；新执行在资源准备之后复核，已有事实按原身份核实恢复。认知机会由原内部状态/时间差/待整理来源驱动，不制造用户消息，tick 不直接写心理内容。可信 UTC 与单调等待时间分开；回拨等候、跃进只给一次当前机会，不无界追赶漏掉的轮次。

正常入口独立于 UI/Vio，使用可中断的有界等待保持控制响应。CLI 的 start 默认持续；TEST 控制器独立设置观察期限并明确 STOP，不把测试限时写成产品规则。此次只运行隔离 Fake，测试结束不得遗留后台实例。

## 精确实现文件范围

- `src/continuity_engine/domain/persistent_runtime.py`
- `src/continuity_engine/storage/json_runtime_repository.py`
- `src/continuity_engine/services/persistent_runtime_service.py`
- `src/continuity_engine/services/runtime_ports.py`
- `src/continuity_engine/services/runtime_cognition.py`
- `src/continuity_engine/runtime.py`
- `src/continuity_engine/testing/p18_runtime_fixture.py`
- `src/continuity_engine/services/wake_perception_thinking_action_service.py`
- `src/continuity_engine/services/thinking_service.py`
- `src/continuity_engine/services/resource_aware_wake_scheduler.py`
- `tests/test_p18_runtime.py`
- `tests/test_p18_runtime_recovery.py`
- `tests/test_p18_runtime_process.py`

## 原文与核对

[完整整合简报](p18_evidence/implementation-brief.md) · [规划原文摘录](p18_evidence/planning-extract.json) · [规划侧基线核验](p18_evidence/baseline-verification.json) · [本轮实测基线](p18_evidence/before.json)。

已验证开工全量是引用施工方 1360 项、1359 PASS/1 既有 1314 SKIP、1171.401 秒，未重跑；不是 1360 PASS。原始失败与八加三处历史格式告警全部保留，无远端 CI PASS 声明。

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IN_PROGRESS；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072 开工；D-073 未创建/未使用。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE（开工未发现冲突，不构成验收）。

## P18 资源局部等待接线的文件范围补充（施工中）

`fairness-before-01` 两项反例已实证：原队列中首个资源不足的认知任务，挡住后来有资源的本地记忆整理。按用户本次要求“局部资源不足不停止其他合法工作”，FILES ALLOWED 追加 `src/continuity_engine/services/scheduler_service.py` 的必要内部可选接线：原 Scheduler 内有界检查资源候选，默认仍只检查一个候选；P18 显式开启。保留原排序、队列、资源入口、回执、尝试和取消职责，不另建 Scheduler 或账本，不改冻结文件。

原开工清单/源码指纹不倒改；追加依据见 [范围补充](p18_evidence/resource-scan-scope.json)、[两项原始失败](p18_evidence/fairness-before-01.stderr.log)。当前全量运行期间未修改源码，完成后该结果将作为补强前历史保留；应用补强后按影响另做必要验证。这不是 P19 开工或用户验收决定。

## 施工完成后的现行状态

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072 开工；D-073 未创建/未使用。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（资源等待进程用例曾超时，根因尚未证实；后续通过不关闭该待复核项，不构成验收）。

全部实现文件仍在上列授权范围。Subject 的意向记录不冒充已落地生命周期；仅原 P15 已合法形成的 SUSPENDED/ARCHIVED/DELETED 限制后续工作，不改变 SubjectState Authority。具体结果见 [测试入口](86_P18_测试索引与验收入口.md)。
