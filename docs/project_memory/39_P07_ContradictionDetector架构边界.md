# P07 Contradiction Detector 架构边界

> P10 现行门：P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。 D-056 与最终依据见 [最终复核及验收记录](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md#p10-accepted)。Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`；Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`；[CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 为 794/794 PASS、0 SKIP、0 FAIL。历史 FAIL、SKIP、旧 CI failure、辅助错误及 P09 segment 10 stderr 缺失/根因 UNKNOWN 原样保留。
> 下文保留该阶段施工及验收时的范围、后续未授权状态与测试历史；P09 的本轮新增授权和接线以本页现行门及 47—50 号档案为准，不倒写既往决定。

## 当前状态

- P00—P07：`ACCEPTED`
- P07 / P07 Engine side：`ACCEPTED`
- P07-01—P07-12：12/12 `ACCEPTED`
- P07 Vio dependency：`NONE`
- P09—P23：`NOT_STARTED`
- D-049：已使用；D-050：用户于 2026-09-04 正式验收 P07，已创建并使用
- `PLANNING_CONFLICT = NONE`
- `EVIDENCE_CONFLICT = NONE`（第二轮两项阻断及当前三轮全量通过）

## 1. 唯一职责

P07 只消费 P06 已封印的完整、可消费 `ContextCompositionResult`，把其中五类 Authority 材料通过可信结构化 claim port 转成可审计 claim，检测同一 proposition/scope 内的 `EPISTEMIC`、`EVIDENTIAL`、`COGNITIVE` 不兼容，并产生非权威 case、disposition、verification task、可信 resolution/reopen/supersession audit 和安全 Trace。

P07 不重新路由、不重新检索、不读取 Manifest 外材料，不执行 P06 Composer，不写 SubjectState/Event/Evolution/Memory/DerivedSummary/Timeline/P06 snapshot/revision，也不建立 Contradiction Authority 或 Context Store。

## 2. 永久 Authority

| 组件 | 权威边界 |
|---|---|
| SubjectState | 当前主体状态唯一权威 |
| Event | 客观历史事实权威 |
| Evolution | 合法状态变化过程 |
| Memory Store | 正式 Memory 与证据链权威，不等于 Event |
| Timeline | Event 历史只读投影 |
| DerivedSummary | Memory 内部可重建有损视图 |
| P06 Snapshot | 本轮 Thinking-ready 材料封印，不是事实或状态权威 |
| P07 case/repository | 非权威、可重建、可验证的矛盾审计与索引 |

每个 P07 case/result 固定 `direct_state_write_allowed=false`、`evolution_commit_allowed=false`。未来合法认知更新仍必须经既定 Action Gate、Event/StateMutation、Evolution 和 SubjectState 权威链；P07 只生成 referral/proposal 形态的审计事实。

## 3. P06 输入封印

`ContradictionDetectorService` 先对 P06 result 做规范往返和 hash 校验，并要求：

- status 为 `COMPLETE`；
- snapshot 存在且 consumable；
- snapshot/trace request、subject、environment、revision、route result、route plan 和 manifest hash 一致；
- fragment 已保留 trusted Authority、source type、stable ID、version/revision、content hash、时间、provenance roots 和既有 marker。

失败结果没有可消费 P07 case；输入绑定或完整性错误在 claim resolver 读取前失败。P07 不调用 P05 Router、P06 resolver 或底层仓储。

## 4. 结构化 Claim

`ClaimProjection` 只允许可信 adapter 提供 proposition、瞬时 canonical value、polarity、evidence type、domain、scope 和 supersession 请求；它没有 Authority、subject、environment、source、version、hash 或 provenance 字段。检测边界立即把 canonical value 转为密封 SHA-256，`StructuredClaim`、case、audit 和 repository 只保存 `canonical_value_hash`，不保存原值。Authority 和来源安全字段全部由 Composer 已封印 fragment 密封；projection 的 supersession 请求还必须由 `ClaimSupersessionVerifier` 对同 subject/environment/source/stable source、严格新版本方向和时间方向验真。因此正文、自报标签、旧版本前向声明、confidence、recency 或 conflict marker 都不能提权、消除冲突或伪造证据链。

无法形成可信投影的材料为 `UNASSESSED/NO_TRUSTED_STRUCTURED_CLAIM`，不进行关键词猜测；Psychological claim 为 `NOT_APPLICABLE/PSYCHOLOGICAL_CONFLICT_OUT_OF_SCOPE`，LOVE/HATE 等 Ambivalence 不进入 P07 case。

## 5. 非权威持久化

`JsonContradictionRepository` 位于调用者提供的 Engine 本地 TEST/RESEARCH/授权根下，按 environment 和 subject 哈希隔离。当前 format v3 单一原子 JSON 文档保存 append-only case revisions，包含显式 `NON_AUTHORITATIVE_P07_AUDIT` 标识和 document hash；持久化 claim 只含密封 value hash、类型、稳定身份与来源引用。首轮返修的 v2 缺少目标封印，不静默升级，也不迁移正式数据。

加载时重新验证：

- document shape/hash/version/subject/environment；
- case/claim/trace canonical hash；
- revision 从 0 连续递增；
- claim、disposition、verification task 与来源 snapshot 不可改写；
- audit prefix 只能追加；
- lifecycle transition 与 verification 状态匹配；
- exact replay 返回原/当前同一 case，不重复写入；同 identity 不同 body 失败关闭。

生命周期写入必须经过 `ResolutionEvidenceVerifier`。公共 `ResolutionEvidence.verified` 只是无权自报字段，不构成验证结果；可信 verifier 必须按 basis 分别核对真实 reference identity、subject/environment、version/hash、provenance、reason 与允许动作，并生成 `VerifiedResolutionEvidence`。`reopen()` 和 `supersede()` 不再接受裸 `source_hashes`。

该仓储不复制完整材料正文，不读正式 Event/Memory/State，不是第二事实源或解决 Authority。

### 第二轮目标与审计封印

可信记录独立声明适用的 proposition/scope 和来源绑定，不从调用方 case 推导授权范围。TEST fixture 固定登记两个关系 Memory 来源的 source/version/content hash/provenance/claim 值 hash；天气等无关命题即使复用同一 P06 fragment 也不能获得关系更正证明。

验证结果密封 target case ID、原 revision/canonical hash、snapshot、detector version、全部 claim hashes、适用 claim hashes 和 allowed action。domain/from_dict 检查归属与审计 action/reason/source hashes/time、前序 case hash；service 检查返回证明；repository 追加及每次重启加载重新调用可信 verifier。缺 verifier、证据版本漂移、重算 hash 的证明篡改、跨 case/snapshot/revision/action 复用全部失败关闭。

## 6. 阶段边界

P07 不实现 P08 Planner、P09 正式集成、P10 Assistant 分支或 P14/P15 心理动力与人格演化。P07 的无 Vio/网络/Provider 隔离只属于本阶段施工与测试；P09/P16/P22 仍按规划开放正式链路、外部知识和真实 Provider/Vio/PWA 集成。

实现索引：

- `src/continuity_engine/domain/contradiction.py`
- `src/continuity_engine/services/contradiction_detector_service.py`
- `src/continuity_engine/storage/json_contradiction_repository.py`
- `src/continuity_engine/testing/p07_contradiction_fixture.py`
- `tests/test_p07_contradiction.py`
- `tests/test_p07_contradiction_detector.py`
- [40_P07_规划施工测试验收矩阵.md](40_P07_规划施工测试验收矩阵.md)
- [41_P07_矛盾分类隔离核实解决与Trace语义.md](41_P07_矛盾分类隔离核实解决与Trace语义.md)
- [42_P07_测试索引与验收入口.md](42_P07_测试索引与验收入口.md)

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
