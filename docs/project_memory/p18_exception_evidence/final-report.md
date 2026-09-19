# P18 连续异常原因保留：返修交付

## 2026-09-19 续接终局说明

本次软件/额度中断续接只核验既有结果，未修改运行源码或测试、未启动测试。原全量已有完整FINISHED/exit 0和stdout/stderr汇总；六组所选结果前后270份源码与当前冻结逐文件一致，原1507身份及断言完整、新增10项。故引用2026-09-14实际完成结果，不重复全量，不冒称本次重跑。

现场初查与上一 final.audit.json 的711项P18成果、32排除项完全一致，无新增/缺失或字节漂移。实际重新核对63保护项、3规划、正式七文件、版本、排除项与原件/归档副本；未发现差异。当前无匹配Engine/P18 Python测试进程，新增Fixture前缀残留0，没有强制清理或恢复旧session。

本次只追加续接说明、核验记录和新审计/清单，并让证据审计工具可指定本次进程观察文件。原审计及原日志保留。当前交付使用[续接核验](resume-verification-20260919.json)、[最终精确清单](final.pending-files-resume-20260919.md)与[最终审计](final.audit-resume-20260919.json)。旧 final.pending-files.md/final.audit.json 为2026-09-14历史快照，新增续接档案导致现行数量变化，以新清单为准。

P18保持IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT。异常链补修交回独立复核，历史F1/H1/F2仍UNKNOWN；不登记D-073、不验收、不Git写、不P19。

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT；D-073未创建/未使用。

本轮新增正式10项，原1507项身份和断言保留。P18 157 PASS；公共兼容 605 PASS；最终全量 1517项：1516 PASS、1既有Windows 1314 SKIP、0 FAIL/ERROR，运行记录耗时1384.364秒，exit 0。各组有交集，不重复相加。

## 修改与责任边界

本轮只修改两个既有运行文件的清理错误处理：`src/continuity_engine/storage/json_repository.py`、`src/continuity_engine/storage/json_runtime_repository.py`。新增 `tests/test_p18_storage_exceptions.py`，其余运行文件及原正式测试字节未变。

旧代码在cleanup处理器内重新抛出primary，覆盖隐式context，只保留显式cause。现在由共享内部helper保留pending主异常自然传播，保留显式cause和隐式context分支，追加清理错误及其自身原因；移除自动回指，共享原因在上方接续，避免新循环。顶层授权拒绝、版本冲突、deferred、原生错误对象/类型与错误码仍保留。正常traceback格式化、原生errno/winerror/文件绑定都有正式回归。

没有更改有限重试资格、次数/期限、当前授权、字节/版本/事务检查、原生替换、PAUSE/STOP、Provider、派发、扣费、revision或事实恢复。没有修改其他运行模块，不改变ACL或只读属性。内部异常链新增完整原因，不自动向既有脱敏对外接口打印任意原文；公共兼容覆盖原P16及Runtime诊断边界。

## 修前、修后及历史证据

- 本轮原样实跑：[independent-before-01](independent-before-01.json)，6项4PASS、2FAIL；[stderr](independent-before-01.stderr.log)、[stdout](independent-before-01.stdout.log)保留。失败确认同一个异常证据缺口，目标未变、替换1次、顶层拒绝生效，不描述成数据损坏/重复执行/停机。
- 修后首次六项6PASS记录 [independent-after-01](independent-after-01.json)。该次尚未加入新测试文件，属于中间源码清单；最终源码身份下另有 independent-final-01 6PASS。
- 新正式10项首次 formal-after-01 10PASS，其源码与最终冻结一致，直接纳入最终证据，没有机械重复。
- 原147专项PASS及35旧独立组合PASS是规划侧上轮实跑；原1507全量1506PASS/1SKIP是上一施工版本。详见[只读原件副本](independent/review-report.md)，本轮不冒称重新运行这些旧标签。
- 本轮所有原件与副本SHA256在[开工清单](before.json)；既有失败、辅助错误、原始输出和缺失证据均未覆盖。
- 默认沙箱CIM只读查询被拒，获准提升后查询成功；内部审阅rg通配路径辅助错误123已记录并修正读取。见[工具观察](tool-observation.json)，不是Engine行为失败。

## 最终实跑

记录秒数含测试发现和运行；unittest秒数来自stderr原文。各组交叉包含，不能相加成总测试数。

| 组 | PASS | SKIP | FAIL/ERROR | 记录秒数 | unittest秒数 | 原始输出 |
|---|---:|---:|---|---:|---:|---|
| [independent-final-01](independent-final-01.json) | 6 | 0 | 0/0 | 1.179 | 0.731 | [stdout](independent-final-01.stdout.log) / [stderr](independent-final-01.stderr.log) |
| [formal-after-01](formal-after-01.json) | 10 | 0 | 0/0 | 2.006 | 1.205 | [stdout](formal-after-01.stdout.log) / [stderr](formal-after-01.stderr.log) |
| [storage-compatibility-final-01](storage-compatibility-final-01.json) | 41 | 0 | 0/0 | 35.762 | 34.901 | [stdout](storage-compatibility-final-01.stdout.log) / [stderr](storage-compatibility-final-01.stderr.log) |
| [p18-final-01](p18-final-01.json) | 157 | 0 | 0/0 | 222.246 | 221.418 | [stdout](p18-final-01.stdout.log) / [stderr](p18-final-01.stderr.log) |
| [compatibility-final-01](compatibility-final-01.json) | 605 | 0 | 0/0 | 927.813 | 926.956 | [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) |
| [full-final-01](full-final-01.json) | 1516 | 1 | 0/0 | 1384.364 | 1383.481 | [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |

源码/测试/资源270份，最终身份 `sha256:e56fcd1d6e2f6d467a708b72866c807eca536fece20af9e881d2a23aba30cfec`；上述组执行前后均匹配[冻结清单](frozen-source.json)。原测试身份完整保留，新增10项单列。

## 原始目标与持续运行语义核对

本轮未改变运行寿命或持续运行入口，不新增无聊天、固定轮数、固定时长或概率停机条件。当前完整P18专项实测包含：无新消息推进、空闲/沉默保活、资源局部等待、耗尽存档尝试后宿主控制响应、释放后复用原事实、局部等待不阻塞独立维护、无重复执行/扣费、PAUSE/STOP与主体生命周期、单宿主及R1/R2恢复。

公共模块仅异常证据链可观察结构补全；原顶层拒绝及执行政策无变化，605项受影响兼容和最终全量提供当前版本证据，不承诺任意未知组合无缺陷。未验证生产部署、实际外部Adapter或任意磁盘故障下控制一定可持久化；生产能力原NOT_READY边界不变。

## 历史F1/H1/F2与待复核项

F1缺历史ThinkSession阶段和完整原生错误链；H1缺清理前活动、水位及系统码；F2缺原始系统错误码/读句柄证据。当前读句柄机制的旧修补和本次原因保留通过，不足以唯一归因上述历史现场，三项仍按UNKNOWN保留，不合并结案、不自行清除EVIDENCE_CONFLICT。P09 segment 10的stderr缺失/UNKNOWN也未改变。

本次局部修补已实现，等待规划监工独立复核。没有用户验收登记、D-073、Git写、Assistant改动或P19；没有访问远端或取得新CI，不宣称CI PASS。

## 复跑与核查入口

用未占用的新标签，避免覆盖原证据；完整全量运行无需重复其他组。测试使用隔离TEST根，全部原始输出保留。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-six-01 --review-class test_independent_storage_final.IndependentStorageFinal
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-formal-01 test_p18_storage_exceptions
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-p18-01 test_p18_
# 仅需要独立全量时：
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-full-01
```

受影响兼容的精确选择及原命令在 compatibility-final-01.json。全部测试历史见[test-history.json](test-history.json)，精确当前成果/32排除项见[final.pending-files.md](final.pending-files.md)，保护、链接、敏感内容、格式提示、源码及Git状态见[final.audit.json](final.audit.json)。审计保留历史原始日志格式告警，不为消除告警改写旧日志；敏感扫描仅有限key特征，不冒称穷尽秘密检测。

正式七文件树指纹应由最终审计实测为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`；63保护项、3规划、版本0.1.0、32排除材料均按开工逐文件hash核验。进程实际观察及测试清理记录单列于审计，不把只读查询失败伪报为零进程。
