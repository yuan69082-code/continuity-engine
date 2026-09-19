# P18 R2 本轮测试历史

所有标签原样保留；表内相交集合不得相加为正式测试总数。实际命令和源码前后 hash 在各 JSON。

| 标签 | 原记录状态 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 | 退出码 | 对应最终源码 |
|---|---|---|---|---|---|---|---|---|
| [budget-control-before-01](budget-control-before-01.json) | FINISHED | 1 | 0 | 0 | 1/0 | 1.598 | 1 | False |
| [compatibility-final-01](compatibility-final-01.json) | FINISHED | 490 | 490 | 0 | 0/0 | 762.217 | 0 | True |
| [confirmation-after-01](confirmation-after-01.json) | FINISHED | 4 | 4 | 0 | 0/0 | 7.332 | 0 | False |
| [confirmation-before-01](confirmation-before-01.json) | FINISHED | 4 | 1 | 0 | 3/0 | 6.385 | 1 | False |
| [confirmation-final-01](confirmation-final-01.json) | FINISHED | 4 | 4 | 0 | 0/0 | 8.934 | 0 | False |
| [confirmation-final-02](confirmation-final-02.json) | FINISHED | 4 | 4 | 0 | 0/0 | 8.34 | 0 | True |
| [formal-after-01](formal-after-01.json) | FINISHED | 5 | 5 | 0 | 0/0 | 8.358 | 0 | False |
| [formal-before-01](formal-before-01.json) | FINISHED | 5 | 2 | 0 | 3/0 | 7.379 | 1 | False |
| [formal-complete-01](formal-complete-01.json) | FINISHED | 21 | 20 | 0 | 0/1 | 31.736 | 1 | False |
| [formal-expanded-01](formal-expanded-01.json) | FINISHED | 14 | 12 | 0 | 2/0 | 21.384 | 1 | False |
| [formal-expanded-02](formal-expanded-02.json) | FINISHED | 14 | 14 | 0 | 0/0 | 21.788 | 0 | False |
| [formal-final-01](formal-final-01.json) | FINISHED | 21 | 21 | 0 | 0/0 | 31.693 | 0 | False |
| [formal-final-02](formal-final-02.json) | FINISHED | 22 | 22 | 0 | 0/0 | 33.816 | 0 | False |
| [formal-final-03](formal-final-03.json) | FINISHED | 22 | 22 | 0 | 0/0 | 38.321 | 0 | True |
| [full-final-01](full-final-01.json) | STARTED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN（缺运行后清单） |
| [full-resume-01](full-resume-01.json) | FINISHED | 1466 | 1464 | 1 | 1/0 | 1376.33 | 1 | True |
| [p18-final-01](p18-final-01.json) | FINISHED | 106 | 106 | 0 | 0/0 | 191.42 | 0 | False |
| [p18-final-02](p18-final-02.json) | FINISHED | 106 | 106 | 0 | 0/0 | 197.842 | 0 | True |
| [resume-after-01](resume-after-01.json) | FINISHED | 12 | 12 | 0 | 0/0 | 26.403 | 0 | False |
| [resume-before-01](resume-before-01.json) | FINISHED | 12 | 11 | 0 | 1/0 | 26.038 | 1 | False |
| [resume-final-01](resume-final-01.json) | FINISHED | 12 | 12 | 0 | 0/0 | 28.14 | 0 | False |
| [resume-final-02](resume-final-02.json) | FINISHED | 12 | 12 | 0 | 0/0 | 30.969 | 0 | True |

full-final-01 保留原 STARTED 记录；现场确认未完成且无存活进程，归类 INCOMPLETE_INTERRUPTED。退出码/原因及最终计数 UNKNOWN，不计为 PASS 或 Engine 行为 FAIL。[中断说明与原件hash](interruption-full-final-01.json)。

工具/新测试辅助错误见 [记录](auxiliary-errors.log)。修前合成Fixture对象的断言输出保留为反例证据；不是运行时诊断输出。
