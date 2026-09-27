# W04-1 逐项施工与验收矩阵

状态：`IMPLEMENTED_NOT_ACCEPTED`；本表记录本子批的实现和施工方测试，不代表 W04 整体验收。权威规划见 [Stage Brief](stage-brief.md) 与 [T01—T90 映射](../planning_v16_20260927/test-stage-map.md)。

| Planning Item | Code Change / 原链 | Test / 原始证据 | Acceptance Result / 边界 |
|---|---|---|---|
| N08 / T16、T17 | `domain/environment_access.py` 的听说、发现、连接、当前可用四态；`JsonEnvironmentRepository` 持久化代次和禁用；`EnvironmentAccessService.require/select` 每次重新核对连接、授权、期限、用途与范围 | `tests.test_w04_1_environment.W04EnvironmentTests` 的 four_states、revocation、alternative_route、current_check、handoff | 本批契约与 TEST 路由；真实服务断连及 P22 真实替代路线未就绪 |
| N09 / T19—T21、T60 | `MigrationPreparation` 区分首次外部导入、同主体交接准备、新主体创建、入口切换；`handoff_isolated` 以原主体和 generation 隔离旧端；不把 P01 快照称为生产恢复 | migration_kinds、isolated_handoff、corrupt_store，以及 P15/P18 兼容 | 仅隔离的清单和失权契约；P20/P21 正式迁移、恢复和运行权交接未就绪 |
| N10 / T22、T85—T87 第一批 | 身体 `NONE/SIMULATED/REAL`、`Body Identity/Binding`、输入输出能力的单位、坐标、范围、时效及未知与零值；模拟观察在 `validate_sensor` 核对，行动仍经原 P17 `ExecutionService`/E5-A | body_none、sensor_missing、body_action、revocation_inside_resource_check | 本批只证明契约与 TEST 入站／行动接线；W04-2 完整 Fake Body 感知→Perception、动作→结果闭环未完成，真硬件未接 |
| N12 / T26、T33 | `AttachmentKind` 区分消息、工具、模型 API、同 Engine 集成；可信 `AttachmentUse` 经原 `ContinuityInteractionService.submit` 内部入口进入 W02 入站前门禁；P17 能力投递前复核。两份受保护的正式接口文件不变 | formal_ingress、enabled_bound_entry、cross_environment、same_account、model_api、body_action | 同名账号不合并身份，关联不扩权；W04-4 跨软件话题连续性与 P22 真实账号未就绪 |
| N21 / T66、T67、T72 第一批 | `HistoryScope` 表达对象、软件/设备/会话、时段、来源、权限、模式、意愿和限量；`ScopedHistoryService` 复用原 Router/Composer，只返回原引用与版本/hash、再验当前权限和主体 revision | scoped_history、history_current_source、history_permission_change、history_old_revision、deep_history | 最小只读局部查询；深层 ARCHIVED/外部考证标 `DEPENDENCY_MISSING`，W05 自然记忆与心智联动未施工 |
| 适用 T18 | repository 的身份、hash、CAS、原子提交及重开；入站拒绝零写入、动作重复原 E5-A 一次效果/扣费；旧调用不设置 W04 门禁时仍沿原链 | isolated_handoff、corrupt_store、formal_ingress、body_action；P16/P17/P18/W02/W03 同版兼容与全量 | 不新增请求/结果账本；未知事实不盲重发；当前仅 TEST/RESEARCH |

各行的本批部分均已实现并完成施工方同版验证：24 项专项 PASS、182 项相关兼容 PASS、全量 1797 项中 1796 PASS／1 既有 SKIP／0 FAIL/ERROR；三组运行前后指纹相同，集合不相加。**验收结果仍为 `IMPLEMENTED_NOT_ACCEPTED`**，等待独立复核；后置能力不得据此标为完成。原始命令和结果见 [测试索引](test-index.md)。原 20 项 D-085 规划归档是前置工作区基线，不属于本批实现。

## 2026-09-27 N09／N10 定点返修增量（待独立复核）

上段 24／182／1797 是**返修前 W04-1 原交付历史**，不能充作本轮终局结果。返修依据和原始失败见[返修报告](repair-report.md)及[增量测试索引](test-index.md)。

| Planning Item | Code Change | Test / 修前与修后 | Acceptance Result |
|---|---|---|---|
| N09 / T19—T21、T60：准备单身份 | `services/environment_access_service.py` 的 `handoff_isolated` 在仓储读取／写入前核对 subject/environment；原 generation、host、revision 链保留 | `test_handoff_preparation_cannot_cross_subject_or_environment` 修前失败；修后专项通过；原 `test_isolated_handoff_fences_old_host_and_restart_keeps_fence` 仍通过 | `IMPLEMENTED_NOT_ACCEPTED`；跨主体/环境零目标写入，正式生产交接仍 P20/P21 |
| N09 / T19—T21：类型、缺项和就绪状态 | `domain/environment_access.py` 的 `MigrationPreparation` 计算唯一合法状态；交接入口仅接受无缺项的同主体准备 | `test_migration_preparation_status_cannot_contradict_kind_or_inventory` 修前失败、修后通过；原缺项/入口切换正向对照保留 | `IMPLEMENTED_NOT_ACCEPTED`；错误类型不能伪称 READY |
| N10 / T22、T85—T87：输出能力时效 | `services/environment_access_service.py` 的原 `require_action` 查当前具体 OUTPUT 能力期限，原 P17/E5-A 仍负责效果和回执 | `test_expired_output_ability_rejects_existing_execution_before_effect_or_cost` 修前失败、修后通过；新增 `test_current_output_ability_executes_through_existing_execution` 正向通过 | `IMPLEMENTED_NOT_ACCEPTED`；到期零效果/零费用，W04-2 双向模拟闭环未提前完成 |
| N10 / T22、T85—T87：传感读数 | `services/environment_access_service.py` 的 `SensorObservation` 拒绝非有限、布尔及非数值读数 | `test_sensor_contract_rejects_non_finite_bool_and_wrong_type` 修前 FAIL/ERROR，修后通过；零值与 `None` 未知正向通过 | `IMPLEMENTED_NOT_ACCEPTED`；不把未知伪装为零 |
| T18 及 P16/P17/P18/W02/W03 兼容 | 无新的状态、请求或结果账本；旧调用无 W04 门禁时行为不变 | `w04-r1-compat-final-01` 182 PASS；`w04-r1-full-resume-01` 1802 项中 1801 PASS／1 既有 SKIP／0 FAIL/ERROR；两者及专项同一前后源码指纹。旧 `w04-r1-full-final-01` 人为中断单列 | `IMPLEMENTED_NOT_ACCEPTED`；独立复核和用户验收仍未发生 |

## D-087 验收附记（不倒改上方施工时状态）

用户正式验收 W04-1 初版与 N09/N10 定点返修；本批各适用 Planning Item 现为 `ACCEPTED`，W04 整体仍 `IN_PROGRESS`。逐项当前验收结论见[验收矩阵](../w04_1_acceptance_evidence/acceptance-matrix.md)。上方 `IMPLEMENTED_NOT_ACCEPTED` 和初版/返修过程 PASS、FAIL、ERROR、`INTERRUPTED` 均为历史记录，保持原貌。
