# W02 整体贯通原始证据索引

本目录的 `run.py` 为每个新标签用独立 `.started.json`、`.stdout.log`、`.stderr.log`、`.json` 保存命令、退出码、耗时、前后源码/测试/资源身份及保护、正式数据、57 项排除材料核对。旧标签不会被覆盖。所有运行均使用隔离 TEST Fixture；没有远端 CI run。

| 作用 | 原始结果 | 状态 |
| --- | --- | --- |
| 开工身份/现有有限联验 | [baseline.json](baseline.json)；[baseline-existing-link-01.json](baseline-existing-link-01.json) | 既有联验 1 PASS，仅有限覆盖。 |
| 新测试首跑 | [integration-draft-01.json](integration-draft-01.json)、[stderr](integration-draft-01.stderr.log) | 3 PASS / 2 ERROR，失败留存。 |
| 恢复同版修前/修后 | [A 对照](a-only-recovery-01.json)、[AB 修前](combined-recovery-01.json)、[AB 修后](combined-recovery-after-01.json) | A PASS；AB 修前 ERROR，修后 PASS。 |
| 恢复拒绝、重复与 Context 诊断 | [边界](recovery-boundaries-01.json)、[错误预期](recovered-memory-context-01.json)、[诊断](recovered-memory-diagnostic-01.json) | 3 PASS；辅助失败与诊断保留。 |
| 部分撤回 TEST 装配过程 | [原复杂超时](integration-draft-01.json)、[根前提错误](withdrawal-integrated-02.json)、[当前通过](withdrawal-integrated-03.json) | 不抹除超时和辅助错误。 |
| 固定版贯通专项 | [integration-targeted-01.json](integration-targeted-01.json)、[stdout](integration-targeted-01.stdout.log)、[stderr](integration-targeted-01.stderr.log) | 8/8 PASS。 |
| 固定版 A/B/C 兼容 | [w02-abc-compat-01.json](w02-abc-compat-01.json)、[stderr](w02-abc-compat-01.stderr.log) | 156/156 PASS。 |
| 固定版公共兼容 | [public-compat-01.json](public-compat-01.json)、[stderr](public-compat-01.stderr.log) | 318/318 PASS。 |
| 固定版全量 | [full-final-01.json](full-final-01.json)、[stdout](full-final-01.stdout.log)、[stderr](full-final-01.stderr.log) | 1736 项：1735 PASS、1 既有 Win1314 SKIP、0 FAIL/ERROR；1677.033 秒，退出码 0。 |

样例可直接从 [通过组 stdout](integration-targeted-01.stdout.log) 查看原请求、站理由、外部请求/回执与最终来源；完整叙述见 [补修与限制](repair-report.md)。测试集合有交集，不得相加成总项数。
