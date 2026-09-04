# Changelog

第二轮返修历史补充：Windows 换行转换的 1 FAIL（0.329 秒）及早期样本保留；二进制保存已修正，第二轮定点修复与规定回归已完成，交回独立复核。历史 segment 10 根因未知。

本文件记录 continuity-engine 的版本级变化。格式参考 Keep a Changelog，但只记录可由当前代码、测试和本次档案工作确认的事实。仓库目前只有一个汇总式初始提交，早期变化无法可靠分配具体日期。

## [Unreleased]

### P09 用户正式验收（D-054）— 2026-09-04

- 用户已明确验收；P00—P09、P09 Engine side 和十二项均 ACCEPTED，Vio dependency NONE；P10—P23 NOT_STARTED。PLANNING_CONFLICT/EVIDENCE_CONFLICT 当前 NONE，仅表示现行阻断闭合。
- 监工本轮原两项 2/2（1.381 秒）、两轮矩阵 30/30（27.690 秒）、全量 770/770（484.753 秒）PASS；现场与其复核后 352 文件逐项 hash 一致，源码/测试无新增变化。
- 仅同步验收档案。原第二轮三轮后条目中的“终局尚未执行”属于当时快照；随后实际终局 70/70（347.630 秒）、770/770（479.431 秒）已在 50 保存，本次不覆盖该阶段记录。
- 历史 segment 10 stderr 缺失、根因 UNKNOWN 及全部失败保留。成果尚未提交，稳定 C1 SHA 待用户提交并 push 后核定；版本 0.1.0，无功能或 Git 写操作。
- 本次纯档案后全量 770/770 PASS、493.514 秒，单次运行；与监工结果分开记录于 [50 正式验收入口](50_P09_测试索引与C1运行入口.md#p09-accepted)。

### P09 第二轮：Evolution 缺失 checkpoint 与测试证据保留（历史阶段记录）— 2026-09-04

- 原两项新反例修改前正式实跑 2 FAIL/1.417 秒；保留缺口 1 FAIL/0.282 秒。独立监工原四反例闭合、16/756 的通过以及新两项失败均单列为历史，不冒充本轮运行。
- 完成状态事实核验由原 Action、稳定 operation/event、ThinkSession 和结果 projection 共同决定；nullable checkpoint 不再关闭事实查询。原记录缺失、身份/版本/授权来源/内容矛盾失败关闭，合法首次更新和已提交事实恢复保留，无新增 Authority 或账本。
- long harness 在失败/可捕获中断时，于 Fixture 清理前独立保存命令、阶段、退出码、stdout/stderr、时间和中断信息；流式写入避免丢失已写输出，无隐式重试，唯一目录不覆盖首次失败，必要脱敏且不复制状态数据。
- 新增矩阵 14/14 PASS（10.666 秒），原 16 项 16/16 PASS（14.465 秒）；P09 专项 70/70 PASS（332.715 秒），E5-A/P02 101/101 PASS（23.893 秒），P03—P08 253/253 PASS（43.846 秒）。连续三轮全量分别为 770/770 PASS（480.525 秒） / 770/770 PASS（479.072 秒） / 770/770 PASS（476.349 秒）。档案后专项及全量终局尚未执行，完成后另行追加实际输出。
- 历史 segment 10 stderr 缺失，根因仍未知，不以当前 PASS 推断过去。本轮 EVIDENCE_CONFLICT 按用户要求保持 PRESENT，P09 IMPLEMENTED_NOT_ACCEPTED；D-053 追加事实，D-054 未使用，P10—P23 未开始，无 Git 写操作。


### P09 C1 当前授权与历史绑定返修（第一轮历史）— 2026-09-04

- 独立监工发现四项反例归属两项阻断；本轮先正式复现 6 项 4 FAIL/2 PASS、3.336 秒，原 40/740 历史保留。D-053 追加定点授权，D-054 未使用，当前 EVIDENCE_CONFLICT=PRESENT。
- 首次状态提交经当前 Context 和原 Action gate；既有 Evolution 身份/内容核对后幂等恢复。C1 输入绑定跨原 journal、ThinkSession、Action 与 E5-A 核对，不能由单处字段降级跳过独立回执。
- 16 项定点扩展已通过，P09 专项 56/56、331.217 秒；加载提前拒绝的两个 helper ERROR、完成重放的一项 FAIL 和修复前后原始结果见 50。本轮兼容 101/253 和连续三轮 756 全量已通过（473.352 / 469.270 / 483.176 秒）；档案后最终专项 56/56（373.797 秒）、全量 756/756（512.954 秒）PASS；首次终局 ERROR 与辅助诊断 ERROR 原样保留，其子进程根因未确认，EVIDENCE_CONFLICT 继续 PRESENT 待独立复核。
- 不改变六份 Schema、外部契约、正式数据、规划、pyproject/0.1.0 或 Authority；不开后续阶段，不执行 Git 写操作，P09 继续 IMPLEMENTED_NOT_ACCEPTED。

### P09 C1 正常运行链集成（首版历史）— 2026-09-04

- 用户已提交并推送 P08，main/P08 开工 SHA 为 `fb8713ccb049ca082079cf820d06956be0954af9`；D-053 记录新增 P09 授权，D-052 原验收保留，D-054 未创建。P09 当前 IMPLEMENTED_NOT_ACCEPTED，P10—P23 NOT_STARTED，本轮无 Git 写操作。
- 在正常 LocalIntegrationApp/ContinuityInteractionService 中贯通 Event/Timeline、P04 Memory、Router、Composer、P07 和原 Thinking/Action Gate/P08。可消费 Context 保存于原 Perception/ThinkSession，确定性与模型输入共享；Direct/Planner 继续复用唯一 E5-A，不增加 Authority 或请求账本。
- 当前 Context/来源/精确引用许可在新 Thinking/行动前重验；已执行事实恢复保留 P08 独立可信回执语义。Feature Gate 关闭覆盖零访问和历史恢复；添加纯 elapsed-time 情绪衰减，持久化仍经既有合法 Evolution。
- 复用 P01 显式 C1 profile 完整覆盖新增持久化文件；提供可运行 golden/long 入口，30 逻辑日/30 轮、两个真实进程重启点。新增 40 项组合测试，保留开发失败、辅助错误及修复记录；实际各轮结果见 50 号索引与原始 log。
- 六份外部 Schema、pyproject/0.1.0、正式数据不变；`interfaces/local_integration_app.py` 仅增加内部组装参数，其余接口文件不变，外部机器路由/字段契约不改。幂等结论限定于本地 Fake 原子回执，未接 Vio、真实 Provider 或生产 Adapter。

- P09 终局实测：专项 40/40、251.136 秒；全量 740/740、389.729 秒。此前三轮全量分别 390.100/385.853/389.943 秒，历史基线与开发失败原文见 50；P09 IMPLEMENTED_NOT_ACCEPTED，交回独立复核。

### P08 用户正式验收档案接续收尾 — 2026-09-04

- 既有 D-052 已登记用户正式验收 P08、方案 A 内部有限泛化及两轮监工阻断返修；本次补齐十二项矩阵、验收索引、未完成/待确认清单、施工日志、修订记录与汇总档案，不重复创建决定。
- P00—P08、P08 Engine side 与十二项均 ACCEPTED，P08 Vio dependency NONE，P09—P23 NOT_STARTED，PLANNING_CONFLICT/EVIDENCE_CONFLICT 均 NONE；不扩大本地 Fake 幂等能力结论，不授权生产 Adapter、P09/P17 或 Git 操作。
- 保留开工 642、36/678、46/688、58/700 和全部失败/返修/历史状态；监工独立及引擎返修终局证据见 P08 测试索引第 10 节，本次档案后的顺序复跑结果单独在最终报告登记。
- 本轮只修改档案，运行代码、测试、六份 Schema、外部接口、pyproject、版本 0.1.0 和正式数据不变。旧任务 remote compact 断流属于上下文压缩/响应传输中断，不是项目测试失败。

### P08 无回执终态与过期停止决定返修 — 2026-09-04

- 原 46/688 通过外再发现两条监工反例：receipt=None 的 FAILED_TERMINAL 可通过协调器，重算 hash 的 EXPIRED 可掩盖 Fake 实际成功；先保留 2/2 FAIL、0.467 秒，当时 EVIDENCE_CONFLICT=PRESENT。
- 内部状态/证据约束贯穿构造、反序列化、attempt 保存和协调消费；成功/执行失败必须核实 receipt，EXPIRED 必须 query 明确类型化 NOT_EXECUTED。UNKNOWN/查询异常不是未执行；停止历史冲突拒绝消费、不覆盖；过期 choice/Context 仍可恢复原真实回执，但不授权新执行。
- 新增 12 项回归，定点 12、P08 58、旧 E5-A/P02 101、直接链路 329、综合 396 均通过；连续三轮全量 700/700（136.457/137.235/138.780 秒）。两条反例修复后 2/2 PASS、0.495 秒；补测 NameError 与修正也追加日志，原 36/678、46/688 和失败历史保留。
- 没有新增 ledger/存储版本或修改外部契约、Authority、Schema、pyproject/0.1.0、正式数据。P08/Engine/十二项 IMPLEMENTED_NOT_ACCEPTED，PLANNING_CONFLICT/EVIDENCE_CONFLICT 闭合为 NONE；D-052 未创建，等待独立复核，不执行 Git 写操作。

### P08 历史回执验真与 Context 失效恢复返修 — 2026-09-04

- 原 36/678 通过后，规划监工发现伪造 ledger 成功可放行 contact、当前 Context 失效阻断既有效果归账；先保留 2/2 正式失败（0.487 秒），当时 EVIDENCE_CONFLICT=PRESENT。
- 内部 coordination 对历史加载消费、终态重放、依赖与追加结果统一查询绑定 Adapter，缺失/UNKNOWN/漂移/不可验证回执失败关闭；自洽存储 hash 不等于独立执行证明。Context 失效时允许精确原请求事实查询/归账，仍禁止新请求、新执行、受控 retry 及后续动作越过当前门禁。
- 新增 10 项正式回归；定点 10、P08 46、旧 E5-A/P02 101、直接链路 317、综合 384 全部通过；三轮 Engine 688/688，130.617/131.293/134.722 秒。原 36/307/374/678、早期失败与本轮两处测试辅助代码错误均保留于日志，不倒写。
- P08 / Engine side / 十二项继续 IMPLEMENTED_NOT_ACCEPTED，两个 conflict 闭合为 NONE，D-052 未创建。未增加第二账本或变更持久化格式、模型通道、外部接口、Authority、正式数据、Schema、pyproject/0.1.0；不接 P09/P17/Vio/真实系统，不执行 Git 写操作。

### P08 Direct / Optional Planner 与 E5-A 内部有限泛化 — 2026-09-04

- 用户独立授权 P08，并明确选择 A：保留外部六份 Schema 与原 model.generate/ThinkSession 通道，仅增加内部 Action/Step 类型及同一 capability ledger 的恢复分派。D-051 已记录；D-052 未创建。
- 简单行动无需 Goal/Plan；复杂、多步、依赖或非原子选择必须走 Planner；Information Need / Action Intent 共用输入封印、Action 权限/风险/资源、确认、Recoverability 与 Reality Boundary 门。
- Fake receipt query 优先，UNKNOWN 不盲重试，旧模型等待/完成记录仍可加载、恢复和精确重放。新增 36 项测试，307 直接链路、374 综合与三轮 678/678 全量通过（116.450/116.219/117.417 秒）。
- 保留 Adapter 漂移和步骤间 Context 漂移两次 1/1 FAIL；分别通过绑定 Adapter/policy hash 和执行前 Context 重验闭合，没有删除或弱化断言。
- P08 / Engine side / P08-01—P08-12 = IMPLEMENTED_NOT_ACCEPTED，P00—P07 ACCEPTED，P09—P23 NOT_STARTED；PLANNING_CONFLICT = NONE，EVIDENCE_CONFLICT = NONE。没有生产 Adapter、Vio/网络/真实 Provider、正式数据或版本变更，不执行任何 Git 写操作。

### P07 用户正式验收 — 2026-09-04

- 用户正式验收 P07，D-050 已创建并使用；P00—P07、P07 Engine side 与 P07-01—P07-12 均为 `ACCEPTED`，P07 Vio dependency `NONE`，P08—P23 保持 `NOT_STARTED`。
- 规划监工独立确认第二轮两个反例被拒绝、合法生命周期及重启重放通过；P07 56/56、Engine 全量 642/642 PASS。初版、两轮阻断、失败回归、35/621、46/632、56/642 和当时的未验收状态按原样保留在以下历史条目。
- 本轮仅校准 Markdown 验收档案，不修改运行代码、测试、冻结契约、正式数据或软件版本 `0.1.0`；不授权 P08、Vio 或任何 Git 写操作。`PLANNING_CONFLICT = NONE`、`EVIDENCE_CONFLICT = NONE`。

### P07 第二轮 Resolution 审计与目标绑定返修 — 2026-09-04

- 原 46/632 通过后仍发现跨 subject/environment 的 RESOLVED 审计和无关命题使用关系更正证据两项阻断；正式回归先取得 2/2 失败（0.372 秒），当时 `EVIDENCE_CONFLICT = PRESENT`。
- 可信 evidence record 独立绑定适用 proposition/scope 与目标来源 version/hash/provenance/claim 语义；证明密封 case ID、原 revision/hash、snapshot、detector、claim 集合及 allowed action。audit 的 action/reason/source hashes/time 必须一致。
- P07 format v3 repository 在追加与每次恢复时重新调用可信 verifier，拒绝自洽 hash 篡改和跨目标证明复用；不迁移正式数据，不建立第二 Authority。
- 新增 10 项回归；当前 56/133/221/338 专项与链路通过，全量连续三轮 642/642（109.848、111.893、109.980 秒）。五类合法 basis、resolve/reopen/supersede、重启与 detect replay 保持通过。
- P07 仍 `IMPLEMENTED_NOT_ACCEPTED`，D-050 未创建；`PLANNING_CONFLICT = NONE`、`EVIDENCE_CONFLICT = NONE`。以下初版和首轮返修记录保留，不倒写。

### P07 Contradiction Detection and Evidential Isolation — 2026-09-03

- 新增 P06 COMPLETE Context 封印、可信结构化 claim、`EPISTEMIC`/`EVIDENTIAL`/`COGNITIVE` 三类检测，以及 Psychological Conflict 明确排除。
- 新增 contested/downgraded/isolated disposition、verification task、verified resolution、reopen/supersession 和 future Evolution referral；不按分数选择 winner，固定零状态写与零 Evolution commit。
- 新增非权威、append-only、canonical hash/原子替换的 contradiction repository，覆盖精确 replay、重启、篡改、非法 transition 和跨边界失败关闭。
- 新增版本化 Golden/fault fixture 与 35 项 P07 专项；当前 P05—P07 112/112、直接相关 200/200、P01—P07 综合 317/317、Engine 全量连续三轮 621/621。施工中一次引用四个不存在模块的无效入口作为命令错误保留，随后真实文件范围 200/200 通过。
- 规划监工在上述首轮证据后复现 fabricated resolution、跨主体 COMPLETE result、canonical secret 明文落盘和旧版本前向 supersession 四项阻断；四个反例先以 4/4 失败测试保存，当时 `EVIDENCE_CONFLICT = PRESENT`。
- 增加可信 `ResolutionEvidenceVerifier` 和 `ClaimSupersessionVerifier` 边界，Result 封印 case/trace subject/environment/snapshot/detector version，repository format v2 只保存 `canonical_value_hash`；`reopen()`/`supersede()` 不接受裸 hash。
- 返修后 P07 46/46、P05—P07 123/123、直接相关 211/211、P01—P07 328/328、全量连续三轮 632/632。系统崩溃只中断档案同步，恢复后监工独立 P07 46/46；首轮数字和失败历史不删除。
- 新增 D-049 和 P07 专责档案 `39`—`42`。P07、Engine side 与 P07-01—P07-12 当前为 `IMPLEMENTED_NOT_ACCEPTED`，P07 Vio dependency `NONE`；D-050 未创建，P08—P23 未开始。

### P06 Context Composer and Authority Layering — 2026-09-03

- 用户于 2026-09-03 正式验收 P06；P06、P06 Engine side 与 P06-01—P06-12 当前均为 `ACCEPTED`，D-048 记录该决定。P06 Vio dependency `NONE`，P07—P23 `NOT_STARTED`。
- 用户在 P05 `ACCEPTED` 后独立授权 P06；新增五类可信 Context Authority、规范序列化/hash、exact material resolvers、独立 Context Budget、Thinking-ready `ComposedContextSnapshot` 和无正文 `CompositionTrace`。
- Composer 只消费 P05 `COMPLETE` Route Result 的既有 Manifest 引用；逐项校验 subject/environment/source/version/revision/content hash/status/permission。Manifest 外读取、二次搜索、分区扩大和候选自报 Authority 提权均失败关闭。
- confirmed_state 的 identity/continuity/relationship 受保护；预算不足以容纳必需材料时返回 `INSUFFICIENT_CONTEXT_BUDGET`。Summary 与 raw source 不因文本相似合并，冲突材料并列保留且不提前实现 P07 裁决。
- 新增版本化 P06 Golden Fixture 和 test-only Thinking consumer；P06 不修改生产 ThinkingProvider/E5-A，不建立 Context Store，也不写 SubjectState、Event、Memory、Summary、Timeline 或 revision。P09 才完成正式运行链接线。
- 初版新增 P06 专项 33 项；P05+P06 72/72、直接相关链路 160/160、P01—P06 综合 277/277、Engine 全量连续三轮 581/581，作为施工历史保留。
- 规划监工验收阻断返修将 Manifest candidate missing 与 P05 upstream notice 真正独立计数，新增 Composer 自有 resolver 总读取/按 source 审计，并为 State/Memory/Summary/Timeline/local exact resolver 固定九类失败原因；当前为 10/10 阻断、38/38 专项、77/77、165/165、282/282 相关矩阵及连续三轮 586/586 全量通过。
- P06 实现和返修完成时保持 `IMPLEMENTED_NOT_ACCEPTED`；其后的用户正式验收状态见本节首项。P06 的本地隔离不是长期产品禁令，P09/P16/P22 仍按规划开放正式 Thinking 接线、外部知识及真实 Provider/Vio/PWA 集成，版本保持 `0.1.0`。

### P05 Context Router — 2026-09-02

- 用户于 2026-09-03 正式验收 P05；P05、P05 Engine side 与 P05-01—P05-12 当前均为 `ACCEPTED`，D-046 记录该决定。
- 用户在 P04 `ACCEPTED` 后独立授权 P05；新增只读、宿主中立 Context Router，基于结构化 Perception 生成确定性 RoutePlan、Candidate Manifest 与 Context Trace。
- 新增 SubjectState、Memory、DerivedSummary、Timeline/Event 和版本化本地 Fact 的有界只读 source adapters；同 subject/environment、ENGINE_PRIVATE、status、version/hash/revision 权限与取用前重验失败关闭。
- Retrieval Budget 默认 50、可配置 30—80，支持 per-source 上限，并与 Storage Budget、未来 P06 Context Budget 分离；来源失败不触发全库扫描或越权回退。
- 排序结合 purpose、relevance、recency、importance、activation 和稳定 identity/version tie-break；Trace 只保存 hash/引用/原因码，不保存秘密、凭据或完整候选正文。
- 规划监工复核后完成四项语义返修：purpose 先选择分区且未选来源零读取；总 Retrieval Budget 在 adapter 调用前分配；Memory/Summary 在仓储边界有界查询且 Timeline 使用可重验的近期相关稳定窗口；必需来源失败返回空 Manifest。Trace 分离 requested/retrieved/evaluated/retained/rejected。
- 新增版本化 P05 Golden Fixture；当前 P05 专项 39/39、相关链路 125/125、跨阶段综合矩阵 244/244，Engine 全量连续三轮 548/548。初版 35/122/240/544 作为历史结果保留。
- P05 Vio dependency `NONE`；P06—P23 `NOT_STARTED`。P05 验收不自动授权 P06；本地隔离也不是长期禁止 Memory 参与 Thinking/Context，P06/P16/P22 仍按既定阶段开放。未实现 P06 Composer、外部来源、Vio/网络/Provider 或任何 Store 写入，版本保持 `0.1.0`。

### P04 Memory Consolidation and DerivedSummary — 2026-08-30

- 用户于 2026-09-01 正式验收 P04；P04、P04 Engine side 与 P04-01—P04-12 当前均为 `ACCEPTED`，P04 Vio dependency `NONE`。D-044 固定 Authority、保留/删除、operation 精确重放、alias 自身来源链、Learning 根证据去重和未来开放边界；P05—P23 继续 `NOT_STARTED`。
- 用户在 P03 `ACCEPTED` 后独立授权 P04 Engine 施工；新增正式 Memory 模型、单一原子 JSON MemoryRepository、root evidence 去重、可解释 activation/温度和追加式 correction/revocation/deletion lineage。
- 新增 Memory 内部 `MemoryConsolidationService` 与宿主中立确定性 summary generator；DerivedSummary 与 Memory/lineage 共用同一仓储权威，可追溯、失效、替换和重建，但没有 Event/StateMutation/SubjectState 写权限。
- LearningEvent/Record 现保存 root evidence identity；同一底层证据经多个 Memory/Summary/重建路径不会重复增加验证或 reinforcement，真正独立来源仍可构成多证据验证。
- 默认可见性为 `ENGINE_PRIVATE`；P04 没有自动过期、物理删除、后台 Scheduler、永久删除入口、网络、Vio、Provider、MCP 或外部存储。HOT/WARM/COLD/ARCHIVED 容量为可配置默认值，显式 maintenance 只重算和降温。
- 新增版本化 P04 本地 Fixture 与 Golden Scenario，复用 P03 intention/fact、争执/和解时间线；所有验证只使用临时 TEST root，正式 `.continuity-data` 不变。
- 规划监工五项阻断返修：普通检索排除但不删除 ARCHIVED；正式 Memory provenance 在 influence 前密封；重复根 alias 的 consolidation operation identity 与 canonical input/result 在同一原子文档持久化；DerivedSummary 精确幂等覆盖 type/scope/source/root/time/confidence/content；lineage 根绑定来源 Event 并在保存/加载期拒绝无关、缺失、前向和篡改引用。
- 返修新增 7 项定点测试；当前 P04 专项 26/26、相关链路 129/129，Engine 全量连续三轮 504/504。首次施工 19/122/497 仍作为历史证据保留。
- 追加返修将 consolidation operation 绑定首次 result Memory revision/canonical hash，并对 alias candidate 自身 source chain 在保存和加载期独立验真；新增 5 项顶层测试后，当前 P04 专项 31/31、相关链路 134/134，Engine 全量连续三轮 509/509。此前 26/129/504 与更早历史保持不变。
- P04 实现和返修完成时保持 `IMPLEMENTED_NOT_ACCEPTED`；其后的用户正式验收状态见本节首项。P05—P23 仍为 `NOT_STARTED`，软件版本保持 `0.1.0`。

### P03 User Acceptance Closure — 2026-08-30

- 用户于 2026-08-30 正式验收 P03；P03、P03 Engine side 与 P03-01—P03-12 当前全部为 `ACCEPTED`，P03 Vio dependency 保持 `NONE`。
- Event 继续是客观历史事实权威，SubjectState 继续是当前主体状态权威，Timeline 继续是无写入权的只读派生投影；P03 验收不改变 Authority 或冻结契约。
- 开工 444、初版 22/469、两项语义返修 28/475、回退时钟恢复返修 31/478 及三项阻断失败历史全部保留。P04—P23 继续 `NOT_STARTED`，本次不授权 P04、P10、Vio 或 Git 操作。
- 本次只同步验收状态、D-042、矩阵、索引和工程档案；不修改运行代码、测试、Schema、`pyproject.toml`、正式数据或版本 `0.1.0`。

### P03 Event Time and Read-only Timeline — 2026-08-30

- 用户在 P02 `ACCEPTED` 后单独授权 P03 Engine 独立施工；P03 Vio dependency 为 `NONE`，P04—P23 保持 `NOT_STARTED`。
- 原位扩展 Event 为可验证分类、来源、证据、内部/来源/关联身份，以及 `occurredAt / observedAt / recordedAt` 三时间；旧单时间 JSON 以 `LEGACY_COALESCED` 向后兼容。
- exact duplicate Event 变为精确幂等重放，不重复 Event、mutation 或 revision；相同 eventId 的不同 canonical body 以身份冲突失败关闭。恢复路径返修后，既有 eventId/canonical identity 判定先于新 Event 时间门，跨重启、回退时钟及已有后续 revision 后的重放保持原历史 update 身份且不读取 applied clock。
- correction/revocation 只追加新 Event；缺失、跨 Subject、前向引用在持久化加载与 Timeline 重建时均失败关闭。监工返修后，FACT、OBSERVATION、INTENTION、CORRECTION、REVOCATION 无论是否迟到均不能携带 mutation；显式 recordedAt 必须不晚于单次读取的 appliedAt。
- 新增无写入权的 `TimelineProjection` / `TimelineService`，仅从 StateUpdateRecord/Event 历史重建，提供 UTC 确定性排序、时间窗口、first/last、distance、chain 和来源/分类/correlation 过滤。
- 新增版本化本地 P03 Fixture/adapter 与 Golden Scenario，区分 intention 和事实、固定争执/和解顺序，并由 SubjectState 权威表达当前关系；不访问 Vio、网络、真实 Provider 或凭据。
- 三项监工语义阻断已定点返修；当前恢复阻断矩阵 4/4、P03 专项 31/31、相关链路 174/174、Engine 全量连续三轮 478/478。施工和返修完成时均保持 `IMPLEMENTED_NOT_ACCEPTED`；其后的用户正式验收状态见上方 P03 User Acceptance Closure。

### P02 User Acceptance Closure — 2026-08-29

- 用户于 2026-08-29 正式验收 P02；P02、P02 Engine side 与 P02-01—P02-12 当前均为 `ACCEPTED`。
- P02 Vio dependency 保持 `NONE`；Real Provider/Vio/PWA production integration 继续 `DEFERRED_TO_P22`；P03—P23 继续 `NOT_STARTED`。
- 本次只同步验收状态、D-040、矩阵、索引和工程档案，不修改运行代码、测试、Schema、`pyproject.toml`、正式数据或版本 `0.1.0`，也不执行 Git 暂存、提交或推送。

### P02 Engine Host-Neutral Model Capability Loop — 2026-08-28

- 新增宿主中立 `ModelProvider` Port、显式 Provider/Model Profile policy、Engine 内确定性 Fake Provider，以及持久化 execution/usage/test-credit 测试账本。
- 以 Alibaba Cloud Model Studio / `qwen-flash-2025-07-28` 作为可替换 Fake Profile 元数据，固定单次 1024、每日 10240 synthetic Token、每次唯一成功 execution 记 1 test-credit、fallback 关闭；不代表真实供应商价格或调用。
- 复用 E5-A 唯一 `model.generate` durable pause/resume，覆盖 success、generation/network failure、timeout、UNKNOWN 查询优先、retryable/terminal、cancelled/expired、预算耗尽、响应丢失、多轮和崩溃恢复；不重复 execution、credit、Thinking、Action 或主体结果。
- 初次施工时 P02 专项 33/33、P01+E5-A+P02 相关链路 129/129、Engine 全量 430/430 通过；该组数字作为历史基线保留。
- 规划监工发现的 UNKNOWN/TIMEOUT 查询解析、部分每日预算调用前约束、usage/test-credit 加载期验真三项阻断已定点返修；当前定点矩阵 16/16、P02 专项 47/47、相关链路 143/143 通过。
- D-039 验收前置返修把 E4/E5 HTTP 所有“读取正文前拒绝 POST”统一为 response-first、flush、半关闭写端和有界固定缓冲丢弃未读输入；不改变认证优先级、路由、状态码、JSON、限制或外部契约。413/401 各连续 50/50、前置拒绝矩阵 20/20、E4 HTTP 340/340、E5 HTTP 140/140，Engine 全量连续三轮 444/444 通过。
- P02 与 Engine side 当前为 `IMPLEMENTED_NOT_ACCEPTED`；P02 Vio dependency `NONE`，真实 Provider/Vio/PWA production integration 后置 P22，P03—P23 未开始。
- 未修改六份冻结 Schema、生产 HTTP/API/Capability/Binding 外部契约、正式数据或版本 `0.1.0`；未访问网络、凭据或 Vio，未执行 Git 提交或推送。

### P01 User Acceptance Closure — 2026-08-27

- 用户于 2026-08-27 正式验收 P01；P01、P01 Engine side 与 P01-01—P01-12 当前均为 `ACCEPTED`。
- P01 Vio dependency 继续为 `NONE`，Vio/PWA production integration 继续后置到 P22；P02—P23 全部为 `NOT_STARTED`，P02 未授权。
- P01 仍只提供测试、实验和 Research Sandbox 的 Snapshot/Rollback，不构成正式 Subject、Owner Domain 或生产恢复；P20/P21 边界不变。
- 本次只同步验收状态和执行提交前核查，不升级 `0.1.0`，不修改运行代码、测试、Schema、正式契约、正式数据或 Vio，也不执行 Git 提交或推送。

### P01 Engine Independent Boundary Closure — 2026-08-27

- 按三份 2026-08-26 最新规划正文重新校准 P01：P01—P21 由 Engine 独立施工与验收，P01 Vio dependency = `NONE`；Vio/PWA production integration 后置到 P22。
- 三份附件按指定 python-docx/NFKC/空白折叠算法的 normalized body SHA-256 全部匹配，并通过 P01—P21 独立施工、P10 实际建仓及 P22 首次重连等语义锚点核对。
- 现有 P01 代码无需重写；四项旧缺陷定点回归、42 项 P01 专项、正式链路和完整回归继续作为 Engine 独立证据。P01 仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`，未升级软件版本、未修改冻结 Schema 或 Vio。

### P01 Engine Review Repair — 2026-08-26

- 保留首次 P01 施工及四项缺陷复现历史，完成标准 Engine 交互 `changed=true`、revision `1→2`、真实 Wake/Think/Action/operation/result 持久化与精确 rollback。
- Snapshot 扩展为 19/19 组件 closed-world inventory；增加 descriptor/registry 外部 anchor，未知/重复物理文件与重算内部 hash 的篡改均失败关闭。
- 增加 acceptance receipt 强制门、ACTIVE 创建即 24 小时 lease、正式整树 hash 与 repository root 隔离证明。
- P01 专项 42/42、相关正式链路回归 200/200、Engine 完整 397/397 通过。P01 仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`、Vio cooperation `NOT_STARTED`；未修改软件版本、冻结 Schema、正式契约或 Vio。

### P01 Engine Test Sandbox Infrastructure — 2026-08-25

- 新增独立 `continuity_engine.testing` TEST Sandbox：disposable Subject/Binding/cycle/namespace/root、Frozen Clock、synthetic Fixture、完整 Snapshot/Branch、原子 rollback、test-only Memory、证据导出、retention 和受保护清理。
- Snapshot 以 15 个逻辑组件的 canonical hash、物理文件 hash、revision/count 和 completeness 验证；缺失/篡改失败关闭，`changed=true` 回滚后逐项精确恢复。
- 固化 `promotionAllowed=false` / `PROMOTION_FORBIDDEN`，以及成功自动清理、失败 24 小时、debug 最长 7 天、无后台 Scheduler 和 link/junction/正式路径拒绝边界。
- 新增 29 项 P01 专项；当前完整本地回归为 384 项。P01 整体仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`，Vio cooperation `NOT_STARTED`；软件版本继续为 `0.1.0`。

### P00 User Acceptance Closure — 2026-08-25

- 规划监工窗口完成 P00 核查后，用户于 2026-08-25 正式验收 P00；P00 与 P00-01—P00-12 当前状态同步为 `ACCEPTED`。
- P01—P23 继续为 `NOT_STARTED`；P01 未获授权，仍须单独 Stage Brief 和用户明确授权，不得自动开始。
- 本次只收口工程档案与验收证据，不修改运行代码、契约、Schema 或软件版本，也不执行 Git 提交或推送。

### P00 Planning, Contract and Independent Upgrade Baseline — 2026-08-25

- 以确认同步版 v1.1/v6.7 建立 P00—P23 唯一施工底图，并新增 P00 阶段基线、施工测试验收矩阵、档案与测试索引、风险回滚与用户决策入口四份专责档案。
- 冻结 Engine/Vio 定位、Subject Authority、六份交互/Capability Schema、D-025 hash 证据、P10 分支语义、P01/P20/P21 恢复边界、唯一现实行动链和 Reality Boundary。
- 登记 Engine 与只读 Vio 的 Git、版本、测试、迁移及独立升级基线；历史连接能力保留，但不构成双方运行或施工依赖，生产 World Adapter 重连仍属于 P22。
- 本次仅修改工程档案，不改变软件版本或运行能力。该次施工完成时 P00 为 `IMPLEMENTED_NOT_ACCEPTED`，P01—P23 均为 `NOT_STARTED`，尚未获得进入 P01 的授权；其后验收状态见上方 P00 User Acceptance Closure 记录。

### S4-Live First Real Provider Acceptance Archive — 2026-08-14

- 正式记录 S4-Live 首次真实供应商单次试聊 `PASS`：在不可晋升的 `disposable_test / promotionAllowed=false` 身份和仓库外短路径可销毁沙箱中，经正式 V5/V1/V3/Engine E5-A/V4/V2 链路完成一次真实调用。
- Alibaba Cloud Model Studio OpenAI-compatible Provider 的 `qwen-flash-2025-07-28` 恰好执行一次并 succeeded，报告 input/output/total Token 为 177/9/186；唯一 CapabilityResult `SUCCEEDED` 首次回传 HTTP 200，result outbox 和 Conversation Turn completed，没有重复 execution/result/Message、incident 或 outcome_unknown。
- 最终主体表达只来自 Engine `FirstRoundSuccessResult.response.content`。Engine `changed=false`、revision `0→0`、`engineUpdateId=null`，没有 Event、StateMutation 或 StateUpdateRecord；该验收没有覆盖真实模型 `UPDATE_STATE`。
- API Key 未进入 Engine 或档案；Vio 费用账本为 `cost_status=not_reported`，不能把供应商界面当时约 0 解释为最终绝对零费用。三个服务端口已停止，沙箱已整根删除且未触及仓库或受保护路径。
- 保留供应商调用前的 Windows 路径预算事故历史；该次没有 CapabilityRequest、Provider execution、CapabilityResult 或费用，修复位于 Vio 启动前门禁/清理边界，没有修改 Engine。
- 本次只同步 Markdown，不提升 `0.1.0` 软件版本。通用 Provider、正式身份/Binding、日常使用、真实状态演化、生产认证、多租户、外网、部署及后续外部能力仍未完成。

### Engine S4-R Acceptance Archive Sync — 2026-08-13

- 正式记录 Engine E5-A、Vio V4、受控 S4 Capability 联验、Vio V5、F1、L1 已完成，Engine S4-R 独立追认结论为 `PASS`；当前双方基线为 Engine `cba52126db2fb5eca57d9b5c0c80884693c59a6f`、Vio `239759d1d219bd140f41257c5da18169fbf773a9`。
- 记录仓库外固定 Binding 的 Engine 独立 RFC 8785/SHA-256 复算通过、L1 只读安全准备、Capability 结果回流原 Thinking/Action、Action Gate 和跨重启幂等边界；Contract v1.1 与 SubjectState 权威未改变。
- 验收基线为 Engine E5 54/54、Engine 全量 355/355、Vio L1 24/24、Vio 后端 202/202、S4 shared 7/7、V5 shared 6/6、Vio 前端 19/19。
- 本次只同步工程档案，不提升 `0.1.0` 软件版本。真实供应商、真实模型调用、真实 API Key、真实费用和 S4-Live 均未发生；生产认证、多租户、公网、部署及后续外部能力仍未完成。

### Engine E5-A — Durable Capability Pause / Resume Core — 2026-08-10

- 新增独立 `continuity-capability/v1` CapabilityRequest、受约束模型输出和 CapabilityResult 领域模型，配套三份严格 Draft 2020-12 Schema、封闭 registry、RFC 8785/SHA-256 hash 和身份/关联验证；不修改 v1.1。
- ThinkSession 新增 `WAITING_CAPABILITY`；capability 模式在 Perception 后持久化不可变请求并暂停，结果返回后经解释器恢复原 Thinking，再进入 Action Gate 与 ReplyComposer。外部结果不能携带 StateMutation，也不能直接修改 SubjectState。
- 新增 capability request/attempt durable ledger 与 operation journal format v3 checkpoint，兼容读取 E4 v1/v2；Action 完成后先持久化结构化 `ActionExecutionResult`，再进入 domain checkpoint。相同请求/结果精确幂等，冲突和损坏状态失败关闭，跨重启不重复 Thinking、Action 或最终结果。
- 同一 E4 服务新增 Engine 侧 capability result 提交/查询语义；默认 deterministic 模式、既有 v1.1 HTTP envelope、SubjectBinding、Action/Evolution 和 E4 recovery 行为保持不变。
- 完成 E5-A 定点复核修正：成功输出在落盘前执行去空白非空校验，CapabilityResult 时间不得早于已持久化请求创建时间，重复 `init` 可验证未使用、等待、retryable/unknown 与已完成 Capability 历史而不改写持久化事实；错误 `serve` 模式仍拒绝。
- 新增 54 项 E5-A 测试，Engine 全量 355 项通过。该里程碑只完成 Engine 核心；Vio V4、真实模型、现实权限/安全确认、供应商调用、真实 usage 和双方共享验收尚未实现，软件版本继续为 `0.1.0`。

### Vio × Engine Formal Local HTTP/JSON Shared Acceptance — 2026-08-09

- 以 Continuity Engine `189441f9bad2a34119b4ef10365a4385ed0949cc` 和 Vio `35780da56c72b822fc018702dfe5e90674ab0fcb` 为正式基线，记录第一阶段本地回环 HTTP/JSON 双方验收通过。
- Vio 的真实持久化请求经正式 V3 transport 进入独立 Engine E4；completed、not_found、recovery_required、POST 响应丢失，以及 Engine/Vio 分别或同时重启均通过。
- S2+S3 15/15、Vio V1+RFC 8785+V2+V3 64/64、Vio 后端全量 113/113、Engine crash-recovery 15/15、E4 67/67、全量 301/301；request/operation 身份、Wake、Thinking、Event、StateUpdateRecord、revision、投影和双方账本未重复。
- 保留首次 S3 在 Engine `c5ebbf9b7583f3fb50198a3bf37ea0553edc131f` 上发现恢复缺陷的历史；D-032 修复后的原失败场景和全部 S3 已通过。
- 本里程碑不提升 `0.1.0` 软件版本，也不表示外网连接、生产部署、真实模型/Capability/MCP/Tool/设备、Vio 公共对话 API 或前端真实链路已经完成。下一阶段尚未开始。

### Engine E4 Durable Domain Crash Recovery — 2026-08-09

- 为 operation journal 增加 domain 子阶段稳定恢复身份与 Wake/Perception/Thinking checkpoint；兼容读取旧 format v1，并以 format v2 保存 durable progress。
- WakeSession 保存结构化 WakeContext 恢复快照，ThinkSession 保存结构化 PerceptionResult 恢复快照；已完成 Wake/Thinking 必须复用，running/failed、多个候选或矛盾状态失败关闭。
- 支持恢复旧 E4 `reserved/domain=null` 但完成 WakeSession/ThinkSession 已落盘的部分状态；继续保证 Action 身份稳定、Evolution 单次提交、completed result 精确重放，以及 Event、StateUpdateRecord 和 revision 不重复。
- 新增 15 项 crash-recovery 回归；E4 相关 82 项、Engine 全量 301 项通过。Vio V3 已开始正式本地 HTTP 验收，但 S3 尚未通过；当前等待在新 Engine SHA 上重跑。
- 本修复不改变外部 HTTP envelope、v1.1、Schema/hash、SubjectBinding、Vio、生产架构或 `0.1.0` 软件版本。

### Engine E4 HTTP/1.1 Transport Boundary Hardening — 2026-08-08

- 第一阶段正式本地服务统一为一请求一连接；success、机器 envelope、查询、health 和全部传输错误均发送 `Connection: close` 并停止复用当前连接，未消费的请求体不再污染下一请求。
- 每条连接新增默认 10 秒、正有限且可验证的读取超时；部分 body 超时后关闭当前连接，串行服务可继续接受健康检查和正式请求。
- 未知 HTTP method 与可安全响应的解析错误改用固定最小 JSON，普通客户端提前断连不再向 stderr 输出 Python traceback 或内部信息。
- 新增 6 项配置及原始 socket 回归；E4 专项由 61 项增至 67 项，Engine 完整测试由 280 项增至 286 项。
- 本修正不改变 `ContinuityInteractionService`、v1.1、Schema/hash、SubjectBinding、幂等/revision/checkpoint、Runner、Vio 或 `0.1.0` 软件版本；Vio V3 与双方 HTTP 共享验收尚未开始。

### Engine E4 — Formal Local HTTP/JSON Integration Adapter — 2026-08-03

- 从 E3 `ContractTestAdapter` 抽取唯一正式 `ContinuityInteractionService`，测试 Adapter 与正式 `IntegrationAdapter` 共用同一验证、领域、Action Gate、Evolution、结果和 checkpoint 恢复链。
- 新增正式单 active SubjectBinding 与原子 JSON 仓储、显式幂等 init、completed/recovery_required 查询，以及只监听 `127.0.0.1:8766` 的串行 HTTP/JSON 服务；内部路由使用 Bearer 服务令牌和严格传输限制。
- E4 专项 61 项、完整 280 项测试通过，原 219 项继续通过；三份 v1.1 Schema、JSONL Runner、旧调试入口、Vio 仓库和 `0.1.0` 软件版本未改变。
- E4 只完成 Engine 侧正式本地服务。Vio 尚未调用，双方 HTTP 共享验收、生产形态 Integration Adapter、真实模型/Capability 和生产部署尚未实现。

### Vio × Engine First-Round Test-Only Shared Acceptance — 2026-08-03

- 以 Engine `7a32a99e60330782c1caf6d6adda5d08d0077a6c` 和 Vio `673983901b38127b15f772a8be8507defec7384e` 为正式基线，记录第一轮 test-only 端到端共享验收通过。
- Vio 持久化 V1 请求已通过 JSONL Runner 进入真实 E3；Vio V2 已严格验证并保存 Engine 结果、revision 0/1 投影和三条 receipt，幂等、revision、四类错误及双方重启精确重放均通过。
- 验证结果为共享 6/6、Vio V1+RFC 8785 17/17、Vio V2 29/29、Vio 后端全量 95/95、Engine Runner 16/16、Engine 全量 219/219。
- 本里程碑不提升 `0.1.0` 软件版本，也不表示正式本地服务、网络连接、生产 Integration Adapter、真实模型或前端数据链路已实现；下一阶段须另行共同确认与授权。

### Engine JSONL Runner Independent Acceptance — 2026-08-02

- 记录项目统筹窗口独立技术验收 Engine test-only JSONL Runner 正式通过；专项 16 项、完整 219 项和 93 个 Python 文件 AST 解析通过，未发现阻塞问题。
- 当前具备整理并提交同步 Runner 成果的条件；本次验收不改变 D-029 机器语义或 `0.1.0` 软件版本。
- Vio 尚未正式调用 Runner，双方端到端共享验收、Vio 投影接收、网络和生产 Integration Adapter 尚未完成；只有 Engine 提交同步后才能开始 Vio 测试代码实际调用。

### First Round Shared Acceptance Preparation — Engine JSONL Runner — 2026-08-02

- 在 `tests/shared/` 新增 test-only UTF-8 JSONL Runner 和真实 E3 装配辅助，必须显式使用受控临时数据目录；每行直接调用 `ContractTestAdapter.submit()` 并立即输出原始成功或错误对象。
- 支持固定 fixture 一次初始化、完整目录恢复、同进程/跨进程精确重放、重启后新请求 UUID 唯一，以及部分、损坏或矛盾目录拒绝启动；未增加网络、生产 CLI/HTTP 或外部能力。
- 新增 16 项真实子进程专项测试，完整 219 项通过，原 E3 验收基线 203 项继续通过。
- Vio 尚未实际调用 Runner，投影接收、双方共享验收、网络和生产 Integration Adapter 尚未完成；软件版本继续保持 `0.1.0`。

### Engine E3 Acceptance — 2026-08-02

- 记录项目统筹窗口独立验收 Engine E3 正式通过；`ContractTestAdapter`、Observation/Event 隔离、确定性领域闭环、Action Gate、Evolution、operation journal、中断恢复和跨重启精确重放均通过核对，未发现阻塞问题。
- E3 专项测试 50 项、完整测试 203 项全部通过；Engine E1、E2、E3 至此均已完成并通过验收。
- E3 仍只代表 Continuity Engine 侧 test-only、进程内闭环完成；Vio 客户端、投影接收器、双方共享测试、网络和生产 Integration Adapter 尚未实现。
- 当前未授权继续代码施工，下一步等待双方确定 Vio 侧施工和共享验收顺序；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E3 — 2026-08-01

- 在已提交同步的 E2 基线 `d1a96b1` 上新增独立、test-only、进程内 `ContractTestAdapter`，按 Schema/hash、Binding、ledger、revision、operation reservation 和领域闭环的固定顺序处理第一轮请求。
- 将已验证平台事实作为只读 `PerceivedPlatformFact` 送入 PerceptionResult；Thinking 只读取感知结果，平台 `sourceEventId` 不直接成为内部 Event/StateMutation。
- 新增确定性 MemoryRetriever、ThinkingProvider、ReplyComposer、TokenBudgetManager，复用真实 Wake、Perception、Action 权限/风险/资源/revision Gate 和必要时 Evolution；无获批 `UPDATE_STATE` 时不改变 revision。
- 新增 `ApprovedStateAction`、集中式 `ActionEvolutionService` 和阶段化 operation journal，以稳定 operation/response/event 身份支持跨重启中断恢复且不重复演化；不宣称多个 JSON 仓储之间具有跨文件原子事务。
- 新增 50 项 E3 测试；完整 203 项测试通过，E2 同步基线 153 项继续通过。
- E3 不复用或修改现有 API/HTTP/UserInteraction 调试入口，不包含 Vio 客户端、投影接收、共享测试、网络或生产连接；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E2 — 2026-08-01

- 在已提交同步的 E1 基线 `ac61e78` 上新增不可变第一轮成功结果、四类固定错误 envelope、最小 stateProjection 和严格恢复边界。
- 将 E1/E2 共用的 RFC 8785/SHA-256 规则集中到领域完整性模块，保留原 service 兼容导出；以同一实现计算 `stateHash` 与 `contentHash`，并新增固定 SubjectBinding fixture/hash 的本地持久化与恢复。
- 新增以 requestId 为永久键的不可覆盖 completed result ledger，支持同 hash 跨重启精确重放、不同 hash 冲突、subject revision 投影唯一和非空 engineUpdateId 唯一。
- JSON 存储使用 UTF-8、显式格式版本、临时文件、flush/fsync 与原子替换；损坏、缺字段、错误版本和 hash 不一致会明确失败。
- 新增 36 项 E2 正反向测试；完整 153 项测试通过，E1 同步基线 117 项继续通过。
- E2 不包含 `ContractTestAdapter`、完整交互编排、Vio 投影接收、实际连接或共享测试；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E1 — 2026-08-01

- 新增 v1.1 第一轮 `ContinuityInteractionRequest`、PlatformObservation、message fact、嵌套值对象和固定 SubjectBinding fixture 的不可变类型化模型。
- 新增三份 Draft 2020-12 Schema 作为单一权威来源，以及仅支持三个绝对 URN、拒绝网络/相对路径/别名回退的本地 registry。
- 新增严格 Schema、禁止状态写字段、identity/conversation/reference、正文位置、UTC 时间和 hash 校验；使用 RFC 8785 规范化并独立复算三个正式固定 hash。
- 新增 `jsonschema>=4.26,<5`（MIT）和 `rfc8785>=0.1.4,<1`（Apache-2.0）两个本地运行依赖。
- 新增 30 项 E1 正反向测试；完整 117 项测试通过，原有 87 项继续通过。
- E1 不包含 `ContractTestAdapter`、持久化账本、跨重启重放、投影、Vio 实际连接或共享测试；软件版本继续保持 `0.1.0`。

### Bilateral Archive Final Review — 2026-07-30

- 记录 Vio 与 Continuity Engine 双方工程档案最终只读复核通过，双方档案一致。
- 当前允许双方共同制定第一轮最小连接施工提示词，但提示词尚未制定完成；本次许可不授权代码施工。
- 第一轮代码施工、共享测试和实际运行时连接尚未开始，所有已列出的运行时连接能力仍未实现。
- 本里程碑仅同步文档阶段状态，不提升 `0.1.0` 软件版本。

### Architecture Consistency Correction — 2026-07-30

- 修正当前工程档案中残留的“Vio 前端直连 Continuity Engine”旧拓扑，统一为 Vio 前端只连接 Vio 平台后端，Vio 与引擎作为平行系统通过正式版本化契约协作。
- 修正“模型回复必然生成 StateMutation”的旧表达，明确只有 Action 合法批准 `UPDATE_STATE` 才能创建内部 Event/StateMutation 并进入 Evolution；未批准时 revision 保持不变。
- 保留历史施工和变更记录，并明确旧描述已被 v1.1、D-025 及本次定点修正取代。双方工程档案同步和定点修正已完成，当前等待最终复核；第一轮施工提示词、代码施工和共享测试尚未开始。
- 本次仅为文档与架构一致性修正，不提升 `0.1.0` 软件版本，也不表示任何连接运行能力已经实现。

### Integration Contract Archive Sync — 2026-07-30

- 记录 Continuity Engine 正式接受 `Continuity Integration Contract v1.1`，并完成 Continuity Engine 侧工程档案同步。
- 记录 Vio 与 Continuity Engine 双方档案同步完成、当前等待档案核对；第一轮施工提示词、代码施工和共享测试尚未开始。
- 本里程碑只涉及文档与架构决定，不提升 `0.1.0` 软件版本，也不表示 PlatformObservation、SubjectBinding、ContractTestAdapter、持久化账本、结果重放、投影连接或生产集成已经实现。

### Architecture Documentation — 2026-07-23

- 新增 `docs/project_memory/05_核心模块架构.md`，集中说明 Continuity Engine 十层核心架构。
- 为 SubjectState、Evolution、Memory、Awakening、Perception、Thinking、Action、Permission、Learning 和 Resource 分别记录当前状态、当前作用和未来扩展方向。
- 在项目总览中增加核心架构入口，并继续明确框架完成不等于真实模型、MCP、外部记忆、动作执行、后台运行或 Token 计费已经接入。
- 本次只新增和更新工程文档，没有修改源码或测试，也没有新增功能。

### Engineering Archive Sync — 2026-07-23

- 以《数字连续性引擎工程总档案 v1.0》同步长期工程档案，明确 Continuity Engine 是位于 AI 模型之外的连续性层。
- 记录目标实时状态闭环：用户输入 → SubjectState 读取 → Memory 检索 → 模型回复 → StateMutation → Evolution → SubjectState 保存。
- 统一 SubjectState、Evolution、Memory、Awakening、Perception、Thinking、Action、Permission、Learning 和 Resource 的框架完成口径，并明确真实接入边界。
- 记录工程总档案后续阶段 8—12：AI 模型、MCP/外部记忆、正式前端、自主学习完善和自主运行；这些均未标记为已完成。
- 明确真实模型、真实 MCP、外部长期记忆、真实动作执行、后台自主运行和真实 Token 计费仍未实现。
- 本次只同步 `docs/project_memory/` 工程文档，没有修改源码、测试、README 或项目配置，也没有新增功能。

### Fixed — 2026-07-23

- 为 `storage/base.py` 启用延迟求值类型标注，修复 Python 3.11–3.13 中 `PermissionRepository.list()` 遮蔽内置 `list` 后影响后续类型标注的问题。
- 保持 `PermissionRepository.list()` 方法名、参数和返回协议不变。

### Documentation — 2026-07-23

- 将 README 更新为 Continuity Engine v0.1 原型的真实能力范围。
- 明确 SubjectState、Memory、Awakening、Perception、Thinking、Action、Permission、Learning、Resource Management、进程内 API、本地 HTTP 和调试前端的当前边界。
- 明确真实 AI Provider、MCP、平台 Skill、外部长期记忆库、真实动作执行、后台常驻运行和真实 Token 计费尚未实现。
- 更新 `pyproject.toml` 的过期项目描述，并同步当前状态与施工日志。

### Verification — 2026-07-23

- Python 3.14.4 完整自动化测试 87 项通过。
- 全部 Python 源码和测试通过 Python 3.11 语法版本解析检查。
- 当前环境未安装 Python 3.11–3.13，因此未执行这些解释器的运行时测试。

### Documentation — 2026-07-22

- 新建 `docs/project_memory/` 长期工程档案系统。
- 记录项目总览、当前状态、归一化施工路线、历史施工摘要和架构决定。
- 记录已完成模块、未完成事项、待确认能力、未来扩展和开发规范。
- 明确当前 Git 基线、README/项目描述过期、缺少 LICENSE/CI 等交付风险。
- 完成档案最终校准：移除不存在的独立思考上下文类描述，独立记录 Event/Evolution，统一 MemoryRetrievalResult 名称，并将 Resource Management 标为部分完成。
- 本次仅新增文档，没有修改任何代码、README 或项目配置。

## [0.1.0] — 尚未发布

### Added

- SubjectState 六分区模型、revision、JSON 持久化和 CLI。
- Event、Evolution、StateUpdateRecord、前后差异和 expected_revision 并发保护。
- 可插拔 Memory 管理层、相关性判断和记忆影响记录。
- Awakening System：WakeCycle、WakeSession、WakeContext 和四类 WakeDecision。
- Thinking Engine：直接接收 PerceptionResult，通过 ThinkSession 保存上下文摘要、预算、结果和关联信息，并提供 ThinkingResult、ThinkingProvider 与预算接口。
- Perception Engine：关注、时间、关系、记忆影响、观察、内在驱力和摘要。
- Action Engine：Intent、Decision、Step、Plan、Session，及权限、风险、资源评估。
- Permission Continuity Layer：PermissionState、历史、Context 和 JSON 恢复。
- Learning：LearningEvent、PersonalityTrait、LearningRecord、验证、固化与回滚框架。
- Resource Management：ResourceState、RuntimeMode、TokenUsageRecord、Policy/Manager。
- APIService、统一请求响应、安全门、MCP Adapter 和 Skill Adapter 接口设计。
- 最小本地 HTTP/FrontendClient/聊天界面、状态调试入口和用户交互编排。

### Architecture

- 正式 SubjectState 修改统一经过 Event / StateMutation → Evolution。
- Perception 成为 Thinking 唯一直接输入层，并保持只读。
- Thinking 模型、Memory、Permission 和外部 Adapter 保持可插拔。
- Action 只决定和规划，不执行真实外部操作。
- 外部入口必须经过 PermissionContext 和 ResourceManager。
- 学习不训练模型，长期变化需要多证据、验证、确认并可回滚。

### Verification

- 当前完整自动化测试集：87 项通过。
- SubjectState、权限、学习和资源的 JSON 重启恢复路径已覆盖。
- Action 权限/风险/资源/revision 边界及 Wake → Perception → Thinking → Action → Evolution 完整链路已覆盖。
- API/Frontend 数据流与“不在前端保存核心状态”边界已覆盖。

### Not Included

- 真实 AI API、MCP 连接、外部记忆库或真实 Token 计费。
- Execution Engine、真实联系用户或真实工具调用。
- 生产数据库、认证、多租户、支付、生产部署或 SSE/WebSocket。
- 模型训练、参数更新、情绪模拟或无确认的永久人格改变。

### Repository Status

- `0.1.0` 来自 `pyproject.toml`；工程档案提交 `216bdfd` 已同步到 `origin/main`，当前发布前整理修改尚未提交，也没有版本标签。
- README 和项目描述已经同步；正式发布前仍需人工评审当前修改，并在后续独立任务中决定 LICENSE、CI 和版本标签。
