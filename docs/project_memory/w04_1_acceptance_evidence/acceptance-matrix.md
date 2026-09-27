# W04-1 逐项正式验收矩阵（D-087）

此表把现行规划的本子批义务对应到实际代码、原始正式测试和本次用户验收。W04-1=`ACCEPTED`，W04 整体仍 `IN_PROGRESS`；后置能力不冒充本批完成。原施工与返修过程见[完整矩阵](../w04_1_evidence/matrix.md)。

| Planning Item | Code Change / 原权威链 | Test / 可复核证据 | Acceptance Result |
|---|---|---|---|
| N08 / T16—T17 | `domain/environment_access.py`、`services/environment_access_service.py` 和单一环境仓储区分听说、发现、连接、当前可用；每次选用重查用途、范围、授权与期限 | `tests/test_w04_1_environment.py` 的四态、撤权、替代路线及当前资格对照；[专项 29 PASS](../w04_1_evidence/w04-r1-targeted-02.json) | 本批 TEST/RESEARCH 契约 `ACCEPTED`；真实设备与生产服务未接 |
| N09 / T19—T21、T60 | `MigrationPreparation` 区分类别、缺项和就绪状态；`handoff_isolated` 在仓储读写前绑定主体/环境，沿原代次和 CAS 使旧端失权 | [返修修前记录](../w04_1_evidence/w04-r1-before-02.json)、[返修报告](../w04_1_evidence/repair-report.md)、同主体交接／跨主体和环境拒绝／重开恢复专项 | W04-1 隔离契约及三处返修中的 N09 边界 `ACCEPTED`；P20/P21 正式交接未就绪 |
| N10 / T22、T85—T87 第一批 | 身体身份、绑定、能力单位和来源；具体 OUTPUT 能力到期在原 P17/E5-A 投递前拒绝，传感读数仅接受有限数值或明确未知 | 到期零效果零扣费／未到期一次合法效果、NaN／无穷／布尔／错误类型拒绝及零值／未知对照，见[专项原始结果](../w04_1_evidence/w04-r1-targeted-02.json) | 身份、能力和传感契约 `ACCEPTED`；W04-2 双向 Fake Body 闭环尚未完成 |
| N12 / T26、T33 | 原正式消息入站和 P17 动作出口可选绑定附件、主体、环境、账号/设备/会话，不凭同名账号扩权 | 正式入口、跨环境、同名账号、模型 API 与动作测试；[原交付报告](../w04_1_evidence/final-report.md) | 第一批身份绑定 `ACCEPTED`；W04-4 跨入口连续性及 P22 真实账号未就绪 |
| N21 / T66、T67、T72 第一批 | `ScopedHistoryService` 复用 Router/Composer、当前来源及权限核验，仅提供有界只读引用 | 范围、撤权、旧 revision、深层查询依赖缺失及零模型/动作/revision 对照；[原施工矩阵](../w04_1_evidence/matrix.md) | 局部历史查询契约 `ACCEPTED`；W05 自然记忆和深层考证后置 |
| 适用 T18、公共兼容 | 环境仓储身份/hash/CAS/原子提交与原 E5-A 请求/回执；不新增第二账本 | [兼容 182 PASS](../w04_1_evidence/w04-r1-compat-final-01.json)；[全量 1801 PASS／1 SKIP](../w04_1_evidence/w04-r1-full-resume-01.json)，均固定同一源码指纹 | 本批已知恢复、权限与隔离阻断 `ACCEPTED`；Windows 1314 SKIP 和历史 UNKNOWN 留存 |

修前失败、辅助错误、旧全量 `INTERRUPTED` 与初版较早测试结果仍在[原始测试索引](../w04_1_evidence/test-index.md)，不能用最终 PASS 倒改。规划窗口为只读复核，表中 PASS 均是施工方同版实跑，集合重叠不相加。
