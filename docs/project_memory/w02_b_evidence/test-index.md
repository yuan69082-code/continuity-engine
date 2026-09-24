# W02-B 实跑证据与复跑入口

本表全部是本批施工方实跑，非规划窗口独立实跑、用户验收或远端CI。集合交叠不相加。最终版本290份源码/测试/资源：`sha256:c3e9649dbf8590a202e5fc82de79bdc6f641fbb41bd4355efd912eaa62c62aed`。原1646身份及旧测试文件逐字节保留，新增57，最终发现与执行数量见表。

| 集合 | 完整运行记录 | 实际结果（runner壁钟） |
|---|---|---|
| W02-B新增正式专项 | [w02-b-final-04](w02-b-final-04.json) | 57项：57 PASS、0 SKIP、0 FAIL、0 ERROR；退出码0，164.630秒 |
| W02-A兼容 | [w02-a-compatibility-04](w02-a-compatibility-04.json) | 66项：66 PASS、0 SKIP、0 FAIL、0 ERROR；退出码0，91.768秒 |
| 实际受影响公共兼容 | [affected-compatibility-04](affected-compatibility-04.json) | 509项：509 PASS、0 SKIP、0 FAIL、0 ERROR；退出码0，644.300秒 |
| 最终完整回归 | [full-final-04](full-final-04.json) | 1703项：1702 PASS、1 SKIP、0 FAIL、0 ERROR；退出码0，3191.570秒 |

每个JSON均含实际命令、测试身份、成功/失败/错误/跳过身份、退出码、开始/结束时间及前后逐文件hash。同标签 `.stdout.log` / `.stderr.log` 是原始输出，不能用日志片段代替完整结果。既有SKIP：[["test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes", "OS does not grant symlink creation: 1314"]]。

## 可直接复跑

在Engine根目录设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=C:/Users/Administrator/Documents/continuity-engine/src`，使用 `E:/Adobe/python.exe`：

```powershell
& 'E:/Adobe/python.exe' -m unittest tests.test_w02_recall tests.test_w02_recall_boundaries tests.test_w02_recall_combinations tests.test_w02_recall_consistency tests.test_w02_recall_semantics -v
& 'E:/Adobe/python.exe' -m unittest discover -s tests -q
```

需要保留完整机器证据时使用本目录 `run.py <未占用标签> [测试模块...]`；标签不得覆盖，缺省模块执行全量，绝不会自动重试。A及受影响兼容的**准确完整参数**保存在对应JSON的command，勿把不同集合的通过数相加。三阶段跨进程TEST演示与只读查看见[实现说明](implementation-notes.md)。

## 引用与历史

修改前W02-A最终1646项=1645PASS/1既有1314SKIP仅为核验引用，未重跑修改前全量。本批前版测试、诊断及真实失败见[测试历史](test-history.md)，只能证明当时版本。当前四组逐文件身份均绑定同一冻结版本；本次没有远端CI结果，不声明CI PASS。
