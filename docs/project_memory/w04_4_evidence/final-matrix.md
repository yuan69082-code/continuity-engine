# W04-4 与包级最终逐项矩阵

每行都是 IMPLEMENTED_NOT_ACCEPTED，不是用户验收。以下为冻结版本施工实跑；开工/中间矩阵保留在 matrix.md，原待批准冲突已获用户决定并落实，EVIDENCE_CONFLICT仍PRESENT等待复核。

| Planning Item | Code Change / 既有权威入口 | Test（正式方法/模块） | Acceptance Result / 边界 |
|---|---|---|---|
|N15/T33可信身份、群聊、主体回显|cross_entry值对象、Environment原绑定、C1原operation；私聊/群目标与收发账号分开|CrossEntryTests.test_wrong_sender_and_same_display_name_do_not_grant_identity；EntryBoundaryTests群聊/自发回显；W04-1旧身份回归|IMPLEMENTED_NOT_ACCEPTED；同人绑定不扩大共享|
|N15/T35具体事项、多话题、歧义|CrossEntryService.adopt_matter/item + W03 UnfinishedItem原Action/Evolution；原输入根|ContinuationTests.test_same_user_two_matters_and_ambiguous_reference_stay_separate；DeliveryEvidenceTests事项重开/幂等|IMPLEMENTED_NOT_ACCEPTED；不自动为每个想法立项|
|N15/T36当前转用、派生材料|EntryPermission、origins、entry_context_source、input_context_source；原Event/ThinkSession/Memory和DeviceCommand根|test_related_native_memory_cannot_bypass_entry_transfer_withdrawal；UI查询允许/撤权双对照；读取回调中绑定变化；重开查询|IMPLEMENTED_NOT_ACCEPTED；未查到不等于不存在，撤权不删历史|
|N16/T34原生API/UI全链|原P18 Wake/Thinking的ContactIntent、P08/P13确认、C1表达前置、P17设备发送/E5-A|CrossEntryTests API/UI 两条question_followup_reply_same_engine_and_matter；7项EntryExpressionTests|IMPLEMENTED_NOT_ACCEPTED；Fake模型只证明所覆盖工程链|
|N16/T37技术替代与现实拒绝|EntryDecisionPolicy技术route_available；DeviceOperation原当前/最终权限和Reality|UI全链在API不可用时成功；表达前撤权/权限拒绝零效果；W04-2外部指令与观察原专项|IMPLEMENTED_NOT_ACCEPTED；被拒绝效果不能借替代路线执行|
|N15/T38三类时间、迟到/镜像/回显|EntryMessage原始时区及不确定性；原消息根和操作去重|ContinuationTests.test_late_timezone_message_preserves_three_times_and_mirror_root；mirror_deduplicates；subject_echo|IMPLEMENTED_NOT_ACCEPTED；同源不增加独立经历|
|N15/T39、T18并发/恢复|原C1 admission锁、revision、原ThinkSession/operation和E5-A|A/B并发BUSY未提交后原身份续接；test_loss_after_effect_reopens_original_thinking_and_send；原请求重开0新增调用/效果/revision|IMPLEMENTED_NOT_ACCEPTED；不是生产分布式恢复|
|N16/T40投递事实/UNKNOWN|inspect/delivery_evidence只读原回执/查询；P17独立新询问例外严格绑定|4项DeliveryEvidenceTests；test_native_new_inquiry_can_send_when_original_remains_unknown；unknown_body_effect反例|IMPLEMENTED_NOT_ACCEPTED；发送不冒充送达已读，UNKNOWN不盲重放|
|N16/T42统一联系暂停、Owner控制|原Environment用户级contact_pause；P17最终控制；原P18|A暂停阻止B；独立native心智推进0效果；Owner PAUSE/STOP与沉默；旧P18全兼容|IMPLEMENTED_NOT_ACCEPTED；局部现实拒绝不是主体关闭|
|N10/N21、T18/26—32/41/60/72/85—87适用范围及包级|W04前三批原Binding/工具/Body/局部查询 + 新入口接线|W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities；同版W04全专项|IMPLEMENTED_NOT_ACCEPTED；T66/67仅本批查询契约，不提前实现W05|
|C01—C15、T25/T43/T45|原只读业务记录/权限/成本与源hash；无新页面|inspect重开无推进；包级真实ID与TEST费用；原公共兼容/完整回归|IMPLEMENTED_NOT_ACCEPTED；完整中文观察页面P19，实际平台P22|
|当前字节/损坏/副本/纯值复用兼容|原environment/SubjectState/Thinking/integration/outbox仓储、temporary_tool_service、action_planning|投影/副本/损坏/值突变、真实junction和元数据权限拒绝新回归；原P03—P18/W02/W03/自主性兼容|IMPLEMENTED_NOT_ACCEPTED；写入、CAS、权限与数据格式未被缓存替代|

方法全名、精确身份与执行结果以 frozen-source-final-02.json 和 test-index.json 为准，表中短名便于查阅；不增加新的测试数量。全矩阵共同绑定 final-report.md 的最终源码。
