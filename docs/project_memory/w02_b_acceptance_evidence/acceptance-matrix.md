# W02-B 当前正式验收矩阵（D-078）

本表按[施工矩阵](../w02_b_evidence/matrix.md)逐行同步现行验收状态；原表送审时的IMPLEMENTED_NOT_ACCEPTED作为历史保留。规划窗口只读复核，没有独立运行Engine测试。测试名称、原始命令、时间及失败史见[测试索引](../w02_b_evidence/test-index.md)和[验收测试口径](test-evidence-index.md)。所有行只代表W02-B本批，不代表W02整体完成。

| Planning Item | Code Change | Test / Evidence | Acceptance Result 与限制 |
|---|---|---|---|
| N02/T03回答前主动评估 | [C1准备](../../../src/continuity_engine/services/continuity_core_service.py)、[Recall.prepare](../../../src/continuity_engine/services/associative_recall_service.py) | [T03真实入站及Provider收到最终Context](../w02_b_evidence/w02-b-final-04.json) | ACCEPTED；先评估再形成回答 |
| T03当前输入与旧材料 | [原输入来源](../../../src/continuity_engine/services/input_context_source.py)、原Memory/Timeline | 同日12点/15点及跨进程恢复测试 | ACCEPTED；当前报告可临时参与本轮，不等于已长期记忆 |
| T04独立根与候选 | Recall复用原P04 Consolidation/DerivedSummary | 同源重放、派生材料、独立Event根对照 | ACCEPTED；候选未确认，无SubjectState直写 |
| T04配置与反证 | [RecallPolicy](../../../src/continuity_engine/domain/associative_recall.py) | 规则配置、负面及他人报告对照 | ACCEPTED；达门槛不等于必然喜欢 |
| T05否定、他人、意愿、旧事与引用 | Recall.assess复用W02-A解释 | 真实入站语义及引用歧义对照 | ACCEPTED；有界解释，不可靠语法保留不确定性 |
| T06有限关联与停止 | 原[Router](../../../src/continuity_engine/services/context_router_service.py)和Recall停止码 | 重复、环路、足够材料、不相关及可配置预算 | ACCEPTED；有理由才展开，不设永久固定推理层数 |
| T06检索、时延与Context预算 | 原Router/Composer及RecallPolicy | 检索量、准备时限、去重冲突裁剪 | ACCEPTED；原JSON完整校验成本仍在 |
| T06失效与不可读 | 原来源、权限、生命周期和Composer复核 | 撤权、版本、撤销、过期、失败与无命中对照 | ACCEPTED；失败不得报告为历史不存在 |
| T01/T02/T18恢复联验 | 原C1操作记录及E5-A事实链 | 返回丢失、重开、重复查询及效果/扣费一次 | ACCEPTED；按原身份和可信事实恢复 |
| 当前权限、身份、隔离及只读 | `recall_outcome`及原Context/来源复核 | 撤权、损坏、跨主体环境及只读零写入 | ACCEPTED；过期准备不能重新授权 |
| 正常主体链及表达边界 | 原C1/Thinking/P18原链 | native认知、PAUSE/STOP、外部等待及不强制表达 | ACCEPTED；不产生现实执行新权限 |
| 旧开关与持久化兼容 | 原集成类型的可选字段及装配门控 | 66项W02-A兼容、509项受影响兼容、1703项全量 | ACCEPTED；原1646身份保留，既有Windows1314 SKIP如实记录 |

正式结论：W02-B=ACCEPTED，W02整体=IN_PROGRESS。W02-C、W03、P19未开工。首次失败和辅助错误在原始证据中继续有效，历史F1/H1/F2仍UNKNOWN。
