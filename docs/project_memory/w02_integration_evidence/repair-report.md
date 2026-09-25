# W02 贯通恢复定点补修与首次异常记录

2026-09-25 用户在本轮明确确认：仅定点修复已复现的 A+B 失败站恢复路径，并补测试后继续 W02 贯通核验。该确认不包含 W02 正式验收或 Git 写操作。[修前报告](blocker-report.md)与其原始输出保留，不用修后 PASS 倒写修前失败。

## 原因及修改

`continuity_core_service.py` 的 `_prepare` 在 W02-B 已存 `input_preparation.continuity_context` 时直接复用，未先完成 W02-A 原操作中仍为 `FAILED_WAITING` 的站。由此，原请求重开后进入 Thinking 前的完整性检查，正确抛出 `INPUT_UNFINISHED_STATION_WITH_CONTEXT`。A 单独配置的原恢复测试在同源码上通过，定位为 A+B 结合处。

只在该复用分支补步骤：先用原记录及当前来源/权限验证部分进度；若仍有未完成站，沿原 `InputProcessingService.prepare` 补做，保留已完成站；再用原 Context 完成 conversation 收据，重新加载同一操作并核对每站结果和 Context 当前有效性。源、身份、版本或权限失效时继续拒绝，不删除原失败，不更换请求，不修改 ThinkSession/E5-A/Memory/SubjectState 权威。无失败站或关闭该特性的旧路径保留原行为。本轮仅修改 `src/continuity_engine/services/continuity_core_service.py` 一处运行实现，新增 `tests/test_w02_integration.py`；没有修改已验收原测试断言。

## 同反例与正反对照

| 标签 | 真实结果 | 说明 |
| --- | --- | --- |
| [a-only-recovery-01](a-only-recovery-01.json) | 1 PASS，1.796 秒 | A 单独恢复正向对照。 |
| [combined-recovery-01](combined-recovery-01.json) | 1 ERROR，1.631 秒 | 修前同一请求重开仍报 `INPUT_UNFINISHED_STATION_WITH_CONTEXT`。 |
| [combined-recovery-after-01](combined-recovery-after-01.json) | 1 PASS，2.393 秒 | 首次最小修补后，原反例恢复完成。 |
| [recovery-boundaries-01](recovery-boundaries-01.json) | 3 PASS，4.543 秒 | 原请求重开、重复失败后合法续做、撤权拒绝；模型/TEST 效果与成功站不重复。 |
| [recovered-memory-context-01](recovered-memory-context-01.json) | 1 FAIL，2.250 秒 | 新测试最初错误地要求先前成功的 recall 必须重跑并改选 Memory 片段。保留此辅助断言失败。 |
| [recovered-memory-diagnostic-01](recovered-memory-diagnostic-01.json) | 1 FAIL，2.243 秒 | 诊断确认原成功 Context 已含旧 `event`，恢复后新 Memory 已巩固；不能把没有重复回忆误报为内容丢失。正式测试改为同时核对 Context 中原 Event 与仓库中新 Memory，未改变用户要求或既有断言。 |
| [withdrawal-integrated-02](withdrawal-integrated-02.json) | 1 ERROR，4.895 秒 | 辅助 Fixture 把派生 hash 当根 canonical hash 后又试图移除，违反 `ExternalRootProof` 自身约束；属于测试前提错误，原输出保留。 |
| [withdrawal-integrated-03](withdrawal-integrated-03.json) | 1 PASS，16.679 秒 | 原文作为 canonical 后再认可派生内容，两可寻址 TEST 根保留原文而撤回派生；旧 Context、Memory、Summary、P15 支持及下一轮使用按原链失效。与已验收 C 的四次独立取得测试范围有别，不冒充该测试。 |
| [integration-targeted-01](integration-targeted-01.json) | 新正式贯通 8/8 PASS，32.328 秒 | 直接从原消息、站记录、回答前召回、回执候选到最终 Context；撤回、失败恢复、只读与拒绝对照。 |
| [w02-abc-compat-01](w02-abc-compat-01.json) | A/B/C 相关 156/156 PASS，251.675 秒 | 11 模块，含 8 项新增贯通；集合交叠不相加。 |
| [public-compat-01](public-compat-01.json) | P04/P05/P06/P09/P16/P17/P18 直接兼容 318/318 PASS，291.693 秒 | 对原 C1 准备链及其下游公共行为的回归；stderr 中 TEST 故障诊断是预期证据，完整汇总为 OK。 |

最初 [integration-draft-01](integration-draft-01.json) 的 5 项中 3 PASS、2 ERROR：一项是上述真实恢复缺口，另一项四次外部取得叠加的测试负载碰到既有 1000 ms 回忆上限。保留原时限；后续用两次原 P16 结果分别证明原文和派生材料、同一 TEST 根保持 canonical 原文，完整部分撤回链通过。不能用后续通过抹去首次超时，也不从它单独推断生产时延结论。

本轮代码、测试及资源在终局四组前后固定为 `sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1`。[单独完整回归](full-final-01.json) 1736 项：1735 PASS、1 个既有 Windows 1314 SKIP、0 FAIL/ERROR，1677.033 秒、退出码 0；四组存在交集，不能相加。测试通过不等于 W02 用户验收；历史 F1/H1/F2 `UNKNOWN`、Win1314 SKIP 和所有首败/辅助输出不变。
