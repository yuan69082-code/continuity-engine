# P06 Context Composer 与 Authority 架构边界

## 当前状态

- P00—P06：`ACCEPTED`
- P06 / P06 Engine side：`ACCEPTED`
- P06-01—P06-12：12/12 `ACCEPTED`
- P06 Vio dependency：`NONE`
- P07：`ACCEPTED`；D-049 已使用，D-050 已用于用户正式验收
- P08—P23：`NOT_STARTED`
- D-047：P06 开工、Authority 与预算边界
- D-048：用户于 2026-09-03 正式验收 P06

## 唯一职责

P06 只消费 P05 已选出的 RoutePlan、Candidate Manifest 与 Context Trace。它按既有引用精确解析材料，验证来源，执行精确去重、稳定排序和独立 Context Budget，输出 `ComposedContextSnapshot` 与 `CompositionTrace`。它不重新决定分区、不再次检索、不扩大来源、不建立 Context Store，也不写 SubjectState、Event、Memory、Summary、Timeline 或 revision。

## 五类可信 Authority

| Authority | 可信来源 | 语义边界 |
|---|---|---|
| `confirmed_state` | SubjectState 当前合法 revision | 当前主体状态权威；identity/continuity/relationship 可受保护 |
| `confirmed_memory` | P04 正式 Memory Record | 正式记忆及证据链，不等于客观 Event 事实 |
| `derived_summary` | P04 有效 DerivedSummary | 可重建、有损视图，永不自动升级 |
| `retrieved_candidate` | Engine 本地授权版本化候选 | 相关或重复命中不等于已确认 |
| `raw_source` | Event/Timeline 等可追溯原始证据 | 可反证旧结论，但 Composer 不裁决或覆盖 |

Authority 来自 Composer 配置的 `TrustedContextResolverBinding`，而不是候选自报标签。材料正文始终作为 data，不得成为系统指令、策略或提权入口。

## 精确解析与不可消费结果

Composer 只接受 `COMPLETE` Route Result，并验证 RoutePlan、Manifest、Trace 的规范 hash。Resolver 只能收到 Manifest 中既有 stable source ID，并校验 subject、environment、source、version/revision、content hash、visibility 与有效状态。Manifest 外材料不得读取。必需材料失败时结果不可消费且没有 Snapshot；可选材料排除时必须在 Trace 留下稳定原因。

验收阻断返修后，Composer 自己统计每次 exact resolver 读取，Trace 同时保存总数与按 source ID 的稳定计数；Feature Gate 关闭、非 COMPLETE Route 和未引用 source 均为零。State、Memory、DerivedSummary、Timeline 与 local/test resolver 不再把失败折叠为通用 stale/ineligible，而是稳定区分 `SOURCE_MISSING`、`SOURCE_SUBJECT_MISMATCH`、`SOURCE_ENVIRONMENT_MISMATCH`、`SOURCE_STATUS_INELIGIBLE`、`SOURCE_VISIBILITY_DENIED`、`SOURCE_VERSION_DRIFT`、`SOURCE_HASH_DRIFT`、`MATERIAL_CONTENT_MISSING` 与 `MATERIAL_PROVENANCE_INVALID`。required/optional 只控制结果是否可消费，不抹掉原因。

## 阶段边界

P06 输出 Thinking-ready 结构化快照，但不修改现有 `ThinkingProvider.think(PerceptionResult, TokenBudget)`，不接入 E5-A 或生产 Thinking。P07 才负责矛盾检测，P09 才负责 C1 正式运行链接线，P16/P22 才分别开放外部知识与真实 Provider/Vio/PWA。P06 的本地隔离不是长期产品禁令。
