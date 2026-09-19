# P18 连续异常保留修补：施工内部范围核查

本记录属于施工内部只读技术核查，不是规划监工独立复核、用户验收或阶段阻断关闭。本次核查未运行测试，测试结果须以各运行原始记录为准。

## 核查依据与身份

- 逐行比较本目录 `source-before/json_repository.py`、`source-before/json_runtime_repository.py` 与当前对应运行文件。
- 两份修前副本的 SHA-256 分别为 `a690a30ccb69a99d74d3db95330fd66ae01102ec93dd1f30e2128531c6ecd0ae`、`07de845cbe14b284dac93e4059a074435a2dcbe4511f10f657c6355bd0a27acc`，均与 `before.json` 一致。
- 当前 270 份源码、测试及资源文件逐文件 SHA-256 与 `frozen-source.json` 一致，未发现漂移。该冻结清单登记总指纹为 `sha256:e56fcd1d6e2f6d467a708b72866c807eca536fece20af9e881d2a23aba30cfec`。
- 相对修前 269 份清单，仅两个已授权运行文件发生变化，另新增 `tests/test_p18_storage_exceptions.py`；没有删除原文件。
- 修前清单中的 90 个测试文件当前字节全部一致。原 1507 个正式测试身份与冻结清单中的原身份集合及顺序完全一致，无缺失；新增 10 个身份单列，当前合计 1517。

## 实际运行差异

`src/continuity_engine/storage/json_repository.py` 仅新增 `_retain_cleanup_error`，并将临时文件清理失败分支接到该内部辅助函数。`src/continuity_engine/storage/json_runtime_repository.py` 仅导入同一辅助函数并替换对应清理失败分支。

原先在清理异常处理器内再次 `raise primary from cleanup` 会改变主异常的隐式上下文。现在让已经挂起的主异常继续原来的传播过程，并在内部异常图中接续清理错误：保留原显式原因、隐式上下文及清理错误自身原因；去除指回原主异常图的反向上下文以避免新增循环；共享原因采用在其上方接入清理错误的方式保留原因对象。

主异常对象仍作为顶层拒绝传播；不存在主异常时，清理失败仍按原行为抛出。该辅助函数只处理异常关联，不打印或持久化任意异常正文，没有改动原对外脱敏出口。

## 未改变的行为范围

逐行差异显示，下列逻辑本轮未改：

- 有限重试资格、固定等待预算、每次当前授权及文件身份/内容/版本/路径检查。
- 原生替换操作、临时文件准备与原子提交，不改 ACL、只读属性或写入手段。
- checkpoint 事务锁、owner/generation/control 绑定、revision 与 CAS 检查。
- PAUSE/STOP、Provider、Action、资源计费、原事实恢复及持续运行控制。
- 未新增运行时长、tick/思考次数、无消息或概率性退出规则。

这里确认的是修改范围和源码身份，不能替代正在执行或后续完成的行为回归。历史 F1/H1/F2 的原始系统证据缺失仍然存在，本次修补不能反推其根因。P18 继续为 `IMPLEMENTED_NOT_ACCEPTED`，`EVIDENCE_CONFLICT=PRESENT`。

## 核查过程说明

只读文件比较及 SHA-256 核对没有执行 Git 写操作或启动测试进程。较早一次只读 `rg` 调用因 Windows 路径通配写法返回辅助错误 123，改用文件筛选参数后读取成功；该错误不是 Engine 行为测试失败。

主代理补充只读核查：src中显式读取cause/context的其他位置限于P18 TEST诊断与P16 TEST故障识别；RuntimeCognition、PersistentRuntimeService和Native Wake业务接线不通过异常原因链授予执行或改变恢复资格。当前补丁不增加外部日志出口，顶层拒绝对象/类型保持。该项是源码读取结论，非新增实跑测试。
