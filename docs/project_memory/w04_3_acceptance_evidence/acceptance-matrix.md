# D-091 正式验收矩阵

Planning Item → Code Change → Test → Acceptance Result。测试引用施工方最终同版实跑；规划窗口只读复核，用户正式验收。原初版、返修矩阵保持当时状态，本表是当前验收结果。

| Planning Item | Code Change / 原链 | Test / 证据 | Acceptance Result |
|---|---|---|---|
| N14/T30 候选发现、核对和合法选路 | temporary_tools.ToolOffer；temporary_tool_service.candidates/offer；P16/E5-A | discovery_is_real_p16_and_not_current_availability、missing_discovery_and_untrusted_material_are_not_callable、technical_api_unavailable_may_select_ui_but_denial_and_unknown_do_not | ACCEPTED；资料不授予权限；缺入口诚实拒绝 |
| N14/T31 授权内接入、缺项等待 | ToolLease、conditions、原P08/P17、advance | authorized_connect_verify_use_cleanup_and_readonly、missing_login_resumes_same_connection_without_discovery_or_cost_repeat、conditions_identify_new_scope_budget_dependency_without_creating_connection | ACCEPTED；不逐步人工审批，购买/扩权不从普通授权推导 |
| N14/T32 单次/限时/持续结束及续期 | 当前租约、原Action/P17回执、Device可选门禁 | single_use_cannot_run_second_business_action、timed_task_completes_then_expiry_cleanup_uses_original_connection、explicit_renewal_uses_new_valid_grant_and_new_connection_identity | ACCEPTED；续期新有效条件，过期使用不复活 |
| N14/T41 退出中断、部分清理/未知/失败 | query/inspect/advance，原E5-A与P17事实 | lost_cleanup_response_recovers_without_duplicate_removal、cleanup_unknown_does_not_claim_closed_or_start_another_cleanup、cleanup_preserves_other_connection_and_subject_files | ACCEPTED；待清理不是断净，原失败不删除 |
| N14/T18 原请求续接及未接入取消 | connect最终门禁、原操作身份/取消与事实查询 | cross_process_lost_connection_recovery_and_replay、cancel_before_connection_reopen_and_replay_never_opens_it、cancel_during_connect_before_native_commit_is_fenced | ACCEPTED；不重复发现、连接、业务效果或费用 |
| N21 查询衔接 | 原DeviceOperation、指定回执Router/Composer | history_query_reuses_original_receipt_router_composer及W04-1/2专项 | ACCEPTED；2048预算不改，不代替W05自然记忆 |
| C11/N14/T31 R1 入队饥饿 | TemporaryToolRuntimeWork.needs复用Scheduler已有身份，最多两个新need | before-02修前FAIL；waiting_first_does_not_starve_second_or_native_work、both_native_needs_and_two_tools_obtain_real_dispatch、dependency_wait_and_pending_cleanup_do_not_block_ready | ACCEPTED；认知/维护仍真实推进；有限测试不保证无界负载 |
| C11/N14/T32/T41 R2 三次永久封顶 | advance每次最多一个清理；原回执completed_at退避，正有限配置默认5秒 | before-02修前FAIL；three_failed_cleanup_facts_can_resume_via_host、automatic_partial_cleanup_survives_three_failures_and_reopen、cleanup_backoff_is_receipt_bound_readonly_and_configurable | ACCEPTED；失败次数不永久撤销恢复资格，不无限快重试 |
| 当前权限、身份、控制与Context | W04绑定、原guard/current条件；旧Context不重绑 | cleanup_revocation_pause_stop_and_other_connection_isolation、current_host_and_scope_denial_prevent_new_cleanup、old_context_is_not_rebound_after_native_revision | ACCEPTED；PAUSE/STOP/host/环境隔离保持 |
| 秘密及只读边界 | 原P16/P17材料检查、静态诊断、inspect前后授权 | credential_secret_rejected_before_ledger_write_and_traceback_safe、view_rechecks_permission_at_return、connection_fact_corruption_refuses_read_and_has_no_effect | ACCEPTED；凭据仅受控引用；只读不触发业务或成长 |
| 兼容与完整回归 | 原P08/P16/P17/P18/W02/W03及W04-1/2 | 定点14、W04-3 60、W04-1/2 87、公共417、全量1922PASS/1SKIP；全组同版 | 验收范围内兼容证据通过；集合交叠不相加，CI未取得 |

测试名位于[初版测试](../../../tests/test_w04_3_tools.py)及[返修测试](../../../tests/test_w04_3_repairs.py)。源路径：[工具域](../../../src/continuity_engine/domain/temporary_tools.py)、[工具服务](../../../src/continuity_engine/services/temporary_tool_service.py)、[Action接线](../../../src/continuity_engine/domain/action_planning.py)、[Device门禁](../../../src/continuity_engine/services/device_operation_service.py)。

[原初版矩阵](../w04_3_evidence/matrix.md)、[原返修矩阵](../w04_3_repair_evidence/matrix.md)、[同版原始证据](../w04_3_repair_evidence/test-index.md)、[本次验收限定](acceptance-report.md)。W04整体IN_PROGRESS；W04-4及后续未开工，F1/H1/F2仍UNKNOWN。
