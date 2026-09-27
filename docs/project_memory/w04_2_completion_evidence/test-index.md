# 同版测试索引

全部为施工方本轮实跑；集合交叠，不相加。规划窗口未运行这些测试，无远端CI结论。正常正式测试没有cProfile或前轮计时包装；原重度插桩超时保留，未增加“所有插桩也必须1秒内”的验收要求。

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-01](targeted-final-01.json) | 32 / 0 / 0 / 0 | 118.793 / 119.595 | 0 |
| [recall-formal-final-01](recall-formal-final-01.json) | 5 / 0 / 0 / 0 | 56.436 / 57.056 | 0 |
| [recall-load-final-01](recall-load-final-01.json) | 2 / 0 / 0 / 0 | 32.868 / 33.394 | 0 |
| [special-final-01](special-final-01.json) | 87 / 0 / 0 / 0 | 173.939 / 174.726 | 0 |
| [compatibility-final-01](compatibility-final-01.json) | 417 / 0 / 0 / 0 | 692.998 / 693.718 | 0 |
| [full-final-01](full-final-01.json) | 1862 / 0 / 0 / 1 | 2012.898 / 2013.912 | 0 |

- [targeted-final-01 stdout](targeted-final-01.stdout.log) / [stderr](targeted-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

- [recall-formal-final-01 stdout](recall-formal-final-01.stdout.log) / [stderr](recall-formal-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

- [recall-load-final-01 stdout](recall-load-final-01.stdout.log) / [stderr](recall-load-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

- [special-final-01 stdout](special-final-01.stdout.log) / [stderr](special-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

- [compatibility-final-01 stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

- [full-final-01 stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log)；命令、时间、退出码及前后完整源码见对应JSON。

## 修前与中间记录（不可代替最终版）

- history-before-01：1 ERROR，新增夹具长路径导致setUp临时文件失败，尚未到目标反例。
- history-before-02：1 ERROR，新增测试误用不合法斜线身份，被原契约正确拒绝。
- history-before-03：1个测试、2个子断言ERROR；同一回执正序/反序都被裁掉，真实修前证据，不能写成负PASS。
- targeted-after-01：30项，26 PASS/4 ERROR；四个新增拒绝断言的异常类型错误，实际原消费边界正确返回DEVICE_SOURCE_NOT_CURRENT。随后新测试改为核对确切类型和静态码，产品拒绝未改。
- targeted-after-02：31 PASS；最终优先级改为保留其他候选原评分并新增对应回归，因此此组仅为中间证据。
- 前轮锁受控1FAIL/1ERROR、cProfile修后1PASS/1ERROR、专项业务错误与导入错误均保留在 ../w04_2_public_repair_evidence/；未倒改。

复跑命令：使用各JSON的command，在仓库根设置PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1、PYTHONPATH为根/src/tests。证据runner仅接受未占用标签；不要直接重用已完成标签或validate_fixed.py覆盖记录。全量命令为 E:/Adobe/python.exe -m unittest discover -s tests -v。
