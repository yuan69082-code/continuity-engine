# 公共阻断续修测试与诊断索引

各集合有交集，不相加。所有结果为施工方实跑；规划窗口未在本轮运行这些测试。原始失败与辅助错误保留。最终全量未启动：P18原测试冲突及新W04-2组装错误需先获授权处理。

| 标签 | PASS/FAIL/ERROR/SKIP | exit | runner秒 | 源码前后相同 | 原始输出 |
|---|---|---|---|---|---|
| [compatibility-current-01](compatibility-current-01.json) | 414/0/0/0 | 0 | 639.304 | True | [stdout](compatibility-current-01.stdout.log) / [stderr](compatibility-current-01.stderr.log) |
| [history-diagnostic-01](history-diagnostic-01.json) | 1/0/0/0 | 0 | 6.451 | True | [stdout](history-diagnostic-01.stdout.log) / [stderr](history-diagnostic-01.stderr.log) |
| [history-pair-01](history-pair-01.json) | 诊断场景，非测试总数 | 1 | 9.483 | True | [stdout](history-pair-01.stdout.log) / [stderr](history-pair-01.stderr.log) |
| [locks-controlled-01](locks-controlled-01.json) | 0/1/1/0 | 1 | 9.903 | True | [stdout](locks-controlled-01.stdout.log) / [stderr](locks-controlled-01.stderr.log) |
| [locks-profile-01](locks-profile-01.json) | 2/0/0/0 | 0 | 7.65 | True | [stdout](locks-profile-01.stdout.log) / [stderr](locks-profile-01.stderr.log) |
| [recall-bounded-after-01](recall-bounded-after-01.json) | 4/0/0/0 | 0 | 56.535 | True | [stdout](recall-bounded-after-01.stdout.log) / [stderr](recall-bounded-after-01.stderr.log) |
| [recall-cpu-01](recall-cpu-01.json) | 0/0/2/0 | 1 | 18.32 | True | [stdout](recall-cpu-01.stdout.log) / [stderr](recall-cpu-01.stderr.log) |
| [recall-cpu-after-01](recall-cpu-after-01.json) | 1/0/1/0 | 1 | 25.727 | True | [stdout](recall-cpu-after-01.stdout.log) / [stderr](recall-cpu-after-01.stderr.log) |
| [recall-profile-01](recall-profile-01.json) | 0/0/5/0 | 1 | 0.6 | True | [stdout](recall-profile-01.stdout.log) / [stderr](recall-profile-01.stderr.log) |
| [recall-profile-02](recall-profile-02.json) | 5/0/0/0 | 0 | 59.859 | True | [stdout](recall-profile-02.stdout.log) / [stderr](recall-profile-02.stderr.log) |
| [recall-profile-after-01](recall-profile-after-01.json) | 5/0/0/0 | 0 | 48.021 | True | [stdout](recall-profile-after-01.stdout.log) / [stderr](recall-profile-after-01.stderr.log) |
| [registry-after-01](registry-after-01.json) | 7/0/0/0 | 0 | 3.408 | True | [stdout](registry-after-01.stdout.log) / [stderr](registry-after-01.stderr.log) |
| [registry-before-01](registry-before-01.json) | 5/2/0/0 | 1 | 4.25 | True | [stdout](registry-before-01.stdout.log) / [stderr](registry-before-01.stderr.log) |
| [registry-denial-before-02](registry-denial-before-02.json) | 1/0/0/0 | 0 | 0.988 | True | [stdout](registry-denial-before-02.stdout.log) / [stderr](registry-denial-before-02.stderr.log) |
| [special-final-01](special-final-01.json) | 48/0/2/0 | 1 | 80.38 | True | [stdout](special-final-01.stdout.log) / [stderr](special-final-01.stderr.log) |
| [w04-1-final-01](w04-1-final-01.json) | 29/0/0/0 | 0 | 13.802 | True | [stdout](w04-1-final-01.stdout.log) / [stderr](w04-1-final-01.stderr.log) |

特别口径：recall-profile-01是五个FailedTest导入错误，未执行业务；registry-before-01含一个重复元数据查询反例失败和一个未命中旧实现路径的辅助注入失败，后者在registry-denial-before-02修正注入位置后旧实现通过。special-final-01含49条正式测试（48 PASS/1 ERROR）和1条错误模块名造成的FailedTest，W04-1后用正确模块单独29/29通过，没有重跑49条抹掉错误。recall-cpu-01为cProfile插桩，开销会触发时限，不能冒充正式性能；locks-controlled-01为明示0.40秒持锁交错，不冒充历史现场耗时。

recall-profile-after-01与recall-bounded-after-01的运行文件等于现版本，但随后新增测试文件仅补非Windows兼容分支，集合指纹从fd7c10…变为当前1a0f35…；其计时为该次诊断引用，不冒充最终同版全量。special-final-01、w04-1-final-01、compatibility-current-01及两次新历史查询诊断绑定当前固定源码。

recall-cpu-after-01也绑定当前固定源码；1 PASS/1 ERROR，四份资料在cProfile下仍超时，不算全部通过。[同条件插桩对照及限制](cpu-comparison.md)。
