# P19前主体自主性边界修复正式验收（D-074）

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

## 验收分项

| 项目 | 当前状态 | 依据 |
|---|---|---|
| R1 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| R2 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| R3 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| R4 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| A1 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| A2 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |
| A3 | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |

R1/A1分离表达或现实拒绝与合法内部Evolution；R2取消名称风险启发式但保留明确风险门；R3保留有来源的倾向与Will成长；R4/A3由原动力学及未决关注支持有界认知复议；A2依实际绑定能力与来源保守区分混合提案。没有逐句效果依赖的新体系，不将全部模型提案自动写入；真实回执可供后续合法认知重新形成判断。权限、资源、STOP及世界效果限制不放宽。

## 身份与测试口径

验收代码身份：275份源码/测试/资源，`sha256:37ca50a9b21595f1e31067d88fefe95d1b4ffcf02e9095ef3393d3afcd4c36f1`。1580个正式测试身份=补修前1551项+新增29项。提交前父基线为`cb528d74884990915737b491ca6a9f2c35cc512a`。

| 来源 | 结果 | 秒 | 原始证据 |
|---|---|---:|---|
| 本轮监工独立实跑 | 原探针8PASS | 6.640 | [JSON](independent/original-01.json) / [输出](independent/original-01.log) |
| 本轮监工独立实跑 | 正式交叉63PASS | 120.684 | [JSON](independent/formal-01.json) / [输出](independent/formal-01.log) |
| 本轮监工独立实跑 | 额外边界8PASS | 10.708 | [JSON](independent/extra-01.json) / [输出](independent/extra-01.log) |
| 施工方实跑，经独立核验引用 | 完整兼容538PASS | 1152.693 | [JSON](../pre_p19_supplement_evidence/compatibility-01.json) |
| 施工方实跑，经独立核验引用 | 全量1579PASS、1SKIP、0FAIL/ERROR，exit0 | 1687.548 | [JSON](../pre_p19_supplement_evidence/full-final-01.json) / [原始输出](../pre_p19_supplement_evidence/full-final-01.stderr.log) |

本次验收操作只执行身份、保护、链接、敏感模式、范围及Git核查；没有新行为测试，没有远端CI PASS声明。本地无Actions workflow，远端CI/check是否取得以最终交付报告为准，不新建workflow。

## 历史与档案

[独立复核报告](independent/review-report.md) · [身份审计](independent/identity-audit.json) · [原件/副本hash](archives.json)。原八项探针复用[既有精确归档](../pre_p19_supplement_evidence/independent/test_independent_boundaries.py)，额外探针见[test_extra_controls.py](independent/test_extra_controls.py)。只在阅读版修正链接；逐字节原件副本另存。规划侧原件未写入。

原R1—R4、A1/A2/A3报告及矩阵增加当前验收入口，原文保留为历史，原始日志/测试结果不改写。历史F1/H1/F2与P09 segment 10原因UNKNOWN均不变；本批次闭合不能倒推旧案根因。

63项保护、三份规划、正式七文件、0.1.0/pyproject和32排除项逐文件核对；正式树保持`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

[验收文档变更与原历史hash](document-history.json) · [最终审计](final.audit.json) · [最终提交及排除清单](final.pending-files.md)。清单包括既有220项成果及必要验收增量，计数以实际清单为准；未纳入32项排除材料。暂存严格使用精确路径，推送仅现有Engine origin/main。提交自身SHA不伪造自引用，最终SHA、父提交与推送核查结果由操作后的最终回复报告。
