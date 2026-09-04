# P06 Context Budget、去重、冲突、缺失与 Trace 语义

> P10 现行门：P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。 D-056 与最终依据见 [最终复核及验收记录](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md#p10-accepted)。Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`；Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`；[CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 为 794/794 PASS、0 SKIP、0 FAIL。历史 FAIL、SKIP、旧 CI failure、辅助错误及 P09 segment 10 stderr 缺失/根因 UNKNOWN 原样保留。
> 下文保留该阶段施工及验收时的范围、后续未授权状态与测试历史；P09 的本轮新增授权和接线以本页现行门及 47—50 号档案为准，不倒写既往决定。

> 当前状态：用户于 2026-09-03 正式验收 P06，本文件约束 P06 当前为 `ACCEPTED`；P07 已由用户于 2026-09-04 正式验收，P07 Vio dependency = `NONE`，P09—P23 = `NOT_STARTED`。

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

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
