# P15 Engine 本轮交付报告

P15 / Engine side / P15-01—12 IMPLEMENTED_NOT_ACCEPTED，等待独立复核；P00—P14 ACCEPTED；P16—P23 NOT_STARTED；Vio dependency=NONE。D-066仅开工决定，未登记用户验收。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE表示当前已知施工缺口闭合，不代替独立复核。

## 实际完成

正常C1消费当前证据并复用Learning形成候选，当前支持验证后经显式确认、Action Gate和Evolution固化Trait；下一轮真实Context可消费。对象关系和自我叙事是带来源/版本的主观状态，支持相反立场与重新理解；长期Will/冲突继续使用P14。新增生命周期管理复用原SubjectState/Event，CREATE原子持久化，暂停/归档阻止新计算，恢复核实已发生事实；主体意图、Owner命令、宿主切换/解绑分开。

没有新增状态、人格、请求或执行账本；旧SubjectState、Learning和ThinkSession字段兼容保留。仅两项强类型内部成长提案接入Thinking，Provider仍不能直接写入。详见[Stage Brief](../71_P15_人格关系学习与主体生命周期架构边界.md)、[十二项矩阵](../72_P15_规划施工测试验收矩阵.md)、[恢复语义](../73_P15_成长纠错与生命周期恢复语义.md)。

[30个源码/测试变更文件的方法导航](source-responsibility-map.json)可按文件定位新增/修改入口；这是AST导航，不能替代完整Git diff、来源hash或验收授权。27个运行/内部测试设施文件与3个新增P15测试文件均列明，原测试文件没有修改。

## 当前实跑与历史引用

- [p15-final-2](p15-final-2.json)：39 项：39 PASS、0 SKIP、0 FAIL、0 ERROR；runner 108.134 秒。
- [compatibility-final-2](compatibility-final-2.json)：311 项：311 PASS、0 SKIP、0 FAIL、0 ERROR；runner 229.353 秒。
- [full-final-2](full-final-2.json)：1176 项：1175 PASS、1 SKIP、0 FAIL、0 ERROR；runner 994.964 秒。

各集合存在包含关系，不相加为互斥覆盖。原1137测试身份完整保留、原测试文件未改；增加39项P15测试。开工1137项（1136 PASS/1 SKIP，898.290秒）仅核验引用P14已验收结果，不是本轮修改前新跑。所有本轮JSON附源码前后hash、完整测试ID、命令、时间、输出和失败信息；最终审计核对当前内容一致。没有远端CI执行或CI PASS声明。

## 首次失败及修复过程

早期 lifecycle-model/service、growth、visibility 和 recovery 的缺失模块/Fixture/入口 ERROR 是新增行为的修复前实际执行记录，不冒充已验收代码回归。已实现后保留原输出。其他有意义的失败及辅助错误如下：

- `lifecycle-entry-before` 的C1请求建立在暂停前、revision已旧；修正新测试的当前请求后，`lifecycle-entry-corrected-before`仍实际暴露C1先写journal及Scheduler实际投递两项缺口。门禁补齐后通过。
- `lifecycle-entry-after` 一项ERROR为新测试过深Temp路径触发Windows MAX_PATH；只缩短新增Fixture测试根，`lifecycle-entry-short-root`通过，未改生产路径规则。
- `growth-first` 暴露Engine内部强类型成长提案未被ThinkSession接受；只增加准确两字段内部序列化，Provider入口继续拒绝。`growth-typed-proposal`随后一项ERROR来自新测试要求旧表达在revision变化后直接重放，违反P13/P14现有契约；改为断言拒绝表达、原事实可查且零额外revision，没有放宽旧门禁。
- `recovery-first` 一项为新并发用例捕获异常类型错误，改为准确捕获StateEvolutionError；其他三项为缺少新Fixture入口。实现后8项通过，未吞并发写入缺陷。
- `paused-model-before` ERROR和`paused-model-count-before` FAIL记录实际Fake Provider事实数0→1。补齐原ModelCapability首次和NOT_EXECUTED后执行前生命周期/C1门禁，`paused-model-after`事实数0→0、LifecycleError；UNKNOWN/已提交事实查询未改成重执行。
- `p15-combination-first` 38 PASS/1 ERROR：多经历关系用例在默认Context预算下未包含材料；新增用例显式使用3000预算（沿用P14多来源场景方式），不改变Engine默认值或断言。`growth-reinterpret-budget`与当前P15全专项通过。
- 首次完整回归`full-final`发现原P09错主体Context的兼容ERROR；新增生命周期读取发生在原身份比对之前。保留首次全量、定点修复前后及准确结果，详见[局部检查顺序修复](continuity-current-repair.md)。只恢复原主体/环境先比对的顺序，再检查生命周期；不修改任何原测试。第二套后缀`-2`证据才对应最终源码，旧39/299项PASS及首次全量保留为中间版本。
- PowerShell中对rg传未展开的通配路径曾返回os error 123；改为`rg -g`后读取。属于辅助命令错误，不计Engine测试FAIL/PASS。早前任务接续误回P14是上下文接续问题，其只读报告单列保留，不是用户撤回P15授权。

各记录的原`.stdout.log`/`.stderr.log`与JSON同名保存，独立于Fixture临时根，后续PASS未覆盖首次失败。历史P09 segment 10 stderr缺失、根因UNKNOWN及P00—P14的FAIL/ERROR/SKIP仍保留。Windows symlink权限1314仍单列SKIP，不算PASS。

| 证据标签 | PASS | SKIP | FAIL记录 | ERROR记录 | runner秒 |
|---|---:|---:|---:|---:|---:|
| [lifecycle-model-before](lifecycle-model-before.json) | 0 | 0 | 0 | 4 | 0.711 |
| [lifecycle-model-after](lifecycle-model-after.json) | 4 | 0 | 0 | 0 | 0.837 |
| [lifecycle-service-before](lifecycle-service-before.json) | 4 | 0 | 0 | 6 | 0.771 |
| [lifecycle-service-first](lifecycle-service-first.json) | 10 | 0 | 0 | 0 | 0.970 |
| [lifecycle-entry-before](lifecycle-entry-before.json) | 11 | 0 | 2 | 0 | 1.503 |
| [lifecycle-entry-corrected-before](lifecycle-entry-corrected-before.json) | 11 | 0 | 2 | 0 | 1.451 |
| [lifecycle-entry-after](lifecycle-entry-after.json) | 12 | 0 | 0 | 1 | 1.526 |
| [lifecycle-entry-short-root](lifecycle-entry-short-root.json) | 13 | 0 | 0 | 0 | 2.035 |
| [growth-before](growth-before.json) | 0 | 0 | 0 | 6 | 0.797 |
| [growth-first](growth-first.json) | 5 | 0 | 0 | 1 | 27.457 |
| [growth-typed-proposal](growth-typed-proposal.json) | 5 | 0 | 0 | 1 | 30.705 |
| [growth-current-bindings](growth-current-bindings.json) | 6 | 0 | 0 | 0 | 51.356 |
| [growth-visibility-before](growth-visibility-before.json) | 0 | 0 | 0 | 1 | 4.270 |
| [growth-visibility-after](growth-visibility-after.json) | 1 | 0 | 0 | 0 | 1.895 |
| [recovery-first](recovery-first.json) | 4 | 0 | 0 | 4 | 2.424 |
| [recovery-implemented](recovery-implemented.json) | 8 | 0 | 0 | 0 | 30.426 |
| [paused-model-before](paused-model-before.json) | 0 | 0 | 0 | 1 | 1.001 |
| [paused-model-count-before](paused-model-count-before.json) | 0 | 0 | 1 | 0 | 1.042 |
| [paused-model-after](paused-model-after.json) | 1 | 0 | 0 | 0 | 0.979 |
| [p15-combination-first](p15-combination-first.json) | 38 | 0 | 0 | 1 | 106.842 |
| [growth-reinterpret-budget](growth-reinterpret-budget.json) | 1 | 0 | 0 | 0 | 9.124 |
| [p15-final](p15-final.json) | 39 | 0 | 0 | 0 | 113.193 |
| [compatibility-final](compatibility-final.json) | 299 | 0 | 0 | 0 | 240.156 |
| [full-final](full-final.json) | 1174 | 1 | 0 | 1 | 1012.898 |
| [context-identity-before](context-identity-before.json) | 0 | 0 | 0 | 1 | 1.349 |
| [context-identity-after](context-identity-after.json) | 1 | 0 | 0 | 0 | 1.432 |
| [p15-final-2](p15-final-2.json) | 39 | 0 | 0 | 0 | 108.134 |
| [compatibility-final-2](compatibility-final-2.json) | 311 | 0 | 0 | 0 | 229.353 |
| [full-final-2](full-final-2.json) | 1175 | 1 | 0 | 0 | 994.964 |

## 当前可运行Golden入口

[CLI实跑](golden-cli.json)，退出码0，12.048秒；[完整JSON输出](golden-cli.stdout.log)、[stderr](golden-cli.stderr.log)。逻辑时长7203秒、3次经历、2次正常计算机会、2次真实子进程重启，PID为[25228, 29208]；Trait和Will身份保留，重复revision差0，真实生产Adapter调用0。子进程输出保留版本、Provider调用和心智数量等观察，不以三轮全量替代长期连续性场景。该有界TEST场景不外推任意生产长期运行可靠性。

## 独立复核命令

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p15_evidence/run.py independent-p15 test_p15_
python docs/project_memory/p15_evidence/run.py independent-compat test_learning test_resources test_awakening test_thinking test_action test_evolution test_pre_p12 test_p02 test_p11 test_p14 test_p09_continuity_core test_p09_review_regressions test_p09_evolution_review test_p09_boundaries
python docs/project_memory/p15_evidence/run.py independent-full
python -m continuity_engine.testing.p15_subject_fixture
python docs/project_memory/p15_evidence/audit.py independent
```

在仓库根顺序执行。标签必须未使用，runner拒绝覆盖已有证据；不并发全量。Golden默认独立Temp根，命令/子进程/PID/逻辑时长/不变量输出为JSON。audit仅核查已有本轮证据并生成独立审计清单，不运行或伪报测试，也不做Git写操作。源码若改变，旧结果仅为历史，应按影响重新验证。

## 保护、Git与剩余边界

[最终只读审计](final.audit.json)保存全部源码/测试hash、63项保护清单、三份规划原件、正式七文件及树指纹、31个P10辅助脚本、原测试身份、AST/链接/敏感扫描、diff检查和完整Git状态。正式树预期`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，版本0.1.0；具体实测结果以审计为准，不用预期替代检查。

[精确待提交清单](final.pending-files.md)逐项列出本轮源码/测试/档案及必要证据；原31个P10本地工具和P14任务接续只读报告单独排除保留，不为清空工作区而加入本轮。HEAD/main及本地origin/main仍`f1185d20da06f52e7e85015bc6b963cf9769d08c`，暂存区空；本轮没有暂存、提交、push、分支或其他Git写操作，未修改Assistant。

正式归档/删除保留与恢复窗口、关系可见性策略尚待用户决定；仅独立TEST确认与策略有实现，逻辑DELETED不是物理擦除。生产认证、备份清除、生产迁移/Provider/Adapter和任意外部exactly-once未实现或宣称。并发/幂等证明限已测本机持久化与Fake能力；P01仅TEST/Research。停止P15，等待独立复核，不自行验收或进入P16。
