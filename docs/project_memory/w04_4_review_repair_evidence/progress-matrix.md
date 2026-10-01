# D-092 返修当前矩阵（最终验证进行中）

此页记录 final-02 W04 专项结束时的事实，不是验收。原 plan.md、旧402项及旧最终结果均为历史记录，原字节保留。

|Planning Item|Code Change|Test / evidence|Acceptance Result|
|---|---|---|---|
|R1 / N15 / T36：列表保留值的来源与转用|cross_entry_service._state_lineage、_lineage_node、scoped_state；从原FieldChanges、Event、ThinkSession逐值重建|counterexamples-before-01两条有效泄露FAIL；lineage-prefix-repair-09及w04-final-02包含修后最终Context/实际表达、SET、B合法内容、重开对照|IMPLEMENTED_NOT_ACCEPTED，复核未关闭|
|R1：原生及间接来源、实际提供片段|_fragment_origins、_context_origins、origins；使用历史revision，不从最后写入者猜来源|新增普通C1及原生ThinkSession派生正反、读取中绑定变化、重复旧请求、合法B独立表达|IMPLEMENTED_NOT_ACCEPTED，复核未关闭|
|R1：当前检查与时限共存|entry_context_source单分区重验；同一次walk复用已验证历史前缀；投影回调后重读控制文档|首冻结W04 213 PASS/2 ERROR原件保留；逐站测量与各中间失败；当前同版定向17 PASS、W04 215 PASS|IMPLEMENTED_NOT_ACCEPTED；不承诺任意负载性能|
|R2 / N16 / T42：最后观察后的入口权限|device_operation_service._current；原设备事务final guard后段再核验；delivery_current回调后完整控制文档对照|修前三种有效交错均出现B发送/credits各1；修后三种0/0，页面未变、最后guard身份可定位；正常1/1|IMPLEMENTED_NOT_ACCEPTED，复核未关闭|
|R2：剩余回调与历史消费|发送观察前/最终检查均保留；消费回执在全部回调后完整核验一次|剩余connection及contact回调暂停0/0；原请求/回执/UNKNOWN语义；旧Context失效不重绑、新合法内部步骤可提交|IMPLEMENTED_NOT_ACCEPTED|
|原1975测试与公共兼容|旧文件和断言保持，新增16项；1000ms、2048、调度边界未变|prefinal-02身份/保护16项通过；公共组正在运行，全量未开始|IN_PROGRESS，不预填PASS|
|历史、范围及交付|三份规划、63保护、7正式、70保留、旧日志后缀核对|prefinal-02通过；最终审计/清单仍待生成|IN_PROGRESS|

当前源码332项：sha256:d77fb9e525eae8bd5d09796db3703029ce3e759ca0eee9207db52f1347ab596c。规划窗口原意见是静态只读，不是实跑。F1/H1/F2 UNKNOWN、既有SKIP和所有原始失败不改；没有远端CI证据。下一步完成当前同版公共兼容与全量、真实结果归档及终局审计，交回独立复核；无Git写操作，无W05。
