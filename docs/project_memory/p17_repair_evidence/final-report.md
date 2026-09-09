# P17 R1/R2返修交付

P17 R1/R2补修已实现，等待独立复核；P17 / Engine side / P17-01—P17-12 IMPLEMENTED_NOT_ACCEPTED。P00—P16 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，监工阻断待独立确认，本轮不自行关闭。D-070仅追加返修事实，D-071未创建/未使用。无Git写操作。

本轮P17专项：74项，74 PASS / 0 SKIP / 0 FAIL / 0 ERROR，128.466秒，exit=0；最终全量：1360项，1359 PASS / 1 SKIP / 0 FAIL / 0 ERROR，1171.401秒，exit=0。原1348测试身份与断言保留，新增12项单列。独立原探针另报，不增加Engine正式测试数。下方初版与旧全量仅为修前历史，不覆盖此次阻断。

R1根因：Broker/Reality/Recoverability读取早于最终capacity同步回调，Outbox锁没有使旧授权自动保持有效。修复仅调整current()顺序，将资源和原gate工作放在授权读取前，最终投递在原事务内读取当前条件。正式测试用事务边界定位，验证三种撤销零新增效果/实际扣费、文件不变、合法显式retry及历史事实恢复。
R2根因：route.cost估计被当作实际Fake积分，而原合成回执固定每成功效果1积分。修复复用实际效果投影，统一预检、文档写入和回执累计；合法cost=0保留，固定1积分语义明确，未改原ActionReceipt契约。覆盖零/默认估计、满额、重放、其他上限和失败0积分。

实际代码增量仅：[ExecutionService](../../../src/continuity_engine/services/execution_service.py)、[P17 Fake](../../../src/continuity_engine/testing/p17_execution_fixture.py)；新增[12项正式回归](../../../tests/test_p17_repair_edges.py)。原1348项测试文件与断言逐字节保留。

| 本轮实跑 | 结果 | 原始证据 |
|---|---|---|
| formal-after-02 | 12项，12 PASS / 0 SKIP / 0 FAIL / 0 ERROR，18.846秒，exit=0 | [JSON](formal-after-02.json) / [stdout](formal-after-02.stdout.log) / [stderr](formal-after-02.stderr.log) |
| independent-after-01 | 7项，7 PASS / 0 SKIP / 0 FAIL / 0 ERROR，6.759秒，exit=0 | [JSON](independent-after-01.json) / [stdout](independent-after-01.stdout.log) / [stderr](independent-after-01.stderr.log) |
| p17-final-01 | 74项，74 PASS / 0 SKIP / 0 FAIL / 0 ERROR，128.466秒，exit=0 | [JSON](p17-final-01.json) / [stdout](p17-final-01.stdout.log) / [stderr](p17-final-01.stderr.log) |
| compatibility-final-01 | 224项，224 PASS / 0 SKIP / 0 FAIL / 0 ERROR，169.793秒，exit=0 | [JSON](compatibility-final-01.json) / [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) |
| full-final-01 | 1360项，1359 PASS / 1 SKIP / 0 FAIL / 0 ERROR，1171.401秒，exit=0 | [JSON](full-final-01.json) / [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |

P17专项包含原62项及新增12项；原独立7项单独运行，不增加Engine正式测试数，也不重复相加。前一轮1348项/1347 PASS/1 SKIP/1100.490秒仅为修前历史，本轮全量是新的实际运行。原1314 SKIP如实保留。
限制：同步本地投递、无写副作用的授权读取端口、确定性Fake效果/回执和本机OS锁；没有跨系统原子撤权或生产exactly-once保证。生产Adapter/凭据/恢复及P18持续运行仍NOT_READY。正常心理内容不纳入现实边界筛查。

[监工报告原件副本](independent/review-report.md) · [完整返修简报](independent/repair-brief.md) · [原探针](independent/test_independent_edges.py) · [全部失败历史](test-history.md) · [矩阵](../80_P17_规划施工测试验收矩阵.md) · [复跑命令](../82_P17_测试索引与验收入口.md) · [终局审计](final.audit.json) · [精确清单及排除项](final.pending-files.md)

保护核对、源码身份和完整Git状态见终局审计。EVIDENCE_CONFLICT=PRESENT，交回独立复核，不自行验收、不创建D-071、不Git写、不进入P18。
