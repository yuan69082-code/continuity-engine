# 独立复核入口

从 Engine 根目录运行，隔离 TEST/Fake，禁止操作正式数据；每次新证据标签必须未占用。run.py 不重试、不覆盖标签，保存命令、stdout/stderr、退出码、准确PASS/SKIP、源码前后清单。独立复核不是用户验收。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH="$PWD/src"
& E:/Adobe/python.exe -B docs/project_memory/w02_a_evidence/repair_r1_r2/run.py review-r1-r2-01 tests.test_w02_input_recovery.PartialInputQueryTests tests.test_w02_input_processing.InputLanguageRepairTests
& E:/Adobe/python.exe -B docs/project_memory/w02_a_evidence/repair_r1_r2/run.py review-w02-01 tests.test_w02_input_processing tests.test_w02_input_recovery tests.test_w02_input_integration
```

兼容精确模块列表及原命令见 [compatibility-scope-02.json](compatibility-scope-02.json)。完整回归：上述 runner 后仅传一个未占用标签（例如 review-full-01），不传测试名即 discover tests。不要并发跑这些集合，不因重复运行而覆盖首次失败。

R1通过正式 f.app.adapter.service.input_outcome 查询。局部失败注入发生在正常 C1，覆盖本进程、reopen和真实新进程；查询前后比全树hash及模型/效果/费用；明确重提原请求才恢复。R2通过正常入站直达Provider的Context，检查原文、解释、候选权威和各站处置，原有正向测试断言未改。

[报告](final-report.md) · [矩阵](matrix.md) · [源码身份](frozen-source-02.json) · [首次失败](reproduction-before-01.json) · [最终清单](final.pending-files.md)。
