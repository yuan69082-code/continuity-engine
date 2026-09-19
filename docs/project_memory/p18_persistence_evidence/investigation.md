# P18 持久化与恢复链：事实、实验与结论边界

当前状态 IMPLEMENTED_NOT_ACCEPTED；EVIDENCE_CONFLICT=PRESENT。调查为本次用户授权的 P18 内返修，不是验收。源码、旧证据及排除项的开工身份见 [before.json](before.json)。原件与归档副本逐文件 SHA256 在同一清单中；旧日志不覆盖。

## 三次历史现场分开记录

| 标识 | 已证实事实 | 缺失材料与结论 |
|---|---|---|
| F2 | 全量1466：1464 PASS、1既有SKIP、1 FAIL；资源等待控制竞争用例15秒内未达到revision=2。清理前Thinking COMPLETED/RETURNED、Context有效、Capability成功且有回执、效果/credits各1、state_update_id为空；异常到SubjectState的os.replace。宿主活着，STOP退出0。 | 原异常类型/errno/winerror缺失。当前可稳定复现同阶段失败，不能补写历史OS码或声称排他根因已证实。 |
| F1 | 全量1444：1442 PASS、1既有SKIP、1 FAIL；第二轮WAITING_VERIFICATION，token_used=640，宿主存活。 | 缺失败时ThinkSession/调用阶段/完整原因链，旧临时根已清理。仍UNKNOWN；不能仅凭UNKNOWN或费用推断同源。 |
| H1 | 专项58：57 PASS、1 FAIL；等待资源超时，token_used=0、无未确认任务，宿主接受STOP退出0。 | 缺可信时间/水位和关键清理前状态。仍UNKNOWN；不由后来PASS推断原因，也不能归因于R1宿主退出问题。 |

原入口：[F2现场](../p18_r2_evidence/full-resume-01-failure.json)、[F2全量](../p18_r2_evidence/full-resume-01.json)、[F1调查](../p18_repair_evidence/full-timeout-investigation.json)、[H1原记录](../p18_evidence/p18-final-04.json)。旧中断full-final-01仍无最终数量/退出码/原因，不能计PASS或据软件退出计Engine FAIL。

## 有界实验与假设判别

1. 原F2用例在未改实现时只跑一次：`original-f2-before-01` 1 PASS，8.351秒。证明该失败不是每次必现，不能据此关闭历史问题。
2. 真实读取句柄：子进程使用原仓储读取，握手确保文件已经打开、尚未读取完。写方记录实际 PermissionError、errno13、winerror5；旧文件hash未变、读方最后得到旧完整快照，排除本次实验中的半写。`reader-before-01` 1 PASS/1 FAIL；Native有效重建 `native-before-02` 3 PASS/2 FAIL。不是随机并发或增大超时。
3. 试验共享DELETE读方式：`win-share-01.log`、`win-share-02.log` 保留实际Windows API结果。即使DELETE access可打开，当前环境MoveFileEx/replace仍可返回5，因此只换读句柄未闭合，`reader-after-01`仍2 FAIL。这个尝试已撤出当前代码，失败保留。不能无条件将所有Win5分类为可重试。
4. 当前修复只在P18明确作用域中，对实际目标DELETE-access探针得到32/33的共享冲突，最多等待0.25秒，单次25ms让出。没有确认共享竞争、长期不释放、文件不存在/磁盘错误均保留真实异常。若竞争在探针前已消失，保守不重试，不宣称穷尽所有文件系统失败。
5. 改进后的握手在确认共享冲突后释放读方，要求有界恢复。用本轮`source-before/json_repository.py`精确旧writer重建同一测试，两项仍FAIL（`old-writer-confirm-01`）；当前正式测试通过。旧快照只在隔离进程内替换类方法，未改工作区源码；runner中的当前source hash不能冒称该重建只运行了当前实现。
6. 竞争窗口中的STOP反例修前真实FAIL（`stop-retry-before-01`）。重试前重查Context及原Runtime guard后，STOP、PAUSE、撤权均不产生新状态；解除PAUSE/重新合法授权后可用原事实推进。目标字节版本变化则拒绝，不覆盖较新合法Event；原RLock、revision/event校验保留。不是跨进程数据库或分布式CAS保证。
7. 已执行事实与状态保存：在效果后注入不可重试OS错误，Thinking已完成、状态仍1、效果/费用各1。未推进Frozen Clock时查询尚未到期；推进原5秒水位后，现有Native查询能恢复原状态提交。重新打开同根仍复用同一ThinkSession，Provider不再次调用；usage身份和预留不增，原Thinking预留从未结算到实际256合法收口，总token仍320。无需改RuntimeCognition分类或新增恢复账本。
8. 状态已经提交、返回丢失：原after_native_evolution故障点证实恢复不再次推进revision、不重复效果/扣费。真正Provider已进入但未知的原R2保守行为由原正式专项继续验证。
9. 保存阶段注入：create/write/flush/fsync/replace及cleanup逐步记录实际测试OS码。原write/flush/fsync失败发生在临时路径登记前会残留；清理失败会盖住主异常。`save-stages-before-01`三个方法中1 PASS/2 FAIL（含4个失败子记录），修后早登记路径并保留主异常及cleanup原因链。正常错误无半写/无残留；若OS连清理也拒绝，单个自建临时文件可能保留，测试解除注入后由隔离根清理，不承诺生产擦除/备份清除。

## 最小修改与诊断责任

- [JsonSubjectStateRepository](../../../src/continuity_engine/storage/json_repository.py)：完整读/校验/写事务RLock不变；私有有界replace流程由P18明确开启，其他调用默认不重试。目标bytes变更拒绝；不会重写Event或当作成功。临时文件路径立即登记，清理异常不覆盖主错误。
- [原Native接线](../../../src/continuity_engine/services/wake_perception_thinking_action_service.py)：仅已有runtime_guard调用上下文开启重试；每次重试重新执行原Context与控制门禁，原ActionEvolution持有写权。
- [TEST诊断](../../../src/continuity_engine/testing/p18_persistence_diagnostics.py)及[P18 Fixture](../../../src/continuity_engine/testing/p18_runtime_fixture.py)：实例级包装，只观察独立TEST根；保存OS异常类型/errno/winerror、最多4层原因链、受控相对栈、具体操作、文件前后hash/修订、预期修订、身份hash、PID/线程和锁持有/释放状态。原过程故障报告继续保存任务、会话、回执、时间、水位与资源。异常原文、repr、私密正文不进入新增诊断；不移除对外脱敏。诊断自身失败仅一次独立stderr静态兜底，不覆盖主异常或递归记录。
- [14项正式回归](../../../tests/test_p18_persistence.py)：新增身份另计；原1466文件断言不变，原15/25秒观察阈值不变。

## 已排除与未证实

受控实验排除了“只缺外部回执”“必须重发动作才可恢复”“必须增加第二账本”等假设：回执已有，原事实恢复可用。当前拒绝路径没有覆盖较新版本、额外Provider调用或费用；OS故障仍真实报告，长期竞争有界。

详细系统码及状态保存诊断见 [按原日志行号索引](diagnostic-index-v2.json)。同一次Native定点可能包含真实读竞争和主动故障注入，必须按测试/记录区分；初版索引按整组归类过宽，原索引保留，由v2仅纠正分类，不改任何原始结果。

本轮不是全库句柄/缓存审计：没有证据证明全量污染、残留monkeypatch、不同Fixture串用或磁盘权限是历史唯一原因；新实验的patch均由上下文恢复，读进程有握手、退出码及回收记录。正常可信时钟会前进，Frozen Clock实验必须推进水位；这仅证明可控实验的等待条件，不证明F1/H1的时钟根因。

F2当前同阶段风险已定位并最小修复，历史那次究竟哪一个句柄或哪一个系统错误无法追溯。F1/H1保留UNKNOWN。当前防护覆盖部分共同候选风险，不能写成三项同源或自动关闭EVIDENCE_CONFLICT。默认持续运行、局部资源等待、STOP/生命周期约束不变；生产恢复及真实Adapter仍NOT_READY。

本次共享句柄及竞争窗口用例针对当前Windows环境；没有执行其他操作系统验证，不宣称新增测试已在其他平台通过。非Windows运行路径沿用原os.replace，不引入生产部署或跨平台恢复保证。
