# P19 前 R1—R4 合并返修 Stage Brief

本轮是用户授权的四项内部补修，不是 P19 开工或 P18 再验收。P00—P18 的历史 ACCEPTED/D-073 不变；本批次 IN_PROGRESS，完成最高 IMPLEMENTED_NOT_ACCEPTED，等待独立复核。已知本轮 EVIDENCE_CONFLICT=PRESENT。

来源：用户本轮确认、[完整工单](independent/repair-work-order.md)、[独立报告](independent/review-report.md)、原探针及05轮原始结果。两份规划缓存对应的 Word SHA-256 已实测一致，采用其正文缓存，不改规划原件。

开工 main/HEAD/local origin = cb528d74884990915737b491ca6a9f2c35cc512a；已跟踪与暂存区干净，32项排除材料原样保留。270份源码/测试/资源、1517个正式测试身份及63项保护清单已固定于 before.json。1516 PASS+1既有1314 SKIP仅是历史，不冒称本轮运行。

## 简短方案、依赖与候选文件

1. R1：先保存原诊断，再分开 C1 内部 Evolution 与外部执行结果。保留原 ThinkSession、Action、E5-A 身份及当前授权检查；独立内部提交不能因已记录的现实拒绝/等待受阻；有外部结果依赖的内容不能提前成为成功事实。重点处理完成重放、Context revision、旧请求核实和新认知不重复派发旧副作用。
   候选：services/continuity_core_service.py、wake_perception_thinking_action_service.py、continuity_interaction_service.py、runtime_cognition.py；如需最小请求查询接线，services/capability_coordination_service.py、action_planning_service.py、execution_service.py（保持既有权限/计费/回执语义）。
2. R2：移除 target 子串风险启发式，保留操作类型最低风险、显式更高风险及原确认/拒绝门。真实能力尚未细分时保持保守规则；不把只读名字当可信低风险。
   候选：services/action_evaluators.py；必要时 action_service.py。原依赖错误启发式的测试须先留存原断言和结果，说明替代保护。
3. R3：复用已有 episode/disposition/will 字段与正常 Mind/Growth 候选链；以当前可消费的独立经历根和内部解释形成/修订倾向，原承诺参与后续评估、可因相关新理解修订，矛盾共存。原 Learning 四字段和 rollback 不变。
   候选：services/dynamic_mind_service.py、subject_growth_service.py。先使用现有字段，不改变持久化格式或公共写入权限。
4. R4：在原 RuntimeCognition.needs 中增加由未决关注/承诺支撑的有界复议，保持最低间隔、已有任务身份、预算和明确休息/放弃；Scheduler 不创造心理内容。
   候选：services/runtime_cognition.py；只有确需的局部宿主接线才修改 persistent_runtime_service.py。

必要测试：新增 tests/test_pre_p19_autonomy_*.py；直接受影响旧测试仅在明确纠正启发式规格时改断言并保留原因/旧证据。Fixture 优先复用；如必要仅局部 testing/p09_core_fixture.py、p14_mind_fixture.py、p15_subject_fixture.py、p17_execution_fixture.py、p18_runtime_fixture.py。直接档案限 README、当前状态、施工日志、决策增量、CHANGELOG、工程总档案及本目录报告/矩阵/证据。

## 验证矩阵

| 项 | 修前/正常与拒绝对照 | 恢复与交叉重点 |
|---|---|---|
| R1 | native/C1 允许、现实拒绝、资源不足、途中撤权；内部独立提交与外部结果分别断言 | 内部/外部断点、真正UNKNOWN、重放/重启、零重复效果/费用/revision |
| R2 | ordinary/critical/noncritical同语义改名，内部UPDATE_STATE、外部读/写保守规则 | 已明确HIGH/CRITICAL仍有原确认/拒绝；名字不是风险证据 |
| R3 | 正常经历→认知→候选→Evolution→下一轮；重复/撤回/失效支持 | 原承诺保持与相关理解修订、相反倾向共存、实际影响理由/选择，Learning/rollback兼容 |
| R4 | 自然稳定及合成饱和、无Observation、未决关注/无需求、休息/暂缓 | 资源耗尽与恢复、跨进程、PAUSE/STOP、无风暴/重复派发 |
| 合并 | 长期承诺在现实拒绝后保持，稳定驱力继续合法内部认知 | C1/P14/P15/P17/P18、权限/资源/学习/存储兼容；最终固定源码后完整回归 |

所有试验在隔离 TEST；先分项、再交叉、再兼容、最终全量。首次失败、辅助错误和中断使用唯一标签保留，各测试集有交集不相加。

## 禁止与待定边界

不修改63项保护文件、六份Schema、冻结契约、三份规划、正式七文件、版本/pyproject、32项排除材料或Assistant/Vio。不接真实服务、账户、凭据或设备。不给模型直接状态写权，不新增Authority/账本，不改变公共权限/计费语义。不实施报告D1/D2/D3的正式风险分级、临时深思政策或全量固化改革。

需要扩大上述边界时先说明最小差异并等待确认；其余无依赖项连续推进。历史 F1/H1/F2 UNKNOWN 与用户接受遗留不确定性的记录不倒改。不得暂存、提交、push、验收或进入P19。

## 收工事实（开工计划及当时状态保留）

R1—R4已实现并完成分项、交叉、受影响兼容及最终完整回归，批次IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT待独立复核。实际运行改动为7个services文件；新增4份正式测试，另有2份旧测试的错误目标预期按本轮授权更正，原效果/扣费/拒绝断言保留。完整范围、失败历史、源码身份及未开放事项见final-report.md、test-index.md和final.pending-files.md；未用计划中的其他候选文件扩修。
