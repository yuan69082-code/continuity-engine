<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# 本轮真实测试索引

下列均为本轮施工实跑，独立原件只作为审查来源；不冒称规划监工已复核修后实现。各集合相互重叠，不相加。
FAIL/ERROR列统计原始失败记录；存在subTest时记录数可能超过失败测试用例数。R2修前3个失败用例包含8条子用例失败。
耗时为run.py实际记录墙钟时间（含加载发现），详细命令、测试身份、时间、源码前后hash及退出码均在对应JSON。

| 标签/原始输出 | run | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | exit | 当前源码 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| [combined-01](combined-01.json) / [stdout](combined-01.stdout.log) / [stderr](combined-01.stderr.log) | 24 | 23 | 0 | 1 | 0 | 62.211 | 1 | 历史中间版本 |
| [combined-02](combined-02.json) / [stdout](combined-02.stdout.log) / [stderr](combined-02.stderr.log) | 28 | 28 | 0 | 0 | 0 | 78.61 | 0 | 历史中间版本 |
| [combined-03](combined-03.json) / [stdout](combined-03.stdout.log) / [stderr](combined-03.stderr.log) | 33 | 33 | 0 | 0 | 0 | 103.439 | 0 | 历史中间版本 |
| [combined-04](combined-04.json) / [stdout](combined-04.stdout.log) / [stderr](combined-04.stderr.log) | 34 | 34 | 0 | 0 | 0 | 103.701 | 0 | 一致 |
| [compatibility-01](compatibility-01.json) / [stdout](compatibility-01.stdout.log) / [stderr](compatibility-01.stderr.log) | 749 | 747 | 1 | 0 | 1 | 1020.05 | 1 | 历史中间版本 |
| [compatibility-final-01](compatibility-final-01.json) / [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) | 342 | 342 | 0 | 0 | 0 | 753.744 | 0 | 历史中间版本 |
| [compatibility-final-02](compatibility-final-02.json) / [stdout](compatibility-final-02.stdout.log) / [stderr](compatibility-final-02.stderr.log) | 175 | 175 | 0 | 0 | 0 | 196.425 | 0 | 一致 |
| [full-final-01](full-final-01.json) / [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) | 1550 | 1548 | 1 | 0 | 1 | 1718.557 | 1 | 历史中间版本 |
| [full-final-02](full-final-02.json) / [stdout](full-final-02.stdout.log) / [stderr](full-final-02.stderr.log) | 1551 | 1550 | 0 | 0 | 1 | 1765.117 | 0 | 一致 |
| [platform-after-01](platform-after-01.json) / [stdout](platform-after-01.stdout.log) / [stderr](platform-after-01.stderr.log) | 1 | 0 | 0 | 1 | 0 | 1.081 | 1 | 历史中间版本 |
| [platform-after-02](platform-after-02.json) / [stdout](platform-after-02.stdout.log) / [stderr](platform-after-02.stderr.log) | 1 | 1 | 0 | 0 | 0 | 1.591 | 0 | 一致 |
| [platform-before-01](platform-before-01.json) / [stdout](platform-before-01.stdout.log) / [stderr](platform-before-01.stderr.log) | 1 | 0 | 0 | 1 | 0 | 1.26 | 1 | 历史中间版本 |
| [platform-legacy-after-01](platform-legacy-after-01.json) / [stdout](platform-legacy-after-01.stdout.log) / [stderr](platform-legacy-after-01.stderr.log) | 1 | 1 | 0 | 0 | 0 | 1.33 | 0 | 一致 |
| [queue-before-01](queue-before-01.json) / [stdout](queue-before-01.stdout.log) / [stderr](queue-before-01.stderr.log) | 1 | 0 | 1 | 0 | 0 | 4.83 | 1 | 历史中间版本 |
| [r1-after-01](r1-after-01.json) / [stdout](r1-after-01.stdout.log) / [stderr](r1-after-01.stderr.log) | 7 | 7 | 0 | 0 | 0 | 9.238 | 0 | 历史中间版本 |
| [r1-before-01](r1-before-01.json) / [stdout](r1-before-01.stdout.log) / [stderr](r1-before-01.stderr.log) | 7 | 1 | 6 | 0 | 0 | 8.138 | 1 | 历史中间版本 |
| [r2-after-01](r2-after-01.json) / [stdout](r2-after-01.stdout.log) / [stderr](r2-after-01.stderr.log) | 17 | 17 | 0 | 0 | 0 | 1.098 | 0 | 历史中间版本 |
| [r2-before-01](r2-before-01.json) / [stdout](r2-before-01.stdout.log) / [stderr](r2-before-01.stderr.log) | 3 | 0 | 8 | 0 | 0 | 1.015 | 1 | 历史中间版本 |
| [r3-after-01](r3-after-01.json) / [stdout](r3-after-01.stdout.log) / [stderr](r3-after-01.stderr.log) | 12 | 12 | 0 | 0 | 0 | 39.552 | 0 | 历史中间版本 |
| [r3-before-01](r3-before-01.json) / [stdout](r3-before-01.stdout.log) / [stderr](r3-before-01.stderr.log) | 5 | 1 | 4 | 0 | 0 | 29.003 | 1 | 历史中间版本 |
| [r4-after-01](r4-after-01.json) / [stdout](r4-after-01.stdout.log) / [stderr](r4-after-01.stderr.log) | 5 | 4 | 0 | 1 | 0 | 9.174 | 1 | 历史中间版本 |
| [r4-before-01](r4-before-01.json) / [stdout](r4-before-01.stdout.log) / [stderr](r4-before-01.stderr.log) | 5 | 2 | 3 | 0 | 0 | 6.698 | 1 | 历史中间版本 |
| [retention-before-01](retention-before-01.json) / [stdout](retention-before-01.stdout.log) / [stderr](retention-before-01.stderr.log) | 1 | 0 | 1 | 0 | 0 | 5.73 | 1 | 历史中间版本 |
| [runtime-extended-01](runtime-extended-01.json) / [stdout](runtime-extended-01.stdout.log) / [stderr](runtime-extended-01.stderr.log) | 8 | 6 | 2 | 0 | 0 | 38.236 | 1 | 历史中间版本 |
| [runtime-extended-02](runtime-extended-02.json) / [stdout](runtime-extended-02.stdout.log) / [stderr](runtime-extended-02.stderr.log) | 8 | 8 | 0 | 0 | 0 | 20.097 | 0 | 历史中间版本 |
| [unknown-compatibility-01](unknown-compatibility-01.json) / [stdout](unknown-compatibility-01.stdout.log) / [stderr](unknown-compatibility-01.stderr.log) | 1 | 1 | 0 | 0 | 0 | 3.986 | 0 | 历史中间版本 |

独立诊断（不按unittest计数）：[修前](independent-before-01.json)、[修后最终](independent-after-02.json)。旧原件及副本hash在[archives.json](archives.json)。

compatibility-01覆盖较广但属中间版本，749项=747PASS/1SKIP/1FAIL；其唯一FAIL及之后两处初稿遗漏见实现记录。最终兼容与完整回归均绑定最终源码。

首次FAIL/ERROR、辅助设置错误与本轮引入遗漏的分类见[实现记录](implementation-notes.md)、[辅助记录](auxiliary-errors.md)。历史P18 F1/H1/F2仍UNKNOWN，不以新通过倒推根因。

## 可复跑命令

从Engine根运行；标签必须尚未占用。runner拒绝覆盖原日志。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/probe.py review-diagnostic-01
& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-targeted-01 test_pre_p19_autonomy
& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-compatibility-01 test_p14 test_p15 test_p18 test_pre_p19 test_action
& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-full-01
```

## 补充正常逐步推进（源码未变，单列场景）

[progressive-02](progressive-02.json)及[stdout](progressive-02.stdout.log)/[stderr](progressive-02.stderr.log)：15轮，每轮6逻辑小时加60秒调度推进，总90小时15分的逻辑跨度；默认need_delta=0.02未改变，TEST时钟跃进容许量明确设86400秒。第7—15轮数值变化低于该门槛仍实际调用并提交，15次Provider调用对应15次revision推进，token_used=4800，世界效果/执行/credits均0；显式STOP，成功Fixture已清理。99.468秒、exit0，前后源码与最终全量一致。不是90小时真实持续负载测试，不计入Engine正式1551项。

[progressive-01](progressive-01.json)及[stderr](progressive-01.stderr.log)保留辅助AttributeError：观察脚本误用host.status()（正确API为query()），诊断和STOP后读取也触发同类错误，未得到完整观察数据；STOP调用位于错误读取前。保留失败根与日志，未修改引擎。修正观察脚本后使用新标签，仅补该场景，未重跑全量。
