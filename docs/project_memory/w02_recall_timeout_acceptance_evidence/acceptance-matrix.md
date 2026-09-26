# D-084 回答前回忆时限定点补修验收矩阵

W02/D-081、W03/D-083 与 P00—P18 历史验收保持；本表仅将已复核的本轮增量登记 `ACCEPTED`。施工时的 `IMPLEMENTED_NOT_ACCEPTED`、`EVIDENCE_CONFLICT=PRESENT` 及修前失败留在[原矩阵](../w02_recall_timeout_evidence/matrix.md)和[原始测试索引](../w02_recall_timeout_evidence/test-index.md)。

| Planning Item | Code Change | Test | Acceptance Result |
|---|---|---|---|
| N02 / T03—T06：正常原始消息回答前完成相关回忆；超时必须明确阻断 | [AssociativeRecallService.prepare](../../../src/continuity_engine/services/associative_recall_service.py)只在一次准备中启用原账本解析复用，原 1000 毫秒限时和 Router/Composer 职责不变 | [正式新增测试](../../../tests/test_w02_recall_timeout.py)、预定四份负载和第三轮各三次原始结果、W02 专项 161 PASS | `ACCEPTED`：两种已复现 TEST 负载均在原时限内；不扩称生产性能 |
| N02 / T06：当前来源、权限、回执、版本及完整日志校验不得因提速跳过 | [JsonIntegrationResultLedger](../../../src/continuity_engine/storage/json_integration_repository.py)每次读当前权威字节，仅对相同且已完整校验的内容返回私有副本；旧调用不启用作用域 | 新正式测试的文件变化/损坏、副本隔离、途中撤权；公共兼容 155 PASS | `ACCEPTED`：无跨请求授权缓存，失效候选仍不得进入回应 Context |
| T18：局部失败、重开、同请求重放和历史事实恢复 | 原请求、模型、行动及 revision 恢复实现不改，回忆作用域结束即清空 | W02 专项 161 PASS、W03 兼容 32 PASS，最终全量 1773 项中 1772 PASS/1 既有 SKIP | `ACCEPTED`：本轮影响范围内无新 FAIL/ERROR；历史失败不倒写 |

上述测试集合有交叠，不相加。规划窗口只读复核、未独立实跑；本次档案归档未重跑测试。当前已知补修阻断关闭不代表大负载、其他设备或生产环境永不超时；F1/H1/F2 仍 `UNKNOWN`，W04 未开工。
