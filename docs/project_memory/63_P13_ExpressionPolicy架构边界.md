<!-- P13_ACCEPTED_START -->
> P13 用户正式验收（2026-09-08，D-063）：P00—P13 ACCEPTED；P13 / Engine side / P13-01—P13-12 ACCEPTED；P13 Vio dependency=NONE；P14—P23 NOT_STARTED。现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示本轮已发现的 R1/R2 阻断经独立复核闭合并由用户确认验收。
>
> 监工独立实跑：原七项 7 PASS（3.832 秒）、P13 三模块 59 PASS（55.614 秒）、新增相邻检查 5 PASS（3.070 秒），均无 SKIP/FAIL/ERROR；59项含七项正式化版本，不相加为互斥覆盖数。全量仅核验引用施工1070项：1069 PASS、1既有 Windows symlink 1314 SKIP、0 FAIL/ERROR；stderr 621.987秒、结构化621.988秒是同一轮。本次纯档案归档未重跑测试。
>
> [验收依据、未提交版本身份及审计入口](P13_用户正式验收_20260908.md)。当前 HEAD 仍为 P12 checkpoint，P13 已验收源码由212文件 hash 标识、尚未提交；验收不等于提交或生产能力开放。下方历次施工/送审状态、PRESENT、FAIL/ERROR/SKIP、辅助错误、审批拒绝和 P09 segment 10 UNKNOWN 均为原样保留的历史。Git 操作及 P14 均须用户另行授权。
<!-- P13_ACCEPTED_END -->

# P13 Expression Policy Stage Brief

## STAGE

2026-09-08，P12 已由 D-061 正式验收；用户通过规划任务明确授权 P13 Engine 独立施工、测试和档案同步。P13 / Engine side / P13-01—12 = IN_PROGRESS，Vio dependency=NONE。不开 P14，不自行验收，不执行 Git 写操作。

## SOURCE OF TRUTH

用户最新授权优先；其次为三份 2026-08-26 同步规划、当前 D-061/P00 基线和实际正常 C1 实现。只读读取正文及表格的 [规划源及有序内容](p13_evidence/planning-read.json) 和 [开工 hash/测试身份](p13_evidence/before.json) 已保存。主规划 181—188 为 P13 施工卡，272—282 统一门，347—416 Override/Keep；v6.7 的 44—49、112—118、273—281、310—318、376—384、458—470、512—513 是直接相关段落（编号为本次 OOXML 非空块零基索引，不冒称原文段号）。三份源文件不得保存修改。

## ORIGINAL REQUIREMENTS

Engine 根据已经形成的主体决定及现有状态、关系、Context 选择表达策略，覆盖 RESPOND、SILENCE、REFUSE、QUESTION、CONFRONT、DEFER、PURSUE。上文七模式优先于后文独立施工边界六模式摘列。Engine 内持久化结构化决定和最终表达产物，不依赖 Vio、assistant Message 或通知。每次选择有可审计依据；未批准 UPDATE_STATE 时 revision 不变。

## V6.7 DETAILS

Thinking / Engine 决定内容及态度，Expression 仅处理措辞、语气、强度、篇幅和呈现。它不能重新判断事实、把愤怒归一化为友好、反转拒绝、改关系/Memory/人格或 EvolutionProposal。主体沉默、主体拒绝、平台拒绝、生成失败、等待/恢复分别标识。现有模型能力只形成 Thinking 输入结果；表达物化使用受约束的本地纯函数 Port，不引入第二次 model.generate 或外部调用。任意自由改写的等义性证明不在本地确定性保证范围内。

## AMENDMENT OVERRIDES

保留简单 Direct / 复杂 Optional Planner、唯一 E5-A 请求通道。Expression 的 PURSUE/DEFER 是表达意图，不证明执行、计划完成或通知送达。Scheduler 只供计算机会；本阶段不新增调度任务或常驻运行时。P12 生命周期继续通过原 Router/Composer exact 来源检查传播。各阶段 Engine 独立，生产连接仍未就绪。

## KEEP RULES

SubjectState 唯一主体 Authority；Event、Timeline、Memory 各守原职责；Action Gate / Evolution / revision 唯一合法状态变化链。保留来源、版本、hash、provenance、当前权限及失效传播。Snapshot/Branch 仅 TEST/RESEARCH。真实已发生的 Action/Evolution 先核实原事实，之后才能判断当前表达是否可再次消费；过期不能授权新工作，也不能抹去旧事实。六 Schema/25 冻结边界/正式数据/版本不变。

## DEPENDENCIES

现有 ContinuityInteractionService 正常 submit/query/recovery，ThinkingResult/ThinkSession，C1 Context/Gates/current，Action 与 E5-A，原 JsonIntegrationResultLedger 的 operation journal。内部可选字段保持旧序列化字节含义和关闭 Gate 行为。最终表达与其 Engine 决定保存在原 operation 的 domain checkpoint；不新建请求账本或状态存储。

输入：已完成 ThinkSession 的正文、可选结构化表达意图、原 Action 决定、同主体/环境的已组装 Context 及其来源身份、当前 SubjectState 的既有表达/关系偏好和简化情绪投影。未提供显式意图的旧 Thinking 使用其既有等待标志/默认回应；不从聊天文本猜测新心理内容。

输出：模式、状态、来源/身份绑定、受限呈现参数及最终正文。SILENCE 为真实空表达；平台拒绝不冒称主体 REFUSE。表现 Port 只能原样引用已形成的正文并选择 Engine 允许的格式，不得提交另一段正文、另一模式或隐藏推理。Trace 只含身份/hash、选择理由码、样式与来源索引，不能复制正文秘密。

## NOT READY

Vio/生产展示、生产通知、任意生产 Provider 的 exactly-once、任意自由文本改写的语义等价保证、Dynamic Mind/P14、Execution Engine/P17、Persistent Runtime 均 NOT_READY。P12 自动清理策略和物理擦除仍关闭；不把 TEST 数值设为生产政策。

## FILES ALLOWED

运行文件仅以下范围，按需要最小实现：

- `src/continuity_engine/domain/expression.py`（新内部类型）。
- `src/continuity_engine/services/expression_policy_service.py`、`expression_ports.py`（新）。
- `src/continuity_engine/domain/thinking.py`、`continuity_core.py`、`integration_results.py`（可选内部绑定/恢复字段）。
- `src/continuity_engine/services/continuity_core_service.py`、`continuity_interaction_service.py`（正常链及当前重验）。
- `src/continuity_engine/testing/p13_expression_fixture.py`（新，复用现有 P01/P08/P09/P12 隔离）。
- `tests/test_p13_expression_policy.py`、`tests/test_p13_expression_recovery.py`（新）；必要的直接兼容回归优先纳入这两文件，不改旧断言。

档案：63—66 P13 专题、`p13_evidence/` 的真实运行/审计证据与必要复现脚本，README、00/01/02/03/04/05 两份/06/07/10/11/12/13 索引、CHANGELOG、工程总档案；P12 59—62 与验收入口仅纯档案，归属 D-061。[P12 验收文件分类](p13_evidence/p12-acceptance-paths.json)。

档案核对补记（全量运行期间，未改源码）：P00 的 11/12 总表仍保留此前 P10/P11 时点的状态，属于现行导航同步的遗漏。新增本轮现行导览并标明原状态表为历史快照；不改冻结规划要求或旧测试数字。此调整仅补齐已授权的档案/索引范围。

## FILES FORBIDDEN

六份外部 Schema、25 项冻结文件（包含全部 interfaces 与 pyproject）、正式七文件、三规划源、版本 0.1.0、Assistant、31 个 P10 未跟踪辅助脚本、所有旧原始证据。不得改 Git 元数据、分支、remote，或新建其他账本/Authority。不得因实现便利扩修旧阶段缺陷。

## TESTS REQUIRED

先保存新行为缺口的真实失败，再运行七模式、正文/决定不可反转、状态/关系/情绪样式、拒绝与零副作用、Gate-off 无额外读取/写入/Port 调用、损坏/缺失绑定、跨主体环境、当前 ACL/Context/P12 失效、崩溃重启/重复结果/事实恢复、原模型 E5-A、Direct/Planner、合法 Evolution 组合以及可运行 Golden。后续一次完整稳定回归，原 1011 身份保留，SKIP 单列。所有输出、源码 hash 和首次错误留存；只档案变化不重跑全量。最后 AST/链接/敏感内容/diff 检查和全部保护 hash 复核。

## PLANNING CONFLICT

NONE（开工核对）。实际发现超出授权的旧缺陷、冻结变化或未解决矛盾时停止对应项并据实登记。当前只是施工范围确认，不预填实现或测试 PASS。

## R1/R2 返修边界补记

此次只改 domain/expression.py、services/expression_policy_service.py、services/continuity_interaction_service.py、testing/p13_expression_fixture.py，并新增 tests/test_p13_review_regressions.py；档案新增 p13_repair_evidence/ 与返修入口，必要导航同步。既有 FILES FORBIDDEN 全部继续适用。上文完整 SubjectState 偏好的初版实现描述已由本次授权投影边界替代；不改用户权限政策。 本轮 P13 专项 59 PASS、0 SKIP/FAIL/ERROR，79.325 秒；直接兼容 445 项：444 PASS、1 既有 SKIP，492.606 秒；最终全量 1070 项：1069 PASS、1 既有 SKIP、0 FAIL/ERROR，621.988 秒。 [逐项证据](P13_独立复核返修_R1-R2.md)。当前 EVIDENCE_CONFLICT=PRESENT，待规划侧复核；未创建 P13 验收决定。

## 2026-09-08 P13 用户正式验收补记（D-063）

本Stage Brief及其返修边界对应的Engine实现已由D-063验收。原IN_PROGRESS、NOT_READY及范围说明保留为开工/施工历史；生产NOT_READY能力不因验收开放。 [正式验收与证据](P13_用户正式验收_20260908.md)。本次无 Git 写操作，不修改 Assistant，不进入 P14。
