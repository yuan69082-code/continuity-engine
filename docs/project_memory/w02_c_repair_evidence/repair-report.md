# W02-C/N11 派生材料部分撤回：定向补修与独立复核入口

**状态：IMPLEMENTED_NOT_ACCEPTED；W02 整体 IN_PROGRESS。** D-079 只记录 W02-C 开工，本次没有验收决定。现行 PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，修补仍待独立复核。W02-A/B 已验收，P00—P18 的历史验收、F1/H1/F2 原因 UNKNOWN 与旧失败不改写；不启动 W02 总贯通、W03 或 P19，也不执行 Git 写操作。

## 真实缺口及最小修补

原 `ExternalRootProof.binding_hash` 排除 `material_hashes`，目的是允许同一根增加原文、翻译或摘要而不使旧绑定整体失效；但原 `ExternalAbsorptionService.memory_current` 只核对根绑定指纹。两个独立根共同认可原文和另一份派生材料，派生材料经原 P04 Consolidation 成为 Memory/Summary；当两个根保持 ACTIVE、版本和原文不变，只撤回派生材料 hash 时，直接候选与旧 Context 已变为不可用，而旧 Memory 仍被视为 current。首次有效修前测试 [`derived-withdrawal-before-02`](derived-withdrawal-before-02.stderr.log) 在该断言处 1 FAIL；之前两个辅助标签因测试中原文/派生 source_id 相同，触发了既有证据不足/冲突规则，均保留但不计 Engine 缺陷。

修补仅改 `src/continuity_engine/services/external_absorption_service.py`：由原 P04 Memory 的确切外部材料内容重算材料 hash，逐个既有根验证当前认可清单，同时保留原根身份/范围/权限/时间/版本检查。根绑定本身及历史取得事实不改；不会因新增无关同根材料而误杀仍获认可的旧记忆。`ExternalAwareMemorySource`、`ExternalAwareSummarySource`、Composer resolver 与 P15 学习支持入口原已调用 `memory_current`，因此依赖的 Summary、当前学习支持及后续回应前材料通过原链失效，没有第二事实源或请求账本。旧 Context 仍按原 current 校验失效，不直接写 SubjectState。

正式测试 `tests/test_w02_external_absorption.py` 新增撤回反例和同根增补正向对照，扩展 `src/continuity_engine/testing/w02_c_child.py` 的只读 TEST 子进程核查。新测试在重开前后验证直接候选、旧 Context、P04 Memory/Summary、P15 Learning、下一轮 Context、原取得事实、主体状态和来源记录。TEST 假结果的 `root_sink` 在撤回后关闭，使当前根 Port 独立于一次新的旧结果；这模拟真实来源认可与取得回执分离，并非通过结果自行重新授予已撤回材料权威。旧 P16/E5-A 回执、ThinkSession、权限及状态 Authority 保持不变。

## 验证身份与结果

开工 `main`，HEAD/本地 `origin/main` 为 `d23441619f82c1b186736f5d65e2f9de34d95522`，原 131 项 W02-C 成果及 57 项排除材料的文件身份与[原清单](../w02_c_evidence/final.files.json)一致，暂存区为空。原补修前源码/测试指纹 `sha256:41c56bd71950de9aca28b13043797fb794dfd04844dba17dd670341732419056`；最终固定源码/测试/资源指纹 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea`。本轮所有终局组在此指纹下运行，前后相同；集合相互重叠，不累计测试项。

| 标签 | 实际结果 | 用途 |
| --- | --- | --- |
| [`formal-final-01`](formal-final-01.json) | 25/25 PASS，88.514 秒 | W02-C 完整专项、正反例、恢复与隔离 |
| [`w02-ab-final-01`](w02-ab-final-01.json) | 123/123 PASS，130.130 秒 | W02-A/B 既有入站和回忆兼容 |
| [`public-final-01`](public-final-01.json) | 260/260 PASS，213.540 秒 | P04/P05/P06/P16/P17 直接公共兼容 |
| [`full-final-01`](full-final-01.json) | **1728 项：1727 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR**，1627.654 秒，退出 0 | 固定源码版本的一次完整回归；运行前后清单一致 |

每个标签的启动文件、原始 stdout/stderr、退出码与前后身份见[原始测试索引](test-index.md)。旧 W02-C `23/23`、W02-A/B `123/123`、公共 `260/260`、全量 `1725 PASS/1 SKIP` 属旧源码历史引用，不代替补修后全量。本次原 1726 项测试身份保留，新增 2 项；Windows 1314 SKIP 不计 PASS。没有远端 CI 通过证据。

## 保护、限制与下一步

本轮没有接真实资料服务、Provider、Vio、正式数据、生产凭据或生产长期吸收策略；未改冻结 Schema、外部契约、三份规划、版本、权限与生命周期。跨 Store/备份的生产删除传播仍属 P20，真实服务仍属 P22。正式数据七文件逐项与开工清单相同；另用原 `tree_inventory_hash` 实测为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。[终局审计](final.audit.json)同时单列该 tree inventory 值与逐文件 map 指纹，两种算法不混用。63 项保护文件和 57 项排除材料均与开工清单相同；全量前后身份一致。最终当前待交付 179 项（审计前 176 项加自身三项），原样排除 57 项，逐路径及 hash 见[精确清单](final.pending-files.md)和[JSON 清单](final.files.json)。全量结束后本轮创建的两个 Python 测试进程均已退出，未终止无关进程。实际远端 `main` 本轮查询因本机 Git 凭据环境错误 `SEC_E_NO_CREDENTIALS` 未取得结果；本地 `origin/main` 不冒充远端，未查询到远端 CI run。

独立复核可运行：`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=src;tests` 下执行 `E:/Adobe/python.exe -m unittest tests.test_w02_external_absorption tests.test_w02_external_recovery -q`；三组兼容的实际模块集合及命令见各标签 JSON。复核时先核对[逐项矩阵](matrix.md)、修前有效失败、终局身份及保护审计，再评价撤回传播。测试通过只代表所测 TEST/Fake 工程链，不代表正式用户验收或生产服务已就绪。
