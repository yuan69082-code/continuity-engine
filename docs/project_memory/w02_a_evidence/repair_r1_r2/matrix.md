# W02-A 补修后逐项对应矩阵

本表补充原矩阵，不覆盖其发生时结论。所有行最多 IMPLEMENTED_NOT_ACCEPTED；施工方验证通过不等于正式验收。原始运行及源码绑定见 [最终报告](final-report.md)，精确测试身份见 JSON。

| Planning Item | Code Change / 当前入口 | Test（现有 test_w02_input_* 模块） | Acceptance Result |
|---|---|---|---|
|A01/N01/T01/T02/R2 原始理解|interpret v2，旧v1核验|InputLanguageRepairTests：negation、other_colors、quote、scope、v1_pending|本轮反例已补，待独立复核|
|A02/N01 来源/时刻|inputPreparation与原manifest/operation绑定|PartialInputQueryTests：corruption、subject_and_environment、version；原current_material|当前核验及原时刻保留|
|A03/N01/T05 相关站|_stations，普通问句不误送核实|原question_routes；report_friend；引用/歧义实际入站|本轮过度分流回归已补；不全模块强制参与|
|A04 接收≠记住|原Memory事实核验，候选不升级|原plain_claim/existing_event/same_event_name；repair quote_and_scope|原职责不变|
|A05 临时Context|当前输入候选与权限来源|新增plain_negation/other_colors真实Thinking材料；原预算/模型能力测试|不是W02-B自动回忆|
|A06 合法内部提交|原Thinking/Action/Evolution未改|原internal_evolution_survives_expression_refusal；表达/心智兼容|不由分流器修改主体|
|A07/T18/R1 部分恢复|原日志inputPreparation+失败/成功回执|partial_public_query、composition_failure、repeat_read_and_resume|同请求只补未完成站|
|A08 原事实恢复|原Memory/ThinkSession/E5-A|原saved_memory/thinking_saved/restart_completed/real_process_restart；新v1_pending|不重复调用/效果/扣费/revision|
|A09 完整性/并发|准备快照不可改写；原admission|partial_preparation、forged_success、unbound_completed_result；原concurrent/cross_process_busy|无第二账本；不宣称生产exactly-once|
|A10 当前门禁|当前来源许可、版本/Context、返回前重查|revoked_permission/revoked_during_query/rechecks_revision/expired_context；原材料门禁|拒绝且只读零副作用|
|A11 旧调用/隔离|可选内部字段，旧请求保守查询|legacy_partial、v1_pending；原disabled/native/snapshot/protected_fixture|冻结契约/Authority不变|
|A12/T24/R1 公开只读出口|input_outcome经可信材料核验|partial_public_query_after_local_failure/after_reopen/in_separate_process；重复查询|可信逐站进度可读，PENDING不假报COMPLETED|

原始4FAIL与中间1FAIL均保留。测试集合有交集，不相加。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，下一步仅独立复核。
