# P19 前 R1—R4 返修实现与限制

本批次是新的返修，不改变 P00—P18 已验收历史。P19—P23 未开工。当前等待验证及独立复核，不自行验收。

## R1：分别记录内部提交与外部事实

CoreDecisionPolicy 先形成可追溯意图，执行仍由原 ActionPlanning/E5-A、当前权限、确认、资源、恢复与现实边界决定。P14 心智上下文下，已登记的外部等待/拒绝不再直接中断独立内部 Evolution；ThinkSession、Action 授权、当前 Context、revision/CAS、主体生命周期仍核验。native 首次写入及存储重试也复核当前内部状态权限。

含联系/工具意图的混合 Thinking 提案，只将 Engine 依据已绑定 Context 生成的心智及成长提案纳入这次内部授权。其他模型提案完整保留在原 ThinkSession，不能凭执行前提案宣称效果已经完成；后续须依据核实结果重新评估。Provider 不得伪造内部心智/成长字段。原无心智路径不享有这项分离。

内部 revision 前进后，对原 choice/request 的恢复只查询原事实，不豁免 Context 以重新执行旧动作。Scheduler 回执仅证明认知机会已完成，不声称世界效果成功；世界 UNKNOWN 留在原 E5-A/Outbox。内部已提交不代表外部成功，也不应长期占用认知队列。既有 Outbox 仅投影 E5-A 请求，未确认的同能力/目标效果阻止通过新认知身份重新投递；不新建请求账本。投递容量耗尽不阻断独立内部提交，实际效果仍拒绝。

## R2：名称不是风险依据

删除 critical 子串启发式。最低风险仍由原 ActionType 决定，USE_TOOL 保持 HIGH，显式更高风险保留，确认/权限/资源不放宽。read-only 等名字也不是可信资产属性。tests/test_action.py 原 critical-admin-tool 预期由 CRITICAL 更正为 HIGH；原测试身份和拒绝断言保留，新增显式 HIGH/CRITICAL 的等效保护与 ordinary/critical/noncritical 改名对照。旧代码和断言保留在开工 HEAD 与 before.json 指纹，独立原件未改。

## R3：经历生成的内部理解与跨轮 Will

使用原 Composer 可消费的结构化 experienced 材料。相同对象/期待下，至少两个当前独立根可以形成可修订的 TRUST 或 DOUBT 理解，记下根及理解依据；重复召回不是第二经历，单次经历和情绪累计不制造 LOVE/HATE。当前撤回或无法重新消费的来源不再作为本轮支持；已形成的主观倾向及历史保留，Will 增加当前支持不足的复议理由。遗忘/检索预算缺失不抹掉主体判断，也不等于旧事实为假。

原 Will 的承诺与支持进入下一轮；当前 Episode、疲劳、冲突继续参与反向理由。无关新经历不重置承诺；相关的新矛盾可改变承诺及 QUESTION/seek-understanding，相反解释共存。正常 C1→Thinking→Action→Evolution 持久化，重启读取同一主体。沿用现有字段；不新增正式隐私/人格政策，不扩大四字段 Learning 固化授权。

这是现有结构化经历词汇的确定性生产者，并非任意自然语言心理理解或生产人格策略。当前来源预算不足可保守地提示既有倾向缺乏本轮可消费支持；不删除历史判断，也不将缺失片段升级为完整证据。

## R4：有依据的复议，不以驱力饱和替主体停止思考

RuntimeCognition 同时考虑驱力变化与已有未决关注/有效 Will。相同 revision/心智根保持稳定任务身份；常规复议沿用最低间隔，全部处于 hold/DEFER/rest 时使用四倍间隔，明确结束且无活跃欲望不触发复议。Scheduler 只收到身份/类别/到期/优先级，不编造心理内容。

持续运行没有期限、轮数、聊天依赖或随机结束规则。预算不足局部等待，控制入口仍有效；恢复后重新评估同一合法需求。STOP/生命周期、真正 UNKNOWN、单宿主/锁/幂等保持原边界。真实进程测试通过显式 TEST 时钟推进观察，到点由控制器 STOP，不把测试时限写进运行寿命。

## 证据分类

修前：independent-before-01 为诊断输出而非正式 PASS 计数；r1/r2/r3/r4-before-01 为正式反例。分项和组合结果见各唯一标签 JSON 与 stdout/stderr，后续通过不覆盖首次失败。

辅助问题：只读路径/glob 读取错误、一次读取证据未指定UTF8、一次补丁上下文不匹配；新增测试 RuntimeNeed.task_id 应为 identity、正常接线测试未持有 owner，均保留工具/运行记录并修正测试设置。runtime-extended-01 的资源额度假设忽略原预留规则；进程在冻结 TEST 时钟的维护任务后，尚未到 next_check_at，清理前完整诊断显示已入队、宿主存活并接受 STOP。修正为真实耗尽后的恢复对照，以及持续推进的 TEST 时钟，未延长25秒断言或改资源政策。这些与旧 F1/H1/F2 UNKNOWN 不混同。

D1/D2/D3 未授权的正式风险体系、临时深思策略、全量固化改革不在本轮。真实服务/凭据/部署仍 NOT_READY。历史 F1/H1/F2 保留 UNKNOWN，未经独立确认不关闭本轮 EVIDENCE_CONFLICT。

## 组合复查后的两处纠正

compatibility-01：749项，747 PASS、1既有Win1314 SKIP、1 FAIL、0 ERROR。唯一失败是旧test_unknown_execution_never_replays_unverified_effect把外部UNKNOWN与内部revision冻结耦合；这与用户本轮R1明确要求相反。原效果/调用/扣费断言全部保留，revision断言更正为合法独立认知确实推进，且每次推进对应本次完成的Thinking调用。未把真正Provider UNKNOWN重置或重发，未改权限/费用语义。旧失败日志原样保留。

本轮初稿还把世界未确认映射为Scheduler认知任务UNKNOWN，queue-before-01在容量2的真实队列上证实内部推进被耗尽阻断。改为认知机会完成回执与世界E5-A结果分开；未确认世界请求依旧阻止同能力/目标的新副作用。此项属于本轮初稿遗漏，不倒归到历史F1/H1/F2。

本轮R3初稿在当前片段未选中旧根时移除已形成倾向。growth-retention-before-01（纯方法）及retention-before-01（正常C1）已保存真实反例。修正为保留历史理解、重查本轮支持并形成有理由的QUESTION；新证据足够时可修订当前依据。本轮新增撤销根测试初稿错误要求删除倾向，按既有P12“遗忘不抹掉合法主体判断”要求改为历史保留、当前支持不可继续声称有效；新增缺失根正向回归。原已验收阶段测试未因此删测，相关初稿及首次结果可追溯。

## 最终全量发现的本轮R1回归

full-final-01实际1550项：1548PASS、1既有Win1314SKIP、1FAIL、0ERROR，1718.557秒，源码前后完全一致。唯一失败为P13原test_context_rejection_and_platform_denial_are_distinct_from_subject_refusal：Action拒绝已记录，但Fake execute_calls=2而非0。根因是移除choose中的approval早退以保留意图后，没有在实际派发处保留原Action拒绝。属于本轮R1引入回归，不是历史F1/H1/F2。

最小修正在原continuity_core_service.after_action中：先形成并核对意图，再尊重原Action拒绝；不prepare/run或产生请求，保留原Thinking/Action拒绝材料及只含身份/静态原因的Trace。若拒绝记录却已有E5-A动作历史则失败关闭，不隐藏矛盾。原权限策略、费用、恢复和所有P13断言不改。platform-legacy-after-01原测试1PASS（1.330秒）；新增platform-after-02为1PASS（1.591秒），覆盖意图保留、零派发/效果/费用/状态变化及重启。

platform-before-01和platform-after-01均为新增辅助测试ERROR，Windows临时根前缀过长导致深层临时文件FileNotFoundError；未到达目标行为，不计Engine失败或有效修前反例。缩短测试根前缀，且在运行前按接口实际list返回类型修正空集合预期，未改运行实现或超时。有效修前反例是full-final-01中的原P13用例，原失败堆栈与日志保留。后续最终选择标签以selected-runs.json为准，旧342/33通过不冒称最后源码覆盖。

原独立probe_boundaries.py内有固定interpretation文字（如旧prior_will诊断描述），副本不改；修后结论依据实际输出值和正式断言，不把旧固定解释当作新事实。正式回归已验证承诺在下一轮理由/选择中的实际作用。

## 补充正常逐步推进（源码未变，单列场景）

[progressive-02](progressive-02.json)及[stdout](progressive-02.stdout.log)/[stderr](progressive-02.stderr.log)：15轮，每轮6逻辑小时加60秒调度推进，总90小时15分的逻辑跨度；默认need_delta=0.02未改变，TEST时钟跃进容许量明确设86400秒。第7—15轮数值变化低于该门槛仍实际调用并提交，15次Provider调用对应15次revision推进，token_used=4800，世界效果/执行/credits均0；显式STOP，成功Fixture已清理。99.468秒、exit0，前后源码与最终全量一致。不是90小时真实持续负载测试，不计入Engine正式1551项。

[progressive-01](progressive-01.json)及[stderr](progressive-01.stderr.log)保留辅助AttributeError：观察脚本误用host.status()（正确API为query()），诊断和STOP后读取也触发同类错误，未得到完整观察数据；STOP调用位于错误读取前。保留失败根与日志，未修改引擎。修正观察脚本后使用新标签，仅补该场景，未重跑全量。
