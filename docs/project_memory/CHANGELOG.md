# Changelog

本文件记录 continuity-engine 的版本级变化。格式参考 Keep a Changelog，但只记录可由当前代码、测试和本次档案工作确认的事实。仓库目前只有一个汇总式初始提交，早期变化无法可靠分配具体日期。

## [Unreleased]

### P03 User Acceptance Closure — 2026-08-30

- 用户于 2026-08-30 正式验收 P03；P03、P03 Engine side 与 P03-01—P03-12 当前全部为 `ACCEPTED`，P03 Vio dependency 保持 `NONE`。
- Event 继续是客观历史事实权威，SubjectState 继续是当前主体状态权威，Timeline 继续是无写入权的只读派生投影；P03 验收不改变 Authority 或冻结契约。
- 开工 444、初版 22/469、两项语义返修 28/475、回退时钟恢复返修 31/478 及三项阻断失败历史全部保留。P04—P23 继续 `NOT_STARTED`，本次不授权 P04、P10、Vio 或 Git 操作。
- 本次只同步验收状态、D-042、矩阵、索引和工程档案；不修改运行代码、测试、Schema、`pyproject.toml`、正式数据或版本 `0.1.0`。

### P03 Event Time and Read-only Timeline — 2026-08-30

- 用户在 P02 `ACCEPTED` 后单独授权 P03 Engine 独立施工；P03 Vio dependency 为 `NONE`，P04—P23 保持 `NOT_STARTED`。
- 原位扩展 Event 为可验证分类、来源、证据、内部/来源/关联身份，以及 `occurredAt / observedAt / recordedAt` 三时间；旧单时间 JSON 以 `LEGACY_COALESCED` 向后兼容。
- exact duplicate Event 变为精确幂等重放，不重复 Event、mutation 或 revision；相同 eventId 的不同 canonical body 以身份冲突失败关闭。恢复路径返修后，既有 eventId/canonical identity 判定先于新 Event 时间门，跨重启、回退时钟及已有后续 revision 后的重放保持原历史 update 身份且不读取 applied clock。
- correction/revocation 只追加新 Event；缺失、跨 Subject、前向引用在持久化加载与 Timeline 重建时均失败关闭。监工返修后，FACT、OBSERVATION、INTENTION、CORRECTION、REVOCATION 无论是否迟到均不能携带 mutation；显式 recordedAt 必须不晚于单次读取的 appliedAt。
- 新增无写入权的 `TimelineProjection` / `TimelineService`，仅从 StateUpdateRecord/Event 历史重建，提供 UTC 确定性排序、时间窗口、first/last、distance、chain 和来源/分类/correlation 过滤。
- 新增版本化本地 P03 Fixture/adapter 与 Golden Scenario，区分 intention 和事实、固定争执/和解顺序，并由 SubjectState 权威表达当前关系；不访问 Vio、网络、真实 Provider 或凭据。
- 三项监工语义阻断已定点返修；当前恢复阻断矩阵 4/4、P03 专项 31/31、相关链路 174/174、Engine 全量连续三轮 478/478。施工和返修完成时均保持 `IMPLEMENTED_NOT_ACCEPTED`；其后的用户正式验收状态见上方 P03 User Acceptance Closure。

### P02 User Acceptance Closure — 2026-08-29

- 用户于 2026-08-29 正式验收 P02；P02、P02 Engine side 与 P02-01—P02-12 当前均为 `ACCEPTED`。
- P02 Vio dependency 保持 `NONE`；Real Provider/Vio/PWA production integration 继续 `DEFERRED_TO_P22`；P03—P23 继续 `NOT_STARTED`。
- 本次只同步验收状态、D-040、矩阵、索引和工程档案，不修改运行代码、测试、Schema、`pyproject.toml`、正式数据或版本 `0.1.0`，也不执行 Git 暂存、提交或推送。

### P02 Engine Host-Neutral Model Capability Loop — 2026-08-28

- 新增宿主中立 `ModelProvider` Port、显式 Provider/Model Profile policy、Engine 内确定性 Fake Provider，以及持久化 execution/usage/test-credit 测试账本。
- 以 Alibaba Cloud Model Studio / `qwen-flash-2025-07-28` 作为可替换 Fake Profile 元数据，固定单次 1024、每日 10240 synthetic Token、每次唯一成功 execution 记 1 test-credit、fallback 关闭；不代表真实供应商价格或调用。
- 复用 E5-A 唯一 `model.generate` durable pause/resume，覆盖 success、generation/network failure、timeout、UNKNOWN 查询优先、retryable/terminal、cancelled/expired、预算耗尽、响应丢失、多轮和崩溃恢复；不重复 execution、credit、Thinking、Action 或主体结果。
- 初次施工时 P02 专项 33/33、P01+E5-A+P02 相关链路 129/129、Engine 全量 430/430 通过；该组数字作为历史基线保留。
- 规划监工发现的 UNKNOWN/TIMEOUT 查询解析、部分每日预算调用前约束、usage/test-credit 加载期验真三项阻断已定点返修；当前定点矩阵 16/16、P02 专项 47/47、相关链路 143/143 通过。
- D-039 验收前置返修把 E4/E5 HTTP 所有“读取正文前拒绝 POST”统一为 response-first、flush、半关闭写端和有界固定缓冲丢弃未读输入；不改变认证优先级、路由、状态码、JSON、限制或外部契约。413/401 各连续 50/50、前置拒绝矩阵 20/20、E4 HTTP 340/340、E5 HTTP 140/140，Engine 全量连续三轮 444/444 通过。
- P02 与 Engine side 当前为 `IMPLEMENTED_NOT_ACCEPTED`；P02 Vio dependency `NONE`，真实 Provider/Vio/PWA production integration 后置 P22，P03—P23 未开始。
- 未修改六份冻结 Schema、生产 HTTP/API/Capability/Binding 外部契约、正式数据或版本 `0.1.0`；未访问网络、凭据或 Vio，未执行 Git 提交或推送。

### P01 User Acceptance Closure — 2026-08-27

- 用户于 2026-08-27 正式验收 P01；P01、P01 Engine side 与 P01-01—P01-12 当前均为 `ACCEPTED`。
- P01 Vio dependency 继续为 `NONE`，Vio/PWA production integration 继续后置到 P22；P02—P23 全部为 `NOT_STARTED`，P02 未授权。
- P01 仍只提供测试、实验和 Research Sandbox 的 Snapshot/Rollback，不构成正式 Subject、Owner Domain 或生产恢复；P20/P21 边界不变。
- 本次只同步验收状态和执行提交前核查，不升级 `0.1.0`，不修改运行代码、测试、Schema、正式契约、正式数据或 Vio，也不执行 Git 提交或推送。

### P01 Engine Independent Boundary Closure — 2026-08-27

- 按三份 2026-08-26 最新规划正文重新校准 P01：P01—P21 由 Engine 独立施工与验收，P01 Vio dependency = `NONE`；Vio/PWA production integration 后置到 P22。
- 三份附件按指定 python-docx/NFKC/空白折叠算法的 normalized body SHA-256 全部匹配，并通过 P01—P21 独立施工、P10 实际建仓及 P22 首次重连等语义锚点核对。
- 现有 P01 代码无需重写；四项旧缺陷定点回归、42 项 P01 专项、正式链路和完整回归继续作为 Engine 独立证据。P01 仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`，未升级软件版本、未修改冻结 Schema 或 Vio。

### P01 Engine Review Repair — 2026-08-26

- 保留首次 P01 施工及四项缺陷复现历史，完成标准 Engine 交互 `changed=true`、revision `1→2`、真实 Wake/Think/Action/operation/result 持久化与精确 rollback。
- Snapshot 扩展为 19/19 组件 closed-world inventory；增加 descriptor/registry 外部 anchor，未知/重复物理文件与重算内部 hash 的篡改均失败关闭。
- 增加 acceptance receipt 强制门、ACTIVE 创建即 24 小时 lease、正式整树 hash 与 repository root 隔离证明。
- P01 专项 42/42、相关正式链路回归 200/200、Engine 完整 397/397 通过。P01 仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`、Vio cooperation `NOT_STARTED`；未修改软件版本、冻结 Schema、正式契约或 Vio。

### P01 Engine Test Sandbox Infrastructure — 2026-08-25

- 新增独立 `continuity_engine.testing` TEST Sandbox：disposable Subject/Binding/cycle/namespace/root、Frozen Clock、synthetic Fixture、完整 Snapshot/Branch、原子 rollback、test-only Memory、证据导出、retention 和受保护清理。
- Snapshot 以 15 个逻辑组件的 canonical hash、物理文件 hash、revision/count 和 completeness 验证；缺失/篡改失败关闭，`changed=true` 回滚后逐项精确恢复。
- 固化 `promotionAllowed=false` / `PROMOTION_FORBIDDEN`，以及成功自动清理、失败 24 小时、debug 最长 7 天、无后台 Scheduler 和 link/junction/正式路径拒绝边界。
- 新增 29 项 P01 专项；当前完整本地回归为 384 项。P01 整体仍为 `IN_PROGRESS`，Engine side `IMPLEMENTED_NOT_ACCEPTED`，Vio cooperation `NOT_STARTED`；软件版本继续为 `0.1.0`。

### P00 User Acceptance Closure — 2026-08-25

- 规划监工窗口完成 P00 核查后，用户于 2026-08-25 正式验收 P00；P00 与 P00-01—P00-12 当前状态同步为 `ACCEPTED`。
- P01—P23 继续为 `NOT_STARTED`；P01 未获授权，仍须单独 Stage Brief 和用户明确授权，不得自动开始。
- 本次只收口工程档案与验收证据，不修改运行代码、契约、Schema 或软件版本，也不执行 Git 提交或推送。

### P00 Planning, Contract and Independent Upgrade Baseline — 2026-08-25

- 以确认同步版 v1.1/v6.7 建立 P00—P23 唯一施工底图，并新增 P00 阶段基线、施工测试验收矩阵、档案与测试索引、风险回滚与用户决策入口四份专责档案。
- 冻结 Engine/Vio 定位、Subject Authority、六份交互/Capability Schema、D-025 hash 证据、P10 分支语义、P01/P20/P21 恢复边界、唯一现实行动链和 Reality Boundary。
- 登记 Engine 与只读 Vio 的 Git、版本、测试、迁移及独立升级基线；历史连接能力保留，但不构成双方运行或施工依赖，生产 World Adapter 重连仍属于 P22。
- 本次仅修改工程档案，不改变软件版本或运行能力。该次施工完成时 P00 为 `IMPLEMENTED_NOT_ACCEPTED`，P01—P23 均为 `NOT_STARTED`，尚未获得进入 P01 的授权；其后验收状态见上方 P00 User Acceptance Closure 记录。

### S4-Live First Real Provider Acceptance Archive — 2026-08-14

- 正式记录 S4-Live 首次真实供应商单次试聊 `PASS`：在不可晋升的 `disposable_test / promotionAllowed=false` 身份和仓库外短路径可销毁沙箱中，经正式 V5/V1/V3/Engine E5-A/V4/V2 链路完成一次真实调用。
- Alibaba Cloud Model Studio OpenAI-compatible Provider 的 `qwen-flash-2025-07-28` 恰好执行一次并 succeeded，报告 input/output/total Token 为 177/9/186；唯一 CapabilityResult `SUCCEEDED` 首次回传 HTTP 200，result outbox 和 Conversation Turn completed，没有重复 execution/result/Message、incident 或 outcome_unknown。
- 最终主体表达只来自 Engine `FirstRoundSuccessResult.response.content`。Engine `changed=false`、revision `0→0`、`engineUpdateId=null`，没有 Event、StateMutation 或 StateUpdateRecord；该验收没有覆盖真实模型 `UPDATE_STATE`。
- API Key 未进入 Engine 或档案；Vio 费用账本为 `cost_status=not_reported`，不能把供应商界面当时约 0 解释为最终绝对零费用。三个服务端口已停止，沙箱已整根删除且未触及仓库或受保护路径。
- 保留供应商调用前的 Windows 路径预算事故历史；该次没有 CapabilityRequest、Provider execution、CapabilityResult 或费用，修复位于 Vio 启动前门禁/清理边界，没有修改 Engine。
- 本次只同步 Markdown，不提升 `0.1.0` 软件版本。通用 Provider、正式身份/Binding、日常使用、真实状态演化、生产认证、多租户、外网、部署及后续外部能力仍未完成。

### Engine S4-R Acceptance Archive Sync — 2026-08-13

- 正式记录 Engine E5-A、Vio V4、受控 S4 Capability 联验、Vio V5、F1、L1 已完成，Engine S4-R 独立追认结论为 `PASS`；当前双方基线为 Engine `cba52126db2fb5eca57d9b5c0c80884693c59a6f`、Vio `239759d1d219bd140f41257c5da18169fbf773a9`。
- 记录仓库外固定 Binding 的 Engine 独立 RFC 8785/SHA-256 复算通过、L1 只读安全准备、Capability 结果回流原 Thinking/Action、Action Gate 和跨重启幂等边界；Contract v1.1 与 SubjectState 权威未改变。
- 验收基线为 Engine E5 54/54、Engine 全量 355/355、Vio L1 24/24、Vio 后端 202/202、S4 shared 7/7、V5 shared 6/6、Vio 前端 19/19。
- 本次只同步工程档案，不提升 `0.1.0` 软件版本。真实供应商、真实模型调用、真实 API Key、真实费用和 S4-Live 均未发生；生产认证、多租户、公网、部署及后续外部能力仍未完成。

### Engine E5-A — Durable Capability Pause / Resume Core — 2026-08-10

- 新增独立 `continuity-capability/v1` CapabilityRequest、受约束模型输出和 CapabilityResult 领域模型，配套三份严格 Draft 2020-12 Schema、封闭 registry、RFC 8785/SHA-256 hash 和身份/关联验证；不修改 v1.1。
- ThinkSession 新增 `WAITING_CAPABILITY`；capability 模式在 Perception 后持久化不可变请求并暂停，结果返回后经解释器恢复原 Thinking，再进入 Action Gate 与 ReplyComposer。外部结果不能携带 StateMutation，也不能直接修改 SubjectState。
- 新增 capability request/attempt durable ledger 与 operation journal format v3 checkpoint，兼容读取 E4 v1/v2；Action 完成后先持久化结构化 `ActionExecutionResult`，再进入 domain checkpoint。相同请求/结果精确幂等，冲突和损坏状态失败关闭，跨重启不重复 Thinking、Action 或最终结果。
- 同一 E4 服务新增 Engine 侧 capability result 提交/查询语义；默认 deterministic 模式、既有 v1.1 HTTP envelope、SubjectBinding、Action/Evolution 和 E4 recovery 行为保持不变。
- 完成 E5-A 定点复核修正：成功输出在落盘前执行去空白非空校验，CapabilityResult 时间不得早于已持久化请求创建时间，重复 `init` 可验证未使用、等待、retryable/unknown 与已完成 Capability 历史而不改写持久化事实；错误 `serve` 模式仍拒绝。
- 新增 54 项 E5-A 测试，Engine 全量 355 项通过。该里程碑只完成 Engine 核心；Vio V4、真实模型、现实权限/安全确认、供应商调用、真实 usage 和双方共享验收尚未实现，软件版本继续为 `0.1.0`。

### Vio × Engine Formal Local HTTP/JSON Shared Acceptance — 2026-08-09

- 以 Continuity Engine `189441f9bad2a34119b4ef10365a4385ed0949cc` 和 Vio `35780da56c72b822fc018702dfe5e90674ab0fcb` 为正式基线，记录第一阶段本地回环 HTTP/JSON 双方验收通过。
- Vio 的真实持久化请求经正式 V3 transport 进入独立 Engine E4；completed、not_found、recovery_required、POST 响应丢失，以及 Engine/Vio 分别或同时重启均通过。
- S2+S3 15/15、Vio V1+RFC 8785+V2+V3 64/64、Vio 后端全量 113/113、Engine crash-recovery 15/15、E4 67/67、全量 301/301；request/operation 身份、Wake、Thinking、Event、StateUpdateRecord、revision、投影和双方账本未重复。
- 保留首次 S3 在 Engine `c5ebbf9b7583f3fb50198a3bf37ea0553edc131f` 上发现恢复缺陷的历史；D-032 修复后的原失败场景和全部 S3 已通过。
- 本里程碑不提升 `0.1.0` 软件版本，也不表示外网连接、生产部署、真实模型/Capability/MCP/Tool/设备、Vio 公共对话 API 或前端真实链路已经完成。下一阶段尚未开始。

### Engine E4 Durable Domain Crash Recovery — 2026-08-09

- 为 operation journal 增加 domain 子阶段稳定恢复身份与 Wake/Perception/Thinking checkpoint；兼容读取旧 format v1，并以 format v2 保存 durable progress。
- WakeSession 保存结构化 WakeContext 恢复快照，ThinkSession 保存结构化 PerceptionResult 恢复快照；已完成 Wake/Thinking 必须复用，running/failed、多个候选或矛盾状态失败关闭。
- 支持恢复旧 E4 `reserved/domain=null` 但完成 WakeSession/ThinkSession 已落盘的部分状态；继续保证 Action 身份稳定、Evolution 单次提交、completed result 精确重放，以及 Event、StateUpdateRecord 和 revision 不重复。
- 新增 15 项 crash-recovery 回归；E4 相关 82 项、Engine 全量 301 项通过。Vio V3 已开始正式本地 HTTP 验收，但 S3 尚未通过；当前等待在新 Engine SHA 上重跑。
- 本修复不改变外部 HTTP envelope、v1.1、Schema/hash、SubjectBinding、Vio、生产架构或 `0.1.0` 软件版本。

### Engine E4 HTTP/1.1 Transport Boundary Hardening — 2026-08-08

- 第一阶段正式本地服务统一为一请求一连接；success、机器 envelope、查询、health 和全部传输错误均发送 `Connection: close` 并停止复用当前连接，未消费的请求体不再污染下一请求。
- 每条连接新增默认 10 秒、正有限且可验证的读取超时；部分 body 超时后关闭当前连接，串行服务可继续接受健康检查和正式请求。
- 未知 HTTP method 与可安全响应的解析错误改用固定最小 JSON，普通客户端提前断连不再向 stderr 输出 Python traceback 或内部信息。
- 新增 6 项配置及原始 socket 回归；E4 专项由 61 项增至 67 项，Engine 完整测试由 280 项增至 286 项。
- 本修正不改变 `ContinuityInteractionService`、v1.1、Schema/hash、SubjectBinding、幂等/revision/checkpoint、Runner、Vio 或 `0.1.0` 软件版本；Vio V3 与双方 HTTP 共享验收尚未开始。

### Engine E4 — Formal Local HTTP/JSON Integration Adapter — 2026-08-03

- 从 E3 `ContractTestAdapter` 抽取唯一正式 `ContinuityInteractionService`，测试 Adapter 与正式 `IntegrationAdapter` 共用同一验证、领域、Action Gate、Evolution、结果和 checkpoint 恢复链。
- 新增正式单 active SubjectBinding 与原子 JSON 仓储、显式幂等 init、completed/recovery_required 查询，以及只监听 `127.0.0.1:8766` 的串行 HTTP/JSON 服务；内部路由使用 Bearer 服务令牌和严格传输限制。
- E4 专项 61 项、完整 280 项测试通过，原 219 项继续通过；三份 v1.1 Schema、JSONL Runner、旧调试入口、Vio 仓库和 `0.1.0` 软件版本未改变。
- E4 只完成 Engine 侧正式本地服务。Vio 尚未调用，双方 HTTP 共享验收、生产形态 Integration Adapter、真实模型/Capability 和生产部署尚未实现。

### Vio × Engine First-Round Test-Only Shared Acceptance — 2026-08-03

- 以 Engine `7a32a99e60330782c1caf6d6adda5d08d0077a6c` 和 Vio `673983901b38127b15f772a8be8507defec7384e` 为正式基线，记录第一轮 test-only 端到端共享验收通过。
- Vio 持久化 V1 请求已通过 JSONL Runner 进入真实 E3；Vio V2 已严格验证并保存 Engine 结果、revision 0/1 投影和三条 receipt，幂等、revision、四类错误及双方重启精确重放均通过。
- 验证结果为共享 6/6、Vio V1+RFC 8785 17/17、Vio V2 29/29、Vio 后端全量 95/95、Engine Runner 16/16、Engine 全量 219/219。
- 本里程碑不提升 `0.1.0` 软件版本，也不表示正式本地服务、网络连接、生产 Integration Adapter、真实模型或前端数据链路已实现；下一阶段须另行共同确认与授权。

### Engine JSONL Runner Independent Acceptance — 2026-08-02

- 记录项目统筹窗口独立技术验收 Engine test-only JSONL Runner 正式通过；专项 16 项、完整 219 项和 93 个 Python 文件 AST 解析通过，未发现阻塞问题。
- 当前具备整理并提交同步 Runner 成果的条件；本次验收不改变 D-029 机器语义或 `0.1.0` 软件版本。
- Vio 尚未正式调用 Runner，双方端到端共享验收、Vio 投影接收、网络和生产 Integration Adapter 尚未完成；只有 Engine 提交同步后才能开始 Vio 测试代码实际调用。

### First Round Shared Acceptance Preparation — Engine JSONL Runner — 2026-08-02

- 在 `tests/shared/` 新增 test-only UTF-8 JSONL Runner 和真实 E3 装配辅助，必须显式使用受控临时数据目录；每行直接调用 `ContractTestAdapter.submit()` 并立即输出原始成功或错误对象。
- 支持固定 fixture 一次初始化、完整目录恢复、同进程/跨进程精确重放、重启后新请求 UUID 唯一，以及部分、损坏或矛盾目录拒绝启动；未增加网络、生产 CLI/HTTP 或外部能力。
- 新增 16 项真实子进程专项测试，完整 219 项通过，原 E3 验收基线 203 项继续通过。
- Vio 尚未实际调用 Runner，投影接收、双方共享验收、网络和生产 Integration Adapter 尚未完成；软件版本继续保持 `0.1.0`。

### Engine E3 Acceptance — 2026-08-02

- 记录项目统筹窗口独立验收 Engine E3 正式通过；`ContractTestAdapter`、Observation/Event 隔离、确定性领域闭环、Action Gate、Evolution、operation journal、中断恢复和跨重启精确重放均通过核对，未发现阻塞问题。
- E3 专项测试 50 项、完整测试 203 项全部通过；Engine E1、E2、E3 至此均已完成并通过验收。
- E3 仍只代表 Continuity Engine 侧 test-only、进程内闭环完成；Vio 客户端、投影接收器、双方共享测试、网络和生产 Integration Adapter 尚未实现。
- 当前未授权继续代码施工，下一步等待双方确定 Vio 侧施工和共享验收顺序；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E3 — 2026-08-01

- 在已提交同步的 E2 基线 `d1a96b1` 上新增独立、test-only、进程内 `ContractTestAdapter`，按 Schema/hash、Binding、ledger、revision、operation reservation 和领域闭环的固定顺序处理第一轮请求。
- 将已验证平台事实作为只读 `PerceivedPlatformFact` 送入 PerceptionResult；Thinking 只读取感知结果，平台 `sourceEventId` 不直接成为内部 Event/StateMutation。
- 新增确定性 MemoryRetriever、ThinkingProvider、ReplyComposer、TokenBudgetManager，复用真实 Wake、Perception、Action 权限/风险/资源/revision Gate 和必要时 Evolution；无获批 `UPDATE_STATE` 时不改变 revision。
- 新增 `ApprovedStateAction`、集中式 `ActionEvolutionService` 和阶段化 operation journal，以稳定 operation/response/event 身份支持跨重启中断恢复且不重复演化；不宣称多个 JSON 仓储之间具有跨文件原子事务。
- 新增 50 项 E3 测试；完整 203 项测试通过，E2 同步基线 153 项继续通过。
- E3 不复用或修改现有 API/HTTP/UserInteraction 调试入口，不包含 Vio 客户端、投影接收、共享测试、网络或生产连接；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E2 — 2026-08-01

- 在已提交同步的 E1 基线 `ac61e78` 上新增不可变第一轮成功结果、四类固定错误 envelope、最小 stateProjection 和严格恢复边界。
- 将 E1/E2 共用的 RFC 8785/SHA-256 规则集中到领域完整性模块，保留原 service 兼容导出；以同一实现计算 `stateHash` 与 `contentHash`，并新增固定 SubjectBinding fixture/hash 的本地持久化与恢复。
- 新增以 requestId 为永久键的不可覆盖 completed result ledger，支持同 hash 跨重启精确重放、不同 hash 冲突、subject revision 投影唯一和非空 engineUpdateId 唯一。
- JSON 存储使用 UTF-8、显式格式版本、临时文件、flush/fsync 与原子替换；损坏、缺字段、错误版本和 hash 不一致会明确失败。
- 新增 36 项 E2 正反向测试；完整 153 项测试通过，E1 同步基线 117 项继续通过。
- E2 不包含 `ContractTestAdapter`、完整交互编排、Vio 投影接收、实际连接或共享测试；软件版本继续保持 `0.1.0`。

### First Round Minimal Connection — Engine E1 — 2026-08-01

- 新增 v1.1 第一轮 `ContinuityInteractionRequest`、PlatformObservation、message fact、嵌套值对象和固定 SubjectBinding fixture 的不可变类型化模型。
- 新增三份 Draft 2020-12 Schema 作为单一权威来源，以及仅支持三个绝对 URN、拒绝网络/相对路径/别名回退的本地 registry。
- 新增严格 Schema、禁止状态写字段、identity/conversation/reference、正文位置、UTC 时间和 hash 校验；使用 RFC 8785 规范化并独立复算三个正式固定 hash。
- 新增 `jsonschema>=4.26,<5`（MIT）和 `rfc8785>=0.1.4,<1`（Apache-2.0）两个本地运行依赖。
- 新增 30 项 E1 正反向测试；完整 117 项测试通过，原有 87 项继续通过。
- E1 不包含 `ContractTestAdapter`、持久化账本、跨重启重放、投影、Vio 实际连接或共享测试；软件版本继续保持 `0.1.0`。

### Bilateral Archive Final Review — 2026-07-30

- 记录 Vio 与 Continuity Engine 双方工程档案最终只读复核通过，双方档案一致。
- 当前允许双方共同制定第一轮最小连接施工提示词，但提示词尚未制定完成；本次许可不授权代码施工。
- 第一轮代码施工、共享测试和实际运行时连接尚未开始，所有已列出的运行时连接能力仍未实现。
- 本里程碑仅同步文档阶段状态，不提升 `0.1.0` 软件版本。

### Architecture Consistency Correction — 2026-07-30

- 修正当前工程档案中残留的“Vio 前端直连 Continuity Engine”旧拓扑，统一为 Vio 前端只连接 Vio 平台后端，Vio 与引擎作为平行系统通过正式版本化契约协作。
- 修正“模型回复必然生成 StateMutation”的旧表达，明确只有 Action 合法批准 `UPDATE_STATE` 才能创建内部 Event/StateMutation 并进入 Evolution；未批准时 revision 保持不变。
- 保留历史施工和变更记录，并明确旧描述已被 v1.1、D-025 及本次定点修正取代。双方工程档案同步和定点修正已完成，当前等待最终复核；第一轮施工提示词、代码施工和共享测试尚未开始。
- 本次仅为文档与架构一致性修正，不提升 `0.1.0` 软件版本，也不表示任何连接运行能力已经实现。

### Integration Contract Archive Sync — 2026-07-30

- 记录 Continuity Engine 正式接受 `Continuity Integration Contract v1.1`，并完成 Continuity Engine 侧工程档案同步。
- 记录 Vio 与 Continuity Engine 双方档案同步完成、当前等待档案核对；第一轮施工提示词、代码施工和共享测试尚未开始。
- 本里程碑只涉及文档与架构决定，不提升 `0.1.0` 软件版本，也不表示 PlatformObservation、SubjectBinding、ContractTestAdapter、持久化账本、结果重放、投影连接或生产集成已经实现。

### Architecture Documentation — 2026-07-23

- 新增 `docs/project_memory/05_核心模块架构.md`，集中说明 Continuity Engine 十层核心架构。
- 为 SubjectState、Evolution、Memory、Awakening、Perception、Thinking、Action、Permission、Learning 和 Resource 分别记录当前状态、当前作用和未来扩展方向。
- 在项目总览中增加核心架构入口，并继续明确框架完成不等于真实模型、MCP、外部记忆、动作执行、后台运行或 Token 计费已经接入。
- 本次只新增和更新工程文档，没有修改源码或测试，也没有新增功能。

### Engineering Archive Sync — 2026-07-23

- 以《数字连续性引擎工程总档案 v1.0》同步长期工程档案，明确 Continuity Engine 是位于 AI 模型之外的连续性层。
- 记录目标实时状态闭环：用户输入 → SubjectState 读取 → Memory 检索 → 模型回复 → StateMutation → Evolution → SubjectState 保存。
- 统一 SubjectState、Evolution、Memory、Awakening、Perception、Thinking、Action、Permission、Learning 和 Resource 的框架完成口径，并明确真实接入边界。
- 记录工程总档案后续阶段 8—12：AI 模型、MCP/外部记忆、正式前端、自主学习完善和自主运行；这些均未标记为已完成。
- 明确真实模型、真实 MCP、外部长期记忆、真实动作执行、后台自主运行和真实 Token 计费仍未实现。
- 本次只同步 `docs/project_memory/` 工程文档，没有修改源码、测试、README 或项目配置，也没有新增功能。

### Fixed — 2026-07-23

- 为 `storage/base.py` 启用延迟求值类型标注，修复 Python 3.11–3.13 中 `PermissionRepository.list()` 遮蔽内置 `list` 后影响后续类型标注的问题。
- 保持 `PermissionRepository.list()` 方法名、参数和返回协议不变。

### Documentation — 2026-07-23

- 将 README 更新为 Continuity Engine v0.1 原型的真实能力范围。
- 明确 SubjectState、Memory、Awakening、Perception、Thinking、Action、Permission、Learning、Resource Management、进程内 API、本地 HTTP 和调试前端的当前边界。
- 明确真实 AI Provider、MCP、平台 Skill、外部长期记忆库、真实动作执行、后台常驻运行和真实 Token 计费尚未实现。
- 更新 `pyproject.toml` 的过期项目描述，并同步当前状态与施工日志。

### Verification — 2026-07-23

- Python 3.14.4 完整自动化测试 87 项通过。
- 全部 Python 源码和测试通过 Python 3.11 语法版本解析检查。
- 当前环境未安装 Python 3.11–3.13，因此未执行这些解释器的运行时测试。

### Documentation — 2026-07-22

- 新建 `docs/project_memory/` 长期工程档案系统。
- 记录项目总览、当前状态、归一化施工路线、历史施工摘要和架构决定。
- 记录已完成模块、未完成事项、待确认能力、未来扩展和开发规范。
- 明确当前 Git 基线、README/项目描述过期、缺少 LICENSE/CI 等交付风险。
- 完成档案最终校准：移除不存在的独立思考上下文类描述，独立记录 Event/Evolution，统一 MemoryRetrievalResult 名称，并将 Resource Management 标为部分完成。
- 本次仅新增文档，没有修改任何代码、README 或项目配置。

## [0.1.0] — 尚未发布

### Added

- SubjectState 六分区模型、revision、JSON 持久化和 CLI。
- Event、Evolution、StateUpdateRecord、前后差异和 expected_revision 并发保护。
- 可插拔 Memory 管理层、相关性判断和记忆影响记录。
- Awakening System：WakeCycle、WakeSession、WakeContext 和四类 WakeDecision。
- Thinking Engine：直接接收 PerceptionResult，通过 ThinkSession 保存上下文摘要、预算、结果和关联信息，并提供 ThinkingResult、ThinkingProvider 与预算接口。
- Perception Engine：关注、时间、关系、记忆影响、观察、内在驱力和摘要。
- Action Engine：Intent、Decision、Step、Plan、Session，及权限、风险、资源评估。
- Permission Continuity Layer：PermissionState、历史、Context 和 JSON 恢复。
- Learning：LearningEvent、PersonalityTrait、LearningRecord、验证、固化与回滚框架。
- Resource Management：ResourceState、RuntimeMode、TokenUsageRecord、Policy/Manager。
- APIService、统一请求响应、安全门、MCP Adapter 和 Skill Adapter 接口设计。
- 最小本地 HTTP/FrontendClient/聊天界面、状态调试入口和用户交互编排。

### Architecture

- 正式 SubjectState 修改统一经过 Event / StateMutation → Evolution。
- Perception 成为 Thinking 唯一直接输入层，并保持只读。
- Thinking 模型、Memory、Permission 和外部 Adapter 保持可插拔。
- Action 只决定和规划，不执行真实外部操作。
- 外部入口必须经过 PermissionContext 和 ResourceManager。
- 学习不训练模型，长期变化需要多证据、验证、确认并可回滚。

### Verification

- 当前完整自动化测试集：87 项通过。
- SubjectState、权限、学习和资源的 JSON 重启恢复路径已覆盖。
- Action 权限/风险/资源/revision 边界及 Wake → Perception → Thinking → Action → Evolution 完整链路已覆盖。
- API/Frontend 数据流与“不在前端保存核心状态”边界已覆盖。

### Not Included

- 真实 AI API、MCP 连接、外部记忆库或真实 Token 计费。
- Execution Engine、真实联系用户或真实工具调用。
- 生产数据库、认证、多租户、支付、生产部署或 SSE/WebSocket。
- 模型训练、参数更新、情绪模拟或无确认的永久人格改变。

### Repository Status

- `0.1.0` 来自 `pyproject.toml`；工程档案提交 `216bdfd` 已同步到 `origin/main`，当前发布前整理修改尚未提交，也没有版本标签。
- README 和项目描述已经同步；正式发布前仍需人工评审当前修改，并在后续独立任务中决定 LICENSE、CI 和版本标签。
