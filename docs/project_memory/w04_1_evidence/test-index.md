# W04-1 原始测试与证据索引

每个标签的 `.json` 记录命令、退出码、耗时与运行前后源码指纹；同名 `.stdout.log` 和 `.stderr.log` 为原始输出。标签不可覆盖。各集合可能重叠，不相加；若运行中源码改变，该轮只作过程证据。

| 标签 | 结果 | 解释 |
|---|---|---|
| `w04-targeted-01` | 11 项中 10 PASS、1 ERROR | TEST Frozen Clock 被辅助测试倒退；非运行实现回归，原样保留 |
| `w04-targeted-02` | 11 PASS | 改正测试时钟推进后的中间结果 |
| `w04-targeted-03` | 17 PASS | 增加边界对照后的中间结果 |
| `w04-targeted-04` | 22 项中 21 PASS、1 FAIL | 测试错误假设普通 FACT Event 必然推进主体 revision；原样保留 |
| `w04-targeted-05` | 22 PASS | 改正正向对照后的中间结果 |
| `w04-targeted-06` | 23 PASS | 后续又增加当前只读权限接线，**不作为最终源码的完成证据** |
| `w04-targeted-07` | 24 PASS | 后续又补旧宿主直接拒绝对照，非最终测试身份 |
| `w04-targeted-08` | 24 PASS，9.964 秒 | 指纹 `sha256:08269c803d08e61b4358a60cf478faea5aa1052f805c91546442b5108015f171`，当前专项 |
| `w04-compat-01` | 450 项，445 PASS、5 ERROR，667.452 秒 | 五项均为证据 runner 缺少 `tests` 顶级导入路径；启动后源码也变动，原样保留 |
| `w04-targeted-09` | 24 PASS，10.105 秒，退出 0 | 固定源码 `sha256:166dc0fcd1404560b7dff5af2bb253e751b5d5051e78484413a60f27bfb02824`；受保护正式接口退回原字节后的本批专项 |
| `w04-compat-final-01` | 502 PASS，750.175 秒，退出 0 | 运行前后源码指纹不同；保留为过程证据，不算终局兼容 |
| `w04-compat-fixed-01` | 182 PASS，265.448 秒，退出 0 | 同一固定源码；P16/P17/P18/W02/W03 代表性受影响兼容，包含 W02 原四份资料和 16 项检索的 1000ms 测试 |
| `w04-full-final-01` | 1797 项：1796 PASS、1 SKIP、0 FAIL/ERROR；1650.896 秒，退出 0 | `unittest discover -s tests -v`；固定源码前后同指纹。SKIP 是原 P08 Windows symlink 创建权限 1314 |

终局三组（`w04-targeted-09`、`w04-compat-fixed-01`、`w04-full-final-01`）运行前后均为 `sha256:166dc0fcd1404560b7dff5af2bb253e751b5d5051e78484413a60f27bfb02824`；组间有交集，不相加。历史 WinError 1314 SKIP、F1/H1/F2 UNKNOWN 保持原记录，不计为本批 PASS。前面两次兼容过程记录分别有 runner 导入 ERROR 和源码指纹漂移，不能覆盖或删去。

## N09／N10 返修新增原始标签

旧标签全部保留，下面是本次新增记录；每项有独立 `.json`、`.stdout.log`、`.stderr.log`，可按 JSON 的完整命令复跑。`w04-r1-full-final-01` 的运行器虽收口，却因人为中断没有 `unittest` 总汇总；它永不充作全量 PASS。

| 标签 | 实际结果 | 源码身份／解释 |
|---|---|---|
| `w04-r1-before-01` | 4 测试方法，8 FAIL／3 ERROR，退出 1 | 修前反例；行动夹具路径过长产生辅助 ERROR，保留原始输出 |
| `w04-r1-before-02` | 4 测试方法，9 FAIL／2 ERROR，退出 1 | 修正辅助路径与子用例干扰后的真实修前反例；输出能力到期曾产生 Fake 效果 |
| `w04-r1-targeted-01` | 28 项，27 PASS／1 ERROR，退出 1 | 引擎正确地通过原入站顶层错误包装拒绝能力；测试误断言异常顶层，原结果保留 |
| `w04-r1-targeted-02` | 29 PASS，13.709 秒，退出 0 | 修后完整 W04-1 专项；前后 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c` |
| `w04-r1-compat-final-01` | 182 PASS，290.358 秒，退出 0 | P16/P17/P18/W02/W03 受影响兼容；前后同上指纹，集合与专项重叠 |
| `w04-r1-full-final-01` | **INTERRUPTED**；无 `unittest` 总汇总，不计 PASS/行为 FAIL | 用户临时暂停后安全中断测试子进程；运行器收口记录退出码 `4294967295`、1611.963 秒、前后同版指纹；[现场与哈希](repair-pause-01.md) |
| `w04-r1-full-resume-01` | **1802 项：1801 PASS／1 既有 SKIP／0 FAIL/ERROR**，运行器 1876.171 秒、退出 0 | 用户明确恢复后只补这一轮最终全量；前后均为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`。SKIP 为原 P08 Windows symlink 创建权限不足 1314；[JSON](w04-r1-full-resume-01.json)、[stdout](w04-r1-full-resume-01.stdout.log)、[stderr](w04-r1-full-resume-01.stderr.log) |

前两组修前指纹分别见原始 JSON；后续 PASS 不覆盖失败或中断。专项 29、兼容 182、全量 1802 互有交集，不相加；全量和两组完成验证共用同一源码指纹。没有取得远端 CI 结果，Windows 1314 SKIP 和 F1/H1/F2 UNKNOWN 继续按历史记录。
