<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# P19前主体自主性边界 A1/A2/A3 补修交付

本轮补修已实现，等待独立复核。IMPLEMENTED_NOT_ACCEPTED；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT。P00—P18历史验收及D-073保留，P19—P23 NOT_STARTED；无新增验收决定、暂存、提交、push、真实服务或Assistant/Vio操作。

## 根因与实际改动

- **A1**：表达专属确认/现实拒绝原先在内部Evolution前抛错。现在只将明确的表达投递门拒绝保存为已有PLATFORM_DENIED空artifact；不吞生成错误、损坏或当前Context错误。合法内部授权仍须原Action/Evolution、权限、来源、生命周期及revision检查。普通C1先形成原Choice/精确确认后评估表达，mind路径在拒绝时不派发；旧非mind顺序保持。native原Evolution事件metadata可附已绑定的空拒绝artifact，解决内部提交后中断而从未建立执行请求的事实恢复；不新建账本、不改变事件版本或外部Schema，不以拒绝作为执行成功证明。
- **A2**：旧投影只看contact/tool两标志，漏掉expression.emit及查询路由。现在根据原Choice和实际CapabilityBinding的CONTACT_USER/USE_TOOL/REQUEST_MEMORY识别本轮外部执行/结果依赖。原ThinkSession中的模型提案完整保留；当前混合轮只提交Engine有来源的独立心智/成长提案，不扫描成功等文本。当前回执即使成功也不倒签Provider早先提案；后续无新外部请求的认知可在原Router/Composer重新核验回执后形成新的合法判断。真正UNKNOWN仍查原事实、不重派、不重复计费。
- **A3**：旧ended条件把旧desires全部结束当成永久无需求。现在采纳原MindDynamics的当前投影，允许已满足后重新出现的需要，同时排除明确abandon旧目标作为唤醒依据。最低间隔、rest/hold复议、预算、背压、生命周期、PAUSE/STOP均保留；Scheduler不创建欲望。

相对补修起点，增量运行文件仅5个：[continuity_core_service.py](../../../src/continuity_engine/services/continuity_core_service.py)、[continuity_interaction_service.py](../../../src/continuity_engine/services/continuity_interaction_service.py)、[expression_policy_service.py](../../../src/continuity_engine/services/expression_policy_service.py)、[runtime_cognition.py](../../../src/continuity_engine/services/runtime_cognition.py)、[wake_perception_thinking_action_service.py](../../../src/continuity_engine/services/wake_perception_thinking_action_service.py)。新增正式测试[test_pre_p19_supplement.py](../../../tests/test_pre_p19_supplement.py)；原1551项测试身份及其既有测试文件、有效断言未改。既有R1—R4修复成果保留，原失败和调查档案未改写。没有扩大权限、资源计费、D1/D2/D3生产政策或主体目标。

## 当前版本真实验证

| 集合 | PASS | SKIP | FAIL/ERROR | 秒 | 退出码 |
|---|---:|---:|---:|---:|---:|
| [combined-02](combined-02.json) | 63 | 0 | 0/0 | 126.864 | 0 |
| [independent-final-01](independent-final-01.json) | 8 | 0 | 0/0 | 7.349 | 0 |
| [compatibility-01](compatibility-01.json) | 538 | 0 | 0/0 | 1152.693 | 0 |
| [full-final-01](full-final-01.json) | 1579 | 1 | 0/0 | 1687.548 | 0 |

原1551个正式身份全部保留，新增29项，当前1580项。原独立8项由施工方原样复跑，单列、不增加Engine正式数量，也不代表本次独立监工已确认闭合；交叉/兼容/全量有交集，不重复相加。SKIP仍为既有Windows符号链接权限1314，非PASS。表内耗时为证据runner总耗时，unittest自身计时保留在原始stderr。以上均为本轮实际运行；旧R1—R4的1551项全量只作历史引用，没有远端CI run或CI PASS声明。

当前275份源码/测试/资源，指纹 `sha256:37ca50a9b21595f1e31067d88fefe95d1b4ffcf02e9095ef3393d3afcd4c36f1`；以上所有组的执行前后均与当前一致，见[最终源码](final-source.json)。

## 失败、修复与限制

修前原八项4PASS/4FAIL（6.803秒），A1两条、A2/A3各一条，见[independent-before-01](independent-before-01.json)。原件副本hash见[archives.json](archives.json)，规划侧原件未改。

formal-01的22PASS/1FAIL是新测试在合法MAINTENANCE tick上要求认知的辅助假设错误；[定向观察](followup-scheduling-diagnostic.json)证明下一次既定机会完成认知，未放宽超时或修改Scheduler。recovery-before-01保留了A1派发前拒绝、内部提交后中断的unconfirmed恢复缺口；expression-order-before-01记录本轮初稿普通C1精确确认顺序回归；query-route-before-01记录A2纯memory.lookup遗漏。对应正式断言均保留并已通过，未用后续PASS覆盖首次失败。所有中间结果及分类详见[补修记录](notes.md)。

这不是在判断思想真伪：限制的是当前执行/结果依赖的入账，不清除原始模型提案、倾向、Will或合法内部认知。混合提案按已有来源保守分离，未引入自然语言关键词审查；未建设新的逐句效果依赖标注格式。正式隐私、联系时段/频率、费用及生产接入仍NOT_READY。持续运行无固定轮数/时长或无消息停机条件；测试由控制器有界观察并STOP。

历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧FAIL/ERROR/SKIP及缺失证据不变。本次三项不得倒推为旧案根因。最终是否闭合仍由独立复核确认。

## 审计与入口

[逐项矩阵](matrix.md) · [命令与全部运行索引](test-index.md) · [最终审计](final.audit.json) · [完整待提交及排除清单](final.pending-files.md) · [进程清理记录](process-cleanup.json)。

审计逐文件检查63项保护、六Schema及外部契约、三份规划、正式七文件/树hash、版本0.1.0/pyproject和原32排除项；额外检查原测试、已有证据、源码AST、本地链接、敏感材料与Git差异。实际数量及格式告警以审计为准，不改写旧原始日志。HEAD和暂存区须与补修起点一致，所有成果留在工作区交复核。
