# N16：STOP CURRENT ITEM / PLANNING_CONFLICT

2026-09-29。当前状态 BLOCKED，等待用户对公共接线的决定。其余不受影响的已授权工作可继续。

原要求：原 Thinking/P08/P13 决定，当前合法授权内经 P16/P17/E5-A 投递；表达拒绝不得被绕过，也不能用每步人工审批替代已授权自主处理。

现场：`ActionService.decide` 对 CONTACT_USER 固定保留 requires_confirmation；`ExpressionPolicyService.decide` 将该标记直接纳入 denied，不读取本次已授予的精确确认再决定该标记是否已被满足。普通 C1（非 mind 分支）在 compose expression 之前执行 after_action。`entry-draft-03` 的真实 C1 隔离原始运行先产生一次模拟发送，随后 completion 校验报 C1_ACTION_HISTORY_WITH_DENIED_EXPRESSION。fixture 启用原 P13 策略，并沿既有确认端口登记具体 request id；未连接真实服务。不能将失败写成通过。

涉及位置：services/action_service.py（只读，固定判定）；services/expression_policy_service.py（请求新增最小修改）；services/continuity_interaction_service.py（已在候选范围，需确认本次执行顺序变化）。

保持全部既有要求的推荐方案：P13 将当前精确授权作为确认条件是否满足的证据，仍运行原 action gate、资源、recoverable、reality 检查；W04-4 先形成并检查表达判定再投递。无授权/撤权/拒绝继续拒绝，已成功事实不重发，合法独立内部认知不受表达失败抹除。以新旧表达/自主性/C1/恢复测试验证，不改旧断言。

代价：公共 P13/C1 接线需有正常及拒绝兼容；现有标记本身不删除，不能放开所有 CONTACT_USER。替代是停止 N16 等待方案；关闭 P13、伪造 requires_confirmation=False、把联系意图改成普通答复均不采用。

暂时措施仅在新增 W04-4 policy 内：在投递前预览原表达拒绝，拒绝则抛出 ENTRY_EXPRESSION_DENIED_BEFORE_DELIVERY。公共 P13 未修改。原日志和失败现场清理前文件摘要保留。

另有已解释的本轮问题：before-entry-01 是辅助脚本 Path 类型错误；before-entry-02 证实旧 C1 缺入口元数据接线。entry-draft-01 的超时经一次 cProfile 定位新增入口检查重复读取环境配置（184次 load，1.371秒累积），profile本身有开销且 unittest 仍 ERROR，虽profile进程退出0也不能算PASS。优化只复用相同当前字节的解析，不缓存授权，仍重新读路径/字节并返回副本；entry-draft-02 已越过回忆站，随后发现fixture未提供原 expression.emit 的授权视图，修正fixture接线后出现上述 N16 冲突。所有原件保留。

## 补充核验与证据口径校正（2026-09-29）

原段“先产生一次模拟发送”是从执行/完成路径推断，entry-draft-03仅存栈及文件摘要，未保存计数正文；不应表述成当次直接测得一次效果。该原描述保留，本段明确收窄其证据结论，不改原始日志。

confirmation-conflict-03在当前版直接记录：Action approved=True、requires_confirmation=True、精确表达确认=True、P13 PLATFORM_DENIED；新入口投递前预检使两端效果及费用均0。前两次confirmation诊断未到目标，不计PASS。详见interim-report-01及完整测试索引。

建议修改范围包含P13 decide/verify历史与当前校验、C1相关入口的表达先于外部派发；原拒绝、独立内部成长及旧事实恢复需保留。公共P13尚未改，等待用户明确决定。

