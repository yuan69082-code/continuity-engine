# W02 回答前回忆超时定点补修交付

**状态：`IMPLEMENTED_NOT_ACCEPTED`；`PLANNING_CONFLICT=NONE`；`EVIDENCE_CONFLICT=PRESENT`，交规划窗口独立复核。** 本轮不是 W02 或 W03 重新验收；D-081、D-083 和 P00—P18 的历史验收不变。未执行 Git 暂存、提交或推送，W04 未启动。

## 修前事实与逐站定位

- 历史 [`integration-draft-01`](../w02_integration_evidence/integration-draft-01.json) 的原始 ERROR 与 [`w02-paired-diagnostic-01`](../w03_n06_repair_evidence/w02-paired-diagnostic-01.json) 中旧 HEAD 1062.669 ms、当时 W03 版 1049.201 ms 的单次第三轮/16 项 `RECALL_TIMEOUT` 保留。两次单次记录不能证明唯一根因，也不能互相替代。
- 本轮当前基线为 Engine `main`、HEAD/本地与实际远端 `8c6e18cd30108f553df0bde55d7a190a114ea1a0`，304 项源码/测试/资源指纹 `sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf`。修前正式第三轮原测试[通过一次](third-prefx-01.json)，但它没有覆盖原四份负载。重建的四份资料经**正常原始消息入口**在第四次提交[真实超时](four-prefx-02.json)：1203.258 ms、14 项检索、模型仅此前 3 次、第四次无新效果；没有未经核查的回答。另两次带仪器的四份测量也失败，原输出分别[01](four-measure-prefx-03.json)、[02](four-measure-prefx-04.json)。第一版测量脚本缺少测试包导入上下文、手动调用测试 `tearDown` 的辅助错误分别保留在 `third-measure-prefx-01/02`；它们不是引擎缺陷。
- 拆站仪器只用于定位，不能用其附加开销冒充业务时延。[修前完整分站记录](four-measure-prefx-04.stdout.log)的一次四份运行：Router 761.846 ms、Composer 449.032 ms；外部候选在同轮被当前读取 5 次，`absorbed` 累计 1015.682 ms，其中能力账本完整读取/解析/校验 45 次、累计 657.902 ms。这些计时是嵌套的，**不可相加**。operation journal 精确字节读取 17 次、3.645 ms；总载入 102.699 ms，其中副本构造 58.268 ms，其余约 40.8 ms 包括解析/记录校验与 Python 调用，不能称为单独精确计时。候选解释 37 次、3.014 ms。资料查询与权限复核的具体来源计时均在原始 JSON 中。

## 最小改动与公共影响

仅在 `AssociativeRecallService.prepare` 的**同一次回答准备**进入原 E5-A 能力账本解析复用作用域。`JsonIntegrationResultLedger` 每次仍读取权威能力文件的当前字节；字节变化立即重做完整解析与现有记录校验，损坏仍失败；字节未变时复用已校验记录并返回独立副本。作用域结束即失效，旧公共调用路径不进入此作用域。没有缓存授权、Provider 结果或根证明：Router/Composer 的候选当前性、P16 回执、权限、来源和版本检查逐次照旧执行。operation journal 原完整校验与副本隔离原样保留。原 1000 ms 策略、原断言、请求与回执身份、模型/现实执行、费用和 revision 逻辑未改。

[修后分站记录](four-measure-draft-01.stdout.log)对应另一份测量：能力账本仍被请求 45 次，但完整解析/校验的累计耗时降至 38.584 ms；Router 394.643 ms、Composer 189.654 ms，回忆记录 607.236 ms。此为隔离 TEST 本机证据，不宣称真实模型语义或生产性能。

## 修后及安全结果

- 预先固定的三次无仪器四份负载分别为 **626.903、624.307、614.196 ms**；第三轮 16 项检索分别为 **682.117、665.591、700.247 ms**，每次均 `READY` 且低于未改的 1000 ms。六份原始结果在[测试索引](test-index.md)，不按绿灯补跑次数。四份情形里的多个资料渲染共享两项根证明，原 W02-C 冲突/去重规则可不把每份资料都放入最终 Context；正式测试检查必要旧 Memory 与当前输入进入回应前 Context、原回执事实仍可追踪，并不把“收到四份”误当“回复必须使用四份”。
- 五项新正式测试覆盖四份负载、第三轮 16 项及派生撤回、当前字节变化/损坏/私有副本、查询中撤权及文件变化。首次辅助路径长度错误与两条过窄断言的 FAIL 原样保留；后续断言准确检查**失效候选未进入回答上下文**，不要求无关合法内部回应一并失败，也不把新合法外部动作的账本追加误判为旧文件未恢复。正式最终 5/5 PASS。
- W02 专项 161/161 PASS；W03 兼容 32/32 PASS；P05/P06/P16 公共兼容 155/155 PASS。最终完整回归 1773 项：1772 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，测试耗时 1792.823 秒、runner 1793.826 秒、退出码 0。五组结果的前后源码指纹均为 `sha256:1008aabea9c72f769b97886cd9017051da083a95d14f9d9a010d7a738daa297b`，原 1768 项身份保留，新增正式 5 项。关闭回忆门控、局部失败/重开、旧同请求恢复、来源撤销/权限变化/损坏等原测试均在对应组中。集合有交集，不能相加；原始输出和命令见[测试索引](test-index.md)。

## 原始目标、限制与停止点

本轮没有增加固定运行时长、聊天触发条件或模型调用频率；引擎持续运行、Owner PAUSE/STOP、资源及生命周期边界不变。失效来源未进入最后 Context，超时仍明确阻断。六次定点说明**这两种隔离负载在此固定版本和本机条件下**通过，不保证更大文件、更多资料或真实服务永不超时；正式资料服务 P22、生产数据恢复 P20/P21、观察页面 P19 均未开放。历史 F1/H1/F2 原因仍为 `UNKNOWN`，既有 Windows 1314 SKIP、历史 FAIL/ERROR、中断和辅助错误不倒改。没有远端 CI 运行结果。

逐项对应见[矩阵](matrix.md)；原始命令、stdout/stderr、退出码、前后源码身份见[测试索引](test-index.md)；终局保护与精确清单以 `verified-final.audit.json`、`verified-final.pending-files.md` 为准。首轮辅助审计的[编码异常](audit-helper-error.md)和 `final.*` 原样保留。下一步仅规划窗口独立复核及用户决定，不登记新验收或执行 Git 写操作。
