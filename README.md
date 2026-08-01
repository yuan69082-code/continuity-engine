# Continuity Engine

连续性引擎是位于 AI 模型之外的独立连续性层。它与 Vio 平台后端是边界独立、数据库独立的平行系统，通过正式版本化契约协作；Vio 前端只连接 Vio 平台后端。它保存的不是聊天记录，而是主体状态及其随事件发生的连续变化。模型、Tool、MCP 和设备只是经 Vio 管理的外部能力，不是主体状态权威。

当前版本为 `0.1.0` 原型，重点是建立可保存、可演化、可审计并受权限与资源约束的连续性内核。它不是已经具备真实自主执行能力的生产 Agent。

## v0.1 能力状态

### 已实现的内部能力

- `SubjectState`：六个状态分区、revision、JSON 保存与重启恢复。
- `Event / Evolution`：显式事件、状态变化规则、before/after 差异、`StateUpdateRecord` 和 expected_revision 保护。
- Memory 管理层：检索请求、候选相关性判断、`MemoryRetrievalResult` 和影响记录接口。
- Awakening：手动、定时和事件触发的单次唤醒流程，`WakeSession`、`WakeContext` 和确定性决策。
- Perception：只读的确定性感知层，输出关注、时间、关系、记忆影响、观察和内在驱力。
- Thinking：直接接收 `PerceptionResult`，通过 `ThinkSession` 保存摘要、预算、结果和关联信息；模型执行器可插拔。
- Action：生成受权限、风险、资源和 revision 约束的 `ActionDecision` 与 `ActionPlan`，不执行真实动作。
- Permission：权限连续状态、变化历史、`PermissionContext` 和本地 JSON 恢复。
- Learning：受控候选、证据验证、长期特征、固化/回滚事件和审计历史；不训练模型。
- Resource Management：`ResourceState`、`ResourcePolicy`、`ResourceManager`、确定性预算和资源检查入口。
- 进程内 API：统一请求响应、安全门以及状态、记忆、感知、思考、行动计划、唤醒和聊天入口。
- 本地 HTTP 服务：为调试前端提供静态资源、状态读取和聊天请求。
- 调试前端：最小聊天界面、错误展示、SubjectState 摘要、revision 和最近事件视图。
- 第一轮机器契约基础（Engine E1）：类型化 `ContinuityInteractionRequest`、`message_created` PlatformObservation、`message_version` fact、固定 SubjectBinding fixture，本地 Draft 2020-12 Schema registry、严格校验、RFC 8785 与三项 hash 验证。

其中 Memory、Awakening、Thinking、Learning、Resource Management、接口和前端属于“内部结构或本地原型已完成，真实外部集成仍未完成”。Action 完成的是决策规划层，不包含执行层。

### 尚未实现

- 真实 GPT、Claude 或其他模型 Provider 接入。
- 真实 MCP 连接或 MCP 协议传输。
- ChatGPT、Claude 或其他平台的真实 Skill 接入。
- 外部长期记忆库、向量库或记忆数据库。
- Execution Engine、真实联系用户或真实工具调用。
- 自动后台循环、常驻调度或无限自主运行。
- 真实 Token 计量、账单、计费、购买或支付。
- 生产数据库、用户认证、多租户和生产部署。

`ContinuityMCPAdapter`、`SkillAdapter`、`ThinkingProvider` 和 Memory 端口只是可插拔接口或适配边界，不能视为对应外部能力已经接入。

## Vio 连接契约状态

2026-07-30，Continuity Engine 通过《Engine Contract Final Read-Only Short Confirmation v1》正式接受 `Continuity Integration Contract v1.1`。长期系统边界和第一轮机器契约语义已经闭合；Vio 与 Continuity Engine 双方工程档案同步、引擎定点文档修正和双方工程档案最终只读复核均已完成，双方档案一致。

双方随后共同确认了第一轮施工范围。2026-08-01，Continuity Engine 完成 Engine E1：三份正式 Schema、类型化机器契约结构、固定 SubjectBinding fixture、本地离线 registry、严格 Schema/交叉字段/hash 校验和正式一致性向量测试已经实现。该完成状态只覆盖机器契约基础，不表示第一轮连接已经完成。

Engine E2 尚未开始。当前仍没有 `ContractTestAdapter`、request/operation/result 持久化账本、跨重启完整结果重放、stateProjection 生成或接收、Vio 实际连接和双方共享测试。现有 `APIService.submit_message`、本地 HTTP 与 `UserInteractionService` 也没有被改造成第一轮摄取入口。机器契约决定见 [`D-025`](docs/project_memory/04_决策记录.md)，E1 实现边界见同文件 `D-026`。

## 当前开发阶段

第一轮最小连接施工的 Engine E1 已完成；下一阶段 Engine E2 尚未开始。E1 只负责解析和验证契约输入，不运行完整交互、不持久化幂等结果、不生成投影，也不连接 Vio。

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
│   ├── schemas/        # E1 三份 Draft 2020-12 Schema 单一权威来源
│   └── local_frontend_app.py # 本地依赖组装与显式初始化
├── frontend/
│   ├── index.html      # 最小聊天与状态调试界面
│   ├── app.js          # 页面交互
│   ├── client.js       # FrontendClient
│   ├── styles.css      # 调试界面样式
│   └── __main__.py     # python -m continuity_engine.frontend
├── cli.py              # 本地验证入口
└── __main__.py         # python -m continuity_engine
tests/                  # 单元测试；含 E1 正反向契约一致性测试
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

当前测试基线：117 项（原有 87 项继续通过，E1 新增 30 项）。
