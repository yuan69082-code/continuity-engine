# P03 Event 时间与 Timeline 架构边界

> P11 现行门：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-058 已登记用户正式验收。监工独立原反例 2/2 PASS、P11 45/45 PASS（8.371 秒）；39/833 全量等修复前结果继续作为历史保留。本次仅验收归档，不运行全量。[P11 验收入口](58_P11_测试索引与验收入口.md#p11-accepted)。
> 下文保留该阶段施工及验收时的范围、后续未授权状态与测试历史；P09 的本轮新增授权和接线以本页现行门及 47—50 号档案为准，不倒写既往决定。

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

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
