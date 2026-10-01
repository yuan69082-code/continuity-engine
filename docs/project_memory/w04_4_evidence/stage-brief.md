<!-- W04_4_LATEST_DELIVERY_20261001 -->
当前状态（2026-10-01）：W04-4及包级 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。最终定向、W04、公共兼容及全量已同版完成；实际结果见[交付报告](final-report.md)与[测试索引](test-index.md)。P13/C1同一批准已生效，不再待确认。以下开工、验证进行中或待确认字样均为保留的历史快照。未验收、暂存、提交、push，不W05。

# W04-4 与 W04 包级贯通开工简报

STAGE：W04第四子批次话题接续与投递结果；W04-4 IN_PROGRESS，W04整体IN_PROGRESS。D-092仅本次开工授权。

SOURCE OF TRUTH：现行索引的总施工v1.6、最终新增v1.6、长期能力v6.10；W04子批次四与包级结束条件、N15/N16/N10/N21、C01—C15及新版test-stage-map。规划原字节hash见baseline。

ORIGINAL REQUIREMENTS：可信入口/收发身份和转用范围；具体话题/未答事项延续；原Thinking/P13形成新表达，经原Action/P16/P17/E5-A投递；API与模拟UI分别闭环；三类时间/镜像/回显去重；UNKNOWN和新询问分开；统一暂停、当前权限、原事实恢复。

CAPABILITY DETAILS：复用W04环境/能力绑定、W03事项与W02上下文、原操作日志和结果回执；内部版本化入口描述绑定原操作，不建平台人格或平行请求账本。跨入口读取在Router/Composer及使用前重查来源转用范围；有依据的独立新询问不以旧送达未知永久冻结。

AMENDMENT OVERRIDES：本次明确授权W04-4实现及W04同版包级贯通，不倒改D-091及前三批历史。

KEEP RULES：主体权威、原P08/P13/P16/P17/P18、E5-A、每轮2need、1000ms回忆、2048指定历史上下文、费用/权限/STOP/生命周期及原测试断言保持；查询零业务推进；UNKNOWN不盲重放。

DEPENDENCIES：前三批已验收；W02/W03与原消息、Thinking、Learning/Evolution、控制/资源链。实际源码缺口先取证，已有能力复用。

NOT READY：真实服务/账号/设备/发送、P19页面、P20/21生产恢复、P22实接及W05自然记忆/再理解/Dream；本轮不能宣称任意平台exactly-once或自然语言通用能力。

FILES ALLOWED（候选，按实际必要使用）：新domain/cross_entry.py、services/cross_entry_service.py、testing/w04_cross_entry_fixture.py、tests/test_w04_4_continuity.py、tests/test_w04_package.py；最小公共接线候选domain/integration_results.py、domain/environment_access.py、domain/device_operation.py、domain/action_planning.py、storage/json_environment_repository.py、storage/json_integration_repository.py、services/continuity_interaction_service.py、services/continuity_core_runtime.py、services/continuity_core_service.py、services/device_operation_service.py。各路径均在src/continuity_engine下（tests除外）。不要求全部修改；新增内部可选字段旧数据缺失保持旧行为。若实际需要其他职责内最小文件，先登记原因与影响，不改冻结契约。

FILES FORBIDDEN：63保护、正式七文件、三份规划原文、版本、70保留材料、既有证据与旧正式测试；Assistant/Vio/真实外界不动；不改受保护interfaces/local_integration_app.py及外部Schema。

TESTS REQUIRED：修前缺口记录；T33—T40/T42逐项正反；T18/26—32/41/60/72/85—87适用联验；T66/67仅W04契约；T43最小只读与T25/45成本支持范围。API/UI两条A→B→原事项正常链、转用/撤权/并发/恢复/暂停等；四批因果组合包级集成；同最终源码专项/公共兼容/一次全量，保留1923原身份。

PUBLIC IMPACT / ROLLBACK：只加可选内部接线，未启用旧调用字节/行为保持。新入站元数据随原operation持久化，动作随E5-A，不直接改SubjectState。隔离TEST失败先保存现场，再只回收本轮进程；不回滚正式数据或丢弃原事实。

PLANNING CONFLICT：开工未发现已证实冲突；发现则STOP CURRENT ITEM并报告用户决定，未确认不降级或后移。EVIDENCE_CONFLICT=PRESENT至交回复核。

## 2026-09-29实际开发范围与停点（保留上方开工快照）

实际新增：domain/cross_entry.py（入口/角色/来源绑定值对象），services/cross_entry_service.py（原链入口与转用/投递绑定及只读投影），services/entry_context_source.py（原SubjectState按当前入口授权投影，无第二状态存储），testing/w04_cross_entry_fixture.py（隔离外界/确定性模型输入），tests/test_w04_4_continuity.py（13项开发中测试）。

实际修改：domain/device_operation.py、integration_results.py（旧字段兼容的内部可选元数据）；storage/json_environment_repository.py（沿原环境配置持久绑定/联系设置，同当前字节解析复用不缓存授权）；json_integration_repository.py（原操作身份绑定及最小投影）；services/continuity_core_service.py、continuity_core_runtime.py、continuity_interaction_service.py（可选入口接线）；device_operation_service.py（原P17投递当前性及效果核验）；input_context_source.py（原输入来源投影）；unfinished_item_service.py（仅启用新入口时沿原授权/Context支持input根）；testing/w04_device_fixture.py（模拟发送操作）。未使用的候选文件不要求修改。

这些公共变化均仍为开发版，旧正式测试文件字节保持，已实跑153项选择兼容但最终回归未做。冻结external Schema、原63保护/正式7/规划/版本/70保留不动。

新增冲突：N16为BLOCKED / PLANNING_CONFLICT，理由与请求修改范围见planning-conflict-n16-01.md。原P13表达策略尚未改；C1仅有已授权入口字段接线，尚未改表达/派发顺序。API/UI完整主动链和包级集成不得报告IMPLEMENTED_NOT_ACCEPTED或PASS。



## 本次确认后的实际增量
用户明确同意此前P13/C1定点方案；该项由等待批准转IN_PROGRESS，历史提出记录不改写。新增tests/test_w04_4_expression.py；domain/thinking.py保存可选ContactIntent（None时旧序列化不变），原ThinkSession保存事实。环境读取重复工作测量后，environment_access_service.py增加私有单次文档复用，原require调用签名不变；当前权限/连接回调后仍重读并比较，含入口绑定和统一联系暂停。JsonEnvironmentRepository不缓存路径或授权，逐次lstat/current bytes，解析只复用同字节并返回独立副本。EntryStateSource内容未变的主体字段保持原版本，P14原核验不改。必须联验P13/P14/Thinking/P18/W04-1及W02旧预算与读取拒绝边界。

## 最终实际文件范围

实际源码/测试逐路径及hash见final.files.json，公共影响与旧数据兼容见final-scope-and-limits.md。前述候选及待授权时点保留；最终P13/C1已获确认。未修改63保护、正式7、规划、版本、70保留或旧测试文件。最终每组验证保持同版，W04-4及包级仅IMPLEMENTED_NOT_ACCEPTED，不启动W05。

