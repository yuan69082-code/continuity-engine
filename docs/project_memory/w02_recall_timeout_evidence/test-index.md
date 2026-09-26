# W02 超时补修：原始运行索引

全部本轮测试通过 `E:/Adobe/python.exe docs/project_memory/w02_recall_timeout_evidence/run.py <唯一标签> <实际命令>` 在仓库根执行。`run.py` 为每次保留独立的 `.json`、`.stdout.log`、`.stderr.log`，记录起止时间、退出码、耗时、前后源码指纹及原始输出 SHA-256；不覆盖旧标签。运行期间环境仅设 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1` 和仓库 `src`/根导入路径，测试数据均在隔离 TEST Temp 根。

| 标签 | 实际执行内容 | 结果与口径 |
|---|---|---|
| [third-prefx-01](third-prefx-01.json) | 原 `tests.test_w02_integration.W02IntegratedChainTests.test_partial_derived_withdrawal_invalidates_integrated_reply_and_support -q` | 1 PASS，17.124 s runner；这是当前修前第三轮一次，不替代历史两次超时 |
| [four-prefx-02](four-prefx-02.json) | `measure.py four`，经四次正常原始消息提交 | 第四次 `RECALL_TIMEOUT`，1203.258 ms；退出 1；[stdout](four-prefx-02.stdout.log) |
| [four-measure-prefx-03](four-measure-prefx-03.json)、[04](four-measure-prefx-04.json) | `measure.py four instrument` | 两次修前带仪器超时；分站原始值[03](four-measure-prefx-03.stdout.log)、[04](four-measure-prefx-04.stdout.log)；仪器开销不当成业务限时 |
| [four-measure-draft-01](four-measure-draft-01.json)、[third-measure-draft-01](third-measure-draft-01.json) | 同一分站测量脚本、修后代码 | 四份 607.236 ms / 第三轮 669.606 ms；原始分站[四份](four-measure-draft-01.stdout.log)、[第三轮](third-measure-draft-01.stdout.log) |
| [four-postfix-01](four-postfix-01.json)、[02](four-postfix-02.json)、[03](four-postfix-03.json) | `measure.py four`，预定三次无仪器独立根 | 626.903 / 624.307 / 614.196 ms，三次成功，源码指纹均同一固定版 |
| [third-postfix-01](third-postfix-01.json)、[02](third-postfix-02.json)、[03](third-postfix-03.json) | `measure.py third`，预定三次无仪器独立根 | 682.117 / 665.591 / 700.247 ms，三次成功，16 项检索 |
| [formal-final-01](formal-final-01.json) | `-m unittest tests.test_w02_recall_timeout -q` | 5 PASS，38.766 s，退出 0；[stderr](formal-final-01.stderr.log) |
| [w02-special-01](w02-special-01.json) | `-m unittest discover -s tests -p test_w02_*.py -q` | 161 PASS，282.900 s，退出 0；[stderr](w02-special-01.stderr.log) |
| [w03-compat-01](w03-compat-01.json) | `-m unittest tests.test_w03_unfinished_items tests.test_w03_recognition tests.test_w03_n06_repair tests.test_w03_core_context -q` | 32 PASS，133.492 s，退出 0；[stderr](w03-compat-01.stderr.log) |
| [public-compat-01](public-compat-01.json) | P05/P06/P16 九个明确测试模块，完整数组见 JSON | 155 PASS，107.880 s，退出 0；[stderr](public-compat-01.stderr.log) |
| [full-final-01](full-final-01.json) | `-m unittest discover -s tests -q` | 1773 项：1772 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR；测试耗时 1792.823 s、runner 1793.826 s、退出 0；[原始 stderr](full-final-01.stderr.log)。运行前后 305 份源码/测试/资源同为 `sha256:1008aabea9c72f769b97886cd9017051da083a95d14f9d9a010d7a738daa297b`。 |

修前/辅助输出 `four-prefx-01`、`third-measure-prefx-01/02`、`formal-draft-01/02/03`、`formal-security-draft-01/02/03` 原样保留。`formal-draft-01` 是 Windows Temp 路径过长的测试辅助错误；`formal-draft-02` 和 `formal-security-draft-01/02` 的具体断言差异见[交付报告](report.md)。没有静默重试，正式测试未删旧断言或调大时限。

旧证据仅作历史引用：[四份首次失败](../w02_integration_evidence/integration-draft-01.json)、[W03 同条件配对](../w03_n06_repair_evidence/w02-paired-diagnostic-01.json)；它们不是本轮实跑。所有集合相互交叠，不相加；没有远端 CI PASS 证据。
