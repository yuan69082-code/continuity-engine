# P18 连续异常原因保留：本轮范围及验证矩阵

当前授权仅两个存储文件的异常保留处理及必要测试/证据/文档。初始源码269份与上一交付、独立复核逐文件一致，原1507身份与断言保留；未改任何此前运行修复。

## 已证实机制

原生拒绝之后，当前授权或版本检查拒绝经隐式context关联原生错误。清理再次失败时，旧代码只接续primary.cause，并在cleanup处理器内重新raise primary，覆盖原context。原生错误因此丢失。原目标字节、顶层拒绝、一次替换仍正确，未证明数据损坏/重复执行/停机。

## 最小方案

两处finally共用内部 `_retain_cleanup_error`：保留pending主异常自然向外传播，避免在cleanup处理器内重新raise主异常；原显式cause和隐式context双分支保留，cleanup自身原因不丢失。移除cleanup在处理pending异常时形成的回指；共享原因在原原因上方插入cleanup，保持原因对象可追溯且不新增循环。普通traceback可格式化，顶层仍为原授权拒绝/版本冲突/deferred/原生错误。不新增外部诊断输出。

辅助代理只读审阅未发现阻断，未运行测试；不冒称规划监工独立复核通过。已存在的恶意循环异常对象不是本轮通用修复目标，遍历使用seen保护。本轮只保证不因追加cleanup产生新循环。

## 按顺序验证

| 范围 | 验证入口 | 要求 |
|---|---|---|
| 原独立六项 | unchanged IndependentStorageFinal | 修前保留4PASS2FAIL；修后六项通过，事务资格对照仍正确 |
| 两条已证实失败及清理成功对照 | 新正式异常链测试 | native/guard或版本/cleanup均在图中，顶层不变，字节不变、替换1次、无更新历史 |
| 同类异常组合 | 新正式异常链测试 | explicit+implicit、cleanup自有cause、共享原因、deferred、正常提交、traceback与无环 |
| 原拒绝和恢复边界 | 原P18 storage/persistence/recovery测试 | 原断言保留，无重复提交/调用/扣费；没有新增运行期限 |
| P18专项 | test_p18_ | 完整运行，交集不相加 |
| 公共兼容 | 原605项兼容选择 | SubjectState/Evolution/C1/Thinking/Action/资源/调度及相关阶段 |
| 最终全量 | 原测试全部+新增 | 固定源码后一次，既有1314 SKIP单列，失败先保留不自动重试 |

历史F1/H1/F2根因仍UNKNOWN。本次诊断修复不用于反推历史唯一原因，不自动关闭EVIDENCE_CONFLICT，不登记D-073，不Git写、不P19。
