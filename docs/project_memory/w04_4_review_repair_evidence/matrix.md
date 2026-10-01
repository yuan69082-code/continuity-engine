# 两项定点返修逐项矩阵

全部Acceptance Result均为IMPLEMENTED_NOT_ACCEPTED，等待独立复核；EVIDENCE_CONFLICT=PRESENT，不登记用户验收。现行v1.6/v1.6/v6.10，沿D-092。

|Planning Item|Code Change|Test / evidence|Acceptance Result|
|---|---|---|---|
|N15/T36：A受限值不能被B末次写入洗去来源|cross_entry_service.scoped_state / _state_lineage / _lineage_node|counterexamples-before-01有效FAIL；test_state_append_withdrawal_*、授权对照、SET；最终Context和实际表达|IMPLEMENTED_NOT_ACCEPTED|
|N15/C来源：原生及间接状态传递|_fragment_origins / _state_origins / origins；原Event/ThinkSession/历史revision|test_indirect_state_derivation_*、test_native_*；原State保留、重开、正常对照|IMPLEMENTED_NOT_ACCEPTED|
|N15：合法B材料不被全面屏蔽|当前投影hash校验、仅实际提供的事项来源|test_redacted_matter_does_not_block_independent_b_expression；selected-state-before-05 ERROR与repair-06 PASS|IMPLEMENTED_NOT_ACCEPTED|
|N16/T42：最后观察后入口权限有效|device_operation_service._current末端delivery_current；原控制文档回调后比对|三种final_observation拒绝及正常1/1对照；原始final guard请求/页面hash、效果/credits记录|IMPLEMENTED_NOT_ACCEPTED|
|N16/C边界：剩余回调不能绕过暂停|delivery_current最终原控制文档再读|remaining_connection_callback / remaining_permission_callback，零效果与费用|IMPLEMENTED_NOT_ACCEPTED|
|T18：恢复及独立合法内部认知|原请求/原Event不重建，失效Context仍拒绝|state_query_and_same_request_reopen；transfer撤回后新合法Context，binding/pause原生心智提交|IMPLEMENTED_NOT_ACCEPTED|
|只读/权限变化|scoped_state回调后重读、原入口拒绝|state_read_binding_change / state_query，模型、效果、费用、revision不推进|IMPLEMENTED_NOT_ACCEPTED|
|W04包级及公共兼容|两个原补修文件及同职责entry_context_source单分区重验；不缓存授权|同版W04、公共及完整回归；见test-index.md|IMPLEMENTED_NOT_ACCEPTED|

修前5 FAIL含辅助问题，不能称五个Engine缺陷；具体分类见repair-progress.md。旧规划/旧失败/历史验收原样保留。下一步仅独立复核与用户决定。
