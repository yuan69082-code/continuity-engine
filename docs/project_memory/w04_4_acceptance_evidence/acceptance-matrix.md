# D-093 正式验收矩阵

Planning Item → Code Change → Test → Acceptance Result。由用户本次正式验收；以下新表不覆盖原初版和返修矩阵。施工方同版实跑引用，规划窗口未独立运行测试。

## W04-4及包级

|Planning Item|Code Change / 原权威链|Test / 已核验证据|Acceptance Result|
|---|---|---|---|
|N15/T33可信身份、群聊、主体回显|cross_entry值对象、Environment原绑定、C1原operation；私聊/群目标与收发账号分开|CrossEntryTests.test_wrong_sender_and_same_display_name_do_not_grant_identity；EntryBoundaryTests群聊/自发回显；W04-1旧身份回归|ACCEPTED；同人绑定不扩大共享|
|N15/T35具体事项、多话题、歧义|CrossEntryService.adopt_matter/item + W03 UnfinishedItem原Action/Evolution；原输入根|ContinuationTests.test_same_user_two_matters_and_ambiguous_reference_stay_separate；DeliveryEvidenceTests事项重开/幂等|ACCEPTED；不自动为每个想法立项|
|N15/T36当前转用、派生材料|EntryPermission、origins、entry_context_source、input_context_source；原Event/ThinkSession/Memory和DeviceCommand根|test_related_native_memory_cannot_bypass_entry_transfer_withdrawal；UI查询允许/撤权双对照；读取回调中绑定变化；重开查询|ACCEPTED；未查到不等于不存在，撤权不删历史|
|N16/T34原生API/UI全链|原P18 Wake/Thinking的ContactIntent、P08/P13确认、C1表达前置、P17设备发送/E5-A|CrossEntryTests API/UI 两条question_followup_reply_same_engine_and_matter；7项EntryExpressionTests|ACCEPTED；Fake模型只证明所覆盖工程链|
|N16/T37技术替代与现实拒绝|EntryDecisionPolicy技术route_available；DeviceOperation原当前/最终权限和Reality|UI全链在API不可用时成功；表达前撤权/权限拒绝零效果；W04-2外部指令与观察原专项|ACCEPTED；被拒绝效果不能借替代路线执行|
|N15/T38三类时间、迟到/镜像/回显|EntryMessage原始时区及不确定性；原消息根和操作去重|ContinuationTests.test_late_timezone_message_preserves_three_times_and_mirror_root；mirror_deduplicates；subject_echo|ACCEPTED；同源不增加独立经历|
|N15/T39、T18并发/恢复|原C1 admission锁、revision、原ThinkSession/operation和E5-A|A/B并发BUSY未提交后原身份续接；test_loss_after_effect_reopens_original_thinking_and_send；原请求重开0新增调用/效果/revision|ACCEPTED；不是生产分布式恢复|
|N16/T40投递事实/UNKNOWN|inspect/delivery_evidence只读原回执/查询；P17独立新询问例外严格绑定|4项DeliveryEvidenceTests；test_native_new_inquiry_can_send_when_original_remains_unknown；unknown_body_effect反例|ACCEPTED；发送不冒充送达已读，UNKNOWN不盲重放|
|N16/T42统一联系暂停、Owner控制|原Environment用户级contact_pause；P17最终控制；原P18|A暂停阻止B；独立native心智推进0效果；Owner PAUSE/STOP与沉默；旧P18全兼容|ACCEPTED；局部现实拒绝不是主体关闭|
|N10/N21、T18/26—32/41/60/72/85—87适用范围及包级|W04前三批原Binding/工具/Body/局部查询 + 新入口接线|W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities；同版W04全专项|ACCEPTED；T66/67仅本批查询契约，不提前实现W05|
|C01—C15、T25/T43/T45|原只读业务记录/权限/成本与源hash；无新页面|inspect重开无推进；包级真实ID与TEST费用；原公共兼容/完整回归|ACCEPTED；完整中文观察页面P19，实际平台P22|
|当前字节/损坏/副本/纯值复用兼容|原environment/SubjectState/Thinking/integration/outbox仓储、temporary_tool_service、action_planning|投影/副本/损坏/值突变、真实junction和元数据权限拒绝新回归；原P03—P18/W02/W03/自主性兼容|ACCEPTED；写入、CAS、权限与数据格式未被缓存替代|

## R1/R2逐项补修

|Planning Item|Code Change|Test / 已核验证据|Acceptance Result|
|---|---|---|---|
|N15/T36：A受限值不能被B末次写入洗去来源|cross_entry_service.scoped_state / _state_lineage / _lineage_node|counterexamples-before-01有效FAIL；test_state_append_withdrawal_*、授权对照、SET；最终Context和实际表达|ACCEPTED|
|N15/C来源：原生及间接状态传递|_fragment_origins / _state_origins / origins；原Event/ThinkSession/历史revision|test_indirect_state_derivation_*、test_native_*；原State保留、重开、正常对照|ACCEPTED|
|N15：合法B材料不被全面屏蔽|当前投影hash校验、仅实际提供的事项来源|test_redacted_matter_does_not_block_independent_b_expression；selected-state-before-05 ERROR与repair-06 PASS|ACCEPTED|
|N16/T42：最后观察后入口权限有效|device_operation_service._current末端delivery_current；原控制文档回调后比对|三种final_observation拒绝及正常1/1对照；原始final guard请求/页面hash、效果/credits记录|ACCEPTED|
|N16/C边界：剩余回调不能绕过暂停|delivery_current最终原控制文档再读|remaining_connection_callback / remaining_permission_callback，零效果与费用|ACCEPTED|
|T18：恢复及独立合法内部认知|原请求/原Event不重建，失效Context仍拒绝|state_query_and_same_request_reopen；transfer撤回后新合法Context，binding/pause原生心智提交|ACCEPTED|
|只读/权限变化|scoped_state回调后重读、原入口拒绝|state_read_binding_change / state_query，模型、效果、费用、revision不推进|ACCEPTED|
|W04包级及公共兼容|两个原补修文件及同职责entry_context_source单分区重验；不缓存授权|同版W04、公共及完整回归；见test-index.md|ACCEPTED|

上表原初版测试在最终修补版W04专项及全量中再次覆盖；不拼接不同源码PASS。当前四组为17 PASS、215 PASS、1144 PASS/1 SKIP、1990 PASS/1 SKIP，均退出0，集合不相加。

W04-1/D-087、W04-2/D-089、W04-3/D-091历史验收不改；W04-4及W04包级ACCEPTED。W05未开工；P19—P23后置能力不冒称完成。

[原初版矩阵](../w04_4_evidence/final-matrix.md) · [原返修矩阵](../w04_4_review_repair_evidence/matrix.md) · [原始测试](../w04_4_review_repair_evidence/test-index.md) · [同版引用核对](test-references.json) · [验收范围与限制](acceptance-report.md)
