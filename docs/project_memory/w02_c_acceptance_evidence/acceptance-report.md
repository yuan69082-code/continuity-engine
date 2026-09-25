# W02-C 正式验收与交付入口（D-080）

2026-09-25，用户正式验收 W02-C/N11 初版及派生材料部分撤回补修，并授权本批按精确清单普通提交、普通推送到现有 Engine `origin/main`。本报告登记验收事实；提交和远端结果以操作后的实际核对为准，不预填成功。

现行依据为[总施工 v1.5、最终新增 v1.5、长期能力 v6.9](../现行规划版本索引.md)。[逐项验收矩阵](acceptance-matrix.md)对应 Planning Item → Code Change → Test → Acceptance Result。W02-A/B/C = ACCEPTED，W02 整体仍为 IN_PROGRESS；W02 总贯通、W03、P19 均未开工。P00—P18 历史验收不变。

## 证据口径

规划监工窗口进行了只读代码与原始证据复核，**没有独立运行 Engine 测试**。本次验收引用施工方同一固定源码指纹 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea` 的实际运行；本轮纯档案归档没有重跑测试：

| 集合 | 原始结果 | 耗时 | 退出码 |
| --- | --- | ---: | ---: |
| W02-C 专项 | [25/25 PASS](../w02_c_repair_evidence/formal-final-01.json) | 88.514 秒 | 0 |
| W02-A/B 兼容 | [123/123 PASS](../w02_c_repair_evidence/w02-ab-final-01.json) | 130.130 秒 | 0 |
| 公共兼容 | [260/260 PASS](../w02_c_repair_evidence/public-final-01.json) | 213.540 秒 | 0 |
| Engine 全量 | [1728 项：1727 PASS、1 既有 SKIP、0 FAIL/ERROR](../w02_c_repair_evidence/full-final-01.json) | 1627.654 秒 | 0 |

集合互有重叠，不相加。SKIP 为既有 Windows 符号链接权限 1314，不计 PASS。四组运行前后源码身份一致，见[施工终局审计](../w02_c_repair_evidence/final.audit.json)。没有取得可验证的远端 CI 结果，不声明 CI PASS。

## 验收范围及现行限制

原 P16/E5-A 回执证明资料取得，W02-C 的根证明、候选处置和回应前投影保持派生地位；当前有权且相关的资料经原 Router/Composer 使用。同源原文、翻译、摘要和转存不重复算独立根；具备隔离 TEST 明确策略的独立有效根可沿原 P04 路径形成长期 Memory。资料中的指令不获得权限、人格或 SubjectState 写权。

补修的有效修前反例证明：同版有效根保留原文、仅撤回一份派生材料认可时，旧 Memory 曾继续被认为可用。现于原外部 Memory 消费核验处逐根核对该 Memory 对应材料 hash，使直接候选、旧 Context、依赖 Summary、P15 当前学习支持与下一轮回应停止使用撤回内容，同时保留历史取得事实。修前失败、两次辅助测试前提错误、修后正反及跨进程证据均见[补修测试索引](../w02_c_repair_evidence/test-index.md)，不改写为从未失败。

本批现行 `PLANNING_CONFLICT=NONE`、`EVIDENCE_CONFLICT=NONE` 仅表示经本次验收关闭 W02-C 已知撤销传播阻断，不保证不存在其他缺陷。历史 F1/H1/F2 根因继续 UNKNOWN；旧失败、中断、辅助错误与既有 SKIP 保留。真实资料服务属 P22、跨 Store/备份生产删除传播属 P20、完整页面属 P19；W02 最后贯通仍待单独授权。这些能力未在本批开放。

## 保护与提交范围

本次验收仅新增和更新档案，不修改已复核运行代码、正式测试或资源。63 项保护文件、三份现行规划、正式七文件和 57 项排除材料按[最终审计](final.audit.json)核对；原[179 项施工快照](../w02_c_repair_evidence/final.pending-files.md)及首次失败保留。包含验收增量的[最终逐文件提交与排除清单](final.pending-files.md)和[机器指纹](final.files.json)为本次 Git 范围依据。
