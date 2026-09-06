# P12 前引擎整体审查报告

日期：2026-09-05。审查对象：Engine `main`，提交 `5f25d0cef3798aa380d457ae670db30ee1b47407`。

## 结论

发现 **8 类此前测试未覆盖、现已独立复现的问题**，对应 10 个失败场景。建议先修复这些问题、完成有针对性的复核，再开始 P12。此结论不改写既有 P00—P11 历史验收，不代表引擎需要重建或改变项目方向。

现有全量测试仍然通过：839 项，838 PASS、1 SKIP，400.902 秒。独立探针最终运行 15 项：5 个正向对照 PASS、10 个缺陷断言 FAIL，0 ERROR，0.823 秒。两者并不矛盾：原有测试没有覆盖这些输入组合、并发交错和恢复窗口。

这是代码审查和缺陷复现，**没有实施修复**，没有修改 Engine/Assistant 源码、正式数据、冻结契约、版本、验收档案或 Git 状态。审查脚本和报告单独放在规划工作区。

P1 表示应优先修复的安全边界、数据完整性或关键运行问题；P2 表示确定存在、影响范围相对受限的正确性问题。

| 编号 | 优先级 | 问题 | 复现结果 |
| --- | --- | --- | --- |
| R01 | P1 | 并发事件写入丢失 | 两次调用均成功，只保存一个事件 |
| R02 | P1 | 权限“限制”接口反而扩权或复活撤销权限 | 新增能力可用；撤销后的能力重新可用 |
| R03 | P1 | 模型请求恢复绕过零预算拦截 | 预算为零，恢复时仍调用一次 Fake Provider.execute |
| R04 | P1 | UNKNOWN/冲突回执饿死正常调度任务 | 连续五次查询旧任务，健康任务始终 QUEUED |
| R05 | P2 | 重复资源请求重复扣费且无法结算 | 扣两次，随后实际用量登记报错 |
| R06 | P2 | 学习固化消费已被否决的支持证据 | 仍生成 trait 和状态演化提案 |
| R07 | P2 | 部分重叠的记忆证据无法合并 | 合法新增证据触发持久化校验错误 |
| R08 | P2 | P11 TEST 接线缺少任务/唤醒周期主体绑定 | A 任务唤醒 B、扣 B 资源，却记录 A 完成 |

## R01：并发事件写入成功却丢失历史

位置：[JsonSubjectStateRepository.save_transition](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_repository.py:72)、[最终文件替换](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_repository.py:190)。

读当前状态、读取历史、检查 revision、追加历史和写回没有处于同一并发保护范围。临时文件原子替换只能保证单次写入完整，不能保证整个读—改—写过程互斥。

复现：同一主体，两个线程提交不同的合法 FACT Event，均不修改 SubjectState 字段。在现有 `_write_payload` 入口放置 barrier，确定性地暴露两个线程均已读取旧历史的合法交错；没有修改待写数据或替换仓库存储逻辑。两个调用均返回成功，最终历史只有一个 Event。顺序执行的正向对照保存两个 Event。

影响：已确认接收的客观事件静默丢失，后续 Timeline/Memory 无法获取该事件。现有 [FrontendHTTPServer](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/interfaces/http_server.py:27) 本身采用 ThreadingHTTPServer，因此不是仅在未来多进程架构才存在的风险。本次复现使用服务层双线程，未声称已通过 HTTP 端到端复现。

建议：在当前支持的并发范围内，保护完整的读取、校验和写回；发生冲突时明确拒绝或安全重试，不能两个调用均成功却只保留一个。不要只给最后的文件替换加锁。

探针：`test_concurrent_events_are_not_silently_lost`。

## R02：restrict_permission 不保证权限单调收缩

位置：[PermissionService.restrict_permission](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/permission_service.py:151)，尤其赋值与清除撤销标记处第 177 行起。

该操作直接接受新的 scope/capabilities，不检查是否为旧授权的子集；同时无条件设置 LIMITED 并清空 revoked_at。

两条独立复现：

1. 原授权只有 `memory:request`，调用 restrict 增加 `action:execute` 并扩大 scope，随后新增能力检查通过。
2. 先 revoke，使原能力不可用；再 restrict，同一能力重新可用。

真实缩小能力集合的正向对照正常通过。问题在于“限制”路径可以完成本应属于重新授权的操作。它是内部权限服务的语义漏洞；本次未证明外部未授权用户能调用该接口，不应描述为已经验证的远程越权攻击。

建议：限制操作只允许有效范围内的真子集/允许的收缩变化；拒绝借此恢复撤销权限。需要重新授予权限时，必须走明确授权流程并留痕，不新增第二套 Authority。

探针：`test_restriction_does_not_expand_capabilities`、`test_restriction_does_not_reactivate_revoked_permission`。

## R03：模型恢复路径在零预算下仍执行 Provider

位置：[ModelCapabilityService 恢复分支](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/model_capability_service.py:165)、[首次请求的零预算处理](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/model_capability_service.py:273)、[事后超额处理](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/model_capability_service.py:391)。

首次请求的正常路径会在 maximum_tokens 为零时生成 RESOURCE_EXHAUSTED 而不调用 Provider。但 attempt 的持久化发生在这项判断之前。若在 `after_provider_dispatch_reserved` 中断，恢复时查询得到 NOT_EXECUTED，直接进入 execute，未重复执行零预算拦截。

复现：每日额度 20，第一次请求实际使用 20；第二次请求保存 maximum_tokens=0 的 attempt 后注入故障；重建应用并恢复第二次请求。结果 `execute_calls=1`、`maximum_tokens=[0]`，Fake Provider 的事实记录从 1 增至 2。

影响：额度耗尽仍启动了 Provider 执行。事后将结果标记 RESOURCE_EXHAUSTED，不能撤销调用本身。复现仅调用本地 Fake，没有真实模型消费；不宣称已经产生生产账单。

建议：将执行前预算门禁用于首次执行和“明确未执行后的重新执行”两条路径。恢复已经发生的事实仍应允许，不能用当前预算否认历史事实，也不能无条件重试 UNKNOWN。沿用原 E5-A/P02 通道，不建立新账本。

探针：`test_model_zero_budget_still_blocks_execute_after_crash`。复用现有 P02 fixture 和已有故障注入点，spy 仅记录 execute 调用。

## R04：UNKNOWN 查询优先级可以永久压住健康任务

位置：[SchedulerService.tick](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/scheduler_service.py:161)、[冲突回执查询分支](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/scheduler_service.py:353)。

tick 优先选择到期 UNKNOWN 并立即返回，之后才处理普通候选任务。持续 UNKNOWN 按固定间隔到期时，宿主若以同样或更慢的间隔 tick，每次都会先查询它。绑定冲突分支甚至没有更新查询退避时间。

两条复现：

1. 原任务回执持续绑定冲突；随后每 60 秒 tick，一共五次均返回 RECEIPT_BINDING_CONFLICT，正常任务仍 QUEUED。
2. 原任务持续返回合法 UNKNOWN；随后每 30 秒 tick 五次，正常任务同样始终 QUEUED。

两例均只有首次 dispatch，之后 query=5。相同时间立即再 tick 的正向对照能执行健康任务，说明“再 tick 一次”的既有测试不能覆盖正常轮询间隔下的问题。五次实测结合分支和时间更新逻辑，支持该模式可持续重复，并非声称实际运行到了无穷次。

建议：给待核实任务查询与健康任务派发建立有界、公平的调度关系，冲突回执也应退避；不能以盲目重执行 UNKNOWN 来解决。正常任务能否前进，不应依赖宿主刻意连续调用多次 tick。

探针：`test_scheduler_receipt_conflict_does_not_starve_other_task`、`test_scheduler_unknown_does_not_starve_at_normal_poll_interval`。

## R05：同一资源请求重放会重复扣费，随后无法登记实际用量

位置：[ResourceManager.request_resources](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/resource_manager.py:110)、[record_actual_usage](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/resource_manager.py:293)。

资源申请每次创建新 usage UUID，没有对稳定请求/session 身份去重；实际用量登记却要求该 session 恰好有一条 usage。

复现：同一个 request_id、同一个 session_id，重复申请 10 tokens。结果 token_used=20、usage_records=2；随后登记实际用量 8，抛出 `ResourceNotFoundError: exactly one usage record is required for session: same-session`。只申请一次的对照正常结算至 8。

影响：重复提交或恢复重放可造成重复预占，且后续结算无法收口。建议同一请求精确重放原分配结果，或在扣费前明确拒绝重复；相同身份、不同内容也应冲突拒绝。沿用既有资源记录，不建设另一套账本。

探针：`test_repeated_resource_request_remains_reconcilable`。

## R06：学习支持证据已被否决，仍可固化为长期特征

位置：[LearningService.validate_learning](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:202)、[solidify_learning](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:298)。

validate 时会检查支持记录并聚合根证据；solidify 时只检查目标记录的 VALIDATED 状态、已存证据数量和置信度，没有重读支持记录当前是否仍有效。

复现：三个独立候选学习，每条置信度 0.6；用两个候选支持目标完成验证；随后 reject 其中一个支持候选；再显式 confirmed=True 固化目标。结果支持记录状态 REJECTED，但仍保存一个 trait、声称有三个支持证据，并返回一个状态演化 Event。

影响：验证与固化之间发生证据撤回时，长期特征仍依赖已失效的证据。这里没有绕过用户确认，也没有应用返回 Event 去修改正式 SubjectState；准确范围是错误依据被固化并产生提案。

建议：在固化时重验支持记录及当前可计数的独立根证据，或可靠地使受影响验证失效。不要通过删除历史验证和撤回记录来消除冲突。

探针：`test_learning_rechecks_rejected_support_before_solidifying`。

## R07：记忆合并把“部分重复”误当作“完全重复”

位置：[MemoryConsolidationService.consolidate](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/memory_consolidation_service.py:99)、[结果追溯校验](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_memory_repository.py:779)。

已有同内容记忆根证据为 `[event:one]`，新候选为 `[event:one,event:two]`。服务发现交集后进入重复/别名处理，没有先将新根证据纳入结果。

复现结果：`MemoryPersistenceError: consolidation operation input is not traceable to its result memory`。原记忆仍只有 event:one，未损坏，但合法的 event:two 无法进入合并结果。完全不重叠的新证据对照能正常合并。

建议：区分已知根与新增根，仅完全重复的候选走无新增别名路径，部分重复则合并新增部分。必须保留仓库追溯校验；不能通过放宽该校验掩盖服务层错误。

探针：`test_memory_partial_overlap_preserves_new_evidence`。

## R08：P11 的 TEST 接线缺少跨主体 cycle 绑定检查

位置：[P11SchedulerFixture.on_delivered](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/testing/p11_scheduler_fixture.py:324)、[ResourceAwareWakeScheduler.wake_manual](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/resource_aware_wake_scheduler.py:80)。

P11 任务和 receipt 按 A 主体绑定，但回调直接将 request.cycle_id 交给唤醒服务；后者根据 cycle 所属主体执行唤醒和扣资源。没有在副作用前核实二者属于同一主体。

复现：在同一独立 Temp fixture 中建立 A、B 两个主体及资源；给 A 的新任务填入 B 的合法 cycle_id。tick A 返回 COMPLETED，但 A 的唤醒数为 0，B 的唤醒数为 1，B 扣除 64 tokens。

范围：确定存在于已实现的 P11 TEST adapter/唤醒组合链。生产 Adapter 未接入，本次未证明生产跨用户攻击。该缺口仍使当前 P11 的主体隔离验证不完整，不能把这种错误接线继承到后续阶段。

建议：在产生唤醒、资源扣减前校验 task/request/cycle/session 的主体与环境绑定，不匹配时拒绝且零副作用；保留一次计算机会的 P11 边界，不提前实现 P17。

探针：`test_scheduler_foreign_cycle_does_not_wake_another_subject`。

## 覆盖范围与限制

本轮进行了源码风险审查、现有全量测试和跨模块独立反例，不只是复述阶段验收报告。检查涵盖：

- 基础层：SubjectState/Event/Evolution、权限、资源、Thinking、Awakening、Learning、JSON 持久化与现有线程式 HTTP 入口。
- P01：Sandbox 路径保护、快照/回滚及完整性检查；未注入真实进程断电。
- P02/E5-A：Provider 请求、预算、事实恢复、幂等与持久化阶段。
- P03—P04：事件历史、Timeline、根证据、记忆合并、派生摘要追溯。
- P05—P07：Router/Composer 的来源与当前授权检查、Context 绑定、矛盾检测/解决边界；未新增确认问题。
- P08—P09：Action/Planner、回执核验、当前 Context 门禁、C1 恢复交叉绑定；原有修复通过全量回归。资源/学习等基础服务的上述缺口仍可能影响上层组合。
- P10：当前 Engine 来源及受保护文件；未修改或重新同步 Assistant，也没有新跑远端 CI。
- P11：admission、持久化队列、排序/aging、恢复、UNKNOWN、回执和 Wake/Resource TEST 接线。

没有连接生产 Adapter、真实 Provider、Vio 或外部数据库，没有进行网络测试，也没有证明所有模块不存在其他 bug。并发复现限定本机双线程；多进程/多机一致性不在本次验证结论内。静态阅读是按风险深入的代码审查，不是逐行形式化验证。

## 测试证据与复现

原有测试：在 Engine 根目录设置 PYTHONPATH=src、PYTHONDONTWRITEBYTECODE=1，执行 `python -m unittest discover -s tests`。结果 839 项、838 PASS、1 SKIP、400.902 秒。SKIP 对应既有 Windows symlink 创建权限限制；未把它写成 PASS。

独立探针运行方式（PowerShell；所有业务数据使用测试临时目录）：

```powershell
$env:PYTHONPATH = 'C:\Users\Administrator\Documents\continuity-engine\src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python 'C:\Users\Administrator\Documents\Codex\2026-08-24\https-github-com-yuan69082-code-continuity\reviews\engine-pre-p12-20260905\review_probes.py'
```

预期当前提交退出码为 1：15 项中 10 个缺陷断言失败、5 个正向对照通过。脚本是审查反例，不应把失败当成可以删除断言的理由；修复后应转成正式回归，并保留合理的拒绝/重放两类实现选择。

- [独立探针源码](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-20260905/review_probes.py)
- [最终独立探针完整输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-20260905/probe-final.log)
- [原有全量测试最终输出片段](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-20260905/baseline-final-chunk.log)：仅最后一次捕获的输出块，不是完整流式日志。
- [只读复核结果](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-20260905/final-readonly-audit.json)

审查探针最初有一处辅助构造错误：Event 的 impact_scope 留空，触发合法输入校验；补上合法 scope 后才进行并发复现。该错误不计为引擎 bug。后续 run-02、run-03、run-04 及最终输出保留在本目录；早期记忆反例的 ERROR 是上述引擎持久化异常，最终探针将同一异常明确记录为缺陷断言 FAIL。

## 文件与 Git 安全核对

结束时 Engine HEAD 仍为 `5f25d0cef3798aa380d457ae670db30ee1b47407`；与本地 origin/main 的 ahead/behind 为 0/0，未联网 fetch，不把本地跟踪引用核对说成实时远端核对。

相对 P11 验收保存的哈希清单：191 个 source/test 文件全部匹配；63 个 protected 文件全部匹配，无缺失。protected 清单包含冻结边界、正式数据和原有 31 个辅助脚本。tracked/index 均干净，未跟踪仍仅原有 31 个 P10 脚本，`git diff --check` 通过。

没有暂存、提交、push、merge、rebase、分支操作或清理旧文件；没有改变当前阶段状态或创建验收决策。测试写入仅限其隔离 fixture，审查材料新增于本规划工作区。

## 建议的下一步

先将 8 项独立反例交回引擎侧修复，保留当前失败证据和历史验收。按数据/授权与恢复门禁优先，其次调度公平性、资源幂等和证据有效性收口；每项先定点验证，最终代码稳定后跑一次完整回归。只有新失败或后续相关代码改动才补必要重跑，不机械重复三轮全量。

这些问题目前没有证据要求改变六份外部 Schema、另建账本、改 Authority 归属、接生产 Adapter 或提前实现 P17。修复若确实超出既定内部边界，应单独列出必要性并请求决定，不能借修 bug 扩大工程范围。复核完成前，建议暂缓 P12。
