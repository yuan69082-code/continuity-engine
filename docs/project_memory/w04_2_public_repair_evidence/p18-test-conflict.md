# P18 两条原测试的可复现时序冲突：STOP CURRENT ITEM

状态：PLANNING_CONFLICT=PRESENT（仅此测试同步/断言适用区间），等待用户决定。原实现和原测试均未修改。

## 原意与证据

原意是一个连续占用区间只报一条BUSY；控制锁有限等待0.25秒，拿不到锁明确拒绝，不假报STOP成功；宿主等待而非退出。两条原测试却对整个进程生命期总BUSY断言恰好1，并将owner锁已持有当成checkpoint已空闲。

- 原未插桩失败见 ../w04_2_evidence/compat-failure-01.json；历史只有两对BUSY/AVAILABLE、STOP忙及最终exit0，缺少当时锁时间，不能唯一归因。
- 本次原样带时序测量两项PASS，见 locks-profile-01.json。
- 有界受控对照只将真实事务内保存延迟0.40秒，原断言和0.25等待不改。结果1 FAIL/1 ERROR，见 locks-controlled-01.json、同名stdout/stderr、locks-controlled-01-traces.summary.json。不是把注入延迟当历史实测耗时。
- 第一项：PAUSE控制pid200持锁1917.538—4251.316ms（2333.779ms）；宿主20068在该段多次申请只报一条BUSY。其后STOP控制pid21932持锁4299.227—4725.302ms（426.074ms），宿主再次等待报第二条BUSY。两个区间中间实际取得并释放过checkpoint锁。STOP持久到revision6，宿主正常exit0。若压成总数1，会压掉第二次真实竞争，违反不压诊断要求。
- 第二项：宿主16768已取得owner锁，但HOST_ATTACHED的checkpoint事务持续7351.485—7789.285ms。控制器7399.330ms发STOP，7664.159ms报RuntimeCheckpointBusy，没有写入该命令。原清理流程稍后重新提交STOP并在8228.199ms持久化，宿主exit0。owner存活不证明控制锁可用；把单次STOP强行变成功只能越权写入或扩大等待。

## 建议最小差异与影响

建议只修 tests/test_p18_runtime_contention.py 两处测试控制器：

1. 在指定held_control占用期间单独检查BUSY去重，释放后确认恢复；允许后续独立STOP事务有自己的BUSY/AVAILABLE，并逐区间核对，不能简单删除去重断言。
2. start等待用例以明确的checkpoint attach完成握手后再STOP；若仍遭后续事务竞争，在原控制器总观察期限内用同一STOP身份有限重试，每次失败核验未提交，成功核验终态且不复活。不得改变产品0.25秒、CAS、owner或revision语义。

新增稳定受控回归保留上述两个交错，证明不依赖偶然快速I/O。原始断言及失败原件作为历史保存。公共运行实现暂不改；不是建议吞掉BUSY。维持原测试绝对断言会把合法不同区间或正确有限拒绝当失败；改产品来迎合则影响权限/安全/持续运行。用户未确认前不改原测试、不宣称公共验证闭合。W02独立调查继续。
