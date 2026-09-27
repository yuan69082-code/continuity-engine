# W04-1 N09／N10 定点返修报告

状态：`IMPLEMENTED_NOT_ACCEPTED`；`EVIDENCE_CONFLICT=PRESENT` 表示本轮仍待独立复核，未登记用户验收。本轮仅在现行总施工 v1.6、最终新增 v1.6、长期能力 v6.10 的 W04-1 内处理 N09/T19—T21、T60 和 N10/T22、T85—T87 的契约边界。原 [Stage Brief](stage-brief.md)、[施工矩阵](matrix.md)及 D-086 开工记录仍有效；不进入 W04-2。

## 复现与最小修复

| 项目 | 修前正式入口证据 | 修复位置与结果 | 正向及拒绝对照 |
|---|---|---|---|
| N09：准备单主体／环境绑定 | 两个独立仓储有相同 `host:a`、generation=1 时，原 `handoff_isolated` 接受另一主体或 RESEARCH 环境的 TEST 准备单；拒绝预期均失败 | `EnvironmentAccessService.handoff_isolated` 在读写目标仓储前核对准备单与当前仓储主体、环境；旧端代次/主机及仓储 CAS 仍由原链验证 | 跨主体/环境拒绝后目标字节、revision、generation 不变；原同主体交接、旧端失权与重开测试保留 |
| N09：类型、缺项、状态一致性 | 准备单可同时称 `FIRST_IMPORT` 与 `READY_FOR_ISOLATED_HANDOFF`，也可有缺项却称就绪 | `MigrationPreparation` 构造时根据类型与实际缺项推导唯一合法状态；交接入口再限定同主体转移且无缺项 | 正常同主体转移仍就绪；导入/新主体为生产未就绪，入口切换仅 ENTRY_ONLY，缺项为 DEPENDENCY_MISSING |
| N10：输出能力期限 | 附件仍连接且未到期，但该路由的 `OUTPUT` 能力在可信时钟到期时，原 P17/E5-A 路径仍完成一次 Fake 效果与扣费 | `EnvironmentAccessService.require_action` 在原投递门禁核对所绑定输出能力的 `valid_until`；到期返回静态 `W04_ACTION_ABILITY_EXPIRED` | 到期拒绝零效果/零费用；未到期的限时能力经原链成功 1 次效果/1 次计费；原无期限能力、撤权及幂等测试保持 |
| N10：传感读数类型和有限性 | `NaN`、布尔可通过；无穷按范围报错；字符串/列表抛出非契约 `TypeError` | `SensorObservation` 在构造时要求读数为严格 `int/float` 且有限；`None` 仍表示未知 | `NaN`、正负无穷、布尔、字符串、列表均以静态代码拒绝；合法零值与未知仍通过且仓储零写入 |

首次证据是 [`w04-r1-before-01`](w04-r1-before-01.json)：4 个测试方法中 8 FAIL、3 ERROR，其中行动夹具 Windows 隔离临时路径过长是辅助 ERROR，不是引擎行为结论。纠正夹具路径与测试子用例互相影响后，[`w04-r1-before-02`](w04-r1-before-02.json) 在修前仍为 9 FAIL、2 ERROR，明确证明三类缺口；原始 stdout/stderr 均保留。修后 [`w04-r1-targeted-01`](w04-r1-targeted-01.json) 28 项中 27 PASS、1 ERROR：测试错把正式入站顶层 `IntegrationExecutionError` 当成内部 `EnvironmentAccessError`；原链正确保留静态原因。修正测试观察方式而不改变引擎行为后，[`w04-r1-targeted-02`](w04-r1-targeted-02.json) 为 29/29 PASS、13.709 秒、退出 0。修前、辅助和中间记录未删除或覆盖。

## 公共链、状态与限制

本轮运行实现只改 `src/continuity_engine/domain/environment_access.py`、`src/continuity_engine/services/environment_access_service.py`，正式回归只增 `tests/test_w04_1_environment.py`。公共影响限显式接入 W04 连接门禁的 TEST/RESEARCH 原入站、P17/E5-A 行动和模拟传感观察；旧调用未接线时仍走原路径。没有改变权限策略、资源计费、Action/SubjectState/Event/Memory 权威、回执、PAUSE/STOP、数据格式或正式外部契约。输出能力到期是本次动作资格拒绝，不把历史已执行事实改写为未执行；真实服务与硬件均未接入。

本轮同版兼容 [`w04-r1-compat-final-01`](w04-r1-compat-final-01.json) 为 182/182 PASS、290.358 秒、退出 0，覆盖 P16/P17/P18、W02 原回忆与贯通、W03 直接相关链。新标签完整回归 [`w04-r1-full-resume-01`](w04-r1-full-resume-01.json) 为 **1802 项：1801 PASS／1 既有 Windows symlink 1314 SKIP／0 FAIL/ERROR**，运行器 1876.171 秒、退出 0；`unittest` 自身计时 1874.690 秒。专项、兼容与全量前后指纹均为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`，集合有交集，不相加。旧 `w04-r1-full-final-01` 因用户临时暂停而[中断](repair-pause-01.md)，未取得总数及最终汇总；**不能计作全量 PASS 或行为 FAIL**。完整命令、退出码及 stdout/stderr 见[原始测试索引](test-index.md)。

W04-2 的完整 Fake Body 感知→Perception／动作→结果双向闭环、W04-3/4、W05 与 P20—P22 的生产能力均未在本轮施工。P00—P18、W02/D-081、W03/D-083、D-084 历史验收不变；旧 Windows 1314 SKIP、W02 较大负载限制及 F1/H1/F2 原因 `UNKNOWN` 不因本补修改写。施工方本地测试不冒充规划窗口独立实跑或远端 CI。

终局保护、文件身份和精确路径由[返修审计](repair-final.audit.json)及[清单](repair-final.pending-files.md)核对。新标签全量收口后没有 Python 测试进程；本轮不修改正式数据、不触碰 63 项保护文件或三份规划原文。D-085 的前置规划档案仍独立，原 57 项排除材料不纳入返修。未暂存、提交、push，也未开启 W04-2；本报告交回独立复核，不自行关闭 `EVIDENCE_CONFLICT`。
