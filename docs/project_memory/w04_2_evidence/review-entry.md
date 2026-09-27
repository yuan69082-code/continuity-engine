# W04-2 独立复核入口

本批是模拟设备、模拟身体和局部历史模拟查询闭环。W04-1/D-087 与历史验收不重开；下一步只能独立复核及用户决定，不自行推进 W04-3。

先看 [Stage Brief](stage-brief.md)、[矩阵](matrix.md)、[实现与兼容说明](implementation-notes.md)、[首次失败](failure-history.md)、[固定源码](frozen-source.json) 和 [排除清单](excluded-files.md)。当前公共兼容失败、全量未启动；先看[阻断说明](conflict-report.md)、[交付报告](final-report.md)及[真实测试索引](test-index.md)。不得把本批当作全部验证通过。

## 复跑命令

在 Engine 根目录运行，使用已有本地 Python 和独立 TEST 根；不需要网络、密钥或真实设备。每个证据标签必须未使用，不能覆盖原输出。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src;C:/Users/Administrator/Documents/continuity-engine/tests'
& 'E:/Adobe/python.exe' 'docs/project_memory/w04_2_evidence/run.py' review-special-01 tests.test_w04_2_simulation tests.test_w04_1_environment
```

受影响兼容的完整真实命令保存于 `w04-2-compat-final-01.json`。完整回归使用同一 runner 的新标签加 `discover -s tests`。复核人员可按需要运行，不把本页命令本身当成实跑结果。

## 最小只读入口

- `DeviceOperationService.observe(use)`：当前授权观察，不推进主体或业务；缺范围、断线等拒绝。
- `DeviceOperationService.inspect(capability_request_id)`：读取原账本与独立回执，返回结果类别及前后观察；不会续跑原请求。
- `DeviceOperationService.history_context(request_id, perception)`：只读验证已有查询结果，经原 Router/Composer 提供带根与版本的候选；不触发新模型或新查询动作。
- `perceive_sensor(use, observation, original_context)`：原 Perception 入口，输出明确标为模拟硬件观察；是否形成内部变化仍走后续原Action/Evolution。

模拟控件和身体仅为隔离 TEST，不能据此宣称任意真实桌面可操作、真实语义理解或生产恢复已验证。历史F1/H1/F2仍UNKNOWN，1314 SKIP如实保留，无远端CI PASS证据。
