# W02-A 输入、处置及恢复边界

这是 W02-A 工作区实现说明，尚未正式验收。完整 W02 的自动回忆、外部资料可信吸收和包级贯通留给后续子批次；原 W01 结论及新版规划副本未覆盖。

## 正常入口

在原 `build_continuity_core` 的 `ContinuityCoreGates(input_processing=True)` 下启用。默认 False 保持原调用行为；并非另起一条测试专用业务链。原 `IntegrationAdapter.submit` 仍承担格式、身份、版本、请求哈希和恢复；W02 启用时在首次操作写入前复用 P16/P17 材料检查。

`PerceivedPlatformFact` 原文和发生/观察时间不改写。新增解释只包含有限语法标记、来源身份、哈希和跨度：否定、愿望、转述、他人、历史时间、假设、不确定性。它不是事实，不是用户授权，也不是全面自然语言理解。无可靠信息时不猜造对象或精确日期。普通心理内容照常处理。

当前消息来源用原 LOCAL_FACT 分区及 `RETRIEVED_CANDIDATE` 权威级别进入 Router/Composer，再进入原 Thinking。LOCAL_FACT 是分区名，不代表事实可信。来源版本/哈希、现有候选/精确引用许可、Context 时效和预算仍检查；不能标成 CONFIRMED_STATE 来获得预算保护。未被选择或被预算裁剪时，明确 NOT_ADOPTED，不能声称 Composer 已提供完整消息。

注意：本批没有重写旧 Perception 的原始事实快照；Composer 的预算是其自身材料预算，不宣称替所有旧 Provider 重新定义整个请求的输入预算。

## 站点与 Authority

| 站点 | 本批处理 | 结果证明 |
|---|---|---|
| 会话 | 临时提供当前消息，或明确未选中/裁剪/失败等待 | 原 Context 片段身份，不是 Trace 自称成功 |
| 记忆 | 对有关消息核实既有 Event/Memory；没有合法事件证据则待证据 | 原 Memory 历史的 ID、revision 和完整内容哈希；不创建替代事实 |
| 核实 | 转述、假设、他人或不确定表达标为待证据 | 静态理由和原输入绑定；不自动选赢家 |
| 原心智/成长 | 仍由原 Thinking/Action/Evolution 处理；只读出口引用原结果及实际 update ID | 未提交是候选或提案，已提交必须有原 Evolution 事实；不把内部成功说成表达成功 |

单纯消息不会被包装为可信 Event。旧 C1 对既有真实 Event 的巩固继续运行；它与“这条消息已记住”分开。认识、事项的 W03 新语义未实现，不能用站点名称冒充已经完成。

`NEEDS_EVIDENCE` 是本轮“尚无充分依据”的真实处置，不是假称记忆成功，也不启动另一条后台循环。原请求成功重放不擅自改写这项历史结论；之后的合法新材料仍经原链处理。跨请求自动关联新证据、回答前回忆及完整外部吸收留后续子批次。本批的自动局部续接针对失败或尚未完成的步骤。

`InputProcessingRecord` 附在原 operation 的 domain progress；原文仍属于原 Perception/ThinkSession 快照，结构记录不再复制一份正文。已启用的请求由 operation 开关、输入 manifest、C1 Context hash、ThinkSession 原快照交叉绑定。旧格式省略新字段，保持旧序列化；新请求不能删字段假装旧格式。

内部处置版本为 `w02-input-v1`，原 operation journal 外壳仍为 v3，以显式可选字段绑定启用请求。这里的兼容是新代码读取原旧记录、关闭开关维持旧序列化；不承诺旧二进制可以读取新启用记录，也不允许两个不同版本宿主混写同一根。未迁移或初始化正式数据，软件版本仍为 0.1.0。

## 局部失败与恢复

站点收据按原 operation 追加；只允许失败等待站继续追加，成功站不能改写或重复执行。记忆局部失败时仍记录可独立完成的会话/核实站，但本轮不假报整体完成。恢复只补失败或未完成站，已有记忆提交按原 Consolidation 身份查询。保存成功但返回丢失不重复写 Event、Memory、ThinkSession、效果或 revision。

重放除检查 journal 顺序外，还核实真实 Context 片段、Memory 历史、ThinkSession 和原 Action/Evolution/E5-A 回执。日志里的自洽哈希不是业务事实证明。原 UNKNOWN 查询及当前授权/时效规则保持；历史事实恢复不自动变为新执行许可。

正常本机并发使用同一 journal 身份的短时 admission：线程锁加复用原 OS 锁原语，有界忙拒绝，释放后可提交或重放。系统 Temp 中只有无业务内容的锁字节，崩溃关闭句柄即释放；它不是第二请求账本、状态权威或生产分布式锁。未协作的旧进程不能因此被宣称获得跨进程写安全；不支持用两个不同版本宿主同时写同一正式主体。本批只验证明确隔离 TEST 的协作入口，不开放生产。

P01 Snapshot/Branch 包含原 operation 中的新增进度，仍是测试/研究机制。锁路径按数据根身份区分，不作为业务快照数据。没有新增 Runtime、后台服务、自动重启或主体寿命限制。

## 可检查入口

- `IntegrationAdapter.service.input_outcome(request_id)`：只读结构视图；返回前复查许可和 operation 身份，不调用模型、不学习、不推进 revision。
- 原始消息链：`python -B -m unittest tests.test_w02_input_processing tests.test_w02_input_recovery tests.test_w02_input_integration -q`。
- 跨进程 Golden：`python -B -m continuity_engine.testing.w02_input_fixture --root <独立系统 Temp 子目录> --phase prepare`，随后同根 `--phase resume`。第一步明确注入已发生效果后中断，第二步验证原事实恢复；不是生产启动方法。

正式删除、实验转正、运行权转交、真实服务和私有页面仍按现行规划分阶段处理，本批不提前开放。
