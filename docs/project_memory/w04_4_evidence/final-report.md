# D-092 / W04-4 与 W04 包级贯通交付

状态：**IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。本次完成施工及同版验证，交回独立复核，不自行验收或关闭复核阻断。D-091及W04前三批验收、所有旧失败保持。W05未启动，未暂存、提交或push。

## 做成了什么

同一主体可以凭可信入口绑定接续具体问题与原事项；原生认知形成新的联系意图，经原表达、Action、P17和E5-A发送。API及模拟UI分别走通A选店问题→无用户新消息的原生续问→B回复→原事项。只认同名不授权；同人多事项分开，群聊收件人、自发回显和三类时间有独立对照。

收到、查到、发送、送达、已读、未答和UNKNOWN保留不同含义。当前允许转用的旧材料才能进入B，输入、原生Event/ThinkSession生成的Memory和普通UI查询资料均沿原根复核；撤权后不能借派生记录绕行。只读inspect不触发观察、模型、学习、派发或revision。

包级因果用例在同一主体/原账本上串起绑定、P16发现、连接/核验、历史查询、原始问题、原生续问、B回复、模拟身体动作/感知、旧身体失权、临时工具清理。它不是前三批旧PASS的拼接；具体ID和模拟成本见[链路样例](readonly-chain-example.md)。

## 修前证据、修改及公共影响

- 原P13当前精确确认与requires_confirmation判断冲突，以及相关C1先投递后表达的问题，已按用户明确授权补修；旧待确认快照保留，当前不再等待相同批准。正常精确确认、拒绝、撤权、历史拒绝不升级均有正式回归。
- `native-related-memory-before-01`证实受限A经原生Event/Memory进入B；修补原始ThinkSession及上下文根追溯。恢复任务时的native-related-memory-repair-01仍是1 PASS/1 ERROR、退出1：撤权对照通过，但正常链超时；该旧结果未改写，也不作为最终整体通过依据。最新UI查询反例`queried-entry-before-01`为1 PASS/1 FAIL；查询没有发送关联仍须追溯原DeviceCommand设备/账号/会话绑定，`queried-entry-repair-01`2 PASS，最终定向集再次覆盖。
- 联系暂停原先在选择阶段抛错，连带阻断独立心智提交；`contact-pause-internal-before-01` FAIL，修后发送/费用0且合法内部revision推进。现实发送仍经过原P17当前和最终检查。
- 正常原生B回复和包级负载曾触发RECALL_TIMEOUT。逐站测量将重复工作定位到环境读取/安全路径、原E5-A解析和副本、来源祖先追溯、结果核验及纯值指纹。只复用当前字节完整验证结果与同次准备内纯值，不缓存授权；逐次读字节、完整日志损坏校验、路径/来源/当前权限与独立返回副本保留。选择在原Router/Composer及原预算内完成。首次全量full-final-01的1969 PASS/1 SKIP/2 ERROR原件保留；该版2e910dd2…不覆盖最终版。后续当前Windows路径属性逐次读取及原日志来源字段投影补修，详见[最终超时调查](final-timeout-investigation-02.md)与[调查记录](package-investigation-20261001.md)和[范围/限制](final-scope-and-limits.md)。
- UNKNOWN旧发送不永久冻结有可靠关联的独立新询问，原发送不重放；未知身体动作不能套用该例外。模拟端若所有查询均不可观察，新发送仍如实等待。没有承诺任意平台exactly-once。

旧公共调用通过可选入口接线保持；内部ContactIntent/entry_record未提供时沿旧格式与路径。SubjectState/Event/ThinkSession、Learning/Evolution、原请求/E5-A仍为唯一权威。事项采纳经公开的adopt_matter调用原W03链，不声称每条消息自动建立事项，也不静默重绑旧Context。具体文件和兼容责任见[文件职责](implementation-map.md)、[最终矩阵](final-matrix.md)及[精确清单](final.pending-files.md)。

## 最终同版测试

源码/测试/资源 **331项**：`sha256:63b8189dda6bca9a7cb5985cfeded9e0d920aca284500d32bdded91040307261`。原1923测试身份和旧测试文件保留，新增52，共1975。以上都由施工窗口实际运行，规划窗口的旧只读检查不是独立实跑；本次尚待新的独立复核。无远端CI证据。

| 最终集合 | PASS | SKIP | FAIL/ERROR | 测试秒 | 外层秒 |
|---|---:|---:|---|---:|---:|
|[targeted-final-02](targeted-final-02.json)|52|0|0/0|306.026|306.668|
|[w04-final-02](w04-final-02.json)|199|0|0/0|662.495|663.233|
|[public-final-02](public-final-02.json)|1144|1|0/0|1666.164|1667.02|
|[full-final-02](full-final-02.json)|1974|1|0/0|2380.273|2381.35|

各集合交叠，不相加。正式运行期间源码冻结；对应前后hash相同。原始完整命令、退出码、输出、测试身份与耗时见[测试索引](test-index.md)和[frozen-source-final-02.json](frozen-source-final-02.json)。公共范围补充原P03/P04/P05/P06/P08/P09，见[事前清单](public-scope-addendum-01.json)。Windows/Python与隔离配置见[环境记录](validation-environment-20261001.json)。

按原始命令独立复跑某一组的方法见[复跑说明](reproduce.md)，恢复和拒绝边界见[恢复语义](recovery-semantics.md)。

## 未被本次证明的范围

真实平台、生产凭据/设备、任意自然语言质量、更大/无界负载性能未验证。1000ms回忆与2048上下文未增加；重度剖析超时及所有中间失败原样保留，不承诺以后永不超时。新TEST辅助初始化/类型/错误模块名、历史运行中源码变化均在索引和续接中明示，不冒充行为通过。

W05自然记忆/人格联动/再理解/Dream、P19完整页面、P20/P21生产恢复及P22真实接入仍未开放。历史F1/H1/F2 UNKNOWN不改变；Windows1314 SKIP保留。原70份保留材料、63保护、正式7及三份规划保持，D-085本地档案不冒称已提交。最终逐项保护、历史日志、语法、链接、敏感信息、进程与只读Git见[终局审计](final.audit.json)。

下一步仅独立复核与用户决定，不自行启动W05。
