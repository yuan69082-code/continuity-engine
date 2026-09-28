# 返修事实、失败及诊断限制

静态复核不是实跑。本轮施工方由原P16发现取得候选，经P08/P17/E5-A准备原请求，挂入真实P18宿主/Scheduler测试。before-02的2 FAIL证实R1/R2，运行源码仍是初交付版；新增测试文件使集合hash不同，JSON逐文件可核对运行文件未改。

## 已证实机制和最小修补

- R1：原 `native.needs(at)[:1] / pending[:1]` 重复将第一条等待提交原Scheduler。后续连接没有入队机会，第二native需求也无保证。修改为每次读取原Scheduler已拥有身份，将未入队的原native+工具需求按due_at、原priority、identity接纳最多2项。既有UNKNOWN、取消、完成都不重建任务，调度/资源/退避仍原Scheduler。没有第二队列、请求表或持久游标。
- R2：`len(closes)<3`把单次防忙循环误写成累计永久门槛。移除总数门槛，每次advance最多发出一份清理；对上一份自动RETRY_CLEANUP用原验证回执completed_at推导下一次时间。默认取原P18 RuntimePolicy.retry_seconds=5，可传正有限参数。首次显式清理失败仍保留原立即续做资格，之后自动失败按间隔。重开不清零，当前条件失效不生成新请求，UNKNOWN先查询，成功不重复。费用/效果仍原P17当前资源和E5-A回执，不重置额度、ACL或权限。

## 原始运行轨迹（均保留）

- before-01：1 FAIL/1 ERROR。夹具在宿主attach前就启用运行guard导致TOOL_VERIFICATION_REQUIRED；早期R1观测尚未跨next_check，不能单独作为充分反例。修正夹具启动顺序，沿原60秒成功间隔/5秒重查推进；没有改产品。
- before-02：2 FAIL/0 ERROR。R1第二工具CANDIDATE而不入队，R2三个失败事实后PENDING_CLEANUP，STOP正常。stdout保存STOP前任务、连接、回执、费用和宿主。
- after-01：R2通过，R1工具完成和维护完成，但新增断言在原动态需求尚未形成的短时间错误期待认知调用。按原P18测试3600秒推进后after-02两项PASS，不改动力学阈值。
- expanded-01：8 PASS/1 FAIL/2 ERROR。零秒advance被可信测试时钟正确拒绝、handoff辅助方法名错误；修夹具为零秒不推进及原handoff_test。同时存在native时的新测试遗漏旧Context版本和Action120秒授权期限：认知先提交revision后，旧工具Context正确拒绝，不是R1仍未入队。expanded-fixes-01 两项通过，第三仍因此失败。
- native-current-01 / native-diagnostic-02 / native-diagnostic-03：新步骤以当前Wake/Perception/C1生成Context，业务效果1/费用1成立；如果每步重新取宽泛Context，清理材料可能包含本轮工具使用结果。准备close后该临时结果已不可继续读取，原检查正确返回CONTEXT_CHANGED_BEFORE_ACTION，保留PENDING_CLEANUP；不将其伪报CLOSED，不放宽当前性。这是本测试新建Action生产器的材料选择问题；可复核原请求/结果和静态错误码。原通用调用方若依赖已失效Context仍会阻断，未修改或承诺自动重绑定。
- native-diagnostic-01：诊断辅助代码错误把capabilities tuple当dict（ERROR）；诊断现有类型与静态码有限兜底，不覆盖原业务异常。
- native-context-02：尝试不存在的Router purpose参数，TypeError被宿主原边界拒绝；运行实现未因此改动。该辅助尝试保留。
- native-context-03：同一当前C1 Context供新的use/close链使用，每步仍原校验，旧connect请求与事实不重绑；真实native认知和维护、后项工具效果及清理均通过。TEST授予该场景300秒租约，不是放宽原产品/旧测试时限；原Action120秒仍未改。新增正对照不代表旧Context授权有效。

额外保留：首次PowerShell花括号路径读取ParserError、几个不存在文件名的只读查找、psutil未安装的进程辅助查询ModuleNotFoundError；未安装依赖、未改Engine数据。Get-Process用于本轮进程观察。

最终验证期间，Get-CimInstance Win32_Process读取Python命令行被系统“拒绝访问”（退出1）。未调整系统权限或安装依赖，继续用原测试session、运行JSON、日志与Get-Process观察；终局进程结论据实际观察范围记录，不把辅助观察失败算作Engine缺陷。

## 结论边界

- targeted-candidate-01：13 PASS / 1 ERROR，167.785秒。新增参数拒绝测试试图读取尚未创建的隔离Fake连接文件，FileNotFoundError属于辅助检查错误；产品已经正确拒绝非法配置、没有调用端口。检查改为比较“文件不存在”这个真实前后状态，不预建成功事实、不删断言。targeted-final-01：14 PASS，167.125秒（runner），前后同版 `sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506`。两次原件均保留。

最终固定版本的完整验证由validate.py预先列定顺序，首次失败即停，不自动反复运行。原1909项测试身份与旧测试文件字节核验一致，新14项共1923项；冻结信息见frozen-source-01.json。最终完成数量只以test-index.md和运行JSON为准。

旧1909测试/断言不动，新增用例另计，所有旧运行结果只作历史。修复不代表无限量工具公平/性能保证；原Scheduler容量/资源上限、当前Context/授权/来源及生命周期仍可阻断。没有把真正未知效果变成未执行，也不因失败停止整个主体。F1/H1/F2历史UNKNOWN不归因本轮。完整回归结果待最终索引，不能从中间PASS推断。
