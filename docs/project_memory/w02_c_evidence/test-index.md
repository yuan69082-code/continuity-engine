# W02-C 原始测试和身份索引

> 本索引保留初版历史结果。部分派生材料撤回的新增失败、补修和新源码版本结果见[定向补修原始索引](../w02_c_repair_evidence/test-index.md)。

每个标签的 `.json` 写明命令、退出码、耗时及运行前后源码指纹；同名 `.stdout.log` / `.stderr.log` 为原始输出。较早的简易标签只保存必要摘要，未被改写。测试集合重叠，不相加为正式总数。

| 标签 | 实际性质与结果 | 身份/解释 |
| --- | --- | --- |
| `preprobe-01` | 修前 2 项，1 PASS、1 FAIL | 真实 C1 路径：外部控制面声明仍被旧 P16 候选投影送入 Context；同根计数对照通过。此时 W02-C 尚未实现。 |
| `formal-01` | 初版正式测试，FAIL/ERROR | 长 Temp 路径与不正确的原夹具记忆前提属于新增测试辅助问题；原样保留。 |
| `formal-02` | 9/9 PASS | 初版修正辅助代码后的中间版本，后续新增场景，不能覆盖最终源码。 |
| `recovery-01` | 7/7 PASS | 原请求回放、返回丢失、UNKNOWN、旧格式、真实子进程重开等；后续代码又变化，最终专项另跑。 |
| `p16-compat-01` | 78/78 PASS | 原 P16 关闭 W02-C 时的兼容；中间源码版本，最终公共兼容另跑。 |
| `new-edges-01` | 3 项中 2 PASS、1 FAIL | 新测试误把 P16 的 `CONSUMPTION_DENIED` 预期为抛错；原 P16 确实拒绝消费且未缓存。辅助断言修正后独立定点通过，旧失败保留。 |
| `formal-final-01` | 19/19 PASS | 加入待验场景前的中间源码。 |
| `w02-compat-01` | 123/123 PASS | W02-A/B 中间源码；后续相关性调整后另跑。 |
| `formal-final-02` | 21 项中 20 PASS、1 FAIL | 新增真实反例：无关候选仍进入回应 Context；随后仅调整 W02-C 投影相关性。 |
| `relevance-fix-01` | 2/2 PASS | 无关候选排除、相关候选正向；随后补 Learning 撤销断言。 |
| `formal-final-03` | 21/21 PASS | 相关性修复后、Learning 撤销断言前的源码。 |
| `core-compat-01` | 208 项，205 PASS、3 加载 ERROR | 本地证据运行器漏 `tests` 搜索路径；P17 辅助类导入失败。并非 Engine 断言失败，保留原输出。 |
| `core-compat-02` | 260/260 PASS | 修正运行器后通过，但测试文件在运行期间新增 Learning 撤销断言，前后身份不同，仅为中间记录。 |
| `formal-final-04` | 21/21 PASS | 固定源码/测试指纹 `sha256:0fb843ae12d8e0d54293e34bba8ec5aba8f34771adf5fbb0f4858f43c0077840`；80.051 秒，退出 0。 |
| `w02-compat-02` | 123/123 PASS | 同一固定指纹；197.829 秒，退出 0。 |
| `core-compat-03` | 260/260 PASS | P04/P05/P06/P16/P17 受影响组合；同一固定指纹，331.588 秒，退出 0。 |
| `full-final-01` | 有记录的主动中断，无完成汇总 | 运行 808.894 秒后为补齐 W02-C 根证明跨 subject/environment 正式用例而停止本轮测试子进程；Windows 返回码 4294967295，不能计算已运行/通过数，也不是 Engine 行为 FAIL。[中断说明](full-final-01-interruption.md)。 |
| `root-boundary-01` | 1/1 PASS（含 subject 与 environment 两个子场景） | 补充本批根证明隔离；7.934 秒，退出 0。 |
| `formal-final-05` | 22/22 PASS | 最终新增边界后的固定指纹 `sha256:700ecb8d0c5b4185d4933c34c64c6994f38b7bd0ba95252826f479ee6b4235e1`；89.922 秒，退出 0。 |
| `w02-compat-03` | 123/123 PASS | 最终指纹，189.928 秒，退出 0，零 SKIP。 |
| `core-compat-04` | 260/260 PASS | 最终指纹，226.630 秒，退出 0，零 SKIP。 |
| `full-final-02` | 有记录的主动中断，无完成汇总 | 约 308.954 秒后为修正 W02-C 对普通心理内容的过宽判定而停止；无已运行数量或 PASS 结论。[中断说明](full-final-02-interruption.md)。 |
| `control-boundary-01` | 2/2 PASS | 明确命令式控制声明拒绝、普通心理内容仍是非权威候选；4.199 秒，退出 0。 |
| `formal-final-06` | 23/23 PASS | 当前最终指纹 `sha256:41c56bd71950de9aca28b13043797fb794dfd04844dba17dd670341732419056`，62.512 秒，退出 0。 |
| `w02-compat-04` | 123/123 PASS | 同一指纹，137.048 秒，退出 0。 |
| `core-compat-05` | 260/260 PASS | P04/P05/P06/P16/P17 联验；最终指纹一致，223.582 秒，退出 0。 |
| `full-final-03` | 1726 项：1725 PASS、1 既有 Windows 1314 SKIP，0 FAIL/ERROR | 固定源码版本的一次完整回归；1656.915 秒，退出 0，运行前后源码/正式数据/保护/排除身份均一致。原始 [运行结果](full-final-03.json)、[stdout](full-final-03.stdout.log)、[stderr](full-final-03.stderr.log)。 |

历史 W02-B 基线 1703 项（1702 PASS、1 既有 Windows 1314 SKIP）是引用，不属于本批实跑。无可验证远端 CI 结果，不声明 CI PASS。测试均使用隔离 TEST 根和 Fake；真实服务、生产数据及生产能力未经验证。
