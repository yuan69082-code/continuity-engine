# W04-2 实现与兼容边界

## 同一权威链

当前观察携带 AttachmentUse（主体/环境/主机/代次/软件/设备/账号/会话/用途/范围），页/焦点/当前状态、版本与时限。`DeviceCommand` 将观察和意图绑定为原 `ActionSpecification.input_payload` 与 argument_hash。原 E5-A 保存请求、尝试及核验回执；原 Outbox 只保存投递状态。本批没有独立请求、参数或主体账本。

`DeviceOperationService.step` 是正式内部结构化动作入口；`ActionPlanningService.run` 仍校验当前 Context、原可信提案来源、权限、资源、确认和恢复条件。`ExecutionService` 继续现实门禁，新增设备动作在最终检查处核对连接/具体能力/期限/页面/焦点。外部端口事务内再检查一次，模拟控件操作和原生回执原子保存，操作后再次观察。

点击只能产生 CLICKED，定位 LOCATED、输入 TYPED、滚动 SCROLLED；只有可验证后置状态才能称 SAVED/SENT/ACTUATED。固定成功标记不能通过结果核验。结果未知保留原请求，查询优先；取消不会擦除已经发生的事实。

`perceive_sensor` 校验 Body binding、输入能力、单位/范围/采样/当前权限和 Context revision，然后调用原 `PerceptionService`。模拟硬件事实明确 TEST_SIMULATED/BODY_OBSERVATION；Somatic和Dream不能进入硬件通道。传感可配置新鲜度默认30秒，仅本批内部端口配置，不是生产策略或运行时限。

UI 历史查询使用原 `HistoryScope`，明确对象/软件/设备/会话/时间/来源/权限/意愿；只返回限定范围材料。结果是 SIMULATED_RESULT_OBSERVATION，经原 ExecutionContextSource→Router→Composer；同根重读按原根标记，不把两个查询回执变成两个独立依据。当前撤权、失效、断线、更正会令该设备候选退出当前版本；旧回执仍可核实，不能据此重新消费。存档损坏、未知端口错误仍明确失败，不被“来源不可读”分支吞掉。

## 公共影响

1. ActionSpecification：已有外部查询/普通动作字节格式不改；新增 `device.*` 内部可选参数分支（带版本、严格形状和hash）。没有正确设备参数拒绝。
2. ExecutionService：只有设备动作需要 DeviceOperationService。普通P17路径仍原样校验。设备已撤回候选从 Context 源剔除，原回执与尝试不删除；未知损坏不静默跳过。
3. ExecutionContextSource：只有设备历史查询继承外部历史原根；其他结果仍沿原执行事实根。

新端口不保存原始凭据，复用P16/P17完整材料检测和静态外部异常边界。模拟装置自身状态是隔离的外界替身，不持有Subject、人格、关系或Memory。真实硬件及任意生产平台的原子性不在本批证明范围。

## 后置与限制

- 支持的模拟控件明确限定为编辑/保存/发送、滚动、定位和局部历史页；不是任意软件通用视觉能力。
- 同一模拟身体演示位置传感/移动。感知不会自动写成SubjectState；成功回流后的更新仍经过Thinking/Action/Evolution。
- W04-3自主发现、W04-4跨入口整体续接、W05自然记忆/情绪/再理解/梦、P19页面及P20—P22生产能力未施工。
- 断线或不可读材料影响对应任务/候选；不新增运行期限、固定思考次数或静默退出规则。
