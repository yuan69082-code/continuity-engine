# P03 Event 时间与 Timeline 架构边界

> P08 现行门：P00—P08 = `ACCEPTED`；P08 / Engine side / P08-01—P08-12 = `ACCEPTED`；P08 Vio dependency = `NONE`；P09—P23 = `NOT_STARTED`。D-051 保留施工决定，D-052 已登记用户正式验收；不授权 P09 或 Git 操作。见 [P08 矩阵](44_P08_规划施工测试验收矩阵.md)。

> 阶段：P03——Event 语义、时间系统与 Timeline
> 当前状态：P03 / P03 Engine side = `ACCEPTED`
> 用户验收：2026-08-30；P04 后续独立获权并于 2026-09-01 正式 `ACCEPTED`
> Vio dependency：`NONE`
> 软件版本：`0.1.0`

## 1. 权威边界

- `SubjectState` 是当前主体状态唯一权威。
- `Event` 是已经进入 Engine 的客观历史事实权威；历史只追加，不原地修改或删除。
- `StateUpdateRecord` 保存 Event、应用时 revision、字段 before/after 与原因。
- `Timeline` 只读取 `StateUpdateRecord/Event` 历史并在内存中确定性重建；它没有 save、update、delete 或 overwrite 权限，也不持久化第二份事实。
- Memory 是记忆，Self-Narrative 是解释；二者都不能覆盖 Event 事实。
- PlatformObservation 的 `sourceEventId` 不是内部 `eventId`，不会因 P03 自动写入 Event 历史。

P03 没有改变唯一状态路径：只有 Action Gate 合法批准的 `UPDATE_STATE` 才能创建当前 `STATE_CHANGE` Event/StateMutation，经 Evolution 推进 SubjectState。FACT、OBSERVATION、INTENTION、CORRECTION 和 REVOCATION 无论是否迟到都只能作为无 mutation 的历史记录追加；若它需要影响当前状态，必须由新的当前 Action/Evolution `STATE_CHANGE` 引用该历史事实。既有 LEGACY/interaction 兼容路径不扩大、不重写。

## 2. Event 模型

P03 在原 `Event` 上向后兼容增加：

- 分类：legacy、fact、observation、intention、interaction、state_change、correction、revocation。
- 来源类别：legacy、internal、user、system、platform、external、test；原 `source` 继续保存具体来源名。
- 三时间：`occurredAt`、`observedAt`、`recordedAt`。
- 时间依据：`EXPLICIT`、`PARTIALLY_COALESCED`、`LEGACY_COALESCED`。
- 身份：内部不可变 `eventId`、可选来源 `sourceEventId`、可选链路 `correlationId`。
- 证据：经过验证、可 JSON 序列化的 `EventEvidenceReference`。
- 引用：`caused_by`、`corrects`、`revokes`，目标必须属于同一 Subject 且已经在写入历史中出现。

旧 JSON 只有 `occurred_at` 时，读取后把缺失的 observed/recorded 确定性合并为同一 UTC instant，并明确标记 `legacy_coalesced`。新入口显式提供三时间时，三者必须带时区并满足 `occurredAt <= observedAt <= recordedAt`；调用方不能在缺失时间时声称 `EXPLICIT`。应用显式 Event 时，`SubjectStateService` 只读取一次时钟形成固定 `appliedAt`，要求 `recordedAt <= appliedAt` 并把同一时间传给 Evolution；未来 recordedAt 失败关闭。合并时间不作为独立测量证据。

## 3. 身份、幂等和不可变历史

- 相同 `eventId` 加完全相同 canonical Event body 是精确幂等重放；不会生成第二 Event、mutation、update 或 revision。
- 相同 `eventId` 加不同 canonical body 抛出 `EventIdentityConflictError`。
- 重放返回当前 SubjectState 和原历史 update，并以 `StateEvolutionResult.idempotent_replay=true` 明确说明 `update.after_revision` 是历史 revision，不能被误读为当前 revision。
- `SubjectStateService` 先从权威历史判断 eventId/canonical body；exact replay 与 identity conflict 均不读取或依赖当前 applied clock。只有新 Event 才读取一次时钟并接受 future recordedAt 校验，因此重启、Frozen Clock 或系统校时回退不能重新否定已提交历史。
- JSON 仓储每次读取都会按真实写入顺序验证 update/revision/Event identity 与引用。即使全集中存在目标，前向引用、缺失目标和跨 Subject 引用仍失败关闭。

## 4. 修正与撤销

修正与撤销只能追加新的 CORRECTION/REVOCATION Event，并分别通过一个 `corrects`/`revokes` 引用目标。原 Event 和原 StateUpdateRecord 永不改写。Timeline 为目标派生 `active`、`corrected`、`revoked` 或 `superseded` 状态；该状态不回写 Event Store。交错规则以写入历史顺序计算，revocation 对被指向目标保持终态优先。

## 5. Timeline 查询

确定性排序键为：

```text
occurredAt → observedAt → recordedAt → eventId
```

Timeline 支持：

- occurredAt 闭区间查询；
- classification、具体 source、source kind、correlation 过滤；
- first/last；
- 相对发生顺序；
- 事件间距；
- correlation 和引用链查询；
- 是否包含 revoked Event；
- 默认 50 项、可配置 20—100 项窗口。

跨时区时间统一转换为 UTC，`+08:00`、`Z` 和负偏移表示同一 instant 时再以其余时间与 eventId 唯一排序。Timeline 服务重启后只从同一 JSON Event/StateUpdateRecord 历史重建。

## 6. 核心文件

- `src/continuity_engine/domain/events.py`
- `src/continuity_engine/domain/timeline.py`
- `src/continuity_engine/domain/evolution.py`
- `src/continuity_engine/services/subject_state_service.py`
- `src/continuity_engine/services/action_evolution_service.py`
- `src/continuity_engine/services/timeline_service.py`
- `src/continuity_engine/storage/json_repository.py`
- `src/continuity_engine/testing/p03_timeline_fixture.py`
- `tests/test_event_persistence.py`
- `tests/test_p03_event_semantics.py`
- `tests/test_p03_timeline.py`

## 7. 阶段外边界

P03 本阶段没有实现 P04 Memory Consolidation/DerivedSummary、P11 Scheduler、P17 Reality Execution、P20/P21 生产恢复、P22 Vio/PWA 重连、真实 Provider、网络或生产数据库。其后 P04、P05、P06 已分别通过独立 Stage Brief 获权并正式 `ACCEPTED`；P07 已通过独立 Stage Brief 实现，并由用户于 2026-09-04 正式验收，P09—P23 保持 `NOT_STARTED`。P03 Vio dependency = `NONE`。
