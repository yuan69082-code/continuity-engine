# P08 Natural/Direct Action 与 Optional Planner 架构边界

> P10 现行门：P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。 D-056 与最终依据见 [最终复核及验收记录](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md#p10-accepted)。Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`；Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`；[CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 为 794/794 PASS、0 SKIP、0 FAIL。历史 FAIL、SKIP、旧 CI failure、辅助错误及 P09 segment 10 stderr 缺失/根因 UNKNOWN 原样保留。

> 下文的 P08 收口与后续未授权状态均为当时记录；D-053 是后续独立授权，不改变 P08 十二项 ACCEPTED 或原有限泛化边界。

> P08 验收时的快照（历史保留）：当前 P00—P08 = `ACCEPTED`；P08 / Engine side / P08-01—P08-12 = `ACCEPTED`；P09—P23 = `NOT_STARTED`。用户于 2026-09-04 正式验收（D-052），D-051 与全部返修历史保留。P08 Vio dependency = `NONE`；PLANNING_CONFLICT/EVIDENCE_CONFLICT = `NONE`。本次验收不扩大方案 A，不代表生产 exactly-once，不授权生产 Adapter、P09/P17 或 Git 操作。

## 1. 唯一执行事实与身份映射

| 对象 | 稳定身份 / 归属 | 持久化与恢复 |
|---|---|---|
| Thinking Need/Decision | producer + decision + subject/environment；封印 P06 snapshot/revision/fragment IDs | 可信 producer 精确验证；正文和 Observation 不产生授权 |
| Direct Action | 单个原子 specification；无 Goal/Plan | operation 按 subject/environment/producer/decision/step 派生 |
| Optional Plan | choice canonical hash 派生 plan ID；依赖只引用先前步骤 | 可重建结构，不保存第二份执行状态 |
| Plan Step | 父 choice + step ID | 每步独立 operation、capability request、idempotency key；不解除旧唯一约束 |
| Internal Capability Request | 显式 internalVersion，不伪装 model.generate | 同一个 E5-A capability ledger；绑定 Adapter ID、能力配置 hash、恢复目标 |
| Attempt / Result | 同一个 request；status、receipt、gate reason、canonical hash | 与旧模型 attempt 共用保存、唯一成功和 terminal 门；按类型恢复 Action/Step 或原 ThinkSession |
| Fake Receipt | Adapter 的原子 synthetic effect/receipt | 只证明该本地 Fake 的效果；不是第二 Engine 请求/重试账本，不代表生产 exactly-once |

## 2. Direct 与 Planner

`OptionalActionPlanner.plan()` 对单步、原子、无长期/额外恢复规划需求的 choice 返回 None。表达、沉默、联系、停止和明确选定的简单能力均不需要 Goal/Plan；这不跳过执行门。

多步、依赖、显式 planning requirement 或能力配置声明 non-atomic 时必须生成计划；Planner 关闭则返回 `PLANNER_REQUIRED`，Fake execute 为零。Information Need 和 Action Intent 使用相同输入封印和执行检查。P08 不生成 P14/P15 心智，不把 Planner 当作意志来源。

## 3. 有限 E5-A 泛化

源码：`domain/action_planning.py`、`domain/action_capability.py`、`services/action_planning_service.py`；加法式扩展已有 `ActionService`、`CapabilityCoordinationService`、`CapabilityRepository` 和 `JsonIntegrationResultLedger`。

同一个 `integration/capability-ledger.v1.json` 路径可保存旧模型与内部行动。仅含模型时保留 format 1；加入内部行动时使用 format 2。旧 request/result/attempt 的 JSON、ID/hash 不变，旧等待、已完成 operation 与原 ThinkSession 恢复继续走旧代码。模型 operation journal/completed result 的外部结构不变；内部 Action/Step 的等待和完成状态直接由同一 capability ledger 投影，不新增另一份 journal/result 事实。非模型记录不经外部 validator 放行，也不暴露 HTTP 入口。

## 4. Authority 与执行门

可信 producer 与 constraints 是宿主中立 Port，本阶段只接 TEST Fixture。所有新执行都经 `ActionService.assess_local_action()` 复用既有 PermissionProvider、RiskEvaluator、ResourceEvaluator；随后检查 Recoverability 和 Reality Boundary。Direct/Planner 两条路径调用同一门，不存在 Adapter 捷径。联系与高风险 test tool 需要绑定 request idempotency key 的明确确认，critical 一律拒绝。

外部结果只成为验证过的 ActionReceipt/Result，返回对应步骤。P08 不消费 P07 结果作为执行授权，不修改 P06 snapshot，不写 SubjectState、Event、Memory、Summary、Timeline 或 revision；输出 `direct_state_write_allowed=false`、`evolution_commit_allowed=false`。合法主体状态更新继续只走既有 Action Gate → Event/StateMutation → Evolution；P08 不新增状态写通道。

## 5. 阶段与长期开放

不建设 P09 生产接线、P17 通用执行引擎、后台 Scheduler、插件平台或生产 Adapter。本地隔离不是长期禁止行动或 Context 进入 Thinking；P09/P16/P22 按既定顺序开放正式链接线、外部能力和 Provider/Vio/PWA 生产重连。

## 6. 监工返修：存储完整性、执行事实和新执行授权分离

能力账本的 schema/hash 检查只证明记录内部完整，不证明 Adapter 实际执行。`CapabilityCoordinationService.action_attempts()` 对每条历史重验内部状态/证据约束：SUCCEEDED/FAILED_TERMINAL 必须携带匹配请求的 receipt，并经当前可信绑定 Adapter query 精确核实；EXPIRED 没有执行回执，只能在原 Adapter 明确返回类型化 NOT_EXECUTED 时作为本地停止决定消费。终态重放、依赖放行和 `accept_action_result()` 追加入口共用此门。重建 repository/Adapter 后仍必须重验；底层原始 ledger 读取只用于存储/审计，不能作为执行授权。缺失、UNKNOWN、查询不可用、字段漂移或停止决定与真实回执冲突均失败关闭，不修写旧历史，不执行后续步骤。

恢复输入仍须通过原 P06 COMPLETE 封印、trusted producer、subject/environment、choice/snapshot/revision/fragment、plan/step、Adapter ID/policy hash 的精确关联。当前 Context 失效只撤销新工作权限，不抹去已发生事实：允许已存在且完全匹配的 request 查询与归账，不允许创建新 request。新 execute、NOT_EXECUTED 受控 retry 和后续未执行步骤必须再通过当前 Context 与所有执行门。无新增仓储或请求账本，Fake receipt 仍只是原有独立执行事实验证端口。

参见 [矩阵](44_P08_规划施工测试验收矩阵.md)、[恢复语义](45_P08_DirectPlanner执行恢复语义.md)、[测试索引](46_P08_测试索引与验收入口.md)、[D-051](04_决策记录.md)。

**2026-09-04 无回执终态返修：** 原“只要 receipt 非空才验真”遗漏已由两条正式失败回归证明。内部结果现只允许 PROPOSED、UNKNOWN、SUCCEEDED、FAILED_TERMINAL、EXPIRED；取消和 retryable terminal 等本阶段不支持的输入明确拒绝，不建设取消系统。构造、反序列化和 InternalActionAttempt 追加执行等价结构约束；真实执行依据仍由同一协调器查询端口验真，不新增字段、存储版本、账本或生产验签基础设施。choice 过期不否定已经发生的成功；原 UNKNOWN 仍可归账真实回执。已存 EXPIRED 若与后来查询的回执冲突，必须拒绝消费并保留原 ledger 与 Fake 历史，不静默覆盖。

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
