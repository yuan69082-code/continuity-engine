# W02 整体贯通正式验收（D-081）

2026-09-25，用户正式验收 W02-A/B/C 的同版整体贯通，并授权必要验收归档、精确普通提交及向现有 Engine `origin/main` 普通推送。W02-A/B/C 各自原验收不变；W02 整体 = `ACCEPTED`。P00—P18 历史验收保持，W03、W04、P19 及后续阶段不因此开工。本次验收不改变运行实现、原测试断言或保护边界。[D-081 正式决定](../04_决策记录.md#d-081用户正式验收-w02-整体贯通并授权精确提交与普通推送)及[逐项验收矩阵](acceptance-matrix.md)保留 Planning Item → Code Change → Test → Acceptance Result 的对应。

## 验收依据与证据口径

权威仍为[现行规划版本索引](../现行规划版本索引.md)所列总施工 v1.5、最终新增 v1.5、长期能力 v6.9，以及 W02 施工卡、N01/N02/N11、T01—T06/T18/T23 的内部部分。规划窗口进行了源码、原始结果、文件身份和保护边界的**独立只读复核，没有独立运行 Engine 测试**。本决定引用施工窗口同一固定源码/测试/资源指纹 `sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1` 上的原始实跑；本次纯验收档案不重跑全量：

| 集合 | 原始证据 | 结果 | 耗时、退出码 |
| --- | --- | --- | --- |
| W02 贯通专项 | [integration-targeted-01](../w02_integration_evidence/integration-targeted-01.json) | 8/8 PASS | 32.328 秒、0 |
| A/B/C 兼容 | [w02-abc-compat-01](../w02_integration_evidence/w02-abc-compat-01.json) | 156/156 PASS | 251.675 秒、0 |
| 公共兼容 | [public-compat-01](../w02_integration_evidence/public-compat-01.json) | 318/318 PASS | 291.693 秒、0 |
| Engine 完整回归 | [full-final-01](../w02_integration_evidence/full-final-01.json) | 1736 项：1735 PASS、1 个既有 Windows 1314 SKIP、0 FAIL/ERROR | 1677.033 秒、0 |

各集合互有重叠，不相加。[原始 stdout/stderr、命令、前后源码身份及历史失败索引](../w02_integration_evidence/test-index.md)保留；没有可验证的远端 CI 结果，不声明 CI PASS。

## 已关闭的本批阻断与保留风险

本批真实发现的 A+B 断点缺口是：W02-A 的 `memory` 站处于 `FAILED_WAITING`，W02-B 已准备的 Context 快捷路径未先完成该站，同一请求重开报 `INPUT_UNFINISHED_STATION_WITH_CONTEXT`。用户另行授权的定点补修只在原 `ContinuityCoreService._prepare` 复用分支沿同一请求完成待处理站、复核成功事实和当前 Context；修前同反例 ERROR，修后同反例、重复失败、撤权和原成功材料对照 PASS，A/B/C 与公共兼容及全量同版通过。[修前、修后和辅助错误](../w02_integration_evidence/repair-report.md)原样保留。因此该项现行验收阻断关闭，本次 W02 范围 `PLANNING_CONFLICT=NONE`、`EVIDENCE_CONFLICT=NONE`；这仅表示已知阻断在本次复核范围内闭合，不保证不存在其他缺陷。

另一项**没有宣称解决**：早期新增贯通场景中，四份外部资料同时进入的 TEST 历史在第四次提交触及原有 1000 毫秒回忆时限，明确返回 `RECALL_TIMEOUT`，没有伪造回答或把检索失败说成历史不存在。最终同版贯通使用两份外部资料、两项独立根证明，并未在最终版重跑原四份负载；所以不能推断四份负载现已通过。其影响限于该受控复杂组合在既有时限内无法完成回忆，不等于已证明派生撤回失效或生产性能结论。需要扩展该负载的验证或调整预算时，应另行按阶段和授权处理。[首次原始失败](../w02_integration_evidence/integration-draft-01.stderr.log)保留。

历史 F1/H1/F2 根因继续 `UNKNOWN`，原 FAIL/ERROR、中断、辅助 Fixture/断言错误及既有 Windows 1314 SKIP 不倒写为 PASS。真实资料服务 P22、跨 Store/备份删除 P20、W03 长期认识部分、P19 页面继续 `NOT_READY`；本次内部 TEST 贯通验收不开放生产接入。

## 本次归档与 Git 边界

[原 81 项交付清单](../w02_integration_evidence/final.pending-files.md)保留为验收前快照；本次只增加必要验收决定、状态、施工日志、完成/未完成事项、验收矩阵与索引。验收归档后[终局审计](final.audit.json)、[逐文件 hash](final.files.json)和[精确提交/排除清单](final.pending-files.md)为当前文件范围依据。63 项保护文件、三份规划、正式七文件及 57 项原排除材料保持不变。实际提交、推送和远端核对只能以操作后结果报告，不在归档时预填成功；本次不启动下一批。
