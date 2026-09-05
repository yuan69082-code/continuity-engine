# P11 待提交与排除清单（2026-09-05）

这是当前整个未提交 P11 工作区的逐文件清单，不是本次归档新增代码清单。本次只修改验收档案；以下源码和测试均为先前已完成、已独立复核的 P11 成果，本轮 hash 不变。没有暂存、提交或推送任何文件。

状态列 ` M` 表示已跟踪且仅工作区修改，`??` 表示未跟踪新增；暂存区为空。HEAD/main/本地 origin/main 为 `a905853ca05edd56d9a8b0164818b4388a90b85f`，ahead/behind=0/0。

用户若后续授权提交，应逐项选择 P11 文件；31 个 P10 本地辅助脚本原样保留并排除。私有 wheel、CI ZIP、缓存、Temp 运行数据、凭证和正式数据均不在本清单的 P11 待提交范围。本清单不构成 Git 操作。

归档正文同步 53 份 Markdown，其中旧阶段档案仅同步原有的现行 P11 状态导航；历史正文、失败记录与修复前全量结果继续保留。证据目录中包含历史原始文本日志、清单、辅助错误记录及修复前两文件副本，不是运行期数据。

## 先前 P11 源码与测试（本次未修改）：14 个

| Git 状态 | 精确路径（仓库相对） |
| --- | --- |
| ` M` | `src/continuity_engine/__init__.py` |
| ` M` | `src/continuity_engine/domain/__init__.py` |
| `??` | `src/continuity_engine/domain/scheduling.py` |
| ` M` | `src/continuity_engine/services/__init__.py` |
| ` M` | `src/continuity_engine/services/resource_aware_wake_scheduler.py` |
| `??` | `src/continuity_engine/services/scheduler_ports.py` |
| `??` | `src/continuity_engine/services/scheduler_service.py` |
| ` M` | `src/continuity_engine/storage/__init__.py` |
| ` M` | `src/continuity_engine/storage/base.py` |
| `??` | `src/continuity_engine/storage/json_scheduler_repository.py` |
| ` M` | `src/continuity_engine/testing/__init__.py` |
| `??` | `src/continuity_engine/testing/p11_scheduler_fixture.py` |
| `??` | `tests/test_p11_scheduler.py` |
| `??` | `tests/test_p11_scheduler_recovery.py` |

## 工程与验收 Markdown 档案：53 个

| Git 状态 | 精确路径（仓库相对） |
| --- | --- |
| ` M` | `README.md` |
| ` M` | `docs/project_memory/00_项目总览.md` |
| ` M` | `docs/project_memory/01_当前状态.md` |
| ` M` | `docs/project_memory/02_工程路线图.md` |
| ` M` | `docs/project_memory/03_施工日志.md` |
| ` M` | `docs/project_memory/04_决策记录.md` |
| ` M` | `docs/project_memory/05_已完成模块.md` |
| ` M` | `docs/project_memory/05_核心模块架构.md` |
| ` M` | `docs/project_memory/06_未完成事项.md` |
| ` M` | `docs/project_memory/07_待确认事项.md` |
| ` M` | `docs/project_memory/08_未来扩展.md` |
| ` M` | `docs/project_memory/09_开发规范.md` |
| ` M` | `docs/project_memory/10_档案修订记录.md` |
| ` M` | `docs/project_memory/11_P00_全周期能力与阶段基线.md` |
| ` M` | `docs/project_memory/12_P00_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/13_P00_档案与测试索引.md` |
| ` M` | `docs/project_memory/14_P00_风险回滚与用户决策入口.md` |
| ` M` | `docs/project_memory/16_P01_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/19_P02_宿主中立模型能力架构与边界.md` |
| ` M` | `docs/project_memory/20_P02_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/23_P03_Event时间与Timeline架构边界.md` |
| ` M` | `docs/project_memory/24_P03_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/27_P04_MemoryConsolidation与DerivedSummary架构边界.md` |
| ` M` | `docs/project_memory/28_P04_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/31_P05_ContextRouter架构边界.md` |
| ` M` | `docs/project_memory/32_P05_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/33_P05_权限检索预算来源失效与ContextTrace语义.md` |
| ` M` | `docs/project_memory/34_P05_测试索引与验收入口.md` |
| ` M` | `docs/project_memory/35_P06_ContextComposer与Authority架构边界.md` |
| ` M` | `docs/project_memory/36_P06_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/37_P06_ContextBudget去重冲突缺失与Trace语义.md` |
| ` M` | `docs/project_memory/38_P06_测试索引与验收入口.md` |
| ` M` | `docs/project_memory/39_P07_ContradictionDetector架构边界.md` |
| ` M` | `docs/project_memory/40_P07_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/41_P07_矛盾分类隔离核实解决与Trace语义.md` |
| ` M` | `docs/project_memory/42_P07_测试索引与验收入口.md` |
| ` M` | `docs/project_memory/43_P08_DirectAction与OptionalPlanner架构边界.md` |
| ` M` | `docs/project_memory/44_P08_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/45_P08_DirectPlanner执行恢复语义.md` |
| ` M` | `docs/project_memory/46_P08_测试索引与验收入口.md` |
| ` M` | `docs/project_memory/47_P09_C1正常运行链与架构边界.md` |
| ` M` | `docs/project_memory/48_P09_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/49_P09_恢复组合语义与施工证据.md` |
| ` M` | `docs/project_memory/50_P09_测试索引与C1运行入口.md` |
| ` M` | `docs/project_memory/51_P10_Assistant建仓架构与StageBrief.md` |
| ` M` | `docs/project_memory/52_P10_规划施工测试验收矩阵.md` |
| ` M` | `docs/project_memory/53_P10_来源Checkpoint与跨仓版本同步.md` |
| `??` | `docs/project_memory/55_P11_EventPriority与Scheduler架构边界.md` |
| `??` | `docs/project_memory/56_P11_规划施工测试验收矩阵.md` |
| `??` | `docs/project_memory/57_P11_队列恢复重试取消与投递语义.md` |
| `??` | `docs/project_memory/58_P11_测试索引与验收入口.md` |
| ` M` | `docs/project_memory/CHANGELOG.md` |
| ` M` | `docs/project_memory/工程总档案.md` |

## P11 文本证据与本次归档核查：69 个

| Git 状态 | 精确路径（仓库相对） |
| --- | --- |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/archive-audit.json` |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/before.json` |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/document-changes.json` |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/helper-observation.txt` |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/matrix-before.md` |
| `??` | `docs/project_memory/p11_evidence/acceptance-20260905/pending-files.md` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/audit.json` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/before.json` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/diff-check.stderr.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/diff-check.stdout.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/p11-specialized.json` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/p11-specialized.stderr.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/p11-specialized.stdout.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/scheduler_service.py.before.txt` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-green.json` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-green.stderr.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-green.stdout.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-red.json` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-red.stderr.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/targeted-red.stdout.log` |
| `??` | `docs/project_memory/p11_evidence/admission-repair-20260905/test_p11_scheduler.py.before.txt` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/identity-helper-first-error.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/identity-helper-second-error.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p09-composition-first.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p09-composition-first.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p11-crash-sentinel-second.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p11-crash-sentinel-second.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p11-first-implementation.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/p11-first-implementation.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/resource-aware-boundary-red.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/resource-aware-boundary-red.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/scheduled-wake-boundary-red.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/scheduled-wake-boundary-red.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/unknown-query-delivery-red.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/unknown-query-delivery-red.log` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/unknown-starvation-red.json` |
| `??` | `docs/project_memory/p11_evidence/implementation-20260905/unknown-starvation-red.log` |
| `??` | `docs/project_memory/p11_evidence/red-20260905/p11-red-first.json` |
| `??` | `docs/project_memory/p11_evidence/red-20260905/p11-red-first.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/direct-related-final-code.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/direct-related-final-code.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/direct-related.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/direct-related.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/final-worktree-check.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-final-archive.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-final-archive.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-1.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-1.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-2.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-2.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-3.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/full-round-3.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p00-p11-matrix-final-code.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p00-p11-matrix-final-code.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p00-p11-matrix.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p00-p11-matrix.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized-final-archive.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized-final-archive.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized-final-code.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized-final-code.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/p11-specialized.log` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/post-final-audit-assistant-head-assumption-failure.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/post-final-audit-helper-failure.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/post-final-audit.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/pre-final-audit.json` |
| `??` | `docs/project_memory/p11_evidence/stable-20260905/test-identities.json` |
| `??` | `docs/project_memory/p11_evidence/start-20260905/before.json` |
| `??` | `docs/project_memory/p11_evidence/start-20260905/planning-sources.json` |

## 明确排除：既有 P10 本地辅助脚本（原样保留）：31 个

| Git 状态 | 精确路径（仓库相对） |
| --- | --- |
| `??` | `docs/project_memory/p10_evidence/closeout-20260904/check_stop.py` |
| `??` | `docs/project_memory/p10_evidence/closeout-20260904/closeout.py` |
| `??` | `docs/project_memory/p10_evidence/closeout-20260904/preserve_failed_closeout.py` |
| `??` | `docs/project_memory/p10_evidence/closeout-20260904/record_stop.py` |
| `??` | `docs/project_memory/p10_evidence/closeout-20260904/sync_assistant.py` |
| `??` | `docs/project_memory/p10_evidence/create_repositories.py` |
| `??` | `docs/project_memory/p10_evidence/final_audit.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-case-repair-20260904/audit.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-case-repair-20260904/independent/p10_fixture_repair_review_probe.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-case-repair-20260904/prepare.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-case-repair-20260904/run.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-case-repair-20260904/sync_docs.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/audit.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/baseline.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/engineering.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/engineering_resume.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/run.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/sync_docs.py` |
| `??` | `docs/project_memory/p10_evidence/fixture-repair-20260904/temp_probe.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/advance.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/build_review_report.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/ci_evidence.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/document_check.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/final_audit.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/repair_namespace_diagnostic.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/temp_checkout_probe.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/validate_temp.py` |
| `??` | `docs/project_memory/p10_evidence/launcher-repair-20260905/workflow.py` |
| `??` | `docs/project_memory/p10_evidence/outside_temp_clone.py` |
| `??` | `docs/project_memory/p10_evidence/publish_assistant.py` |
| `??` | `docs/project_memory/p10_evidence/remote_review.py` |

## 其他未分类成果（若非空须先核实）：0 个

无。

## 当前结论

P00—P11 = ACCEPTED；P11 / Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED。D-058 已登记；入队阻断关闭。监工原两个反例 2/2 PASS，P11 45/45 PASS（8.371 秒）。本次没有运行测试，修复前全量仍是历史证据。

本清单仅反映当前工作区。正式 P11 提交 SHA 尚未产生，不能将开工 HEAD 当作最终 P11 提交。
