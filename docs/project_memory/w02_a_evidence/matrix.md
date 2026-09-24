# W02-A 验证矩阵

十二项均为 IMPLEMENTED_NOT_ACCEPTED，已完成本地验证，等待独立复核与用户确认。W02-A 专项 41 PASS；受影响兼容 813 项（812 PASS、1 SKIP）；最终全量 1621 项（1620 PASS、1 既有 Windows 1314 SKIP），均 0 FAIL/ERROR。 下列测试名为定位入口，精确身份/结果见 [最终报告](final-report.md) 与 [运行索引](test-history.md)。本表不是整个 W02 完成或验收。

| 项 | 实现入口 | 正反向与恢复测试 | 覆盖/限制 |
|---|---|---|---|
| A01 原始输入 | input_processing_service.interpret；原 Perception | processing：raw_message、negation_desire_other_and_history | N01/T01/T02 有界规则；不是完整 NLU |
| A02 来源/时间 | InputProcessingRecord.manifest；InputContextSource | integration：current_material_is_bound；recovery：cross_operation | 原时刻不猜造；请求/操作/主体/环境/版本/hash |
| A03 相关站选择 | InputProcessingService.prepare | processing：question_routes、uncertain_report | 不强迫所有模块每句参与；W03 留后续 |
| A04 接收与记住 | 原 Consolidation、Memory 历史 | processing：plain_claim、existing_authoritative_event、same_event_name | 单纯消息待证据；有根才引用 |
| A05 临时材料 | 原 Router/Composer 扩展 | integration：model_capability_input、budget_clipping | N02 当前输入前置；不冒充 B 的自动回忆 |
| A06 内部更新 | 原 C1 Thinking/Action/Evolution | integration：internal_evolution_survives_expression_refusal | 表达门保持开启；拒绝现实不抹掉合法内部变化 |
| A07 局部恢复 | 原 domain progress 追加站点收据 | recovery：local_memory_failure、completed_station、composer_failure | 一站失败保留其他完成证据；整体不假报完成 |
| A08 事实重放 | 原 Memory/ThinkSession/E5-A | recovery：saved_memory、thinking_saved、restart_completed；integration：real_process_restart | 成功事实独立核实；零重复模型/效果/费用 |
| A09 篡改/并发 | operation 顺序、来源核验、C1 admission | recovery：forged_*、receipt_cannot、concurrent_submission；integration：cross_process_busy | 不能用删 checkpoint 降级；不是分布式生产保证 |
| A10 当前门禁 | 原材料检查、许可、TTL、生命周期 | recovery：permission_revocation、context_expired；integration：material_rejected、psychological_content | 不新增心理内容筛查；不放宽权限 |
| A11 兼容/隔离 | 旧可选字段、原 Snapshot、原 P08 路径保护 | integration：disabled_feature、snapshot_branch、protected_fixture | 六 Schema/25 契约/63保护/正式数据不改 |
| A12 只读出口 | ContinuityInteractionService.input_outcome | integration：read_view、read_rechecks_permission | 返回结构/原因/结果身份；P19 页面未做 |

专题、兼容与全量集合有交集，不能相加成新测试总数。原 1580 项身份保留；新增正式用例单列。独立复核未进行，测试通过也不等于用户验收。
