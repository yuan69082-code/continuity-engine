<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# P19 前 R1—R4 定向返修复核矩阵

P00—P18 历史 ACCEPTED 不变；本批次实现与最终验证完成，等待独立复核，P19 未开工。不得将下列过程结果直接作为用户验收。

| 项 | 实现责任 | 正向/反例与恢复入口 | 状态 |
|---|---|---|---|
| R1 | ContinuityCoreService/CoreDecisionPolicy；C1/native Action→Evolution；RuntimeCognition；既有 Execution Outbox投影 | test_pre_p19_autonomy_execution：允许/现实拒绝/资源/Broker撤回/UNKNOWN；混合提案；C1/native；内部提交前后中断；回执丢失；跨轮独立认知且零重复效果 | IMPLEMENTED_NOT_ACCEPTED；最终定点/兼容/全量见报告 |
| R2 | RiskEvaluator（操作类型下限+显式更高风险） | test_pre_p19_autonomy_risk 与 test_action：同语义改名不改变风险；HIGH/CRITICAL保持原门禁 | IMPLEMENTED_NOT_ACCEPTED；最终定点/全量通过 |
| R3 | MindCognition.finalize、MindDynamics.deliberate/influence；原 Action/Evolution | test_pre_p19_autonomy_growth：经历生产/重启/重复根/撤回/途中权限变化/无关与相关理解/相反倾向；补检索缺失不抹去历史判断 | IMPLEMENTED_NOT_ACCEPTED；历史保留及当前支持重验已验证 |
| R4 | RuntimeCognition.needs；原宿主/Scheduler/资源门 | test_pre_p19_autonomy_runtime：近饱和/饱和/自然推进、无需求、hold、稳定身份、资源耗尽恢复、真实子进程、STOP、旧世界UNKNOWN | IMPLEMENTED_NOT_ACCEPTED；最终兼容/全量已覆盖 |
| 交叉 | 上述原通道，不新增权限/账本 | test_denied_reality_keeps_experience_formed_commitment_for_next_cognition；test_world_unknown_does_not_block_next_internal_cognition_or_repeat_effect | 已运行，通过结果的源码身份以JSON为准 |
| 兼容 | P14/P15/P17/P18；C1/P08/P02/E5-A；Action/Learning/Resources/Permissions/Thinking/Evolution/Repository；既有审查修复 | compatibility-* 原命令和退出码见JSON | 最终结果见报告/测试索引 |
| 全量 | 原1517身份全部保留；新增另计；原Win1314 SKIP不算PASS | full-final-* | 最终实跑见报告/测试索引 |

## 复跑方式

从Engine仓库执行，使用未占用的证据标签；run.py拒绝覆盖旧标签。环境：PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONPATH=src。Python为本机 E:/Adobe/python.exe。

```powershell
& E:/Adobe/python.exe -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-targeted-01 test_pre_p19_autonomy
& E:/Adobe/python.exe -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-full-01
```

独立审查原探针副本保持原样。本轮 probe.py 只调用其 pure_probes/native_fixture_probe；不调用会写回规划目录的旧main。诊断字段不是正式测试PASS计数：

```powershell
& E:/Adobe/python.exe -B docs/project_memory/pre_p19_autonomy_evidence/probe.py review-diagnostic-01
```

全部测试仅使用隔离TEST根；进程控制器显式STOP/回收自己的子进程。未取得远端CI，不声明CI PASS。本批次不修改生产政策，D1/D2/D3及真实服务/部署保持原NOT_READY。

R4补充正常逐步进入低变化区的完整过程见[progressive-02](progressive-02.json)：15轮中第7—15轮低于原驱力delta门槛仍实际认知，源码未变。该额外场景及首次观察脚本ERROR单列，不重复增加正式测试数。
