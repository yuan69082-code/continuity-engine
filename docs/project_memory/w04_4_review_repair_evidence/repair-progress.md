# D-092 独立复核意见返修进度

## 已证实及辅助问题（2026-10-01）

原规划窗口材料是静态复核，不是其运行的FAIL。施工窗口基线331项/63b8189d…、原402成果、70保留、63保护、7正式、3规划和暂存区已实时核对，见baseline.json；原全量1974 PASS/1 SKIP原件不改写。

counterexamples-before-01：7项，2 PASS、5 FAIL、0 ERROR，退出1，46.543秒unittest/47.199秒控制器。两个正常对照通过。两条列表来源反例在最终Context与真实模拟表达均出现A私有标记；B合法标记也在，原State历史保留。最后观察撤转用和联系暂停均记录实际效果1、credits1。

五条失败不等于五个缺陷。其中绑定用例未进入预定关口：私聊契约要求user_account与recipient_account相等，辅助用例只改了后者，原接口正确拒绝。修正新增测试的合法输入为两个账号字段配套变化；binding-before-02命中port事务中final guard的最后观察，页面/附件不变，效果1、费用1、revision 2→3，有效FAIL。原辅助失败未删除或改写。

## 具体修补依据与范围

R1：原scoped_state按整个字段最后写入C1入口过滤，APPEND保留的A值被B末次写入重新标为B；原生更新没有C1映射又被跳过，origins没有engine.subject-state分支。修补在cross_entry_service内只读重建原StateUpdateRecord.changes逐值来源，保留相同值旧源，以原ThinkSession实际选入的Context片段及历史revision追溯间接来源。只构造本次读取投影，不写第二份状态、来源账本或权限缓存。列表按值筛选；被预算压缩的结构化字段无法细分证明时保守保留字段全部来源。原历史和当前权威State不删除。

R2：原DeviceOperation在observe前核验入口，后续附件检查不能证明入口read_from、绑定、联系暂停仍有效。在原port事务final guard中，observe/connection回调后再次delivery_current；该检查全部回调后重读原环境控制文档，发生变化即拒绝。权限未变时仍走原P17/E5-A发送。只覆盖同步回调与隔离端最终派发窗口，不宣称任意生产并发撤权保证。

运行修改限定services/cross_entry_service.py、services/device_operation_service.py；新增tests/test_w04_4_review_repairs.py。旧正式测试不改。原1000ms、2048、调度、权限、费用、回执与UNKNOWN规则不改。

## 首次修后验证及测试语义澄清

counterexamples-repair-01：7项6 PASS/1 FAIL，退出1，64.84秒控制器；运行前后源码53394918…相同。R1两反例和正对照通过；R2绑定、暂停为效果0/费用0、revision正常推进。撤转用已效果0/费用0，但旧Context随后正确报C1_CONTEXT_STALE_OR_UNAUTHORIZED，新增测试要求该旧Context继续推进revision不符合用户明确保留的旧Context拒绝规则。

因此保留这次失败，修正本轮新增验证：仍断言最后关口效果/费用0；旧Context不偷偷重绑；另以B新原始消息取得当前合法Context，通过原链证明独立内部认知可提交。没有修改任何既有正式断言或运行语义。绑定/暂停仍直接验证原轮独立心智推进。

下一步补查原生/间接来源、SET保留值、重开、剩余回调和只读查询边界；随后冻结最终源码，定向、W04、公共兼容及一次全量。未完成不预填PASS，不引用旧版通过覆盖新修补。IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT；不验收、不写Git、不W05；F1/H1/F2 UNKNOWN保持。

## 扩展验证归因

lineage-and-guard-02：11项7 PASS/2 FAIL/2 ERROR，退出1，102.336秒控制器。两个原生辅助反例未产生预期judgments：诊断native-diagnostic-01/02证实ThinkSession已提出更新，但TEST表达声明SILENCE同时should_wait=False使既有CoreDecisionPolicy选expression.emit，原混合轮次正确仅保留独立mind更新。本轮新增夹具改为一致的SILENCE/should_wait=True，不改运行策略。

另两ERROR分别为来源不可用与新六轮SET场景回忆超时。来源不可用来自补修在状态候选授权中又将已按权限过滤的item_records展开为完整来源；重复全历史展开也增加耗时。修正同一cross_entry_service职责内的重复检查：scoped_state已经逐值检查当前许可，候选继续核对该当前投影hash，后续resolver/version校验保持；scoped_state回调结束再比原控制文档，授权不缓存。

lineage-and-guard-03：11项10 PASS/1 FAIL，退出1，122.927秒。上述来源不可用和六轮SET超时均未再发生；唯一FAIL为新增原生正常对照期望可选intentions片段一定进入最终Context，但原2048预算下可选片段未提供，最终表达如实为空。新增原生正反对照改用原受保护continuity.current_focus列表承载同样派生内容，使测试明确核验已提供材料；不改预算、旧断言或运行选材。普通C1间接judgments用例保留。

另一次只读进程查询在沙箱中拒绝访问，随后经工具正常只读权限核验确认无残留Python；不是测试ERROR。两处额外候选路径不存在的读取错误均未修改文件。

## 进一步边界验证

boundary-extension-04：15项13 PASS/2 ERROR，146.296秒。两项新辅助验证分别错期待已推进revision的旧表达Context可成功重播、错捕获内部异常类型；实际正式入口正确包装IntegrationExecutionError。现保留旧Context拒绝并核验原Event/revision/效果不重复，权限变化测试限定到状态来源读取期间，检查回调确实发生且Provider未调用。

selected-state-before-05：3项1 PASS/2 ERROR，9.003秒。一项辅助访问不存在的result_id；另项证实补修中把被隐藏的事项纳入投递来源，导致无关B表达WAITING_CAPABILITY。按实际Context的next项ID追溯原事项，隐藏项不再充当模型已读依据；不移除原来源授权。selected-state-repair-06同场景及旧正常API链3 PASS，25.389秒。所有原输出保存；本次仅修补范围内来源处理，不改公共预算或原测试。

## 同版专项失败与定向测量（final-01）

targeted-final-01：16 PASS；w04-final-01：215项213 PASS/2 ERROR，错误均为RECALL_TIMEOUT（原包级B回复、新增六轮SET最后读取）。这组不是通过，公共兼容与全量尚未启动。两组源码均4120264a…，原日志保留。

package-lineage-diagnostic-01仅一次：在目标B回复前的A输入已超时，插桩点未命中，不能据此声称取得B耗时。package-all-diagnostic-02对同一原包级用例的各实际回忆阶段测量：291.322、906.473、1257.355ms；B回复最后记录1214.606ms/17项/RECALL_TIMEOUT。嵌套计时不可相加；测量记账开销分别1.090、3.010、4.272ms，不把插桩值当正常性能。

B阶段当前scoped_state重复18次310.253ms，Environment读取482次419.657ms（含其他路径），每个状态候选校验重新处理六个分区及权限。新来源重建lineage256次含递归/复用109.769ms。这些是本次补修引入重复工作的实测依据，不宣称旧热点或历史F1/H1/F2已唯一定位。

最小调整：cross_entry_service.py只读投影接受当前所需分区，完整原仓储字节/记录验证仍执行，ThinkSession实际祖先跨分区仍递归追溯。一次投影在同一开始控制文档上核对各绑定，权限回调后比较完整当前文档；授权不跨调用缓存。entry_context_source.py把单个候选的重验/解析接到该分区投影，不重做五个无关分区。两文件属于plan.md原允许职责，device最终guard不变；不改1000ms/2048/原断言。

接下来预定一次原包级用例与新六轮SET用例正常运行，回答本次重复工作是否消除对应超时；新失败先分析，不循环求绿。通过后重新冻结final-02并完成各组，新旧源码结果严格分列。

scoped-package-diagnostic-03：同一包级单次插桩仍ERROR，A阶段956.986ms，B1097.447ms（内部1059.315ms）。B状态过滤由310.253降到160.435ms，Environment482→365，来源展开629→394；仍未声称通过。测量开销B3.656ms，嵌套不可相加。

另一个本轮引入的重复已确认：R2把回执consume也增为两次完整entry.delivery_current，结果读取每次重新展开原投递来源。DeviceOperationService限定发送execute保留观察前早拒绝及回调后最终检查；consume没有观察/发送，在全部附件/连接回调结束后做一次完整当前入口检查。未去掉消费核验、未缓存授权或动查询预算，原执行链不改。

预定一次同一包级正常用例和R2三类交错/正常对照，验证消除重复对结果及拒绝的影响；同源码后再冻结，不将诊断超时记PASS。

consume-current-repair-08：四个R2对照PASS，原包级B回复仍RECALL_TIMEOUT。不能把部分提速写成完成。当前来源图存在另一可定位重复：_state_lineage在重建较新版本时，Event的ThinkSession引用已遍历的旧revision，却重新从头重建前缀；诊断的196次lineage调用含这些重入。

本轮内最小处理：同一已核验walk中在每个真实after_revision保存已重建只读前缀；节点保存其子节点来源集合，避免每次重新遍历相同嵌套对象。只保存来源计算，不保存授权或可用性；公开读取仍新walk、当前字节读取与完整校验照旧。没有第二持久账本。预定一次原包级及R1全部正式反例，验证历史revision重用不混淆来源。

lineage-prefix-repair-09：17 PASS（16新增及1原包级），277.089秒unittest/277.817秒控制器，退出0。源码前后d77fb9e5…一致。不是反复相同版本求绿：每步运行对应已说明的重复工作修补，所有中间错误保留。当前冻结final-02为332项、原1975+新增16=1991测试；17项作为最终定向，不另机械重复一次。

prefinal-02.audit.json的16项身份与保护核验均通过；原402项历史（除三项已说明运行文件及共享档案顶部）原字节保持，旧测试文件/身份、70保留、63保护、7正式、3规划及暂存index不变。W04-final-02正在执行，公共与全量尚未启动。本轮另有一次Windows rg文件通配读取辅助错误，改用目录-g搜索；不计Engine失败。

w04-final-02完成：215 PASS，904.839秒unittest/905.626秒控制器，退出0，源码d77fb9e5…前后相同。原包级和六轮SET均在本组通过。接下来公共1145项，随后全量1991项；本条不预填这两组结果。源码保持冻结。

public-final-02完成：1145项=1144 PASS/1既有Windows1314 SKIP，1605.812秒unittest/1606.717秒控制器，退出0；d77fb9e5…源码前后相同。与定向/W04重叠，不相加。现在单独启动本次第一轮完整回归full-final-02（1991项），不预填结果。

full-final-02于本地2026-10-02 00:00前完成：1991项=1990 PASS/1既有Windows1314 SKIP、0 FAIL/ERROR，退出0；2460.921秒unittest/2462.046秒控制器。运行前后同为332项d77fb9e5…，原1975身份保持，新增16。四组最终结果均同版，集合重叠不相加。本轮没有再次启动全量；旧402项交付与各次失败原件照留。终局进程查询未见Python测试进程，无强制清理或无关进程终止；实测记录见process-final.json。

交付仅IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，尚待独立复核；本轮未查询实际远端，未取得CI结果，没有Git写操作或W05开工。归档脚本将最新续接信息置顶并保留各历史时点的旧续接正文，不把旧“正在运行”快照改成当时已完成。
