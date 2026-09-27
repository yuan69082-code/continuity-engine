# W04-1 正式入口和只读查看示例

以下均为隔离 TEST 例子，实际可复核步骤在 `tests/test_w04_1_environment.py`。它们说明数据如何走原入口，不声称真实设备或外部账号已连通。

1. TEST 主体原 Genesis 与 Subject Binding 不变。`JsonEnvironmentRepository.register` 保存一条 `MESSAGE_INGRESS` 连接：主体、环境、宿主、通道、软件、设备、账号、会话、用途与有效代次同时绑定。仅“听说有入口”或“发现入口”不授予接收权。
2. 原 `ContinuityInteractionService.submit(payload, access_use=...)` 的**内部入口**接受未改格式的 v1 原始消息，在 W02 输入处理、operation journal 和 Wake 的第一次写入前检查现行连接、期限、授权和完整绑定；通过后仍由原 W02 入站、Perception、Router/Composer 与 E5-A 继续。重复同一请求使用原回执，不制造第二事实。错误账号、跨主体、断线或撤权在本入口被拒绝且 TEST 根零写入。受保护的正式适配器接口保持原样；W04 后续批次再处理真实软件接入。
3. 模拟身体的 `SensorObservation` 带 `BODY_OBSERVATION`、主体/环境/设备、代次、能力、单位、采样时间及数值。`EnvironmentAccessService.validate_sensor` 检查现行授权、连接、能力单位与范围；`0` 是合法测量，`None` 是未知。`INTERNAL_SOMATIC` 和 `DREAM_SIMULATION` 不冒充硬件来源。完整 Fake Body 感知→Perception 及动作→结果闭环留 W04-2。
4. TEST 的动作仍由原 P17 `ExecutionService`、世界边界和 E5-A 执行；附加的 `AttachmentUse` 在最终同步投递检查中核对身体/工具身份与路由。原 Fake World 成功一次产生一次效果和扣费，同请求重放沿原事实；现实授权回调期间撤销附加资格则零新增效果。
5. `EnvironmentAccessService.snapshot/body_state` 先要求只读授权，返回当前连接状态，不赋予使用权。`ScopedHistoryService.query` 用有范围的 `HistoryScope` 经原 Router/Composer 取**候选引用**及版本/hash；当前来源或权限不满足时返回阻断或拒绝。查询无模型、学习、动作和 revision 写入。深层归档或外部考证仅在意愿或明确请求存在时可提出，现阶段返回 `DEPENDENCY_MISSING`。

隔离迁移测试使用 `prepare_migration` 的清单、缺项和时间来源引用，`handoff_isolated` 使旧宿主 generation 失效并在重开后保留；P20/P21 的生产迁移、备份恢复和真正运行权交接仍未就绪。
