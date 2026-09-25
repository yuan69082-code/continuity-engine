# W02 整体贯通：首次集成反例与待确认定点补修

> 本文保留**定点补修前**的真实停止点。用户随后已确认该恢复路径的最小运行代码补修；后续状态和原始修后结果见[补修报告](repair-report.md)，不要把本文的待确认状态当成最终状态。

2026-09-25。本轮是已验收 W02-A/B/C 的同版核验；**W02 整体仍为 `IN_PROGRESS`，贯通验收项为 `BLOCKED`**。本报告不是新阶段决定，也不是 W02-A/B/C 原验收的撤销。`PLANNING_CONFLICT=NONE`；本轮真实贯通恢复失败使 `EVIDENCE_CONFLICT=PRESENT`，须待定点修复和独立复核。历史 F1/H1/F2 的 `UNKNOWN` 不变。

## 现场及运行口径

- Engine `main`，开工 HEAD、本地 `origin/main`、实际远端 `main` 都为 `d6bd8ecf3041578cf5f101d6feecf7d22a451571`。开工 296 份源码/测试/资源指纹 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea`。只新增本轮正式集成测试后，运行前后 297 份指纹均为 `sha256:322d7464a48f2f95475c51fbe1c274eabdbbde85755e10d2ee7df1e10b90fa43`。既有运行实现、原正式测试、保护项、正式数据及 57 项排除材料均未改。
- [现有 A/B/C 联验](baseline-existing-link-01.json)于开工源码实跑 1/1 PASS（3.854 秒）。它证明有限的一段接线，不证明所有贯通恢复情形。
- [首次新增贯通组](integration-draft-01.json)实跑 5 项：3 PASS、2 ERROR、0 SKIP，20.938 秒，退出码 1；[stdout](integration-draft-01.stdout.log)、[stderr](integration-draft-01.stderr.log)原样保留。其中原始消息→A 站内处置→B 回答前旧记忆→C 的 E5-A 回执和当前候选→最终 Context/Thinking，以及无关材料不展开、只读零副作用，均为通过的正向对照。组内数字不可写成 5 PASS。
- [A 单独恢复对照](a-only-recovery-01.json)在上述新测试指纹上 1/1 PASS（1.796 秒，退出码 0）；[A+B/C 贯通恢复反例](combined-recovery-01.json)在**同一指纹**上 1 ERROR（1.631 秒，退出码 1），原始 [stderr](combined-recovery-01.stderr.log) 保存。全部运行前后源码、保护、正式数据和排除项一致。

## 已复现的恢复缺口（N01/N02/T18）

正常 Engine 原始消息提交，W02-A 的 `memory` 站在隔离 TEST 注入的局部失败后留下可信 `FAILED_WAITING` 回执；`input_outcome` 在失败后、同根重开后都返回只读 `PENDING`、`resume_stations=['memory']`，未调用模型或外部能力。再次提交**原请求身份**时，预期仅补做失败站，复用成功站。实际抛出 `INPUT_UNFINISHED_STATION_WITH_CONTEXT`，没有完成该请求。

只读代码定位：`continuity_core_service.py` 的 `_prepare` 在 `recall_enabled` 且已存 `input_preparation.continuity_context` 时直接返回；它没有先判定 W02-A 的各站回执是否仍待补。`continuity_interaction_service.py` 于是带该准备 Context 进入 `before_thinking`，`input_processing_service.py` 正确拒绝未完成站。A 单独配置没有这条 B 的快捷路径，原 A 正向恢复通过。这是 A+B 组合中的实际缺口，不能通过删除 `before_thinking` 的校验、伪造完成回执或改用新请求身份解决。

建议在现有 `ContinuityCoreService._prepare` 的复用准备 Context 入口，先按原操作记录和当前材料核验 W02-A 回执是否已完整；仍有合法 `FAILED_WAITING` 时复走原 `InputProcessingService.prepare` 补做失败站，重新建立与现行回执绑定的 Context；已完成站、原请求、旧事实保持不变。至少验证同进程/重开、当前授权和来源、重复提交、失败站仍失败、撤权及数据损坏拒绝；兼容关闭 A 或 B 的旧路径。**这会修改已验收的公共运行实现**，本轮贯通授权明确要求另获用户定向确认，故尚未改动。

## 第二项首次报错的界定

两独立根、原文和派生材料四次正常消息建立历史后，新加的“部分撤回后下一轮”组合测试在第四次提交遇到 `RECALL_TIMEOUT`。原 B 策略的单轮时延上限为 1000 ms；首次日志显示它在处理复杂 TEST 历史时按已有预算失败。这是当前集成测试未完成的结果，**还不是已证明的撤销传播回归**；原 C 已验收的撤回测试不因该报错变为失败，也不能用旧 C 通过冒充本轮组合通过。后续应在不改原时限、不删同根/部分撤回断言的条件下，明确分离必要链路和独立负载，重做同源码定点；若仍能在正常负载稳定触发，再以新证据分类。

## 已取得的最小只读链路样例

本轮通过组的结构输出在 [stdout](integration-draft-01.stdout.log)：同一主体的第一条原消息生成 `conversation/memory` 站记录（memory 判定为 `MESSAGE_IS_NOT_VERIFIED_EVENT`，没有把收到材料当成记住）；第一轮经原 E5-A 生成 capability request `action-cap:b8c7…` 与 receipt `receipt:9936…`，外部资料仅为候选。第二条原消息在回应前评估旧进食 Event/Memory，并在 Router/Composer 的最终片段里含 `engine.current-input`、`engine.memory`、`engine.timeline`、`engine.external-candidates`；Fake Provider 收到的正是该最终 Context。该样例不宣称候选为事实或真实外部服务已接入。

## 当前停止点

W02-A/B/C 既有 `ACCEPTED`，W02 整体保持 `IN_PROGRESS`；当前贯通检查 `BLOCKED`，不能提交 `IMPLEMENTED_NOT_ACCEPTED` 或执行终局全量。需要用户确认上述**仅限 A+B 失败站恢复入口**的定点运行代码补修，之后再以固定源码完成正式集成、A/B/C 兼容、公共兼容及完整回归。本轮没有 Git 写操作、W03/P19 开工或远端 CI 结果。
