# W02 回答前回忆时限定点补修矩阵

本表仅描述本轮补修；W02/D-081、W03/D-083 和 P00—P18 的既有 `ACCEPTED` 不撤回。本轮补修最高状态为 `IMPLEMENTED_NOT_ACCEPTED`，`EVIDENCE_CONFLICT=PRESENT` 待独立复核。

| Planning Item | Code Change | Test | Acceptance Result |
|---|---|---|---|
| N02 / T03—T06：真实消息在回答前完成有限关联回忆；1000 ms 超时明确阻断 | `AssociativeRecallService.prepare` 仅在一次准备内启用 E5-A 能力账本的精确字节解析复用；策略和 Router/Composer 未改 | `test_w02_recall_timeout.py` 四份资料和第三轮 16 项、`four-postfix-01—03`、`third-postfix-01—03`；原 W02 专项 | `IMPLEMENTED_NOT_ACCEPTED`；六次定点均在旧限时内，独立复核待办 |
| N02 / T06：当前来源、权限、回执及日志完整性不能因提速跳过 | `JsonIntegrationResultLedger._verified_capability_reads` 对每次读取仍读取权威字节；只对字节相同且已完整校验的记录返回独立副本；旧调用路径不入作用域 | 正式回归的字节变更、损坏、私有副本、途中撤权；原 P16/P05/P06 兼容 | `IMPLEMENTED_NOT_ACCEPTED`；新失败日志全部保留，待独立复核 |
| T18：局部失败、重开、同请求重放及失效来源保守处理 | 未改变原请求、行动或恢复逻辑 | `tests.test_w02_integration`、`test_w02_recall_consistency`、`test_w02_external_recovery` 及 W02 专项；第三轮派生材料撤回 | `IMPLEMENTED_NOT_ACCEPTED`；已实跑证据见测试索引 |
| W03 受影响链：旧认识、核心和未完事项 | 未修改 W03 实现 | W03 兼容 32 项 | `IMPLEMENTED_NOT_ACCEPTED`；兼容通过，不替代用户验收 |
| P05/P06/P16 公共链、关闭功能旧路径 | 未更改原公共权限/Composer/Router 契约；账本作用域只由 W02 回忆准备启用 | 公共兼容 155 项、W02 原关闭开关测试、最终全量 | `IMPLEMENTED_NOT_ACCEPTED`；全量结果见索引 |

固定源码 `sha256:1008aabea9c72f769b97886cd9017051da083a95d14f9d9a010d7a738daa297b` 的完整回归为 1773 项：1772 PASS、1 既有 SKIP、0 FAIL/ERROR，退出 0；该结果属于施工方本轮实跑，尚待独立复核。测试集合重叠，不相加。历史四份资料首次失败及 W03 旧/当时版单次超时保留；本轮定点通过不改写历史，也不保证生产时延。
