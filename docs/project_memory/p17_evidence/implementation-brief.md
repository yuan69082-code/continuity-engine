# P17 开工简报：Execution Engine、World/Capability Layer 与现实行动

日期：2026-09-09。执行仓库：`C:/Users/Administrator/Documents/continuity-engine`。本文件由规划侧准备，用户转发给 codex 引擎实施。规划侧没有修改 Engine，也没有跨任务派单。

## 1. STAGE 与授权

用户已明确要求：检查 P16 收尾及八处历史格式告警，没有问题即可开始 P17，并由用户转发提示词。规划侧只读核对已通过，详见 [baseline-verification.json](baseline-verification.json)。本次授权为 P17 Engine 独立实现、必要测试和档案同步，完成后交回独立复核；不是 P17 验收或 Git 写操作授权。

现行 P00—P16 ACCEPTED，P17—P23 NOT_STARTED。本次指令生效后按 P17 开工，不要因旧历史快照中的“等待 P17 授权”退回 P16 收尾。原成果保留，不重复验收或提交 P16。不开始 P18，不自行验收、暂存、提交、push、merge、rebase、tag/release 或切换分支。

## 2. SOURCE OF TRUTH 与核实基线

P16 D-069 已正式登记，十二项矩阵 ACCEPTED。规划侧本轮独立核实：

- main，提交 `0c440b0476b07723abafe93777fe895b64fd8d0e`；直接父提交 `a41a733635b0f5978c19b287274b4c63925b8979`。
- 提交说明 `feat: implement and accept P16 external capability providers`。
- 实际 226 项提交与精确清单完全一致，包含已复核的全部 192 项 P16 成果。
- 本地 HEAD、本地 origin/main 与实际 `git ls-remote origin refs/heads/main` 一致；已跟踪工作区和暂存区干净，本地 ahead/behind 0/0。
- 未跟踪仅原 31 个 P10 辅助脚本与 1 份旧 P14 接续报告；保持排除且原样保留，不作为待提交 P17 成果。
- 当前 243 个源码/测试/资源文件仍与已验证最终代码一致，63 保护项、三份规划、正式七文件、版本及独立证据副本未变。
- 行为基线引用已核验 1286 项：1285 PASS、1 既有 Windows symlink 权限 1314 SKIP、0 FAIL/ERROR，1072.026 秒。P16 独立 78 PASS 含原九项；额外独立四项不进入正式数量。本轮没有重跑这些测试。
- 八处历史格式告警已逐项实查：七处是 `p16_evidence`、`p16_repair_evidence` 原始失败 stderr 行尾空格；一处是 `p16_repair_evidence/test-history.md` 末尾空行。没有本次提交中的执行代码告警。保持证据原样，不为消除告警重写历史；新增告警另行检查，不统一忽略。
- 无已跟踪 Actions workflow。本轮没有独立读取 CI API，不声明远端 CI PASS；施工方报告 CI/check 查询 403 不等于测试 FAIL。

开工读取 README、现行状态、路线、`.agents/workflow.md`、相关代码与测试，并记录真实 Git、源码及测试身份。若现场已经有新增或重叠修改，先辨明归属；不得回滚、覆盖或伪造基线。

## 3. 原规划依据与优先级

用户本次授权和边界要求优先；阶段范围依据 2026-08-26 v1.1 P17 施工卡，v6.7 提供细节。2026-08-26 Engine 独立施工 OVERRIDE 优先于旧 Vio 联调表述。不得用较早阶段的历史暂停指令覆盖本次开工。

三个原件位于本规划工作区 outputs；本轮已核对原件 SHA-256 与正文缓存记录相同：

- 全周期工程监工规划 v1.1：`9cbc30b5beb7f12c046556bd9461b59d5d4e45c2315dc2da4f07c8bd132ae1a1`。
- 长期能力增补规划 v6.7：`a47bfb5e19092ee11963c0554897fbb29cbbba775183bddecb284c24f3788027`。
- Assistant 分支构想 v0.1：`5513e8241a96f4d661d9520cbcb3c2ea9914ca8d430b2db4dacc13ba3dd744a1`。

[相关正文摘录](planning-extract.json)来自 Engine `docs/project_memory/p12_evidence/planning-source.json` 的已核实缓存，不是新造的规划原文。v1.1 blocks 213—219 为 P17 卡；v6.7 blocks 444—451、459—472、483—497 及边界确认附录为本阶段相关内容。若发现缓存、原件或实际实现矛盾，核对原件并说明，不默默改规划。

## 4. ORIGINAL REQUIREMENTS 与交付目标

P17 实现 Execution Engine、Capability Resolver、World Classification、Alternative Route、Reality Boundary Port、Recoverability Check、Research Routing、Blast Radius 接口、Outbox、幂等、补偿、查询及 Action Result Absorption。

不是只有独立类、假返回值或测试入口：至少通过正常 C1/Thinking/Action 的 Direct 路径及需要 Planner 的复杂路径，实际调用本地 Fake Adapter，产生隔离测试效果、可核验回执，再经既有主体链吸收结果。允许结果在后续正常轮次消费，不重写已完成的原 Thinking 事实。

以下是据原规划形成的工程要求，不冒充原件逐项编号：

1. **执行与可靠投递**：持久化执行状态、Outbox 投递、查询、取消/停止与恢复；保留原请求、主体、环境、目标、参数、版本及幂等键绑定。Outbox 是原 E5-A 请求的投递/执行索引，不是第二本权威请求或结果账本。
2. **能力解析**：复用原 P08/P16 的 capabilityRef、注册/版本/凭据引用和结果核验；宿主中立，不写死 Vio。简单且明确选定的原子动作允许 Direct；复杂多步骤才使用原 Optional Planner；model.generate 保持原 Thinking 路径。
3. **当前边界**：在新副作用发生前重新验证当前 Context、权限、确认、资源、主体生命周期、能力版本、世界、资产/目标及恢复条件；查询到旧成功事实可核实恢复，但不等于允许再次执行或重新消费。
4. **世界与恢复**：有实际隔离的 Research/Test World，使用独立的数据、Adapter/通道、凭据引用、审计及 readiness；不能只加一个 world 标签。正式恢复依赖 P20/P21，未就绪返回 RECOVERABILITY_NOT_READY。P01 仅作为测试/实验恢复设计参考，不得用其回滚正式 Subject 或 Owner Domain。
5. **替代路线与影响范围**：显式记录等待、换路线、补充信息、放弃或以后重试；新路线不得复用与其不匹配的旧确认或扩大目标、权限、world、费用。资源/次数/并发/消息/存储等影响范围在 TEST 中有可验证上限。UNKNOWN 先查询，不能通过另一条路线重复同一可能已发生的效果。
6. **幂等与补偿**：在支持幂等键及独立查询的 Fake 假设下实测一次效果、一次结算；重复投递、双 worker 竞争、回执丢失和重启不得重复执行。不能对任意生产 Adapter 宣称 exactly-once。补偿是独立可审计动作，有自己的权限、绑定和幂等性；补偿失败或未知必须保留，不能擦除原事实或冒称现实已回滚。
7. **结果吸收**：原请求—执行—回执—结果—吸收身份交叉核验；只接受对应的实际证据，不因 status=success 就直接提升材料为主体判断。通过原 Thinking/Action、Event/Memory/Learning/Evolution 职责分工完成吸收与必要 revision，重复恢复不得重复记事件、扣资源或推进 revision。
8. **研究来源**：Research 结果默认不进入 Main Event、Memory 或 revision。若演示经明确授权吸收，必须核验来源、权限、真实性并走原演化流程；不能将模拟成功写成真实世界事实。研究环境不可用返回 RESEARCH_UNAVAILABLE，不退回 Real 执行。不得仅因思想或情绪内容将 Subject 转入 Research。

## 5. Reality Boundary 与心理边界

唯一链路保持：

Subject → Thought → Desire → Will → Decision → Structured Action → Capability Resolution → Permission / Resource / Recoverability Check → Reality Boundary → World Adapter → Reality Effect。

Reality Boundary 只在结构化行动已形成后、现实效果发生前控制权限、所有权、费用、影响范围和恢复条件，不成为 Thought、Emotion、Desire、Will、Personality、内部冲突或普通语言表达的审核器。不得自行增加“友好人格”或心理纠正规则。

保留独立结果语义：SUBJECT_REFUSAL、PLATFORM_DENIAL、REALITY_DENIAL、CAPABILITY_UNAVAILABLE、RESOURCE_EXHAUSTED、RESEARCH_UNAVAILABLE、GENERATION_FAILED、NETWORK_FAILED，以及 RECOVERABILITY_NOT_READY、等待、UNKNOWN、取消等适用状态。不要把平台拦截写成主体不想做，不把生成失败写成主动沉默，也不能把没执行写成已执行成功。

## 6. 依赖、可修改范围与 NOT_READY

优先复用实际代码中的 ActionPlanningService、CapabilityCoordinationService、原 E5-A、ContinuityCore/Interaction、P11 Scheduler、Permission/Resource、P15 生命周期及 P16 Broker/Provider/缓存边界。三类 P16 秘密隔离修复必须保持：回执全材料校验、首次持久化前查询/模型结果检查、外部端口异常静态诊断。

允许增加本阶段所需内部 Domain/Service/Port/Storage、可恢复执行/Outbox 元数据、隔离 Fixture、正式测试及最小既有内部接线；档案新增前核对编号，只登记实际开工决定和 Stage Brief，不预创建验收决定。文件具体设计由施工方结合当前架构确定，先说明职责，避免平行重建已验收模块。

不修改冻结六份 Schema、外部契约、63 项受保护边界、三份规划原件、正式数据、pyproject/0.1.0、32 项既有排除材料或历史证据。不改 Assistant/Vio，不建第二 SubjectState、第二 Authority 或第二套权威请求/结果账本。若确有无法用内部扩展实现的冻结边界冲突，只暂停相关项并请求确认。

**本阶段不开放真实副作用**：不真实发邮件/消息、操作设备/浏览器账号、花钱、配置云资源或连接生产服务。相关能力可在明确隔离的本地 Fake 中演示；这不是永久取消这些能力，真实首个 Vio/PWA Adapter 属 P22。P20/P21 未验收的生产恢复/安全依赖保持 FEATURE_GATED / NOT_READY / Disabled。

P18 常驻、自启动、后台轮询不在本次范围，不安装服务或创建自动化；用有界人工触发/tick/独立子进程验证执行恢复即可。现有本机 loopback 回归可照常运行，不扩展为外网接入。真实供应商、生产凭据、Owned Asset Registry 生产数据与隐私政策仍待后续明确授权。

## 7. 验证矩阵与效率

为上述要求建立可追踪矩阵，覆盖正常路径、反例、具体文件、命令、断言和真实证据。不要把只有负例拒绝当成完整能力实现。

- 正常 Direct 与 Planner、真实本地 Fake 效果、正常 C1 结果回流/后续吸收。
- 投递前、效果产生后回执保存前、结果入账后吸收前，以及补偿中断的恢复。
- 重复请求、双 worker 竞争、同身份不同参数/世界/目标/版本；UNKNOWN 与明确 NOT_EXECUTED 分离。
- 授权撤销、确认失效、Context 漂移、资源耗尽、主体暂停/归档/删除发生在调用途中或等待恢复时。
- Outbox/执行数据损坏、回执或结果替换、取消与成功竞争、补偿失败/未知、有界重试/替代路线；失败不能隐式扩大执行范围。
- Research/Test 数据、审计、凭据引用和正式根隔离；研究不可用不落入 Real；生产恢复未就绪明确拒绝。
- 合法心理内容和主体拒绝/沉默正向对照；拒绝原因不改写原内部意图。
- 秘密材料和异常原文不能进入请求/回执/结果持久化、Context、日志或 Git；测试使用合成标记，不读取真实密钥。
- 至少一个真实跨进程 Golden，验证重启后继续原请求、不产生第二次效果，并从正常主体链处理结果。
- 原 P16 78 项及既有 1286 项身份和原断言保留；相关 P08/E5-A、P09/P11/P12/P15/P16 与 P01 隔离回归按影响选择。

先定点反例及正常对照，再 P17 专项和受影响兼容。代码稳定后一次完整回归；只有新失败或相关代码再次变化才追加必要运行，不机械三轮全量。开工可核验引用已通过的源码匹配基线，不把历史全量写成新运行。

每次用唯一标签记录命令、UTC 起止、耗时、退出码、方法身份、PASS/SKIP/FAIL/ERROR、stdout/stderr、运行前后源码 hash；保留首次失败及辅助错误，不覆盖历史，不把 1314 SKIP 算作 PASS。并发跑测试前确认 Fixture/资源隔离，避免互相污染或让计时失真。

## 8. 交付与停止条件

交付实际成果和架构职责、逐项矩阵、原始运行与失败证据、独立可复跑命令、精确文件清单/排除清单、保护项/静态解析/链接/敏感信息/差异检查，以及完整 Git 状态。已知历史八处格式告警单列；新增格式问题按实际处理，不改写原始失败日志。

P17 仅登记 IMPLEMENTED_NOT_ACCEPTED，P00—P16 保持 ACCEPTED；冲突按真实证据登记，未解决阻断不得标为 NONE；没有已知阻断也不等于正式验收。未就绪生产边界明确列出。

完成后停止，等待独立复核和用户确认；不自行验收，不提交或 push，不进入 P18。
