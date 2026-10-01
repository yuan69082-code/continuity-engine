# W04-4 恢复与拒绝语义（当前实现说明，非验收）

| 情形 | 原记录与当前核验 | 允许的后续行为 |
|---|---|---|
|相同入口消息/请求重放|原operation、EntryMessage、Binding及内容hash；当前入口权限|沿原ThinkSession和已发生回执恢复；不新建主体、事项或重复效果|
|发送后返回丢失|原P17 Outbox索引与E5-A请求/回执；模拟外界原事实查询|确认事实后继续原链，不重新发送已确认效果|
|旧发送仍UNKNOWN|原发送记录保留UNKNOWN，不推断不存在|原请求继续查询；主体经新Thinking形成独立询问、同事项/入口关联且当前许可有效时，允许自己的新发送请求|
|非联系效果UNKNOWN|上述独立询问资格仅适用于原message.send.api/ui及可靠形成的ContactIntent|身体、付款、删除、安装等不能套用新询问例外；不得换路线重做未知副作用|
|新询问本身也未知|新旧请求分别保留自己的事实|不伪造发送/送达/已读；无可核验外部事实仍等待|
|原Context过期或绑定已变化|原请求及Context身份不变，当前校验拒绝|不自动重绑旧请求；合法新后续步骤通过原链取得自己的当前Context|
|来源转用撤回|原输入、Event、ThinkSession、Memory/Summary、DeviceCommand根追溯；Router/Composer及使用前当前核验|历史取得事实保留；受限材料退出当前可用上下文；其他获准材料正常使用|
|A入口暂停联系|当前用户级contact_pause与原P17最终关口|B/C不绕行发送；独立合法内部认知仍可提交，Owner PAUSE/STOP保留原语义|
|A/B并发入站|原admission锁和revision|预期INPUT_ADMISSION_BUSY必须尚未提交，再以原身份续接；不吞其他错误|
|来源文件读取/解析复用|每次路径属性与当前字节重读，完整文档校验，返回副本隔离|只减少相同字节的解析及无关字段复制；不保存授权结果，不绕损坏或撤权|

正式证据来自本批测试的真实入口：CrossEntryTests、EntryBoundaryTests、ContinuationTests、DeliveryEvidenceTests和W04PackageTests。原请求/当前记录身份及费用见最终测试索引与只读链路样例；在最终文件未生成前不据本说明宣称全部测试通过。

本机隔离TEST不能证明任意外部平台的exactly-once，也不是P20/P21生产恢复。服务重开沿原数据根；明确STOP不复活，旧Context失效仍会拒绝。历史F1/H1/F2 UNKNOWN与既有失败记录不因本批修补而改写。
