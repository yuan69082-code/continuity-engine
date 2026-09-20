# 归档阅读版

只修正链接；独立报告正文结论未改。逐字节原件见[原件副本](review-report.original.md)，原件及副本 hash 见[归档清单](../archives.json)。本报告发生时尚待用户验收；当前决定见[D-074验收入口](../acceptance-report.md)。原独立运行器依赖规划目录旧 runner，保留原链接作为来源，不在归档目录直接复跑以免追加原观察日志。

# P19 前 A1/A2/A3 补修：独立复核通过

日期：2026-09-20。

结论：在本轮已授权补修范围和已验证版本内，上一轮 A1、A2、A3 三项反例均已闭合；原 R1—R4 与新增补修交叉测试通过，补充恢复/当前权限对照未发现新增阻断。建议进入用户正式验收。

这是独立技术复核结论，不是用户正式验收，不代表永久无缺陷。本轮没有修改 Engine 实现、测试、档案或 Git 状态，没有自行提交、push 或进入 P19。Engine 当前 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT 标签未由本复核改写，待用户正式确认及相应归档。

## 1. 三项结论

| 项目 | 核验结果 | 独立结论 |
|---|---|---|
| A1 表达门槛连带阻断内部保存 | 原确认拒绝/现实拒绝反例均通过；内部获准提案可提交，外部拒绝仍零效果。普通 C1 与 native 表达开启的正式用例、当前权限和来源撤回、内部提交前后崩溃恢复均通过。 | 本轮阻断闭合 |
| A2 表达等路由遗漏效果依赖 | 原 reflect 无 contact/tool 标志反例通过；未获回执支持的本轮模型提案不提前进入当前状态，原始提案仍保留。contact、expression、memory 路由、UNKNOWN、成功回执和后续认知用例通过。 | 本轮阻断闭合 |
| A3 本次已满足被当成永久停止认知 | 原 MindDynamics act→recur 反例通过；无足够新需要时不强制调用，明确放弃不单独作为调度唤醒依据。正式持久化恢复、资源等待/恢复、PAUSE/STOP 用例通过。 | 本轮阻断闭合 |

实际实现核对：

- [ExpressionPolicy 专属拒绝分类](../../../../src/continuity_engine/services/expression_policy_service.py:16)与[空拒绝记录形成](../../../../src/continuity_engine/services/expression_policy_service.py:128)：没有将生成故障或失效 Context 一概视作可继续的表达拒绝。
- [普通 C1 次序](../../../../src/continuity_engine/services/continuity_interaction_service.py:1003)：先形成本轮 Choice，再评估表达并决定派发，内部提交仍走原授权链；非 mind 旧路径保留。
- [实际能力路由与内部投影](../../../../src/continuity_engine/services/continuity_core_service.py:174)：复用原 Choice/CapabilityBinding，而不是只看模型两个标志或扫描文本关键词。
- [native 拒绝恢复](../../../../src/continuity_engine/services/wake_perception_thinking_action_service.py:291)：原 Evolution 事件 metadata 保留空拒绝 artifact，不要求从未派发的操作提供成功回执，也不把内部提交当作世界执行成功。
- [已满足需要重新出现](../../../../src/continuity_engine/services/runtime_cognition.py:129)：使用原 MindDynamics 投影，不再用旧 desires 全结束永久否决新需要；调度自身不创造欲望。

注意 A2 的范围：当前混合轮仍采取保守的提案来源分离，不是已经具备逐句效果依赖判断的新体系。回执到达后，后续合法认知可重新形成判断；不能将其描述成所有模型提案都可立即写入。本轮未新增这种产品政策或扩大写权限。

## 2. 本轮独立实跑

| 集合 | 本轮结果 | 耗时 |
|---|---:|---:|
| 上一轮独立探针原样复跑 | 8 PASS，0 FAIL/ERROR/SKIP | 6.640 秒 |
| R1—R4 与 A1/A2/A3 正式交叉集 | 63 PASS，0 FAIL/ERROR/SKIP | 120.684 秒 |
| 新增独立恢复与权限对照 | 8 PASS，0 FAIL/ERROR/SKIP | 10.708 秒 |

上次独立探针文件未修改，SHA-256 为 `10600a9e54b7a9aa44142f0a11526aca9740d9be6416a351a1bc2d6418d01a55`。本轮只将运行中的观察输出目录指向新复核目录，不覆盖旧观察或结果。

新增八项独立检查：

1. 表达拒绝后、内部 Evolution 前中断：恢复同一次 Thinking，内部只提交一次，零外部效果。
2. 表达拒绝后的内部提交已经完成、随即中断：重开后即使表达许可恢复，也不追发旧操作；原任务完成恢复。
3. 既有拒绝事实恢复期间撤回内部写权限：不重新写状态、不重新调用 Provider、不产生外部效果。
4. 表达生成器异常仍保留为异常，不被转换成可继续的普通权限拒绝。
5. 表达过程中撤回来源权限：不提交内部状态，也不产生外部效果。
6. 表达拒绝后、Evolution 前撤回内部权限：内部写入仍被拒绝。
7. reflect 路由拒绝、已提交过滤后的内部状态再中断：重开不补写提前完成声明，不执行旧副作用。
8. reflect 世界效果发生但回执响应丢失，内部提交后再中断：恢复原事实，不重复调用 Provider、效果、扣费或 revision。

这些检查没有调用生产服务。故障注入输出是上述负向对照的预期证据，不是被隐瞒的测试失败。全部使用隔离 TEST 夹具，控制器明确 STOP，临时夹具正常回收。

## 3. 全量证据核对，不冒称本轮重跑

提供方选定最终运行均已逐文件核对，与当前 275 份源码/测试/资源的执行前后 hash 一致：

- combined-02：63 PASS，126.864 秒。
- independent-final-01：8 PASS，7.349 秒（提供方对原独立探针的复跑，区别于上表本轮独立运行）。
- compatibility-01：538 PASS，1152.693 秒。
- full-final-01：1579 PASS、1 既有 Windows 符号链接权限 1314 SKIP、0 FAIL/ERROR，1687.548 秒。

本轮没有重跑上述完整兼容集或完整全量；核对绑定后引用，不能称“监工本轮全量实跑”。各集合覆盖交叉，不重复相加为覆盖率。没有取得或宣称远端 CI PASS。

## 4. 身份、范围与保护核对

- HEAD：`cb528d74884990915737b491ca6a9f2c35cc512a`。
- 当前源码集合：275 项，hash 为 `sha256:37ca50a9b21595f1e31067d88fefe95d1b4ffcf02e9095ef3393d3afcd4c36f1`。
- 当前实际发现 1580 个唯一测试身份；补修前 1551 项全部保留，新增 29 项。补修前已有测试文件均未改动。
- 相对补修起点，仅五个运行文件及一个新增正式测试文件发生源码/测试变化，与声明范围一致。
- 63 项保护文件、三份规划原件、7 个正式数据文件及正式数据树、版本/pyproject、32 项排除材料全部匹配基线。
- 先前不在本轮允许修改范围的待提交成果和旧证据未变；6 份归档原件/副本匹配。
- 220 项累计待提交清单的可核 hash 全部匹配；清单/审计自身的非循环 hash 约定单列，不伪造自引用校验。
- 265 个 Python 文件语法解析通过；本轮独立 git diff --check 通过。
- 暂存索引匹配起点；每组独立运行前后 Engine tracked/untracked 内容、Git 状态和 HEAD 完全一致。

本轮未另查远端，不把本地 origin/main 视为新的远端查询。后续若获准提交/push，执行方应重新核对当时现场和提交清单。

历史 F1/H1/F2 仍为 UNKNOWN，本轮没有新证据能够唯一归因旧案，也不修改用户此前接受的不确定性。原 P18 验收历史和 D-073 保留。

## 5. 独立证据入口

- [原八项复跑结果](original-01.json)
- [正式六十三项复跑结果](formal-01.json)
- [新增独立对照](test_extra_controls.py)及[实跑结果](extra-01.json)
- [独立身份审计](identity-audit.json)
- [复跑入口](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-supplement-independent-20260920/run_review.py)：使用新标签，不覆盖已有结果。三个集合的模块参数分别为 `original_probe`、原四个 autonomy 测试模块加 supplement 模块、`test_extra_controls`。

同目录的同名 `.log` 是原始输出；结构化观察分别存于 independent-observations.jsonl 与 extra-observations.jsonl，均只属于本轮新目录。

## 6. 下一步需用户确认

可以进入本批次“P19 前自主性边界返修”的正式验收及收尾，不需重做 P18 验收，也不是开始 P19。

用户如确认验收并 push，执行方应按精确清单归档本次独立证据与用户决定，保留排除材料、历史失败和 UNKNOWN；先核对无新源码增量，再普通提交和 push，报告真实远端结果。未获该确认前，不执行上述 Git 写操作。

P19 开工仍须用户另行授权。
