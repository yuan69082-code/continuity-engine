# P14 逐轮原始运行索引

FAIL/ERROR列为unittest记录条目数；子用例与总用例不强行相加。每轮源码和命令以对应JSON为准；包括中间失败，不能跨版本累加为通过。

| label | 执行 | PASS | SKIP | FAIL | ERROR | runner秒 |
|---|---:|---:|---:|---:|---:|---:|
| [initial-red](initial-red.json) | 8 | 0 | 0 | 0 | 8 | 0.622 |
| [mechanism-first](mechanism-first.json) | 8 | 8 | 0 | 0 | 0 | 0.637 |
| [integration-red](integration-red.json) | 4 | 0 | 0 | 0 | 4 | 0.643 |
| [integration-first](integration-first.json) | 4 | 3 | 0 | 0 | 1 | 4.909 |
| [integration-contract-checked](integration-contract-checked.json) | 12 | 12 | 0 | 0 | 0 | 5.434 |
| [native-opportunity-red](native-opportunity-red.json) | 5 | 4 | 0 | 0 | 1 | 5.731 |
| [native-opportunity-first](native-opportunity-first.json) | 5 | 5 | 0 | 0 | 0 | 5.877 |
| [owner-visibility-red](owner-visibility-red.json) | 4 | 0 | 0 | 0 | 4 | 2.587 |
| [owner-visibility-first](owner-visibility-first.json) | 4 | 4 | 0 | 0 | 0 | 2.842 |
| [lifecycle-detail-red](lifecycle-detail-red.json) | 12 | 9 | 0 | 3 | 0 | 0.663 |
| [lifecycle-detail-fixed](lifecycle-detail-fixed.json) | 12 | 12 | 0 | 0 | 0 | 0.673 |
| [affective-chain-red](affective-chain-red.json) | 6 | 5 | 0 | 0 | 1 | 5.700 |
| [affective-chain-first](affective-chain-first.json) | 6 | 5 | 0 | 0 | 1 | 6.612 |
| [resume-affective-before](resume-affective-before.json) | 6 | 5 | 0 | 0 | 1 | 7.112 |
| [resume-affective-scoped](resume-affective-scoped.json) | 6 | 6 | 0 | 0 | 0 | 9.149 |
| [remaining-mechanisms-red](remaining-mechanisms-red.json) | 23 | 18 | 0 | 4 | 1 | 10.346 |
| [remaining-mechanisms-first](remaining-mechanisms-first.json) | 27 | 24 | 0 | 1 | 2 | 10.353 |
| [remaining-mechanisms-query](remaining-mechanisms-query.json) | 27 | 26 | 0 | 1 | 0 | 12.447 |
| [c1-recovery-extended-red](c1-recovery-extended-red.json) | 13 | 12 | 0 | 1 | 0 | 13.676 |
| [c1-recovery-extended-fixed](c1-recovery-extended-fixed.json) | 32 | 32 | 0 | 0 | 0 | 17.018 |
| [downstream-resolution-red](downstream-resolution-red.json) | 33 | 30 | 0 | 2 | 1 | 18.034 |
| [downstream-resolution-first](downstream-resolution-first.json) | 37 | 35 | 0 | 1 | 1 | 18.385 |
| [downstream-resolution-bounded](downstream-resolution-bounded.json) | 15 | 13 | 0 | 1 | 1 | 18.120 |
| [observation-golden-red](observation-golden-red.json) | 26 | 21 | 0 | 1 | 4 | 24.378 |
| [golden-and-boundaries-first](golden-and-boundaries-first.json) | 44 | 43 | 0 | 0 | 1 | 36.051 |
| [p14-boundary-combination-first](p14-boundary-combination-first.json) | 50 | 50 | 0 | 0 | 0 | 39.168 |
| [p14-stable](p14-stable.json) | 50 | 50 | 0 | 0 | 0 | 54.001 |
| [gate-off-native-red](gate-off-native-red.json) | 1 | 0 | 0 | 1 | 0 | 1.384 |
| [p14-final](p14-final.json) | 51 | 51 | 0 | 0 | 0 | 40.956 |
| [compatibility-final](compatibility-final.json) | 741 | 740 | 1 | 0 | 0 | 644.020 |
| [explicit-decisions-red](explicit-decisions-red.json) | 3 | 0 | 0 | 3 | 0 | 4.044 |
| [p14-final-2](p14-final-2.json) | 54 | 54 | 0 | 0 | 0 | 44.509 |
| [targeted-compatibility-final](targeted-compatibility-final.json) | 85 | 85 | 0 | 0 | 0 | 56.503 |
| [full-final](full-final.json) | 1124 | 1123 | 1 | 0 | 0 | 683.111 |

[失败根因与版本解释](failure-history.md) · [最终报告](final-report.md)
