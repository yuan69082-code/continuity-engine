# D-089 验收矩阵

Planning Item → Code Change → Test → Acceptance Result。依据用户正式验收及规划窗口只读复核；测试均引用施工方同版实跑，不重复计数。

| Planning Item | Code Change / 原链 | Test / 证据 | Acceptance Result |
|---|---|---|---|
| N13/N12 UI，T27—T29/T37 | device_operation、DeviceOperationService、隔离模拟Adapter；原Action/P17/E5-A | 原42项模拟测试、专项87及全量；[初版定位](../w04_2_evidence/coverage-map.md) | ACCEPTED，本机隔离模拟范围 |
| N10，T22/T85/T86 | W04-1 Body绑定复用，传感→Perception、动作→原回执 | NONE/合法零/未知、代次/到期/撤权/断开/未知/恢复，专项及全量 | ACCEPTED，本批模拟闭环；真实硬件未接入 |
| N10，T87 | 模拟硬件/Somatic/Dream分源契约 | 原模拟链及隔离反例 | ACCEPTED，本批分源；W05 Dream联动未实现 |
| N21，T66/T67/T72 | HistoryScope与原ExecutionContextSource→Router/Composer | 新9项指定回执测试、原历史查询/同源/权限与恢复 | ACCEPTED，本批局部模拟查询；不代替W05自然记忆 |
| T18/唯一结果权威 | 原操作身份、E5-A、当前来源和权限，不盲重放UNKNOWN | 重开/返回丢失/重复/取消，原模拟专项及全量 | ACCEPTED，本批适用恢复 |
| W02/N02/T03—T06 | json_external_provider_repository._safe优化，原1000ms不变 | 原5场景、追加2负载、公共417及全量 | ACCEPTED，本机正式负载；cProfile超时历史照留 |
| P18控制测试 | test_p18_runtime_contention获准两项修正及3项受控回归 | 定向32、公共417及全量；原断言全文与受控失败保留 | ACCEPTED，产品期限/CAS/控制语义未改 |
| 指定历史回执选择 | device_operation_service与execution_context_source目标选择；不扩2048预算 | history-before-03修前；新9项正反/预算/权限/同根/只读/重开 | ACCEPTED，不接受其他同根回执冒充 |
| W04-1/公共兼容 | 原权威、权限、生命周期、主体性及持续运行边界保留 | 专项87含W04-1原29；公共417；全量1862PASS/1SKIP | 本批兼容门通过；不重做D-087及其他历史验收 |

[同版结果及限定](acceptance-report.md)；[原施工矩阵](../w04_2_completion_evidence/matrix.md)保持当时状态。W04整体IN_PROGRESS；W04-3/4及后续未开工。
