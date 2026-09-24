# W02-A 当前逐项验收矩阵

仅验收W02-A初版及R1/R2补修，原交付矩阵原样保留。[D-076](../04_决策记录.md)为用户验收依据；规划窗口完成的是只读代码与证据复核，结论仅为本轮核查范围内未发现新的验收阻断、实现/正式测试/原始结果相互对应；没有重新运行测试，也不保证不存在其他缺陷。

|Planning Item|Code Change / 原链入口|Test / 既有正式证据|Acceptance Result|
|---|---|---|---|
|A01/N01/T01/T02/R2 原始理解|interpret v2，旧v1核验|InputLanguageRepairTests：negation、other_colors、quote、scope、v1_pending|ACCEPTED（D-076）；本轮反例已补，用户已确认|
|A02/N01 来源/时刻|inputPreparation与原manifest/operation绑定|PartialInputQueryTests：corruption、subject_and_environment、version；原current_material|ACCEPTED（D-076）；当前核验及原时刻保留|
|A03/N01/T05 相关站|_stations，普通问句不误送核实|原question_routes；report_friend；引用/歧义实际入站|ACCEPTED（D-076）；本轮过度分流回归已补；不全模块强制参与|
|A04 接收≠记住|原Memory事实核验，候选不升级|原plain_claim/existing_event/same_event_name；repair quote_and_scope|ACCEPTED（D-076）；原职责不变|
|A05 临时Context|当前输入候选与权限来源|新增plain_negation/other_colors真实Thinking材料；原预算/模型能力测试|ACCEPTED（D-076）；不是W02-B自动回忆|
|A06 合法内部提交|原Thinking/Action/Evolution未改|原internal_evolution_survives_expression_refusal；表达/心智兼容|ACCEPTED（D-076）；不由分流器修改主体|
|A07/T18/R1 部分恢复|原日志inputPreparation+失败/成功回执|partial_public_query、composition_failure、repeat_read_and_resume|ACCEPTED（D-076）；同请求只补未完成站|
|A08 原事实恢复|原Memory/ThinkSession/E5-A|原saved_memory/thinking_saved/restart_completed/real_process_restart；新v1_pending|ACCEPTED（D-076）；不重复调用/效果/扣费/revision|
|A09 完整性/并发|准备快照不可改写；原admission|partial_preparation、forged_success、unbound_completed_result；原concurrent/cross_process_busy|ACCEPTED（D-076）；无第二账本；不宣称生产exactly-once|
|A10 当前门禁|当前来源许可、版本/Context、返回前重查|revoked_permission/revoked_during_query/rechecks_revision/expired_context；原材料门禁|ACCEPTED（D-076）；拒绝且只读零副作用|
|A11 旧调用/隔离|可选内部字段，旧请求保守查询|legacy_partial、v1_pending；原disabled/native/snapshot/protected_fixture|ACCEPTED（D-076）；冻结契约/Authority不变|
|A12/T24/R1 公开只读出口|input_outcome经可信材料核验|partial_public_query_after_local_failure/after_reopen/in_separate_process；重复查询|ACCEPTED（D-076）；可信逐站进度可读，PENDING不假报COMPLETED|

[最终测试索引](test-evidence-index.md)按真实版本绑定。N02回答前自动回忆、N11完整可信吸收等后续内容不因本表验收；W02整体IN_PROGRESS，W02-B/C、W03、P19未开工。历史F1/H1/F2仍UNKNOWN。
