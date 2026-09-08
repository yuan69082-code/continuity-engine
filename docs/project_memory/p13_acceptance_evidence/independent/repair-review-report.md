# P13 R1 R2 返修独立复核结果

2026-09-08。结论：本轮 R1/R2 独立复核通过，已发现的两项阻断闭合，未发现本轮新增阻断。可以提交用户正式验收。此结论不等于用户已验收、不宣称没有任何未知 bug，也不授权提交、push 或 P14 开工。

## R1 当前表达授权

已核对 `ExpressionPolicyService._authorize()` 使用原 ActionService 的只读评估，按当前时间、主体、表达 capability 的实际许可/成本与当前确认、资源、Recoverability、Reality 接口核验；不是只检查原 ActionDecision 或历史成功回执。

首次呈现、Port 返回后和 `verify(current=True)` 均经过当前核验。`submit`、`query_request` 拒绝当前无权正文；`expression_outcome` 先验证原事实，仅把当前访问拒绝转换成 `CURRENTLY_UNAVAILABLE`，不把 UNKNOWN/冲突回执伪装成已核实成功。

确认视图仅传给原确认/边界接口，不注册、投递或执行新请求。TEST Fixture 的显式确认与生产宿主确认必须区分：真实宿主没有确认时必须拒绝，不能从旧回执补签。代码没有新增请求存储或账本。

原三个撤权失败时点现均 PASS；额外独立检查确认，仅保留原 Action 确认而移除精确表达确认时，首次表达确实被拒绝；撤权导致物化中断后，明确重新授权可恢复原正文和 REFUSE 模式，没有重新 Thinking、执行或扣费。原合法 SILENCE 不被可见表达许可错误拦截，仍为空表达、零呈现调用、零效果和零计费。

## R2 获准的样式依据

已核对 `_style_inputs()` 只消费 Composer snapshot 中可信的 `CONFIRMED_STATE` / `engine.subject-state` 片段，不再绕过 Context 直接从完整 SubjectState 获取表达偏好。identity、relationship、emotion 的实际来源进入内部 hash/理由码；缺失时不使用相应偏好。情绪强调不借未获准的 effective_emotion 旁路补回。

原关系片段遗漏且拒绝的反例通过。正式回归覆盖三类来源的缺失、拒绝、调用期间失效及合法样式；独立补充验证三类片段同时遗漏时仍能输出未改写的原正文，而不是一律拒绝。关闭已有情绪投影功能时不额外添加情绪强调。表达没有新增认知、人格、Memory、关系或 Evolution 写权限。

## 本轮实际独立执行

| 执行 | 结果 | unittest 耗时 | 原始日志 |
|---|---|---|---|
| 原始七项探针，原件未改 | 7 PASS，0 SKIP/FAIL/ERROR | 3.832 秒 | `repair-original-probes-01.stderr.log` |
| 当前完整 P13 三个测试模块 | 59 PASS，0 SKIP/FAIL/ERROR | 55.614 秒 | `repair-p13-01.stderr.log` |
| 新增独立边界和正向对照 | 5 PASS，0 SKIP/FAIL/ERROR | 3.070 秒 | `repair-neighbors-01.stderr.log` |

三个执行的包装总耗时分别为 4.388、56.185、3.590 秒，不与 unittest 计时混用。59 项中已含原七项的正式化版本，三个数字不可相加为互不重叠的覆盖数。

新五项在 `repair_neighbor_probes.py`：SILENCE 不要求可见表达 grant、三类样式来源同时遗漏、关闭情绪投影、不以原 Action 确认替代表达确认、物化中断后明确重新授权且零重复效果。

每次执行前后均核对 Engine 1364 个非 Git、非 bytecode 文件，变化清单为空。运行器和全部新复核产物仅在规划工作区；实际测试写入均位于独立临时 TEST Fixture。原失败和规划侧首次探针辅助错误历史未覆盖。

## 身份与保护

`repair-identity-check.json` 中 21 项独立核对全部通过：

- 当前 212 个源码/测试及资源文件与返修方最终专项、全量记录完全匹配。
- 原 1049 项测试身份与原测试文件保留，当前 1070 项无重复；新增 21 项均在 `test_p13_review_regressions`。原七项探针的正式测试类 AST 与规划原件一致，没有弱化断言。
- 本轮源码/测试增量精确为五个文件：`domain/expression.py`、`services/expression_policy_service.py`、`services/continuity_interaction_service.py`、`testing/p13_expression_fixture.py`、`tests/test_p13_review_regressions.py`。
- 63 项保护文件、正式七文件、三份规划源、31 个 P10 排除脚本、独立原始证据及副本均无漂移，`git diff --check` 通过。
- 正式数据树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

返修方最终完整回归为 1070 项：1069 PASS、1 既有 Windows symlink 权限 1314 SKIP、0 FAIL/ERROR。本轮核验其当前源码身份及原 stderr 后引用，未重新运行完整全量。stderr 为 621.987 秒，结构化计时为 621.988 秒，是同一次执行。未联网核实远端，也未宣称新 CI PASS。

本次只读查看期间有两次辅助命令笔误：Select-Object 的 First 参数误写英文，以及误读不存在的 final_audit.py（本轮实际为 audit.py）。均已纠正，仅影响文件查看，不是测试失败或引擎缺陷，不涉及文件写入。

## 交接与停止点

Engine 仍在 `main`，HEAD 与本地 `origin/main` 均为 `7afceba17635a8d9fd915bf09fa9df68f3ff3974`；本地 ahead/behind 0/0、暂存空。172 个待提交成果与 31 个排除脚本保留，未执行任何 Git 写操作，未修改 Assistant。

规划侧本轮 R1/R2 阻断已闭合。Engine 当前档案仍是送审时的 `IMPLEMENTED_NOT_ACCEPTED` / `EVIDENCE_CONFLICT=PRESENT`，本次未直接修改 Engine 档案；后续验收归档可引用本报告记录独立复核闭合，但旧失败必须继续保留。

P00—P12 ACCEPTED 不变；P13 等待用户正式验收，P14—P23 未开始。P13 仍是 Engine TEST/本地纯表达机制，不代表生产 Provider、自由改写语义等价、外部消息送达或生产 exactly-once 已验收。等待用户决定，不自动归档验收、提交、push 或推进下一阶段。
