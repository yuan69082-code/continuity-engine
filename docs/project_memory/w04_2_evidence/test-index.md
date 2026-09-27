# W04-2 真实测试索引

施工方本轮实跑；不是规划窗口独立实跑或远端CI；集合重叠不相加

固定源码：`sha256:61bb34c6728e6850786b10b867bf9a440b8193e1534c82ff30b46ba488392b0f`。**兼容未通过，最终全量未启动**，不能写成全批验证通过。

| 标签 | PASS / FAIL / ERROR / SKIP | runner秒 / unittest秒 | exit | 原始输出 |
|---|---|---|---|---|
| w04-2-before-01 | 0 / 0 / 1 / 0 | 0.58 / 0.008 | 1 | [命令与hash](w04-2-before-01.json) · [stdout](w04-2-before-01.stdout.log) · [stderr](w04-2-before-01.stderr.log) |
| w04-2-contract-01 | 0 / 0 / 1 / 0 | 0.459 / 0.013 | 1 | [命令与hash](w04-2-contract-01.json) · [stdout](w04-2-contract-01.stdout.log) · [stderr](w04-2-contract-01.stderr.log) |
| w04-2-chain-01 | 15 / 0 / 3 / 0 | 34.325 / 33.729 | 1 | [命令与hash](w04-2-chain-01.json) · [stdout](w04-2-chain-01.stdout.log) · [stderr](w04-2-chain-01.stderr.log) |
| w04-2-query-fix-01 | 3 / 0 / 0 / 0 | 6.992 / 6.354 | 0 | [命令与hash](w04-2-query-fix-01.json) · [stdout](w04-2-query-fix-01.stdout.log) · [stderr](w04-2-query-fix-01.stderr.log) |
| w04-2-chain-02 | 28 / 2 / 1 / 0 | 59.228 / 58.673 | 1 | [命令与hash](w04-2-chain-02.json) · [stdout](w04-2-chain-02.stdout.log) · [stderr](w04-2-chain-02.stderr.log) |
| w04-2-boundary-fix-01 | 3 / 0 / 1 / 0 | 7.18 / 6.629 | 1 | [命令与hash](w04-2-boundary-fix-01.json) · [stdout](w04-2-boundary-fix-01.stdout.log) · [stderr](w04-2-boundary-fix-01.stderr.log) |
| w04-2-host-fix-01 | 1 / 0 / 0 / 0 | 4.103 / 3.573 | 0 | [命令与hash](w04-2-host-fix-01.json) · [stdout](w04-2-host-fix-01.stdout.log) · [stderr](w04-2-host-fix-01.stderr.log) |
| w04-2-flow-01 | 5 / 0 / 0 / 0 | 24.5 / 23.353 | 0 | [命令与hash](w04-2-flow-01.json) · [stdout](w04-2-flow-01.stdout.log) · [stderr](w04-2-flow-01.stderr.log) |
| w04-2-guards-01 | 5 / 0 / 1 / 0 | 12.367 / 11.673 | 1 | [命令与hash](w04-2-guards-01.json) · [stdout](w04-2-guards-01.stdout.log) · [stderr](w04-2-guards-01.stderr.log) |
| w04-2-special-final-01 | 71 / 0 / 0 / 0 | 220.526 / 219.768 | 0 | [命令与hash](w04-2-special-final-01.json) · [stdout](w04-2-special-final-01.stdout.log) · [stderr](w04-2-special-final-01.stderr.log) |
| w04-2-compat-final-01 | 407 / 1 / 6 / 0 | 3368.009 / 3367.155 | 1 | [命令与hash](w04-2-compat-final-01.json) · [stdout](w04-2-compat-final-01.stdout.log) · [stderr](w04-2-compat-final-01.stderr.log) |

专项71项=本批新增42项+W04-1原29项。原1802项身份和113份旧测试字节保留，未宣称本轮完整运行。
有界原HEAD/当前对照各4项、各0 PASS/1 FAIL/3 ERROR，独立报告不与专项或兼容相加，见[对照记录](recall-paired-diagnostic-01.json)。
三个隔离链路样例exit 0、80.321秒，不计正式测试数量，见[样例执行记录](sample-run-01.json)及[链路引用](chain-examples.json)。
本轮没有执行最终全量；既有1801 PASS/1 Win1314 SKIP仅为历史基线引用，不能充当本轮结果。
原失败与辅助问题见[failure-history.md](failure-history.md)，当前阻断见[conflict-report.md](conflict-report.md)。
