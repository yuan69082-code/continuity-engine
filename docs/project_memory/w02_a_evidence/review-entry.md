# W02-A 独立复核入口

本批是输入理解与逐站处置记录，不是完整 W02，也不是 P19 开工。施工与测试状态以 [最终结果索引](selected-runs.json)、[续接记录](continuation.md) 和运行 JSON 为准；没有完整结果的运行不能计为通过。

## 先看哪些内容

1. [开工范围](stage-brief.md) 与 [用户已确认的逐文件边界](../w01_planning_v15_20260923/w02-a-proposed-brief.md)。
2. [实现和恢复说明](architecture-and-recovery.md)、[十二项验证矩阵](matrix.md)。
3. [首次失败和修补过程](failure-history.md)。旧失败、辅助错误和历史 UNKNOWN 不因当前通过被删除。
4. `selected-runs.json` 指向最终专项、兼容、全量；对应 `.json` 有命令、身份、退出码、前后源码、墙钟时长；`.stderr.log` 有 unittest 计数/用时；`.stdout.log` 保存进程 Golden 和清理记录。
5. 终局生成的 `final-report.md`、`final.audit.json`、`final.pending-files.md` 和 `final.inventory.json` 用于交付核对，不是提交授权。

## 可实际复跑的命令

从 Engine 根运行。只使用独立 TEST Fixture，Python 不写字节码。已有日志标签不可覆盖，复核者应使用新标签。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'
& 'E:/Adobe/python.exe' docs/project_memory/w02_a_evidence/run.py review-w02-01 tests.test_w02_input_processing tests.test_w02_input_recovery tests.test_w02_input_integration

# 原 P17/P18 测试有裸模块导入；统一 runner 同时保留根、src、tests 的导入上下文。
$w02Modules=(Get-Content docs/project_memory/w02_a_evidence/compatibility-plan.json -Raw | ConvertFrom-Json).modules
& 'E:/Adobe/python.exe' docs/project_memory/w02_a_evidence/run.py review-compatibility-01 @w02Modules

# 无模块参数时 discover 全部正式测试；只在独立复核需要时执行，不隐式重复。
& 'E:/Adobe/python.exe' docs/project_memory/w02_a_evidence/run.py review-full-01
```

原直接 `unittest` 专项命令仍可运行：

```powershell
& 'E:/Adobe/python.exe' -B -m unittest tests.test_w02_input_processing tests.test_w02_input_recovery tests.test_w02_input_integration -q
```

## 用户现在可以检查的内容

- 一条“我想吃苹果，但还没有吃”的真实输入进入本轮 Context/Thinking；结构解释保留愿望和否定，不宣称已经吃过。
- 会话暂用和“已记住”分开；只有原 Event/Memory 的合法匹配才返回记忆引用，缺证据如实显示待证据。
- 某站失败时看得到静态理由；重开同一测试数据根后接回原请求，而不是另造请求绕过失败。
- 两个真实进程的 Golden 中，第一个进程完成一次 Fake 效果后中断，第二个恢复原事实，模型/效果/费用不重复。专项 stdout 保存实际输出。
- `input_outcome(request_id)` 返回只读结构、原因和原结果身份，返回前检查当前权限；没有新页面，也不自动写长期人格或关系。

正常接线在 `build_continuity_core` 中通过 `ContinuityCoreGates(input_processing=True)` 启用，开关默认关闭以保持旧路径。现阶段只在受控 TEST/Research 根验证；本轮不操作正式主体。

## 明确剩余范围

W02-B 的回答前自动回忆、W02-C 的外部资料完整可信吸收和 W02 包级贯通尚未施工；W03 认识/事项、W04 实验、W05 联动、W06 整合与 P19 页面不由本批代替。没有真实服务、生产 exactly-once、实验转正或正式恢复能力承诺。

独立复核应重点看新增源绑定和逐站结果是否真实，旧路径及主体自主性是否保持；不得将工程上的复核审批变成主体日常内部行为逐条审批。
