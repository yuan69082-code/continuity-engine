# P04 Memory Consolidation 与 DerivedSummary 架构边界

> P10 现行门：P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。 D-056 与最终依据见 [最终复核及验收记录](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md#p10-accepted)。Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`；Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`；[CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 为 794/794 PASS、0 SKIP、0 FAIL。历史 FAIL、SKIP、旧 CI failure、辅助错误及 P09 segment 10 stderr 缺失/根因 UNKNOWN 原样保留。
> 下文保留该阶段施工及验收时的范围、后续未授权状态与测试历史；P09 的本轮新增授权和接线以本页现行门及 47—50 号档案为准，不倒写既往决定。

> 阶段：P04——Memory Consolidation 与 DerivedSummary
> 当前状态：P04 / P04 Engine side = `ACCEPTED`（用户于 2026-09-01 正式验收）
> Vio dependency：`NONE`
> P05、P06：后续独立获权并正式 `ACCEPTED`；P07：`ACCEPTED`；P09—P23：`NOT_STARTED`
> 软件版本：`0.1.0`

## 1. 权威边界

- `SubjectState` 是当前主体状态唯一权威。
- `Event/StateUpdateRecord` 是已经进入 Engine 的客观历史事实权威。
- P04 `Memory Store` 是正式 Memory 记录、版本和证据链权威，但不能覆盖 Event 或 SubjectState。
- `Timeline` 仍是 Event 历史的只读派生投影。
- `DerivedSummary` 只是在同一 Memory 仓储边界内保存的可重建、有损压缩视图；它不是 Event、Raw Source、Confirmed Memory、Self-Narrative 或第二个事实库。

Consolidation、Summary 生成、检索、温度迁移和来源传播均没有 Event/StateMutation/SubjectState 写权限。P04 专项测试直接验证上述操作前后 SubjectState revision 为 0 且 Event/StateUpdateRecord 历史为空。

## 2. 正式 Memory 模型

`MemoryRecord` 包含：

- stable `memory_id`、`subject_id`、`environment`；
- `episodic / semantic / relational` Memory kind；
- `experiential / analytical / external` evidence type；
- content、唯一根证据、Event/Memory/Message 来源引用；
- occurred/observed/recorded/consolidated UTC 时间及 time range；
- confidence、importance、activation、relation relevance、emotional weight；
- scope、tags、HOT/WARM/COLD/ARCHIVED、`ENGINE_PRIVATE`；
- status、revision/version、consolidation identity/hash 和追加式 lineage event。

`episodic` 只属于 Memory kind，不属于正式 evidence type。当前既有 Memory API 没有旧 evidence type 输入，因此不存在需要长期双轨保留的旧字段；非法 `evidence_type=episodic` 直接失败关闭。

## 3. 单一持久化权威

`JsonMemoryRepository` 在一个按 subject/environment 隔离、带格式版本与文档完整性 hash 的原子 JSON 文档中保存：

- `memory_records`：每个 Memory 的追加式、连续 revision 历史；
- `derived_summaries`：每个摘要的连续版本与有效/失效/被替代状态；
- `consolidation_operations`：`consolidation_id → canonical input hash/body → result memory_id/revision/canonical hash` 的 durable 幂等证据，重复根 alias 同样登记；它和 Memory 记录共用原子文档，不是第二账本或第二 Authority。
- `lineage_records`：correction/revocation/deletion 传播事实。

Summary 没有独立仓储。每次加载都重新验证格式、document hash、subject/environment、稳定 identity、连续 revision/version、来源先后、唯一根证据追溯、consolidation operation 的 canonical input/result、lineage 来源 Event 根与先后、摘要来源和当前有效性。相同 identity/version 与相同 canonical body 是精确幂等；不同 body 是 identity conflict。写入采用同目录临时文件、flush/fsync 和 `os.replace` 原子替换；替换失败时原文档保持可读。

## 4. Consolidation 与根证据去重

- 相同 consolidation identity 与相同 canonical 输入返回原结果；即使请求因重复根映射到既有 Memory，也在同一原子文档登记 operation identity，跨重启不丢失 alias。
- operation 精确绑定首次结果 revision/hash；重放从同一 append-only Memory history 取该版本，后续 reinforcement、terminal propagation 或重启均不能使旧 operation 漂移到 latest。
- alias candidate 在映射既有结果前后都必须用自身 source Event/Message/Memory 验证根证据；missing、forward、cross-subject/environment 或无关根在保存和加载时失败关闭，不能借用 result Memory 的来源链补齐 candidate。
- 相同 identity 与不同输入失败关闭。
- 相同 root evidence 经另一个 Memory identity 或重放到达，不增加 evidence count 或 activation reinforcement。
- 只有新的独立 root evidence 可以形成一次 reinforcement。
- 同 kind/evidence/scope 且内容一致的独立证据可以合并为新 Memory revision。
- P07 尚未施工，冲突内容不得静默覆盖或裁决；当前以显式 `MemoryEvidenceConflictError` 失败关闭。

上述“P07 尚未施工”保留为 P04 当时的阶段边界；P07 后续已独立施工并由用户于 2026-09-04 正式验收（D-050），并不改变 P04 的失败关闭规则或自动接入生产链路。

Learning 继续使用既有候选、确认和 Evolution 门，但 `LearningEvent/LearningRecord` 现在保存底层 `root_evidence_ids`。Repository retriever 生成的 root/source/kind/evidence/visibility/status/temperature/version provenance 在 influence 记录前被密封，调用方 metadata 不能覆盖或删除。验证按密封后的根证据集合去重，不再把两个 Memory ID 或重建后的摘要当成两份独立经验；DerivedSummary 没有独立 Learning source 类型。

## 5. DerivedSummary

摘要保留可扩展且经过校验的 `summary_type`，以及 summary identity/type/scope/time range/generated time/version、Event/Memory/合法 Message 来源、root evidence、confidence、content、canonical hash 方法和 ACTIVE/INVALIDATED/SUPERSEDED 状态。

P04 仅提供确定性本地生成器。精确重放同时比较 summary identity/type/scope、source memory/event/message、root evidence、time range、confidence 和生成正文；type/scope 稳定身份冲突失败关闭，合法来源或派生结果变化时旧 ACTIVE 版本先被追加为 SUPERSEDED，随后产生新 ACTIVE 版本。correction/revocation/deletion 会在与 Memory 墓碑同一次原子写入中把依赖摘要追加为 INVALIDATED；重新生成只读取当前 ACTIVE Memory。`trace_summary()` 按需打开来源，不要求每次检索复制全部原文。

## 6. 生命周期和未来接入

活跃度评分显式组合 importance、recent access、relation relevance、emotional weight、unique reinforcement 与 time decay，并保存解释项。HOT 300、WARM 3000、COLD 30000 只是 `MemoryActivationConfig` 的可替换默认值；容量超出时显式 maintenance 调用只降温，不物理删除。P04 没有自动过期、后台线程或 P11 Scheduler。

`RepositoryMemoryRetriever` 是对既有 `MemoryRetriever` 的只读兼容适配器；普通检索只返回 HOT/WARM/COLD，不返回 ARCHIVED。ARCHIVED 仍可经显式 repository load、维护、审计和授权 trace 读取，不等于删除、失效或事实为假。Feature Gate 关闭时返回空集合，检索全程无隐式写入。P04 的无 Vio/网络/Provider 隔离只属于本阶段施工与测试：P05 Context Router、P06 Composer、P16 外部长记忆/MCP/Skill 和 P22 Provider/Vio/PWA 重连仍按冻结顺序开放。

lineage 的 `root_evidence_ids` 必须至少包含由 `source_event_id` 稳定映射的 Event 根；其他根只能来自目标 Memory、合法 replacement Memory 或它们已经持有的可追溯来源链。缺失/无关根、跨 subject/environment、缺失或前向 replacement、重算 document hash 后的结构篡改在保存和每次加载时都失败关闭。该校验不读取 Event Store，也不改变 Event Authority。

## 7. 核心文件

- `src/continuity_engine/domain/memory.py`
- `src/continuity_engine/services/memory_consolidation_service.py`
- `src/continuity_engine/services/memory_service.py`
- `src/continuity_engine/storage/json_memory_repository.py`
- `src/continuity_engine/domain/learning.py`
- `src/continuity_engine/services/learning_service.py`
- `src/continuity_engine/testing/p04_memory_fixture.py`
- `tests/test_p04_memory_repository.py`
- `tests/test_p04_memory_consolidation.py`

## 8. 阶段外边界

P04 不实现 P05 Router、P06 Composer、P07 Contradiction Detector、P10 Assistant、P11 Scheduler、P12 Intentional Forgetting、P16 外部记忆/MCP/Skill、P20/P21 正式删除/恢复或 P22 Provider/Vio/PWA 重连。P04 Vio dependency = `NONE`；网络、真实 Provider、API Key、真实费用和正式 `.continuity-data` 均未访问或修改。

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
