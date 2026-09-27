# W04-2 公共验证定点处理完成报告

状态 IMPLEMENTED_NOT_ACCEPTED，交独立复核。用户本次已授权P18测试同步与历史回执选择修补；此前对应工程选择已解除等待，无新PLANNING_CONFLICT。EVIDENCE_CONFLICT=PRESENT表示本轮证据尚待独立确认，不自行验收或关闭复核门。W04-3未开工。

## 根因、范围与实际变化

1. **W02（保留前轮修补）**：外部注册仓储每次路径安全检查对同一文件/祖先做三次元数据查询；_safe已合为一次当前lstat。当前源码该文件与本轮开工基线完全一致；D-084原读取复用实际有效，未删除授权、来源、版本、损坏检查或复制隔离，原1000ms和材料不变。两种原负载、五个原失败场景在正常正式测试中复核。旧cProfile四份场景超时仍是保留的重度观察结果，不把它算通过，也不新增对所有插桩条件的1秒保证。历史五次瞬时差异不能全部唯一归因到该机制。
2. **P18测试时序**：两个独立占用区间应分别报一次BUSY；owner存活不等于attach事务已完成。只改tests/test_p18_runtime_contention.py获准两项及必要测试辅助，产品实现未改。真实子进程通过原runtime.main启动，TEST hook在原事务释放后发attach标记；两次真实PAUSE/STOP占用分别严格核对一条BUSY及解除后一条AVAILABLE。STOP用同一身份，在原15秒控制观察期限（含退出）内只重试RuntimeCheckpointBusy；每次忙时核对未提交，成功后检查幂等、终态、无效果/费用/revision重复、重启不复活。新增3项稳定覆盖attach持锁STOP拒绝、实际忙后释放再重试、非忙错误立即透传。未改0.25秒、owner、CAS、权限或主体寿命。
3. **W04指定回执**：旧history_context只按对象检索，两个同根回执同分时按ID排序，2048预算保留一个，恰好裁掉目标就正确拒绝返回。正式双目标反例正反序证实。只改device_operation_service.py与execution_context_source.py：用原Router查询身份绑定指定请求的固定长度摘要；来源仍从原E5-A取当前可核验结果，先选指定目标，并只提高其查询候选评分，其他候选评分/冲突/根材料保持；原Router排序及Composer核心保护、去重、裁剪、2048预算继续执行。目标本身装不下仍拒绝；过期、撤权、途中撤权、材料撤回仍返回原静态拒绝。普通未定向查询保持原评分与入口，无跨请求缓存/第二账本。

新9项历史选择测试经过实际query动作回执、DeviceOperationService、Router、Composer入口，包含目标互换和不同合法ID、重开/重复、预算不足、失权/期间失权/过期、同根撤回及原非定向路线。只读检查使用持久树hash、状态revision、效果和费用对照；没有以其他同根回执冒充指定目标。

## 同版结果与来源

固定源码/测试/资源316项：`sha256:bee6fabd77fcdad99521ddaefdb1bf9166bc0b908b418e485fa998eb5fed53b5`；1863项正式身份，原1851项保留，新增12项（历史9、P18受控3）。原两项测试是本次用户明确批准的同步及区间断言修正；原全文与hash在baseline及before.txt，其他旧正式断言未改。

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-01](targeted-final-01.json) | 32 / 0 / 0 / 0 | 118.793 / 119.595 | 0 |
| [recall-formal-final-01](recall-formal-final-01.json) | 5 / 0 / 0 / 0 | 56.436 / 57.056 | 0 |
| [recall-load-final-01](recall-load-final-01.json) | 2 / 0 / 0 / 0 | 32.868 / 33.394 | 0 |
| [special-final-01](special-final-01.json) | 87 / 0 / 0 / 0 | 173.939 / 174.726 | 0 |
| [compatibility-final-01](compatibility-final-01.json) | 417 / 0 / 0 / 0 | 692.998 / 693.718 | 0 |
| [full-final-01](full-final-01.json) | 1862 / 0 / 0 / 1 | 2012.898 / 2013.912 | 0 |


这些集合交叠，不相加。完整回归的唯一SKIP为原Windows符号链接权限1314，原始原因见stderr；无新增SKIP。完整回归仅此一次，之前没完成/失败/插桩记录不会升级为PASS。规划窗口只读复核不冒称独立实跑。

## 范围和限制

历史F1/H1/F2根因仍UNKNOWN，原验收不撤回，也不因本次通过唯一归因旧失败。本机隔离TEST证明所覆盖工程链；其他设备、更大负载、真实语言效果、生产性能、真实设备/账号均未验收。W04-3/4、W05、P19及生产恢复/接入按原阶段未开放。没有远端CI证据；本轮没有远端查询或Git写操作，不把本地origin/main当实际远端。

[逐项矩阵](matrix.md) · [原始测试索引](test-index.md) · [固定源码与身份](frozen-source-01.json) · [精确清单](final.pending-files.md) · [终局审计](final.audit.json) · [进程清理](process-cleanup.json)。所有原始失败与辅助错误原样保留。下一步仅为独立复核与用户确认。
