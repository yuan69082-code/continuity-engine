# P19 前 R1—R4 合并返修：独立复核

日期：2026-09-20。结论：仍有三项可复现阻断，不建议验收、提交、push 或进入 P19。

本轮只审查和隔离测试，没有修改 Engine 实现、测试、档案或 Git 状态；本报告和独立探针仅存放于规划仓库。没有调用真实服务、设备或生产凭据。本报告不是新的施工授权，也不是用户验收记录。

## 1. 本轮发现（按优先级）

### A1 / P1 / 原 R1 未完整闭合：表达许可仍然决定内部状态能否保存

定位：

- [wake_perception_thinking_action_service.py:307](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/wake_perception_thinking_action_service.py:307)：在内部 Evolution 之前同步调用表达分支。
- [expression_policy_service.py:75](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/expression_policy_service.py:75)：表达确认或现实边界拒绝抛出异常。
- [runtime_cognition.py:107](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:107)：未将表达层拒绝与内部认知提交分离。

复现使用正常 P18 native 路径，保留表达策略开启，不改权限、不禁用任何保护。两组分别只将 `constraints.confirmation_allowed=False` 或 `constraints.reality_ready=False`，然后触发一次无消息认知。

两组都观察到：Thinking 成功完成一次，已经形成 `intentions.dynamic_mind` 提案；原 UPDATE_STATE Action 为 approved=true、automatic=true、requiresConfirmation=false；但表达分支抛出拒绝后，主体 revision 仍为 1，dynamic_mind 仍为空。外部效果与扣费均为 0，宿主仍活着，进入 WAITING_VERIFICATION。

正对照：相同路径全部授权时，revision 从 1 到 2，效果/扣费各一次。另一个对照只拒绝 Execution Adapter，revision 能从 1 到 2，效果和扣费均为 0。这说明补丁修通了 Adapter 拒绝分支，却没有修通表达门槛分支；不是内部写入权限本就被拒绝。

影响：不能把当前结果表述为“现实行动受阻时合法内部认知均可继续”。用户不允许表达或现实表达不可用时，独立内部状态仍会被一起扣住。

建议：表达/现实专属拒绝应保留在对应分支，合法内部提交单独经当前身份、Context、来源、权限、生命周期和 revision 校验后保存。不能关闭表达策略、放宽许可或吞掉全部异常来过测。恢复时也不得重复 Thinking、效果、扣费或 revision。普通 C1 表达开启的同类组合也应补测；本轮实跑反例是 native，普通 C1 相邻代码仅作静态关注，不冒称已复现。

### A2 / P1 / 原 R1 未完整闭合：以两个 Thinking 标志判断混合行动，会漏掉表达路由的现实效果

定位：[continuity_core_service.py:176](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/continuity_core_service.py:176)。

`internal_mutations` 仅在 suggest_future_user_contact 或 suggest_tool_use 为真时收窄内部提案；这两个标志都为假就原样返回全部提案。但现有 CoreDecisionPolicy 仍能生成 `expression.emit`，既有 P17/P18 测试接线会将它路由到 `execution.write`。没有 contact/tool 标志，不等于没有现实效果。

复现：P18 reflect 模式，两个标志都为 false；保留原表达/执行接线，拒绝现实 Adapter，并加入与原正式混合提案测试同类的、合法数据类型的提前完成声明：`continuity.current_focus = ['world write completed']`。

结果：世界效果 0、扣费 0、ActionRun 为 WAITING_CAPABILITY；但 revision 从 1 到 2，当前状态已保存 `['world write completed']`，与独立心智提案一起提交。

影响：同类未完成行动声明，仅因使用不同能力路由就获得不同处理。这里不是发现真实外部越权执行，而是发现状态中提前混入无回执支持的“完成”声明，违反原工单 R1 第 2 条。

建议：混合行动及其效果依赖应依据实际绑定的 Choice/能力路由与可核验回执处理，不能仅依赖这两个标志，更不能改成扫描文本关键词。保留合法独立内部提案、原始模型提案及其来源；未执行/未知结果不升级为已完成。补齐 contact、expression.emit、memory/tool 等实际路由的正反矩阵，保持已有事实恢复和幂等约束。

### A3 / P1 / 原 R4 新增退化：已完成的旧欲望被当成永久停止认知

定位：

- [runtime_cognition.py:121](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:121)：从旧状态排除 act/disappear/abandon/suppress 后计算 active。
- [runtime_cognition.py:128](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:128)：只要旧 desires 非空且 active 为空，就以 ended 否决所有认知需求，包括已重新增长的驱力。
- [dynamic_mind_service.py:130](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py:130)：原动态模型实际支持已完成欲望在需要重新积累后 recur。

独立模块边界反例，不冒充完整跨进程场景：用原 MindDynamics 先正常产生七种内生需要，再通过原 outcomes 接口将它们标为 act（本次已满足），不是直接手写虚假完成状态，也没有执行 STOP/PAUSE。再推进一小时。

结果：动态模型生成的七个欲望均为 recur，最大驱力约 0.28347，明显高于 0.02 的调度变化阈值；但 RuntimeCognition.needs 返回空。未完成需要的对照能请求 cognition，休息对照在 60 秒时不派发、240 秒后可复议。

影响：当所有旧欲望都处于上述结束/抑制阶段时，无新消息、无其他外部触发的认知需求路径可能持续被挡住。宿主存活不能证明内部认知仍在推进。“这次已经满足”不等于主体选择永不产生新需要。

建议：区分个别旧目标完成/放弃、临时抑制、合法重新出现的新需要，以及真实主体暂停/归档/STOP。保留最低间隔、预算、休息与明确放弃语义；不能通过强制恢复旧目标来修。调度可采纳原动态模型已有的有根据需求，不应自己编造心理内容。补齐原正常增量触发未被新 ended 条件切断的回归。

## 2. 已通过和未通过分别是什么

| 范围 | 本轮判断 |
|---|---|
| R1 Adapter 拒绝、资源拒绝、UNKNOWN 与独立内部提交 | 原正式测试通过；独立 Adapter 拒绝对照也通过。但 A1、A2 尚未闭合。 |
| R2 名称 critical/noncritical 风险启发式 | 三项正式测试复跑通过，删除名称子串规则，原 HIGH/CRITICAL 与能力风险下限仍有对照。本轮未发现新阻断；不代表提前验收未来完整风险分级。 |
| R3 经历形成倾向、保留/修订 Will、重复根与撤回 | 正式正常链、恢复、相反心理及来源用例复跑通过。本轮未新增确认的 R3 缺陷；不是对所有长期成长行为作无限保证。 |
| R4 稳定/饱和驱力与既有未决关注 | 原正式测试通过，真实子进程测试也已独立通过；新增 A3 说明正常“满足后再次产生需要”的路径仍有回归。 |

## 3. 实跑记录与证据口径

| 记录 | 实际结果 | 秒 | 口径 |
|---|---:|---:|---|
| formal-01 | 33 PASS、1 FAIL | 79.285 | 34 项全部执行；其中子进程失败是本复核 runner 未传 PYTHONPATH，子进程无法导入包。原证据保留，不算 Engine 缺陷。 |
| formal-process-02 | 1 PASS | 6.780 | 仅补跑上述一项；修正 runner 的子进程环境，没有修改 Engine 测试、断言或源码。合计 34 个唯一正式测试均有本轮独立 PASS。 |
| independent-01 | 4 PASS、4 FAIL | 6.302 | 首版边界探针；其中“提前完成声明”误用标量而非列表，未进入目标断言，不据此判定 A2。其余反例证据保留。 |
| independent-02 | 4 PASS、4 FAIL、0 ERROR | 6.336 | 修正探针数据类型后，A2 在真实保存后的目标断言失败。三个问题均有有效反例。 |
| independent-03 | 4 PASS、4 FAIL、0 ERROR | 6.394 | 最终探针，增加原 Action 批准/提案字段诊断，行为断言不变；四个失败对应 A1 两项、A2 一项、A3 一项。 |

最终 8 项边界测试的四项通过对照是：授权完整的 native 一次提交/一次效果；仅 Adapter 拒绝时内部可提交且零效果；未结束欲望可提出认知；休息间隔仍有界。

各组包含和重复运行不相加为唯一测试数。所有失败、辅助错误和先前运行结果均保留，没有删证据或“跑绿覆盖失败”。

独立入口（绝对路径）：

- [最终独立探针](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/test_independent_boundaries.py)
- [最终结果与运行前后源码快照](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/independent-03.json)
- [最终原始输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/independent-03.log)
- [三轮结构化观察，按时间追加](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/independent-observations.jsonl)
- [身份与交付证据核对](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/identity-audit.json)

复跑使用新标签，不覆盖旧输出；当前未修复版本预期仍为 4 PASS / 4 FAIL。示例：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:/Adobe/python.exe' 'C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-repair-independent-20260920/run_review.py' independent-new-label test_independent_boundaries
```

runner 自行配置 Engine 的绝对导入路径及子进程环境；结果只写规划审查目录，使用隔离 TEST 夹具。诊断 observations 文件追加新记录，原有结果 JSON/log 不覆盖。最终结果含复核脚本 hash，早期辅助版本结果另行保留。

## 4. 代码身份与提供方全量结果

已实际核对：

- HEAD：`cb528d74884990915737b491ca6a9f2c35cc512a`，与本轮开工基线一致。
- 当前 274 个源码/测试/资源文件与 final-source、最终审计及选定专项/兼容/全量的运行前后 hash 完全一致。
- 源码集合 hash：`sha256:e58eceb0c28b1f753ce9be059ff22b6bd4d5cf1562d64737b6f5cd318908cc93`。
- 当前发现 1551 个唯一测试身份；原 1517 个全部存在，新增 34 个，与选定全量身份完全一致。
- 63 项保护文件、三份规划原件、7 个正式数据文件及正式数据树、31 个 P10 排除文件及 1 个既有 P14 接续文件无差异；10 份独立原件/归档副本一致。
- 154 项交付清单的可核 hash 全部匹配，32 项排除未动；264 个 Python 文件语法解析通过。
- 本轮每组运行前后 Engine tracked/untracked 内容 hash、状态及 HEAD 一致。

引用而未由本轮重跑的提供方结果：

- combined-04：34 PASS，103.701 秒。
- compatibility-final-02：175 PASS，196.425 秒。
- full-final-02：1550 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1765.117 秒。

这些全量记录与当前文件的对应关系真实成立，但不能覆盖新增独立反例。本轮未重跑全量、未取得远端 CI 结果，不宣称独立全量通过或 CI PASS。远端同步情况不在本轮另作查询，不能将本地 origin/main 当作新查远端。

## 5. 建议停止点

这不是四项全部失败，也不是要求推倒重做。建议仅围绕 A1/A2/A3 做一轮有限补修并保留已通过部分，再交回独立复核。若修改必须扩大保护文件、正式 Schema、公共授权语义或生产边界，仍需用户另行确认。

当前批次继续保持 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT。本次三个问题不得混入历史 F1/H1/F2；它们的 UNKNOWN 与原 P18 验收历史不改写。不自行登记验收、不提交或 push、不进入 P19。
