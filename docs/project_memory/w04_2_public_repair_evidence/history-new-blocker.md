# 新发现：W04-2 定向历史查询被其他同根回执挤出 Context

状态BLOCKED / EVIDENCE_CONFLICT=PRESENT。不是本轮_safe修改引入的调用行为；尚未授权扩修此新问题，运行实现和原测试均保持。

原special-final-01同根重复查询用例ERROR，第一次失败的临时根由原测试清理，缺少当时Composer明细。随后只做预定一次带诊断原样运行history-diagnostic-01，通过但显示2048 token预算只能留下两个各931 token回执中的一个；另一项被CONTEXT_TOKEN_BUDGET_EXHAUSTED裁剪。是按原排序选择，不是同根去重（deduplicated_count=0）。不能用这次通过关闭旧失败。

为避免随机身份决定通过/失败，预定history-pair-01在同一隔离根真实执行两次query后，各只读查询一次两份当前有效回执的Context。保留原2048预算、原排序和原权限/账本：第一份RETURNED，第二份DEVICE_HISTORY_CONTEXT_NOT_READY。两次组装中的唯一差别是要求的目标回执ID，得到相同全局排序；后一个目标被预算裁剪。返回前必须存在本次requestId的检查正确阻止了伪完成。

证据：[定向双查询](history-pair-01.trace.json) · [原始结果](history-pair-01.json) · [首次专项失败](special-final-01.stderr.log) · [一次原样诊断](history-diagnostic-01.trace.json)。前后revision=1、效果=0、费用=0；这条链外部注册仓储_safe调用0次，排除本轮单一运行文件改动直接造成此选择变化。W04-2原文件本轮字节未改。

代码：DeviceOperationService.history_context（device_operation_service.py:260）给Router传对象词，未表达具体目标回执的选择优先级；Composer维持预算正确裁剪，随后history_context要求该目标必须存在。执行结果同分时稳定ID参与排序，而请求ID来自不同运行身份，因此测试结果可能变化。

需协调的最小范围：仅此W04-2历史查询接线及必要正式回归（候选device_operation_service.py、execution_context_source.py，需先核对能复用的原Router选择契约）。让本次明确查询的回执与其根材料优先进入原Router/Composer，保留其他冲突/来源和原预算，放不下仍明确阻断。不得接受任意同根旧回执冒充本次结果，不扩大预算或削弱断言。原公共Router/Composer权威、权限与E5-A事实保持。

本轮授权针对W02超时与P18锁；新错误是W04-2自身组装缺口，已保存可复现证据。请求用户确认上述定向补修范围，未确认前不自行修理、不启动最终全量以碰运气。
