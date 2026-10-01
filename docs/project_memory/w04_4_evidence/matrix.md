<!-- W04_4_LATEST_DELIVERY_20261001 -->
当前状态（2026-10-01）：W04-4及包级 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。最终定向、W04、公共兼容及全量已同版完成；实际结果见[交付报告](final-report.md)与[测试索引](test-index.md)。P13/C1同一批准已生效，不再待确认。以下开工、验证进行中或待确认字样均为保留的历史快照。未验收、暂存、提交、push，不W05。

# W04-4 施工矩阵（开工）

| Planning Item | 现有入口 / Code Change候选 | 真实缺口 | Test | Acceptance Result |
|---|---|---|---|---|
|N15/T33身份、私聊群聊/自发自收|EnvironmentAccess/SubjectBinding + cross_entry内部绑定|现Attachment未表达用户与主体收发角色和群目标|同名/错收件/跨主体环境正反|IN_PROGRESS|
|N15/T35具体话题/事项|W03 UnfinishedItem，原operation输入元数据|缺跨入口topic/item来源关联及歧义处理|双话题/澄清/原事项接回|IN_PROGRESS|
|N15/T36转用|原Router/Composer/Memory来源核验 + 可选当前入口策略|同主体权限尚未区分窗口转用|原文/summary/history/UI绕行拒绝、其他可读成功|IN_PROGRESS|
|N16/T34真实新表达投递|原Thinking/P13/Action/P17设备动作/E5-A|缺绑定话题的新询问与当前通道接线|API与UI完整链、回执后用户回复|IN_PROGRESS|
|N16/T37合法替代|原P17 alternative、W04-2当前观察/动作|仅补跨入口投递绑定与对照|技术不可用成功，拒绝/UNKNOWN不盲转|IN_PROGRESS|
|N15/T38时间/同源/回显|原输入/operation/Event来源|缺外部根消息与三类时间关联|迟到时区、镜像转发和主体回显|IN_PROGRESS|
|N15/T39/T18并发恢复|原C1入站锁、CAS、operation/ThinkSession/E5-A|缺新绑定/话题同请求恢复联验|写入/回执丢失、重开/并发/当前权限|IN_PROGRESS|
|N16/T40投递状态/新问vs重传|原发送回执投影与新Choice|送达已读要凭外部证据，旧UNKNOWN不永久禁止新问|sent/delivered/read/unknown/未答、未知付款反例|IN_PROGRESS|
|N16/T42统一暂停|原Owner/Contact权限当前检查|跨入口发送当前控制接线|A暂停B不绕过、内部工作保持|IN_PROGRESS|
|N10/N21/包级|前三批Body/历史查询/临时工具 + 本批入口|最终同版因果贯通尚无证据|换身体旧代次拒绝、历史回流、工具等待/清理、四批组合|IN_PROGRESS|
|C06/T43/T25/T45|原只读记录和成本事实|本批最小可读链路与支持表|只读无调用/费用/revision；真实耗时记录|IN_PROGRESS|

所有测试待运行；规划窗口旧复核不是本轮实跑。各条完成不代表用户验收。

## 2026-09-29中间核验（不覆盖开工矩阵）

| Planning Item | Code Change（实际） | Test / 原始证据 | Acceptance Result |
|---|---|---|---|
|N15/T33入口身份与自发自收|cross_entry + 原C1/Environment可选元数据|independent-scope-01账号/镜像/回显通过；群聊完整正反尚缺|IN_PROGRESS|
|N15/T35具体事项|原unfinished_item增加当前合法input根，entry关联草稿|主动联系前置被P13冲突阻断；native续接未完成|IN_PROGRESS，依赖N16 BLOCKED|
|N15/T36转用|EntryPermission/InputContextSource/原状态投影|8项集中的受限A与合法B对照通过；全派生/历史/UI和交错仍缺|IN_PROGRESS|
|N16/T34新表达|原P08/P13/P17接线，新增入口拒绝预检|entry-draft-03 ERROR；confirmation-conflict-03直接确认冲突且守卫效果/费用0|BLOCKED / PLANNING_CONFLICT|
|N16/T37路线替代|原DeviceCommand/DeviceOperation及Fake发送草稿|API/UI完整主动链未完成|BLOCKED（同上）|
|N15/T38三类时间、同源|EntryMessage及原输入记录|镜像/主体回显正反通过；迟到时区/并发未完成|IN_PROGRESS|
|N15/T39/T18恢复|原请求元数据绑定、最小只读投影|重开只读通过；副作用恢复与并发未完成|IN_PROGRESS|
|N16/T40投递与新问|E5-A只读投影及原结果事实|SENT/NO_EVIDENCE有限对照；送达/已读与UNKNOWN独立新问未完成|IN_PROGRESS，依赖N16 BLOCKED|
|N16/T42统一暂停|新入口沿原当前权限，用户级联系暂停配置|有效完整联系前置未通过，不能认定该项完成|IN_PROGRESS|
|N10/N21及包级|本批入口草稿，前三批原实现保持|153旧兼容PASS不等于包级；新因果贯通未完成|NOT_STARTED（包级正式验证）|
|C06/T43/T25/T45|inspect只读+原费用回执、计时证据|8项集中重开只读通过；轻量794.51ms只覆盖当次回忆准备|IN_PROGRESS|

各项均未验收；8项与153项是施工窗口实跑且集合不可累计成最终总数；原1923项旧身份由旧测试文件逐字节保留核对，当前新增13项并非13项全部通过。


## 2026-10-01最新事实

最终逐项证据移至[final-matrix.md](final-matrix.md)，历史表保持原时点。W04-4/包级为IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT；P13/C1已获授权并完成，不再等待同一决定。

