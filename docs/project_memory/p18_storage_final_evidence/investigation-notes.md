# P18 F1/H1 存储返修：因果证据与历史限制

日期：2026-09-14。本文记录本轮已读取的实验结果及其版本范围；不是验收结论。P18 仍为 `IMPLEMENTED_NOT_ACCEPTED`，`EVIDENCE_CONFLICT=PRESENT`；没有 D-073、Git 写操作或 P19 开工。

## 1. 当前机制与历史事件分别判断

| 项目 | 已证实的当前事实 | 不能据此补写的历史结论 |
|---|---|---|
| F1 同流程反例 | 真实读句柄使 SubjectState 原子替换返回 `PermissionError / errno13 / winerror5`；读者在分类前释放，旧 DELETE 探测成功，旧代码不在原提交内继续。第二轮 Thinking 已完成但状态提交未完成，原任务进入 UNKNOWN / WAITING_VERIFICATION。Frozen Clock 停在查询水位之前，原 25 秒观察失败。 | 历史 F1 没有失败时完整 ThinkSession 阶段及系统原因链。当前反例能形成相似状态，但不是历史那一次的唯一归因。 |
| H1 同流程反例 | 真实读句柄阻挡发布 WAITING_RESOURCES 的 checkpoint 替换；旧代码随后另写 BACKOFF / WORK_PORT_UNAVAILABLE，Frozen Clock 没有越过新的 next_check_at，原观察失败。 | 历史 H1 缺少 STOP 前关键活动、水位和原异常。相同读写代码及当前受控交错不能证明历史 H1 一定发生同一文件竞争。 |
| F2 | 先前受控 Windows 读句柄竞争、已有事实与未完成状态提交之间的恢复风险已复现并修补。本轮保留该保护。 | 历史 F2 虽有 `_write_payload / os.replace` 栈位置，缺原异常类型、系统错误码及句柄身份，不能自动与 F1/H1 合并结案。 |

原材料入口：[F1 清理前调查](../p18_repair_evidence/full-timeout-investigation.json)、[H1 首次失败](../p18_evidence/p18-final-04.json)、[F2 清理前失败](../p18_r2_evidence/full-resume-01-failure.json)、[上一轮定向调查](../p18_f1_h1_evidence/investigation-report.md)。旧失败、未知项、辅助错误均保留。

本轮引用并核对源码身份一致的前轮修前实跑：原正常流程与受控交错合计四项，2 PASS、2 FAIL，外层耗时 79.248 秒；两个 FAIL 分别为上述 F1/H1 反例，原流程、断言及 25 秒观察期限没有放宽。不是本轮再次执行修前测试。见 [original-flows-before-01](../p18_storage_repair_evidence/original-flows-before-01.json) 及同名 stdout/stderr。

冻结时钟与文件失败是两层条件。修改前另行运行的同类持续走时对照为 2/2 PASS、28.540 秒，见 [advancing-clock-before-01](../p18_storage_repair_evidence/advancing-clock-before-01.json)。这说明原到期恢复可以工作，不证明文件失败不存在，也不把原冻结时钟反例改成 PASS。产品正常入口仍持续运行；测试控制器的时限没有成为产品停机规则。

## 2. 已获确认的行为变化及最小实现

用户另行明确确认了“完整操作绑定的固定 WinError5 在当前条件允许时进行有限尝试”的行为差异。新处理不再要求分类瞬间仍观察到共享占用，名称及结论是**当前条件允许同提交有限尝试**，不是“已证明此前发生共享冲突”。

仅两个运行文件变化：

- `src/continuity_engine/storage/json_repository.py`：沿用显式 P18 retry guard；绑定原始序列化内容、自建临时文件身份、目标原内容及身份、目录身份、错误所指的 source/destination，检查只读/链接及必要当前 DELETE 访问条件；在同一有界期限内重试同一份提交，每次继续前重查授权及文件条件。无显式授权的原公共路径仍只尝试一次。
- `src/continuity_engine/storage/json_runtime_repository.py`：在原 checkpoint 事务内使用上述处理；事务资格绑定原实例、线程、唯一 token 及活动生命周期。耗尽的合格写入用专用 `RuntimeCheckpointWriteDeferred` 表达，复用原 RuntimeCheckpointBusy 保活路径，不把所有权限、损坏、版本冲突或 OSError 一并吞掉。不重新获取原非重入 OS 锁，不新增持久字段、Authority 或账本。

有限写入耗尽不表示提交成功。checkpoint 的旧字节、控制记录及版本保留；控制调用不得声称 PAUSE/STOP 已成功。解除限制后重新处理当前合法工作，原命令身份可按既有规则重放。已完成动作的回执仍走原事实核实，不能因状态保存失败重派动作或再次计费。

真实权限对照保留了一个重要区别：目标 READONLY 时，原生替换返回 WinError5，即使异常 source/destination 正确且 DELETE 探测都成功也不能重试绕过属性。隔离 DACL 拒绝的原生错误及恢复证据见 [acl-access-02](../p18_storage_repair_evidence/independent/acl-access-02.json)；本轮接线验证见 [native-denial-final-01](native-denial-final-01.json)，4/4 PASS、0.593 秒。该组是中间源码版本的实际结果，不能单独冒充最终源码覆盖。

## 3. 本轮新发现与辅助失败如何归类

| 记录 | 真实结果与机制 | 处理范围 |
|---|---|---|
| [boundaries-after-01](boundaries-after-01.json) | 22 项，19 PASS、3 FAIL，8.253 秒。新增 TEST 根名称较长，部分流程在预定持句柄故障点之前就失败。 | 原输出保留；没有把未到达故障点的失败伪称为读句柄修补反例。 |
| [fixture-length-02](fixture-length-02.json) / [原始诊断](fixture-length-02.stdout.log) | 定点 1 FAIL，1.337 秒；实际捕获 `FileNotFoundError / errno2 / winerror=null`，`NamedTemporaryFile` 的目标完整文件名长度 **261**，父目录存在，栈经过 `JsonAwakeningRepository._write_json`。当时尚无 ThinkSession、效果为零、token_used=64。 | 缩短本轮新建 TEST 根前缀，保留同一流程和断言。不能把 winerror 补写成一个未取得的系统码，也不据此宣称所有 Windows 长路径政策已查明或已修补。 |
| [fixture-short-01](fixture-short-01.json) / [host-boundaries-after-02](host-boundaries-after-02.json) | 相同定点短根 1/1 PASS、2.409 秒；同一七项宿主测试 7/7 PASS、10.498 秒。 | 这是 TEST 路径条件修正，未改公共 Awakening 实现或原断言；旧三个 FAIL 仍在。一般长路径支持不是本轮完成项，更不能倒推历史 F1/H1 根因。 |
| [new-guards-before-01](new-guards-before-01.json) | 3 个正式测试身份，0 PASS，1.543 秒；日志含 6 条失败断言/子用例记录，不是 6 个不同正式测试。分别证明：临时文件初次基准未绑定调用方原 payload/inode；复制 Context 到其他线程可带出事务资格；清理异常覆盖了原生错误原因链。 | 属于本轮实现审查确认的实际边界遗漏；补齐原始 payload/inode、线程及事务 token、原生错误与清理错误链，未借机扩改其他运行模块。 |
| [boundaries-after-03](boundaries-after-03.json) | 上述补齐后 25/25 PASS、12.353 秒。 | 中间结果保留；后续又发现事务生命周期问题，不能把这一组直接当作最终版本证据。 |
| [expired-context-before-01](expired-context-before-01.json) | 1 项，0 PASS、1 ERROR，1.165 秒。原事务退出后，在同一线程恢复复制 Context，旧 token 仍允许有限尝试，最终得到未预期的 WRITE_DEFERRED。 | 这是事务资格过期未失效的真实遗漏；增加原 token 的活动生命周期，原事务 finally 失活。保留 ERROR 原记录，不改成辅助运行错误或 PASS。 |
| [auxiliary-placement-01](auxiliary-placement-01.json) | 新测试类误插入既有 helper，出现 `IndentationError`；保存前后 hash。 | 仅修正新测试类位置；不是 Engine 行为失败，未修改运行源码来处理这个辅助问题。 |

此外，ACL 实验首版将整个安全描述符二进制一致误作权限恢复的唯一条件，留下辅助失败。后续记录证明 DACL 条目恢复、仅继承控制位变化，保留原错误并单独记录清理，见 [acl-access-01](../p18_storage_repair_evidence/independent/acl-access-01.json)、[acl-access-01-cleanup](../p18_storage_repair_evidence/independent/acl-access-01-cleanup.json)。不把权限条目等价写成原始字节完全一致。

## 4. 已完成验证与最终版本范围

截至撰写本备注，已核对 [frozen-source-02.json](frozen-source-02.json)：269 份源码/测试/资源；原 1480 项身份保留，新增 27 项，当前 1507 项身份。源码清单聚合指纹为：

`sha256:31ebcd2eb210304a98dae87a836ff2bed9581bc41d26216dc5dc75e4eaa4bb7e`

旧 `frozen-source.json` 对应新增 26 项的中间版本，原样保留，不能替代第二份冻结记录。

| 已读取记录 | 实际执行结果 | 与第二份冻结的关系 |
|---|---|---|
| [boundaries-final-04](boundaries-final-04.json) | 27/27 PASS，23.097 秒，exit 0 | 运行前后源码均匹配第二份冻结；覆盖新生命周期反例及前述守卫。 |
| [originals-final-03](originals-final-03.json) | 4/4 PASS，37.523 秒，exit 0 | 原两个正常进程对照及两个受控读句柄反例；运行前后源码匹配第二份冻结，原 25 秒断言保留。 |
| [host-process-final-01](host-process-final-01.json) | 1/1 PASS，11.514 秒，exit 0 | 此次单项实际运行属于先前 26 项版本；同一正式用例已包含在匹配第二份冻结的 27 项组中，不重复相加。 |
| [advancing-final-01](advancing-final-01.json) | 2/2 PASS，19.309 秒，exit 0 | 中间版本的持续走时对照。不能替代正在对第二份冻结进行的后续验证。 |

表内秒数来自各 JSON 的外层执行时间，各组相互有交集，不能相加为新的正式总测试数。本文作者只读核查这些已有输出，未另行重跑它们。

真实宿主进程用例明确验证：checkpoint 长占用超过一次存储尝试预算，进程继续存活；资源观察失败时不伪报等待已保存、不调用模型；句柄释放后恢复 WAITING_RESOURCES；PAUSE 期间预算恢复仍不执行；RESUME 后无需聊天消息推进；STOP 后退出 0，再开仍保持 STOP。实际效果场景另验证动作、credits、Provider 调用及状态推进不重复。测试控制器显式停止和回收子进程，未增加产品运行期限或外部自动重启。

最终专项、兼容和完整回归由主线程按第二份冻结继续记录；本备注不预填未完成测试的数量、退出码或 PASS，也不把旧全量当作本轮全量。最终报告需引用实际完成记录，并保留既有 Windows 1314 SKIP，不宣称未经取得的远端 CI 结果。

## 5. 当前可交付结论的边界

当前两个受控读句柄机制有修前失败及同流程修后通过证据；公共写入资格、事务生命周期和错误链遗漏也有具体修前/修后记录。全阶段完成状态仍须结合最终专项、兼容、全量、保护与进程审计，之后交独立复核。

历史 F1/H1/F2 的原始缺口未被新实验补出。可以说明“当前保护覆盖了已复现的这一风险”，不能说明“历史三个事件已证实同源且全部结案”。不自动清除 EVIDENCE_CONFLICT，不自行接受遗留风险、验收或推进后续阶段。
