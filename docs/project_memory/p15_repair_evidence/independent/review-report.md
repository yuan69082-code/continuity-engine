# P15 独立复核：三项阻断，等待用户确认返修

复核日期：2026-09-08。仅检查 Engine 工作区、运行隔离 Fixture，并在规划工作区保存证据。未修改 Engine 源码/测试/档案，未调用其他任务、未提交/push、未自行验收、未进入 P16。

## 结论

P15 的正常交付和既有通过记录属实，但目前不能验收。独立反例确认三类遗漏：生命周期存档与历史未互相核验；未提交的 Learning 固化记录在状态变化后阻塞新的合法确认；成长观察出口没有在返回前重查权限。

规划侧复核结论为 REQUEST_REPAIR / EVIDENCE_CONFLICT=PRESENT。这是本报告的结论，尚未写入 Engine 档案；Engine 保持 IMPLEMENTED_NOT_ACCEPTED，待用户确认后由用户转发返修提示词。没有替用户决定正式删除保留窗口、归档策略或关系可见性政策。

## 实际验证

| 验证 | 实际结果 | 耗时 |
| --- | --- | --- |
| 独立重跑原 P15 专项 | 39 PASS，0 SKIP/FAIL/ERROR | unittest 115.665 秒；runner 116.263 秒 |
| 独立边界反例与正向对照（第二轮有效探针） | 8 项：4 PASS、4 FAIL、0 ERROR；四个失败归为三类根因 | unittest 10.580 秒；runner 11.556 秒 |
| 当前源码/证据/保护/Git 身份核对 | 15 项全部符合 | 不冒充行为测试或正式验收 |

原施工方全量 1176 项（1175 PASS、1 既有 1314 SKIP）、兼容 311 PASS 与专项 39 PASS，均核对当前 230 个源码/测试/资源文件身份和各自原始输出；它们是引用的施工证据，不是本次又跑了一遍全量。原 1137 测试身份及全部原测试文件保留，新加 39 个身份。独立专项本身包含两子进程 Golden 用例。

两轮探针及独立专项执行前后，Engine 中纳入快照的 1690 个文件均无变化。全部注入中断、错误存档和撤权操作仅作用于 disposable TEST Fixture；没有真实 Provider、生产数据或外部写操作。

## P15-R1：[P1] 缺字段/旧状态片段可绕过暂停和逻辑删除

代码入口：

- `C:\Users\Administrator\Documents\continuity-engine\src\continuity_engine\domain\subject_lifecycle.py:33`，无字段即返回 ACTIVE。
- `C:\Users\Administrator\Documents\continuity-engine\src\continuity_engine\storage\json_repository.py:167`，`_validate_history` 检查身份/revision 链，但不把当前 lifecycle 与生命周期 Event/changes 的最终值核对。

复现：

1. 正常 CREATE → ACTIVATE → SUSPEND，保留全部 Event/changes/revision，仅从当前 state 删除 `temporal.subject_lifecycle`。重新加载及 `require_active(..., 'TEST')` 均放行。
2. 正常 ACTIVE → ARCHIVE → DELETE，保留全部历史和最终 revision，仅用之前 ACTIVE 的 lifecycle 片段替换当前片段。`require_active` 再次放行。

这是有生命周期历史的新存档，不是真正不含该能力的旧存档。任一序列化遗漏、旧组件写回或数据损坏都不应把它当成旧数据默认激活。暂停/删除历史与当前状态已经矛盾，加载端没有识别，导致统一运行入口得到错误的 ACTIVE 状态。

独立用例：

- `LifecyclePersistenceReview.test_suspended_history_cannot_downgrade_to_legacy_by_missing_field`：FAIL。
- `LifecyclePersistenceReview.test_deleted_history_cannot_be_reopened_by_stale_active_projection`：FAIL。
- 真正旧状态兼容、未经篡改的暂停状态重启拒绝：均 PASS。

返修目标：区分真正旧格式与已经引入生命周期语义的新记录，加载/保存时核对 lifecycle 与既有权威历史的绑定，缺失、旧值、终态回退、主体/环境/所有者冲突应失败关闭。保留旧格式兼容、原 Event 和正常重放；不创建第二权威或擅自恢复/改写损坏存档。这里只要求校验现有 P15 的自身一致性，不提前建设生产备份恢复。

## P15-R2：[P1] 中断后的未提交固化被当成已完成，阻塞后续合法学习

代码入口：

- `C:\Users\Administrator\Documents\continuity-engine\src\continuity_engine\services\subject_growth_service.py:161`：先持久化 Learning/active Trait，再提交 Evolution。
- 同文件第 142—149 行：原命令恢复要求旧字段值和旧 revision；拒绝旧命令本身是正确的。
- `C:\Users\Administrator\Documents\continuity-engine\src\continuity_engine\services\learning_service.py:339` / 第 678 行：仅据 CONSOLIDATED 记录和 active Trait 判已固化，没有区分对应 Evolution 是否真正发生。

复现：三份独立经历验证通过，在现有 `after_learning_record` 故障点中断（尚无实际人格变化）；重启后加入一项无关的合法 Trait 变化。原命令因旧版本/旧值正确拒绝，但携带当前 revision 和全新有效确认的新命令也被拒绝：`learning is already consolidated`。

实际观察：SubjectState 只有原 `continuity` 和无关的新 Trait，未包含 `consider evidence`；Learning 库却将 `consider evidence` 记为 active。旧命令不可继续，新命令又被“已固化”拦住；现有修正/拒绝入口也以 active consolidation 约束，不能把它当作普通未提交候选处理。

独立用例 `GrowthRecoveryReview.test_pending_growth_can_be_reauthorized_after_unrelated_revision`：FAIL；原“重启后版本不变即可恢复”和“已提交事实不重复 revision”专项仍 PASS。

返修目标：以实际 Evolution 事实区分待提交/已提交，不把未发生的状态变化提前当成已完成。为待提交操作提供可审计的重确认、重建当前提案或终止待提交状态的闭合路径，保留原命令身份与失败历史。旧命令不能偷偷换 revision 或覆盖后来状态；新的有效确认不能永久被孤立的旧 active Trait 锁住。同步检查 SOLIDIFY/ROLLBACK 两条中断路径；不另造请求账本、不放宽当前来源/确认/权限校验。

## P15-R3：[P2] 成长详情读取没有返回前撤权校验

代码入口：`C:\Users\Administrator\Documents\continuity-engine\src\continuity_engine\services\mind_projection_service.py:49`，`read_growth` 仅在第 61 行调用 `_authorize`，读取 state 后直接返回。

复现：Owner 在读取开始时合法，读取当前状态期间撤销真实 Fixture PermissionService 的查看授权。新 `read_growth` 仍返回关系和叙事详情，没有抛出 MindAccessError；相同条件下原 `read` 在返回前再次校验，正确拒绝。

独立用例：

- `GrowthVisibilityReview.test_growth_projection_rechecks_revocation_before_returning_details`：FAIL。
- `GrowthVisibilityReview.test_existing_mind_projection_rechecks_same_revocation`：PASS。
- 同一批真实关系数据、未撤权正常读取及零状态写入对照：PASS。

返修目标：新出口与旧出口保持一致的交付前当前权限、状态身份和版本一致性检查，包含读取途中撤权/到期、状态改变及 export 边界。所有策略仍只控制可观察内容，不改主体内部状态。这是在复核已经实现的观察权限语义，不替用户启用或决定正式隐私政策。

## 证据入口与复现命令

- [独立专项输出](p15-original-01.stderr.log)、[专项运行摘要](p15-original-01.result.json)。
- [独立探针源码](p15_review_probe.py)、[有效探针失败输出](independent-probes-02.stderr.log)、[现场观察](independent-probes-02.stdout.log)、[运行摘要及零改动检查](independent-probes-02.result.json)。
- [源码及保护身份核对](identity-check.json)、[核对脚本](verify_evidence.py)。
- 第一轮探针输出仍保留在 `independent-probes-01.*`。该轮 4 FAIL、3 PASS、1 ERROR；ERROR 是规划侧正向 Fixture 未形成关系数据后访问空对象，不计 Engine 缺陷。第二轮沿用原 P15 已证实能形成关系的 care/peer-a 场景并增加显式非空前置断言，4 FAIL、4 PASS、0 ERROR。未修改 Engine 或弱化业务断言，第一次输出未覆盖。
- 探针文件第一次仅将场景由 private-care/peer 改为 care/peer-a，并增加形成关系的前置断言；故第一次原始输出对应修正前辅助场景，不能充作第二轮相同输入的证据。

在规划仓库运行以下命令；runner 只在规划目录保存证据，不使用 Engine 的证据输出目录。复跑时必须换未使用标签，文件以排他创建防止覆盖。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:\Adobe\python.exe' 'C:\Users\Administrator\Documents\Codex\2026-08-24\https-github-com-yuan69082-code-continuity\reviews\p15-independent-review-20260908\run_review.py' repair-probes-01 -m unittest -v p15_review_probe
```

单独重跑原专项时，把标签改为新的 `repair-p15-01`，模块参数改为 `test_p15_subject_growth test_p15_subject_lifecycle test_p15_subject_recovery`。先定点修复与正向对照，再 P15 专项、受影响兼容，稳定代码最后一次全量；不能引用旧全量冒充返修后新全量。

## 保护与范围

63 项保护、三份规划原件、正式七文件及树指纹、0.1.0、31 个原 P10 排除脚本均未改变。Git main，HEAD/本地 origin/main 均 `f1185d20da06f52e7e85015bc6b963cf9769d08c`，本地 ahead/behind 0/0，暂存区空；37 tracked 修改、146 untracked，恰为 151 个 P15 清单文件、31 个排除脚本及一份旧任务接续核查报告。本次未联网核实远端，因为没有提交/push任务。

正式树指纹仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。220 个 Python 文件解析通过，`git diff --check` 通过。既有源码核对、全量绿色和档案完整不能取代上面新反例的修复，也不能据此提前宣布 P15 ACCEPTED。
