# W02-C 派生材料部分撤回定向补修矩阵

本矩阵只对应已授权的 N11/T23 撤销传播疑点；W02-C 仍为 `IMPLEMENTED_NOT_ACCEPTED`，W02 整体仍为 `IN_PROGRESS`。原 [W02-C 矩阵](../w02_c_evidence/matrix.md)其余项目及原始结果保持历史有效。

| Planning Item | Code Change / 原职责 | 正式测试与原始证据 | Acceptance Result |
| --- | --- | --- | --- |
| N11/T23：单一派生材料撤回，不抹掉同根原文和取得事实 | `ExternalAbsorptionService._decide` 原有材料 hash 核对保留；`memory_current` 从原 P04 Memory 所存的确切材料重算 hash，逐根核对当前 `material_hashes`。根绑定 hash 仍允许不相关材料增补，不另建来源权威。 | `test_withdrawing_only_derived_material_invalidates_every_dependent_use`；[修前真实失败](derived-withdrawal-before-02.stderr.log)，[修后定点](derived-withdrawal-process-01.json)。 | IMPLEMENTED_NOT_ACCEPTED |
| N11/T23：依赖传播到旧 Context、Summary、P15 学习支持及下一轮回应 | 复用原 Router/Composer 的 Memory/Summary 来源与 resolver，以及 P15 当前支持重验；未改这些公共模块本身。 | 同一正式测试核对直接候选、旧 Context、Memory/Summary、Learning、跨进程重开、下一轮 Context、主体状态和历史事实。 | IMPLEMENTED_NOT_ACCEPTED |
| N11/T04：不相关同根呈现和独立根规则 | 新材料加入不得使仍获认可的旧 Memory 失效；被撤回的具体内容不能仅凭另一同源副本恢复。 | `test_adding_unrelated_same_root_material_preserves_current_memory`；原 `test_same_root_original_and_derived_wrapper_count_once`。 | IMPLEMENTED_NOT_ACCEPTED |
| T18：只读重开与原事实保留 | `w02_c_child.py` 增加隔离 TEST 子进程只读失效核对；原 E5-A/ThinkSession/回执不变。 | 新测试的子进程结果及原 `tests.test_w02_external_recovery`；查询前后主体、Fake 事实及根字节不变。 | IMPLEMENTED_NOT_ACCEPTED |
| 权限、隔离及旧路径兼容 | 原 `current_root` 继续核对主体、环境、范围、权限、状态与时间；W02-C 未启用时 P16 路径不变。 | 原 W02-C 权限/主体/环境测试与 W02-A/B、P04/P05/P06/P16/P17 兼容组；最终结果见[测试索引](test-index.md)。 | IMPLEMENTED_NOT_ACCEPTED |

本批当前已知缺口修补仍待独立复核；测试通过不能代替用户验收。跨 Store/备份的生产删除传播仍属 P20，真实资料服务仍属 P22。
