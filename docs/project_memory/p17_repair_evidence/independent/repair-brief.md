# P17 R1/R2 合并返修指令

用户已确认本轮返修。请在现有 P17 成果上完成以下两项修复、必要测试和档案同步，再交回独立复核。本次不是验收、Git 写操作或 P18 开工授权；不要退回 P16 收尾或重新施工整个 P17。

执行仓库：`C:/Users/Administrator/Documents/continuity-engine`。

独立复核材料目录：
`C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p17-independent-review-20260909`

## 先读材料并保留现场

读取上述目录的 `review-report.md`、`test_independent_edges.py`、`identity-check.json`，以及两轮 `independent-edges-01`、`independent-edges-02` 原始记录。保留原件；需要归档时复制到 Engine 本轮返修证据目录并记录来源及 hash，不修改规划侧材料。

复核基线：main，HEAD/本地 origin/main 为 `0c440b0476b07723abafe93777fe895b64fd8d0e`；现有 P17 成果 136 个路径，另有 32 个既有排除项。原 P17 专项独立 62/62 PASS；独立补测两次均为 3 PASS、4 FAIL，归为以下两个根因。先记录当前状态、文件和测试身份；如有新增重叠修改，辨明归属，不能回滚或覆盖。

## R1：最终检查期间撤权仍发生新效果

检查 `src/continuity_engine/services/execution_service.py` 的 `current()` 和 `execute()`。

Broker 授权、Reality 授权、Recoverability 在 capacity 之前检查；最终 Outbox 事务内的 capacity 回调中撤销任一条件后，仍能产生一次本地效果。原反例通过正常 C1，在第三次 capacity 调用时分别撤销三个条件，每项均期望 0、实际 1。

修复目标：在真正产生新效果之前，使用一致且仍有效的当前门槛判断，明确检查顺序、有效期和提交点。覆盖资源检查期间撤销 Broker、Reality 授权和恢复条件三个场景；不依赖任意增加固定检查次数或无限重试来掩盖时序窗口。基于现有接口做最小修复；不要求引入通用分布式事务框架，也不宣称任意生产 Adapter 都能提供瞬时撤权或 exactly-once。

拒绝时必须零新增世界效果、零新增实际扣费；如需要留下拒绝记录，应保留准确原因，不能把它记成成功执行。保持：合法执行与相同请求重放；已执行事实在撤权后仍可核实恢复而不重新执行；UNKNOWN 不盲重发；取消、补偿、Direct/Planner、跨进程恢复；旧结果撤权后不再消费，但不阻断正常沉默或普通心理内容。

## R2：检查预计消耗与 Fake 实际扣费不一致

检查 `src/continuity_engine/testing/p17_execution_fixture.py` 的 `FakeRealityBoundary.capacity()`、`FakeWorldAdapter.projected_document()` 及相关回执/世界存储约束。

WorldCapability 合法 cost 包括 0，但检查计算“已用 credits + route.cost”，Fake 实际每次成功固定增加 1。设置 credits 上限为 1、路径 cost=0，创建新请求并重建 C1 后，两轮执行实际累计扣 2，突破上限。

修复目标：投递前预计消耗与世界实际写入、回执采用同一明确计费规则，优先复用真实效果投影；如该 Fake 不支持某种配置，须在效果前明确拒绝并说明，不得全局禁止所有合法零费用能力。不要仅在超限后报错，或通过隐藏扣费、提高上限、放松断言制造通过。

至少验证：合法 cost=0 的明确定义、默认 cost=1、额度恰好够一次及下一次拒绝、重复请求不再次扣费，并检查请求数、消息数、存储上限及失败回执未受破坏。本项是本地 TEST 积分模型修复，不接真实支付或生产服务。

## 验证和证据

1. 修改前重现原反例，保留 stdout/stderr、命令、退出码、耗时和源码身份；修复后重跑同一探针并增加正式回归及正常对照。
2. 原独立探针逐字节保留。其 R1 含“第三次检查”的基线定位断言，R2 含当前 Fake 固定扣 1 的前提；若合理实现变更使定位或计费前提不再适用，原运行如实记录，不修改旧探针冒充原样通过。另加对准真实最终投递点、检查实际消耗不超限的等价或更强测试，说明差异交监工复核。
3. 定点通过后运行完整 P17 专项及受影响兼容组合。最终代码稳定后跑一次完整回归；仅在出现新失败或再次改动相关代码时追加必要运行，不机械多轮全量。
4. 保留原 1348 项测试身份与原断言，新增测试另计。既有 Windows symlink 1314 SKIP 不算 PASS；首次失败、中间错误、历史八处格式告警及原始日志全部保留。旧运行只可注明引用，不能冒充当前运行或远端 CI PASS。

## 范围及停止条件

只改 R1/R2 必要实现、Fixture、正式测试和相关档案。保持单一主体状态、原 E5-A 权威请求/结果链及 Outbox 索引职责。Reality Boundary 只约束结构化行动效果，不扩大成思想、情绪、欲望或人格筛查。

63 项保护文件、六份冻结 Schema、外部契约、三份规划原件、正式七文件、pyproject/版本 0.1.0、32 个排除项不变；不修改 Assistant，不配置生产凭据、真实服务、常驻进程或自动化。生产 Adapter 和正式恢复仍为 NOT_READY。如修复确需突破冻结边界或扩大范围，停止相关部分并说明，不自行授权。

同步根因、修复过程、矩阵、原始证据、可复现命令、源码身份、完整逐文件清单及排除项；核对静态解析、链接、敏感信息、差异和完整 Git 状态。清单明确区分既有 P17 成果与本次返修增量。

完成后保持 P17 `IMPLEMENTED_NOT_ACCEPTED`，独立复核阻断待确认，不自行宣告验收或关闭监工结论。D-071 不创建；不暂存、commit、push、merge、rebase、切换分支、tag/release；不进入 P18。提交返修报告后停止，等待独立复核及用户另行确认。
