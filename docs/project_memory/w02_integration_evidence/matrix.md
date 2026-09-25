# W02 整体贯通 Planning Item → Code Change → Test → Acceptance Result

本轮先新增 [正式集成测试](../../../tests/test_w02_integration.py) 发现 A+B 恢复缺口；用户确认后仅定点修改 `continuity_core_service.py` 的已准备 Context 复用路径。下表最终测试均对应固定源码/正式测试指纹 `sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1`；[阻断说明](blocker-report.md)保留修前指纹与原始失败，不用最终结论倒改历史。

| Planning Item | Code Change / 原入口 | Test / 当前真实证据 | Acceptance Result |
| --- | --- | --- | --- |
| N01 / T01 | 复用 `ContinuityInteractionService.submit`、原始契约 hash、`InputProcessingService`；新增 `test_raw_message_stations_old_memory_receipt_and_final_preanswer_context` | 原消息进入正式入口、conversation/memory 站理由，贯通专项 PASS；A 原 `test_raw_message_reaches_thinking_through_actual_composition` 纳入 156 项兼容 | `IMPLEMENTED_NOT_ACCEPTED`，整包未验收 |
| N01 / T02 | 复用 `input_outcome` 与原 Event/Memory；新增 `test_public_read_only_views_do_not_retrieve_or_execute` | 收到但未验证的消息不自动成为旧经历；只读不调用模型/学习/效果，贯通专项 PASS；原 A 防伪及跨进程查询纳入兼容 | `IMPLEMENTED_NOT_ACCEPTED` |
| N02 / T03 | 复用 `AssociativeRecallService`、Router/Composer；新增首条/次条真实消息联验 | 旧进食 Event/Memory 在回应前进入最终 Context，Provider 收到同一 Context，贯通专项 PASS；原 B 时间案例纳入兼容 | `IMPLEMENTED_NOT_ACCEPTED` |
| N02 / T04 内部部分 | 原 `test_t04_replay_and_derived_summary_do_not_add_roots` 及 W02-C 根证明；新部分撤回联验 | 156 项兼容与新撤回测试 PASS；同源转述不增加独立根、候选不自动升级为偏好。W03 长期认识部分仍 `NOT_READY` | `IMPLEMENTED_NOT_ACCEPTED` |
| N02 / T05 | 原 B `test_t05_actual_ingress_variants_reach_final_context`、A 否定/指代真实入站；本轮不改有界解释规则 | 156 项兼容 PASS；否定、他人、愿望、历史时间维持非事实解释 | `IMPLEMENTED_NOT_ACCEPTED` |
| N02 / T06 | 原 `test_finite_association_records_a_reason_and_stops_on_repetition`、预算/超时测试；新无关候选不展开 | 156 项兼容、新贯通专项 PASS；首次复杂 TEST 四取得碰到 1000 ms 上限的 ERROR 留原日志，不把超时伪称旧历史不存在 | `IMPLEMENTED_NOT_ACCEPTED` |
| N11 / T23 内部部分 | 原 P16/E5-A 回执、`ExternalAbsorptionService` 与根证明；新原消息→回执→下一轮 Context 联验 | 同一主体原请求、原回执、当前外部候选与最终 Context 串起，贯通专项 PASS；真实服务 P22、页面 P19 仍 `NOT_READY` | `IMPLEMENTED_NOT_ACCEPTED` |
| N11 撤销 / T23 | 原根、Memory/Summary/P15 支持当前核验；新 `test_partial_derived_withdrawal_invalidates_integrated_reply_and_support` | 同根保留原文，仅撤回派生后旧 Context、Memory、Summary、学习支持及下一轮使用失效，贯通专项 PASS；P20 跨 Store/备份删除 `NOT_READY` | `IMPLEMENTED_NOT_ACCEPTED` |
| T18 / N01+N02 恢复 | 用户在首败后定向确认，只改 `ContinuityCoreService._prepare` 的已准备 Context 复用点；新增 4 个恢复/拒绝正反测试 | 修前 A 单独 PASS、A+B 同原请求 ERROR；修后同反例、重复失败、撤权与旧事件 Context 均 PASS，156 项 A/B/C 兼容 PASS | `IMPLEMENTED_NOT_ACCEPTED`，待独立复核 |
| W02 整体 | A/B/C 正常链与上述一处获确认的恢复定点补修；新 `tests/test_w02_integration.py` 共 8 项 | 固定版贯通专项 8/8、A/B/C 兼容 156/156、公共兼容 318/318 PASS；完整回归 1736 项中 1735 PASS、1 既有 SKIP、0 FAIL/ERROR，集合重叠不相加 | `IMPLEMENTED_NOT_ACCEPTED`，待规划窗口只读复核及用户验收 |

W03 长期认识、P19 页面、P20 跨 Store/备份删除、P22 真实资料服务继续 `NOT_READY`；不以它们替代 W02 内部链。既有 A/B/C `ACCEPTED`、历史 F1/H1/F2 `UNKNOWN`、Windows 1314 SKIP 保留。
