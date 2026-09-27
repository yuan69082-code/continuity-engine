# W04-2 公共验证阻断：STOP CURRENT ITEM

W04-2 实现维持 IMPLEMENTED_NOT_ACCEPTED。公共兼容收口、最终全量为 BLOCKED；本轮不修改已验收 W02/P18 的预算、锁策略或原测试来绕过失败。

## 当前项与原要求

当前项是 W04-2 公共兼容与最终同版回归门。原要求保持 W02 已验收的 1000 毫秒、原 P18 控制/恢复语义、旧断言及观察期限，完成专项、兼容及最终全量。用户同时要求实际环境/依赖冲突停受影响项，不越权处理其他模块。

## 实测事实

- 本批专项71/71 PASS，包含42项新增与29项W04-1。
- 兼容414项：407 PASS、1 FAIL、6 ERROR、0 SKIP，exit 1，3368.009秒；前后固定源码相同。原始证据：[结果](w04-2-compat-final-01.json)、[stderr](w04-2-compat-final-01.stderr.log)、[故障提取及原子进程记录](compat-failure-01.json)。
- 五项W02用例为RECALL_TIMEOUT：原四份资料、原第三轮16项检索、派生材料撤回贯通、消息/回执/回应前Context贯通、A/B外部候选联验。
- P18 `test_long_busy_host_remains_live_and_diagnostic_is_not_flooded` 期望一条BUSY诊断，实际出现两组BUSY/AVAILABLE；`test_start_waits_for_checkpoint_without_relaxing_owner_lock` 在控制器发送STOP时遇到RuntimeCheckpointBusy。两项原记录显示子进程均最终退出0、未强制清理；不据此声称发生无STOP宿主退出。
- 失败时只读进程快照仅有本轮runner和unittest进程，未发现重叠Python测试/遗留宿主：[进程快照](compat-process-observation-01.json)。没有证据证明机器性能、杀毒软件或测试污染是原因。

## 有界原基线/当前版本对照

预先限定一次原HEAD、一次当前版，各执行原P18两项和原W02两项，不改断言、1000毫秒或控制等待时限。原HEAD用只读git archive的src/tests，在等长隔离路径解包；当前对照仅叠加本批七份实现/测试文件。归档身份与各文件hash、命令在[对照记录](recall-paired-diagnostic-01.json)。并非重新跑整套到绿。

| 版本 | 结果 | runner秒 | 回忆超时的elapsed_ms / 检索量 |
|---|---|---|---|
| fc185843 原HEAD | 0 PASS、1 FAIL、3 ERROR | 69.321 | 1194.462 / 14；1299.456 / 11 |
| 当前版 | 0 PASS、1 FAIL、3 ERROR | 47.433 | 1131.481 / 14；1336.462 / 11 |

这些对照在到达原场景最后一轮之前就超时，不能把14/11写成最终16项场景通过或完成四份资料。回忆准备中的模型/外部调用为0。测量只在整个prepare外包装，并在原elapsed_ms计算后提取记录；有观察开销，不把它与未插桩正式结果混淆。

当前与基线各有18次ActionSpecification校验处于回忆中；两版均未在回忆中调用ExecutionService.current、results_for_context或ExecutionContextSource.resolve。现有证据可排除“只有W04-2改动后才能出现这些异常”，不能证明本批开销绝对为零，也不能唯一定位原失败机制。[原版诊断](recall-baseline-diagnostic-01.trace.json) · [当前诊断](recall-current-diagnostic-01.trace.json)。

## 不能直接完成的原因及公共影响

本批三个公共文件改动只覆盖设备参数/最终设备门禁/设备历史来源；上述失败涉及原回答前回忆、控制事务锁与其既有测试。仍需定位读写/校验耗时与控制交错，才能提出有证据的最小修改。直接改1000毫秒、等待预算、断言或吞掉异常会改变既有已验收边界；目前没有依据这样做。

PLANNING_CONFLICT=PRESENT，仅指本批验证门与现场已有依赖失败的实施冲突、处理范围待用户决定，并非断言三份规划正文矛盾。EVIDENCE_CONFLICT=PRESENT；不撤销历史验收，也不自行接受风险。

## 保持原方案所需工作、选项及推荐

推荐另行确认对本轮原样复现的W02/P18异常作定向根因调查，保持原时限/断言，先测量后提出最小文件范围。候选只读入口是AssociativeRecallService、JsonIntegrationResultLedger、PersistentRuntimeService和JsonRuntimeRepository；不是对这些文件的自动修改授权。定位后再核对是否属于本批回归或原有/环境问题。

若认为只需在指定已验证环境复核，应固定该环境和有限次数，保留本轮失败；通过不能倒写本轮记录。不建议通过放宽预算、忽略旧测试或修改项目持续运行目标解决门禁。扩大共享模块修补前需用户决定；本轮暂停受影响项，不启动W04-3。

最终完整回归尚未启动：先修复/解释前置失败再验证，避免用全量碰运气掩盖失败。没有完整回归PASS证据。历史F1/H1/F2仍UNKNOWN，本次错误不擅自与旧案合并。
