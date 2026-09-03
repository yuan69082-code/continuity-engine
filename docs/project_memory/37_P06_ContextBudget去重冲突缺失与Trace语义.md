# P06 Context Budget、去重、冲突、缺失与 Trace 语义

> 当前状态：用户于 2026-09-03 正式验收 P06，本文件约束 P06 当前为 `ACCEPTED`；P07 已由用户于 2026-09-04 正式验收，P07 Vio dependency = `NONE`，P08—P23 = `NOT_STARTED`。

## Context Budget

- Storage Budget、P05 Retrieval Budget、P06 Context Budget、Thinking/Provider TokenBudget 彼此独立。
- 核心片段默认 10，可配置 6—15；token cap 默认 2048，也可消费 P05 `context_budget_hint`。
- cost 由可替换确定性 estimator 计算；先验证、去重，再裁剪。
- confirmed_state 的 identity、continuity 和当前 relationship 属于受保护材料。
- 若预算不足以容纳必需受保护材料，返回 `INSUFFICIENT_CONTEXT_BUDGET`，不生成可消费 Snapshot。
- 未进入本轮 Context 只表示被裁剪，不表示底层忘记、删除或失效。

## 去重和冲突

精确重复由 source、stable ID、version/revision 与 content hash 共同确定，只保留一个 fragment，同时保留稳定 provenance。跨 Authority 不因文字相似而合并；DerivedSummary 与 raw source 即使正文相似也保持不同证据角色。raw source 与 confirmed_state/confirmed_memory 不一致时双方均保留，P06 不判断谁正确，不推进 Evolution；P07 才负责矛盾检测。

## 缺失与失败原因

Router 未打开、来源无候选、材料失效、权限拒绝、版本/hash 漂移、预算裁剪和内容缺失使用不同稳定原因码。精确解析至少区分 `SOURCE_MISSING`、`SOURCE_SUBJECT_MISMATCH`、`SOURCE_ENVIRONMENT_MISMATCH`、`SOURCE_STATUS_INELIGIBLE`、`SOURCE_VISIBILITY_DENIED`、`SOURCE_VERSION_DRIFT`、`SOURCE_HASH_DRIFT`、`MATERIAL_CONTENT_MISSING`、`MATERIAL_PROVENANCE_INVALID`。必需材料解析失败时结果不可消费；可选材料可以排除，但 Trace 必须保留原始具体原因，不能改写成通用 required/optional 失败。Feature Gate 关闭时 resolver 读取次数为零。

## CompositionTrace

Trace 记录 request/route/plan/manifest 身份与 hash、subject/environment、预算、resolver 总读取次数及按 source ID 的稳定分解、resolved/candidate-missing/deduplicated/retained/dropped 数量、每个引用的可信 Authority 与决定原因。`missing_count` 只统计 Manifest candidate 的解析缺失，`upstream_notice_count` 只统计 P05 分区 notice，完整性公式固定为 `resolved_count + missing_count == candidate_count`；upstream notice 不参与候选覆盖。读取审计和两组计数都进入 canonical serialization/hash/roundtrip/tamper 校验。Trace 不保存完整材料正文、secret、Authorization、凭据或 Provider hidden Chain-of-Thought，也不能反向成为 Router、Thinking、Evolution、Memory 或 SubjectState 的输入。

## Authority 与写入禁令

所有 fragment 固定 `direct_state_write_allowed=false`。Composer 没有 Event、StateMutation、Evolution、Memory、Summary、Timeline、SubjectState 或 revision 写入口；候选的 authority 标签和正文都不能改变此规则。
