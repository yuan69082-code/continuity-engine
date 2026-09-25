# W02-C 派生材料撤回补修：原始测试索引

每个新标签的 `.started.json`、`.json`、`.stdout.log`、`.stderr.log` 分别保存命令、起始/终局身份、退出码、耗时和原始输出；标签互不覆盖。最终计数以相应 `.json` 和 stderr 汇总为准，集合有交集，不能累加。原 [W02-C 测试索引](../w02_c_evidence/test-index.md)及失败历史继续保留。

| 标签 | 性质与结果 | 身份与解释 |
| --- | --- | --- |
| `derived-withdrawal-before-01` | 辅助测试前提错误，ERROR | 最初以相同 source_id 表示原文/派生，未满足独立证据条件；原输出保留，非 Engine 缺陷。 |
| `derived-withdrawal-diagnostic-01` | 辅助测试前提错误，FAIL | 相同 source_id 下被既有冲突规则正确隔离；随后改成两个独立内容身份，原输出保留。 |
| `derived-withdrawal-before-02` | **有效修前 1 FAIL** | 原 C1/P16/P04 链中，派生材料撤回后 `memory_current` 仍为 True；此前候选与旧 Context 失效断言已通过。 |
| `derived-withdrawal-after-01` | 修后 1/1 PASS | 同一有效反例通过；之后补充正向与真正跨进程核查，以最终固定版本的专项为准。 |
| `derived-withdrawal-controls-01` | 定点 2/2 PASS | 撤回反例与添加无关同根材料的正向对照；后续又补真正子进程重开。 |
| `derived-withdrawal-process-01` | 定点 1/1 PASS | 子进程重开后只读确认旧 Memory/Summary 失效；查询前后主体、原效果与根文件字节不变。 |
| `formal-final-01` | W02-C 专项 25/25 PASS，88.514 秒 | 固定指纹 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea`，前后相同。 |
| `w02-ab-final-01` | W02-A/B 兼容 123/123 PASS，130.130 秒 | 与专项同一固定指纹，前后相同。 |
| `public-final-01` | P04/P05/P06/P16/P17 兼容 260/260 PASS，213.540 秒 | 与专项同一固定指纹，前后相同。 |
| `full-final-01` | **1728 项：1727 PASS、1 既有 Windows 1314 SKIP，0 FAIL/ERROR**；1627.654 秒，退出 0 | 完整终局汇总已保存；与前三组同一固定指纹，运行前后源码、保护、正式数据、排除材料一致。 |

旧 W02-C 交付版本的 23 项专项及 1726 项全量是历史引用，不覆盖当前补修版本。新版本原 1726 项身份保留，正式回归增加 2 项；既有 Windows 符号链接权限 SKIP 不计 PASS。没有远端 CI 实跑证据。
