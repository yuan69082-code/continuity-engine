# P18 独立复核：需要返修，尚未验收

复核日期：2026-09-12（本地晚间，Asia/Shanghai）。仅检查及隔离测试；未修改 Engine 源码、测试或档案，未操作 Git 写入，未联系施工任务，未进入 P19。

## 结论

发现 **1 项已证实的实现缺陷 R1**，用两条独立反例复现；另有施工方已披露的 **1 项历史证据待查 H1**，仍不能关闭。64 项原 P18 专项独立重跑全部通过，并不覆盖下面新增的并发反例。因此保持 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，不登记 D-073、不提交或 push。

## R1 / P1：短时控制事务竞争可以意外结束持续宿主

大白话：后台正在记运行状态，你也正好按下暂停，两边同时写同一本账。现在它不是等另一边写完，而是可能报错直接退出。你并没有叫它关机，进程却结束了；这违反 P18 的持续运行和“暂停仍保留控制”的要求。

### 原因与位置

- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_runtime_repository.py:31` 的 `file_lock` 使用立即失败的 OS 非阻塞锁（Windows `LK_NBLCK`，第 43 行）；第 113–115 行的控制/运行状态 `transaction()` 也使用它。锁短暂被另一个合法控制进程占用时，会产生 `RUNTIME_BUSY`。
- `C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/persistent_runtime_service.py:124` 的 `_observe()` 需要取得该事务锁。
- 同文件第 143 行 PAUSED 分支的 `_observe()` 在工作异常处理之外；锁忙会直接逃出 `tick()`。
- RUNNING 路径即便在第 181 行被捕获，第 183 行又调用需要同一把锁的 `_observe()`，在锁仍被占用时再次抛出。
- 第 83 行 `running()` 的异常/退出诊断也要写同一事务；第 185 行 `serve()` 未对这类正常竞争延后处理。因此实际 `runtime start` 可以无 STOP 退出，退出码 2，stderr 为 `RUNTIME_BUSY`。

### 独立反例，不依赖修改 Engine

探针文件：[test_independent_runtime.py](test_independent_runtime.py)。所有修改和锁竞争注入均限于临时 TEST 数据根及子进程内对象；没有改产品文件。

1. `test_idle_tick_survives_overlapping_owner_control`：完成初始维护后，另一个进程发起真实授权 PAUSE，在控制事务即将保存时用握手保持锁，调用当前宿主 tick。结果异常 `RuntimeBoundaryError / RUNTIME_BUSY` 逃出。控制随后保存成功；没有模型调用。
2. `test_paused_process_survives_overlapping_owner_control`：通过真实 `python -m continuity_engine.runtime start` 启动已暂停的宿主；另一个真实授权 PAUSE 事务占用状态锁，独立测试控制器最多观察 2.5 秒。宿主在没有 STOP 时退出，退出码 2。之后才执行测试清理 STOP；没有强制结束进程。

三个正向对照全部通过：非竞争的暂停/恢复/停止；重开后查询零持久化写入；零额度等待后补充资源无需新消息即可继续认知。

原始记录：[stdout](independent-edges-01.stdout.log)、[stderr](independent-edges-01.stderr.log)、[运行信息](independent-edges-01.result.json)。共 5 项：3 PASS / 2 FAIL，0 ERROR；unittest 6.310 秒，runner 6.979 秒。两个控制子进程均正常完成；测试所拥有的所有子进程均已回收。失败完整保留。

### 返修应满足的边界（待用户批准后交给施工方）

短时 checkpoint 事务忙应采用有界等待/退避或等价串行化，使现有宿主继续存活并及时处理控制，而不是意外退出或无休止忙循环。不要把当前宿主的短时状态锁竞争，与拒绝第二宿主的 owner OS 锁混为一谈；第二宿主仍须被拒绝。保留 generation fencing、控制幂等、revision CAS、STOP 终态、权限校验和损坏档案的真实错误。不能靠外部自动重启掩盖崩溃，也不能盲目吞掉所有异常。

需补充真实跨进程回归，覆盖 RUNNING/PAUSED/资源等待下的控制交错、锁释放后继续运行、STOP 仍可正常结束，以及锁长期不可得的有界行为与准确诊断。继续保留单宿主、零重复效果和零重复扣费约束。

## H1：历史 p18-final-04 超时原因仍未知，不等于 R1

已读原始 stderr/stdout/json。该次资源等待进程用例等待 WAITING_RESOURCES 超时：58 项中 57 PASS / 1 FAIL。清理 STOP 当时查询到宿主仍活着，随后进程正常退出 0；没有强制清理。记录没有保存超时前完整的活动/候选状态，STOP 又覆盖了当前活动信息。

这与 R1 的无 STOP 意外退出 2 不同，**没有证据证明 R1 就是那次超时的根因**。不能把后来通过解释为历史根因已解决，也不能凭空归因于 Windows 慢、额度截断或测试机性能。

可以补充清理前诊断与有界重复验证以判断当前风险；若原失败因缺失现场而无法重建，应继续如实记录 UNKNOWN，单独说明证据缺口和处置建议，交用户决定是否接受残余风险。不要删除失败、修改旧记录、直接增加超时阈值来宣称修好。

## 已验证的正常部分与证据身份

- 独立重跑原 P18：64/64 PASS；unittest 106.574 秒，runner 107.300 秒。包含原真实进程场景。记录：[运行信息](p18-original-01.result.json)、[stdout](p18-original-01.stdout.log)、[stderr](p18-original-01.stderr.log)。
- 施工方已完成的最终全量：1424 项中 1423 PASS、1 项既有 Windows 1314 SKIP、0 FAIL/ERROR，1036.819 秒。这里只核验记录与源码身份，**没有声称本次独立重跑全量或远端 CI PASS**。
- 当前 263 份源码/测试/资源与施工最终专项、最终全量运行前后 hash 完全一致；原 1360 项测试身份及原测试文件保留，新增 64 项。
- 独立身份审计 21 项检查通过：63 项保护文件、3 份规划、7 份正式数据及树指纹、版本和 32 项排除材料未变；253 份 Python 文件可解析；163 个登记清单 hash 一致，全部 164 个成果与本次初始快照一致。
- 原有历史文件排除明确工作区修改后，2124 份逐一核对无漂移。原格式告警与历史失败仍保留；不是本次新发现的实现问题。
- Engine Git：main，HEAD / 本地 origin/main 为 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地 ahead/behind 0/0，暂存区为空。21 tracked 修改 + 175 untracked = 164 个 P18 成果 + 32 个排除项。本轮没有联网查询远端。
- 两次测试前后各 2329 份 Engine 工作区文件快照一致，changed=[]。没有修复实现，也没有更改验收状态。

审计原始结果：[identity-check.json](identity-check.json)。

## 复现命令

在规划工作区执行；runner 自动配置 Engine 的源码导入、禁用 pyc，并把所有输出保存在规划侧。label 必须用新值，不能覆盖原失败记录。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:/Adobe/python.exe' 'reviews/p18-independent-review-20260912/run_review.py' independent-edges-02 -m unittest test_independent_runtime -v
```

注意：当前版本预期两条反例仍失败。返修后应原样通过，并增加正式回归及必要兼容验证。

## 工具操作说明

本轮读取时曾猜错 85 号文档名称、对 rg 传入不存在的通配文件路径；均为只读辅助查询错误，随后通过文件清单和精确路径读取。未计作 Engine 测试失败。行为测试没有导入 ERROR 或辅助控制失败。

下一步：请用户确认是否返修 R1，并继续核查 H1；确认前不修改实现、不发施工消息、不验收或 push。
