# W03/N06 定点返修原始测试索引

运行器：`E:/Adobe/python.exe docs/project_memory/w03_evidence/run.py <label> <unittest args>`，工作目录为 Engine 根，设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=<Engine>/src`。每个标签都有 `.started.json`、完整结果 `.json`、`.stdout.log`、`.stderr.log`；只有 STARTED 而无结果的中断标签除外。所有运行器结果记录命令、退出码、时长及源码前后指纹。不同集合有重叠，不求和。

| 标签 | 用途及事实 |
| --- | --- |
| `n06-repair-before-01` | 第 65 项容量反例；同时保留初版夹具分类、Memory 状态和 Windows 长路径 ERROR。 |
| `n06-repair-before-02` | 旧事项迁移入口缺失、Memory 状态误判；外部材料设置辅助错误。 |
| `n06-source-before-03/04` | 修正 Memory 入站比较后，不可用 Memory 仍进入 ready；外部材料约束辅助错误原样保存。 |
| `n06-external-before-05` | 真实外部派生材料部分撤回后，重开 `ready` 仍返回旧事项。 |
| `n06-existing-legacy-before-01` | 已有结构化事项完成时才明确绑定旧字符串，首次修补不能同步清除旧唤醒。 |
| `n06-memory-permission-before-01` | 仅撤销未入本轮 Context 的 Memory 来源权限后，事项仍被列为 ready。 |
| `n06-memory-permission-after-01` | 测试方法名拼错的辅助 ERROR；`after-02` 才是正确命令 1/1 PASS。 |
| `n06-repair-after-01/02`、`n06-source-after-03` | 中间源码的定点和旧 N06 对照；不作为最终版本证据。 |
| `w03-n06-special-final-01/02/03` | 中间源码 W03 专项，全部保留；最终版本为 `-04`。 |
| `w03-n06-compat-final-01/03`、`w03-n06-full-final-01` | 只有 STARTED，发现更完整 N06 兼容反例后主动中断；没有完整退出码或数量，不计 PASS/FAIL。 |
| `w03-n06-compat-final-02` | 更早源码 176 项中 175 PASS、1 `RECALL_TIMEOUT` ERROR；非最终版，不覆盖历史。 |
| `w03-n06-special-final-04` | 最终源码 32/32 PASS，155.062 秒，exit 0。 |
| `w03-n06-compat-final-04` | 同一最终源码 176/176 PASS，350.243 秒，exit 0；此前 W02 超时历史及独立同条件诊断仍有效。 |
| `w03-n06-full-final-02` | 同一最终源码完整回归 1768 项：1767 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1883.314 秒，exit 0；原始输出见同标签 stdout/stderr，源码前后指纹见 JSON。 |

W02 同条件比较：[旧 HEAD 与 W03 工作版逐站耗时](w02-paired-diagnostic-01.json)，原始输出见 `w02-paired-old-01.stdout.log`、`w02-paired-new-01.stdout.log` 及各自 `.stderr.log`。两版同在 `associative_recall_service._prepare` 超过原 1000ms 预算；该诊断进程本身退出 0 只代表成功保存观察记录，内部受测用例结果为 ERROR，绝不能当作通过。

修前、辅助、中断、PASS、ERROR 和既有 Windows 1314 SKIP 分开统计。未获远端 CI 结果，不写 CI PASS。
