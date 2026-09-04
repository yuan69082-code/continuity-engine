# P05 权限、检索预算、来源失效与 Context Trace 语义

> P08 现行门：P00—P08 = `ACCEPTED`；P08 / Engine side / P08-01—P08-12 = `ACCEPTED`；P08 Vio dependency = `NONE`；P09—P23 = `NOT_STARTED`。D-051 保留施工决定，D-052 已登记用户正式验收；不授权 P09 或 Git 操作。见 [P08 矩阵](44_P08_规划施工测试验收矩阵.md)。

> 用户于 2026-09-03 正式验收 P05、P06；本文件规则及 P06 当前均为 `ACCEPTED`。P07 已由用户于 2026-09-04 正式验收，P07 Vio dependency = `NONE`，P09—P23 = `NOT_STARTED`。

## 1. 权限门

候选必须同时满足：

1. source binding、routing request 与 candidate 的 subject ID 一致；
2. environment 一致；
3. visibility 明确为当前 Engine 内允许的 `ENGINE_PRIVATE`；
4. source 与 candidate 状态有效；
5. version、version hash 或 revision 与请求及取用前重验结果一致。

权限未知、跨主体/环境和不可见均拒绝。Router 不读取另一条来源、旧缓存或全库内容绕过拒绝；Trace 只记稳定引用、hash、状态和原因码，不记 secret candidate 的正文。

## 2. Retrieval Budget

P05 只执行候选数量预算：默认 50，可配置 30—80。Router 在读取任何来源前，先根据本轮已选分区和稳定 source 顺序分配每来源 limit；所有来源 requested limit 之和不得超过总预算。source 返回超过其声明范围时立即失败关闭，不得用最终排序/截断掩盖过读。候选排序后仍受总量上限，不因一个来源失败而扩大其他来源查询。

`context_budget_hint` 与 Retrieval Budget 一同携带，但只供未来 P06 使用；P05 不拼装最终上下文、不执行 token 裁剪。Storage Budget 仍属于各权威仓储自身，不由 Router 修改。

## 3. 来源资格

purpose/signals 先决定本轮打开的逻辑分区，required partition 再以显式规则加入。未选分区记录 `NOT_OPENED/PURPOSE_NOT_SELECTED`，其来源记录 `NOT_OPENED/PARTITION_NOT_SELECTED`；requested limit 与 retrieve 调用次数均为 0，未选来源不能凭自己的 relevance 反向打开分区。

- SubjectState 必须匹配 routing request 的精确 revision。
- Memory 必须为 ACTIVE，temperature 为 HOT/WARM/COLD；ARCHIVED 保留在仓储供显式审计，但不进入普通路由。
- DerivedSummary 必须是当前 ACTIVE 版本；INVALIDATED/SUPERSEDED 不进入候选。
- Timeline/Event 只读适配器按 P03 派生状态排除 corrected/revoked target，不改写 Event。
- 本地 Fact source 必须有显式版本和内容 hash，仅供 TEST/RESEARCH Fixture。
- Attention、Desire、Conflict、Somatic、Expression 等未来分区没有实现 source 时必须标为 UNAVAILABLE/FEATURE_GATED，不生成假内容。

Memory/DerivedSummary 通过 `MemoryRepository.query_memories/query_summaries` 在仓储边界执行 subject/environment、状态、可见性/温度、查询词、确定性排序和 limit。原子文档仍在加载时完成 P04 全量完整性验真，但 Router 不通过公开 `list_*` 接口把全部对象加载为候选后再截断。Timeline 以完整只读 Event 投影为来源，先按 relevance/recency 排序再截取请求窗口，因此大历史不会固定只见最早 100 条。

## 4. 两阶段来源验证

每个已选 source 先返回有界 `ContextSourceBatch`。Router 对候选完成结构、subject/environment、partition、status 和权限判断后，在保留引用前再次调用 source validation；只有 stable ID、version、version hash、visibility 和状态仍一致才能进入 Manifest。Timeline 的 initial read 与 revalidate 由同一 query 和同一窗口算法重建，不能初读 30/50 条却用固定 100 条重验。

来源在 query 与保留之间漂移时使用 `SOURCE_STALE`/`SOURCE_INVALID` 等稳定原因拒绝。required source 被拒绝、失效或读取失败时，Route Result 为 INCOMPLETE 或 REJECTED，Manifest 必须为空；此前从 optional source 得到的候选统一标记 `ROUTE_NOT_CONSUMABLE_REQUIRED_SOURCE_FAILURE`，不能留给尚未施工的 P06 误用。optional source 单独失败只在 Trace 中隔离，不会把缺失伪装成完整。

## 5. 确定性排序

候选分数由下列可解释因子构成：

- purpose/结构化 signal 与候选分类、标签的匹配；
- source-provided relevance；
- 相对 route time 的 recency；
- importance；
- activation。

稳定 tie-break 使用 partition、source ID、candidate stable ID、version 和 version hash，不依赖本机时区、集合遍历顺序或随机值。Router 不因普通检索写 access、reinforcement、Memory 或 Learning。

## 6. Context Trace 安全

Trace 记录 request、subject、revision、UTC route time、purpose、feature gate、打开/未打开分区、每来源 requested、retrieved、evaluated、retained、rejected、permission、预算、版本、失效、候选 rank/score/reason 及最终状态。`retrieved` 是 adapter 实际返回数，不能使用最终 Manifest 数量代替；每个来源和分区都校验 `retained + rejected = retrieved`。

Trace 不保存：

- 原始秘密、凭据或 Authorization；
- 完整候选正文；
- 可复用认证材料；
- Provider 隐藏思维链。

Trace 只是一次路由结果中的审计结构，不是第二 Trace Store、缓存权威或下一轮 Router/Thinking/Evolution/Memory/SubjectState 输入。

## 7. Feature Gate 和长期边界

P05 Feature Gate 关闭时返回 FEATURE_GATED 空计划/Manifest/Trace，来源 query 次数为零。P05 不访问 Vio、网络、Provider、凭据、MCP、外部数据库或正式数据。

这一阶段隔离不会永久禁止 Memory 参与 Context 或未来 Provider/Vio 集成。P06、P16、P22 仍按冻结阶段分别开放 Composer/Authority、外部知识能力和真实 Provider/Vio/PWA production integration。

P05 验收不改变上述长期开放边界，也不自动授权 P06。
