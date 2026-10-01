# D-092 / W04-4 两项独立复核返修交付

状态：**IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。R1/R2在本机隔离TEST形成修前反例并完成最小补修，同版验证见下表；交规划窗口独立复核及用户决定，不自行关闭复核阻断或验收。W04前三批验收不改，不W05，不暂存、提交或push。

## R1：状态值及派生内容的入口来源

原按整个字段最后一个C1写入入口过滤，保留在APPEND/SET中的A值被B末次写入掩盖；无C1映射的原生更新也缺少来源处理。修前真实原始消息经过C1、Thinking、Action、Evolution把A私有标记写入current_focus；撤转用后B追加合法值，再次响应中A标记同时进入最终Context和模拟表达。重开仍复现，正常授权对照通过。

`services/cross_entry_service.py`现在按原StateUpdateRecord.changes重建仅供当前读取的逐值来源；不变的值保留旧来源，新值继承原Event及原ThinkSession实际获得的片段，按片段历史revision追溯。来源关系包括engine.subject-state；原生/间接更新不再因缺C1映射被跳过。原权威State及Event历史不删除，不建立第二来源账本。当前转用与绑定每次重核；当前投影、Resolver与版本/内容核验保持。

列表逐值保留可读成员。原结构化字段的有界投影不能证明细粒度来源时保守保留该字段完整来源；事项则按实际提供的next项身份追溯，不能把已隐藏项当作模型读过的材料而挡住B合法表达。原生及普通C1派生、SET保留值、重开、读取中绑定变化、只读查询、重复旧请求不重复提交均有正式回归。

## R2：最后观察和回调后的入口许可

原入口检查在观察前，后续附件/能力检查不能替代入口绑定、read_from和联系暂停检查。修前在模拟port持设备事务锁的final guard最后一次observe内改变上述条件，页面和附件不变，实际B发送效果与credits各1。三种交错均有有效反例；绑定辅助输入错误另存，未冒充产品FAIL。

`services/device_operation_service.py`在原同步派发边界的observe/connection回调之后再次调用原delivery_current；后者所有回调结束后重读原控制文档，任何期间变化拒绝。修后三种观察交错及剩余连接/权限回调均零发送、零费用；权限未变仍一次合法发送/一次费用。原P17/E5-A请求、回执、设备事务、UNKNOWN及重放规则不改，不承诺任意生产并发下的瞬时撤权保证。

联系暂停/绑定变化对照仍验证独立原生心智提交。转用撤销导致旧Context真正失效时保留拒绝和WAITING_VERIFICATION，不静默重绑；以新的B原始消息取得当前Context，证明合法内部提交仍可进行。失效旧请求重开/重复仍核验原Event、revision与效果/费用不增加。

## 同版施工实跑

|集合|PASS|SKIP|FAIL/ERROR|退出码|unittest / 控制器秒|
|---|---:|---:|---|---:|---|
|[lineage-prefix-repair-09](lineage-prefix-repair-09.json)|17|0|0 / 0|0|277.089 / 277.817|
|[w04-final-02](w04-final-02.json)|215|0|0 / 0|0|904.839 / 905.626|
|[public-final-02](public-final-02.json)|1144|1|0 / 0|0|1605.812 / 1606.717|
|[full-final-02](full-final-02.json)|1990|1|0 / 0|0|2460.921 / 2462.046|

这些集合相交，不能相加。源码/测试/资源332项：`sha256:d77fb9e525eae8bd5d09796db3703029ce3e759ca0eee9207db52f1347ab596c`；原1975项身份及旧测试文件原字节保持，新增16项，共1991。规划窗口提供的是静态只读意见，未独立运行这些测试；本次以上各组为施工窗口实跑。既有Windows1314 SKIP不计PASS。没有远端CI结果。

原331项/63b8189d…的1974 PASS/1 SKIP仍是旧交付的有效历史证据，不能作为新版本覆盖。修前、辅助错误、修补引入的过度过滤、首轮修后失败及全部诊断在[test-index.md](test-index.md)和[repair-progress.md](repair-progress.md)逐项列出，未覆盖、删改或循环全量求绿。

## 公共影响与范围

本轮运行差异为CrossEntryService、同职责EntryStateSource/Resolver及DeviceOperationService；新增正式测试只有test_w04_4_review_repairs.py。旧P13/C1已批准补修保留。来源投影用于原Router/Composer、回忆、Event/Memory派生及投递当前检查；最终入口再核验用于已有设备发送链。外部Schema、权限政策、费用、主体性、调度、生命周期及运行寿命未改变；1000ms与2048配置、原断言和时限不改。

首轮冻结版W04专项213 PASS/2 ERROR，原包级与新六轮SET触发RECALL_TIMEOUT，原日志不改。逐站测量证实每个状态候选重复过滤六分区；改为当前所需分区后仍完整验证原记录，并递归查实际祖先。一次投影复用开始控制文档，回调后再次读取当前文档；授权不跨检查保存。R2重复消费回执检查改为全部回调后一次完整核验，发送仍保留观察前和最终两次。同一来源walk按真实after_revision复用已重建前缀及子节点来源集合，不跨读取保存授权。详见repair-progress；旧失败和插桩结果不能冒充最终正常性能。本次未放宽时限、缩减负载或修改旧断言。

验证只证明当前本机TEST负载及明确交错，不能推出真实平台、真实模型语义、无界历史负载或生产性能。旧Context失效仍拒绝；没有删除历史或把真正UNKNOWN改成成功。历史F1/H1/F2仍UNKNOWN，原有中断/超时/辅助错误/行尾提示照留。P19页面、P20/21正式恢复、P22真实接入、W05梦境等仍未开放。

## 复核入口

[逐项矩阵](matrix.md) · [测试索引](test-index.md) · [冻结身份](frozen-source-final-02.json) · [原静态意见副本](independent-readonly-review.json) · [原件/副本hash与开工身份](baseline.json) · [终局审计](final.audit.json) · [累计精确清单](final.pending-files.md) · [逐文件hash](final.files.json) · [70项排除](exclusions.json) · [只读链路样例](read-only-examples.md)。

63项保护、7份正式数据、三份规划原文、70份保留和旧历史后缀是否一致，以终局审计实测为准；审计必须全部满足后才交付。Git只读，实际远端本次未重新查询；不把本地origin/main冒充远端或宣称CI PASS。
