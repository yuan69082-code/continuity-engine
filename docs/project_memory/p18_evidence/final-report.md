# P18 施工交付与独立复核入口

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072 开工；D-073 未创建/未使用。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（资源等待进程用例曾超时，根因尚未证实；后续通过不关闭该待复核项，不构成验收）。

已完成默认持续宿主、独立控制、原 P11/Wake/C1/P14/Expression/P17 接线、资源局部等待恢复、幂等与中断恢复。产品 start 无测试期限；本轮实测为隔离本地 Fake，未开放生产供应商、凭据、部署服务或正式联系政策。

本报告于2026-09-12续接生成。下列行为结果均来自2026-09-10已完成的施工实跑，本次只重新核对源码/测试/保护身份、原始stdout/stderr、进程和档案，没有重跑专项或全量。规划侧续接检查也没有重跑行为测试；不能冒称已独立验收。见 [续接要求](resume-brief-20260912.md) 与 [续接身份核对](resume-check-20260912.json)。

实现文件及逐项语义见 [Stage Brief](../83_P18_PersistentRuntime架构与开工简报.md)、[十二项矩阵](../84_P18_规划施工测试验收矩阵.md)、[恢复语义](../85_P18_持续运行控制资源等待与恢复语义.md)、[运行与复核命令](../86_P18_测试索引与验收入口.md)。仅局部改动四个旧运行文件，其余实现/测试均新增；旧测试不改。原Scheduler资源候选检查的追加范围见 [接线范围](resource-scan-scope.json)，原开工清单不倒改。完整工作区归属见 [精确清单](final.pending-files.md)，32个既有排除项原样保留。

## 真实测试证据

| 唯一标签 | RUN | PASS | SKIP | FAIL/ERROR | 秒 |
|---|---|---|---|---|---|
| compatibility-final-01 | 738 | 737 | 1 | 0/0 | 1077.849 |
| compatibility-scheduler-final-01 | 110 | 110 | 0 | 0/0 | 12.683 |
| control-after-01 | 4 | 1 | 0 | 3/0 | 2.49 |
| control-after-02 | 4 | 3 | 0 | 1/0 | 3.98 |
| control-after-03 | 4 | 4 | 0 | 0/0 | 3.657 |
| control-before-01 | 4 | 0 | 0 | 0/4 | 0.724 |
| control-edges-after-01 | 3 | 3 | 0 | 0/0 | 5.842 |
| control-edges-before-01 | 3 | 0 | 0 | 3/0 | 5.833 |
| control-edges-before-02 | 3 | 0 | 0 | 3/0 | 5.521 |
| controls-expanded-01 | 21 | 21 | 0 | 0/0 | 18.028 |
| fairness-after-01 | 2 | 2 | 0 | 0/0 | 1.426 |
| fairness-before-01 | 2 | 0 | 0 | 2/0 | 1.788 |
| fairness-formal-01 | 4 | 4 | 0 | 0/0 | 3.807 |
| full-final-01 | 1418 | 1417 | 1 | 0/0 | 1121.067 |
| full-final-03 | 1424 | 1423 | 1 | 0/0 | 1036.819 |
| p18-candidate-01 | 51 | 51 | 0 | 0/0 | 78.384 |
| p18-diagnostic-05 | 58 | 58 | 0 | 0/0 | 90.569 |
| p18-final-01 | 52 | 52 | 0 | 0/0 | 77.763 |
| p18-final-02 | 54 | 53 | 0 | 1/0 | 79.899 |
| p18-final-03 | 54 | 54 | 0 | 0/0 | 79.817 |
| p18-final-04 | 58 | 57 | 0 | 1/0 | 120.372 |
| p18-final-06 | 62 | 62 | 0 | 0/0 | 93.749 |
| p18-final-07 | 64 | 64 | 0 | 0/0 | 94.627 |
| pressure-before-01 | 2 | 1 | 0 | 1/0 | 2.085 |
| process-01 | 5 | 4 | 0 | 1/0 | 54.657 |
| process-resource-diagnostic-01 | 1 | 1 | 0 | 0/0 | 6.518 |
| recovery-01 | 17 | 17 | 0 | 0/0 | 17.022 |
| stop-after-01 | 2 | 2 | 0 | 0/0 | 0.735 |
| stop-before-01 | 2 | 0 | 0 | 2/0 | 0.92 |
| stop-formal-01 | 2 | 2 | 0 | 0/0 | 1.52 |

每个标签对应同目录 `.json`、`.stdout.log`、`.stderr.log` 三个原始文件。最终有效三轮次是 p18-final-07, compatibility-scheduler-final-01, full-final-03；历史轮次的源码身份各自保存，不能当作最终版本结果。开工全量仅引用，未新跑。新增64项与原1360身份分别保留；全量1424=1423PASS+1SKIP。1314是既有Windows符号链接创建权限不足，未改为PASS。

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

## 2026-09-12 实际收口检查

本次实际运行归档编译器和只读审计，没有重跑任何行为测试。收口预检命令：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python docs/project_memory/p18_evidence/audit.py closeout-check-20260912
```

[预检原始结果](closeout-check-20260912.audit.json)退出码0、errors为空；263份源码/测试/资源与最终专项、全量及续接核对完全一致，253个Python源码/测试文件及P18证据辅助脚本解析通过。原1360个测试身份、旧测试文件字节完整保留；十二项矩阵映射覆盖全部64个P18测试，110项旧兼容身份也完整包含在最终全量中。未改写任何先前原始证据。

当前源码清单指纹（路径→SHA-256映射按键排序后的紧凑JSON）：

`sha256:83d162101362916f12041ae21fa3b066676fa4b59523076c420d87c1f462ff3b`

63项保护文件（含六份Schema和外部契约）、三份规划、正式七文件、原31个P10辅助脚本和1份P14旧接续报告全部逐文件hash一致。正式数据树仍为：

`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`

版本仍0.1.0；pyproject SHA-256仍为 `40703a155ab1c1626901d1b61363384e49b5c64e58303cc110fe499ff6c25419`。Assistant/Vio未操作。

预检扫描1169个本地链接，无断链；敏感材料模式检查无命中，没有缓存、正式数据、构建包或临时运行产物混入P18清单。敏感扫描是模式检查，其结果不等同于任意材料均安全的证明。`git diff --check`退出0，Git另有四个既有修改文件的LF/CRLF提示，未据此转换文件。历史八处格式告警、P17原始日志三处告警继续保留；P18原始 `full-final-02.stderr.log` 第721行有一处行尾空格，原样保留，非行为测试结论。没有新增可编辑档案格式告警。最终链接数和逐文件hash以稍后生成的[终局审计](final.audit.json)为准，不把预检数量冒充终局实测。

最终专项与全量各含6项真实进程测试，各记录9个子进程：7个正常退出0、1个故障注入退出73、1个双进程竞争拒绝退出2，均已回收且无forcedCleanup。旧full-final-02受控中断的父子进程退出另有原记录。2026-09-12对限定P18 Python命令行的只读系统查询匹配0个进程，见[本次进程记录](resume-process-check-20260912.json)；本次没有启动或终止运行时及测试子进程。该结果不扩大为所有系统进程审计。

Git维持main，HEAD及本地origin/main均为 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地ahead/behind=0/0、暂存区为空。origin配置为 `https://github.com/yuan69082-code/continuity-engine.git`，本次没有访问实际远端，没有Git写操作。21个已跟踪修改包括4个既有运行文件及17个README/工程档案；新实现7个文件、新正式测试3个文件、83—86号专题档案及P18证据均按[完整待提交与排除清单](final.pending-files.md)归属。终局新增审计文件也纳入清单，不用开工文件数限制最终档案数量。

Git忽略的正式数据、旧Word材料及已有缓存等172个路径只作只读清点，未清理，未进入清单；开工没有保存全部忽略缓存的逐文件hash，因此不宣称全部缓存字节均已证明与开工一致。正式七文件及指定32项的身份有独立完整保护证据。先前受控中断留下的仓库外隔离P09临时根按原记录保留，未混入版本化成果。没有已跟踪Actions workflow，没有本次CI run/check或CI PASS声明。

终局审计入口为 `python docs/project_memory/p18_evidence/audit.py final`，其输出保存此次检查、完整Git状态、精确文件及排除清单。复核时应使用未占用标签，例如 `audit.py independent-closeout-01`，脚本拒绝覆盖已有审计。本报告完成后仅生成终局清单/审计并只读核对其hash。

## 交回独立复核

P18已实现，尚未验收。独立复核优先检查历史资源等待超时及现有诊断限制，并复跑86号档案中的专项/全量入口；不能将后来PASS作为已查明原故障的依据。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT；D-073未创建/未使用，P19—P23未开始。正式联系时段、频率、费用上限和长期部署方式仍待用户另行决定。
