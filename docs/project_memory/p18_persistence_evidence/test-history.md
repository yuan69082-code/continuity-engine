# 本轮全部唯一标签与源码覆盖

失败栏按unittest失败记录计；子用例可能多于失败方法，不能减去记录数伪算PASS。旧writer重建使用归档方法替换，不能作为当前实现PASS。辅助错误见 [说明](auxiliary-errors.md)。

| 标签 | RUN | PASS | SKIP | FAIL记录/ERROR | 秒 | exit | 证据 |
|---|---|---|---|---|---|---|---|
| bounded-after-01 | 5 | 5 | 0 | 0/0 | 5.59 | 0 | [记录](bounded-after-01.json) · [输出](bounded-after-01.stdout.log) · [诊断](bounded-after-01.stderr.log) |
| compatibility-final-01 | 605 | 605 | 0 | 0/0 | 841.034 | 0 | [记录](compatibility-final-01.json) · [输出](compatibility-final-01.stdout.log) · [诊断](compatibility-final-01.stderr.log) |
| formal-after-01 | 11 | 11 | 0 | 0/0 | 7.171 | 0 | [记录](formal-after-01.json) · [输出](formal-after-01.stdout.log) · [诊断](formal-after-01.stderr.log) |
| formal-after-02 | 14 | 13 | 0 | 1/0 | 11.656 | 1 | [记录](formal-after-02.json) · [输出](formal-after-02.stdout.log) · [诊断](formal-after-02.stderr.log) |
| formal-final-01 | 14 | 13 | 0 | 1/0 | 11.478 | 1 | [记录](formal-final-01.json) · [输出](formal-final-01.stdout.log) · [诊断](formal-final-01.stderr.log) |
| formal-final-02 | 14 | 14 | 0 | 0/0 | 11.493 | 0 | [记录](formal-final-02.json) · [输出](formal-final-02.stdout.log) · [诊断](formal-final-02.stderr.log) |
| full-final-01 | 1480 | 1479 | 1 | 0/0 | 1284.129 | 0 | [记录](full-final-01.json) · [输出](full-final-01.stdout.log) · [诊断](full-final-01.stderr.log) |
| guarded-after-01 | 8 | 8 | 0 | 0/0 | 7.048 | 0 | [记录](guarded-after-01.json) · [输出](guarded-after-01.stdout.log) · [诊断](guarded-after-01.stderr.log) |
| native-before-01 | 5 | 1 | 0 | 4/0 | 3.375 | 1 | [记录](native-before-01.json) · [输出](native-before-01.stdout.log) · [诊断](native-before-01.stderr.log) |
| native-before-02 | 5 | 3 | 0 | 2/0 | 5.816 | 1 | [记录](native-before-02.json) · [输出](native-before-02.stdout.log) · [诊断](native-before-02.stderr.log) |
| old-writer-confirm-01 | 2 | 0 | 0 | 2/0 | 2.942 | 1 | [记录](old-writer-confirm-01.json) · [输出](old-writer-confirm-01.stdout.log) · [诊断](old-writer-confirm-01.stderr.log) |
| original-f2-before-01 | 1 | 1 | 0 | 0/0 | 8.351 | 0 | [记录](original-f2-before-01.json) · [输出](original-f2-before-01.stdout.log) · [诊断](original-f2-before-01.stderr.log) |
| p18-final-01 | 120 | 120 | 0 | 0/0 | 174.733 | 0 | [记录](p18-final-01.json) · [输出](p18-final-01.stdout.log) · [诊断](p18-final-01.stderr.log) |
| reader-after-01 | 5 | 3 | 0 | 2/0 | 6.142 | 1 | [记录](reader-after-01.json) · [输出](reader-after-01.stdout.log) · [诊断](reader-after-01.stderr.log) |
| reader-before-01 | 2 | 1 | 0 | 1/0 | 1.522 | 1 | [记录](reader-before-01.json) · [输出](reader-before-01.stdout.log) · [诊断](reader-before-01.stderr.log) |
| save-stages-before-01 | 3 | 1 | 0 | 4/0 | 0.87 | 1 | [记录](save-stages-before-01.json) · [输出](save-stages-before-01.stdout.log) · [诊断](save-stages-before-01.stderr.log) |
| stop-retry-before-01 | 1 | 0 | 0 | 1/0 | 1.975 | 1 | [记录](stop-retry-before-01.json) · [输出](stop-retry-before-01.stdout.log) · [诊断](stop-retry-before-01.stderr.log) |

[逐次源码差异和输出hash](test-source-coverage.json)。所有标签不相加为正式测试总数；原探针/组间交集保留。
