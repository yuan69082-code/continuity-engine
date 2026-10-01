# 首次最终全量的两处超时：事实、定向测量与最小补修

本文件记录D-092范围内的继续施工，不是验收，也不解释历史F1/H1/F2。原1000ms/2048、场景负载和原断言未更改。

## 已证实的事实

- 冻结版2e910dd2…的full-final-01为1969 PASS/1既有SKIP/2 ERROR；两处B回复RECALL_TIMEOUT。此前49/196/1144 PASS分别属于该版的其他集合，不能抵消全量失败。
- 预先限定的full-errors-stations-01各执行原失败场景一次：UI正常链PASS，855.962ms；包级ERROR，记录elapsed_ms=1098.926、retrieved_count=17。原生模型/外部调用不在回忆准备内补做。
- 包级Environment读验256次/390.091ms、operation读取161次/189.123ms。Router770.249、授权89.087、Composer238.457为嵌套计时，不能相加。观察记账约2.662ms，GC约0.034ms。
- 为回答“环境成本来自哪里”，另一次预定单场景full-errors-copy-stations-01记录Environment路径lstat4777次/304.570ms、环境副本39.324ms、journal副本217.692ms；该统计覆盖B回复入口，范围比内部回忆更宽，不能逐数相减。仍ERROR，不算通过。
- 32次受控只读path-metadata-comparison-01，在实际TEST层级17个组件上，lstat25.498ms、Windows当前GetFileAttributesW7.032ms（原JSON为精确值）；当前reparse判定一致，缺失文件独立对照。微测量不冒充整轮回应时延。

## 修改及为何没有缓存授权

1. `storage/json_environment_repository.py`：Windows路径检查每次逐组件调用GetFileAttributesW，取真正需要的reparse标记，不获取未使用的整份stat字段。仅系统FILE/PATH_NOT_FOUND按原缺失处理；访问拒绝及其他系统错误继续抛出。非Windows保留lstat。目录/文件逐次检查、当前内容读取、完整封套校验及私有副本、后续当前权限回调均保留。无ACL、只读、提权或文件写入绕行。
2. `services/cross_entry_service.py`：来源追溯从完整校验后的原operation记录投影request/entry/根Event及Evolution身份，再复制需要的字段；不先复制无关的完整逐站记录和感知正文。原日志仍每次读取当前字节，任何未选中损坏记录仍拒绝，投影不可写回，没有新账本或授权缓存。
3. `tests/test_w04_4_boundaries.py`新增真实TEST junction、访问拒绝（故障注入）及日志完整性/副本隔离对照。其他原有测试不变；原UI/包级原方法、负载、断言不变。

本次证据证明重复元数据和副本构造是当前可减少的成本，并保留了同负载超时反例。不声称已取得首次全量运行中每一次系统调用的计时；不能把当前优化反推成历史F1/H1/F2根因。正式时延结果必须以补修后新的固定源码测试为准。

## 预定验证顺序

先一次正式五项：三个新边界及原两个失败场景；失败先分类，不自动重试。通过后冻结新版本，跑全部新定向、W04专项、原已列公共兼容和完整回归。全部旧最终标签原样保留，新标签final-02。完整回归不得在源码修改期间进行。

在最终组前，另做一次相同双场景轻量测量作为改善对照；它不代替正式测试。若正式组再出现失败，保留现场并调查，不自动启动下一轮全量。

## 首次补修验证及新测试辅助错误

full-errors-repair-01为3 PASS/2 ERROR：原UI及包级场景均PASS，来源投影对照PASS。两处ERROR来自新增测试把正式C1入口的IntegrationExecutionError误写成内部EnvironmentAccessError/PermissionError；原栈明确保留W04_STORE_LINK_FORBIDDEN与WinError5，且均在binding阶段拒绝。未改产品异常语义。测试修正为同时核验外层、原原因类型/码、无operation及零效果，正常解除后仍成功；full-errors-guards-02三项PASS。原错误原件保留，不写成产品绕过拒绝。

## 限制

修后预定轻量对照full-errors-stations-after-01为2 PASS，退出0：UI包裹准备787.441ms，包级827.428ms；同版63b8189d…，没有减少原场景。包级Environment256次/202.192ms、operation160次/126.381ms；修前161次含失败记录保存，多出来的一次不能算检索工作被删除。这里是嵌套诊断值，不能相加或当成整轮回答耗时。正式targeted-final-02为52 PASS，w04-final-02为199 PASS，二者前后源码一致；公共兼容和全量仍以各自完成汇总为准。

更大或其他机器负载仍可能触及1000ms。超时继续阻断未完成必要核验的回应，不先答后查。性能不是生产承诺，未知来源或撤权不会因优化放行。最终结果与状态以最新test-index和final-report为准；这些文件尚未生成前，本文件不是通过声明。
