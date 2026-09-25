# W03 原始运行索引

运行器：从 Engine 根目录设置 `PYTHONPATH=src`，以 `E:/Adobe/python.exe docs/project_memory/w03_evidence/run.py <新标签> <unittest 参数>` 执行。每个标签分别保存开始记录、stdout、stderr、最终 JSON；JSON 绑定运行前后源码/测试/资源指纹及退出码。不得覆盖旧标签。所有测试仅使用隔离 TEST 根。

| 标签 | 范围 | 真实结果 | 说明 |
| --- | --- | --- | --- |
| `core-before-01` | N04 首次反例 | FAIL/ERROR | Gate 尚未实现；修前证据。 |
| `core-after-01` | N04 首轮 | FAIL | TEST 直接改写受保护主体字段，改为合法 Event/Evolution；原记录保留。 |
| `core-after-02` | N04 | 4 PASS | 首批 N04 实现验证。 |
| `recognition-draft-01` | N03 首轮 | ERROR | Windows TEST 路径过长，为辅助夹具问题。 |
| `recognition-draft-02/03/04` | N03 | 逐轮通过 | 增补更正和撤回测试；各轮结果见各自 JSON。 |
| `recognition-input-01/02` | W02 原消息联验 | ERROR/FAIL | 第一次缺候选；第二次定位为路由已有事件、Composer 预算未纳入。 |
| `recognition-input-03` | W02 原消息联验 | ERROR | 同根 Timeline/Memory 片段在原 P15 捕获里重复创建候选；保留真实反例。 |
| `recognition-input-04` | W02 原消息联验 | 1 PASS | 同轮去重后，原消息、Event、Learning、Evolution 连通。 |
| `items-draft-01/02` | N06 | 逐轮通过 | 事项状态和事实回放。 |
| `items-source-before-01` | N06 来源撤销 | FAIL | ready 曾保留来源失效事项；修前证据。 |
| `w03-targeted-01` | N03/N04/N06 | 15 PASS、1 FAIL | 原子失败测试打错仓储实例，为测试辅助错误。 |
| `w03-targeted-02` | N03/N04/N06 | 16 PASS | 注入原提交仓储后通过。 |
| `item-completion-01` | N06 完成事实 | 1 PASS | 事项创建记录不能充当完成事实；独立绑定的内部事实可完成。 |
| `w03-special-01` | W03 专项 | 19 PASS、0 SKIP | 与兼容及全量启动时的源码指纹 `sha256:faf867faf3c9eeb4d9cb03698a30e931e9a67e5858ba7821529e19ba4065115e` 相同；终局仍须核对。 |
| `w03-compat-01` | P09/P11/P14/P15/P18/W02 相关兼容 | 175 PASS、1 ERROR | W02 已知 1000ms 回忆时限在两根+摘要场景触发 `RECALL_TIMEOUT`；原输出保留。 |
| `w02-timeout-diagnostic-01` | 原失败用例单独复查 | 1 ERROR | 同一 `RECALL_TIMEOUT`，并非兼容组相互污染才会发生。 |
| `w02-deadline-diagnostic-01` | 诊断辅助 | ERROR | 导入环境少仓库根；不计 Engine 缺陷。 |
| `w02-deadline-diagnostic-02/03` | 限定诊断 | 测试流程被明确阻断 | 记录 16 项检索、1036.62/1033.849ms；事项记录解析 883 次合计 2.58ms。未放宽原时限或吞异常。 |
| `due-before-01` / `due-after-01` | N06 期限含义 | 前版 FAIL；修后 3 PASS | 到期是期限与排序因素，不能误作最早可开始时间；原失败保留。 |
| `read-boundary-01` / `w03-extra-01` | 当前读取、来源与并发 | 2 PASS / 4 PASS | 只读理由、权限撤销、CAS、等待恢复等。 |
| `w03-special-03` | W03 扩展专项 | 21 PASS、1 FAIL | 保护核心计数的 TEST 断言曾把独立的保护意图也计入，修正测试期望；原失败保留。 |
| `w03-special-final-02` | 最终 W03 专项 | 25 PASS，101.762 秒，退出 0 | 前后源码指纹均为 `sha256:fb18d1c75f80219939ac0acb7c2099e2a7653be3115810ad3b6b687a8641bb7f`。 |
| `w03-compat-final-02` | 最终受影响兼容 | 175 PASS、1 ERROR，378.054 秒，退出 1 | 同一最终指纹；W02 回忆时限 `RECALL_TIMEOUT`。不可写为整组通过。 |
| `full-final-01` | 早期完整回归 | 1755 项：1753 PASS、1 既有 SKIP、1 ERROR；1990.323 秒，退出 1 | 较早源码 `sha256:faf867faf3c9eeb4d9cb03698a30e931e9a67e5858ba7821529e19ba4065115e`；错误为同一 W02 回忆时限，不是最终版结果。 |
| `head-w02-deadline-01` | HEAD 旧版隔离对照 | 1 ERROR：`RECALL_TIMEOUT` | Git HEAD 的 src/tests 解包至独立 Temp 后用原测试复现同一时限；此对照不能把当前兼容错误算作通过。 |
| `full-final-02` | 最终版完整回归 | 1761 项：1759 PASS、1 既有 Win1314 SKIP、1 ERROR；2013.319 秒，退出 1 | 前后源码指纹均为 `sha256:fb18d1c75f80219939ac0acb7c2099e2a7653be3115810ad3b6b687a8641bb7f`。唯一 ERROR 仍是原 W02 用例的 `RECALL_TIMEOUT`；不可写为全量通过。 |

测试集合有交集，不能相加。历史 W02 全量仅为基线引用，非本轮实跑。既有 Windows 1314 SKIP 与 F1/H1/F2 UNKNOWN 保留。无远端 CI 实跑证据。

## N06 独立复核后返修增量

本表上方均为返修前当时的真实结果，不作覆盖。返修修前反例、辅助 ERROR、中断标签、同条件 W02 诊断及最终同版专项/兼容/全量，见[新运行索引](../w03_n06_repair_evidence/test-index.md)和[返修报告](../w03_n06_repair_evidence/report.md)。最终源码指纹为 `sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf`；W03 仍待独立复核。
