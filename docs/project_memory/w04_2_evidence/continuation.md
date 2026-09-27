## 当前安全停点

W04-2功能实现为IMPLEMENTED_NOT_ACCEPTED，公共兼容收口/最终全量BLOCKED，W04整体IN_PROGRESS，W04-3未开工。D-088仅开工。专项71 PASS；兼容414项为407 PASS/1 FAIL/6 ERROR；原HEAD与当前版各一次4项对照均1 FAIL/3 ERROR。最终全量未启动，不借用旧全量。原1000毫秒/旧断言未改，历史F1/H1/F2仍UNKNOWN，未取得远端CI结果。PLANNING_CONFLICT=PRESENT（验证依赖/处理范围待决定），EVIDENCE_CONFLICT=PRESENT；不倒改历史验收。

原兼容会话1545、诊断98533和样例12008均已完成，不得盲恢复或重复启动。源码未改。下一步为用户决定W02/P18定向调查范围；不启动W04-3。终局审计与进程记录见final.audit.json/process-cleanup.json。以下为旧进度，不代表进程仍运行。

## 最新进度（2026-09-27 UTC）

固定源码专项 w04-2-special-final-01 已完成：71 PASS（42新增+29 W04-1），220.526秒，exit 0。兼容 w04-2-compat-final-01 正在运行，会话1545；先确认真实进程和结果后接续，不能重复启动。完整回归及链路样例尚未运行；progress-01.audit.json 全部保护/保留/历史尾部核对无变化。以下是较早的施工记录，运行状态以最新JSON为准。

# W04-2 接续记录

当前授权仍为 W04 第二子批次施工；不是 W04-1 收尾，不开 W04-3，不验收、不执行 Git 写操作。

已核基线 main / fc185843d7de815262d9efbcab4a04337c6f303d，310 源码与 D-087 一致，70 份保留材料逐项固定于 baseline.json。D-088 为开工决定。

已实现内部 DeviceCommand/Observation 参数随原 E5-A 持久化；原 P17 门禁接设备当前观察；隔离 UI/Body 操作与再观察；传感进入原 Perception；UI 历史结果经原 Router/Composer，根身份去重，当前不可读候选退出而旧事实保留。初版公共影响限 ActionSpecification、ExecutionService、ExecutionContextSource，旧调用路径和正式测试字节不变。

固定源码见 frozen-source.json：314 项，sha256:61bb34c6728e6850786b10b867bf9a440b8193e1534c82ff30b46ba488392b0f。原 1802 项测试身份见 baseline-test-identities.json；原113份测试文件字节未改。

当前 `w04-2-special-final-01` 正在运行（本次工具会话 96802）。恢复时先查该标签 JSON、stdout/stderr 和真实进程，不盲用会话、不重叠启动。还需受影响兼容及一次完整回归；未完成记录不能计 PASS。

已保留中间结果：修前 1 ERROR（旧内部契约不接受 device 参数）；时间格式辅助 1 ERROR；首轮 15 PASS/3 ERROR（新参数数组持久化前后类型不一致，已规范化）；第二轮 28 PASS/2 FAIL/1 ERROR（新夹具续接、预期拒绝方式、深临时路径）；后续定点修正均有原始输出。主体生命周期用例误用 PAUSE 而非原 SUSPEND 的辅助 ERROR 保留，未改原生命周期。

历史 F1/H1/F2 UNKNOWN；W02原1000ms不改；本批 TEST 只证明工程链，不证明真实语言质量、真实设备、生产恢复或长期 exactly-once。无远端 CI 结果。
