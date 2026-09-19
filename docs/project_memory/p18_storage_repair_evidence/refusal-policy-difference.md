# P18已授权两文件补修：旧拒绝行为差异需单独确认

2026-09-14。用户已确认两个运行文件范围，**不重复申请该范围**。本轮检查触发的是用户另行明确要求的条件：“若新方案需要改变固定winerror5、实际无共享占用时不重试的既有行为约束，先提出差异、理由和真实权限拒绝对照，等待确认”。因此目前保留现场，未修改运行实现或正式测试。

## 实测差异

原规划侧`IndependentPersistenceTests.test_winerror5_without_actual_handle_conflict_is_not_retried`已原样复跑。它注入固定PermissionError(errno13)、手工设置winerror5，未提供filename/filename2。当前一次替换拒绝、guard零调用，旧字节完整；原独立8项本轮全部通过，8.778秒。

只增加错误路径绑定检查，可使这个**缺少路径的具体探针**继续拒绝。但不能以此声称“无实际共享占用始终不会重试”的行为完全不变。本轮补充了带真实原生形状src/dst字段的固定WinError5，证明：

|当前可检查事实|真实读者导致失败后已释放|没有读者、固定WinError5但带完整src/dst|
|---|---|---|
|errno / winerror|13 / 5|13 / 5|
|异常绑定本次临时文件、目标|是|是|
|目标旧字节、临时提交字节未变|是|是|
|同父目录、两者为普通文件|是|是|
|目标/临时文件只读属性|均否|均否|
|当前两文件DELETE访问|均允许|均允许|
|当前共享冲突探测|False|False|

`retry-observations-01`两项观察断言通过，0.437秒。当前原writer对第二列和第三列均不在原提交内重试；第三列实跑一次替换、guard零调用。不是凭异常文本、mock类型或合成字符串作分类。

没有可靠的历史阶段证据可让存储层只为第二列重试、又保证第三列永不重试。文件绑定、字节、属性和访问检查可以约束**现在是否允许有限尝试**，不能证明此前一定发生过共享冲突。

## 必须单独确认的具体规则

拟采用：仅在已明确启用P18重试授权的作用域内，错误确切绑定本次自建临时文件及目标、临时身份/内容与目标旧字节完整、路径/属性及必要当前访问条件允许时，对特定Windows替换错误允许同一提交的有界重试。名称为“当前条件允许有限重试”，不是“已经证明共享冲突”。

这意味着：**带完整有效操作绑定、当前条件全部允许的固定WinError5，也可能进入有限尝试，随后在持续拒绝时按上限失败**。它不再保证只调用一次替换或guard零调用。这是本次需要用户确认的行为差异。

缺少本次操作绑定的原固定错误探针仍应一次拒绝、guard零调用，原规划探针保持原样。无显式重试授权的公共旧路径继续原行为。不会按异常是否由mock产生来区别处理，不绕过原`os.replace`以假装该探针通过。

确认后仍保持：目标/临时字节与文件身份检查、CAS及当前授权、等待上限；普通权限/属性拒绝、路径/磁盘错误和损坏真实失败；不重复模型、动作、扣费或revision。两文件范围不扩大，不改变权限/计费政策或状态格式。

## 真实权限及属性拒绝对照

只在自建隔离Temp中，原生`os.replace`、无共享读者、无mock，完成五个OS观察。`independent/acl-access-02.json`，exit0、0.056秒：

|条件|原生替换|访问观察|
|---|---|---|
|正常文件|成功|当前DELETE允许|
|目标READONLY|拒绝errno13/winerror5，字节不变|目标、临时、父目录DELETE相关探测仍全部成功|
|临时文件READONLY|成功|不能把它虚报成Windows必然拒绝|
|目标DELETE与父目录DELETE_CHILD实际DACL拒绝|拒绝13/5，两文件字节不变|目标及父目录相应访问拒绝|
|临时DELETE与父目录DELETE_CHILD实际DACL拒绝|拒绝13/5，两文件字节不变|临时及父目录相应访问拒绝|

因此只检查DELETE可打开还不够，目标只读属性必须单独检查。普通实际权限拒绝仍应拒绝，不按winerror5直接重试。上述为五个实验观察，不是Engine正式回归5 PASS。

`acl-access-01`首次辅助检查exit1、0.051秒：DACL恢复调用成功，但整个安全描述符hash因继承控制位不同而未相等；原错误保留。`acl-access-01-cleanup`exit0、0.038秒：核对原DACL权限条目相同、有效权限恢复，仅SE_DACL_AUTO_INHERITED位变化；随后仅回收本次自建Temp。第二轮权限条目与属性也恢复，自建根已清理。不冒称安全描述符原始字节完全相同；没有修改正式数据或其他目录权限。

## 原流程与走时对照

`original-flows-before-01`：4项=2正常PASS、2受控读句柄FAIL，0ERROR/SKIP，79.248秒。原流程、断言和25秒观察期限保持；两条有效FAIL保留真实winerror5及STOP前现场。这是修前复现，不是修复失败或新增运行改动造成的回归。

`advancing-clock-before-01`：相同受控占用，另设可信测试时间以1倍现实时间持续推进，2/2 PASS、28.540秒。原冻结时钟反例未修改。这说明当前两个受控场景可在查询/退避到期后恢复，并不证明原提交即时重试缺口已修复，也不证明常规走时必然永久死锁。

此前F1/H1/F2历史原始系统现场仍不足，不能唯一归因或合并结案。原1480正式身份和267源码/测试/资源保持不变，上一轮全量仅是历史引用；本轮没有修后专项、兼容或全量结果。

## 下一步与停止位置

等待用户确认上述**拒绝行为差异**后，再按已授权两个文件实施。此前“两文件范围尚未授权”的记录是历史，不再构成暂停理由；本次仅依据用户关于旧拒绝行为的单独确认条件暂停，不是因为调查轮次结束、暂未复现或对照通过而停止。

确认后依次执行同反例、正式新增回归、真实走时/冻结对照、权限/版本/控制、R1/R2及P18专项、受影响公共兼容，最终源码固定后一次全量。当前未改运行源码，不为等待期间机械重跑整套全量。

P18 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT；不D-073、不验收、不Git写、不P19。精确身份及文件范围见[audit-02.json](audit-02.json)、[pending-files-02.md](pending-files-02.md)。

## 可复跑命令

使用未占用标签；设置PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONPATH=src：

```powershell
& 'E:/Adobe/python.exe' docs/project_memory/p18_storage_repair_evidence/run.py review-old-boundaries-01 --review-class test_prior_boundary.IndependentPersistenceTests
& 'E:/Adobe/python.exe' docs/project_memory/p18_storage_repair_evidence/run.py review-observations-01 --review-class test_retry_observations.RetryObservationTests
& 'E:/Adobe/python.exe' docs/project_memory/p18_storage_repair_evidence/run.py review-process-baseline-01 --review-class test_process_inherited.baseline_suite
& 'E:/Adobe/python.exe' docs/project_memory/p18_storage_repair_evidence/run.py review-advancing-01 --review-class test_process_inherited.advancing_suite
```

权限实验脚本使用专门唯一标签，不重复运行默认已有标签；所有原始stdout/stderr/result及归档原件hash完整保留。辅助脚本/探针不是正式Engine总数增长；集合交叉不相加。
