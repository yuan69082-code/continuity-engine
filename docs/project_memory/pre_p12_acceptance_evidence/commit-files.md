# P12 前整体审查修复：本次精确提交清单

D-059；覆盖整个尚未提交的 R01—R08 及 R05/R06 成果。路径相对 Engine 根。应提交 **139** 个文件，排除 **31** 个原有 P10 辅助脚本，其他未忽略且无关/不应提交文件 **0** 个。忽略的正式数据、缓存、Temp/Sandbox、构建和 wheel 不参加暂存。

## 修复运行源码（10）

```text
src/continuity_engine/services/learning_service.py
src/continuity_engine/services/memory_consolidation_service.py
src/continuity_engine/services/model_capability_service.py
src/continuity_engine/services/permission_service.py
src/continuity_engine/services/resource_manager.py
src/continuity_engine/services/scheduler_service.py
src/continuity_engine/services/subject_state_service.py
src/continuity_engine/storage/json_repository.py
src/continuity_engine/storage/json_resource_repository.py
src/continuity_engine/testing/p11_scheduler_fixture.py
```

## 正式回归测试（3）

```text
tests/test_permissions.py
tests/test_pre_p12_r05_r06_followup.py
tests/test_pre_p12_repairs.py
```

## 工程与验收档案（16）

```text
README.md
docs/project_memory/01_当前状态.md
docs/project_memory/03_施工日志.md
docs/project_memory/04_决策记录.md
docs/project_memory/05_已完成模块.md
docs/project_memory/06_未完成事项.md
docs/project_memory/07_待确认事项.md
docs/project_memory/10_档案修订记录.md
docs/project_memory/13_P00_档案与测试索引.md
docs/project_memory/57_P11_队列恢复重试取消与投递语义.md
docs/project_memory/58_P11_测试索引与验收入口.md
docs/project_memory/CHANGELOG.md
docs/project_memory/P12前整体审查_R01-R08修复与复核入口.md
docs/project_memory/P12前整体审查_R05-R06补修与复核入口.md
docs/project_memory/P12前整体审查_用户验收与Git收尾.md
docs/project_memory/工程总档案.md
```

## 必要修复及验收证据（110）

```text
docs/project_memory/pre_p12_acceptance_evidence/archive-diagnostics.json
docs/project_memory/pre_p12_acceptance_evidence/before.json
docs/project_memory/pre_p12_acceptance_evidence/commit-files.json
docs/project_memory/pre_p12_acceptance_evidence/commit-files.md
docs/project_memory/pre_p12_acceptance_evidence/independent-final/after.json
docs/project_memory/pre_p12_acceptance_evidence/independent-final/before-corrected.json
docs/project_memory/pre_p12_acceptance_evidence/independent-final/before.json
docs/project_memory/pre_p12_acceptance_evidence/independent-final/evidence-helper-initial-error.log
docs/project_memory/pre_p12_acceptance_evidence/independent-final/evidence-helper-name-format-error.log
docs/project_memory/pre_p12_acceptance_evidence/independent-final/evidence-verification.json
docs/project_memory/pre_p12_acceptance_evidence/independent-final/final-review.md
docs/project_memory/pre_p12_acceptance_evidence/independent-final/independent-probes.log
docs/project_memory/pre_p12_acceptance_evidence/independent-final/targeted-and-compatibility.log
docs/project_memory/pre_p12_acceptance_evidence/independent-final/verify_evidence.py
docs/project_memory/pre_p12_acceptance_evidence/pre-commit-audit.json
docs/project_memory/pre_p12_r05_r06_evidence/audit.py
docs/project_memory/pre_p12_r05_r06_evidence/before.json
docs/project_memory/pre_p12_r05_r06_evidence/final-audit.json
docs/project_memory/pre_p12_r05_r06_evidence/final-full.json
docs/project_memory/pre_p12_r05_r06_evidence/final-full.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/final-full.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/final-targeted.json
docs/project_memory/pre_p12_r05_r06_evidence/final-targeted.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/final-targeted.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/formal-red.json
docs/project_memory/pre_p12_r05_r06_evidence/formal-red.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/formal-red.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/git-status.txt
docs/project_memory/pre_p12_r05_r06_evidence/helper-diagnostics.json
docs/project_memory/pre_p12_r05_r06_evidence/independent-green.json
docs/project_memory/pre_p12_r05_r06_evidence/independent-green.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/independent-green.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/independent-red.json
docs/project_memory/pre_p12_r05_r06_evidence/independent-red.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/independent-red.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/interim-audit.json
docs/project_memory/pre_p12_r05_r06_evidence/pending-files.md
docs/project_memory/pre_p12_r05_r06_evidence/r05-green.json
docs/project_memory/pre_p12_r05_r06_evidence/r05-green.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/r05-green.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/r06-green.json
docs/project_memory/pre_p12_r05_r06_evidence/r06-green.stderr.log
docs/project_memory/pre_p12_r05_r06_evidence/r06-green.stdout.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/baseline-learning-and-launcher-error.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/baseline-learning.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/baseline_learning_check.py
docs/project_memory/pre_p12_r05_r06_evidence/review-original/before.json
docs/project_memory/pre_p12_r05_r06_evidence/review-original/engine-full.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/engine-targeted.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/independent-probes-01.log
docs/project_memory/pre_p12_r05_r06_evidence/review-original/readonly-audit.json
docs/project_memory/pre_p12_r05_r06_evidence/review-original/recheck-report.md
docs/project_memory/pre_p12_r05_r06_evidence/review-original/recheck_probes.py
docs/project_memory/pre_p12_r05_r06_evidence/run_tests.py
docs/project_memory/pre_p12_r05_r06_evidence/stable-source.json
docs/project_memory/pre_p12_r05_r06_evidence/test-results.json
docs/project_memory/pre_p12_repair_evidence/audit.py
docs/project_memory/pre_p12_repair_evidence/before.json
docs/project_memory/pre_p12_repair_evidence/binding-confidence-red.json
docs/project_memory/pre_p12_repair_evidence/binding-confidence-red.stderr.log
docs/project_memory/pre_p12_repair_evidence/binding-confidence-red.stdout.log
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-green.json
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-green.stderr.log
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-green.stdout.log
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-targeted.json
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-targeted.stderr.log
docs/project_memory/pre_p12_repair_evidence/compatibility-repair-targeted.stdout.log
docs/project_memory/pre_p12_repair_evidence/expanded-targeted-first.json
docs/project_memory/pre_p12_repair_evidence/expanded-targeted-first.stderr.log
docs/project_memory/pre_p12_repair_evidence/expanded-targeted-first.stdout.log
docs/project_memory/pre_p12_repair_evidence/final-audit.json
docs/project_memory/pre_p12_repair_evidence/final-full-02.json
docs/project_memory/pre_p12_repair_evidence/final-full-02.stderr.log
docs/project_memory/pre_p12_repair_evidence/final-full-02.stdout.log
docs/project_memory/pre_p12_repair_evidence/final-full.json
docs/project_memory/pre_p12_repair_evidence/final-full.stderr.log
docs/project_memory/pre_p12_repair_evidence/final-full.stdout.log
docs/project_memory/pre_p12_repair_evidence/final-targeted-02.json
docs/project_memory/pre_p12_repair_evidence/final-targeted-02.stderr.log
docs/project_memory/pre_p12_repair_evidence/final-targeted-02.stdout.log
docs/project_memory/pre_p12_repair_evidence/final-targeted.json
docs/project_memory/pre_p12_repair_evidence/final-targeted.stderr.log
docs/project_memory/pre_p12_repair_evidence/final-targeted.stdout.log
docs/project_memory/pre_p12_repair_evidence/formal-first-green.json
docs/project_memory/pre_p12_repair_evidence/formal-first-green.stderr.log
docs/project_memory/pre_p12_repair_evidence/formal-first-green.stdout.log
docs/project_memory/pre_p12_repair_evidence/formal-red.json
docs/project_memory/pre_p12_repair_evidence/formal-red.stderr.log
docs/project_memory/pre_p12_repair_evidence/formal-red.stdout.log
docs/project_memory/pre_p12_repair_evidence/helper-diagnostics.json
docs/project_memory/pre_p12_repair_evidence/independent-red.json
docs/project_memory/pre_p12_repair_evidence/independent-red.stderr.log
docs/project_memory/pre_p12_repair_evidence/independent-red.stdout.log
docs/project_memory/pre_p12_repair_evidence/interim-audit.json
docs/project_memory/pre_p12_repair_evidence/pending-files.md
docs/project_memory/pre_p12_repair_evidence/r01-r03-green.json
docs/project_memory/pre_p12_repair_evidence/r01-r03-green.stderr.log
docs/project_memory/pre_p12_repair_evidence/r01-r03-green.stdout.log
docs/project_memory/pre_p12_repair_evidence/review-original/baseline-final-chunk.log
docs/project_memory/pre_p12_repair_evidence/review-original/final-readonly-audit.json
docs/project_memory/pre_p12_repair_evidence/review-original/probe-final.log
docs/project_memory/pre_p12_repair_evidence/review-original/probe-run-02.log
docs/project_memory/pre_p12_repair_evidence/review-original/probe-run-03.log
docs/project_memory/pre_p12_repair_evidence/review-original/probe-run-04.log
docs/project_memory/pre_p12_repair_evidence/review-original/review-report.md
docs/project_memory/pre_p12_repair_evidence/review-original/review_probes.py
docs/project_memory/pre_p12_repair_evidence/run_tests.py
docs/project_memory/pre_p12_repair_evidence/stable-source-02.json
docs/project_memory/pre_p12_repair_evidence/stable-source.json
docs/project_memory/pre_p12_repair_evidence/test-results.json
```

## 原样排除的 31 个 P10 脚本

```text
docs/project_memory/p10_evidence/closeout-20260904/check_stop.py
docs/project_memory/p10_evidence/closeout-20260904/closeout.py
docs/project_memory/p10_evidence/closeout-20260904/preserve_failed_closeout.py
docs/project_memory/p10_evidence/closeout-20260904/record_stop.py
docs/project_memory/p10_evidence/closeout-20260904/sync_assistant.py
docs/project_memory/p10_evidence/create_repositories.py
docs/project_memory/p10_evidence/final_audit.py
docs/project_memory/p10_evidence/fixture-case-repair-20260904/audit.py
docs/project_memory/p10_evidence/fixture-case-repair-20260904/independent/p10_fixture_repair_review_probe.py
docs/project_memory/p10_evidence/fixture-case-repair-20260904/prepare.py
docs/project_memory/p10_evidence/fixture-case-repair-20260904/run.py
docs/project_memory/p10_evidence/fixture-case-repair-20260904/sync_docs.py
docs/project_memory/p10_evidence/fixture-repair-20260904/audit.py
docs/project_memory/p10_evidence/fixture-repair-20260904/baseline.py
docs/project_memory/p10_evidence/fixture-repair-20260904/engineering.py
docs/project_memory/p10_evidence/fixture-repair-20260904/engineering_resume.py
docs/project_memory/p10_evidence/fixture-repair-20260904/run.py
docs/project_memory/p10_evidence/fixture-repair-20260904/sync_docs.py
docs/project_memory/p10_evidence/fixture-repair-20260904/temp_probe.py
docs/project_memory/p10_evidence/launcher-repair-20260905/advance.py
docs/project_memory/p10_evidence/launcher-repair-20260905/build_review_report.py
docs/project_memory/p10_evidence/launcher-repair-20260905/ci_evidence.py
docs/project_memory/p10_evidence/launcher-repair-20260905/document_check.py
docs/project_memory/p10_evidence/launcher-repair-20260905/final_audit.py
docs/project_memory/p10_evidence/launcher-repair-20260905/repair_namespace_diagnostic.py
docs/project_memory/p10_evidence/launcher-repair-20260905/temp_checkout_probe.py
docs/project_memory/p10_evidence/launcher-repair-20260905/validate_temp.py
docs/project_memory/p10_evidence/launcher-repair-20260905/workflow.py
docs/project_memory/p10_evidence/outside_temp_clone.py
docs/project_memory/p10_evidence/publish_assistant.py
docs/project_memory/p10_evidence/remote_review.py
```

## 核对方式

机器清单 commit-files.json 逐文件列出工作区 SHA-256；其自身不递归写入自身 hash，暂存入口单独固定全部文件（含清单）的 Git blob，暂存后逐项核对。提交前只读记录为 pre-commit-audit.json。不得无差别暂存，不清理任何既有成果。
