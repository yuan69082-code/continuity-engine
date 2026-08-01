# Changelog

本文件记录 continuity-engine 的版本级变化。格式参考 Keep a Changelog，但只记录可由当前代码、测试和本次档案工作确认的事实。仓库目前只有一个汇总式初始提交，早期变化无法可靠分配具体日期。

## [Unreleased]

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
