# W02-C：N11 逐项施工、测试与待验收矩阵

> 后续定向补修发现并修复了“同版有效根只撤回单条派生材料时，旧 Memory 仍可被使用”的缺口。本表记录初版施工时的矩阵与结果；本项现行增量、真实修前失败及终局证据见[撤回传播补修矩阵](../w02_c_repair_evidence/matrix.md)。初版结果不能代替补修后的复核。

现行依据为归档总施工 v1.5、最终新增 v1.5、长期能力 v6.9 的 W02、N11、T23，并联验 T04/T18。下列 `IMPLEMENTED_NOT_ACCEPTED` 表示施工方实现及测试，**不是**用户验收。原 W02-A/B 保持 ACCEPTED，W02 整体 IN_PROGRESS。

| Planning Item | Code Change / 原职责 | Test / 原始证据 | Acceptance Result |
| --- | --- | --- | --- |
| N11-1：请求、回执、根、版本、时间、范围与校验 | 原 P16/E5-A 证明取得事实；`external_absorption.py` 将当前 TEST 根证明与原候选及 Connector 精确绑定，P16 缓存仅保存可重建处置 | `test_receipted_root_becomes_pre_answer_candidate_not_subject_fact`、`test_old_date_and_wrong_result_hash_are_rejected_before_absorption`、`test_corrupt_absorption_binding_fails_closed_before_context` | IMPLEMENTED_NOT_ACCEPTED |
| N11-2 / T04：原文、翻译、摘要、转存同根去重 | 根 ID 和证明 hash 保留，同根不同呈现只算一根；P04 Consolidation 使用原根证据，不另建记忆权威 | `test_same_root_original_and_derived_wrapper_count_once`、`test_two_independent_current_roots_can_use_original_p04_memory_and_summary` | IMPLEMENTED_NOT_ACCEPTED |
| N11-3 / T23：候选、临时参照、待证据、冲突、不采用 | `ExternalAbsorptionService` 记录处置及静态原因；`ExternalContextSource` 仅把当前相关候选送原 Router/Composer，并保留冲突标志、来源和审计计数 | `test_missing_root_proof_waits_and_does_not_infer_history_absent`、`test_distinct_counterevidence_is_conflict_not_a_winner`、`test_unrelated_external_material_is_not_selected_for_this_response` | IMPLEMENTED_NOT_ACCEPTED |
| N11-4：需要补证先等待与恢复，不先给确定结论 | 无根证明不进回应材料；后到的当前证明通过原回执和候选绑定后解除等待，不重发原查询；真正 UNKNOWN 保守 | `test_late_current_root_proof_closes_wait_without_repeating_original_effect`、`test_unknown_result_never_means_not_executed` | IMPLEMENTED_NOT_ACCEPTED |
| N11-5：合法长期更新，不直接写主体 | 显式 TEST 策略要求两个独立且当前有效的根及置信度，经原 P04 Consolidation 生成 EXTERNAL Memory；不写 SubjectState，生产策略未决定 | `test_one_root_is_not_enough_for_long_term_and_no_automatic_memory`、`test_two_independent_current_roots_can_use_original_p04_memory_and_summary` | IMPLEMENTED_NOT_ACCEPTED；生产策略 NOT_READY |
| N11-6：更正、撤销、删除、过期、撤权传播 | P16 当前消费、Memory/Summary Router 源、Composer resolver、P15 学习支持重验均检验当前根；旧 Context 失效 | `test_revocation_correction_scope_and_expiry_invalidate_old_context`、`test_permission_revocation_blocks_current_use_without_erasing_original_fact`、`test_revoked_source_never_becomes_new_material_on_replay` | IMPLEMENTED_NOT_ACCEPTED；跨 Store/备份生产删除 P20 |
| T18：原请求、返回丢失、重开与旧格式 | 普通工具 Result Observation 仍经 P16/E5-A；模型仍经原 ThinkSession；旧 P16 无证明缓存不静默升级 | `tests.test_w02_external_recovery` 全部 7 项，包含真实子进程重开 | IMPLEMENTED_NOT_ACCEPTED |
| T23：外部文本无权限或人格权威 | 明确控制面指令声明不进入候选；其余资料始终为 `RETRIEVED_CANDIDATE`，不能直接写 State；原 Broker、Permission、Action/Evolution 保持 | `test_external_control_claim_is_not_usable_or_permission`、P16/P17 兼容 | IMPLEMENTED_NOT_ACCEPTED |
| W02-A/B 联验：真实入站、回应前上下文与只读查询 | 原输入处置及自动回忆 gates 保留；外部候选在本轮 Thinking 前进入原 Composer；`outcome` 仅查询静态处置/身份 | `test_w02_a_and_b_real_ingress_share_pre_answer_external_candidate`、`test_read_only_outcome_does_not_advance_model_memory_or_revision`、W02-A/B 兼容 | IMPLEMENTED_NOT_ACCEPTED |
| 后置边界与身份 | 仅隔离 TEST/RESEARCH Fake；无真实 Provider/Vio、正式数据、P19 页面或 P20 生产删除 | 基线、各测试前后 identity、终局保护与排除审计 | IMPLEMENTED_NOT_ACCEPTED；P19/P20/P22 NOT_READY |

证据时间与完整数量以[测试索引](test-index.md)和[终局报告](final-report.md)为准；上表测试集合有交集，不累计求和。首次失败和辅助错误仍见原标签，不倒改为 PASS。
