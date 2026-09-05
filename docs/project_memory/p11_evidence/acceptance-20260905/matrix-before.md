# P11 规划、施工、测试与验收矩阵

> 当前门：P00—P10 = `ACCEPTED`；P11 / P11 Engine side / P11-01—P11-12 = `IMPLEMENTED_NOT_ACCEPTED`；P11 Vio dependency = `NONE`；P12—P23 = `NOT_STARTED`。D-057 已使用；D-058 未创建、未使用。测试通过不等于用户验收。

| Planning Item | Implementation | Verification | Current Result | Status | Evidence | Boundary | Acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P11-01 调度记录、稳定身份、绑定与状态机 | `SchedulerTask`、稳定 identity/attempt、subject/environment、六态终态保护；submit 在仓储读取前检查纯净初态 | round trip、重复提交、身份冲突、跨绑定拒绝；伪造运行历史/attempt 上限入队前拒绝，文件与资源零变化；合法恢复 | 首次 admission 缺口已定点修复，6 项新增与 45 项 P11 专项本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | [58 第 8 节](58_P11_测试索引与验收入口.md#p11-admission-repair)；[57](57_P11_队列恢复重试取消与投递语义.md) | 仅首次 admission；不收紧持久化恢复对象 | 返修待独立复核和用户验收 |
| P11-02 priority 与确定性排序 | `effective_priority` + due/sequence/taskId 稳定排序 | 优先级、同条件顺序、重启后排序 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | `test_priority_due_time_and_sequence_are_deterministic` | priority 不是 Will/Desire | 待验收 |
| P11-03 dueAt 与可信 UTC | 只接受 timezone-aware UTC；到期前不投递 | naive/非 UTC 拒绝、未来到期、乱序输入 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | P11 Domain/Queue tests | 不修改 Event 客观时间 | 待验收 |
| P11-04 wakeReason 与单次 opportunity | event/scheduled/internal/runtime-recovery 枚举；通知只含结构化引用 | Event 与 Scheduled WakeSession 组合、无心理/Action 字段 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | Awakening 组合测试 | 不调用 model/Planner/Action | 待验收 |
| P11-05 原子持久化与并发保护 | 单一 `queue.v1.json`、临时文件+fsync+replace、queue/task revision、共享进程锁、record hash | 重启、过期 revision、损坏 JSON、未知字段、顺序篡改 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | Repository tests | hash 仅检损，不代替可信回执 | 待验收 |
| P11-06 有界队列与背压 | 固定 capacity；终态不占 active capacity；明确 BACKPRESSURE | 满队列拒绝并断言文件零写入 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | `test_backpressure_has_explicit_result_and_zero_queue_write` | 不丢弃既有任务 | 待验收 |
| P11-07 防饥饿与 aging | `priority + floor(wait/agingInterval)`；再按 due/sequence/id | 102 个冻结逻辑 tick、持续高优先到达、低优先在第 100/101 界内获得机会 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | bounded-long 与 aging tests | 无真实 sleep、结果确定 | 待验收 |
| P11-08 ResourceManager 复用 | attempt 前 `preview`；实际 Wake 复用 `ResourceAwareWakeScheduler.request_wake` | 资源不足零 attempt/零 Wake/零投递/资源和队列零写；成功只分配一次 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | resource tests；Awakening/Resources 兼容回归 | 不另建资源系统 | 待验收 |
| P11-09 静默时段与 Fake Notification | UTC quiet-hours；持久 TEST Fake receipt、零网络 | 跨午夜、静默零 attempt；Fake receipt/restart | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | P11 Fixture 与专项 | Fake 不代表生产 Adapter | 待验收 |
| P11-10 有界重试与 UNKNOWN | 指数有界 backoff、稳定 attempt、UNKNOWN 查询退避、receipt exact binding | FAIL/NOT_DELIVERED、超限、query exception、普通字符串、绑定冲突、重启 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | Recovery tests | 禁止盲目重试 | 待验收 |
| P11-11 取消与 no-duplicate-dispatch | queued/retry 可幂等取消；UNKNOWN 先核实；completed 不倒退 | 重复 cancel/tick/receipt、未知后 delivered/not-delivered、投递后中断恢复 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | Recovery tests | 本地持久化语义，不宣称生产 exactly-once | 待验收 |
| P11-12 组合、Golden、Trace 与入口 | Awakening/Resource/Event/Timeline/P09 正常链；版本化 Golden 和公开服务入口 | 客观 Event 不变、C1 状态/模型/Action 不被 Scheduler 改写、Golden 重复 hash 一致 | 已实现并本地通过 | `IMPLEMENTED_NOT_ACCEPTED` | [58](58_P11_测试索引与验收入口.md) | 不提前实现 Persistent Runtime/P17 | 待验收 |

## 现行结果

- 首次 admission 定点返修：新增 6/6 PASS（0.335 秒），完整 P11 45/45 PASS（7.529 秒），均 0 SKIP、0 FAIL；独立复核发现的缺口已本地闭合，交回返修复核。
- 本次按用户授权仅运行定点与完整 P11 专项；下列 39/833 全量等结果为修复前历史，未冒充本次验证。

### 首次 admission 返修前的历史结果

- P11 专项最终代码版：39/39 PASS，0 SKIP、0 FAIL，7.704 秒。
- 直接相关最终代码版：238 项，237 PASS、1 既有环境 SKIP、0 FAIL，317.671 秒。
- P01—P11 综合矩阵最终代码版：475 项，474 PASS、1 既有环境 SKIP、0 FAIL，371.445 秒。
- Engine 完整稳定三轮：每轮 833 项，均为 832 PASS、1 既有环境 SKIP、0 FAIL；415.083 / 419.188 / 422.227 秒。
- 档案后终局：P11 39/39 PASS（7.673 秒）；Engine 833 项中 832 PASS、1 既有环境 SKIP、0 FAIL（438.796 秒）。
- 唯一 SKIP 是既有 P08 symlink 创建权限 `WinError 1314`；真实 Windows junction 用例实际执行并通过。SKIP 不计为 PASS。
- 初始红灯、过程缺口、辅助测试/证据工具错误全部保存在 [58](58_P11_测试索引与验收入口.md)，未被后续通过覆盖。

## 状态门

本矩阵十二项均只到 `IMPLEMENTED_NOT_ACCEPTED`。D-058 未创建；没有规划监工独立复核或用户正式验收结论。`PLANNING_CONFLICT = NONE`；`EVIDENCE_CONFLICT = NONE` 仅表示当前本地实现没有未闭合证据矛盾，不改变任何历史失败。
