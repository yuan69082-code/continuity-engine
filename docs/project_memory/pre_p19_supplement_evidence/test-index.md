<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# 命令与运行历史

所有标签唯一，原始stdout/stderr与JSON并存；旧记录不覆盖。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'
& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-new-01 test_pre_p19_
& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-independent-new-01 --review-class test_independent_boundaries.IndependentBoundaries
& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-compatibility-new-01 test_p09 test_p13 test_p14 test_p15 test_p17 test_p18 test_action test_permissions test_resources test_learning
& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-full-new-01
```

全量不传测试前缀。复核须使用尚未占用标签，配置PYTHONPATH以供现有子进程继承；runner对独立探针仅隔离观察输出路径，不改代码/断言。

| 记录 | 状态/数量 | 秒 | 退出码 | 原始输出 |
|---|---|---:|---:|---|
| [combined-01](combined-01.json) | FINISHED: 61 / 61PASS / 0SKIP / 0FAIL / 0ERROR | 125.598 | 0 | [stdout](combined-01.stdout.log) / [stderr](combined-01.stderr.log) |
| [combined-02](combined-02.json) | FINISHED: 63 / 63PASS / 0SKIP / 0FAIL / 0ERROR | 126.864 | 0 | [stdout](combined-02.stdout.log) / [stderr](combined-02.stderr.log) |
| [compatibility-01](compatibility-01.json) | FINISHED: 538 / 538PASS / 0SKIP / 0FAIL / 0ERROR | 1152.693 | 0 | [stdout](compatibility-01.stdout.log) / [stderr](compatibility-01.stderr.log) |
| [expression-order-before-01](expression-order-before-01.json) | FINISHED: 1 / 0PASS / 0SKIP / 1FAIL / 0ERROR | 1.465 | 1 | [stdout](expression-order-before-01.stdout.log) / [stderr](expression-order-before-01.stderr.log) |
| [formal-01](formal-01.json) | FINISHED: 23 / 22PASS / 0SKIP / 1FAIL / 0ERROR | 28.280 | 1 | [stdout](formal-01.stdout.log) / [stderr](formal-01.stderr.log) |
| [formal-02](formal-02.json) | FINISHED: 23 / 23PASS / 0SKIP / 0FAIL / 0ERROR | 30.523 | 0 | [stdout](formal-02.stdout.log) / [stderr](formal-02.stderr.log) |
| [full-final-01](full-final-01.json) | FINISHED: 1580 / 1579PASS / 1SKIP / 0FAIL / 0ERROR | 1687.548 | 0 | [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |
| [independent-after-01](independent-after-01.json) | FINISHED: 8 / 8PASS / 0SKIP / 0FAIL / 0ERROR | 6.924 | 0 | [stdout](independent-after-01.stdout.log) / [stderr](independent-after-01.stderr.log) |
| [independent-before-01](independent-before-01.json) | FINISHED: 8 / 4PASS / 0SKIP / 4FAIL / 0ERROR | 6.803 | 1 | [stdout](independent-before-01.stdout.log) / [stderr](independent-before-01.stderr.log) |
| [independent-final-01](independent-final-01.json) | FINISHED: 8 / 8PASS / 0SKIP / 0FAIL / 0ERROR | 7.349 | 0 | [stdout](independent-final-01.stdout.log) / [stderr](independent-final-01.stderr.log) |
| [query-route-before-01](query-route-before-01.json) | FINISHED: 1 / 0PASS / 0SKIP / 1FAIL / 0ERROR | 1.538 | 1 | [stdout](query-route-before-01.stdout.log) / [stderr](query-route-before-01.stderr.log) |
| [recovery-before-01](recovery-before-01.json) | FINISHED: 1 / 0PASS / 0SKIP / 1FAIL / 0ERROR | 2.196 | 1 | [stdout](recovery-before-01.stdout.log) / [stderr](recovery-before-01.stderr.log) |

最终选择及身份匹配见[selected-runs.json](selected-runs.json)；中间版本PASS不等于最终版本覆盖。
