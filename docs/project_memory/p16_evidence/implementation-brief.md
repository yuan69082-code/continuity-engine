# P16 开工简报 外部记忆知识与可插拔能力

日期：2026-09-09。执行仓库：`C:/Users/Administrator/Documents/continuity-engine`。执行任务：codex 引擎。规划侧本轮只准备简报和转发提示词，未修改 Engine、未发送跨任务指令。

## STAGE 与本次授权

用户在 P15 验收及 push 完成后明确说“那我们开始P16”。本次范围为 P16 Engine 独立实现、必要测试及工程档案同步，完成后交回独立复核。P15 的验收/push 授权已经执行完毕，不自动延伸至 P16；本次不自行验收、不暂存、提交或 push，不开始 P17。

本简报由用户转发时，与转发提示词一起作为 P16 本次开工范围。先核对真实工作区并记录 Stage Brief；范围一致即可施工，不要因历史记录中的“P16 未授权/未开始”返回 P15 收尾。发生需要新增权限、改变规划或决定真实服务清单的问题时，保留证据并请用户确认，不自行扩大范围。

## SOURCE OF TRUTH 与依赖

P15 已登记 D-067、P00—P15 ACCEPTED。上一阶段已核实的提交：

- 分支 `main`，HEAD `a41a733635b0f5978c19b287274b4c63925b8979`。
- 直接父提交 `f1185d20da06f52e7e85015bc6b963cf9769d08c`。
- 提交说明 `feat: implement and accept P15 subject growth and lifecycle`。
- 247 个精确清单文件已提交；规划侧上一轮已独立读取实际远端 `refs/heads/main`，与本地一致。
- 暂存区和已跟踪工作区干净；未跟踪只保留 31 个 P10 脚本与 1 个 P14 接续报告。它们不是漏交的 P15 成果，不修改、不纳入 P16 清单。
- 行为基线：1208 项，1207 PASS、1 既有 Windows symlink 权限 1314 SKIP、0 FAIL/ERROR。独立 P15 71 PASS，原 8 探针属于 71 项；额外独立 8 项不增加正式测试总数。
- 当前 232 个源码/测试/资源文件和保护范围经 P15 收尾核对不变；基线全量是已核验历史记录，不冒称 P16 新运行。

开工重新读取 README、当前状态、路线、`.agents/workflow.md`、相关实现和测试，记录源码/测试身份及完整 Git 状态。核对现行状态优先于历史快照；不重复 P15 验收，不回滚已有成果。若存在未解释的并发修改，不覆盖。

规划源为本规划工作区 `outputs` 下 2026-08-26 三个冻结原件。规划侧本轮核对三个原件 SHA-256 与 P15 验收来源记录全部相同，并读取 Engine `docs/project_memory/p12_evidence/planning-source.json` 中的对应正文缓存。此为内容核对，不是 DOCX 排版验收。

- 全周期工程监工规划 v1.1：`9cbc30b5beb7f12c046556bd9461b59d5d4e45c2315dc2da4f07c8bd132ae1a1`。
- 长期能力增补规划 v6.7：`a47bfb5e19092ee11963c0554897fbb29cbbba775183bddecb284c24f3788027`。
- Assistant 分支构想 v0.1：`5513e8241a96f4d661d9520cbcb3c2ea9914ca8d430b2db4dacc13ba3dd744a1`。

v1.1 P16 施工卡是本阶段顺序与范围依据，v6.7 提供长期细节，2026-08-26 Engine 独立施工 OVERRIDE 优先于旧 Vio 联调表述。若缓存与原件或真实代码存在冲突，读取原件相关内容并报告，不默默改写规划。

## ORIGINAL REQUIREMENTS

P16 要建立宿主中立的 Memory Provider、Knowledge Provider、MCP、Skill、Connector 注册与 Credential Broker 端口，让外部能力可替换、可撤销、可审计。Engine 保留 capabilityRef 与结构化结果，不保存原始 API Key。

外部检索结果只能作为 `retrieved_candidate`，带来源、权限、时效和内容 hash，不直接修改 SubjectState。离线、超时、撤销、缓存过期、恶意结果、重启以及秘密不进入状态/日志/Git，是原规划明确验收要求。

这次交付应让独立 TEST 引擎能够实际完成“需要信息 → 选择获准来源/能力 → 本地 Fake 调用 → 验证结果 → 原 Context/Thinking 消费或明确拒绝 → 可追溯恢复”的运行流程。仅新增 dataclass、注册表、孤立示例或 MCP-shaped facade，不足以宣布阶段完成。

## V6.7 DETAILS 与现有基础

本次已核实以下基础存在，实施者须进一步阅读具体责任边界并优先复用：

- `src/continuity_engine/services/memory_ports.py`：既有 MemoryRetriever、MemoryInfluenceRecorder 等宿主中立端口。
- `src/continuity_engine/interfaces/mcp_adapter.py`：现有对外 API facade 明确不含 MCP transport 或 SDK。
- `src/continuity_engine/interfaces/skill_adapter.py`：现有平台中立 API 委托接口，不等同于已完成 P16 外部能力注册与使用。
- 原 Memory/P04、Router/P05、Composer/P06、P07、P08 Direct/Optional Planner、P09 C1、P12 生命周期和 P15 活跃/恢复门禁。
- `src/continuity_engine/services/capability_ports.py`、原 CapabilityCoordination 与 JsonIntegrationRepository：唯一 E5-A 请求/结果/attempt 恢复基础。
- `src/continuity_engine/domain/action_capability.py`：已有与冻结外部 Capability v1 区分的内部动作类型，不可另建一套平行请求账本。
- 现有 `CapabilityResultInterpreter` 是模型结果恢复路径，不能把外部检索数据伪装成模型 response_candidate 直接表达。

外部数据按“候选/经验证的 Result Observation”回流 Engine；需要时重新进入 Perception，再经 Router/Composer/Thinking。保留内容与其来源、权限、时效、不确定性之间的关系；模型生成结果仍恢复原 ThinkSession。外部 sourceEventId 不能冒充内部 Event 身份，外部载荷不能携带可执行的 StateMutation 授权。

信息不足可以形成 Information Need；简单明确的查询走 Direct，复杂多步才用 Optional Planner，不强制所有查询建 Goal/Plan，model.generate 仍保持原 Thinking 路径。

## AMENDMENT OVERRIDES 与 KEEP RULES

P01—P21 只用 Engine 内 Fixture/Fake Adapter、Research/Test World、宿主中立端口和隔离数据根；本阶段不访问 Vio/Assistant 的进程、仓库、数据、凭据或网络，不使用真实密钥、外网或真实 MCP 服务。真实连接器与平台 Adapter 生产接入仍属于 P22。

SubjectState 是当前主体状态唯一权威；Event 是内部事实历史权威；Timeline、索引和缓存不能变成第二事实源。Memory 是记忆，Self-Narrative 是解释；长期状态变化仍经过既有 Evolution/revision。

现实权限边界管理能力访问、数据流出和现实副作用，不增加思想、情绪、人格、Desire、Will 或心理冲突审查。不能为了 P16 重新设计主体定位或收缩已确认的主体表达权利。

P01 Snapshot/Branch 仅用于隔离实验恢复。P16 不建设完整 P17 Execution/Reality/Outbox/补偿体系，不假定 P20/P21 的生产恢复已就绪，也不提前建设 UI、后台常驻或生产认证。

## 首批测试能力与 NOT READY

本简报提出的首批范围只用于本地测试：外部记忆检索、知识条目检索，以及无现实副作用的 MCP/Skill 查询或确定性处理示例；对应本地 Fake Adapter。每项显式登记描述、版本、capabilityRef、输入输出结构、所需权限和限制，不能将本地演示写成真实网络互通。

用户尚未指定生产首批外部记忆库、MCP 服务和 Skill 产品清单，继续登记为待决定；不要替用户挑选供应商、安装第三方服务、索取密钥、开账号或默认开放整个工具目录。这个待决定项不妨碍建设已授权的中立端口及本地测试能力，但阻止真实服务接入。

Credential Broker 只验证引用、绑定和状态，宿主负责保管真实凭据；引擎不接收或持久化原始 API Key。测试使用可识别的合成秘密标记检验拒绝/脱敏路径，不使用真实秘密。不得把扫描器没有命中当成不存在秘密流入的证明。

## 十二项施工验收分解

以下是对原 P16 要求的施工分解，不冒称原件已经逐项编号。实施时给每项绑定实现文件、正常场景、反例、复现命令、原始结果和状态。

| 项 | 范围与验收重点 |
| --- | --- |
| P16-01 | Memory Provider 中立端口与本地 Fake，真实检索结果走已有记忆/Context 入口。 |
| P16-02 | Knowledge Provider 中立端口与本地 Fake，区分外部知识、内部经历与主体判断。 |
| P16-03 | Connector/Provider 注册、禁用、版本和替换；能力描述不成为请求账本或状态权威。 |
| P16-04 | MCP/Skill 注册与有界输入输出；本地实例可实际调用，旧 facade 保持兼容，不宣称已有真实 transport。 |
| P16-05 | Credential Broker 引用与主体/环境/连接器绑定，凭据撤销、缺失、过期与秘密隔离。 |
| P16-06 | 统一外部候选类型：来源、版本、内容 hash、客观时间/时效、权限、根身份和不确定性；损坏/伪造/越界结果明确拒绝。 |
| P16-07 | 当前权限与生命周期检查覆盖首次调用、结果消费、缓存复用和恢复后新执行；撤权不被历史成功绕过。 |
| P16-08 | Router/Composer 最小检索、预算、同根去重及冲突标记；保留 P12 停用/归档/权重语义和 P15 学习当前支持校验。 |
| P16-09 | 离线、超时、取消、空结果和有界重试；明示失败/不可用，资源核算不重复，不无限占用 tick。 |
| P16-10 | 缓存版本、时效、权限与绑定重验；过期数据不能冒充新结果，也不能靠换包装升级为新的独立证据。 |
| P16-11 | 持久化与重启恢复复用 E5-A；同身份不同内容冲突、重复回执、已完成/未执行/UNKNOWN 分离；历史事实可核实恢复，不盲目重发未知调用。 |
| P16-12 | 正常 C1 端到端与跨进程 Golden，覆盖能力替换/撤销及重启；Feature Gate 关闭与旧格式兼容；隔离、秘密与审计证据齐全。 |

注册表可新增其职责所需的元数据持久化，缓存可新增可重建存储；不能借此建立第二套 operation/result 权威。内部类型可以按必要范围扩展，但不得回写冻结的外部六份 Schema/契约。若实际无法复用或需要改变已冻结边界，先报告冲突，不能用任意新内部字段绕过冻结。

## FILES ALLOWED 与 FILES FORBIDDEN

允许在既有 domain/services/storage/testing 责任目录中新增必要 P16 内部类型、端口、注册/查询/缓存实现和隔离 Fixture，及直接相关原服务的最小接线。先列出具体计划文件，再实施；避免无关重构或大范围格式化。新增正式测试位于 `tests/test_p16*.py`。

允许增加 P16 Stage Brief、十二项矩阵、恢复语义、测试/独立复核索引及必要证据，并同步直接相关现行档案。阶段档案编号预期接续 75—78，开工决定预期 D-068；先确认是否空闲，不覆盖已有编号，不创建验收决定。

禁止修改三份规划原件、63 项保护文件及冻结外部 Schema/契约、正式七文件和数据根、版本 0.1.0、已验收历史证据与排除脚本。首轮现有 1208 测试身份及原断言完整保留；若确有原测试需兼容调整，先区分真实缺陷与 Fixture 假设，不能删测试、降断言或伪造 PASS。

不改 Assistant/Vio，不真实联网/安装服务，不读真实凭据。正式删除、归档及可见性政策仍待用户决定，本阶段不代替用户选择。

## TESTS REQUIRED 与效率

1. 先记录源码、测试身份、Git、保护清单、正式数据与排除项 hash；引用已核验 P15 全量作为开工基线，不冒称本轮重跑。
2. 先做定点正常/反例测试，再完整 P16，再按真实依赖选择兼容组合。恶意数据只测试其不能改变指令/授权/状态权威，不通过删除合法内容或强制友好化“修复”。
3. 特别覆盖：查询后消费前撤销、缓存有效但权限失效、同身份版本/hash 变化、跨主体/环境/连接器结果、返回伪造 StateMutation、原始秘密进入错误消息、同根重复、多次重启与重复回执、UNKNOWN 与 NOT_EXECUTED、新执行时主体已暂停/归档/删除。
4. 同时保留合法来源、当前有效权限、真正旧格式、已提交事实恢复以及不同真实根的正向对照；拒绝场景验证无未授权调用、无主体变化和无秘密写入。必要审计写入与“全部零写入”分开描述。
5. 在正常 C1 用本地 Fake 形成可核对的查询、候选、获准 Context 消费和结果回流；必要状态变化只经原门禁/Evolution。安排真实子进程重启 Golden，并验证 P01 测试恢复覆盖新增持久化，绝不碰正式数据。
6. 最终代码稳定后跑一次完整回归；只有新失败或相关代码再次变化才按影响补跑，不机械三轮全量。保留原 1208 身份，新增项单列；WinError 1314 的既有 SKIP 如实报告，不算 PASS。
7. 每次使用唯一标签保存命令、退出码、stdout/stderr、方法身份、PASS/SKIP/FAIL/ERROR、耗时与执行前后源码 hash；保留首次失败、中间错误和历史结果，不覆盖日志。
8. 终局检查：源码解析、文档链接、秘密扫描、差异、精确成果清单、冻结/正式数据/排除项指纹。原有两处已记录格式问题分别是失败日志行尾空格和 subject_lifecycle_ports.py 的 EOF 空行；保留历史，不混称新缺陷或全部 diff 检查无提示。

## PLANNING CONFLICT 与交付

当前静态核对未见 P16 与已批准独立施工范围冲突；实施中若需要真实网络、供应商决定、Vio、冻结契约修改或新的外部权限，停止对应未授权部分并报告，不以“阶段已授权”推定这些选择已获授权。范围内实现缺陷可正常修复并留证；新出现且超出本范围的问题请用户决定。

完成后停在 P16/Engine side/十二项 IMPLEMENTED_NOT_ACCEPTED，P17—P23 NOT_STARTED。报告实际能力、未就绪边界、全部测试与历史失败、源码身份、精确变更清单和真实 Git 状态。两类 conflict 按事实登记：施工方已知缺口闭合不等于用户验收；出现独立阻断不能擅自清空。

开工、阶段进展及当前有效授权边界写入 P16 Stage Brief，压缩上下文后从当前记录接续，不返回 P15 push 指令。交回用户转发独立复核，不向其他任务自动发送资料。未经后续明确确认，不验收、不提交/push、不开始 P17。
