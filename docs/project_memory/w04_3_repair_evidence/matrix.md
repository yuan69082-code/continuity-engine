# W04-3 R1/R2 返修矩阵

现行依据：v1.6 / v1.6 / v6.10 的 W04 第三子批次、N14、T30—T32、T41、C11和适用T18。原N21衔接保持。各条状态IMPLEMENTED_NOT_ACCEPTED；定点及以下最终同版集合已通过，但不等于正式验收。

运行实现仅 `src/continuity_engine/services/temporary_tool_service.py`；新增正式回归仅 `tests/test_w04_3_repairs.py`。不改原测试断言、Scheduler、权限或账本。

| Planning Item | Code Change / 原权威复用 | Test（新文件中test_省略） | Acceptance Result |
|---|---|---|---|
|N14/T31/C11 R1：等待首项不排除后项|RuntimeWork.needs从原Scheduler已收身份中排除重复入队；待入队native与工具按due_at、原priority、identity最多2项|waiting_first_does_not_starve_second_or_native_work；both_native_needs_and_two_tools_obtain_real_dispatch|修前before-02失败；修后targeted-final-01通过，IMPLEMENTED_NOT_ACCEPTED|
|N14/T31/T18 真实认知和维护仍推进|原native.needs、dispatch/query、Wake/Perception/C1、Action/Evolution；不造人格或新任务账本|两项上表用例均有真实宿主tick、Scheduler、业务回执；同时存在认知和维护正向链取得revision变化及一次工具效果|定点通过，待独立复核；不以进程活着代替认知推进|
|N14/T31 缺登录/依赖与可执行事项并存|原Scheduler等待及E5-A父请求；重开按原身份恢复|login_wait_reopen_pause_resume_and_original_identity；dependency_wait_and_pending_cleanup_do_not_block_ready|定点通过；缺条件不新发现，不重复费用|
|N14/T41 UNKNOWN/待清理与其他事项并存|原query查询事实，UNKNOWN不变为未执行；后项正常派发|unknown_first_does_not_block_second_or_replay；dependency_wait_and_pending_cleanup_do_not_block_ready|定点通过，UNKNOWN仍保留|
|N14/T32/T41/C11 R2：已失败三次后仍可合法续清理|advance去永久累计3次限制；每次最多一个清理，自动失败从原回执completed_at退避|three_failed_cleanup_facts_can_resume_via_host；automatic_partial_cleanup_survives_three_failures_and_reopen|修前before-02失败；同反例通过；保留原连接及旧清理记录|
|C11 有界预算与恢复资格分开|cleanup_retry_seconds默认原RuntimePolicy.retry_seconds=5，可配正有限值；原资源/账本不变|cleanup_backoff_is_receipt_bound_readonly_and_configurable；backoff_survives_reopen_without_reset_or_read_side_effect；invalid_cleanup_pacing_is_rejected_without_port_work|定点通过；退避不是永久停止或无限快重试|
|T18 返回丢失/UNKNOWN/已清理幂等|查询原close事实及原成功回执；不重建连接、清空次数或恢复过期使用|cleanup_unknown_and_return_lost_use_original_fact；automatic_partial_cleanup_survives_three_failures_and_reopen|定点通过；历史回执hash保持|
|当前权限、PAUSE/STOP、host/generation、隔离|沿原conditions/current与宿主guard；当前拒绝不新建清理请求|cleanup_revocation_pause_stop_and_other_connection_isolation；current_host_and_scope_denial_prevent_new_cleanup；login_wait_reopen_pause_resume_and_original_identity|定点通过；邻接连接与TEST正式数据替身字节不变，STOP不复活|
|当前Context版本，不偷偷改旧绑定|新use/close必须原C1生成当前Context，旧connect不改；原Action逐步复核|old_context_is_not_rebound_after_native_revision；both_native_needs_and_two_tools_obtain_real_dispatch|定点通过；旧Context拒绝仍有效，不宣称自动重绑|
|原T30/T32/N21及公共链兼容|原46项W04-3、87项W04-1/2、417项公共兼容及完整回归|由validate.py固定顺序，同版证据见test-index.md|未完成集合不可计PASS；最终报告给出实际结果|

原初版矩阵及其旧结论原样保留于[原矩阵](../w04_3_evidence/matrix.md)。当前 `EVIDENCE_CONFLICT=PRESENT`，本轮不自行关闭复核阻断；`PLANNING_CONFLICT=NONE` 表示本次未发现需要更改规划的实际冲突。

## 最终同版验证对应

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-01](targeted-final-01.json) | 14 / 0 / 0 / 0 | 166.421 / 167.125 | 0 |
| [w04-3-final-01](w04-3-final-01.json) | 60 / 0 / 0 / 0 | 324.797 / 325.487 | 0 |
| [w04-12-final-01](w04-12-final-01.json) | 87 / 0 / 0 / 0 | 159.335 / 160.0 | 0 |
| [compatibility-final-01](compatibility-final-01.json) | 417 / 0 / 0 / 0 | 701.162 / 701.916 | 0 |
| [full-final-01](full-final-01.json) | 1922 / 0 / 0 / 1 | 2390.489 / 2391.61 | 0 |

上述组均绑定frozen-source-01.json；集合交叠不相加，原初版结果不替代本轮。尚未独立确认，EVIDENCE_CONFLICT继续PRESENT。
