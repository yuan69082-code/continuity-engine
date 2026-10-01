# W04 包级续作：结果读取及上下文选择

本记录是本轮施工实跑与代码调查，不是独立复核或验收。原失败及本记录之前的快照保留。D-092 继续 IN_PROGRESS，EVIDENCE_CONFLICT=PRESENT。未写 Git、未启动 W05。

## 已观察事实

- package-chain-02：已完成 P16 发现、临时连接与核验、模拟历史查询，后续原始选店消息 RECALL_TIMEOUT。
- package-stations-01 单次轻量计时：回忆 1031.892ms；结果核验 5 次/711.156ms，原 E5-A 读取 221 次/184.957ms。各项嵌套，不相加。
- package-projection-01：副本/完整校验回归 PASS，包级仍 ERROR，未完成。
- package-projection-02：仍超时，另有新 TEST 根尚未创建的辅助错误。随后修正辅助初始化；旧输出原样保留。
- package-stations-02：一次轻量计时 819.748ms，但目标查询未入最终 Context。另有新增辅助断言误将已保存 revision=1 与未保存 empty revision=0 比较，已改为原保存文档比较，未改产品 revision。
- package-selection-01：普通回应候选按 ID 截取，真实 query 未被选中。包级断言 FAIL。
- package-selection-repair-01、package-tool-read-01：仍有 RECALL_TIMEOUT，不能称已修复。
- package-cpu-01：一次重度剖析，4241733 次函数调用；其 1.916 秒包含剖析开销，不作为验收时延。重复请求规范化/指纹与重复工具结果核验已对应到实际路径。
- package-bounded-read-01：回忆完成，目标查询到达 Composer 后因预算被排除；947 token 的 query 在普通历史、未保护状态之后排队。原预算2048不变。
- package-query-priority-01：仍超时，保留 ERROR。
- package-digest-01：3项中2 PASS/1 ERROR，选店 Context 已含 query，native 主动续问已发送；B回复阶段 RECALL_TIMEOUT，后续身体和清理尚未验证。

## 本次实现范围与公共影响

1. json_integration_repository：始终完整验证原 E5-A，每次读取当前字节；仅把选取单请求/尝试的投影放在复制之前，不再复制所有无关结果。新增损坏未选中记录及副本隔离反例。原数据格式、事实、写入不变。
2. temporary_tool_service：投影读取原类型请求；核验一次后返回已核验的 fact/payload，避免 `_value → read_result → query` 嵌套重复核验以及同一布尔表达式两次 `_value`。每次公共读取仍取得当前原生事实及材料；使用前后当前资格复核不缓存。待 W04-3/P16/P17 兼容验证。
3. w04_tool_fixture 的 SimulatedConnections：每次安全路径/当前字节检查；同字节复用原完整解析并返回独立副本。只作用隔离模拟端，不接真实设备。损坏与副本正式对照已加入。
4. execution_context_source：仅 entry_selective 接线使用原索引安排有界读取，候选逐个完整验证后才返回；失效候选不作为可读事实。查询材料与效果回执按职责区分选择，显式指定目标优先；不改旧默认路径、Router/Composer、冲突/权限或2048预算。查询进入最终 Context 仍不代表真实事实或强迫表达。
5. action_planning 的 `verified_digest_reads`：可选一次准备内纯值指纹复用，逐次遍历完整当前值为键；保留 RFC8785 原计算，不缓存对象身份、授权或事实核验，2048条内存上限仅约束临时纯计算缓存。只在本批 Core.prepare 开启，旧调用不启用；新增值突变、类型区别及无效值拒绝对照。冻结 hashing 原件未修改。

所有代码变化仍待最终同版验证。当前未固定最终源码，不能拼接这些中间结果为包级 PASS。原1000ms、2048上下文、P18控制/两个need、费用和原请求身份均未改变。

## 下一步

对 B 回复阶段做一次轻量逐站测量（package-reply-stations-01），据实际结果继续最小修补。必须完成完整因果链和权限/撤销/恢复，再固定源码运行专项、公共兼容和一次全量。历史 F1/H1/F2 UNKNOWN 不变，无远端 CI 证据。

## 后续定位与最终版本（原记录保留）

package-reply-stations-01：B回复1088.187ms；环境读取292次/391ms，operation155次/168.5ms，origins233次/113.6ms；Router726.86和Composer221.44为嵌套统计，不相加。按一次来源检查复用初始完整环境文档，回调后重读并比较绑定；不缓存授权。package-binding-batch-01后续错误是新增TEST错误地把单独身体更换与host代次推进混用，原OLD_HOST_FENCED正确；隔离测试改走原disable/register身体附件，再核旧身体及错误代次拒绝，未改变host语义。

w04-entry-development-01中间45PASS之后，又用两条正式查询反例验证普通UI资料绕转用问题；before为1PASS/1FAIL，repair为2PASS。新增原生UNKNOWN发送可独立新问与未知身体动作不可重放两项，同版定向通过。最终source为sha256:63b8189dda6bca9a7cb5985cfeded9e0d920aca284500d32bdded91040307261，最终结果见test-index而非这些中间标签。

辅助：续作一次CIM进程详情查询被系统拒绝，随后用已知exec会话和Get-Process核实原进程；一次Windows rg通配路径无效后改用-g。不是Engine测试失败，不隐藏。任何重度剖析/轻量计时与无插桩正式测试分列。没有为性能改1000ms、2048或减少包级负载。首次全量两处超时及后续定向最小补修另见final-timeout-investigation-02.md，不用这些较早的通过代替最终同版验证。

