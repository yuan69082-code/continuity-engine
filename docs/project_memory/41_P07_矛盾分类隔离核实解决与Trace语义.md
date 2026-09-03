# P07 矛盾分类、隔离、核实、解决与 Trace 语义

> 用户于 2026-09-04 正式验收 P07（D-050）；P07、Engine side 与 P07-01—P07-12 均为 `ACCEPTED`。本文既有 Authority 与两轮返修语义保持不变；P08—P23 `NOT_STARTED`，本次不授权 Git 写操作。

## 1. 三类矛盾

- `EPISTEMIC`：同一 proposition/scope 下的认识或知识判断不兼容，且不属于更具体的证据/认知冲突。
- `EVIDENTIAL`：analytical 与 external 等证据类型、来源或证明关系直接冲突。
- `COGNITIVE`：confirmed state/memory 等既有认知与 raw/retrieved 的新结构化证据不一致，需要后续合法链重新评估。

分类只描述冲突性质，不表示 winner、真值裁决或 StateMutation。相同 claim、语义一致、不同 proposition/scope/subject/environment 及明确同源版本 supersession 不形成 case。

## 2. Psychological Conflict 排除

LOVE/HATE、靠近/逃离、舍不得/想离开、信任/怀疑可以同时存在。可信 adapter 若把材料标记为 `ClaimDomain.PSYCHOLOGICAL`，P07 只记 `NOT_APPLICABLE/PSYCHOLOGICAL_CONFLICT_OUT_OF_SCOPE`，不比较强度、不选 winner、不删除较弱心理状态。P14/P15 才负责动态心理冲突与人格关系演化。

## 3. Disposition 与待核实

矛盾 claim 按既有 Authority 角色显式标为：

- `RETAINED_DISPUTED`：既有 confirmed state/memory 暂时保留使用，但明确处于争议；
- `ISOLATED`：DerivedSummary/retrieved candidate 不进入无争议消费；
- `CONTESTED`：raw source 等证据保留且待核实；
- `DOWNGRADED`：保留给明确降级策略，不能等价于删除或判假。

每个 case 都生成绑定全部 claim ID 的 `VerificationTask`，列出合法解决条件。Authority、confidence、recency 只参与描述，不能单独解决 case。

## 4. 合法解决与审计

公共 `ResolutionEvidence` 只是待验证请求；其 `verified` 布尔值没有 Authority。`ResolutionEvidenceVerifier` 必须从可信 binding 核对稳定 resolution ID、同 subject/environment、合法 basis、真实 basis reference、reference version、exact source hashes、provenance roots、reason、UTC 时间与允许动作，再密封成带 verifier/request/verification hash 的 `VerifiedResolutionEvidence`。支持的 basis 为用户更正、来源版本 supersession、独立佐证、合法 Evolution 记录或错误来源证明，各自使用稳定且不同的 reason/action 语义。

解决追加 `RESOLVED` audit 和新 case revision，不改写初始 claims/dispositions/source snapshot。新独立冲突证据只有经 verifier 密封且此前审计未覆盖时才能 `REOPENED`；可信来源 supersession 可追加 `SUPERSEDED`。`reopen()`/`supersede()` 不接受裸 hash。非法前向、跨边界、缺失/伪造/漂移证据、错误 basis、重复旧证据 reopen 或 audit prefix 改写均失败关闭。

Claim 的 canonical value 仅在本次检测内用于生成密封 SHA-256；case、Trace、audit 和 repository 不保存原值。supersession 请求本身也不可信：只有可信 source-version binding 证明同 subject/environment/source/stable source 的严格新版本替代旧版本才可消除误报；旧版本前向声明、互相/循环、同版本、跨来源、跨边界或缺失 target 均拒绝。

2026-09-04 第二轮返修补充：证据必须先在可信记录中明确适用 proposition/scope、目标来源及其版本/hash/provenance/claim 语义。存在且已验证的证据不代表适用于任意 case。输出证明进一步绑定 target case identity、原 revision/hash、snapshot、detector、claim 集合和单一允许动作；不允许把 RESOLVED 证明用于 REOPENED/SUPERSEDED，也不允许跨 case、快照或后续 revision 重用。audit reason、source hashes、UTC 时间必须与证明逐项相等，且不能早于前序审计。仓储加载以原历史 revision 重新验证证据适用性和 exact proof，而不是以最新 case 或自洽 hash 代替验真。

## 5. Trace 与计数

`ContradictionTrace` 记录 request/subject/environment/revision、P06 snapshot hash、detector version、固定检测时间、fragment/evaluated/unassessed/psychological excluded/case 数量，以及每个 fragment 的稳定 evaluation 和 case ID。

P06 Manifest candidate missing 与 P05 upstream notice 分开继承：

- `candidate_missing_count` 只等于 P06 candidate 解析缺失；
- `upstream_notice_count` 只等于 P06/P05 上游分区 notice；
- 二者都不冒充 P07 的 unassessed structured claim。

Trace 不保存 fragment content、secret、Authorization、credential、Provider hidden Chain-of-Thought 或可复用认证材料。它不反向成为 Router、Composer、Thinking、Evolution、Memory 或 SubjectState 输入。

## 6. 安全与阶段边界

P07 Fixture 和仓储只使用临时 TEST/RESEARCH 根；没有 socket、HTTP client、网络、Vio、Provider、API Key、MCP 或外部数据库依赖。P07 不进入 P08/P09/P10，也不修改六份冻结 Schema、`pyproject.toml`、软件版本或正式 `.continuity-data`。
