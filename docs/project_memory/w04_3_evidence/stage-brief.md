# W04 第三子批次开工简报

STAGE：W04-3 工具发现与临时接入，IN_PROGRESS。W04整体IN_PROGRESS。本次不是验收/Git授权。

SOURCE OF TRUTH：现行索引对应总施工v1.6子批次三、最终新增v1.6 N14/T30—T32/T41及N21、长期能力v6.10；规划原件hash见baseline.json。保留共用C01—C15、P08/P16/P17/P18及W04-1/2边界。

ORIGINAL REQUIREMENTS：发现候选、核对、合法选路、授权内试连、缺条件等待、验证、实际任务、结束/撤销/清理/恢复；单次/限时/持续条件独立，发现不是授权。

CAPABILITY DETAILS：P16查询事实验证候选；P08结构Choice、P17执行和唯一E5-A保存接入/使用/清理事实。W04 Attachment是可重建当前门禁，不建工作流账本。设备/历史查询复用DeviceOperation与指定回执Router/Composer。等待沿原Scheduler/P18 guard续接，不新建运行时。

AMENDMENT OVERRIDES：本次用户授权W04-3；不倒写旧“未开工”记录。

KEEP RULES：1000ms回忆、2048 Context、P18控制/唯一宿主/CAS、Subject Authority、权限/材料/来源/费用/UNKNOWN不重放不变。正常内部认知不逐步审批。

DEPENDENCIES：已验收P08/P16/P17/P18、W02/W03、W04-1/2。D-085独有档案及其他70保留材料单列。

NOT READY：生产工具服务、真实登录/采购/安装/付费、W04-4跨入口联验、W05自然记忆与梦境、P19页面、P20/21正式恢复、P22真实接入。

FILES ALLOWED：新增`src/continuity_engine/domain/temporary_tools.py`、`services/temporary_tool_service.py`、`testing/w04_tool_fixture.py`、`tests/test_w04_3_tools.py`；最小接线`src/continuity_engine/domain/action_planning.py`、`services/device_operation_service.py`；必要Scheduler/P18适配置于本批服务。档案限本证据目录、当前状态/施工日志/决策/未完成事项/档案修订记录/工程总档案/README/CHANGELOG。候选文件非必须全部修改；新增运行文件先记录职责。

FILES FORBIDDEN：63保护、冻结Schema/外部契约、正式七文件、三份规划原文、版本、Assistant/Vio、70保留材料、旧证据；不改W02/P18既有产品语义或旧测试断言。

COMPATIBILITY：新增内部ToolCommand仅tool.*分支，旧Choice字节不变；设备可选connection_guard默认None；不增加外部Schema或状态权威。隔离TEST回退只停止自建进程、保留证据，不修改正式数据。

TESTS REQUIRED：先记录未实现入口，再定点正反/恢复；T30/T31/T32/T41及N21，原W04-1/2、P16/P17/P18/W02/W03相关兼容，最终固定源码一次完整回归。有限故障注入及进程恢复，不循环跑绿。

PLANNING CONFLICT：当前未发现实际冲突；如发现按STOP CURRENT ITEM报告。测试通过仍不代表验收。
