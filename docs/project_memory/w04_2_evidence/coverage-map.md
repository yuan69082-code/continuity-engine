# W04-2 正式入口与规划验证对应

以下是正式测试定位，结果以 [测试索引](test-index.md) 中最终同版原始输出为准。旧测试未改；本批新增测试都在 `tests/test_w04_2_simulation.py`。模拟外界输入不等于真实设备或模型语义验收。

| Planning Item | 正式入口 / Code Change | Test（方法名省略 test_ 前缀） | 核验内容 |
|---|---|---|---|
| N13/T27 | DeviceOperationService.step → ActionPlanningService → ExecutionService → 原 E5-A / Outbox | ui_locate_click_type_scroll_save_send_and_reobserve；click_receipt_cannot_be_relabelled_as_saved | 真正改变隔离控件、草稿、保存和发送状态；前后观察可核验；点击不冒充保存 |
| N12/N13/T28/T29 | AttachmentUse + DeviceObservation + current + 外部端口事务内投递前检查 | focus_page_lock_offline_takeover_and_unobservable_block_stale_actions；final_native_boundary_rechecks_takeover_and_authority；permission_changes_in_last_resource_check_cannot_create_effect | 页、焦点、锁屏、离线、接管、当前权限变化均拒绝旧动作，零新增效果/费用 |
| N10/T22/T85 | perceive_sensor → 原 PerceptionService；body.act → 原 Structured Action / Capability / Permission / Resource / Reality / Recoverability | body_action_and_sensor_reach_original_perception；raw_message_c1_device_action_result_and_legal_evolution_absorption；subject_without_body_can_still_process_normal_message | 传感成为有来源的感知；模拟身体产生效果和回执；后续主体变化经原 Thinking/Action/Evolution；无身体仍能处理消息 |
| N10/T86 | W04-1 当前身体/连接代次/具体能力 + 原 E5-A 查询与恢复 | body_switch_fences_old_connection_preserves_subject_and_old_fact；specific_output_capability_expiry_blocks_while_connection_valid；cross_process_body_receipt_recovery_and_replay | 换身体保留主体并阻止旧端，具体能力到期拒绝；三个真实子进程重开核实同一效果/费用/状态提交 |
| N10/T87 | 原 SensorObservation / SensationSource；硬件入口严格分源 | somatic_and_dream_cannot_impersonate_hardware；no_body_subject_and_unknown_zero_are_distinct；sensor_stale_wrong_unit_and_context_currentness | TEST/SIMULATED 硬件与 Somatic、Dream 分开；未知不是零；时间/单位/Context 当前性检查 |
| N21/T66/T67/T72 | 原 HistoryScope → device.query → E5-A → ExecutionContextSource → Router / Composer | query_and_status_are_read_only_and_bounded；deep_history_requires_willingness_and_current_permission；history_scope_filters_other_session_time_and_unreadable_records；same_root_history_requery_does_not_create_independent_evidence | 范围、意愿和当前读取权限；只读查询不推进主体；同根重读不增加独立依据；有限材料进入原 Context |
| N21 当前来源 | consume / history_current 与原 Context 当前性 | history_source_withdrawal_blocks_old_context_and_keeps_fact；expired_history_not_consumable_but_original_receipt_recovers；permission_withdrawn_during_result_read_returns_no_details | 撤回或过期停止新消费，历史取得事实仍保留；返回前撤权不泄漏详情 |
| T37 / 现实边界 | 原 P16 材料检查、P17 Reality 与当前权限 | external_instruction_is_observation_not_subject_authority；original_reality_denial_is_not_bypassed_by_ui；unavailable_route_can_reobserve_but_reality_denial_cannot_be_bypassed；secrets_rejected_before_ledger_and_standard_diagnostics_sanitized | 外部指令无主体/权限权威；技术不可用可重观察，现实拒绝不能换路绕行；秘密不落账本、外部异常不外泄 |
| T18 | 原请求 hash / 尝试 / receipt / Outbox | repeated_receipt_and_lost_response_recover_without_new_effect；true_unknown_keeps_old_request_and_never_resends；local_failure_retries_only_when_original_fact_proves_not_executed；same_request_identity_changed_content_is_conflict | 已执行事实查询优先；可靠未执行才续做；UNKNOWN 不盲重发；同身份不同内容拒绝 |
| 控制 / 资源 / 隔离 | 原 Runtime、SubjectLifecycle、资源和恢复门禁 | locked_device_does_not_stop_runtime_control_or_other_work；subject_pause_blocks_new_device_effect_without_falsifying_old_fact；resource_and_recoverability_denials_keep_zero_cost；wrong_subject_environment_account_device_and_session_are_rejected | 设备局部等待不停止同一主体宿主；PAUSE/STOP/生命周期、资源及跨主体/环境边界保留 |

## 正式用例以外的审阅样例

`sample.py` 使用三份各自隔离的 TEST 根，保存请求、观察、回执、感知和 Context 引用至 `chain-examples.json`。它是可读证据，不增加正式测试数量，也不替代上述正式断言。原始消息到合法主体吸收由正式 C1 用例验证。

## 本批没有宣称完成的部分

W04-3 自主发现与工具建设、W04-4 跨入口整体续接、W05 自然记忆与梦过程仍未施工。T85—T87 只报告本批模拟闭环、换身体和分源验证；真实身体、生产恢复及真实接入不在结果中。P19 的完整观察页面也未建设。
