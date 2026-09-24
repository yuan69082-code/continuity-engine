<!-- W02_B_ACCEPTED_D078_20260924 -->
# W02-B 验收状态补记

用户以D-078正式验收本批。下表各项Planning Item的**现行Acceptance Result均为ACCEPTED**，其原IMPLEMENTED_NOT_ACCEPTED仅保留为送审时历史状态；W02整体仍IN_PROGRESS。规划窗口只读复核未独立运行Engine测试；施工方57项专项、66项A兼容、509项相关兼容、1703项全量（1702 PASS/1既有SKIP）是原始实跑且集合交叠。[逐项正式验收映射](../w02_b_acceptance_evidence/acceptance-matrix.md)与[决策D-078](../04_决策记录.md#d-078)给出当前判定；以下旧表原样保留实现位置、测试和送审历史。

---

# W02-B 规划—实现—测试—交付矩阵

本矩阵是 N02 / W02-B 的施工分解，不冒充新版规划原始编号，也不表示 W02 整体完成。所有行最高状态为 **IMPLEMENTED_NOT_ACCEPTED**；本轮原始专项记录 [w02-b-final-04](w02-b-final-04.json)，最终兼容与全量见[测试索引](test-index.md)。规划窗口尚未复核本批。

| Planning Item | Code Change（实际入口） | Test（正式方法/集合） | Acceptance Result / 限制 |
|---|---|---|---|
| N02 / T03 回答形成前主动评估 | [C1 prepare](../../../src/continuity_engine/services/continuity_core_service.py) 调用 [Recall.prepare](../../../src/continuity_engine/services/associative_recall_service.py)，先完成 Context 再 Thinking | `test_original_message_is_assessed_before_thinking`、`test_t03_raw_noon_and_afternoon_messages_recall_before_answer` | IMPLEMENTED_NOT_ACCEPTED；原始消息进入真实内部入口，Provider 实收最终 Context；不是模型自行决定查记忆 |
| T03 当前输入与旧材料 | [InputContextSource / HistoricalInputContextSource](../../../src/continuity_engine/services/input_context_source.py)，原 Memory/Timeline/原 journal | T03 同日12/15点，旧Event根、临时午饭报告同时进入最终fragment；`test_failure_and_reopen_resume_same_request` | IMPLEMENTED_NOT_ACCEPTED；原输入不必先长期巩固，仍是候选报告 |
| T04 独立根、去重与候选规则 | Recall `_preference_candidates` 调用原 P04 Consolidation.generate_summary；无新 Authority | `test_t04_preference_candidate_uses_original_roots_without_state_write`、`test_t04_replay_and_derived_summary_do_not_add_roots`、`test_new_independent_root_keeps_prior_candidate_source_readable` | IMPLEMENTED_NOT_ACCEPTED；多根未确认视图、重复不加票、无主体写入；W03完整长期认识不在本批 |
| T04 正反证及配置 | [RecallPolicy](../../../src/continuity_engine/domain/associative_recall.py)，原来源/权限再验 | `test_t04_no_fixed_number_implies_true_preference`、`test_t04_configured_candidate_rule_is_recorded_and_never_confirms`、`test_negative_counterevidence_prevents_candidate_confirmation`、`test_other_person_report_does_not_count_as_user_preference` | IMPLEMENTED_NOT_ACCEPTED；规则可配置并记录，达门槛仍不等于已确认喜欢 |
| T05 否定、他人、意愿、旧事、引用 | Recall `assess` 复用 A interpret，按分句和谓词范围构造不具事实权威的框架 | `test_t05_actual_ingress_variants_reach_final_context`、`test_quoted_and_ambiguous_reports_never_confirm_preference`、`test_not_wanting_is_not_positive_intent` 及 `test_t05_variants_preserve_report_scope` | IMPLEMENTED_NOT_ACCEPTED；有界中文工程解释，未知语法不强行确定。源时间不冒充事件时间，不确定饥饿程度 |
| T06 有理由展开与终止 | 原 [Router](../../../src/continuity_engine/services/context_router_service.py) 可选 recall_terms；Recall保存关联来源hash/SHARED_EVENT/停止码 | `test_finite_association_records_a_reason_and_stops_on_repetition`、`test_sufficient_material_stops_before_configured_depth`、`test_unrelated_material_does_not_trigger_association`、`test_bound_policy_does_not_force_fixed_depth` | IMPLEMENTED_NOT_ACCEPTED；轮数为配置，不是永久固定能力上限，不把全库塞进上下文 |
| T06 检索/时延/上下文分别受限 | policy/原 RetrievalBudget、ContextBudget；monotonic覆盖准备全过程；原 Composer去重、冲突及missing notices | `test_retrieval_and_context_budgets_are_independent`、`test_timeout_is_blocked_before_model_and_query_is_read_only`；P06组合含冲突/缺失/裁剪 | IMPLEMENTED_NOT_ACCEPTED；记录elapsed_ms、retrieved_count、model_calls/external_calls=0；原JSON仓储完整校验的I/O成本仍是限制 |
| T06 失效、不可读与失败不能等同无历史 | 原 revalidate / Composer resolve，历史输入附原根生命周期检查 | `test_stale_source_version_cannot_be_consumed`、`test_denied_memory_source_is_not_recorded_as_empty_history`、`test_no_match_is_distinct_from_source_failure`、`test_archive_and_delete_cannot_reenter_through_input_history`、`test_current_context_invalidated_by_corrected_root`、撤销对照 | IMPLEMENTED_NOT_ACCEPTED；拒绝、过期索引和source failure分层记录，不借摘要或输入副本绕过根失效 |
| T01/T02/T18 局部失败与恢复 | [原interaction](../../../src/continuity_engine/services/continuity_interaction_service.py)、[原journal](../../../src/continuity_engine/storage/json_integration_repository.py) 可选recall进度/绑定；原E5-A不变 | `test_ready_preparation_return_lost_reuses_receipt`、`test_actual_effect_return_lost_replays_without_duplicate`、`test_cross_process_restore_and_read_only_show`；A66兼容、P09/P16/P17/P18恢复组合 | IMPLEMENTED_NOT_ACCEPTED；同一请求、原回执恢复，真实跨进程0新模型/效果/扣费及不推进原revision |
| 当前权限/身份/隔离/只读 | 原 `recall_outcome` 返回前复核，原Context.current、根版本、主体生命周期 | `test_reference_withdrawal_prevents_new_model`、`test_stale_context_does_not_authorize_resume`、`test_wrong_subject_record_is_rejected`、跨环境/损坏/撤权中查询/只读重复/原revision变化对照 | IMPLEMENTED_NOT_ACCEPTED；只读不会检索、学习、模型调用或提交；旧过期上下文不偷刷新 |
| 正常主体链与不强迫表达 | [原C1工厂](../../../src/continuity_engine/services/continuity_core_runtime.py)、旧Thinking/Action/Runtime | `test_native_cognition_uses_same_pre_answer_evaluation`、`test_p18_native_recall_keeps_pause_stop_and_continuous_host`、`test_recalled_information_does_not_force_expression`、`test_local_recall_preserves_existing_external_capability_wait_channel` | IMPLEMENTED_NOT_ACCEPTED；无消息仍能原认知推进，PAUSE/STOP有效；外部UNKNOWN原链不盲重发 |
| 旧开关与持久化兼容 | [IntegrationOperationRecord](../../../src/continuity_engine/domain/integration_results.py)、[C1 Context](../../../src/continuity_engine/domain/continuity_core.py) 仅可选字段，旧路径不构造回忆 | `test_disabled_gate_preserves_original_round_trip`、`test_legacy_gate_disabled_does_not_construct_recall`、原测试全量；Snapshot/Branch独立根 | IMPLEMENTED_NOT_ACCEPTED；原1646测试身份/字节保留，原保护文件未改，未新增政策或审批 |

正式新增文件：[8项基础测试](../../../tests/test_w02_recall.py)、[14项边界测试](../../../tests/test_w02_recall_boundaries.py)、[25项组合测试](../../../tests/test_w02_recall_combinations.py)。另有[6项读取一致性补测](../../../tests/test_w02_recall_consistency.py)。及[4项实际入口语义补测](../../../tests/test_w02_recall_semantics.py)。这些是57项，含子用例的测试方法不能按子用例再加总。T01/T02/T18沿用已验收A及原权限/恢复链，同时由本批交叉用例核对；并非重做旧阶段。

未开放：W02-C完整外部可信吸收/最终贯通、W03完整长期认识、P19页面、生产外部接入。没有用后置能力替代本批回忆及未确认候选要求，也没有提前建设后置系统。

版本02追加的T06/T18联验：`test_historical_root_revoked_during_permission_cannot_be_returned`、`test_candidate_record_changed_during_permission_blocks_before_model`，对应 `InputContextSource._resolve` 的返回前根检查及 `AssociativeRecallService._preference_candidates` 的授权后原记录比较。用于证明减少重复解析仍失败关闭，而不是放宽原时延或授权。首轮全量T04超时及前后测量见[定向调查](full-timeout-investigation.md)；01版本的通过与失败保留，最终覆盖必须引用04版。

版本03补充：四项真实入站语义测试把一般偏好与进食域分开，保留同对象食物历史及引用不确定性。两项解析复用测试证明返回副本隔离、损坏即时拒绝及离开scope后旧加载行为；原授权回调撤销/记录变更测试继续保留。原T03/T04以及两项多根反例再次覆盖。当前正式完成结果以04标签原始JSON和最终索引为准，测试成功不等于验收。

最终04补充：`test_scoped_input_projection_matches_original_without_persisting_changes`和`test_input_projection_cannot_hide_corruption_in_another_original_record`核查输入投影与原绑定等价、原件不变、整份日志损坏仍拒绝。第三版专项超时及定向后续修补详见调查，不以诊断PASS关闭失败；正式最终结果见04标签。
