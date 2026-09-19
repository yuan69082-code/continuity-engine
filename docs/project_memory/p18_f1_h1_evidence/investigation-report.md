# P18 F1/H1 定向调查：已取得当前反例，公共实现修改等待确认

本地日期2026-09-14。P18仍为IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT。不是验收、结案或新阶段开工。当前只新增隔离探针、证据及档案；没有修改运行源码或正式测试，不登记D-073、不执行Git写操作、不进入P19。

## 本轮证实的机制

### H1同流程：资源等待发布被短暂查询读句柄打断

`JsonRuntimeRepository.load`直接读取checkpoint；查询读者不取得写事务锁。Windows普通读句柄不允许删除共享时，会阻止原子替换。测试通过握手让实际仓储读者保持句柄，原`os.replace`返回PermissionError、errno13、winerror5；没有伪造系统异常。旧checkpoint字节/hash完整保留。

当写入WAITING_RESOURCES失败后，`PersistentRuntimeService._tick`捕获异常并再次观察为BACKOFF/WORK_PORT_UNAVAILABLE。短读句柄此时已释放，第二次写入成功，`next_check_at`变为当前可信时间+5秒。时钟停在09:01:00，观察期限内不会重新计算，原资源等待断言超时。

当前反例现场：revision1主体、token_used0、compute_remaining999、1个QUEUED认知任务、0个UNKNOWN、运行checkpoint revision4/observations2、last_time09:01:00/next_check09:01:05、宿主仍活着。没有模型调用或世界效果。与历史H1清理前可推知的剩余信息一致。

真实进程验证沿用原`test_resource_wait_host_lives_and_restores_without_message`及25秒超时，只有普通读者交错受到控制。有效记录`h1-original-process-before-03`，28.472秒、1 FAIL/0 ERROR。STOP前完整现场及替换错误已保存，随后STOP退出0、未强制清理。

历史H1存档与当前`JsonRuntimeRepository.load/save`的函数AST完全相同，见[身份核对](historical-runtime-functions.json)。这证明该路径历史已存在，**不证明当时一定就是该句柄**；旧现场没有原系统码、读者身份或BACKOFF活动，不能补写。

### F1同流程：短占用已解除时，现有写入分类不允许原提交继续

现有F2补丁仅在`_replace_contended`当前DELETE探测仍返回共享冲突32/33时重试。当真实读者使替换返回winerror5，然后在探测之前关闭，探测成功，分类返回False，原提交退出。这个交错与“从未发生竞争”不同，当前实现未能利用已解除的可写条件继续同一提交。

第二轮正常Provider已返回，ThinkSession COMPLETED/RETURNED、Context有效、Action与原能力回执存在；SubjectState写入未提交，仍revision2。任务UNKNOWN，宿主WAITING_VERIFICATION，token_used640/compute_remaining994，可信时间10:02:00，下次检查10:02:05。普通固定时钟观察不推进水位，原暂停/恢复用例超时。

定点记录`f1-classification-before-01`保留真实errno13/winerror5、旧文件hash、分类False；推进到查询水位后沿原请求恢复revision3，Provider仍两次、token仍640、世界效果/credits仍0。**这一步仅证明原事实恢复有效，不作为缺陷已修复**；断言仍检查读者释放后的原提交不应滞留，因此该反例仍FAIL。

真实进程验证沿用原`test_idle_and_subject_silence_do_not_end_process`及25秒观察期限，有效记录`f1-original-process-before-02`，34.111秒、1 FAIL/0 ERROR。STOP前原系统码、状态/会话/Action/能力/时间及任务均保存，随后STOP退出0。

该现场与历史F1的控制修订5/6、运行revision8、token640、任务due09:02、第二维护due09:01、UNKNOWN及10:02:05水位高度吻合。F1缺失原会话阶段与异常链，**仍不能唯一归因，也不能排除当时其他持久化或处理异常**。

## 区分证据与假设

|问题|已证实|仍缺失或未证实|
|---|---|---|
|当前H1同流程|实际读句柄→checkpoint替换WinError5→BACKOFF水位→原期限超时|历史那次是否由该读者引起|
|当前F1同流程|实际读句柄→替换WinError5→读者先释放、分类False→原状态未提交→UNKNOWN；到期原事实可恢复|历史F1原异常类型、调用阶段及读者身份|
|历史F2|上一轮已证实当前SubjectState读句柄竞争机制并补修；本轮发现已解除占用分类的剩余窗口|历史F2缺原系统码，不能直接认定与F1/H1是同一事件|

共同的**当前风险族**是Windows短读句柄与原子替换，以及失败后水位在冻结时钟下无法自然到期。具体失败文件及恢复分支不同，不把三次历史失败合并成一个已结案问题。当前通过的六个时钟交接点、正常进程对照，只排除那些实际试验条件；未证明所有时钟交错、测试污染或外部进程干扰均不存在。

## 本轮实跑（集合有重叠，不相加为正式总数）

|标签|结果|runner秒|解释|
|---|---|---:|---|
|hypotheses-before-01|3项：2 PASS、1 FAIL|16.476|F1六个时间交接子用例归属1项；H1正常对照通过，真实仓储读者反例失败|
|f1-classification-before-01|1 FAIL|3.801|真实SubjectState读者释放后的分类窗口；包含随后到期恢复正向核查|
|h1-original-process-before-01|1 FAIL|1.263|辅助脚本缺tests导入路径，子进程ModuleNotFoundError，不计Engine缺陷|
|h1-original-process-before-02|1 FAIL|28.445|辅助短路径/完整路径relative_to错误，不能作为文件竞争有效反例|
|f1-original-process-before-01|1 FAIL|33.954|同一辅助ValueError，不能作为文件竞争有效反例|
|original-process-controls-01|2/2 PASS|17.834|原两个真实进程测试，无注入、无改断言|
|h1-original-process-before-03|1 FAIL|28.472|有效：实际WinError5、完整握手、原H1断言超时|
|f1-original-process-before-02|1 FAIL|34.111|有效：实际WinError5、完整握手、原F1断言超时|

所有标签均FINISHED，独立输出JSON/stdout/stderr没有覆盖，当前各次源码运行前后与开工267文件一致。本轮没有新增正式测试身份、没有改原1480项断言，没有跑全量、专项或兼容整组。上述受控FAIL不是“新改运行代码引入的回归”。

上一轮完整回归1480项=1479PASS+1既有Win1314SKIP、1284.129秒，仅引用[p18_persistence_evidence记录](../p18_persistence_evidence/final-report.md)，不冒称本轮通过。它也不能覆盖本轮新反例。R1/R2已验证成果原样保留，但未在本轮重新跑完整返修矩阵。

## 范围确认与下一步

最低必要的运行实现修改拟涉及公共`storage/json_repository.py`与P18专用`storage/json_runtime_repository.py`，详见[待确认方案](proposed-change.md)。前者是公共模块，按本轮用户“公共实现修改须先确认”的要求，**此处保存进度并等待明确确认**。不是因调查轮次结束或当前对照通过而结案。

确认后才实施最小修复、将有效反例纳入正式测试并验证。目标是有依据的有界同提交重试、CAS/当前授权检查；不把未知动作重新派发、不放宽超时、不改变资源计费、不重构其他模块。需要证明同反例修后通过，再跑受影响兼容与最终全量。

## 复跑入口

在Engine根设置`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=src`，使用未占用标签：

```powershell
& 'E:/Adobe/python.exe' docs/project_memory/p18_f1_h1_evidence/run.py review-hypotheses-01 --review-class test_hypotheses.Hypotheses
& 'E:/Adobe/python.exe' docs/project_memory/p18_f1_h1_evidence/run.py review-h1-process-01 --review-class test_process_hypotheses.OriginalFlowWithReadOverlap.test_resource_wait_host_lives_and_restores_without_message
& 'E:/Adobe/python.exe' docs/project_memory/p18_f1_h1_evidence/run.py review-f1-process-01 --review-class test_process_hypotheses.OriginalFlowWithReadOverlap.test_idle_and_subject_silence_do_not_end_process
```

这两份探针仅放在本证据目录`independent/`，不是规划侧原件，也不是Engine正式发现集的增长。必须使用明确测试方法，避免继承类重复统计。当前预期相应反例FAIL；未经修复不预填PASS。

辅助读取曾出现路径通配不适用、猜测的诊断文件不存在、编码名utf8-sig不识别及摘要字段stage缺失的KeyError；均是本轮辅助错误，不计为Engine行为缺陷。进程辅助错误的原始输出及修正过程完整保留。早期辅助脚本未另存每版hash，不冒称已事前固定其所有版本；最终探针及全部原始输出hash见本目录审计。

原始历史材料身份见[historical-identities.json](historical-identities.json)，开工身份见[before.json](before.json)，本次范围/保护/进程与精确清单见[audit-02.json](audit-02.json)和[pending-files-02.md](pending-files-02.md)。当前EVIDENCE_CONFLICT继续PRESENT，不接受遗留风险、不关闭F1/H1。
