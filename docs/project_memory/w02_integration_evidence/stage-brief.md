# W02 整体贯通检查 Stage Brief

2026-09-25。**本批是 W02-A/B/C 已验收实现的同版串联核验，不是新阶段，也不是 W02 用户验收。**开工时 Engine `main`、HEAD／本地 `origin/main`／实际远端 `main` 均为 `d6bd8ecf3041578cf5f101d6feecf7d22a451571`；296 份源码、测试及资源指纹为 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea`。暂存和已跟踪工作区干净，57 项排除材料逐项 hash 不变；63 项保护文件、三份现行规划及 7 份正式数据保持原样。当前测试尚未运行，不能把 A/B/C 原结果写成本轮贯通 PASS。

| 栏位 | 本轮确定范围 |
| --- | --- |
| STAGE | W02 整体贯通检查；施工中，最高交付 `IMPLEMENTED_NOT_ACCEPTED`，独立复核及用户正式验收另行进行。 |
| SOURCE OF TRUTH | [现行规划版本索引](../现行规划版本索引.md)所列总施工 v1.5、最终新增 v1.5、长期能力 v6.9；W02 施工卡、N01/N02/N11、T01—T06/T18/T23 内部部分、[测试阶段映射](../w01_planning_v15_20260923/test-stage-map.md)、[A](../w02_a_acceptance_evidence/acceptance-matrix.md)／[B](../w02_b_acceptance_evidence/acceptance-matrix.md)／[C](../w02_c_acceptance_evidence/acceptance-matrix.md) 验收矩阵。 |
| ORIGINAL REQUIREMENTS | 原始消息从正常 Engine 入站；相关站记录来源、理由和处置，接收不等于长期记忆；回答形成前自动评估、合法本地召回，经 Router/Composer 形成最终材料；外部资料经 P16/E5-A 回执与当前根核实后作为候选；同根去重、冲突、预算和失败恢复均可追溯。 |
| CAPABILITY DETAILS | 同一主体／请求或消息／站内记录／Recall 评估／外部请求与回执／Memory 或候选／最终 Context／恢复位置连成真实 TEST 链。只读链路样例不触发新模型、学习、执行或 revision。 |
| AMENDMENT OVERRIDES | 用户本轮仅授权贯通核验、最小正式集成测试、TEST 夹具、证据及直接档案；若发现已验收运行实现缺口，先留失败、说明最小改法及公共影响，**未获用户对定向修改确认前不改运行实现**。 |
| KEEP RULES | SubjectState/Event、Memory、Learning/Evolution、ThinkSession 与唯一 E5-A 各守原权威；不新增第二请求账本、强制表达或逐条内部审批；当前权限、Context、来源、生命周期、预算、PAUSE/STOP 和 TEST/RESEARCH 隔离不变。 |
| DEPENDENCIES | W02-A/B/C 已 `ACCEPTED`；复用 `continuity_interaction_service` 正常 submit 与 input/recall 只读出口、`continuity_core_service` 准备链、原 `InputProcessingService`、`AssociativeRecallService`、`ExternalAbsorptionService`、Router/Composer、P16 回执与 TEST Fake。 |
| NOT READY | W03 的长期认识细化和 T04 对应部分；P19 页面及 T23 显示；P20 跨 Store/备份删除；P22 真实资料服务。它们不替代本轮内部核验，也不作为其开工前置。 |
| FILES ALLOWED | 新增 `tests/test_w02_integration.py`，必要时新增职责仅为 TEST 装配的 `src/continuity_engine/testing/w02_integration_fixture.py`；本目录中的 Stage Brief、矩阵、原始测试/审计/清单与只读样例；直接同步 `docs/project_memory/03_施工日志.md`、`01_当前状态.md`、`06_未完成事项.md`、`10_档案修订记录.md`、`13_P00_档案与测试索引.md`、`CHANGELOG.md`、README 与工程总档案（仅确有必要时）。 |
| FILES FORBIDDEN | 现有运行实现与已验收正式测试断言、六份冻结 Schema／外部契约、63 项保护文件、三份规划原文、正式七文件、版本与 pyproject、Assistant/Vio、57 项排除材料；不执行 Git 写操作。 |
| TESTS REQUIRED | 先逐项复核 A/B/C 证据覆盖，再加最小真实入口正反与恢复用例；贯通专项、A/B/C 兼容、受影响公共兼容，固定源码后一次完整 Engine 回归。每组保留命令、退出码、耗时、stdout/stderr、前后源码与测试身份，SKIP/失败/中断分开。 |
| PLANNING CONFLICT | 开工对照未见需改规划或权威的冲突，暂记 `NONE`；若实测出现真实规划冲突，停止冲突项并呈报原要求、实际障碍、保持/变更方案代价及选项。 |

施工矩阵和结论以本轮真实验证更新；本简报不预填通过。W02-A/B/C 既有验收、历史 F1/H1/F2 `UNKNOWN`、原失败及 Windows 1314 SKIP 保留。

## 开工后的定点授权增量

新增贯通反例在 A+B 同开时稳定证明：原操作已有 W02-A `FAILED_WAITING` 站，但 B 的已准备 Context 路径跳过该站恢复。用户在看到原反例和公共影响后，本轮**另行明确确认只修这一恢复路径**。因此上表 `FILES ALLOWED` 增加 `src/continuity_engine/services/continuity_core_service.py` 中 `_prepare` 的该分支及对应正式回归；其他运行实现、冻结边界和验收权限未扩大。修前/修后同身份对照与具体修改见[定点补修报告](repair-report.md)。
