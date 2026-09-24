# W02-A 全部运行索引

各组有交集；只按最终全量报告正式测试总数。原始输出不可覆盖。
早期 runner 的 passed 减法在失败子用例场景下可能不准确，失败运行列原始记录数，不替它补造通过数量。

| 标签 | 运行次数 | PASS（成功计数或无失败） | FAIL记录 / ERROR / SKIP | 秒 / exit | 源码前后相等 |
|---|---|---|---|---|---|
| [admission-before-01](admission-before-01.json) · [stderr](admission-before-01.stderr.log) · [stdout](admission-before-01.stdout.log) | 1 | 见原始记录，不重算 | 1 / 0 / 0 | 0.873 / 1 | True |
| [compatibility-final-01](compatibility-final-01.json) · [stderr](compatibility-final-01.stderr.log) · [stdout](compatibility-final-01.stdout.log) | 761 | 见原始记录，不重算 | 77 / 9 / 1 | 616.42 / 1 | True |
| [compatibility-final-02](compatibility-final-02.json) · [stderr](compatibility-final-02.stderr.log) · [stdout](compatibility-final-02.stdout.log) | 813 | 812 | 0 / 0 / 1 | 613.244 / 0 | True |
| [feature-before-01](feature-before-01.json) · [stderr](feature-before-01.stderr.log) · [stdout](feature-before-01.stdout.log) | 未完成 | None | 0 / 0 / 0 | 0.9745511000000988 / 1 | False |
| [full-final-01](full-final-01.json) · [stderr](full-final-01.stderr.log) · [stdout](full-final-01.stdout.log) | 1621 | 1620 | 0 / 0 / 1 | 1545.244 / 0 | True |
| [native-before-01](native-before-01.json) · [stderr](native-before-01.stderr.log) · [stdout](native-before-01.stdout.log) | 1 | 见原始记录，不重算 | 0 / 1 / 0 | 0.933 / 1 | True |
| [receipt-before-01](receipt-before-01.json) · [stderr](receipt-before-01.stderr.log) · [stdout](receipt-before-01.stdout.log) | 2 | 见原始记录，不重算 | 2 / 0 / 0 | 2.236 / 1 | True |
| [targeted-01](targeted-01.json) · [stderr](targeted-01.stderr.log) · [stdout](targeted-01.stdout.log) | 6 | 见原始记录，不重算 | 1 / 0 / 0 | 3.398 / 1 | True |
| [targeted-02](targeted-02.json) · [stderr](targeted-02.stderr.log) · [stdout](targeted-02.stdout.log) | 27 | 27 | 0 / 0 / 0 | 17.992 / 0 | True |
| [targeted-03](targeted-03.json) · [stderr](targeted-03.stderr.log) · [stdout](targeted-03.stdout.log) | 34 | 见原始记录，不重算 | 1 / 0 / 0 | 24.203 / 1 | True |
| [targeted-04](targeted-04.json) · [stderr](targeted-04.stderr.log) · [stdout](targeted-04.stdout.log) | 34 | 34 | 0 / 0 / 0 | 23.817 / 0 | True |
| [targeted-05](targeted-05.json) · [stderr](targeted-05.stderr.log) · [stdout](targeted-05.stdout.log) | 37 | 37 | 0 / 0 / 0 | 26.384 / 0 | True |
| [targeted-06](targeted-06.json) · [stderr](targeted-06.stderr.log) · [stdout](targeted-06.stdout.log) | 39 | 39 | 0 / 0 / 0 | 29.312 / 0 | True |
| [targeted-final-01](targeted-final-01.json) · [stderr](targeted-final-01.stderr.log) · [stdout](targeted-final-01.stdout.log) | 39 | 39 | 0 / 0 / 0 | 29.227 / 0 | True |
| [targeted-final-02](targeted-final-02.json) · [stderr](targeted-final-02.stderr.log) · [stdout](targeted-final-02.stdout.log) | 40 | 40 | 0 / 0 / 0 | 29.735 / 0 | True |
| [targeted-final-03](targeted-final-03.json) · [stderr](targeted-final-03.stderr.log) · [stdout](targeted-final-03.stdout.log) | 41 | 41 | 0 / 0 / 0 | 31.325 / 0 | True |
