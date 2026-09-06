# P12 前整体审查修复：用户验收与 Git 收尾入口

<a id="pre-p12-accepted"></a>

## 用户正式验收

2026-09-06，用户明确确认接受 R01—R08 整体修复及后续 R05/R06 补修。最终独立复核已通过，验收前现场 193 个源码/测试文件与全量前稳定快照及监工核验版本一致。登记 [D-059](04_决策记录.md#d-059)，本轮整体修复和补修现行状态为 **ACCEPTED**。

P00—P11 历史 ACCEPTED 保持，P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE，EVIDENCE_CONFLICT = NONE。这里的 NONE 仅表示本轮已解决的审查阻断闭合，不否认历史 FAIL/ERROR/SKIP，不表示未来阶段已开工或所有未知缺陷均已排除。

本轮仅做验收档案和获授权的 Engine Git 收尾，不修改运行代码/测试、不重跑全量、不修改 Assistant、不接生产 Adapter/真实 Provider/Vio、不改变 Authority 或账本、不进入 P12/P17。

## 独立实跑与全量引用

| 证据 | 来源及真实结果 | 耗时 |
| --- | --- | ---: |
| 原独立探针 | 规划监工最终独立实跑 21/21 PASS；R05/R06 三个遗留反例全部闭合 | 1.485 秒 |
| 两轮正式定点及 Resources/Learning 兼容 | 规划监工最终独立实跑 74/74 PASS，0 FAIL/ERROR/SKIP | 4.317 秒 |
| 完整 Engine 回归 | 修复方先前实跑，监工核验引用；894 项，893 PASS、1 既有 SKIP、0 FAIL/ERROR。本次归档未重复执行 | 425.134 秒；墙钟 425.738 秒 |
| 源码与测试身份 | 当前 193 个源码/测试文件 SHA-256 对应完整全量；894 项发现身份与日志、稳定清单完全一致 | 只读核验，不计为测试执行 |
| 置信度公式 | 监工独立比对 4608 组纯公式输入与既有政策等价 | 不是 4608 项端到端测试 |

唯一 SKIP 仍是 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`：Windows symlink 创建权限不足，错误码 1314。该项未变成 PASS，也没有新增跳过项；用户验收涵盖这一已如实披露的环境限制。

最终独立材料按原字节归档，未修改规划工作区原件：

- [最终独立报告](pre_p12_acceptance_evidence/independent-final/final-review.md)
- [21 项独立输出](pre_p12_acceptance_evidence/independent-final/independent-probes.log)
- [74 项定点及兼容输出](pre_p12_acceptance_evidence/independent-final/targeted-and-compatibility.log)
- [全量身份/时间/hash/公式核验](pre_p12_acceptance_evidence/independent-final/evidence-verification.json)及[核验脚本原件](pre_p12_acceptance_evidence/independent-final/verify_evidence.py)
- [监工开始修正清单](pre_p12_acceptance_evidence/independent-final/before-corrected.json)与[结束清单](pre_p12_acceptance_evidence/independent-final/after.json)
- [修复方完整全量日志](pre_p12_r05_r06_evidence/final-full.stderr.log)、[运行元数据](pre_p12_r05_r06_evidence/final-full.json)及[稳定源码/测试清单](pre_p12_r05_r06_evidence/stable-source.json)

监工初次读取清单形状错误、namespace 测试目录发现入口错误、日志身份拼接错误均为辅助核验错误，原始 before.json 和两个错误日志保留在同一归档目录；正确结论来自其后已完成的核验，不将辅助错误计为 Engine 缺陷，也不删除历史。

## 现行修复验收矩阵

| 项目 | 已验收范围 | 当前状态 | 可追溯证据 |
| --- | --- | --- | --- |
| R01 | 事件本机线程读/检/追加/写回事务、成功历史与稳定重放身份、revision 兼容 | ACCEPTED | [原根因/修复/失败记录](P12前整体审查_R01-R08修复与复核入口.md)、21/74 独立实跑 |
| R02 | 权限限制单调收缩、真实 scope 包含关系、撤销权限不复活 | ACCEPTED | 原八项档案、21/74 独立实跑 |
| R03 | 模型首次与可信 NOT_EXECUTED 恢复执行前预算门、已发生事实仍可核实 | ACCEPTED | 原八项档案、21/74 独立实跑 |
| R04 | UNKNOWN/冲突查询与健康任务有界公平、冲突退避、原调度门保留 | ACCEPTED | 原八项档案、21/74 独立实跑 |
| R05 | 资源重复身份、允许/拒绝共用事务内 request/session 检查、首个结果保留及结算 | ACCEPTED | [R05/R06 补修记录](P12前整体审查_R05-R06补修与复核入口.md)、21/74 独立实跑 |
| R06 | 当前支持重查、既有置信度公式一致、目标自身与聚合值区分、确认/Evolution 边界 | ACCEPTED | R05/R06 补修记录、21/74 独立实跑及公式核验 |
| R07 | 部分重叠记忆新增合法根、完全重复去重、来源追溯与持久完整性 | ACCEPTED | 原八项档案、21/74 独立实跑 |
| R08 | 当前 TEST 唤醒接线的 task/request/subject/environment/cycle/session 绑定及零副作用拒绝 | ACCEPTED | 原八项档案、21/74 独立实跑 |

不扩展为多进程/分布式存储、任意生产 Adapter exactly-once、生产漏洞验证或新的执行/状态 Authority。原单一 E5-A 恢复与幂等通道保持。

## 历史保存与保护边界

原八项施工及两轮补修档案作为历史快照保留，包括开工 839 项（838 PASS、1 SKIP）、首轮 39/878、后续 16 项红灯、两次独立三个反例失败、首次全量 3 ERROR、所有辅助字段/NameError/启动错误，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN。旧日志和原始 hash 清单不改写。

验收开工 [before.json](pre_p12_acceptance_evidence/before.json) 固定 976 个已跟踪/未跟踪、未忽略文件；其中 193 个源码/测试文件与监工一致，63 个保护文件全部一致（25 项冻结边界，含六份 Schema、外部契约与 pyproject；正式 7 文件；31 个 P10 辅助脚本）。版本保持 0.1.0，正式数据路径和逐文件 SHA-256 不变；历史正式数据树指纹为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

## 精确 Git 收尾边界

用户已在本次明确连续授权验收归档、精确暂存、一次普通提交和普通推送，目标仅为 Engine `main` → 已配置 `origin/main`：`https://github.com/yuan69082-code/continuity-engine.git`。开工 HEAD、本地 origin/main 及宿主凭据上下文实际查询的远端 main 均为 `5f25d0cef3798aa380d457ae670db30ee1b47407`。

提交说明：`fix: resolve and accept pre-P12 review findings`。提交覆盖全部尚未提交的 R01—R08 和 R05/R06 源码、测试、必要失败/修复证据及验收档案；不能仅提交最后两个运行文件。31 个原有 P10 本地辅助脚本原样排除。正式数据、缓存、Sandbox/Temp、wheel、构建目录、凭据及无关材料不进入提交。准确清单见[逐文件分类](pre_p12_acceptance_evidence/commit-files.md)与[机器清单](pre_p12_acceptance_evidence/commit-files.json)；归档后检查见[提交前只读核查](pre_p12_acceptance_evidence/pre-commit-audit.json)。

不得 `git add .`、无差别 `git add -A`、强推、amend、改写历史、创建分支/tag/release 或变更 remote。暂存后必须核对集合、内容与保护边界。提交和推送的真实 SHA、远端核验、CI 状态及最终剩余文件以执行后的交付报告为准；本档案不预填尚未发生的 Git 成功。

当前修复前置已验收；P12 仍等待用户下一项明确开工指令。

归档辅助检查曾因启动命令漏设 `PYTHONPATH=src` 出现 discovery import ERROR，未执行测试方法；补齐环境后按同一源码核验。错误与纠正范围保存在[归档辅助记录](pre_p12_acceptance_evidence/archive-diagnostics.json)，不计为 Engine 回归失败，不修改原测试或通过数量。

暂存后默认 `git diff --cached --check` 返回 2：六份首轮独立原始日志/审计 JSON 存在历史 EOF 空行。逐份 SHA-256 与验收开工原件完全一致，不能为消除格式提示改写原始证据。原输出与明确文件清单见上述归档辅助记录；其余全部暂存文件单独进行零空白错误检查，所有文件仍核对精确 blob。本例外仅限原样保留的六份历史原件，不改变源码、测试、Git 配置或验收标准。
