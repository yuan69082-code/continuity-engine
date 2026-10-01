# W04-4 实际文件职责与公共调用影响

本表解释本批增量，不替代逐文件 hash 清单。实现已冻结，结果以最终测试索引为准；所有旧正式测试文件保持原字节。

| 实际路径（相对仓库） | 变更职责 | 公共调用方 / 保留规则 |
|---|---|---|
|src/continuity_engine/domain/cross_entry.py（新增）|入口绑定、消息来源、主体联系意图、三类时间与版本校验|内部值对象；账号同名不建立身份，消息与主体现实效果分开|
|src/continuity_engine/services/cross_entry_service.py（新增）|可信入站、事项来源接续、当前转用、投递绑定及只读证据投影|原C1、W03、P13/P17/E5-A；不建第二请求/结果账本|
|src/continuity_engine/services/entry_context_source.py（新增）|原SubjectState针对当前入口的授权投影|原Router/Composer；不存第二主体状态，不改未变字段版本|
|src/continuity_engine/domain/integration_results.py；domain/thinking.py|内部可选entry_record/ContactIntent|原operation与ThinkSession仍为权威；未启用旧格式保持|
|src/continuity_engine/domain/device_operation.py|发送命令携带原入口/事项/询问绑定|原DeviceCommand观察及P17动作路径，非另建发送服务|
|src/continuity_engine/services/continuity_core_service.py；continuity_core_runtime.py|可选入口接线、原生Wake/Thinking接续、准备阶段受控读取范围|旧默认路径不开启入口选择策略；原Scheduler/两need/生命周期保留|
|src/continuity_engine/services/continuity_interaction_service.py；expression_policy_service.py|用户明确批准的相关C1先表达核验再投递，以及当前精确确认判定|原P13拒绝/历史核验/独立内部提交不取消，不把旧拒绝升级|
|src/continuity_engine/services/device_operation_service.py；execution_service.py|原P17当前/最终联系边界、可靠独立新询问与原UNKNOWN发送区分|非联系效果不能使用例外；原费用、回执、取消、恢复规则保留|
|src/continuity_engine/services/environment_access_service.py；storage/json_environment_repository.py|原环境配置中保存入口绑定/用户级联系暂停；同次核验减少重复构造|回调后读取当前文档并核对绑定/控制；每次路径/当前字节检查，不缓存授权|
|src/continuity_engine/services/input_context_source.py；execution_context_source.py|输入/查询源追溯与入口专用有界候选选择|原Router/Composer、当前权限、源版本、指定回执及2048预算；索引非事实|
|src/continuity_engine/services/unfinished_item_service.py|新入口原input根的合法来源支持|原W03事项集合/Action/Evolution，旧调用不新建门槛|
|src/continuity_engine/services/temporary_tool_service.py|投影原工具类型请求；一次事实核验返回匹配payload，去除嵌套重复读取|W04-3公开查询/读取仍重查当前事实与资格；R1/R2公平和清理续做不变|
|src/continuity_engine/storage/json_integration_repository.py|当前字节完整验证原operation/E5-A；复制前选取必要投影|未选中坏记录仍拒绝；原写入、身份、事实不变，副本不共享|
|src/continuity_engine/storage/json_repository.py；json_thinking_repository.py|准备阶段受控解析/投影复用，当前字节完整验证和独立副本|原SubjectState和ThinkSession写入/事务/CAS/revision语义不变|
|src/continuity_engine/storage/json_execution_outbox.py|同次安全路径检查去除重复系统读取|原Outbox资格、路径限制和事实不变|
|src/continuity_engine/domain/action_planning.py|一次准备内纯值digest计算复用，逐次读取当前值形成键|原RFC8785算法/无效值拒绝保持；不缓存授权或对象身份，旧默认不启用|
|src/continuity_engine/testing/w04_cross_entry_fixture.py（新增）；testing/w04_device_fixture.py；testing/w04_tool_fixture.py|确定性模型、隔离API/UI外界、同原权威的工具/身体组合|只提供TEST外界与模拟结果；SimulatedConnections仍读取当前字节、完整校验、独立副本|
|tests/test_w04_4_continuity.py、test_w04_4_expression.py、test_w04_4_boundaries.py、test_w04_4_delivery.py、test_w04_4_continuation.py、test_w04_package.py（6个新增文件）|52项正常/拒绝/恢复/只读/包级正式回归（原49及最终全量后增加的3个存储边界对照）|原1923身份和原测试文件/断言不改；不是生产或任意语言质量验收|

原Body、工具发现、Owner控制、Resource、Memory/Event/Learning/Evolution职责复用。未新增生产端口、后台服务、ACL变更或真实凭据。精确差异与来源hash由终局清单核对，旧档案/失败输出原样保存。

2026-10-01全量后补修仅追加到上表既有两个职责：Environment每次原生查询当前reparse属性，来源追溯先投影必要根字段再复制。完整字节校验、当前权限、写入及账本格式不变。代码与原始证据见[最终超时调查](final-timeout-investigation-02.md)。
