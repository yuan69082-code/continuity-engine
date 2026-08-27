# P01 Snapshot 组件与清理策略

> 适用范围：一次性 TEST Sandbox。禁止用于正式 Subject、Owner Domain 或生产恢复。

## 1. Snapshot 完整组件

| 逻辑组件 | 当前物理来源 | 逻辑证据 | 回滚要求 |
| --- | --- | --- | --- |
| SubjectState | sandbox branch `subject-state/` | canonical state hash、revision=快照 revision、count | 完全一致 |
| Event | SubjectState envelope update history | Event 列表 hash、count | 完全一致 |
| StateMutation | Event 中 mutation 列表 | mutation hash、count | 完全一致 |
| Evolution | StateUpdateRecord history | update hash、revision、count | 完全一致 |
| Memory | `test-memory/memory-ledger.v1.json` | candidates + influences hash/count | 完全一致 |
| Learning | `learning/` | LearningEvent、PersonalityTrait、LearningRecord hash/count | 完全一致 |
| relationship state | SubjectState relationship 分区 | canonical hash、revision | 完全一致 |
| WakeSession | `awakening/sessions/` | 完成会话结构 hash/count | 完全一致 |
| ThinkSession | `thinking/` | 完成会话与 ThinkingResult hash/count | 完全一致 |
| ActionSession | `test-actions/action-sessions.v1.json` | test-only durable ActionSession hash/count | 完全一致 |
| operation journal | `integration/operation-journal/` | operation/checkpoint JSON hash/count | 完全一致 |
| completed result ledger | `integration/result-ledger/` | immutable completed result hash/count | 完全一致 |
| capability ledger | `integration/capability-ledger.v1.json` | request/attempt hash/count | 完全一致 |
| resource ledger | `resources/` | ResourceState、usage、decision hash/revision/count | 完全一致 |
| SubjectBinding | `binding/subject-binding.v1.json` | binding hash/count | 完全一致 |
| AwakeCycle | `awakening/cycles/` | cycle hash/count | 完全一致 |
| subject clock | `clock/subject-clock.v1.json` | frozen UTC time hash | 完全一致 |
| State Fixture | `fixture/state-fixture.v1.json` | synthetic metadata hash/revision | 完全一致 |
| test trace | `test-trace/subject-clock-trace.v1.json` | structured summary hash/count | 完全一致 |

以上共 19/19 个必需组件。每项记录唯一安全相对物理位置和由物理文件清单产生的聚合 SHA-256；branch 全部物理文件还必须与 Manifest 的 closed-world inventory 完全一致。任一项不存在、不可解析、处于 link/reparse path、数量/revision 不符、映射重复/遗漏或逻辑/文件 hash 不符，Snapshot/rollback 均失败关闭。WakeSession、ThinkSession、ActionSession 和 operation/completed result 都来自本轮标准交互的真实 durable/test-durable 记录，test trace 不替代这些会话。

Snapshot 创建成功后，descriptor 与 registry 保存独立的 `snapshotId → manifestHash` 外部锚点。校验顺序先核对外部锚点，再核对 Manifest、component identity、logical 内容和 physical payload；因此修改 payload/逻辑/组件 hash/Manifest 并重算内部 hash 仍会返回 `SNAPSHOT_TAMPERED`。

## 2. 原子回滚步骤

1. 验证 registry、Sandbox descriptor、TEST/synthetic/non-promotable 标识。
2. 验证外部 anchor、snapshot/sandbox/subject/namespace/branch/revision 身份、snapshot manifest、19 个逻辑组件与 closed-world physical inventory。
3. 在同一 branch 父目录构造 staging 并再次校验。
4. 原子把当前 data 移到 backup。
5. 原子把 staging 安装为 data。
6. 再次执行全组件逻辑校验。
7. 成功后删除 backup；失败则移除新 data、恢复 backup 并返回 `ROLLBACK_FAILED`。

回滚不删除正式 Event，不访问正式路径，不接受正式 subject ID，也不把测试快照解释为 P20/P21 的生产恢复。

## 3. 保留策略

| 结果 | RetentionMode | 到期 | 动作 |
| --- | --- | --- | --- |
| 验收成功 | `SUCCESS_AUTO_CLEAN` 语义 | 有效 acceptance receipt 与证据导出后立即 | 自动清理目标 Sandbox |
| 遗弃 ACTIVE | 创建即 24h lease | 24 小时 | 下一次入口扫描清理 |
| 测试失败 | `FAILURE_24_HOURS` | 24 小时 | 保留供诊断，到期入口扫描清理 |
| 显式调试 | `DEBUG` | 正时长且最多 7 天 | 到期入口扫描清理 |
| 手动清理 | 当前登记状态 | 即时 | 仅清理指定、已登记 Sandbox；重复调用幂等 |

没有后台 timer、线程或 Scheduler。扫描只在 manager 启动、Sandbox 创建/结束或显式维护操作发生，并处理到期 ACTIVE/RETAINED Sandbox。

## 4. 清理安全门

清理必须同时满足：

- sandbox ID 存在于 P01 registry；
- target 是 `sandboxes/` 的直接子目录且绝对路径与 registry 一致；
- descriptor 存在、hash 匹配，并声明 TEST、synthetic、`promotionAllowed=false`；
- target 及路径组件不是 symlink、junction 或 reparse point；
- target 不与仓库、正式数据根、用户主目录、受保护路径或其危险父子范围重叠。

未知目录、marker 缺失、registry 冲突、路径不明、正式路径、仓库、主目录、父目录、路径穿越和链接目标全部拒绝。失败不得扩大删除范围。

## 5. 当前验收证据

P01 Engine 专项包含真实标准交互 `changed=true`、19/19 durable 组件、closed-world 未映射/重复映射拒绝、外部 anchor 重算攻击拒绝、acceptance receipt 门、注入回滚故障、formal 整树 hash、repository root 授权、promotion、ACTIVE lease、retention、expiry、手动清理、link/junction 和 frozen clock 回归。用户已于 2026-08-27 正式验收 P01；P01 与 Engine side 均为 `ACCEPTED`，P01 Vio dependency 为 `NONE`。该验收不把本策略提升为正式 Subject、Owner Domain 或生产恢复能力。
