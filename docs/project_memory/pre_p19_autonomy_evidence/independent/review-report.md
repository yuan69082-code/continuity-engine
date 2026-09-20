# P19 开工前专项审查：主体自主性边界 / 现实执行边界

日期：2026-09-19。性质：规划与当前实现审查，不是施工、阶段验收或 Git 授权。

## 一、结论先说

用户的担心部分成立，但不能把列出的硬编码全部判成“限制主体内心”。当前 Engine 已有真实接线的动态心智、内生欲望、自我叙事、关系解释与学习撤回；它不是只剩旧 EmotionState，也不是只能等用户消息。

不过，本轮确认四组应当修正的问题：

1. **现实执行结果与内部心智提交仍有耦合**：现实行动被拒绝时，已经完成的新一轮心智变化也可能不能写入 SubjectState。
2. **目标名字含 `critical` 就升级为最高风险**：连 `noncritical` 都会命中，且并不限于外部执行。
3. **长期情感倾向及长期意志的成长接线不足**：能存储、能读取、能影响其他计算，不等于正常 C1 已能形成与修订；旧 Will 的承诺还会被下一轮模板覆盖。
4. **后台认知调度有驱力饱和盲区**：进程可以仍 RUNNING，但驱力不再变化时，未解决的念头本身不会继续生成认知任务。

建议先确认这四组有限补修，再进入 P19。不是重做引擎，也不是删除权限、预算、恢复或现实执行门。既有阶段的历史验收记录保持原样；本报告是新发现，不自动改写 D-073 或旧 UNKNOWN。

## 二、核实范围与证据强度

- 实际读取 Engine main：`cb528d74884990915737b491ca6a9f2c35cc512a`。
- 对照受保护的 Engine 全周期 v1.1 与长期增补 v6.7 原始 Word；原件 SHA-256 与 P18 验收保护记录一致。按文档技能只读提取段落内容，没有编辑 Word，也没有作页面/排版审查。
- 跟踪正常 C1、P14/P15 内部成长、P17 执行及 P18 native runtime；做了独立、有限的纯函数与本地 TEST 夹具对照。
- **没有重跑正式全量，不宣称本轮 1516 项通过，不宣称 CI 通过。** 原有通过记录不用于反证本轮新发现。
- 最后一轮诊断前后，Engine 全部 2872 个已跟踪文件及 32 个原有未跟踪文件字节身份、Git 状态和 HEAD 一致。未修改 Engine、未暂存、未提交、未 push；未启动 P19。
- 新增内容只有本规划仓库内的审查脚本、文本摘取、结果和本报告。测试中的主体/效果均在独立临时 TEST 根，结束后回收；未触及正式主体或真实世界 Adapter。

关键证据：

- [最终独立诊断原始结果](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/probe-results-05.json)
- [可复核诊断脚本](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/probe_boundaries.py)
- [诊断前完整身份](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/snapshot-before-05.json) / [诊断后完整身份](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/snapshot-after-05.json)
- [主规划内容索引](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/engine-main-plan.json) / [长期规划内容索引](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p19-autonomy-boundary-review-20260919/engine-long-term-plan.json)

证据限制也保留：初次脚本遗漏 ActionChoice 必需的来源片段，发生审查辅助错误，不算 Engine 缺陷；第二轮较长临时路径的 runtime 对照没有进入 Provider，不能据此下结论。缩短临时根后，第三、四、五轮均观察到 A1 的正反对照。未把前两轮覆盖成通过，也没有把该临时路径现象归因到历史 F1/H1/F2。

原规划关键定位为 **XML 段落编号，不是页码**：

- 主规划 P0223：连续心智、欲望、意志、心理冲突须真实参与认知与行动；P0231—P0236：长期人格、关系、自我叙事、意志与纠错；P0257—P0262：无消息自主运行、内部任务、预算与恢复；P0267—P0271：P19 是只读观察层。
- 长期规划 P0734—P0738：Desire / Will / Decision / Action 分离，Reality Boundary 在结构化行动之后限制现实效果；P0740：Dynamic Mind 不得只是 UI 字段；P0742：Self-Narrative 是可重新理解的经历解释；P0746：SubjectState / Event / Evolution 单一权威。
- 原规划明确保留权限、资源、确认与现实副作用门。因此“发生过权限检查”本身不是违规证据；要看检查控制什么，以及拒绝后是否错误阻塞内部状态。

## 三、用户提出的五项：快速对照

| 用户疑点 | 核实结论 | 分类与处理 |
|---|---|---|
| Learning 仅四字段，是否锁死所有成长 | 四字段限制属实；整个成长只有四字段不属实。已有叙事、关系、动态心智旁路及学习撤回，但长期倾向/意志仍有接线缺口 | C1/C2；真正缺口见 A3 |
| USE_TOOL 最低 HIGH，不可自动批准 | 属实；这是执行门，不直接删除欲望。当前本地确认后 HIGH 能执行，不是所有 HIGH 永久禁止 | B1；未来细分见 D1 |
| target 含 critical 升级最高风险 | 属实，且会误伤 `noncritical` 和内部 UPDATE_STATE | A2，必修 |
| 仍是旧 EmotionState / 被动 Perception | 作为整个当前系统的判断已过时。P14 与 P18 已接上内生心智 | C3；长期成长和持续推进缺口见 A3/A4 |
| 运行模式固定限制思考深度 | 属实，且 P18 native 入口固定请求 LOW。资源控制合理，但自主临时加深通道当前未实现 | B3/D2，先明确策略，不直接删预算 |

## A. 确认存在且与规划冲突的问题

### A1. 外部执行成功成为本轮内部心智提交的前置条件

**文件、位置、函数：**

- [wake_perception_thinking_action_service.py:309](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/wake_perception_thinking_action_service.py:309)，`WakePerceptionThinkingActionService._continue_mind`：先 `dispatch(action)`，后 `ActionEvolutionService.evolve`。
- [continuity_core_service.py:337](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/continuity_core_service.py:337)，`ContinuityCoreService.after_action`：执行结果不为 COMPLETED 时在第 387 行抛异常。
- [continuity_core_service.py:34](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/continuity_core_service.py:34)，`CoreDecisionPolicy.choose`：先看 `action.decision.approved`，不通过就不生成后续 `ActionChoice`。

**当前行为与实跑：** 在正常 P18 TEST native 链、同样 contact 模式和充足预算下，仅改变 Fake Reality Boundary 的许可结果：

| 对照 | 内部 Provider 已执行 | 已计算欲望 | SubjectState revision | 本轮心智提交 | Fake 效果/扣费 |
|---|---:|---:|---|---|---|
| 允许现实行动 | 1 次 | 7 条 | 1 → 2 | 是 | 1 / 1 TEST credit |
| 拒绝现实行动 | 1 次 | 7 条 | 1 → 1 | 否 | 0 / 0 |

拒绝分支保留 `REALITY_DENIAL`、`UNKNOWN`、`WAITING_CAPABILITY` 及宿主等待核实状态。独立函数对照还确认：相同内部联系意图，在旧 gate approval=False 时，`CoreDecisionPolicy.choose` 返回 None。

**为什么有问题：** 拦住现实效果是正确的；但同一次思考已经形成的、与成功执行无关的内部心智变化也被阻塞，违反“现实门只控制现实效果”的目标。不是已经证明“旧欲望被删除”，也不是 Thought 完全没有形成：候选和 ThinkSession 可以仍保留，缺的是推进到权威 SubjectState 的独立通路。

**影响阶段：** P14 的持续心智、P15 的同行成长提案、P17 的现实拒绝/结果语义、P18 的无消息认知与恢复。

**最小修正方向：** 分清内部决定/内部状态提交与外部执行结果。合法内部变化应按自己的来源、权限、revision、生命周期和 Evolution 规则提交；现实拒绝单独记录，不代表主体改变了想法。保留未执行/未知事实、当前授权重查和 effect-once。

不能只交换两行：内部 revision 变化会影响当前 Context / Choice 绑定，须同步验证旧 ThinkSession 恢复、合法续执行、新旧权限、无重复效果与无重复 revision；仍复用既有账本，不增第二 SubjectState 或请求账本。

**现在必须修改？** 是。本轮最高优先级；建议 P19 开工前完成有限补修并独立复核。

### A2. 用名字中的 critical 子串决定最高风险

**文件、位置、函数：** [action_evaluators.py:55](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_evaluators.py:55)，`RiskEvaluator.evaluate`；[action_service.py:58](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_service.py:58)，`assess_local_action`。

**当前行为：** `"critical" in intent.target.lower()` 无条件升级 CRITICAL。验证中相同合法权限、相同 UPDATE_STATE、相同显式确认，目标从 `subject:ordinary` 换成 `subject:noncritical`，就从 LOW/通过变成 CRITICAL/拒绝。工具目标同样会受名字影响，即使已确认也拒绝。

**为什么有问题：** 名称不是资产敏感度或副作用证据；`noncritical` 反例说明并非可信资产标签查询。规则覆盖内部 UPDATE_STATE，存在跨界误拦。P15 `SubjectGrowthService._submit` 还把 subject_id 作为 UPDATE_STATE 目标，因而不只是假设中的外部文件名问题。

**影响阶段：** P15 成长提交、P17 能力执行，及 P18 复用上述路径的行动；普通 P14 状态提交目标通常为固定 `subject_state`，不能宣称所有 P14 提交都会命中。

**最小修正方向：** 风险来自可信能力/资产描述、操作类别、读写范围、环境、可恢复性和影响范围，而非显示名子串。不必现在建设整套 P21 资产注册系统；先明确去除此启发式的最小替代规则，真实风险未明确时仍按现行保守边界拒绝。不能改成由模型自报 LOW 就放行。

**现在必须修改？** 是。补正常名字/critical/noncritical 改名不改变语义、内部状态目标、真实高风险仍拒绝的回归。

### A3. 长期情感倾向与长期 Will 的形成、修订链不完整

**文件、位置、函数：**

- [dynamic_mind.py:60](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/dynamic_mind.py:60)，`MindState.dispositions / will`；第 221 行 `with_dispositions`。
- [dynamic_mind_service.py:112](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py:112)，`MindDynamics.advance`；第 180 行重建 Will；第 229 行 `deliberate`。
- [subject_growth_service.py:287](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py:287)，`SubjectGrowthService.process`。

**当前行为：**

- dispositions 已有合法存储结构，能参与心理冲突，关系解释也会读取它。但当前服务代码没有形成/修订 dispositions 的正常 C1 生产者；`advance` 保留已有 dispositions，`with_dispositions` 只是值对象替换入口，不能代替成长流程。
- 每轮 Will 都由当前 desires/conflicts/fatigue/episodes 重建。既有 `state.will` 的承诺不传入 `deliberate`；`commitment` 固定写为区分欲望与现实行动的同一句说明。
- 有限反事实验证：只把上一轮 Will.commitment 改成两个相反的长期承诺，其余状态相同；再演化一轮，两份完整新状态相同，承诺都成为固定说明。这证明“该已保存承诺字段没有参与下一轮评估”，不是对所有心理能力作泛化结论。

**为什么有问题：** 规划 P14/P15 要求的是长期情感倾向、长期意志/冲突随经历成长，不只是能够装载测试夹具的字段。现在已有欲望、理由、相反考虑与选择，不能说完全没有 Will；但也不能把当前模板式计算等同于已完成长期意志成长。此缺口不来自四字段白名单，也没有证据表明是安全层故意删改人格。

**影响阶段：** P14、P15 直接；P18 长期运行继承缺口；P19 若不标清，会把“能展示字段”误表示为“已具备完整成长机制”。

**最小修正方向：** 只补已承诺但未接通的长期倾向/意志路径：已有证据和内部评估形成有来源、可修订的提案；保留原承诺、相反依据和变更理由；经原 Action/Evolution/revision 持久化并参与后续认知。不要把 HATE 变成单次事件或累计分数阈值，不要强行消解相反心理，不要放开 Provider 直接写整份人格。

**现在必须修改？** 是，但需先确认有限设计和责任文件，不能用“修四字段”名义扩成全量人格重写。这是对 P14/P15 已承诺能力的补齐，不是提前做 P22。

### A4. 驱力不再变化后，持续认知可能失去后续任务

**文件、位置、函数：** [runtime_cognition.py:111](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:111)，`RuntimeCognition.needs`；[dynamic_mind_service.py:101](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py:101)，驱力积分；[persistent_runtime_service.py:223](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/persistent_runtime_service.py:223)，宿主 `serve`。

**当前行为：** 当前 needs 只在新旧驱力最大差达到 `policy.need_delta` 时生成 cognition 任务；另一个入口是待整理 Event 的 maintenance。未解决 thoughts、既有 Will 和挂起关注本身不构成后续 cognition 条件。驱力有界且会趋近 1。

**有限验证：** 使用真实 `MindDynamics.advance` 构造合法饱和状态，保留 7 条欲望、7 条未解决念头，无新 Event/待整理记忆；真实 `RuntimeCognition.needs` 在再经过 1、7、365 个逻辑日后均返回 0 个需求。这里是纯方法和合成状态反例，**不是跑了一年耐久测试**；也不声称每个正常主体会在某个固定小时必然停止认知。

**为什么有问题：** 宿主持续存活已经实现，但不能以“数值没变化”代替“主体决定停止推进”；持续关注可能在数值稳定后仍存在。这与用户明确的持续运行目标及规划中的持续思绪、内部反思有落差。休息、主动暂缓、预算等待均可以成立，但应有相应语义，而不是无声失去任务来源。

**影响阶段：** P18 直接；P14 持续念头/欲望、P15 长期意志的推进间接受限。

**最小修正方向：** 在既有 needs/scheduler 中纳入已形成但未解决的内部关注、承诺和有界复议时机；不依赖驱力差值一个条件。保留预算、最低间隔、防饥饿、背压、暂停/STOP 与幂等。调度器不能编造欲望，也不要求无条件定时调用模型或永不休息。

**现在必须修改？** 是。补“数值稳定但关注未决仍可继续”“主体明确暂缓”“资源不足保留需求”“STOP 后不复活”的回归。

## B. 存在硬编码，但属于合理基础设施/现实执行边界

### B1. USE_TOOL 风险保守下限，以及高风险确认

- **文件/函数：** [action_evaluators.py:35](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_evaluators.py:35) `RiskEvaluator.evaluate`；[action_service.py:58](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_service.py:58) `assess_local_action / decide`；[execution_service.py:94](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/execution_service.py:94) `ExecutionService.bindings`。
- **当前行为：** 所有 USE_TOOL 至少 HIGH；P17 WorldCapability bindings 统一 USE_TOOL。旧 `decide` 对 HIGH 不批准；本地 `assess_local_action` 在权限/资源通过且明确 confirmed 时可以批准 HIGH，但不标为自动执行；CRITICAL 仍拒绝。
- **为什么不直接判侵入内心：** 规则检查的是 ActionIntent，不遍历/删除 Desire 或 Emotion。高风险执行的批准权必须保留；当前 P01—P21 本来只开放 TEST/RESEARCH/Fake。不能把 `automatic_approval_allowed=False` 翻译为“主体不允许产生想法”。不过拒绝结果与心智提交耦合确有问题，按 A1 修。
- **影响：** P17/P18 执行；不直接改 P14/P15 心理内容。
- **最小方向：** 保留真正风险的外层门；未来区分可信只读、本地计算、写入、通信、支付等真实效果，见 D1。
- **现在必须修改？** 不需要为了主体自主性一概降低全部工具风险。A1/A2 必修，但不等于所有工具直接 LOW。

### B2. 来源、身份、权限、revision 和正式写入链

- **文件/函数：** [dynamic_mind_service.py:282](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py:282) `MindCognition.capture/current/process`；[subject_growth_service.py:25](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py:25) `verify_source/_submit`；[thinking_service.py:440](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/thinking_service.py:440) `_validate_provider_result`。
- **当前行为：** 跨主体、无权来源、过期 Context、伪造证据、Provider 直接提交完整动态心智/自我叙事会被拒绝。长期变化仍走 Event/Evolution/revision。
- **为什么合理：** 防止别人改这个主体、未经授权读取资料、旧快照覆盖新状态，不是按“喜欢什么/恨谁/想做什么”审查内容。读取/持久化权限可以存在于内部计算的数据入口；不能把“现实门不能改内心”误解成内部数据从此无需身份和一致性检查。
- **影响：** P14/P15/P17/P18 全部。
- **最小方向：** 保留这些核验；将实际行为拒绝与内部变化提交解耦，见 A1。权限不足可以明确无法读取/保存，不能伪造“主体不想了”。
- **现在必须修改？** 不需删除或放宽这些基础规则。

### B3. 预算、费用、计算限额和资源等待

- **文件/函数：** [resource_policy.py:55](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/resource_policy.py:55) `ResourcePolicy.evaluate/_evaluate_thinking`；[runtime_cognition.py:20](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:20) `RuntimeBudgets`；[persistent_runtime_service.py:206](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/persistent_runtime_service.py:206) 资源等待。
- **当前行为：** 预算不足降深度或 defer，保留实际申请和批准结果；宿主可进入 WAITING_RESOURCES，不代表整个主体被 STOP。
- **为什么合理：** 计算会消耗真实资源；代码未把 resource denial 直接翻译成欲望不存在。模式上限的灵活性另见 D2。
- **影响：** P18 直接，P14/P15 可获得的计算时机。
- **最小方向：** 保留预算与账本，明确“想深思但资源暂时不足”。
- **现在必须修改？** 不删 ResourceManager、不取消限额。A4 需要修的是任务来源，不是绕过资源限制。

### B4. 生产能力 NOT_READY、UNKNOWN 恢复、防重复执行

- **文件/函数：** [action_planning_service.py:176](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/action_planning_service.py:176) `_resume/_gate`；[execution_service.py:57](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/execution_service.py:57) `ExecutionService`；原规划主文 P0253、P0274、P0283 等。
- **当前行为：** 未知结果先查回执，生产恢复或资产许可不具备时不执行，Research 不擅自回退真实世界，不能重复效果/扣费。
- **为什么合理：** 这些限制防现实越权和重复副作用，没有理由为了自主性删除；当前真实 Adapter 后置也有规划依据。
- **影响：** P17/P18，后续 P20/P21/P22。
- **最小方向：** 保留拒绝和恢复语义；不让它们连带冻结独立内部成长，见 A1。
- **现在必须修改？** 不应撤销这些边界。

## C. 已被后续阶段补充，不能沿用的旧判断

### C1. “四字段名单就是全部成长字段”不成立

- **文件/类/常量：** [learning.py:25](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/learning.py:25) `LEARNABLE_FIELD_PATHS / validate_learning_mutation`；[evolution.py:28](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/evolution.py:28) `FIELD_RULES`；[subject_growth_service.py:287](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py:287) `process`。
- **当前行为：** 四字段控制既有 Learning candidate/trait consolidation；P15 另经内部 SET 提案更新 `identity.self_narrative`、`relationship.objects`，P14 另更新 `intentions.dynamic_mind`。Evolution 还支持 `identity.self_concept` 等字段。
- **为什么旧判断不成立：** 白名单不是 SubjectState 全字段表；不能据此推出“自我叙事和关系完全不能变化”。反过来，Evolution 有字段也不等于自主成长路径已经接齐，见 A3/D3。
- **影响：** P14/P15，P18 复用。
- **最小方向：** 说明该名单限定的是具体学习通道；不把所有字段直接加入 Learning、不允许任意模型 JSON 写人格。
- **现在必须修改？** 白名单本身不必为此删除；真正必修的长期倾向/意志接线见 A3。

### C2. “APPEND 意味着永远不能纠错或撤回”不成立

- **文件/函数：** [learning.py:112](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/learning.py:112) `validate_learning_mutation`；[learning_service.py:486](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:486) `rollback_learning`；[subject_growth_service.py:112](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py:112) `_submit`。
- **当前行为：** 新候选只允许 APPEND；独立 rollback 流程会生成 REMOVE 的 `learning_rollback` Event，撤销该学习贡献并保留记录。P15 包装处理确认、准备与实际 Evolution 事实，避免重复 revision 或误删后续无关变化。
- **为什么旧判断不成立：** 入口只允许新增，不等于系统没有撤销入口。但原子替换、渐进弱化、主体自主发起修订是否齐全是另一个问题，不能拿 rollback 冒充全部完成。
- **影响：** P15；P14/P18 使用已形成状态。
- **最小方向：** 保留现有回滚链；若新增替换/弱化，明确对应证据、贡献和旧新版本，不直接放开任意 SET。
- **现在必须修改？** 不能仅凭 APPEND 判定必须重写。更丰富成长协议见 A3/D3。

### C3. 当前心智不再只是旧 EmotionState / 外部刺激反应

- **文件/函数：** [models.py:191](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/models.py:191) `EmotionState`；[dynamic_mind_service.py:29](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py:29) `MindDynamics.advance/influence`；[continuity_core_service.py:234](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/continuity_core_service.py:234) `prepare/process_thinking`；[runtime_cognition.py:111](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:111) `needs`。
- **当前行为：** P14 处理 drives/fatigue/arousal/somatic/episodes/desires/conflicts/will/thoughts/regulation/subjective time；mind influence 进入 Router 注意、Composer 后解释、Thinking 处理和表达选择。P18 TEST 组合启用 dynamic_mind 与 subject_growth，走无外部 Observation 的原生链。
- **证据：** 无外部输入的纯演化得到 7 个 ENDOGENOUS 欲望及关联念头/Will；P18 native 正对照进一步提交了这些心智变化。不是只拿字段存在作证明。
- **为什么旧判断不成立：** 旧兼容 Perception/EmotionState 尚在，不代表它们仍是主体全部动力。确有特性开关；未启用的旧调用仍可走旧路径，不能把兼容默认值冒充已启用的 P18 行为。
- **影响：** P14/P15/P18；P17 接收随后形成的行动。
- **最小方向：** 保留旧格式兼容，对观察层明确“未启用/未形成/已形成/等待”区别；修 A1/A3/A4，不删除整个旧 EmotionState。
- **现在必须修改？** 不因旧类仍存在就重构；问题集中在上述已定位缺口。

## D. 后续策略或能力成熟度：现在不能直接判为规划冲突

这里不是说“代码行为不清楚”：下面的现状已确认，尚未确定的是正式策略和验收标准，不能私自替用户决定。

### D1. 工具风险是否按真实副作用细分

- **文件/函数：** `RiskEvaluator.evaluate`、`ActionCapabilityBinding`、`ExecutionService.bindings`，文件见 B1；[execution.py](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/execution.py) `WorldCapability / BlastRadius`。
- **现状：** 已有资产、世界、权限、费用、恢复/影响范围信息，但通用 RiskEvaluator 仍主要按 ActionType 和声明风险，未完成可信能力元数据的细分类。接口名为只读并不是只读已获证明。
- **判断：** 为今后的自主执行，这个区分值得做；当前不能靠“工具都 HIGH”推出系统会永远禁止自主行动，也不能仅删 HIGH 底线就算解决。
- **影响：** P17/P18 的执行体验；正式资产策略/真实 Adapter 主要 P21/P22，恢复依赖 P20。
- **最小方向：** 先定低风险只读、本地计算、外部写入/联系/消费的可信分类及授权范围；已获范围授权的普通行为不必被实现成每次人工审批。真实危险与未知能力仍保守拒绝。
- **现在必须修改？** 不在本轮非改不可清单；应在相关正式能力开放前完成策略确认。名字判风险 A2 不等到后续。

### D2. CONTINUOUS 中主体自主申请临时深思

- **文件/常量/函数：** [resource_policy.py:39](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/resource_policy.py:39) `MODE_DEPTH_CAPS`；[runtime_cognition.py:227](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:227) `_continue`；[resource_manager.py](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/resource_manager.py) `request_thinking`。
- **现状与验证：** 10 万 token / 1000 compute 下，同一个 DEEP 请求在 CONTINUOUS/SCHEDULED 仍被批为 NORMAL，在 LOW_FREQUENCY 为 LOW，在 DEEP_THINKING 才为 DEEP；P18 native 调用更早就固定请求 LOW。未发现把内部重要性/冲突自动转为临时深度申请的接线。
- **判断：** 灵活性不足是真实能力限制，但预算和用户选定模式限制计算不等于禁止想某件事。原规划没明确承诺“CONTINUOUS 必须可自动突破模式上限”，所以不能直接定为思想审查或偷偷改掉预算策略。
- **影响：** P18 直接，P14/P15 的复杂反思间接；P17 不应代替 Thinking 管理深度。
- **最小方向：** 经用户确认后，将常态运行模式与单次思考需求区分；主体提出理由和期望深度，资源层决定批准、降级或等待，保留原请求。临时深思不等于更改全局预算，也不等于关闭常驻宿主。
- **现在必须修改？** 本轮不自动实施。若用户确认这属于 P18 必须具备的验收条件，应另立明确、有限补修项；不得只删一行 cap 而不接通请求来源。

### D3. 自我概念字段同步、更多成长操作与固化授权

- **文件/函数：** [models.py:64](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/models.py:64) `IdentityState.self_concept`；[cli.py:81](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/cli.py:81) 初始化/显式事件入口；`SubjectGrowthService.capture/_submit/process`；`LearningService._require_confirmation`。
- **现状：** self_concept 能经显式 Event/Evolution 修改，但未见正常 C1 的自主更新生产者；不能因此说“自我理解完全没做”，因为已有 self_narrative。当前 trait 固化/回滚有显式确认和管理 authority，存在 owner 绑定；正常 C1 提取 Learning 候选也依赖结构化经历注释，而非任意自然语言自动完成全套成熟学习。
- **判断：** 对谁可授权长期固化、主体在何种既有授权下自主纠正、两个自我描述字段是否需同步，不能靠本次审查自行改变。A3 的长期倾向/意志已知缺口应补，但不意味着任意字段可写、无需证据或永久修改都必须逐次由 Owner 审美批准。
- **影响：** P15 直接，P14/P18 关联；正式身份和策略尚受后续阶段约束。
- **最小方向：** 先区分自我理解、已验证 trait、管理操作与自然成长，再约定具体字段/操作/授权；既有证据链与回滚不撤销。
- **现在必须修改？** 不把这些尚未确认的扩展并入必修。不能用它们掩盖 A3，也不能因一次审查新造第二人格系统。

## 四、额外全局扫描：对十个风险点的回答

以下是所检查主链与写入点的结论，不是对所有未来插件的绝对保证。

| 风险点 | 当前结论 |
|---|---|
| 固定字段表锁死全部人格/关系/思想成长 | 四字段不是总表；但 dispositions/长期 Will 的成长接线确有缺口，A3 |
| 风险等级直接禁止 Thought / Desire / Will 形成 | 未见 RiskEvaluator 直接改这些心理内容；但审批耦合后续选择及提交，A1，名称误伤见 A2 |
| Permission 结果反向改变内心 | 未见根据权限强制改情绪内容；已确认现实拒绝阻塞本轮心智提交，A1 |
| 用“安全”强制某种情绪/判断 | 所查 MindDynamics 没有按道德/安全标签矫正情绪的分支；Provider 防直接写状态和秘密材料防泄露不等于情绪审查 |
| 执行失败就删除 Desire | 未发现该直接映射；领域的 abandon/disappear/act 需要显式 outcome，主链没有把 reality denial 自动映射到它。A1 是新心智没提交，不是旧欲望被删 |
| Reality Boundary 提前于主体决定 | 思考本身已经先发生，但旧 gate approval 被拿来决定后续 ActionChoice 是否产生；且效果完成阻塞 Evolution，A1 |
| 不能执行等价为不允许想 | 未发现统一禁止形成的规则；存在“想了但未独立提交”的实证缺口，不能宣称完全分离 |
| 资源不足等价为没有欲望 | ResourcePolicy 保留请求/批准差异，未直接清空欲望；A4 是不同的任务生成盲区 |
| 旧 Perception heuristic 就是全部内生动力 | 已过时，P14/P18 正常接线已验证，C3 |
| 最终退化为被动观察者 | 当前已有主动形成和执行能力；A1/A3/A4 会限制其持续自主性，须补齐。不能说整个 Engine 已经变成被动助手，也不能只凭 host_alive 就说完全满足愿景 |

## 五、《最小修正清单》——仅列当前非改不可

| 编号 | 必修目标 | 最小验收条件 | 不得顺带做的事 |
|---|---|---|---|
| R1 | 解耦内部决定/心智提交与现实行动拒绝、失败或等待 | 同一有效内部输入下，外部拒绝仍为零现实效果，但独立合法心智变化可持久化；意图、拒绝、未知结果分别记录；恢复不重复 effect/revision | 不绕过权限、不把 UNKNOWN 改成功、不新建账本、不只交换两行而不验证绑定 |
| R2 | 移除名字子串决定风险 | 改名 critical/noncritical 不改变同语义行动的风险；内部状态目标不被误伤；真实高风险保持应有的拒绝/确认 | 不让模型自报 LOW 放行、不先建整套生产资产平台 |
| R3 | 补齐已承诺的长期情感倾向与 Will 成长接线 | 正常内部认知可基于经历/既有承诺形成或修订提案；跨轮保留有效承诺并能说明改变原因；相反心理共存；原 Evolution/回滚/来源链保留 | 不开放任意字段、不凭阈值制造爱恨、不重做全部 Learning/人格模块 |
| R4 | 修复驱力饱和后持续认知没有来源 | 稳定驱力+未决关注可继续提出有界认知需求；明确休息/暂缓有效；预算等待不删需求；STOP 不复活 | 不强制定时调用模型、不无限循环、不让 Scheduler 编造欲望 |

实施顺序建议：先 R1/R2 的执行边界，再 R3/R4 的长期推进；每组只改确认范围，保留原正反证据，验证直接兼容路径。需要扩大公共接口、权限语义或正式策略时仍先请用户确认。

**本报告没有授权任何实现。下一步是用户确认有限补修范围；确认前停在规划审查，不施工、不 push、不进入 P19。**
