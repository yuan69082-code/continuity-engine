# P05 Context Router 架构边界

> P11 现行门：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-058 已登记用户正式验收。监工独立原反例 2/2 PASS、P11 45/45 PASS（8.371 秒）；39/833 全量等修复前结果继续作为历史保留。本次仅验收归档，不运行全量。[P11 验收入口](58_P11_测试索引与验收入口.md#p11-accepted)。
> 下文保留该阶段施工及验收时的范围、后续未授权状态与测试历史；P09 的本轮新增授权和接线以本页现行门及 47—50 号档案为准，不倒写既往决定。

> 当前状态：P00—P07 = `ACCEPTED`；P07 = `ACCEPTED`，P07 Vio dependency = `NONE`；P09—P23 = `NOT_STARTED`。用户于 2026-09-03 正式验收 P05、P06，决定分别见 D-046、D-048；P07 施工决定见 D-049。

## 1. 职责

P05 Context Router 位于结构化 `PerceptionResult` 之后，负责回答“本轮查哪些逻辑分区、向哪些已授权来源取多少候选”。它产生三个可序列化、可复算的结果：

- `RoutePlan`：目的、信号、分区及每来源范围；
- `CandidateManifest`：经过权限、状态、版本和预算门后保留的稳定候选引用；
- `ContextTrace`：打开/未打开分区、来源范围、权限决定、预算消耗、排序解释和拒绝原因。

Router 不负责 P06 Context Composer，不拼装最终 Thinking 输入，不进行 token 级裁剪，也不冻结 P06 的五层 Context Authority。现有 `ThinkingProvider.think(PerceptionResult, TokenBudget)` 外部兼容接口没有改变；Router 结果不会直接进入 Thinking。

## 2. Authority

- `SubjectState`：当前主体状态唯一权威。
- `Event/StateUpdateRecord`：客观历史事实权威。
- `Memory Store`：正式 Memory 及证据链权威。
- `Timeline`：Event 历史的只读派生投影。
- `DerivedSummary`：同一 Memory 仓储内可重建的有损视图。
- `Context Router`：只读选择与审计层，不是 Store、事实权威、状态权威或 Context Composer。

“小抽屉”只表示一次路由选择，不复制正文、不创建第二 Store、不保存权威事实。Router 没有创建 Event、StateMutation、Evolution、Memory、Summary 或推进 SubjectState revision 的接口。

## 3. 领域对象

`domain/context_routing.py` 定义：

- `ContextRoutingRequest`、`RoutingSignal`、`RetrievalBudget`；
- `ContextPartitionRequest`、`RoutePlan`；
- `ContextSourceCandidate`、`ContextSourceBatch`；
- `ContextCandidateReference`、`CandidateManifest`；
- `CandidateDecision`、`SourceTrace`、`PartitionTrace`、`ContextTrace`；
- `ContextRouteResult` 及 COMPLETE、INCOMPLETE、REJECTED、FEATURE_GATED 状态。

所有身份、时间、ratio、版本 hash、rank、预算计数和跨对象关联在构造及反序列化时验证。Trace 中的 routing signal 只保存 SHA-256，不保存原始秘密或完整敏感正文；Manifest 只保存稳定引用和评分解释，不保存候选正文。

## 4. 只读来源端口

`services/context_router_service.py` 提供宿主中立的 `ContextCandidateSource`、`ContextPermissionPolicy` 和 `ContextSourceBinding`。当前只读适配器为：

- `SubjectStateContextSource`：按精确 revision 读取 identity、relationship、continuity、temporal、intentions、emotion_state 分区；
- `MemoryContextSource`：读取 ACTIVE 且非 ARCHIVED 的 `ENGINE_PRIVATE` Memory；
- `DerivedSummaryContextSource`：只读取当前 ACTIVE Summary；
- `TimelineContextSource`：从 P03 Timeline 读取有效 Event 投影，排除已 corrected/revoked 的目标；
- 版本化本地 Fact source：只存在于 `continuity_engine.testing`，用于 P05 TEST/RESEARCH Fixture。

来源只能返回事先声明分区内、subject/environment 一致的候选。Router 不会在来源失败时扩大范围、回退全库或读取另一路径。

Route Plan 在调用来源前先按结构化 purpose/signals 选择分区。SubjectState 等固定必需来源由明确 `required_partitions` 规则加入，而不是以“读取全部来源”间接获得。当前 purpose 规则为：

| Purpose | 可打开分区 |
|---|---|
| `memory` | MEMORY、DERIVED_SUMMARY |
| `temporal` | TIMELINE |
| `fact` | TIMELINE、LOCAL_FACT |
| `relationship` | SUBJECT_STATE、MEMORY、DERIVED_SUMMARY、TIMELINE、LOCAL_FACT |
| `continuity`/neutral | 只打开显式 required partitions；其余来源不读取 |

未选择分区的 RoutePlan 与 PartitionTrace 均为 `NOT_OPENED/PURPOSE_NOT_SELECTED`；该分区下的 SourceTrace 为 `NOT_OPENED/PARTITION_NOT_SELECTED`，`requested_limit=0`，adapter `retrieve()` 调用次数为零。未选来源即使自报 relevance=1.0，也没有机会反向迫使 Router 打开分区。

## 5. 权限、预算与确定性

默认权限策略只允许同一 subject、同一 environment、`ENGINE_PRIVATE` 候选。权限未知、跨主体/环境、不可见、缺失、撤销、失效、被替代或版本/revision/hash 漂移均 fail closed，并在 Trace 中记录稳定原因码。

Retrieval Budget 与 Storage Budget、未来 P06 Context Budget 分离：

- 单轮候选默认 50；
- 可配置范围 30—80；
- 每来源有独立上限；
- `context_budget_hint` 只是未来提示，不执行 P06 token 裁剪。

总预算在任何 adapter 调用前按已打开分区和 source ID 稳定排序后确定性分配。分配采用逐轮配额且受每来源上限约束，所有 `requested_limit` 之和始终不超过 `total_candidate_limit`；来源 over-return 立即失败关闭。Memory/DerivedSummary 的 subject/environment/status/visibility/temperature、查询词、排序和 limit 在 `MemoryRepository.query_*` 边界生效，不先调用 `list_*` 全量加载。Timeline 从完整只读 Event 投影中按相关性和新近性选出有界窗口，初读和 revalidate 复用同一 query/window 推导，避免固定 100 条重验窗口产生自发 `SOURCE_STALE`。

排序结合 purpose/词项匹配、来源 relevance、recency、importance、activation；同分时使用 partition、source ID、stable ID、version、version hash 确定性打破平局。相同输入、状态、配置、时钟和来源版本产生相同 RoutePlan、Manifest、Trace 与 canonical hash。

## 6. 取用前重验与失败关闭

来源在初次 query 后、候选保留前必须再次验证稳定 identity、version、version hash、subject、environment、visibility 和状态。Trace 分别记录 requested、retrieved、evaluated、retained 与 rejected；retrieved 是来源实际返回量，不得用最终 Manifest 数量代替。必需来源失败使结果为 INCOMPLETE 或 REJECTED，并将 Manifest 清空，使其他来源候选不可消费；可选来源失败只排除该来源并记录原因，不会伪造“完整上下文”。Feature Gate 关闭时返回明确 FEATURE_GATED 空结果且来源读取次数为零。

## 7. 阶段隔离与未来开放

P05 只使用 Engine 本地、版本化 synthetic TEST/RESEARCH Fixture；不访问 Vio、网络、真实 Provider、API Key、MCP、外部数据库、向量服务或正式 `.continuity-data`。P05 Vio dependency = `NONE`。

该隔离只属于 P05 施工和测试，不是长期产品禁令。P06 将负责 Context Composer 与最终 Authority 分层；P16 才处理外部记忆、知识、MCP 和 Skill；P22 才首次正式重连真实 Provider 与 Vio/PWA World Adapter。

P05 验收不改变这一开放顺序，也不自动授权 P06。Memory 未来仍可按 P06/P16/P22 的正式边界参与 Thinking、Context、外部知识和 Provider/Vio 集成；本阶段本地隔离不得被解释为长期产品禁令。

## 8. 实现索引

- `src/continuity_engine/domain/context_routing.py`
- `src/continuity_engine/services/context_router_service.py`
- `src/continuity_engine/testing/p05_context_fixture.py`
- `tests/test_p05_context_routing.py`
- `tests/test_p05_context_router.py`
- [32_P05_规划施工测试验收矩阵.md](32_P05_规划施工测试验收矩阵.md)
- [33_P05_权限检索预算来源失效与ContextTrace语义.md](33_P05_权限检索预算来源失效与ContextTrace语义.md)
- [34_P05_测试索引与验收入口.md](34_P05_测试索引与验收入口.md)

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
