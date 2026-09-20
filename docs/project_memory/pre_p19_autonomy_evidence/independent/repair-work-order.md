# P19 开工前：主体自主性边界四项合并返修工单

## 0. 当前授权与唯一任务

用户已确认本轮四组必修问题，并要求尽量合并为一轮完整修复。

当前唯一任务是：完成下述 R1—R4 的必要实现、测试和直接相关档案，交回独立复核。

这不是再次执行旧 P18 验收或 Git 收尾，也不是开始 P19。历史提示中的“等待这四项返修授权”已由本次授权替代；不因读到旧档案中的暂停/待确认文字而退回旧任务。

本轮授权涵盖四项范围内必要的代码修改、回归测试及直接档案更新。先写简短施工方案和候选文件范围，再在该范围内连续实施，不必每完成一项重复请求相同授权。

“全部”仅指本工单 R1—R4，不包括专项报告 D1/D2/D3 中尚待确定的正式风险分级、临时深思政策、全量成长操作与固化授权改革。

不授权：提交、push、自行验收、进入 P19、修改 Assistant/Vio、接真实服务或设备、使用生产凭据、发生真实消费、清理用户文件。

若必须修改冻结契约、保护文件、正式 Schema/迁移规则、公共权限语义、生产策略或扩展上述范围，列出最小差异与必要性，先请用户确认。能够安全独立完成的其他已授权部分可继续，不能借此绕过缺失的授权。

## 1. 仓库、审查依据与基线

Engine 工作仓库：

`C:/Users/Administrator/Documents/continuity-engine`

规划/独立审查仓库：

`C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity`

先完整读取以下独立材料，不得只看摘要或截图：

1. `C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/review-report.md`
2. `C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/probe_boundaries.py`
3. `C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/probe-results-05.json`
4. 同目录的 `engine-main-plan.json`、`engine-long-term-plan.json`：仅在所指原始 Word hash 仍一致时作为原规划文本缓存使用；不得改原件。

审查时 main 为 `cb528d74884990915737b491ca6a9f2c35cc512a`，已跟踪工作区/暂存区干净，另有 32 项既有排除材料。这是审查快照，不是未经检查就假定当前仍相同。

开工先只读核对当前 HEAD、工作区、原保护清单、排除材料及源/测试身份。若现场已有增量，识别来源并保留，不能 reset/覆盖；若与本轮有冲突或来源无法核清，报告具体重叠点，不笼统重做或回退 P18。

审查探针是独立诊断，不是完整正式测试集：初次辅助错误和未进入 Provider 的早期对照已保留，不能算作 Engine 缺陷；有效的 native 正反对照在第三至第五轮得到观察。不得修改独立审查原件来制造通过，可复制必要逻辑为本轮正式回归，并把断言改为正确目标行为。

先形成一份精简 Stage Brief，列出四项依赖、实际候选文件、禁止修改范围和验证矩阵。本次用户已批准四项有限补修；该方案不新增义务或扩展边界时，写明后即可实施。

## 2. 四项共同不变量

- SubjectState 是当前主体状态唯一权威；历史事实为 Event；长期变化经原 Evolution/revision。不得建立第二人格、第二事实源或平行请求账本。
- 内部 Thought、Emotion、Desire、Will、Decision 与外部执行许可/执行事实分开。现实门不能因为某个行动不允许执行，就强制改掉主体内心。
- 内部数据仍需要身份、合法来源、证据、生命周期、版本和并发核验。不是所有任意提案都必须落盘，也不允许 Provider 绕过引擎直接写人格。
- Permission、Resource、Recoverability、Reality Boundary、World Adapter、幂等与当前授权复查保留；未知外部结果仍先核实，不得无凭据重发或冒充未执行/已成功。
- 内心变化在后续获得真实执行结果后可以自然重新评估，但不能把“执行拒绝”直接硬映射为欲望消失、情绪归零或意志放弃。
- 不增加人格、情绪、普通表达或主体意愿的内容审查；不以哲学判断缩减项目目标。
- 原长期目标不变：无用户消息也能持续托管并推进有根据的内部活动；资源等待、休息和暂缓应有明确语义，不等于无声停止主体运行。已存在的 STOP、主体暂停/归档和用户控制仍有效。

## 3. R1：内部心智提交与现实执行结果解耦

已定位：

- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/wake_perception_thinking_action_service.py`：`_continue_mind` 先 dispatch，后 Evolution。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/continuity_core_service.py`：`after_action` 对未完成执行抛异常；`CoreDecisionPolicy.choose` 把旧 gate approval 放在后续 ActionChoice 形成之前。

目标：同一轮中，合法且不依赖外部成功事实的内部变化，不能仅因现实行动被拒绝、等待或结果未知而无法提交。主体意图、内部决定、内部提交状态、外部许可与外部执行事实分别可追溯。

要求：

1. 保留已形成的意图及依据；可以生成可审计的候选/拒绝记录，不代表获得执行权。
2. 独立内部变化仍经原写入链提交；声称“动作已成功/已满足”的状态只能由真实回执支持，不能提前提交。
3. 外部拒绝保持零效果、零实际扣费；UNKNOWN 保持未知，不因内部提交完成而改写为外部成功。
4. 未决外部行动不得永久绑住主体其他独立认知；不能借新的认知 ID 偷偷重发同一副作用。
5. 不是简单交换两行：处理内部 revision 推进后的 Context/Choice 绑定、同一 ThinkSession 恢复和当前授权复查；不能取消 stale/CAS 检查来获得通过。

最小回归：允许/拒绝正反对照；权限中途撤回；资源不足；已知未执行与结果未知；内部提交前后中断；外部效果后回执前中断；重启/重放；内部状态与外部结果分别正确、无重复效果/扣费/revision；旧 C1 与 P18 native 路径均验证。

## 4. R2：移除 target 名称子串决定风险

已定位：

- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_evaluators.py`：`RiskEvaluator.evaluate` 中的 `"critical" in intent.target.lower()`。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_service.py`：两个现有评估入口。

目标：同样语义和可信资产属性的操作，不因显示名称、subject_id 或路径里出现 critical/noncritical 而改变风险。

要求：

1. 风险依据应来自现有可信操作/能力/资产边界和明确风险规则，不是目标名称，也不是模型自报 LOW。
2. 不顺便把全部 USE_TOOL 降为 LOW，不放宽既有真实高风险、权限、确认或资源条件。
3. 不提前建设整套 P21 资产注册体系；最小替代设计不能完成时说明具体缺失的可信信息，不能以关键词或默认放行填空。
4. 已有关键资产保护若依赖旧规则，先识别真实保护目的并保留，不盲目删除后声称风险问题全部解决。

最小回归：普通名字/critical/noncritical 的同语义改名对照；内部 UPDATE_STATE；外部只读/写入按真实规则处理；已明确的 HIGH/CRITICAL 仍满足原确认/拒绝条件；相关旧测试若把错误启发式当目标，保留旧测试证据、明确修正理由并增加等效真实风险保护断言，不得静默删测。

## 5. R3：补齐长期情感倾向与长期 Will 成长

已定位：

- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/dynamic_mind.py`：`MindState.dispositions / will`。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py`：`advance / deliberate`。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py`：正常内部成长路径。

目标：不只会保存夹具预填的倾向和承诺；正常 C1 必须能依据经历与内部评估形成、保持、重新理解或修订相应提案，并通过既有持久化链影响下一轮认知。

先区分：短期 Episode、长期 disposition、欲望、意志/承诺、关系解释、叙事与客观事实。只补当前缺失的生产者与跨轮使用，复用既有结构，不重做整个 Learning。

要求：

1. dispositions 的形成/修订有当前合法证据、经历根和内部理解依据；单次事件或累计分数不能直接制造 LOVE/HATE，重复根不能冒充独立经历。
2. 旧 Will 的有效承诺、支持与相反依据进入下一轮评估；保持或改变都能说明依据。不能每轮无条件重建成固定模板，也不能“永远复制旧承诺”而禁止自然变化。
3. 相反心理可共存；不能靠简单选最大值消除矛盾，不按执行许可修饰心理内容。
4. 经原 Action/Evolution/revision 保存、恢复、追踪；Provider 不直接提交整份最终人格。已有四字段 Learning 和独立 rollback 机制保留。
5. 不把用户对代码返修的确认转换成对正式主体人格/关系的修改授权；本轮行为测试只使用隔离主体。
6. 若为此必须改正式 Schema、扩大公共写入权限或重定固化授权，提交最小方案请用户另行确认，不以“R3 已授权”为理由扩大。

最小回归：正常经历→认知→倾向/意志提案→Evolution→重启→后续评估的完整正向链；证据重复/撤回/失效；无关新证据不应抹去原承诺；有关新理解可以修订；相反心理并存；变化真实影响后续理由/选择，而非仅把字符串或 hash 变得不同。不得只通过直接构造已完成的 dispositions 来证明自主形成。

## 6. R4：修复驱力饱和后的认知任务盲区

已定位：

- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py`：`needs` 主要依据 drives delta。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/persistent_runtime_service.py`：常驻宿主与既有调度恢复。

目标：驱力数值稳定不等于主体已经决定不再思考。既有未决关注、承诺和内部任务应能在适当时机提出有界复议需求。

要求：

1. 调度依据来自已形成的内部状态和明确复议理由，不由 Scheduler 创造欲望、情绪或行动目标。
2. 支持稳定/接近饱和/完全饱和驱力且无新外部消息的场景；不能仅在数值发生足够变化时才有认知任务。
3. 尊重主体休息、暂缓、放弃及用户暂停/STOP；区分未来复议与已明确终止，不能用“持续运行”强制永远做同一件事。
4. 保留最低间隔、背压、防饥饿、预算和防忙循环；资源不足保留可恢复需求，不捏造没有欲望，也不增加费用上限。
5. 同根任务在排队、执行、UNKNOWN 或等待回执时不得被重复派发；内部认知继续不等于旧现实行动可再执行。

最小回归：稳定驱力+未决关注可提出新认知；无需外部 Observation；正常逐步运行进入稳定区的路径与合成饱和状态都覆盖；休息/暂缓正确；无待决需求不强制调用 Provider；预算耗尽与恢复；跨进程续接；PAUSE/STOP 不被自动重启；无任务风暴和重复效果。

## 7. 实施与验证顺序

建议按 R1 → R2 → R3 → R4 在同一返修批次完成。若依赖分析支持更小的顺序调整，记录理由即可；不要多个执行者同时改同一状态/恢复链。

1. 固定开工身份和保护基线，保留修前反例；若反例未复现，说明为何，不照抄结论冒称已复现。
2. 每组先定点修复并通过正反对照，再推进下一组；不为每个小改动重跑整个工程。
3. 四组合并后做交叉验证：长期承诺在现实拒绝后仍存在并可继续被评估；驱力稳定后仍可有合法内部认知；现实效果仍严格受控；恢复不重复记录或效果。
4. 覆盖直接受影响的 P14/P15/P17/P18 及原 C1、资源、学习、执行恢复、权限与相关存储兼容；固定最终代码/测试身份后做完整回归。
5. 若最终回归发现真实失败，保留原现场，定位并修复范围内问题后补足必要验证。不得反复盲跑直到偶然全绿，也不得因“只跑一次全量”而交付未经验证的新最终代码。
6. 范围内普通实现错误无需再次索取同样授权；超范围或行为语义需新增用户选择时才请确认。不能把所有新失败直接算进旧 F1/H1/F2。
7. 软件/额度中断时写明 checkpoint、源码 hash、运行命令/日志/进程身份；接续先检查原测试是否仍在运行，不启动重叠测试，不清理其他任务进程。未完成、被中断与已失败分开记录。

## 8. 交付、档案与停止条件

只同步直接相关的报告、测试矩阵/索引和必要决策增量，不批量改写无关阶段的历史状态，不为每个微小步骤复制整套档案。

交付必须包含：

- R1—R4 各自的真实根因、修改文件/函数、为什么不改变项目初衷、兼容影响。
- 修前反例、修后正反验证、交叉验证、受影响兼容及最终完整回归的命令、原始输出、退出码、耗时和精确计数；有包含关系的结果不相加。
- 特别区分：内部意图、合法内部提交、平台拒绝、已知未执行、执行未知、实际效果；不以过程存活代替认知持续性的证据。
- 当前源/测试身份与最终实跑绑定；保护文件、规划原件、正式数据、原排除材料核对结果。
- 精确待提交清单及明确排除清单、未解决事项；不把测试/日志数量或新增文件数量当完成度。

旧验收事实与 D-073 保留。本轮作为新的返修批次记录，完成后最高状态为 IMPLEMENTED_NOT_ACCEPTED，等待独立复核；不得自行登记新的用户验收、关闭未经独立确认的本轮阻断，或宣称已经 push。

本轮停止点：四项完成并验证后交回独立复核；若确有需新授权的阻断，说明已完成项、证据和最小待确认差异。任何情况下都不进入 P19，不提交或 push。

用户的意思是一次授权尽力把这四组问题合并修完整，不是保证一次测试就全部通过，也不是无限扩大工程范围。
