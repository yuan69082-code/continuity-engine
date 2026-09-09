<!-- P17_ACCEPTED_START -->
2026-09-10 用户正式验收 P17 初版及 R1/R2 返修（D-071）。P00—P17 ACCEPTED；P17 / Engine side / P17-01—P17-12 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示独立复核覆盖范围内已知阻断闭合，不保证不存在其他缺陷。

监工独立实跑：完整 P17 74 PASS（unittest 101.169 秒），原探针及额外检查共 11 PASS（9.246 秒），均为 0 SKIP/FAIL/ERROR；24/24 身份与保护检查通过。全量仅引用已核验的施工方 1360 项：1359 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1171.401 秒。12 项返修正式测试已包含在 74 项中，独立探针不增加 Engine 正式测试数；本次归档未重跑行为测试。

验收范围为隔离 Research/Test World 与本地 Fake；生产 Adapter、真实凭据、生产恢复及正式策略仍 NOT_READY。保留唯一 E5-A 通道，不宣称生产 exactly-once，不修改 Assistant，不进入 P18。用户已授权本阶段精确清单普通提交及推送；提交身份与实际推送结果在完成后另行报告，不预填成功。下方旧状态、未验收/无 Git 授权说明和全部 FAIL/ERROR/SKIP、辅助错误、P09 segment 10 UNKNOWN 均为历史，不倒改。

[正式验收依据、审计与精确提交清单](P17_用户正式验收_20260910.md)。
<!-- P17_ACCEPTED_END -->

> R1/R2现行状态：IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT，等待独立复核；下方初版内容及其测试为历史。见[返修报告](p17_repair_evidence/final-report.md)。

> P17现行状态：IMPLEMENTED_NOT_ACCEPTED，等待独立复核；D-070开工，不使用D-071。下方Stage Brief的IN_PROGRESS等表述为开工历史。

# P17 Stage Brief：Execution Engine 与 World/Capability Layer

STAGE：P17 IN_PROGRESS，Engine 独立施工。用户2026-09-09明确授权；D-070为开工决定，D-071保留给未来验收，本轮不使用。

SOURCE OF TRUTH：用户本轮授权、[完整开工简报](p17_evidence/implementation-brief.md)、[核实规划摘录](p17_evidence/planning-extract.json)、D-069与真实P08/P09/P16源码。[开工身份](p17_evidence/before.json)实查main/0c440b0476b07723abafe93777fe895b64fd8d0e，243源码/测试/资源身份相同。原1286项仅引用1285 PASS/1 Windows1314 SKIP/1072.026秒，未重跑。

ORIGINAL REQUIREMENTS：Execution Engine、Capability Resolver、世界分类、替代路线、Reality Boundary、Recoverability、Research Routing、Blast Radius、Outbox、幂等、查询、取消、补偿与结果吸收，实际经过正常C1 Direct/Optional Planner。

V6.7 DETAILS：UNKNOWN先查事实；研究世界独立数据、Adapter、凭据引用与审计；补偿为独立动作；资源/次数/并发/消息/存储限额；结果在后续正常Router/Composer/Thinking轮次作为有来源候选消费，经原Action/Evolution形成需要的状态变化，不能直接写SubjectState。

AMENDMENT OVERRIDES：v1.1 blocks213—219及350—354、401—406；v6.7 blocks444—451、459—472、483—497及574—578。宿主中立端口，P17仅本地Fake；P22真实Adapter，P20/P21正式恢复。Reality Boundary只管已形成结构化行动的世界效果，不审查心理内容。

KEEP RULES：单一E5-A权威请求/结果；model.generate原Thinking路径；简单行动不强迫Planner；SubjectState/Event/Memory/Evolution职责不转移；P16三项秘密边界与P15生命周期不变；历史失败与P09 segment10 UNKNOWN保留。

DEPENDENCIES：P08 ActionPlanningService与ActionGate、E5-A；P09正常C1、P05/P06候选来源；P12生命周期；P15主体活跃门禁；P16凭据/材料端口模式。P11仍只发计算机会，不在本轮增加常驻Scheduler。

NOT READY：生产世界执行、真实供应商/凭据、真实Owned Asset Registry、生产恢复、安全/隐私政策、常驻运行均不开放。REAL恢复门返回RECOVERABILITY_NOT_READY；Research不可用不退回Real。不部署任何真实服务。

设计职责：新增ExecutionService作为原ActionCapabilityBinding的宿主中立Adapter桥，所有请求身份及结果仍由E5-A核对。JsonExecutionOutbox仅保存request ID/hash、路由hash、投递/租约/取消/关联索引，不存第二份请求正文或结果。执行前在原C1 Context与ActionGate上重新校验。World路由不可在恢复中静默替换；补偿/替代需要新的独立授权请求。ExecutionContextSource将经过独立回执和当前消费授权重查的结果交给原Router/Composer，不直接记事实或修改状态。

FILES ALLOWED：新增 `src/continuity_engine/domain/execution.py`、`services/execution_ports.py`、`services/execution_service.py`、`services/execution_context_source.py`、`storage/json_execution_outbox.py`、`testing/p17_execution_fixture.py`、`tests/test_p17_execution.py`、`tests/test_p17_recovery.py`、`tests/test_p17_boundaries.py`。必要局部接线限 `services/continuity_core_runtime.py`、`services/continuity_core_service.py`、`services/continuity_interaction_service.py`、`services/action_planning_service.py`；如需超出先记录责任理由。档案79—82、p17_evidence本轮证据与工具，以及README、00—12相关当前档案、CHANGELOG、工程总档案。旧证据原样保留。

FILES FORBIDDEN：63项保护清单、六份Schema与外部接口、三份规划、正式七文件、pyproject/版本0.1.0、Assistant/Vio、32排除项、历史证据；所有Git写操作。

TESTS REQUIRED：先新行为反例及正常对照、P17专项、实际受影响兼容，稳定后一次全量。验证Direct/Planner、结果消费/合法Evolution、重复并发、断点/跨进程、取消竞争、补偿失败/未知、替代路线、当前授权/资源/生命周期/世界、损坏与秘密材料、受保护根零写入。Frozen Clock、有界调用，无sleep。原1286身份保留，SKIP单列，唯一标签原始日志与前后hash。

PLANNING CONFLICT：NONE（开工核对未发现冲突；不代表验收）。EVIDENCE_CONFLICT：NONE（尚未执行新增行为测试，不预填通过）。当前有效任务始终为P17施工；旧“等待P17”属于已完成P16历史。

施工档案范围补充：13_P00_档案与测试索引.md只同步P17入口，符合本轮索引维护授权；其他已验收专题与历史证据不改。

## R1/R2返修范围追加（2026-09-10）

用户授权范围保持不变。FILES ALLOWED增量仅execution_service.py、p17_execution_fixture.py、tests/test_p17_repair_edges.py及相关档案/证据。冻结契约与原1348项测试文件不变，不重新建设P17，不D-071、不P18。首次入队/权限历史与本次返修分开记录。
