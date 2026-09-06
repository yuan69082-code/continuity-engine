# Continuity Engine

> 当前验收（2026-09-06，D-059）：用户正式接受 R01—R08 整体修复及 R05/R06 补修，现行 ACCEPTED。监工独立实跑 21/21 与 74/74 PASS；完整回归引用经身份核验的修复方 894 项结果（893 PASS、1 既有 SKIP、0 FAIL/ERROR，425.134 秒），本次未重跑。P00—P11 历史 ACCEPTED；P12—P23 NOT_STARTED；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE，仅关闭本轮已解决阻断。已授权按精确清单完成 Engine 普通提交和推送，完成后停止。[验收矩阵与证据入口](docs/project_memory/P12前整体审查_用户验收与Git收尾.md)。

> 补修完成、验收前历史快照（2026-09-06）：仅补 R05/R06；其他六项独立复核通过成果保留。R05/R06 补修已实现，等待独立复核。正式定点 55/55、原独立探针 21/21 PASS；本轮全量 894 项（893 PASS、1 既有 SKIP、0 FAIL/ERROR，425.134 秒），完整结果见[补修与复核入口](docs/project_memory/P12前整体审查_R05-R06补修与复核入口.md)。P00—P11 历史 ACCEPTED 不变，P12—P23 NOT_STARTED；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT。等待独立复核，不自行验收、不执行 Git 写操作。

> 首轮修复历史快照（2026-09-06，后续独立复核发现 R05/R06 未闭合）：P12 暂停；仅执行整体审查 R01—R08 内部缺陷修复。P00—P11 历史 ACCEPTED 不变，P12—P23 NOT_STARTED。本轮修复已实现，等待独立复核；定点 39/39 PASS，终局全量 878 项（877 PASS、1 既有 SKIP、0 FAIL/ERROR，420.025 秒）；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（审查问题尚待独立复核关闭）。[本轮修复与证据入口](docs/project_memory/P12前整体审查_R01-R08修复与复核入口.md)。

> P11 历史验收快照（D-058）：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-058 已登记用户正式验收。监工独立原反例 2/2 PASS、P11 45/45 PASS（8.371 秒）；39/833 全量等修复前结果继续作为历史保留。本次仅验收归档，不运行全量。[P11 验收入口](docs/project_memory/58_P11_测试索引与验收入口.md#p11-accepted)。

连续性引擎是位于 AI 模型之外的独立连续性层。它与 Vio 平台后端是边界独立、数据库独立的平行系统，通过正式版本化契约协作；Vio 前端只连接 Vio 平台后端。它保存的不是聊天记录，而是主体状态及其随事件发生的连续变化。模型、Tool、MCP 和设备是外部能力，不是主体状态权威。历史 Vio 连接仍受已冻结契约约束；P09 按现行独立规划使用宿主中立 Port，Vio 不是本轮运行依赖。

当前版本为 `0.1.0` 原型，重点是建立可保存、可演化、可审计并受权限与资源约束的连续性内核。它不是已经具备真实自主执行能力的生产 Agent。

## v0.1 能力状态

### 已实现的内部能力

- `SubjectState`：六个状态分区、revision、JSON 保存与重启恢复。
- `Event / Evolution`：Event 分类/来源/证据、occurred/observed/recorded 三时间、内部/来源/关联身份、追加式 correction/revocation、精确幂等与冲突保护；状态变化仍只经 before/after、`StateUpdateRecord`、expected_revision 和 Action Gate/Evolution。
- `Timeline`：只从 Event/StateUpdateRecord 历史重建的只读 UTC 投影，支持确定性排序、范围、first/last、间距、链及来源/分类/correlation 过滤；没有第二 Event Store 或写入权。
- Memory 管理层：P04 在既有检索/影响接口上新增正式 Memory 领域模型、单一原子 JSON `MemoryRepository`、根证据去重、可解释 HOT/WARM/COLD/ARCHIVED 生命周期、追加式纠错传播和可重建 `DerivedSummary`；普通召回排除但不删除 ARCHIVED，正式 provenance 被密封，consolidation operation、Summary 语义输入与 lineage 来源根均在同一仓储边界加载期验真；Summary 无 Event/StateMutation/SubjectState 写权限。
- Context Router：P05 在结构化 `PerceptionResult` 之后先按 purpose/signals 选择逻辑分区，再在读取前把默认 50（可配置 30—80）的独立 Retrieval Budget 确定性分配给已打开、获授权的 SubjectState、P04 Memory/DerivedSummary、P03 Timeline/Event 及 Engine 本地版本化来源；未打开来源零读取，Memory/Summary 在仓储边界有界查询，Timeline 使用可重验的近期相关稳定窗口。它生成只读 `RoutePlan`、`CandidateManifest` 与 `ContextTrace`；必需来源失败时 Manifest 为空，结果只含稳定引用和原因，不复制正文、不写任何 Store，也不提前实现 P06 Composer。
- Context Composer：P06 只消费 P05 的可消费 Manifest，通过可信 exact resolver 密封 `confirmed_state`、`confirmed_memory`、`derived_summary`、`retrieved_candidate`、`raw_source` 五类 Authority；候选自报标签不能提权。Composer 验证 subject/environment/version/revision/hash 后精确去重、稳定排序，并使用独立 Context Budget 保护 identity/continuity/relationship；必需材料失效或预算不足时失败关闭。`CompositionTrace` 将 Manifest candidate missing、P05 upstream notice 与 Composer 自有 resolver 读取次数分开审计，并保留具体稳定失败原因。输出仍为 Thinking-ready `ComposedContextSnapshot` 和不含正文/秘密的 Trace，不建立 Context Store，不写任何权威状态，P06 单阶段交付不修改 Thinking/E5-A；P09 本轮在既有正常交互服务中接线，见下述 C1 入口。
- Contradiction Detector：P07 只消费完整、可消费且 hash 封印通过的 P06 `ContextCompositionResult`，通过可信结构化 claim resolver 发现 `EPISTEMIC`、`EVIDENTIAL`、`COGNITIVE` 三类矛盾；无法形成可信 claim 的材料保持未评估，LOVE/HATE 等心理矛盾明确排除。检测结果只追加 contested/isolated disposition、verification task、resolution/reopen/supersession 审计与未来 Evolution referral；不选择赢家、不写 SubjectState/Event/Memory/Timeline/P06 snapshot，P07 单阶段交付不进入后续阶段；P09 本轮复用其非权威检测/核实边界。
- Awakening：手动、定时和事件触发的单次唤醒流程，`WakeSession`、`WakeContext` 和确定性决策。
- Perception：只读的确定性感知层，输出关注、时间、关系、记忆影响、观察和内在驱力。
- Thinking：直接接收 `PerceptionResult`，通过 `ThinkSession` 保存摘要、预算、结果和关联信息；模型执行器可插拔。
- Action：生成受权限、风险、资源和 revision 约束的 `ActionDecision` 与 `ActionPlan`，不执行真实动作。
- P08 本地行动：简单 Direct Action 无 Goal/Plan，复杂 Information Need/Action Intent 使用 Optional Planner；内部非模型请求经唯一 E5-A ledger 和既有 Action 权限/风险/资源门、确认、恢复与 Reality Boundary 进入 TEST Fake Adapter。执行成功和执行失败都必须有经绑定 Adapter query 独立核实的回执；无回执 EXPIRED 只是本地停止决定，须 query 明确 NOT_EXECUTED，不能靠 reason/时间/自洽 hash 掩盖已发生成功。历史冲突拒绝消费且不覆盖；当前 Context 失效不阻止原请求已发生事实归账，但仍阻止新执行、重试和后续步骤。旧 model.generate 契约和原 ThinkSession 恢复不变，UNKNOWN/查询异常不盲重试，重复结果不重复 synthetic effect/credit；P08 单阶段交付不含 P09 接线；P09 本轮复用原通道，仍没有生产 Adapter 或 P17 执行引擎。
- Permission：权限连续状态、变化历史、`PermissionContext` 和本地 JSON 恢复。
- Learning：受控候选、证据验证、长期特征、固化/回滚事件和审计历史；不训练模型。
- Resource Management：`ResourceState`、`ResourcePolicy`、`ResourceManager`、确定性预算和资源检查入口。
- 进程内 API：统一请求响应、安全门以及状态、记忆、感知、思考、行动计划、唤醒和聊天入口。
- 本地 HTTP 服务：为调试前端提供静态资源、状态读取和聊天请求。
- 调试前端：最小聊天界面、错误展示、SubjectState 摘要、revision 和最近事件视图。
- 第一轮机器契约基础（Engine E1）：类型化 `ContinuityInteractionRequest`、`message_created` PlatformObservation、`message_version` fact、固定 SubjectBinding fixture，本地 Draft 2020-12 Schema registry、严格校验、RFC 8785 与三项 hash 验证。
- 第一轮持久化基础（Engine E2）：不可变成功结果与四类错误 envelope、最小 `stateProjection`、`stateHash`/`contentHash`、固定 Binding 本地恢复，以及 request/operation/result 跨重启账本和投影唯一性约束。
- 第一轮确定性领域闭环（Engine E3）：独立、test-only、进程内 `ContractTestAdapter`，固定验证顺序，只读外部事实感知，确定性 Memory/Thinking/Reply/Token 替身，真实 Action Gate、Evolution，以及可恢复 operation journal。
- 第一轮共享验收测试桥：`tests/shared/` 下的 test-only JSONL Runner 可由外部测试进程逐行提交真实 v1.1 请求，并直接返回 E3 的成功结果或四类错误 envelope；它不是网络或生产 Adapter。
- 第一轮双方 test-only 共享验收：Vio 的持久化 V1 请求已通过 JSONL Runner 进入真实 Engine E3，结果由 Vio V2 严格验证并持久化；幂等、revision、投影唯一性、四类错误和双方重启恢复均已完成端到端验证。
- 正式本地集成服务（Engine E4）：`ContinuityInteractionService` 是测试与正式 Adapter 共用的唯一处理链；显式 `init` 持久化单一 active SubjectBinding；正式 HTTP/JSON 服务只监听 `127.0.0.1:8766`，提供提交、结果/恢复查询和最小健康检查，并以串行请求、Bearer 服务令牌、1 MiB 上限、默认 10 秒读取超时和“一请求一连接”的严格 JSON 传输边界保护本地入口。domain 子阶段现持久化稳定恢复身份和 Wake/Perception/Thinking checkpoint；重启会复用已完成 WakeSession、ThinkSession/ThinkingResult，并继续沿用稳定 Action、Event、StateUpdateRecord 和最终结果身份。
- 第一阶段正式本地回环连接验收：以 Engine `189441f9bad2a34119b4ef10365a4385ed0949cc` 和 Vio `35780da56c72b822fc018702dfe5e90674ab0fcb` 为基线，Vio 的真实持久化请求已通过 V3 HTTP transport 进入独立运行的 Engine E4；S2/S3 覆盖 completed、not_found、recovery_required、响应丢失以及双方分别或同时重启，稳定身份、领域经历、状态演化、投影和双方账本均未重复。
- Durable Capability 暂停/恢复核心（Engine E5-A）：新增独立版本化 `CapabilityRequest`、`CapabilityResult` 和受约束模型输出 Schema；capability 模式会在 Perception 后持久化请求并将原 ThinkSession 置为 `WAITING_CAPABILITY`，通过同一 E4 HTTP 服务返回 `capability_required`。合法结果在写入 capability ledger 前必须通过严格 Schema、去除首尾空白后的非空输出、身份/hash 和请求时间一致性校验，再经结果解释器、原 ThinkSession、Action Gate 和 ReplyComposer 形成最终结果；operation journal format v3 还持久化已完成的 `ActionExecutionResult`，使 Action 完成后、domain checkpoint 前崩溃也能直接复用而不再次决策。capability ledger 与 journal 共同支持跨重启恢复和精确重放。重复 `init` 会按既有持久化历史选择校验模式，只验证或补齐允许的空 capability ledger，不改写任何身份、状态或历史；`serve` 的模式保护不变。
- P02 Engine 独立模型能力闭环：新增宿主中立 `ModelProvider` Port、可替换 Provider/Model Profile、Engine 内确定性 Fake Provider、持久化 execution/usage/test-credit 账本、1024 单次/10240 每日 synthetic Token 预算门，以及 success、generation/network failure、timeout、`UNKNOWN`、retryable/terminal、cancelled/expired、响应丢失和重启恢复矩阵。UNKNOWN/TIMEOUT 会保存原始模糊事实并以单调 query resolution 恢复；当日剩余额度在调用前下压为 `maximumTokens`；usage/test-credit 每次加载均与唯一成功 Provider fact 逐字段验真。P02 只驱动 E5-A 唯一 durable Capability 通道；Provider 候选必须返回原 ThinkSession，再经过 Thinking、Action 和 ReplyComposer。E4/E5 HTTP 读取正文前拒绝路径已统一使用 response-first、半关闭和固定缓冲短时丢弃收口，认证优先级和外部契约不变。47 项 P02 专项、143 项相关链路及连续三轮 444 项完整回归已通过；用户于 2026-08-29 正式验收 P02，当前为 `ACCEPTED`。没有真实 Provider、网络、API Key、Vio 或真实费用。
- 受控 S4 Capability 链路、S4-R 与首次 S4-Live：Vio V4、双方受控 S4、Vio V5 Conversation、F1、L1 和 Engine S4-R `PASS` 均已完成。2026-08-14 又在不可晋升的独立可销毁沙箱中完成一次真实供应商单次试聊；真实 CapabilityResult 返回原 operation/ThinkSession，经 Engine Thinking、Action Gate 和 ReplyComposer 形成最终表达。本次 `changed=false`、revision `0→0`，没有 Event、StateMutation 或 StateUpdateRecord；它不是通用 Provider 接入、日常使用能力或生产部署。

其中 Memory、Awakening、Thinking、Learning、Resource Management、接口和前端属于“内部结构或本地原型已完成，真实外部集成仍未完成”。Action 完成的是决策规划层，不包含执行层。

### 尚未实现

- 真实 Provider SDK/网络、更多供应商、并发和真实 `UPDATE_STATE` 场景验证；P02 已完成宿主中立 Port、Fake Provider、Profile、故障/恢复和 synthetic 预算闭环，但真实接入后置到 P22。
- 面向日常使用或生产的真实 Provider、密钥治理与可信费用闭环；Engine 仍不读取、不接收或保存供应商 API Key。
- 真实 MCP 连接或 MCP 协议传输。
- ChatGPT、Claude 或其他平台的真实 Skill 接入。
- 外部长期记忆库、向量库或记忆数据库。
- Execution Engine、真实联系用户或真实工具调用。
- 自动后台循环、常驻调度或无限自主运行。
- 真实 Token 计量、账单、计费、购买或支付。
- 生产数据库、用户认证、多租户和生产部署。
- 面向生产和一般用户开放的公共对话 API、前端真实使用链路及运行治理；Vio V5/F1 当前完成的是固定本地受控链路。
- 面向生产部署的 Integration Adapter、TLS/反向代理、生产认证、多租户和运行监控。

`ContinuityMCPAdapter`、`SkillAdapter`、`ThinkingProvider` 和 Memory 端口只是可插拔接口或适配边界，不能视为对应外部能力已经接入。

## Vio 连接契约状态

2026-07-30，Continuity Engine 通过《Engine Contract Final Read-Only Short Confirmation v1》正式接受 `Continuity Integration Contract v1.1`。长期系统边界和第一轮机器契约语义已经闭合；Vio 与 Continuity Engine 双方工程档案同步、引擎定点文档修正和双方工程档案最终只读复核均已完成，双方档案一致。

双方随后共同确认了第一轮施工范围。2026-08-01，Continuity Engine 完成 Engine E1：三份正式 Schema、类型化机器契约结构、固定 SubjectBinding fixture、本地离线 registry、严格 Schema/交叉字段/hash 校验和正式一致性向量测试已经实现。该完成状态只覆盖机器契约基础，不表示第一轮连接已经完成。

Engine E1、E2、E3 的完成基线依次为 `ac61e78`、`d1a96b1`、`c732f35`，Engine Runner 正式共享验收基线为 `7a32a99e60330782c1caf6d6adda5d08d0077a6c`。Vio V1/V2 施工基线为 `c1e1336`/`97874ee`，双方 test-only 共享验收基线为 `673983901b38127b15f772a8be8507defec7384e`。第一轮 test-only 端到端共享验收现已通过：Vio 测试代码实际启动 Runner，把持久化请求送入真实 E3，并严格验证、保存结果、投影和 receipt。

Engine E4 随后完成 Engine 侧正式本地 HTTP/JSON Adapter。Vio V3 首次在 Engine `c5ebbf9b7583f3fb50198a3bf37ea0553edc131f` 上执行 S3 时，发现完成 Wake/Thinking 后、operation domain checkpoint 前退出无法恢复的缺陷；该失败保留为历史。Engine 通过 D-032 完成定点修复并以 `189441f9bad2a34119b4ef10365a4385ed0949cc` 提交，Vio 在 `35780da56c72b822fc018702dfe5e90674ab0fcb` 上重新执行正式 S2/S3。第一阶段正式本地回环 HTTP/JSON 双方验收现已通过：S2+S3 为 15/15，Vio V1+RFC 8785+V2+V3 为 64/64，Vio 后端全量为 113/113，Engine crash-recovery 为 15/15、E4 为 67/67、全量为 301/301。机器契约决定见 [`D-025`](docs/project_memory/04_决策记录.md)，E1—E3 与 Runner 边界见 `D-026`—`D-029`，test-only 共享验收见 `D-030`，E4 与 durable recovery 见 `D-031`、`D-032`，正式本地双方验收里程碑见 `D-033`。

2026-08-10，Engine E5-A 在 E4 基础上完成 Engine 侧 durable Capability 暂停/恢复核心，并完成空白成功结果、结果时间倒序和 Capability 历史目录重复初始化的定点修正。它使用独立的 `continuity-capability/v1` 协议，不修改 v1.1；E5-A 专项测试为 54 项，Engine 完整测试基线为 355 项。架构决定见 `D-034`。

随后 Vio V4、受控 S4、V5、F1 和 L1 依次完成；Engine 在当前双方基线 Engine `cba52126db2fb5eca57d9b5c0c80884693c59a6f`、Vio `239759d1d219bd140f41257c5da18169fbf773a9` 上完成 S4-R 独立追认，结论为 `PASS`。实际复跑为 Engine E5 54/54、Engine 全量 355/355、Vio L1 24/24、Vio 后端 202/202、S4 Capability shared 7/7、V5 Conversation shared 6/6、Vio 前端 19/19。Contract v1.1 与 Engine 主体权威边界未改变；整个受控链路没有调用真实供应商或真实模型，也没有产生真实费用。

2026-08-14，Vio 在执行基线 `d6964a81f96540ab279bc8a5f6e3367f564f0cb8` 上使用仓库外短路径可销毁沙箱 `C:\VioS4\first-001` 和不可晋升测试身份完成首次 S4-Live，结论为 `PASS`。真实供应商为 Alibaba Cloud Model Studio OpenAI-compatible Provider，模型为 `qwen-flash-2025-07-28`；唯一一次 execution 成功，报告 input 177、output 9、total 186 Token，finish reason 为 `stop`。CapabilityResult `SUCCEEDED` 首次回传 HTTP 200，result outbox 和 Conversation Turn 均完成，没有第二次 execution、第二份结果、incident、outcome_unknown 或重复 Message。最终主体表达只来自 Engine `FirstRoundSuccessResult.response.content`；供应商候选没有绕过 Engine。

该次验收保持 `stateProjection.changed=false`、revision `0→0`、`engineUpdateId=null`，没有创建 Event、StateMutation 或 StateUpdateRecord。API Key 只存在于 Vio 后端当次本地进程环境，Engine 未接收或保存。Vio 账本的费用事实为 `cost_status=not_reported`；供应商界面当时约为 0，但官方统计可能延迟，不能记录成永久确定的绝对零费用。验收后 5173、8787、8766 均停止监听，沙箱已整根删除且未触及仓库或受保护路径。首次尝试在供应商调用前暴露的 Windows 持久化路径预算问题由 Vio 的启动前门禁和旧沙箱清理兼容处理解决，未修改 Engine 代码，也不属于 Engine 领域、Schema、HTTP 或恢复协议缺陷。

## 当前开发阶段

P00—P09 已正式 ACCEPTED（P09：D-054），用户已提交并 push；稳定 C1 核定为 `9d58b427ffaca2e64a268640979337e4c759d49d`。D-055 授权 P10 实际 Assistant 建仓，当前 IMPLEMENTED_NOT_ACCEPTED，P11—P23 未开始。历史 UNKNOWN 保留。详见 [P09 正式验收](docs/project_memory/50_P09_测试索引与C1运行入口.md#p09-accepted)。

历史阶段顺序已推进为 `E5-A → V4 → 受控 S4 → V5 → F1 → L1 → S4-R PASS → S4-Live 首次真实供应商单次试聊 PASS → Engine 工程档案归档完成`。

> P09 开工前的历史阶段记录（现行状态见文首及 D-053）：P00—P08 已分别由用户正式验收，当前均为 `ACCEPTED`。P07 Contradiction Detector、P07 Engine side 与 P07-01—P07-12 已完成 Engine 独立实现和首轮四项及第二轮两项监工阻断返修，当前均为 `ACCEPTED`；P07 Vio dependency = `NONE`。P07 验收证据为 专项 56/56、P05—P07 133/133、直接相关 221/221、P01—P07 综合 338/338，以及返修后连续三轮完整回归 642/642；首轮 35/112/200/317/621 作为历史保留。D-049 记录开工、Authority 边界和可信 resolution/supersession 补充决定；D-050 记录用户于 2026-09-04 正式验收 P07。P09—P23 保持 `NOT_STARTED`；P06/P07 本地隔离不是长期产品禁令，P09/P16/P22 仍按规划分别开放正式 Thinking 接线、外部知识和真实 Provider/Vio/PWA 集成；软件版本保持 `0.1.0`。 第一轮返修 46/123/211/328/632 仍作为当时历史证据保留。 用户于 2026-09-04 正式验收 P08（D-052），含方案 A 有限泛化及两轮返修；监工独立四项反例 4/4、P08 58/58、全量 700/700 通过。不扩大生产 exactly-once，不授权生产 Adapter、P09/P17 或 Git 操作。

P00 的唯一全周期入口：

- [`11_P00_全周期能力与阶段基线.md`](docs/project_memory/11_P00_全周期能力与阶段基线.md)
- [`12_P00_规划施工测试验收矩阵.md`](docs/project_memory/12_P00_规划施工测试验收矩阵.md)
- [`13_P00_档案与测试索引.md`](docs/project_memory/13_P00_档案与测试索引.md)
- [`14_P00_风险回滚与用户决策入口.md`](docs/project_memory/14_P00_风险回滚与用户决策入口.md)
- [`15_P01_测试隔离架构与边界.md`](docs/project_memory/15_P01_测试隔离架构与边界.md)
- [`16_P01_规划施工测试验收矩阵.md`](docs/project_memory/16_P01_规划施工测试验收矩阵.md)
- [`17_P01_Snapshot组件与清理策略.md`](docs/project_memory/17_P01_Snapshot组件与清理策略.md)
- [`18_P01_测试索引与联合验收入口.md`](docs/project_memory/18_P01_测试索引与联合验收入口.md)：P01 Engine 独立验收与 P22 未来重连边界
- [`19_P02_宿主中立模型能力架构与边界.md`](docs/project_memory/19_P02_宿主中立模型能力架构与边界.md)
- [`20_P02_规划施工测试验收矩阵.md`](docs/project_memory/20_P02_规划施工测试验收矩阵.md)
- [`21_P02_Provider配置预算与失败语义.md`](docs/project_memory/21_P02_Provider配置预算与失败语义.md)
- [`22_P02_测试索引与验收入口.md`](docs/project_memory/22_P02_测试索引与验收入口.md)
- [`23_P03_Event时间与Timeline架构边界.md`](docs/project_memory/23_P03_Event时间与Timeline架构边界.md)
- [`24_P03_规划施工测试验收矩阵.md`](docs/project_memory/24_P03_规划施工测试验收矩阵.md)
- [`25_P03_时间来源修正撤销语义.md`](docs/project_memory/25_P03_时间来源修正撤销语义.md)
- [`26_P03_测试索引与验收入口.md`](docs/project_memory/26_P03_测试索引与验收入口.md)
- [`27_P04_MemoryConsolidation与DerivedSummary架构边界.md`](docs/project_memory/27_P04_MemoryConsolidation与DerivedSummary架构边界.md)
- [`28_P04_规划施工测试验收矩阵.md`](docs/project_memory/28_P04_规划施工测试验收矩阵.md)
- [`29_P04_保留可见删除与证据去重语义.md`](docs/project_memory/29_P04_保留可见删除与证据去重语义.md)
- [`30_P04_测试索引与验收入口.md`](docs/project_memory/30_P04_测试索引与验收入口.md)
- [`31_P05_ContextRouter架构边界.md`](docs/project_memory/31_P05_ContextRouter架构边界.md)
- [`32_P05_规划施工测试验收矩阵.md`](docs/project_memory/32_P05_规划施工测试验收矩阵.md)
- [`33_P05_权限检索预算来源失效与ContextTrace语义.md`](docs/project_memory/33_P05_权限检索预算来源失效与ContextTrace语义.md)
- [`34_P05_测试索引与验收入口.md`](docs/project_memory/34_P05_测试索引与验收入口.md)
- [`35_P06_ContextComposer与Authority架构边界.md`](docs/project_memory/35_P06_ContextComposer与Authority架构边界.md)
- [`36_P06_规划施工测试验收矩阵.md`](docs/project_memory/36_P06_规划施工测试验收矩阵.md)
- [`37_P06_ContextBudget去重冲突缺失与Trace语义.md`](docs/project_memory/37_P06_ContextBudget去重冲突缺失与Trace语义.md)
- [`38_P06_测试索引与验收入口.md`](docs/project_memory/38_P06_测试索引与验收入口.md)
- [`39_P07_ContradictionDetector架构边界.md`](docs/project_memory/39_P07_ContradictionDetector架构边界.md)
- [`40_P07_规划施工测试验收矩阵.md`](docs/project_memory/40_P07_规划施工测试验收矩阵.md)
- [`41_P07_矛盾分类隔离核实解决与Trace语义.md`](docs/project_memory/41_P07_矛盾分类隔离核实解决与Trace语义.md)
- [`42_P07_测试索引与验收入口.md`](docs/project_memory/42_P07_测试索引与验收入口.md)

P01 不是正式 Subject 或生产恢复能力；P20/P21 仍负责正式恢复。通用真实 Provider、日常正式使用、外网、生产认证、多租户、部署、MCP/Tool/设备和后台长期主动运行仍未开始；它们只能按冻结顺序逐阶段授权。

第一阶段已经完成：

- 建立 `SubjectState` 六个状态分区
- 创建、读取和保存主体状态
- 使用 JSON 文件持久化状态

第二阶段已经完成内部状态演化核心：

- 使用 `Event` 描述发生的事情
- 根据事件影响范围和变更指令执行领域规则
- 记录每个字段变化前后的差异
- 保存变化原因以及导致变化的原始事件
- 使用 `revision` 表示主体状态版本
- 将新状态和更新记录原子保存到同一个主体文档

第三阶段已建立可插拔的 Memory 管理层：

- 构造带主体、时间、查询目标、状态范围和上下文的记忆检索请求
- 接收外部记忆提供方返回的候选及相关性分数
- 根据主体一致性、时间、状态范围和最低分数作出相关性判断
- 对相关候选排序并按请求限额选择
- 记录选中记忆对判断、响应或 `SubjectState` 更新造成的影响
- 通过抽象端口连接外部检索器和影响记录器，不在引擎内部长期保存记忆

第四阶段已建立自主唤醒基础框架：

- `AwakeCycle` 支持手动和定时两种周期模式
- 每次实际唤醒先创建并保存一条 `WakeSession`
- 按固定顺序读取主体状态、最近演化、相关记忆并构建 `WakeContext`
- 使用无 AI 的确定性规则返回 `WakeDecision`
- 保存唤醒原因、观察内容、决策原因、成功状态和失败信息
- 定时周期只提供到期判断与下一次唤醒时间推进，不启动后台线程

第五阶段已建立独立 Thinking Engine：

- 在 Wake 编排链中，只有 `WakeDecision == THINK` 时才创建 `ThinkSession`；进程内 API 也可基于已有 `PerceptionResult` 显式请求思考
- 通过可插拔 `ThinkingProvider` 执行思考，不依赖具体模型
- 使用 `TokenBudgetManager` 预留最大、剩余、本次预算和思考深度
- 使用标准 `ThinkingResult` 表达内部思考结果和可选状态演化意图
- 所有状态写回仍转换为 `Event`，经 Evolution 规则进入 `SubjectState`
- 自动写回仅限 `continuity` 和 `intentions`，禁止身份学习和情绪模拟
- Thinking 日志只保存过程摘要和引用，不保存完整模型思维链

第六阶段已建立 Perception Engine：

- 使用 `PerceptionContext` 接收 `SubjectState`、`WakeContext`、Memory 结果、最近事件和当前时间
- 生成关注点、时间感、关系感、回忆影响、观察、内在驱动力和感知摘要
- 时间、关系和记忆输出表达意义与影响，不执行任何动作
- `PerceptionService` 不依赖存储，也不允许修改 `SubjectState`
- `ThinkingProvider` 的唯一上下文输入改为 `PerceptionResult`
- 总流程固定为 `Wake → Perception → Thinking → Result`

第七阶段已建立 Action Engine：

- 将 `ThinkingResult` 转换为一个或多个 `ActionIntent`
- 依次审计状态 revision、权限、风险和确定性资源估算
- 生成 `ActionDecision`、`ActionPlan` 和可追溯的 `ActionSession`
- `CONTACT_USER`、`USE_TOOL`、`REQUEST_MEMORY` 等只生成计划，不执行外部操作
- 只有获批且无需确认的 `UPDATE_STATE` 才转换为 `Event` 并进入 Evolution
- Action Service 不读取状态存储，也不直接修改 `SubjectState`

规划第五阶段的 Permission Continuity Layer 已建立：

- 使用 `PermissionState` 长期保存权限类型、范围、能力、状态和 revision
- 使用 `PermissionChangeRecord` 保存获得、限制、撤销和过期前后的完整快照及原因
- 使用 `PermissionContext` 向 Action 提供当前权限、可用能力、限制和最近变化
- 使用本地 JSON 原子保存当前权限及完整历史，支持进程重启恢复
- 权限变化只返回 `Event`，由上层选择交给 Evolution；`PermissionService` 不修改 `SubjectState`

规划第六阶段的 Personality Evolution & Self Learning 已建立：

- 使用 `LearningEvent` 保存经历、观察、假设、候选变化、置信度和验证状态
- 使用 `PersonalityTrait` 表示经多次证据验证的长期表达、判断与互动特征
- 使用 `LearningRecord` 保存候选、置信度调整、验证、固化和回滚的完整因果历史
- 至少三条来源不同且变化一致的经历、综合置信度达到阈值后才能验证
- 未验证学习只保存为候选；固化与回滚都需要显式确认，并只返回交给 Evolution 的 `Event`
- 使用本地 JSON 保存学习候选、特征和审计记录，支持进程重启恢复

规划第七阶段的 Token & Resource Management 已建立：

- 使用 `ResourceState` 保存 Token/计算预算、已用量、剩余量、运行模式和 revision
- 使用 `TokenUsageRecord` 记录 Thinking、Memory、Learning 和 Other 会话的估算消耗
- 使用 `ResourcePolicy` 将请求确定性地批准、降级到 LOW、降低频率或延迟
- `ResourceManager` 实现现有 `TokenBudgetManager` 端口，并提供 Learning、Memory、Wake 资源申请入口
- `ResourceAwareWakeScheduler` 在创建 WakeSession 前检查资源，不启动后台循环
- 使用本地 JSON 原子保存当前资源、使用历史和策略决策，支持重启恢复

当前已经包含进程内 API、本地 HTTP 调试服务、MCP/Skill 适配接口和最小调试前端。它们不代表真实 MCP、平台 Skill、AI API、外部记忆、主动消息、动作执行、后台常驻调度、真实 Token 计费、外部支付、外部权限集成或模型训练已经实现。

这里的“自主唤醒”仅表示引擎具备可被定时器、人工或事件触发后独立运行一次检查流程的能力。当前不会主动发消息，也不会真正执行决策动作。

## Awakening System

固定唤醒流程：

```text
创建 WakeSession
  ↓
读取 SubjectState
  ↓
读取最近 StateUpdateRecord 和 Event
  ↓
通过 MemoryService 请求相关记忆
  ↓
构建 WakeContext
  ↓
生成 WakeDecision
  ↓
完成并保存 WakeSession
```

`WakeContext` 包含：

- 当前完整 `SubjectState`
- 最近事件
- 最近状态更新及逐字段变化
- `MemoryRetrievalResult`
- 当前时间、最后互动时间和距上次互动时长

当前只允许四种决策：

- `SLEEP`：没有需要继续处理的信息
- `THINK`：发现相关记忆或近期状态变化，但暂不执行思考
- `CHECK_MEMORY`：看到了候选记忆，但没有候选通过相关性选择
- `READY`：存在当前关注点或未完成事项，上下文已经准备好

`WakeDecisionPolicy` 只生成决策、原因和证据，不调用动作执行器。

每条 `WakeSession` 日志保存：

- 为什么醒来以及可选来源事件
- 唤醒和结束时间
- 读取到的主体版本
- 查看过的事件、更新和记忆 ID
- 最终决策、决策原因和证据
- 是否成功完成
- 失败时的错误摘要

## Perception 与 Thinking Engine

完整服务链：

```text
WakePerceptionThinkingActionService
  ↓
AwakeningService → WakeDecision
  ↓
PerceptionContext
  ↓
PerceptionService → PerceptionResult
  ↓ 仅当 THINK
创建 ThinkSession
  ↓
TokenBudgetManager.allocate
  ↓
ThinkingProvider.think(PerceptionResult)
  ↓
ThinkingResult
  ↓
ActionIntent
  ↓
PermissionCheck → RiskAssessment → ResourceAssessment
  ↓
ActionDecision → ActionPlan → ActionSession
  ↓ 仅限获批 UPDATE_STATE
Event → SubjectStateService.apply_event → Evolution → SubjectState
```

`PerceptionResult` 统一包含：

- 当前关注点 `CurrentFocus`
- 时间感 `TemporalPerception`
- 关系感 `RelationshipPerception`
- 回忆影响 `MemoryInfluence`
- 统一观察 `Observation`
- 内在驱动力 `Drive`
- 感知摘要以及来源 revision、事件、更新和记忆引用

`PerceptionResult` 不携带原始 `SubjectState` 或 `WakeContext`。Thinking 只接收感知结果；需要写回时，使用感知来源 revision 做并发保护，并严格经过 `Event → Evolution → SubjectState`。

`ThinkingResult` 标准字段包括：

- 是否产生新想法
- 是否更新 `SubjectState`
- 是否请求更多记忆
- 是否需要等待
- 是否建议未来联系用户
- 是否建议工具计划或再次思考
- 结果摘要与原因摘要
- 本次 `TokenBudget`
- 可选的状态变更指令

`TokenBudget` 当前只定义：

- `maximum_tokens`
- `remaining_tokens`
- `session_tokens`
- `ThinkingDepth`：`LOW`、`NORMAL`、`DEEP`

`actual_token_consumption` 已在 `ThinkSession` 中预留，当前保持为空；`TokenBudgetManager.record_usage` 只定义接口，不会被调用。

`ThinkingProvider` 是模型无关协议。未来 GPT、Claude 或本地模型适配器实现相同接口即可接入；核心引擎不导入任何模型 SDK。

Thinking 日志保存思考原因、查看过的状态版本、事件、更新和记忆 ID、结果摘要、原因摘要及状态写回引用。禁止保存完整模型思维链。

## Action Engine 边界

`ActionType` 支持：`NO_ACTION`、`UPDATE_STATE`、`REQUEST_MEMORY`、`CONTACT_USER`、`USE_TOOL`、`DEFER` 和 `REQUEST_MORE_THINKING`。

行动决策由三类确定性检查组成：

- `PermissionProvider` 检查权限是否存在、有效、撤销、过期、需重新确认或超出范围；当前提供纯内存实现。
- `RiskEvaluator` 保证联系用户至少为 `MEDIUM`，工具计划不低于 `HIGH`，`HIGH`/`CRITICAL` 不自动批准。
- `ResourceEvaluator` 只比较计划步骤和估算成本与 `ResourceLimits`，不读取真实 Token 或计费。

Action 只保存计划状态：`PLANNED`、`BLOCKED`、`DEFERRED`、`REJECTED`。不存在 `EXECUTED`，也不会伪造外部执行成功。

状态边界固定为：

```text
Approved UPDATE_STATE
  → Event / StateMutation
  → SubjectStateService.apply_event(expected_revision=...)
  → Evolution
  → SubjectState
```

旧的 `WakePerceptionThinkingService` 作为兼容入口保留，但其状态写回同样经过 Action 审批，不再允许 Thinking 直接写回。

## Permission Continuity Layer

权限连续层回答的是“当前拥有什么权限，以及它如何变化”，不同于 Action 中针对单次行动的即时 `PermissionCheck`。

`PermissionState` 保存：

- `permission_id`、`subject_id`、权限类型、名称和说明
- 可访问 `scope` 与可执行 `capabilities`
- `ACTIVE`、`LIMITED`、`REVOKED`、`EXPIRED` 状态
- 授权/撤销时间、来源和 revision

每次创建、限制、撤销、过期或重新激活都会产生 `PermissionChangeRecord`，其中保留 `before_state`、`after_state`、原因、来源和时间。`JsonPermissionRepository` 把当前状态与历史记录原子保存在同一权限文档中。

`PermissionContext` 只暴露当前有效或受限的权限、可用能力、限制摘要和最近变化。ActionContext 提供该对象时，只从其中读取连续权限能力；`PermissionProvider` 再执行本次行动的有效性、撤销、过期、确认和范围复核。

权限变化与主体状态的边界为：

```text
PermissionService → PermissionChangeResult + Event
                                      ↓ 由上层显式提交
                    SubjectStateService.apply_event
                                      ↓
                                  Evolution
                                      ↓
                                SubjectState
```

权限服务自身不依赖 `SubjectStateService`，也不会申请权限或执行任何外部能力。

## Personality Evolution & Self Learning

学习层实现的是“经历如何经过验证成为长期特征”，不是训练或修改 AI 模型。流程固定为：

```text
经历 / MemoryInfluenceRecord / Event 历史
  → 观察
  → 假设与 PENDING LearningEvent
  → 至少 3 条独立一致证据
  → VALIDATED
  → 显式确认
  → StateMutation / Event
  → Evolution
  → SubjectState
```

`LearningService` 只从显式的结构化 `learning_*` 元数据提取候选，不分析真实用户行为。可学习字段限制为稳定特征、表达偏好、判断原则和互动偏好；单次经历不能创建 `PersonalityTrait`，验证也不会直接修改 `SubjectState`。

固化或回滚返回 `LearningChangeResult.event`。只有上层将该事件提交给 `SubjectStateService.apply_event(expected_revision=...)` 后，主体状态才会变化。错误学习会保留原始经历、观察、假设、前后差异、固化事件和回滚事件的审计记录。

## Token & Resource Management

资源层管理主动运行的估算成本，不连接真实计费系统。统一流程为：

```text
Thinking / Learning / Wake / Memory Request
  → ResourceManager
  → ResourcePolicy
  → 批准 / 降低思考深度 / 降低频率 / 延迟
  → ResourceState + TokenUsageRecord + ResourceDecision
```

运行模式包括 `LOW_FREQUENCY`、`SCHEDULED`、`CONTINUOUS` 和 `DEEP_THINKING`。LOW_FREQUENCY 将思考限制为 LOW；SCHEDULED 和 CONTINUOUS 最高为 NORMAL；只有资源充足且处于 DEEP_THINKING 时才允许 DEEP。默认保留 10% Token 安全余量，连 LOW 成本也无法满足时返回延迟决策。

`ResourceManager` 在批准申请时立即记录估算 Token 和计算单位。`actual_tokens` 当前保持为空；未来模型适配器可以通过回填接口校正已用量，但本阶段不读取账单、不计算价格，也不购买资源。

Thinking 可以直接使用 `ResourceManager` 作为 `TokenBudgetManager`。资源不足时，Thinking 生成等待结果并跳过 Provider。Learning 配置了 ResourceManager 时，会在资源不足时延迟结构化候选提取。`ResourceAwareWakeScheduler` 提供资源检查后的单次唤醒入口，但底层 `AwakeningService` 仍可被直接调用，因此 v0.1 尚未强制所有内部路径经过统一资源入口。当前没有持续后台循环。

## API、HTTP 与调试前端

`APIService` 是进程内服务门面，不是独立部署的生产 API。它统一返回：

- `request_id`
- `subject_id`
- `timestamp`
- `current_revision`
- `result`
- `error`

进程内 API 提供以下调用：

- 获取 SubjectState 摘要、revision 和最近事件。
- 查询相关记忆。
- 获取当前 PerceptionResult。
- 请求 Thinking。
- 读取最近 ActionDecision 与 ActionPlan。
- 触发需要确认的手动 Wake。
- 提交一条用户消息并运行本地连续性流程。

这些核心调用先经过 `PermissionContext` 和 `ResourceManager` 组成的访问门。外部请求可以通过 Event/Evolution 触发受控状态变化，但不能直接修改 SubjectState 或 JSON 文件。

本地 `http.server` 实现只服务于调试前端，当前暴露：

- `GET /api/config`
- `GET /api/state`
- `POST /api/chat`
- 同源 HTML、CSS 和 JavaScript 静态文件

它不是完整生产 HTTP API，没有用户认证、TLS、限流、多租户或部署配置。

`ContinuityMCPAdapter` 只是调用 `APIService` 的 MCP-shaped 工具门面，没有 MCP SDK、Server/Client 或协议传输。`SkillAdapter` 是平台无关协议及 API 委托基类，没有接入任何真实 Skill 平台。

最小前端只负责输入、展示和 API 通信，不在浏览器中保存 SubjectState、记忆、人格或权限，也不执行感知、思考、行动和学习规则。

## Memory 管理边界

Memory 层负责：

- `MemoryRetrievalRequest`：表达需要回忆什么、为哪个主体回忆以及希望影响哪些状态范围
- `MemoryCandidate`：承接外部记忆库返回的候选内容、来源、时间、范围和提供方相关性分数
- `MemoryRelevanceDecision`：保存接受或拒绝候选的判断与原因
- `MemoryRetrievalResult`：保存一次请求的全部判断及最终选中的记忆
- `MemoryInfluenceRecord`：记录某条选中记忆产生了什么影响、为什么产生影响，以及关联的事件和状态更新

Memory 层不负责：

- 保存长期记忆正文
- 建立本地向量库或数据库
- 调用 AI 模型计算语义相似度
- 直接实现 MCP 协议

外部系统需要实现两个可插拔端口：

- `MemoryRetriever`：接收检索请求并返回候选记忆
- `MemoryInfluenceRecorder`：接收记忆影响记录并交给外部系统处理

未来 MCP 适配器可以实现这两个端口，而不需要修改 Memory 领域模型和服务逻辑。

## Event 结构

一个事件包含：

- `event_id`：事件唯一标识
- `occurred_at`：事件发生时间，必须带时区
- `source`：事件来源
- `event_type`：事件类型；`interaction` 会推进最后互动时间
- `content`：发生了什么
- `impact_scope`：允许影响的状态分区
- `mutations`：明确的字段变更意图
- `reason`：为什么该事件需要改变状态
- `metadata`：可选的 JSON 元数据

当前阶段不使用 AI 猜测自然语言效果。领域层只接受显式变更指令，并检查：

- 目标字段是否允许由事件修改
- 目标字段是否位于事件声明的影响范围内
- `set`、`append`、`remove` 操作是否适合目标字段
- 变更值类型是否正确
- 同一个事件是否已经应用过

## 更新记录

每次应用事件都会产生 `StateUpdateRecord`，其中保存：

- 完整原始事件
- 更新原因
- 应用时间
- 更新前后的 `revision`
- 每个实际变化字段的 `before`、`after`、操作类型和具体原因

没有造成实际字段变化的事件仍可留下事件记录，但不会推进状态版本。

## 代码结构

```text
src/continuity_engine/
├── domain/
│   ├── models.py       # SubjectState 六分区和版本
│   ├── events.py       # Event、变更指令、字段差异和更新记录
│   ├── evolution.py    # 状态演化白名单与领域规则
│   ├── memory.py       # Memory 请求、候选、相关性规则和影响记录
│   ├── awakening.py    # 周期、会话、上下文和决策对象
│   ├── awakening_rules.py # 无 AI 的唤醒决策规则
│   ├── perception.py   # 感知输入、结构化感知结果和来源引用
│   ├── perception_rules.py # 无 AI 的确定性感知规则
│   ├── thinking.py     # 思考结果、会话与 Token Budget
│   ├── action.py       # 行动上下文、意图、评估、决策、计划和会话
│   ├── permissions.py  # 权限状态、变化历史和 PermissionContext
│   ├── learning.py     # 学习候选、长期特征、上下文、结果和审计记录
│   ├── resources.py    # 资源状态、使用记录、请求、决策和运行模式
│   ├── resource_policy.py # 深度降级、频率降低与延迟规则
│   ├── integration_contract.py # E1 类型化请求、事实、观察与绑定 fixture
│   ├── integration_hashing.py # E1/E2 共用 RFC 8785 与 SHA-256 规则
│   ├── integration_results.py # E2 结果/投影与 E3/E4 durable operation checkpoint
│   ├── capability.py  # E5-A Capability 请求、结果、状态与 envelope
│   ├── subject_binding.py # E4 正式运行 SubjectBinding
│   └── errors.py       # 领域异常
├── services/
│   ├── subject_state_service.py  # 创建、读取、应用事件、查询历史
│   ├── memory_ports.py           # 外部检索与影响记录端口
│   ├── memory_service.py         # Memory 检索、筛选和影响编排
│   ├── awakening_service.py      # 固定顺序的唤醒流程编排
│   ├── perception_service.py      # 无存储、只读的感知服务
│   ├── thinking_ports.py         # Provider 与 Token 管理接口
│   ├── thinking_service.py       # ThinkSession；不直接写回状态
│   ├── action_ports.py           # 可插拔权限和评估端口
│   ├── action_permissions.py     # 纯内存确定性权限提供器
│   ├── action_evaluators.py      # 风险与资源规则
│   ├── action_service.py         # 意图提取、检查、决策和计划
│   ├── permission_service.py     # 权限状态、历史、能力检查和上下文
│   ├── learning_service.py       # 候选提取、验证、固化和回滚
│   ├── resource_manager.py       # 资源申请、扣减、回填和模式管理
│   ├── resource_aware_wake_scheduler.py # 资源检查后的单次 Wake 调度
│   ├── integration_contract_hashing.py # RFC 8785 与三类 SHA-256 计算
│   ├── integration_contract_validation.py # 严格 Schema、交叉字段和 hash 校验
│   ├── integration_result_factory.py # E2 结果与投影的确定性构造
│   ├── contract_test_bootstrap.py # E3 全新主体、固定 Binding/Cycle 准备
│   ├── contract_test_doubles.py # E3 进程内确定性替身
│   ├── deterministic_integration_providers.py # E4 正式进程内确定性 Provider
│   ├── integration_ports.py # E4 Binding/回复端口
│   ├── continuity_interaction_service.py # E3/E4 共用的唯一交互核心
│   ├── capability_ports.py # E5-A Capability 持久化端口
│   ├── capability_contract_validation.py # E5-A 严格机器契约校验
│   ├── capability_coordination_service.py # E5-A 请求创建、结果接收与幂等协调
│   ├── capability_result_interpreter.py # E5-A 外部结果进入 Thinking 的解释边界
│   ├── action_evolution_service.py # Action Gate 授权后的统一 Evolution 入口
│   ├── user_interaction_service.py # 用户输入转 Event 并运行连续性流程
│   ├── wake_perception_thinking_action_service.py # 第七阶段完整编排
│   └── wake_perception_thinking_service.py # 兼容入口
├── storage/
│   ├── base.py         # 各模块仓储 Protocol
│   ├── json_repository.py        # SubjectState 与演化记录持久化
│   ├── json_awakening_repository.py # 周期与 WakeSession 日志
│   ├── json_thinking_repository.py  # ThinkSession 摘要日志
│   ├── json_permission_repository.py # 权限状态与历史 JSON 持久化
│   ├── json_learning_repository.py # 学习候选、特征与历史 JSON 持久化
│   ├── json_resource_repository.py # 资源状态、消耗与决策 JSON 持久化
│   ├── json_integration_repository.py # 固定 Binding 与不可变结果账本
│   ├── json_subject_binding_repository.py # E4 单 active Binding 原子持久化
│   └── in_memory_action_repository.py # 进程内 ActionSession 仓储
├── interfaces/
│   ├── models.py       # 统一 API 请求、响应与错误模型
│   ├── ports.py        # API、Perception 和 Action 只读端口
│   ├── security.py     # PermissionContext 与 ResourceManager 访问门
│   ├── api_service.py  # 进程内 API 门面
│   ├── core_views.py   # ActionSession 只读视图
│   ├── mcp_adapter.py  # MCP-shaped 接口；无真实 MCP 传输
│   ├── skill_adapter.py # 平台无关 Skill 协议；无平台接入
│   ├── http_server.py  # 本地调试 HTTP 服务
│   ├── integration_contract_schema.py # 仅本地解析的三 Schema registry
│   ├── contract_test_adapter.py # E3 test-only 进程内契约入口
│   ├── integration_adapter.py # E4 正式进程内薄 Adapter
│   ├── integration_config.py # 仅回环地址、端口与令牌配置
│   ├── local_integration_app.py # E4 正式初始化、恢复与装配
│   ├── integration_http_server.py # E4 串行 HTTP/JSON 服务
│   ├── capability_schema.py # E5-A 封闭本地 Schema registry
│   ├── schemas/        # E1 与 E5-A 的 Draft 2020-12 Schema
│   └── local_frontend_app.py # 本地依赖组装与显式初始化
├── frontend/
│   ├── index.html      # 最小聊天与状态调试界面
│   ├── app.js          # 页面交互
│   ├── client.js       # FrontendClient
│   ├── styles.css      # 调试界面样式
│   └── __main__.py     # python -m continuity_engine.frontend
├── integration_server.py # E4 显式 init/serve 进程入口
├── cli.py              # 本地验证入口
└── __main__.py         # python -m continuity_engine
tests/                  # 单元测试；含 E1—E5-A、HTTP、持久化与 crash recovery 测试
└── shared/             # test-only JSONL Runner 与真实 E3 装配辅助
```

调用路径：

```text
Event
  ↓
SubjectStateService.apply_event
  ↓
SubjectStateEvolver（领域规则）
  ↓
新 SubjectState + StateUpdateRecord
  ↓
JsonSubjectStateRepository.save_transition
```

Memory 调用路径：

```text
MemoryRetrievalRequest
  ↓
MemoryService
  ├── MemoryRetriever（未来由 MCP 适配器实现）
  ├── MemoryRelevancePolicy
  └── MemoryInfluenceRecorder（未来由 MCP 适配器实现）
```

Awakening 调用路径：

```text
人工 / 外部定时器 / Event
  ↓
AwakeningService
  ├── SubjectStateService
  ├── MemoryService
  ├── WakeDecisionPolicy
  └── JsonAwakeningRepository
  ↓
WakeContext + WakeSession（仅返回决策，不执行动作）
```

## 快速运行

先安装项目及其运行依赖，再在项目根目录执行：

```powershell
python -m pip install -e .
```

E1 新增 `jsonschema>=4.26,<5`（MIT，用于 Draft 2020-12 严格校验与本地 registry）和 `rfc8785>=0.1.4,<1`（Apache-2.0，用于标准 JSON 规范化）；二者均为本地库，不连接网络服务、不需要账户或密钥。

```powershell
$env:PYTHONPATH = "src"
python -m continuity_engine init demo-subject --self-concept "一个重视连续性的助手"
python -m continuity_engine update demo-subject `
  --focus "实现状态演化" `
  --emotion "专注" `
  --content "项目进入第二阶段" `
  --reason "当前开发重点已经改变"
python -m continuity_engine touch demo-subject
python -m continuity_engine show demo-subject
python -m continuity_engine history demo-subject
```

默认数据保存在项目根目录的 `.continuity-data/`。可以在子命令之前使用 `--data-dir` 指定其他目录：

```powershell
python -m continuity_engine --data-dir .\local-state show demo-subject
```

### 启动本地调试前端

首次启动必须显式创建本地主体、权限、资源和手动唤醒周期：

```powershell
$env:PYTHONPATH = "src"
python -m continuity_engine.frontend --initialize
```

之后可省略 `--initialize`：

```powershell
$env:PYTHONPATH = "src"
python -m continuity_engine.frontend
```

默认地址为 `http://127.0.0.1:8765`，默认数据目录为 `.continuity-data/`。该服务只用于本地调试，不应作为生产部署方式。

## 在代码中应用事件

```python
from datetime import datetime, timezone
from pathlib import Path

from continuity_engine import ChangeOperation, Event, StateMutation, StateSection
from continuity_engine.services import SubjectStateService
from continuity_engine.storage import JsonSubjectStateRepository

repository = JsonSubjectStateRepository(Path(".continuity-data"))
service = SubjectStateService(repository)
service.create("demo-subject")

event = Event.create(
    occurred_at=datetime.now(timezone.utc),
    source="user",
    event_type="state_update",
    content="项目进入第二阶段。",
    impact_scope=[StateSection.CONTINUITY],
    mutations=[
        StateMutation(
            field_path="continuity.current_focus",
            operation=ChangeOperation.APPEND,
            value="实现内部状态演化能力",
            reason="用户明确指定了新的开发重点。",
        )
    ],
    reason="让主体状态反映当前项目阶段。",
)

result = service.apply_event("demo-subject", event)
print(result.state.revision)
print(result.update.changes[0].before)
print(result.update.changes[0].after)
```

## 持久化兼容性

第一阶段的纯 `SubjectState` JSON 文件仍然可以直接读取。第一次应用事件时，存储层会把该文件升级为包含以下内容的原子文档：

```text
{
  persistence_format_version,
  state,
  updates
}
```

## 测试

项目目标兼容 Python 3.11–3.14。E1 使用 `jsonschema` 和 `rfc8785` 两个第三方运行依赖；仓库当前尚未配置多版本 CI。

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

P01 验收时的历史测试基线：397 项（P01 专项 42 项；施工前 355 项基线继续全部通过）。当前 P07 验收基线为 642 项，P07 专项 56 项；各阶段历史结果保留在施工日志及专项索引中。

正式本地集成服务必须先显式初始化，再使用至少 32 字符的进程环境令牌启动：

```powershell
$env:PYTHONPATH = "src"
python -m continuity_engine.integration_server init `
  --data-dir <Engine正式本地数据目录> `
  --binding-file <完整Binding fixture JSON文件> `
  --binding-fixture-hash <sha256:...> `
  --cycle-id <稳定Engine cycle id>

$env:CONTINUITY_ENGINE_INTEGRATION_TOKEN = "<至少32字符的本地服务令牌>"
python -m continuity_engine.integration_server serve `
  --data-dir <Engine正式本地数据目录> `
  --port 8766
```

默认 `serve` 继续使用 `deterministic` 模式。仅在 Engine E5-A 验证场景中显式启用 capability 模式：

```powershell
python -m continuity_engine.integration_server serve `
  --data-dir <Engine正式本地数据目录> `
  --port 8766 `
  --thinking-mode capability
```

capability 模式新增 `POST /internal/v1/continuity/capability-results`，并通过既有请求查询路由返回 `capability_required`、`capability_failed` 或完成结果。它不会自行联网或调用模型；真实执行方未来由 Vio 提供。

该服务固定监听 `127.0.0.1`，不会隐式初始化，也不向浏览器前端开放。所有响应都声明 `Connection: close` 并结束当前连接；每条连接默认使用 10 秒有界读取超时，普通超时、提前断连和可安全响应的解析错误不会产生 HTML 错误页或 Python traceback。当前确定性 Memory/Thinking/Reply/Token Provider 不是 GPT、Claude 或其他真实模型接入。Vio V3 与 Engine E4 的第一阶段正式本地回环 HTTP/JSON 双方验收已经通过；该结论不等于外网连接、生产部署、公共对话 API 串联或前端真实数据链路已经完成。

共享验收 Runner 只能从仓库根目录显式使用受控临时目录启动：

```powershell
$env:PYTHONPATH = "src"
python -m tests.shared.continuity_contract_jsonl_runner --data-dir <受控临时数据目录>
```

它从 stdin 接收每行一个完整 `ContinuityInteractionRequest`，并在 stdout 对每个合法 JSON 对象立即输出一行紧凑 UTF-8 结果。该命令仅供双方测试代码使用，不是正式 CLI、HTTP 服务或生产连接入口。

## P09 C1 Engine 独立入口（已由用户正式验收）

P09 已按 D-053 接入既有正常交互服务：Event/Timeline → Memory Consolidation → Router → Composer → P07 → Thinking/Action Gate → Direct/Optional Planner。可消费 Context 保存于既有 Perception/ThinkSession checkpoint；原模型契约及唯一 E5-A ledger 保留。情绪时间衰减只读，StateMutation 仍必须走原合法 Evolution。P09 当前为 `ACCEPTED`；P10 已由 D-055 另行授权，P11—P23 未开始。

以下入口只创建独立临时 P01 数据根，并禁止网络连接；无需 Vio、Provider 或凭据：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m continuity_engine.testing.p09_core_runner --scenario golden
python -m continuity_engine.testing.p09_core_runner --scenario long
```

Golden 包括 Direct、Information Need、复杂 Planner、静默及重放；Long 固定 30 逻辑日/30 轮，在第 10、20 轮后真实进程重启。报告输出临时证据位置，长期场景会随追加历史增加校验耗时。完整矩阵、真实失败与兼容/全量结果见 [P09 测试索引](docs/project_memory/50_P09_测试索引与C1运行入口.md)。幂等只限本地 Fake 原子回执；D-054 未创建，稳定 C1 提交须待正式验收后确定。


本轮 P09 监工返修已补齐首次 Evolution 的当前 Context/Action 授权检查，以及 C1 输入与既有 ThinkSession/Action/E5-A 之间的恢复绑定；合法状态更新、已提交事实恢复与旧格式兼容保留。定点、专项、兼容、三轮全量及档案后终局复跑已通过；首次终局异常根因未确认，EVIDENCE_CONFLICT 继续 PRESENT 待独立复核；全部首次失败和结果见 [50 返修索引](docs/project_memory/50_P09_测试索引与C1运行入口.md#p09-repair-01)。


## P10 实际建仓与验证入口（2026-09-04，D-055）

P10 分支、独立本地/PRIVATE 远程、13 文件初始化提交及首次 push 已完成。Assistant HEAD `c6dd2c0cab17337a445b64fb8611d317190242c6`，直接父提交/共同祖先为固定 C1 `9d58b427ffaca2e64a268640979337e4c759d49d`。本地、Temp 外远程干净克隆及首次真实 CI 的构建/安装、已安装包导入/Golden、原 Core 770 项和新增 P10 12 项均通过；具体命令、耗时及全部首次失败见 54。P10 / Engine side / P10-01—P10-12 = IMPLEMENTED_NOT_ACCEPTED，P10 Vio dependency=NONE；P00—P09 ACCEPTED，P11—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT：Temp 内首次克隆暴露的原 P08 Fixture 路径边界反例未修，须独立复核；后续通过不覆盖它。D-055 登记开工与事实，D-056 未创建、未使用。Engine main 未提交或推送，Engine P10 档案仍是未提交成果。

- [51 架构与 Stage Brief](docs/project_memory/51_P10_Assistant建仓架构与StageBrief.md)
- [52 逐项矩阵](docs/project_memory/52_P10_规划施工测试验收矩阵.md)
- [53 来源/checkpoint 与显式版本同步](docs/project_memory/53_P10_来源Checkpoint与跨仓版本同步.md)
- [54 测试、CI 与验收入口](docs/project_memory/54_P10_测试索引与验收入口.md)

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。

## P11 Event Priority 与 Scheduler 独立实现（2026-09-05，D-057）

P11 在 Engine 内新增唯一 Scheduler Queue/Record、宿主中立 Notification Port、原子 JSON 仓储和 TEST Fixture。它按可信 UTC、priority、dueAt、稳定 sequence 与可解释 aging 安排一次 computation opportunity；背压、资源不足和静默时段只延迟，不消耗 attempt。投递后不明状态进入 UNKNOWN，按稳定 attempt/receipt 身份先查询；取消与结果恢复幂等，本地调度不重复语义不外推为生产 exactly-once。

Scheduler 复用现有 `AwakeningService`、`WakeSession`、`ResourceManager` 和 `ResourceAwareWakeScheduler`，不生成 thought/emotion/desire/will/action intent，不调用模型、Planner、Action 或现实副作用。P11 专项 39/39；三轮全量每轮 833 项，均为 832 PASS、1 个既有环境 SKIP、0 FAIL。P11 仍为 `IMPLEMENTED_NOT_ACCEPTED`，D-058 未创建；详见 [架构边界](docs/project_memory/55_P11_EventPriority与Scheduler架构边界.md)、[矩阵](docs/project_memory/56_P11_规划施工测试验收矩阵.md)、[恢复语义](docs/project_memory/57_P11_队列恢复重试取消与投递语义.md)和[复核入口](docs/project_memory/58_P11_测试索引与验收入口.md)。

## P11 正式验收归档（2026-09-05，D-058）

用户在独立复核通过后确认验收：原两个反例 2/2 PASS，P11 45/45 PASS（8.371 秒），修改范围和受保护文件 hash 核对通过；首次入队阻断关闭。P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。修复前全量继续标为历史，全部失败/修复证据保留。本次仅档案归档，源码/测试不改、不复跑全量、不修改 Assistant、不进入 P12、不执行 Git 写操作。详见 [验收入口](docs/project_memory/58_P11_测试索引与验收入口.md#p11-accepted)。

## 2026-09-06：P12 前 R01—R08 定点修复

用户授权仅修复审查列明的八项缺陷并交回独立复核，未授权本轮自行验收或 Git 写操作；不占用后续阶段决定编号。P11 已于此前提交到 `5f25d0cef3798aa380d457ae670db30ee1b47407`，本轮以该 SHA 为开工基线。当前修复属于该提交之后尚未提交的 Engine 工作区增量，与 P11 历史验收事实分开记录。根因、文件责任、失败/修复/兼容证据与状态见 [本轮入口](docs/project_memory/P12前整体审查_R01-R08修复与复核入口.md)。保留所有历史证据，31 个 P10 辅助脚本原样排除；Assistant 不修改、P12 不开始。
