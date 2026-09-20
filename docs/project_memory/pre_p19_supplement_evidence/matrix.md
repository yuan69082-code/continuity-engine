<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# A1/A2/A3 复核矩阵

各项当前IMPLEMENTED_NOT_ACCEPTED；测试通过不等于用户验收。测试文件[正式新增回归](../../../tests/test_pre_p19_supplement.py)。

| 项目 | 实现与正反/恢复入口 | 结果范围 |
|---|---|---|
| A1 | ExpressionIndependenceTests：native确认/现实/恢复条件拒绝；普通C1表达开启及合法确认；内部权限/晚撤权/过期Context/失效来源；原Evolution之后崩溃且无执行请求时重开恢复 | combined-02；independent-final-01；兼容及全量 |
| A2 | RoutedProposalTests：contact/expression.emit/execution.read/memory.lookup路由；拒绝/UNKNOWN/真回执；不提交先于效果的模型提案；真实回执经后续Composer消费后的新判断；纯内部反思正常 | 同上 |
| A3 | RenewedNeedTests：原Dynamics outcomes act→recur；无足够新需要不调用；abandon不强制复活；临时抑制；原持久化状态重开、PAUSE/资源等待/恢复/认知实际推进/STOP不复活 | 同上 |
| 原成果 | 原34项R1—R4，及直接相关P09/P13/P14/P15/P17/P18/Action/Permission/Resources/Learning | combined-02及compatibility-01；最终full-final-01 |

集合真实结果及原始输出见[test-index.md](test-index.md)，最终源码见[final-source.json](final-source.json)。不另算独立八项为正式测试增长。
