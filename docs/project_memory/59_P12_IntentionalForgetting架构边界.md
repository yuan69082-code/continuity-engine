# P12 Stage Brief：Intentional Forgetting 与记忆停用

<!-- P12_REVIEW_CURRENT_START -->
> P12 独立复核后现行状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE（本轮独立复核阻断已闭合，非用户正式验收）。监工实跑原 9 条 PASS（1.207 秒）、新 7 条 PASS（1.011 秒）、P12 117 PASS（27.198 秒）；核验引用施工全量 1011 项：1010 PASS、1 既有 SKIP、0 FAIL/ERROR，stderr 521.632 秒、结构化记录 521.633 秒。
>
> [独立复核与本次 Git 收尾范围](P12_独立复核与Git收尾_20260907.md)。今晚一次性普通提交推送已获条件放行；此档为提交前记录，实际 SHA 和推送结果由 Git 记录及施工最终报告确认。没有创建 D-061，没有授权 ACCEPTED；下方全部 FAIL/ERROR/SKIP、证据冲突及 P09 segment 10 UNKNOWN 历史保留。
<!-- P12_REVIEW_CURRENT_END -->

<!-- P12_SECOND_CURRENT_START -->
> P12 第二轮 F1/F2 返修送审历史状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，等待独立复核。本轮 P12 117/117 PASS，29.667 秒；新 7 条与原 9 条探针均 PASS（1.090 / 1.327 秒）。兼容 257 项：257 PASS、0 SKIP，58.099 秒；全量 1011 项：1010 PASS、1 既有 SKIP、0 FAIL/ERROR，521.633 秒。
>
> [本轮修改、失败历史与复核入口](P12_第二轮返修_F1-F2.md)。下方第一轮及初版结果均为历史，不能代替本轮。保留 117 项首次兼容失败、前轮全部 FAIL/ERROR/SKIP 和 P09 segment 10 UNKNOWN。没有用户验收决定，没有 Git 写操作。
<!-- P12_SECOND_CURRENT_END -->

<!-- P12_REPAIR_CURRENT_START -->
> P12 第一轮返修历史状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（独立复核阻断待监工确认关闭）。本轮 P12 专项 98/98 PASS（22.654 秒）。兼容 257 项：257 PASS、0 既有 SKIP，55.715 秒；稳定全量 992 项：991 PASS、1 既有 SKIP，0 FAIL/ERROR，523.914 秒。
>
> [五项返修、原始失败及独立复核入口](P12_独立复核返修_R1-R5.md)。初版 71/965 与其 NONE 状态作为历史保留，不能代替本轮结果。不登记用户验收，不执行 Git 写操作，不进入 P13；生产自动策略/物理删除仍未开放。
<!-- P12_REPAIR_CURRENT_END -->


2026-09-06。用户本轮指令已确认本阶段范围；下列 Stage Brief 保留开工时快照，此档先于实现建立。

- STAGE：P12 Engine 独立施工；IN_PROGRESS，非验收。P00—P11 ACCEPTED；P13—P23 NOT_STARTED；Vio dependency=NONE。
- SOURCE OF TRUTH：本轮用户授权；2026-08-26 全周期 v1.1、v6.7 及 Assistant 同步规划；D-059 和当前源码。只读提取保留正文、表格顺序与三份源文件 hash，见 [规划来源](p12_evidence/planning-source.json)。开工 HEAD 为 `1b8020fbe687dafaaf83a629dbeee65d69a71d67`，实测见 [基线](p12_evidence/before.json)。
- ORIGINAL REQUIREMENTS：v1.1 P12 施工卡（正文块 173—180）要求 active/inactive/archived/deleted、衰减、检索排除、恢复、证据保留及删除传播；普通遗忘不得静默删除 Event；永久删除需要明确生命周期命令。统一门槛（272—282）要求来源追溯、重启幂等、隔离、可运行入口和实际测试。
- V6.7 DETAILS：Memory Consolidation 是现有 Memory 内部流程；DerivedSummary 保留 source ID/version/hash，不能升级为事实权威。J 类测试（365—374）要求 resolved/archived 后实际降权、普通召回减少、强关联有限历史召回及不同时间跨度验证；降低本轮材料影响不等于自动改写已形成的主体判断。长期场景明确逻辑时长、事件数、重启点、预算和不变量。
- AMENDMENT OVERRIDES：v1.1 Override/Keep、v6.7 Architecture Amendment D1 及 Engine 独立施工附录适用。P01—P21 使用宿主中立 Port/Fake；正式恢复与删除生产能力不得用 P01 Sandbox 冒充；Reality Boundary 不控制内在心理。Assistant 已独立，不自动同步。
- KEEP RULES：唯一 SubjectState/Evolution/revision 权威、唯一 Memory 和既有 lineage/Consolidation 操作链、Event 历史不可因遗忘删除；保留根证据去重、R01—R08、R05/R06 当前置信度公式、E5-A 恢复路径、P09 segment 10 UNKNOWN 及全部历史证据。
- DEPENDENCIES：P04 Memory/Consolidation/JsonMemoryRepository；P05 Router；P06 Composer；P07 来源失效；P09 正常 C1 链；既有 PermissionService、Learning 与 P11 边界。生命周期使用当前 Memory 版本与既有 lineage 原子写入，不设第二账本。
- NOT READY：正式遗忘阈值、归档年限、永久删除确认策略未决定；自动策略默认未配置。仅显式 TEST 策略验证逻辑 tombstone 与恢复禁止，物理擦除、备份清除、生产删除/恢复属于 P20/P21，未实现。不存在 Engine Actions workflow；不报告远程 CI PASS。
- FILES ALLOWED：`src/continuity_engine/domain/memory.py`、新增 `domain/memory_lifecycle.py`；`services/memory_consolidation_service.py`、`memory_service.py`、`context_router_service.py`、`context_material_resolvers.py`、`learning_service.py`、`continuity_core_service.py`、`continuity_core_runtime.py`、新增 `memory_lifecycle_service.py`；`storage/json_memory_repository.py`、`json_learning_repository.py`、必要 `storage/base.py`；新增 `testing/p12_memory_fixture.py`；新增 `tests/test_p12_memory_lifecycle.py`、`tests/test_p12_memory_integration.py`。档案：59—62 P12 专题、`p12_evidence/`、README、当前状态、路线图、施工日志、决策记录、完成/未完成/待确认清单、核心架构、P00 测试索引、修订记录、CHANGELOG、工程总档案。
- FILES FORBIDDEN：六份外部 Schema、25 项冻结边界、pyproject/version 0.1.0、正式七文件、三份规划源、Assistant、31 个 P10 脚本、所有既有原始证据；不改 Git 元数据、不联网、不开发 P13—P23。
- TESTS REQUIRED：先保存真实反例与新增行为红测，再跑 P12 专项及 P04/P05/P06/P07/P09/Learning/前审查修复直接兼容；代码稳定后一次全量。检查原 894 个测试身份保留；PASS/SKIP/FAIL/ERROR 分列；拒绝路径检查零写入/零唤醒/零扣费。静态解析、链接、敏感信息、保护 hash、差异核查。仅档案变化不机械全量重跑。
- PLANNING CONFLICT：NONE。生产删除/自动策略的未就绪状态按授权显式保留，不计作已实现。

## 实施约束

生命周期与温度、事实有效性分别记录；旧记录不迁移、不改变旧 canonical hash。降权改变可消费权重，不宣称事实变假。每条新生命周期命令绑定 subject/environment、当前权限、scope、expected revision/hash、理由与确认；当前读取不静默写入。历史召回只读且有界，不生成恢复命令。所有长期状态写入仍归既有 Evolution。

## 当前交付状态

P12 / Engine side / P12-01—12 = IMPLEMENTED_NOT_ACCEPTED；P00—P11 ACCEPTED，P13—P23 NOT_STARTED；Vio dependency=NONE。已发现的施工失败已修正并完成稳定专项、兼容和一次全量，PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE；仍等待独立复核及用户正式验收，不创建验收决定。真实运行与限制见 [62](62_P12_测试索引与验收入口.md)，原开工 IN_PROGRESS 和所有失败记录保留。

<!-- P12_REPAIR_FACT -->

## P12-R1—R5 Stage Brief 范围补记

FILES ALLOWED 在原列表内限定五个运行文件：domain/memory.py、services/memory_lifecycle_service.py、services/memory_consolidation_service.py、storage/json_memory_repository.py、services/context_router_service.py；新增 tests/test_p12_memory_review_regressions.py 和 tests/test_p12_memory_weight_windows.py、p12_repair_evidence/ 和五项返修说明。其他原文件只同步直接档案。原件、旧测试、已有证据和保护边界均不变；NOT READY 策略不变。 本轮 P12 专项 98/98 PASS（22.654 秒）。兼容 257 项：257 PASS、0 既有 SKIP，55.715 秒；稳定全量 992 项：991 PASS、1 既有 SKIP，0 FAIL/ERROR，523.914 秒。 [本轮入口](P12_独立复核返修_R1-R5.md)。
<!-- P12_REPAIR_FACT_END -->

<!-- P12_SECOND_FACT_START -->

## P12-F1/F2 Stage Brief 范围补记

FILES ALLOWED：本轮运行代码仅 src/continuity_engine/storage/json_memory_repository.py、src/continuity_engine/services/memory_service.py；新增 tests/test_p12_memory_second_review.py、P12_第二轮返修_F1-F2.md、p12_second_repair_evidence/，以及本档和直接导航 18 份档案。SOURCE OF TRUTH 为本轮授权、只读 p12-recheck-20260907 报告及原七条探针；其他原 Stage Brief 和 NOT READY 边界继续适用。先验证旧 204 文件与前轮全量 hash 一致，未重跑修改前全量。 本轮 P12 117/117 PASS，29.667 秒；新 7 条与原 9 条探针均 PASS（1.090 / 1.327 秒）。兼容 257 项：257 PASS、0 SKIP，58.099 秒；全量 1011 项：1010 PASS、1 既有 SKIP、0 FAIL/ERROR，521.633 秒。 [第二轮证据](P12_第二轮返修_F1-F2.md)。
<!-- P12_SECOND_FACT_END -->
