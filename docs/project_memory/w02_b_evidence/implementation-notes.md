# W02-B 实现与恢复说明

这是 D-077 授权的 W02 子批次，尚未验收。W02-A 的输入与回执、P00—P18 已验收历史不变；W02-C、W03 和 P19 未启动。

## 正常入口和实际处理

原 `build_local_integration_app` 的 `continuity_core_factory` 使用原 `build_continuity_core`，设置 `ContinuityCoreGates(input_processing=True, automatic_recall=True)`。不是另外建立一条测试业务链。保留旧开关和旧请求的序列化与恢复；未启用本批开关的请求保持旧路径，不偷偷改写旧请求的绑定。

原始消息经过入站校验、Perception 和 W02-A 逐站处理后，在 `ContinuityCoreService.prepare` 内完成本批评估和来源组装，再交给原 Thinking。主动认知沿同一个 C1 准备入口，根据原内部关注评估，不制造用户消息。原 P18 的持续运行、局部等待和控制语义不变。

`AssociativeRecallService` 只协调原 Router/Composer。有界解释分清报告对象、进食/意愿/否定/引用和历史时间；支持本批受控进食表达、午餐/午饭、用餐及螺丝粉/螺蛳粉变体。不可靠的语法保留不确定性；这是局部工程规则，未宣称通用中文理解或真实模型的语义能力已经验收。未知主题仍是低确定性的候选检索，不能产生偏好证据。

相关的 Memory、Timeline、DerivedSummary 走原来源端口。临时旧消息从原 operation journal 取可核验引用，只有有界的相关窗口进入 Context；没有另建聊天、人物或请求权威。原 JSON 仓储读取仍需完整校验原存储文档，这是当前实现的 I/O 局限，不等于把全量聊天塞给模型。一次调用内复用已验证材料，权限之后再次读取核验，不跨请求缓存授权。

首轮全量曾发生T04准备超时，不能用前面专项通过掩盖。首轮后的第一步修补去掉历史resolver的重复前置读取，并把候选逐条重复日志解析合并为“同批原记录逐条授权、所有授权后完整再读比较”。任一参与记录变化或根材料撤销立即拒绝。当前输入仍保持原授权前后读取；不是跨请求缓存。[真实失败、单次测量与修补范围](full-timeout-investigation.md)。

默认候选总预算60、单轮20、关联轮次上限4、时延1000毫秒、原 Composer 输入预算900；均通过原 C1 的 policy/budget 选项配置。候选总量沿用 P05 的30—80范围，不改旧契约。四轮是当前配置，不是永久能力上限。足够材料、没有新关系、重复关系、相关性不足、检索/关联预算耗尽分别停止。超时或来源不可用阻止新 Thinking；不会把失败说成没有历史。

recall记录中的 `model_calls=0`、`external_calls=0` 只统计本地回忆准备本身，并不声称整轮回应没有模型消耗。随后Thinking及行动仍按原usage/回执账本核算；跨进程用例另核对实际模型调用、效果和credits，不建立新的费用账本。检索量是候选量，原JSON完整性读取的底层I/O未冒称为只读了同样数量的磁盘条目。

原 Composer 仍负责权威分层、必要主体核心保留、去重、冲突标记和裁剪。当前输入、相关旧报告与记忆优先于不相关的可选状态材料；P14 所需内部心智输入仍保留。时间在材料中注明为**来源时间**，不偷推实际事件时间；12点与15点的报告只能给出相应时间关系，不能确定主体不饿。召回不会强迫表达或现实行动。

## 候选偏好与后续阶段边界

T04 使用原 P04 的可追溯 DerivedSummary 生成未确认候选视图。它只采用当前可读、有效且与原入站身份/内容匹配的独立 Event 根对应 Memory；同一消息重放、同一根的摘要和派生材料不增加独立根。纯输入不因被看到就成为已验证经历。

候选规则记录在 policy 和原操作回忆记录中：默认至少3个独立根并有积极报告；可注入其他明确规则。负面反例单列；即使达到规则，仍为 `UNCONFIRMED_CANDIDATE`、`confirmed=False`、`DERIVED_CANDIDATE_NOT_FACT`。没有把数字门槛写成“必然喜欢”，没有自动写 Trait/SubjectState，也不伪造 P15 的结构化学习确认。W03 的完整长期认识、反例更新与正式确认不在本批施工；本批的候选视图不能替代它。

## 原记录、失败和恢复

原 operation journal 增加可选 `recallEnabled` 和 `recallProgress`，原 Context 增加可选 recall。记录绑定 request/operation/subject/environment/perception/policy/snapshot hash；旧格式不增字段。失败追加 BLOCKED，完成准备记录与原输入准备 checkpoint 同次保存。它是原请求的准备证据，不是第二执行账本。

准备返回丢失后复用原 READY checkpoint；来源、权限、生命周期、revision、Context 时效仍按当前条件核验。不能把旧 hash 自洽当作授权。能力结果和历史效果继续由原 E5-A 独立回执核实，不盲重发 UNKNOWN。原成功事件、模型调用、效果、扣费及 revision 不因回忆恢复重复。

撤销、更正、P12停用/归档/删除通过原 Memory/Timeline 状态和版本传播，历史输入引用也必须经过当前根材料可用性检查，不利用旧输入副本绕过禁用根。

## 最小只读查看

正式内部入口是同一已装配 Engine 的 `app.adapter.service.recall_outcome(request_id)`。它读取原记录，重新核对授权、原材料、版本、Context 和 ThinkSession 绑定；不调用 Router检索、模型、学习或业务提交。返回 READY/BLOCKED/待准备及原结构证据，不能把总流程尚未完成说成完成。旧 Context 已过期或来源已经失效时明确拒绝当前可消费结果，不偷偷刷新。

独立 TEST 跨进程演示：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'
# root 必须是独立且初始为空的 Temp TEST 目录，绝不能是正式数据目录。
& 'E:/Adobe/python.exe' -m continuity_engine.testing.w02_recall_fixture --root '<独立Temp目录>' --phase prepare
& 'E:/Adobe/python.exe' -m continuity_engine.testing.w02_recall_fixture --root '<同一Temp目录>' --phase resume
& 'E:/Adobe/python.exe' -m continuity_engine.testing.w02_recall_fixture --root '<同一Temp目录>' --phase show
```

prepare 控制注入一次效果返回丢失；resume 是新进程复用原事实；show 为只读查询。它不是 P19 页面，不启动常驻实例，也不开放生产入口。自动测试在各子进程退出后只回收自建临时根。

完整测试与源码绑定见最终报告和测试索引。历史 F1/H1/F2 的 UNKNOWN 不因本批测试而改变。

## 准备内的解析复用与语义范围补修

JsonIntegrationResultLedger的可选私有scope仅由本批Recall.prepare进入：每次读取仍取当前原文件字节，相同且已完整验证时才复用解析，返回独立深拷贝；字节和解析对象成对绑定。scope退出即清除，旧调用不启用，没有授权缓存、持久索引或另一权威。全量再次超时与剖析定位、两轮调整、拒绝和隔离回归原样归档，详见full-timeout-investigation.md。

普通偏好不再作为meal事件线索；明确进食谓词才启用进食关联理由。偏好仍是候选报告，同对象旧进食可以召回，但不证明当前已吃。负面、引用、他人、愿望和历史时间的原边界保留。所有结果须以最终04源码对应实跑为准。

最终04输入投影在完整原日志校验之后才构造，仅为读取输入，不含无关旧回应Context；当前文件字节改变仍重新验证全部原记录。投影无保存接口，返回副本与缓存、原存档相互隔离。`SHARED_EVENT`表示同类进食报告的关联理由，不证明两条报告是同一个已经发生的客观事件；modality、报告人、来源时间及非事实标记继续保留。
