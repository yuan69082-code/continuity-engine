# W02-B 开工简报

2026-09-24；仅用户已授权的回答形成前自动关联回忆。状态 IN_PROGRESS，非验收。

| 项目 | 本批边界 |
|---|---|
| SOURCE OF TRUTH | 用户本轮授权；现行索引中的总施工 v1.5、最终新增 v1.5、长期能力 v6.9；W01 测试映射、W02-A 说明 §7、D-076 |
| ORIGINAL REQUIREMENTS | N02、W02 回答前回忆及 T03—T06；联验 T01/T02/T18。原始消息入站、当前对象/表达/时间理解、有理由的有限关联、来源与成本、只读查看 |
| KEEP RULES | 原 Memory/Timeline/Router/Composer、SubjectState/Action/Evolution、唯一请求账本；当前权限、生命周期和现实效果边界不变 |
| DEPENDENCIES | W02-A 已 ACCEPTED；当前输入在原日志有可核验准备材料。Memory/Timeline 和原候选来源提供材料，不把输入解释变成事实 |
| NOT READY | W02-C 完整外部吸收、W03 长期认识细化、W05 新运行联动、P19 页面、生产服务；不得以这些后置能力替代本批要求 |
| TESTS REQUIRED | 修前真实入口；T03—T06 正反例及 T01/T02/T18；W02-A、上下文/学习/恢复/权限等实际影响兼容；固定源码一次全量，原1646身份保留 |
| PLANNING CONFLICT | 开工时尚无已证实冲突；T04 必须核实既有候选路径，不改学习政策或另造人物库；发现实际冲突停对应项 |

## 实测基线

main，HEAD/local origin/main/实际远端 main 均为 `de710773ef6c12c12c1422711f1aab5113abd3e3`。远端为本轮实际只读查询，不引用规划窗口失败的查询。暂存区及已跟踪工作区空。282 项源码/测试/资源指纹 `sha256:1021239d8214b38493aa3ff8ea5011c7b27856966bfe3395545607a8c066c523`，保护及原32+规划25排除材料逐文件匹配。见 [baseline](baseline.json)。已核验全量1645 PASS/1 WinError1314 SKIP仅为历史引用，不是本轮实跑。

## 具体路径与公共影响

候选运行修改范围：`services/continuity_core_service.py`、`services/continuity_core_runtime.py`、`services/continuity_interaction_service.py`、`services/context_router_service.py`、`services/input_context_source.py`、`domain/continuity_core.py`、`domain/integration_results.py`、`storage/json_integration_repository.py`。必要新增：`domain/associative_recall.py`、`services/associative_recall_service.py`、`testing/w02_recall_fixture.py`。正式测试限新增 `tests/test_w02_recall*.py`。

这些是候选清单，不要求全部修改。通过原 C1 工厂装配、Router可选查询和原日志的可选绑定接入；旧开关/旧记录必须兼容。共享上下文、入站和重放为直接公共影响，权限/计费/运行寿命/外部契约不改。资料检索失败需在原进度中可见，不重新派发已成功业务。长期事实仍由原权威存储提供；必要的历史输入仍是有来源的候选。

禁止：63保护项、六份Schema、冻结interfaces、pyproject/版本、正式数据、规划原件及25规划材料、32排除项、既有证据、Assistant/Vio；不改公共权限或Learning置信度政策。不接真实服务，不启动后续批次，不写Git。

文档允许：本目录；README、01当前状态、03施工日志、04决策、06未完成、CHANGELOG、工程总档案。只追加现行记录，不倒写历史。

## Planning Item → Code Change → Test → Acceptance Result

| 项 | 计划落点 | 实际验证入口 | 当前结果 |
|---|---|---|---|
| N02/T03 回答前自动评估 | C1准备/Router/Composer | 原消息12点与15点，检查Provider收到材料的顺序 | NOT_STARTED |
| T04 独立根与候选 | 原来源、候选及学习入口复用 | 多次独立/重放/摘要/积极与反例 | NOT_STARTED |
| T05 对象/否定/时间 | 有界结构解释与原来源 | 原始入站、引用/意愿/旧事/同义错字 | NOT_STARTED |
| T06 有限关联 | 可配置预算、停止原因和原Composer | 环路/无新关联/不可读/过期/超时/裁剪/成本 | NOT_STARTED |
| T01/T02/T18兼容恢复 | 原输入进度/权限/成功事实 | 部分失败、重开、重复请求、只读零业务副作用 | NOT_STARTED |

复杂输入不能可靠解释时保留不确定性；测试Fake只证明工程链。不能用受控几句话推导真实语言理解或生产服务已验收。若现有合法路径无法满足一项，提供具体证据并等待决定，不能默默删减。

## 证据规则

唯一标签保存命令、输出、退出码、耗时及前后源码；旧失败保留。集合重叠不相加。只读勘查曾误查不存在的 `testing/p09_fixture.py`（实际为 `p09_core_fixture.py`），属于辅助路径错误，未运行测试、未修改实现。历史F1/H1/F2仍UNKNOWN。

结束最多 IMPLEMENTED_NOT_ACCEPTED；W02整体仍IN_PROGRESS。下一步仅独立复核与用户决定。
