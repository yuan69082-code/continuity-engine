# P18 返修后独立复核：R1 定点通过，新增 R2 阻断

日期：2026-09-13，Asia/Shanghai。测试原始 UTC 时间对应本地 00:28—00:34。

结论：**不能验收或 push。** R1 原探针及正式竞争测试独立通过；另确认一个恢复活性缺陷 R2。历史 H1 和施工方全量 F1 仍未证明根因，不将其与 R2 擅自合并。

本轮只读复核 Engine，在隔离 TEST 数据根运行测试。没有修改 Engine 源码、测试、档案或 Git，没有给施工任务发消息，没有登记 D-073、进入 P19。用户报告 Codex 软件意外退出后，确认四组测试及前后快照已完整保存，仅补写独立身份核验和本报告，没有重复运行已经完成的测试。该软件退出与以下 Engine 缺陷不是同一事件。

## R1：短时存档锁竞争导致进程退出，针对性复核通过

- 原独立五项探针原样重跑：5/5 PASS，unittest 9.114 秒，runner 9.807 秒。
- 新增正式竞争回归 20 项 + 施工全量失败的原进程用例 1 项：21/21 PASS，unittest 51.556 秒，runner 52.302 秒。
- 已检查 owner 锁与 checkpoint 锁区分、有界等待、忙锁退避、最新控制修订核对、退出时保留原异常，以及相关正式正反向测试。原单宿主、权限、CAS、STOP、效果不重发的定点检查通过。
- 这里只确认 R1 的针对性修复，不是正式验收整个 P18；原全量失败也不能被这 21 项的本轮通过覆盖。

记录：[original-five-01](original-five-01.result.json)、[targeted-formal-01](targeted-formal-01.result.json)，同名前后快照及 stdout/stderr 均在本目录。

## R2 / P1：明确未调用模型的暂停，被持久化成失败并困在 UNKNOWN

### 大白话

引擎已把“准备开始思考”登记好，但模型还没有被调用。这一瞬间收到暂停，本应先放下这件事；之后恢复时，重新检查条件再继续。

现在它把这次暂停登记成“思考失败”，之后又把这份记录一律解释成“可能已经执行过，结果不知道”，只等核实，不再继续这次认知。进程仍活着、资源也够，状态却不再推进；重新打开也没有解除这个状态。它不是停止所有控制功能，但阻断了正常的持续认知恢复。

### 已证实代码路径

1. `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/thinking_service.py:143` 创建 ThinkSession，随后先保存准备记录。
2. 第 185 行执行 `execution_guard('before_provider')`，第 186 行才实际调用 Provider。
3. 合法 PAUSE 在此检查点触发 RuntimeDeferred，实际 Provider 调用次数不增加。然而第 215—234 行通用异常处理将会话写为 FAILED，错误码为 `RUNTIME_CONTROL_PAUSED_OR_STOPPED`，并抛出 ThinkingExecutionError。
4. 原 Scheduler 在派发前已记录 attempt UNKNOWN；异常后继续保持结果未知。
5. `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/runtime_cognition.py:187` 的 query，第 192—194 行把所有未成功完成的 ThinkSession 一律返回 UNKNOWN，没有区分明确的调用前暂停。
6. 同文件第 92—103 行的认知任务身份以主体 revision 和 MindState 为依据。状态没有推进时仍得到同一任务身份；UNKNOWN 查询不再调用模型，也没有新的认知工作推进当前状态。因此仅恢复、推进可信时间或重开同一数据根都无法解除已确认场景中的停滞。

这里不是要求把真正的 UNKNOWN 当成未执行；问题是**未记录/未正确消费“明确在调用前被控制阻断”这个区别**。不能仅凭错误字符串推断所有 FAILED 都可安全重试。

### 独立确认与对照

先执行预定的 12 项交错检查：9 个时钟推进点、普通双轮暂停恢复、预算后会话创建前暂停、Provider 调用前暂停。

结果 11 PASS / 1 FAIL，unittest 27.531 秒，runner 28.297 秒。只有最后一种暂停位置失败。普通暂停恢复以及更早的资源后暂停正常，不是所有暂停都出错。

进一步固定检查四种条件：

| 条件 | Provider 实际调用 | 恢复后现场 | 结果 |
|---|---|---|---|
| 首轮调用前暂停再恢复 | 0 次 | revision 1，宿主 alive，desired RUNNING，WAITING_VERIFICATION，预留 token 320 | FAIL |
| 第二轮调用前暂停再恢复 | 仅首轮 1 次 | revision 2，宿主 alive，desired RUNNING，WAITING_VERIFICATION，预留 token 640 | FAIL |
| 首轮调用前暂停，重新打开同一根再恢复 | 原进程与重开对象均未调用模型 | 同一 FAILED 会话仍在，宿主 alive，WAITING_VERIFICATION | FAIL |
| Provider 已实际进入后抛异常 | 1 次，之后不重放 | 继续 UNKNOWN，无新效果 | PASS，必须保留的保守对照 |

第二组 1 PASS / 3 FAIL，0 ERROR，unittest 6.376 秒，runner 7.052 秒。每条失败在恢复后都推进可信时间并执行多个到期 tick，排除了只是还没到下一次检查时间。清理/离开运行上下文前的诊断明确记录宿主仍存活。

首次交错探针：[test_independent_resume.py](test_independent_resume.py)、[resume-edges-01.stdout.log](resume-edges-01.stdout.log)、[resume-edges-01.stderr.log](resume-edges-01.stderr.log)。

确认探针：[test_pause_resume_confirmation.py](test_pause_resume_confirmation.py)、[pause-confirmation-01.stdout.log](pause-confirmation-01.stdout.log)、[pause-confirmation-01.stderr.log](pause-confirmation-01.stderr.log)。确认探针复用首次探针的取证 helper，复跑时两份文件均需保留。运行器：[run_review.py](run_review.py)。

### 修复边界建议，等待用户确认

应在原 Thinking/Runtime/Scheduler 恢复链中正确区分明确未派发的控制延后，与调用已开始或确实无法证明的 UNKNOWN；在当前权限、材料、控制与生命周期检查通过后，允许明确未执行的工作合法继续或按既有机制重新评估。

必须保留原会话/任务身份关联、既有事实、预留及结算，不能删除 FAILED、抹掉 usage、每次恢复另造无关联任务，或把所有 UNKNOWN/FAILED 重置成未执行。已进入 Provider、已发生 Action/Evolution/外部效果的事实仍不得盲目重复调用或扣费。跨重开恢复也应有可核验的持久依据，而非只靠内存布尔标记或可伪造错误字符串。

本轮 R1 返修未修改 ThinkingService 和 RuntimeCognition；本次发现 R2 不等于已经证明 R1 修改引入了它。

## H1 与 F1：分别保留，不宣称已经破案

- **H1**：旧 p18-final-04 的资源等待超时，原 token_used=0、无未确认任务；清理前关键活动和水位缺失。仍 UNKNOWN。
- **F1**：施工本轮 full-final-01：1444 项中 1442 PASS、1 既有 Windows 1314 SKIP、1 FAIL、0 ERROR，1233.659 秒。失败现场是第二轮认知 UNKNOWN/WAITING_VERIFICATION，token_used=640，宿主 alive，checkpoint_busy=false，随后 STOP 正常退出 0。
- 本次对 F1 原进程用例只做了一次复跑，它通过了；不因此关闭原失败。
- R2 第二轮反例的部分症状与 F1 相似，但 F1 缺失失败时 ThinkSession/异常链，而独立反例明确插入了调用前 PAUSE。**不能仅凭相同 token 数和 UNKNOWN 状态断言它们是同一根因。** R2 是独立确认的缺陷；F1 继续作为尚未解释的全量失败记录。
- 后续诊断应在 STOP/删除临时根之前，保存脱敏的会话状态、调用阶段、原始请求/回执身份、错误码和异常链位置，不记录秘密正文。不得用连续重跑到绿或放宽超时替代定位。

## 身份与保护核验

[identity-check.json](identity-check.json) 的 25 项身份检查全部通过，**这是文件和证据一致性通过，不是行为验收通过**。

- 当前 264 份源码/测试/资源与施工最终五组运行前后清单一致，包含真实失败的全量记录。
- 原 1424 项身份保留，新增正式回归 20 项。原进程用例断言调用 AST、函数参数及超时默认值保持一致，其他原测试文件 hash 不变。
- 本轮修复源码/测试变化恰为两个运行文件、一个新正式测试文件、一个增加诊断的原进程测试文件。
- 63 保护项、3 份规划、7 份正式数据及树指纹、版本/pyproject、31 个 P10 脚本和 1 份旧报告均未变。
- 10 份独立原件与施工归档副本 hash 一致；初版 P18 证据无漂移，旧历史排除明确工作区修改后核对一致。
- 当前 238 个 P18 成果 + 32 排除项与 Git 清单完全对应；登记的 237 个成果 hash 一致，全部 238 个成果也与本次测试前快照一致。
- main / HEAD / 本地 origin/main 仍为 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地 ahead/behind 0/0，暂存区空；21 tracked 修改、249 untracked。本轮没有联网查远端，没有 CI PASS 声明。
- 四组独立测试前后均为 2403 份 Engine 工作区文件，changed=[]。本轮没有重跑完整 84 项 P18 或整套全量，不将施工记录称作本轮独立实跑。

只读文件搜索曾遇到规划侧旧 testdeps 目录访问被拒；没有修改那些目录，也没有作为测试失败统计。软件退出打断的是尚未落盘的身份脚本创建；恢复后确认该文件不存在才重新创建，原四组日志没有覆盖或重跑。

## 后续复现

在规划工作区运行，使用未占用标签，不能覆盖已有原始失败：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:/Adobe/python.exe' 'reviews/p18-repair-review-20260913/run_review.py' pause-confirmation-02 -m unittest test_pause_resume_confirmation.PauseResumeConfirmation -v
```

当前版本预期 3 FAIL / 1 PASS。修后应原样通过，并将有效反例加入 Engine 正式回归；真正不明执行结果仍须保持不盲目重放。

下一步等待用户确认：授权施工方返修 R2，并继续定位 F1、如实保留 H1 的证据限制。当前保持 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，不自行登记验收、提交、push 或进入 P19。
