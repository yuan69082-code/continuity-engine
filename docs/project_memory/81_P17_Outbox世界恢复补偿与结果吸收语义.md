<!-- P17_ACCEPTED_START -->
2026-09-10 用户正式验收 P17 初版及 R1/R2 返修（D-071）。P00—P17 ACCEPTED；P17 / Engine side / P17-01—P17-12 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示独立复核覆盖范围内已知阻断闭合，不保证不存在其他缺陷。

监工独立实跑：完整 P17 74 PASS（unittest 101.169 秒），原探针及额外检查共 11 PASS（9.246 秒），均为 0 SKIP/FAIL/ERROR；24/24 身份与保护检查通过。全量仅引用已核验的施工方 1360 项：1359 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1171.401 秒。12 项返修正式测试已包含在 74 项中，独立探针不增加 Engine 正式测试数；本次归档未重跑行为测试。

验收范围为隔离 Research/Test World 与本地 Fake；生产 Adapter、真实凭据、生产恢复及正式策略仍 NOT_READY。保留唯一 E5-A 通道，不宣称生产 exactly-once，不修改 Assistant，不进入 P18。用户已授权本阶段精确清单普通提交及推送；提交身份与实际推送结果在完成后另行报告，不预填成功。下方旧状态、未验收/无 Git 授权说明和全部 FAIL/ERROR/SKIP、辅助错误、P09 segment 10 UNKNOWN 均为历史，不倒改。

[正式验收依据、审计与精确提交清单](P17_用户正式验收_20260910.md)。
<!-- P17_ACCEPTED_END -->

> R1/R2现行状态：IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT，等待独立复核；下方初版内容及其测试为历史。见[返修报告](p17_repair_evidence/final-report.md)。

> P17现行状态：IMPLEMENTED_NOT_ACCEPTED，等待独立复核；D-070开工，不使用D-071。下方Stage Brief的IN_PROGRESS等表述为开工历史。

# P17 执行、世界、恢复与结果吸收语义

请求与结果的权威仍在原 E5-A capability ledger。P17使用原InternalActionRequest、InternalActionResult、ActionReceipt，以及P08 Direct/Optional Planner。Outbox只保存request ID/hash、route hash、投递状态、尝试数、receipt hash和关联索引；不保存第二份请求正文、模型结果或回执正文。索引的自洽hash不是执行证明，每次成功/失败恢复仍查询独立Adapter事实。

World Adapter不仅按adapter_id解析，还在任何query/execute/read_result前核对subject_id、environment、world及version。Fake世界文档持久化并核对自身subject/environment/world绑定及回执/结果世界；把另一主体的Fake注册到同名adapter_id会在外部调用前拒绝，不写入对方世界。此约束属于本地TEST接线，不能据此宣称已验证生产Adapter安全性。

BlastRadius.storage_bytes在Fake中指世界状态完整JSON文件的UTF-8字节（包括revision、document/hash封装和行尾换行），不只计算输出正文。容量检查复用实际写入的确定性构造，在任何新增效果前计算结果尺寸；正好达到上限可执行，超限保持原字节和效果数。Outbox和原Engine审计文件分别受有界记录约束，未将storage_bytes宣称为整个Engine磁盘配额。

`ExecutionService`从已登记的WorldCapability解析能力、主体、环境、世界、目标、版本、Adapter及Credential引用。参数由原ActionSpecification.argument_hash绑定。正常C1的结构化选择经原ActionGate后进入P17桥；简单行动保持Direct，复杂两步由原Optional Planner建立依赖。model.generate原路径不改变。P16和P17同时可用时串行调用各自材料检查，关闭P17不会触碰其端口。

新执行依次核对原请求、原choice/Context身份、当前Context、权限/确认、主体活跃状态、世界readiness、凭据引用、恢复条件、原ActionGate和资源范围，并在投递租约内再查当前条件。不能把新的有效Context套到旧请求上。历史成功或执行失败回执的核实不依赖现在的执行授权，但重新消费结果仍须通过当前权限、生命周期和来源重验。

Outbox全事务由进程内RLock和本机OS非阻塞文件锁保护，覆盖核对、持久化DISPATCHING、调用、独立核实、DELIVERED写入。竞争未取得OS锁返回EXECUTION_BUSY，不sleep、不后台重试。锁随进程退出释放；重启时先query原attempt/request identity。Fake世界把隔离效果、测试积分与事实回执放在一个原子文档内，保证此测试能力的效果和可信查询一致。进程崩溃后仍可核实一次效果；不代表任意生产系统的一次且仅一次保证。

UNKNOWN、普通字符串NOT_EXECUTED、query异常、丢失/冲突回执均不授权派发或换路线。只有枚举ReceiptQuery.NOT_EXECUTED允许在当前门禁下尝试新执行。每个能力的尝试上限为显式测试配置，未执行故障也消耗已持久化的派发尝试。P08 ledger和Outbox共同约束上限，但Outbox不是结果权威。

取消查询实际事实：已成功返回COMPLETED；无法核实返回UNKNOWN；明确未执行时，在**原E5-A**登记本地停止决定（UNKNOWN状态、CANCELLED原因），再登记投递索引CANCELLED。此决定不是“真实执行失败”回执。重复取消不新增索引写入；Outbox取消片段缺失仍由原账本阻止重新派发。`stop(decision_id)`逐项停止剩余步骤，不把已完成步骤倒退，不把未知投递伪报为取消成功。

替代路线仅是等待、补充信息、重试建议、放弃或新请求关联。CHANGE_ROUTE必须先明确核实原请求未执行，保留原停止事实；新请求需要独立当前确认，world/asset/subject/environment一致且费用不扩大。UNKNOWN不能用另一个Adapter掩盖重复效果。

补偿是新的结构化请求、新的幂等键与回执，参数hash绑定原可信receipt hash。必须存在唯一原请求关联、同世界/目标/主体环境及当前授权；直接调用补偿能力也不能绕过关联检查。补偿仍由原Planner/E5-A派发。原成功回执永久保留；补偿成功、失败、未知分别记录，补偿失败不会把原效果说成已回滚。Fake补偿仅产生可审计的补偿效果记录，不冒称真实资产已恢复。

ExecutionContextSource逐次核对E5-A结果、独立回执、payload hash、当前权限与返回前状态，将带来源、版本、hash和模拟标识的RESULT_OBSERVATION交给原Router/Composer。它不是Event/Memory/SubjectState权威。Golden后续Thinking明确形成带TEST限定的状态提议，由原Action/Evolution提交一次revision；重放不重复更新。Research默认不进入Main Context、Event、Memory或revision，无法用world标签把模拟结果改成真实事实。本阶段未开放Research→Main生产晋升接口。

PLATFORM_DENIAL、REALITY_DENIAL、RESOURCE_EXHAUSTED、RECOVERABILITY_NOT_READY在原E5-A非执行结果中保留静态原因；可信Fake失败回执可区分GENERATION_FAILED/NETWORK_FAILED/REALITY_DENIAL。UNKNOWN仍独立。SUBJECT_REFUSAL为显式主体结果语义，P17不根据措辞推断拒绝；普通情绪、欲望、人格或沉默不作为Reality Boundary判据。

REAL始终RECOVERABILITY_NOT_READY。Research不可用返回RESEARCH_UNAVAILABLE，不回退到REAL。独立World目录、Adapter、凭据引用、事实文件及投递审计均在TEST根；没有真实密钥、SDK、外网、邮件/设备操作、Vio或Assistant。生产Adapter属于P22，生产恢复依赖P20/P21，持续运行属于P18，均未施工。

证据与命令见[测试入口](82_P17_测试索引与验收入口.md)，逐项对应见[矩阵](80_P17_规划施工测试验收矩阵.md)。

## R1/R2修正后的投递与计费语义

capacity及原Context/ActionGate是投递准备，可能触发同步的资源状态变化；这些工作完成后才读取当前readiness、主体生命周期、Broker授权、Reality授权和Recoverability。最终检查在同一Outbox事务内，并仅授权紧随其后的本地同步投递，不保存可跨请求复用的许可。没有增加固定检查次数或重试循环；原三次capacity定位探针全部通过。

授权读取端口应无写副作用；此边界解决已复现的本地同步资源回调变更，不承诺任意异步外部系统的瞬时撤权。Outbox锁不等于跨系统授权事务。后续每次新执行仍重新检查；原事实查询恢复不走新执行额度门。直接ExecutionError保留静态拒绝原因；原Planner未收到回执时仍按原E5-A记录UNKNOWN，不能将其说成真实执行失败。当前重新授权也不会自动重发UNKNOWN；需明确NOT_EXECUTED及既有显式retry。

本Fake继续遵循现有ActionReceipt合成契约：一次成功效果=1 TEST credit，失败=0；WorldCapability.cost是原ActionGate的estimated_resource_cost，不会改写Adapter回执中的实际合成积分。cost=0仍是合法估计并能执行，但不代表该Fake的效果免积分。容量检查使用与实际写入相同的projected_document，按预计完整文档的credits/facts/effects/字节量判断，不再以route.cost替代真实积分。实际累计credits来自receipt.test_credits；读取核对事实回执、效果identity和累计积分。不改ActionReceipt/冻结契约或另建账本。

补偿、取消、UNKNOWN查询、心理内容/沉默、秘密检查及旧结果撤权后排除保留。仅隔离TEST积分，不涉及真实支付；生产Adapter/恢复仍NOT_READY。
