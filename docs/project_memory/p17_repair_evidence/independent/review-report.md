# P17 独立复核：两项返修建议，未验收

日期：2026-09-09。范围：Engine P17 实现、原专项与独立反例、来源/保护项/证据/Git 只读核对。

结论：原 62 项专项独立运行全部通过，但独立补测稳定发现两个缺口。建议保持 `IMPLEMENTED_NOT_ACCEPTED`，等待用户确认返修；不登记 D-071，不提交、不 push、不进入 P18。本报告不修改 Engine 的现行状态文件。

## R1：最终资源检查期间撤权，仍然产生新效果（优先修复）

位置：`C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/execution_service.py` 的 `current()`，第 177—198 行，以及 `execute()` 第 223—230 行。

原因：Broker 授权、Reality 授权、Recoverability 检查都在 `capacity()` 之前。最后一次持有 Outbox 事务锁的 `capacity()` 返回后，只检查原 Context/Planner gate，并没有发现刚才的 P17 授权或可恢复条件已经变更。Outbox 的锁串行化投递，却不使这些外部门槛成为同一个有效快照。

独立反例使用现成 TEST Fixture 的资源检查 hook，在正常 C1 的第三次 capacity 调用（最终 Outbox 事务内检查）分别执行：

1. 撤销 Broker 授权；
2. 将 recoverability 置为不就绪；
3. 撤销 Reality 授权。

三项均确认实际到达最终检查，预期零新增效果，实际均产生 **1 次本地 Fake 效果**，断言 `1 != 0`。两次独立运行结果相同。第一次检查之前撤权的正反对照通过；原专项只覆盖较早的一次 hook 变更，未覆盖最后一次。

修复目标：在产生新效果的边界获得一致、有效的当前许可与资源/恢复条件；明确检查有效期及提交点。不能只靠固定次数重复检查来掩盖同一时序窗口。至少覆盖以上三个最晚检查时序，同时保留合法执行、历史已执行事实核实、UNKNOWN 不盲重发、取消/补偿和正常心理内容不受筛查等已有语义。

边界说明：这是用本地同步回调确定性复现的检查顺序问题，不是关于所有真实分布式系统任意瞬间撤权的保证；没有调用生产服务。

## R2：合法零费用配置与 Fake 实际扣费不一致，越过积分上限

位置：`C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/testing/p17_execution_fixture.py` 第 89—106 行 `projected_document()`，第 152—157 行 `FakeRealityBoundary.capacity()`；合法配置依据为 `domain/execution.py` 第 45、57 行。

原因：`WorldCapability.cost` 合法范围包括 0；容量检查计算 `已用 credits + route.cost`，但 Fake 每次成功效果实际固定增加 1 credit。许可检查与实际效果使用了不同的计费规则。

独立反例：设置 `BlastRadius(credits=1)`，在新请求创建前把路径 cost 设为合法的 0 并重建 C1 运行时。第一轮成功后实际 credits=1；下一轮仍然获准执行，实际 credits=2、效果数=2。预期始终不超过 1，断言 `2 not less than or equal to 1`。两次独立运行结果相同。

修复目标：让投递前预计消耗、Fake 实际世界写入及回执使用同一计费语义，或者在任何效果前明确拒绝该 Fake 不支持的配置。覆盖 cost=0、正常 cost=1、上限恰好可用及下一次被拒绝；不能篡改测试上限、隐藏实际扣费、放松断言或把有效的零费用能力全局禁用来制造通过。

边界说明：这是 P17 本地 TEST Fake 的费用模型与 BlastRadius 验证缺口，**不是已发生真实货币扣费**；默认 cost=1 的既有案例仍通过。

## 本次独立实跑

| 运行 | 结果 | unittest 耗时 | Engine 前后文件快照 |
| --- | --- | --- | --- |
| 原 P17 专项 `p17-original-01` | 62 PASS，0 SKIP/FAIL/ERROR | 84.570 秒 | 2098 / 2098，零变化 |
| 独立补测 `independent-edges-01` | 3 PASS，4 FAIL，0 ERROR | 6.900 秒 | 2098 / 2098，零变化 |
| 同一补测复现 `independent-edges-02` | 3 PASS，4 FAIL，0 ERROR | 6.959 秒 | 2098 / 2098，零变化 |

4 条 FAIL 对应 R1 的三个时序场景和 R2 的一个额度场景，不是四个独立根因。

三个通过的对照：正常 C1 相同请求重放仅产生一次效果/扣费；初始已撤权时零效果；既有结果撤权后不再进入上下文，且不阻断后续正常沉默轮次。最后一项排除了“旧结果撤权必然毒化以后所有思考”的猜测，未作为缺陷报告。

原始命令、stdout、stderr、前后快照及退出码均在本目录保存；第二次运行未覆盖第一次证据。

复现命令（PowerShell，从本规划工作区运行；标签必须未使用）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:/Adobe/python.exe' 'reviews/p17-independent-review-20260909/run_review.py' independent-edges-03 -m unittest test_independent_edges -v
```

## 来源、保护项和既有证据

本次独立运行 `verify_evidence.py`：**22 / 22 项通过**，详细结果见本目录 `identity-check.json`。

- 当前 252 个源码、测试及资源文件与最终专项、最终全量的运行前后身份记录完全相同；原 1286 项测试身份保留，新增 62 项，原测试文件逐字节不变。
- 源码/测试增量为 4 个旧文件修改、9 个新文件；242 个 Python 文件独立语法解析通过。
- 63 项保护文件、三份规划、7 个正式数据文件及其树指纹、31 个 P10 脚本及另 1 个旧接续报告均不变；三份开工材料原件与副本完全匹配。
- 136 个 P17 待提交路径与 32 个排除路径精确覆盖当前 21 个 tracked 修改、147 个 untracked 文件；已记录的 135 个待提交文件 hash 匹配（审计文件本身不自哈希）。
- 本地 `main` 与本地 `origin/main` 均为 `0c440b0476b07723abafe93777fe895b64fd8d0e`，本地 ahead/behind 为 0/0，暂存区为空。未查询远端、未写 Git。版本 0.1.0 及 pyproject 不变。
- 本轮 tracked `git diff --check` 通过。既有 8 处格式告警仍是历史材料事项，不是本轮两个功能缺口的根因；未改写历史原始日志。

施工方的 **1347 PASS + 1 既有 1314 SKIP，1100.490 秒**，本次核对了原始结果、数量、身份和来源，并未独立重跑这次全量。施工方 644 PASS + 1 SKIP 的兼容组合是在最后四文件修补前运行，不能称为当前版本独立兼容结果；其全部 645 项身份确实已被当前最终全量覆盖。原记录明确标识了该时间差，没有用旧版本冒充当前版本。

没有远端 CI PASS 声明。以上通过项不覆盖本次新增反例，不能以原全量通过否认已复现的缺陷。

## 下一步权限

等待用户确认后，才提供合并 R1/R2 的返修提示词，由用户转发 Engine。修复后独立复核，再由用户单独确认验收、Git 收尾；不擅自发消息给其他任务，不改 Assistant，不进入 P18。所有本轮新增文件只在本规划工作区的 review 目录。
