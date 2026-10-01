# D-092 / W04-4 独立复核两项定点返修

状态：IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT。沿既有成果继续，不重新开工、验收或写Git，不W05。规划窗口仅静态阅读，两项尚待施工窗口正式反例验证。原402项交付、四组同版结果及全部历史原件保持。

基线已核对：main/c910be8ff65f1384c4942c980fc4087c1b595a87；331项源码63b8189d…；402项及70保留hash匹配，63保护/7正式/3规划不变，暂存空，无Python测试进程。原复核JSON与副本hash见baseline.json。

| Planning Item | Code Change 候选 | Test | Acceptance Result |
|---|---|---|---|
|N15/T36：累积状态逐值保留来源；原生及间接来源不消失|services/cross_entry_service.py scoped_state/origins；原Event、StateUpdateRecord、ThinkSession来源重建只读投影|原C1/Thinking/Action/Evolution写A列表值，撤转用，B追加合法值，再读最终Context和表达；原生/间接、重开、授权成功|NOT_STARTED；先验证静态发现，不预填FAIL|
|N16/T42/T36：最后观察和剩余回调后仍须当前许可|services/device_operation_service.py原同步最后派发边界；必要时cross_entry_service.py当前绑定复核|仅port持锁final guard内observe触发转用撤回/收件绑定变化/联系暂停；页面不变；效果及费用0，合法内部提交保留；正常成功|NOT_STARTED；不承诺任意生产并发撤权|
|原要求兼容|原1000ms、2048、P18调度、P13/C1已批准语义不改|同一冻结源码新增定向、W04专项、受影响公共兼容、完整回归；旧1975身份和文件断言保持|NOT_STARTED；施工实跑与只读复核/CI分列|

FILES ALLOWED：上列两个运行文件；若只读来源材料解析需要细化，同职责services/entry_context_source.py；新增tests/test_w04_4_review_repairs.py；本目录证据/报告；必要共享工程档案顶部增量。准确实际修改以最终清单为准。

FILES FORBIDDEN：规划原文、保护/正式数据/版本/70保留、既有测试文件和原始日志、其他未说明运行模块、Assistant/Vio/真实服务。不得直接写正式State，另造账本、缓存授权或整片屏蔽合法状态。源记录只读；新日志不倒写旧段。

验证顺序：每项有限一组修前反例与正常对照，保存失败清理前TEST诊断；证实后最小修改；必要新边界组；冻结后各组各跑一次。新失败先解释，不自动循环全量。真实规划冲突STOP CURRENT ITEM并报告。P13/C1同一授权已生效，不重复申请。

辅助阅读记录：记忆索引检索无相关命中；三处候选文件名不存在及一次Windows rg通配路径错误，随后从实际目录和类定义定位；这些不是Engine缺陷，也不是运行反例。
