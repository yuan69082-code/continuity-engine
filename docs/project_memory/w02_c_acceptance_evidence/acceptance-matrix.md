# W02-C 初版与部分撤回补修正式验收矩阵（D-080）

以下为 2026-09-25 **现行验收判定**；[初版施工矩阵](../w02_c_evidence/matrix.md)和[补修施工矩阵](../w02_c_repair_evidence/matrix.md)的 `IMPLEMENTED_NOT_ACCEPTED` 是各自发生时的历史状态，原样保留。测试证据均为施工方实跑，规划监工只读复核；W02 整体仍 IN_PROGRESS。

| Planning Item | Code Change / 原职责 | Test / 原始证据 | Acceptance Result |
| --- | --- | --- | --- |
| N11-1：请求、回执、根、版本、时间、范围与校验 | 原 P16/E5-A 证明取得事实；`external_absorption.py` 与 `external_absorption_service.py` 绑定当前根、请求、回执和材料 | [初版矩阵](../w02_c_evidence/matrix.md)及 `test_receipted_root_becomes_pre_answer_candidate_not_subject_fact`、错误 hash 正反例 | ACCEPTED |
| N11-2 / T04：原文、译文、摘要、转存同根去重 | 根 ID 与材料证明留在派生处置，原 P04 Consolidation 按独立根巩固 | `test_same_root_original_and_derived_wrapper_count_once`、双独立根正向例 | ACCEPTED |
| N11-3 / T23：候选、临时参照、待证据、冲突、不采用 | `ExternalAbsorptionService` 记静态理由，`ExternalContextSource` 只把当前相关候选送原 Router/Composer | 缺证明等待、反例冲突、无关资料不进入 Context 的正式测试 | ACCEPTED |
| N11-4：补证先等待、旧事实恢复 | 复用原 P16/E5-A 回执与等待，不把 UNKNOWN 当作未执行 | 后到证明解除等待、UNKNOWN 不盲重发的正式测试 | ACCEPTED |
| N11-5：合法长期更新 | 明确 TEST 策略下双独立当前根经原 P04 Consolidation 建 EXTERNAL Memory；不写 SubjectState | 单根不足与双根长期 Memory/Summary 正反测试 | ACCEPTED；生产策略 NOT_READY |
| N11-6：撤销、更正、过期、撤权 | 原候选、Context、Memory/Summary、P15 当前支持按原链重验 | 撤销、更正、范围、到期、权限测试；[补修有效修前失败和修后证据](../w02_c_repair_evidence/test-index.md) | ACCEPTED；跨 Store/备份生产删除 P20 |
| N11/T23：只撤回同版有效根的一份派生材料 | `external_absorption_service.py` 的 `memory_current` 逐根核对 Memory 所存材料 hash，保留原文和历史取得事实 | `test_withdrawing_only_derived_material_invalidates_every_dependent_use`、跨进程重开与下一轮测试 | ACCEPTED |
| N11/T04：增添同根无关材料不误伤 | 保留根绑定的可扩展性，只使依赖被撤回材料的旧 Memory 失效 | `test_adding_unrelated_same_root_material_preserves_current_memory` | ACCEPTED |
| T18：重开、重复请求、返回丢失、旧格式 | 普通工具沿 Result Observation，模型沿 ThinkSession；原回执与身份重验 | `tests.test_w02_external_recovery`、补修子进程只读失效测试 | ACCEPTED |
| T23：外部指令没有权限或人格权威 | 控制声明不升级为可信候选，资料不直接写 State；Broker/Permission/Action/Evolution 不变 | `test_external_control_claim_is_not_usable_or_permission`、P16/P17 兼容 | ACCEPTED |
| W02-A/B 联验与当前回应 | 原入站处置、自动回忆和 Router/Composer gate 保留，当前外部候选只在回应前进入 Context | 真实入站、只读 outcome、[W02-A/B 123/123](../w02_c_repair_evidence/w02-ab-final-01.json) | ACCEPTED（本批联验） |
| 权限、隔离和后置边界 | 当前 root 继续核对 subject/environment/scope/permission/time；仅 TEST/RESEARCH Fake | [W02-C 25/25](../w02_c_repair_evidence/formal-final-01.json)、[公共兼容 260/260](../w02_c_repair_evidence/public-final-01.json)、[全量 1727 PASS/1 SKIP](../w02_c_repair_evidence/full-final-01.json) | ACCEPTED；P19/P20/P22 NOT_READY |

原始命令、退出码、耗时、失败和测试身份见[补修测试索引](../w02_c_repair_evidence/test-index.md)与[验收报告](acceptance-report.md)。集合重叠，不累计求和。
