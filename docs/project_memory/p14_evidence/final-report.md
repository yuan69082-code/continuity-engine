# P14 本轮施工与独立复核交付

P14 / Engine side / P14-01—P14-12 = IMPLEMENTED_NOT_ACCEPTED；P00—P13 ACCEPTED；P15—P23 NOT_STARTED；P14 Vio dependency=NONE。D-064 为开工与边界决定；D-065 未创建、未使用。当前 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示本地已发现缺口有闭合证据，不等于独立复核或用户验收。

## 实际形成的能力

同一主体的心智保存在原 SubjectState，跨会话和实际进程重启延续。在获准计算机会中，没有 Observation 也会形成内生欲望、反复关注和时间体验。躯体/疲劳与未决解释会改变真实召回、Thinking、信息需求、Direct/Planner 与表达选择；明确的拒绝、沉默和对抗仍被保留，不被通用驱力覆盖。

新经历只消费实际 Composer 材料；单根 Memory 与 Timeline 按根去重，保留权限、版本、生命周期、消费权重和独立预算。道歉不重置旧 Episode；认知理解经原 Action/Evolution 才成为持久状态。长期倾向、心理冲突、欲望/意志/决定/行动保持分层，没有第二主体或账本。

可信 Owner 的详细实验投影读取真实心智和 Evolution 历史；摘要、私有模式和导出授权分开。读取零写入、不唤醒、不扣费，隐私切换的两个分支产生相同内部演化。TEST 权限文件已精确进入原 Snapshot 清单。

## 验证结果

| 本轮实跑 | 执行 | PASS | SKIP | FAIL/ERROR | runner秒 |
|---|---:|---:|---:|---:|---:|
| P14最终专项 | 54 | 54 | 0 | 0/0 | 44.509 |
| 较大兼容组合（末次P14选择补修前） | 741 | 740 | 1 | 0/0 | 644.020 |
| 补修后Thinking/Action/P13兼容 | 85 | 85 | 0 | 0/0 | 56.503 |
| 最终完整Engine回归 | 1124 | 1123 | 1 | 0/0 | 683.111 |

runner秒包含测试发现与执行；各 stderr 另记 unittest 执行时间。最终全量 unittest 为682.489秒，runner为683.111秒。既有 SKIP 是 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`：Windows未授予创建符号链接权限1314，不能计PASS。没有新增跳过。

P13原1070身份和原测试文件逐字节保留。引用基线为1069 PASS/1 SKIP、621.988秒，是已验收P13的历史结果，不是本轮重跑。最终全量是施工方本地实跑的1124项，其中新增P14为54项。

741项较大兼容运行后，仅 P14 dynamic_mind_service.py 和新 P14 recovery 测试发生明确选择补修。它不是最终源码逐字节相同的证据；补修后重新运行54项专项和85项相关兼容，最终全量覆盖原741个身份。全部最终运行的220个源码/测试/资源文件在各自执行前后相同。

本期 Golden 是6个逻辑小时、6次计算机会、3个实际进程（2个重启点）；每段2次新Evolution，重复最后机会不重写。它不是多轮全量代替长期测试。实际主体ID、revision、主观秒、心智字节、轨迹点、Provider调用和TEST费用均在 [最终专项stdout](p14-final-2.stdout.log) 与 [全量stdout](full-final.stdout.log)；客观事件时间不变、零现实调用。

## 源码身份与保护

已提交基线/当前HEAD：`b02d8c9cc894b3060089d7cc24e06afaeab89ebf`；P14仍为未提交工作区成果，没有新的P14 commit SHA。

最终源码集合：220个文件；按“路径→SHA-256”排序JSON（紧凑分隔符、UTF-8）计算的清单指纹为 `sha256:88f46e1f3d6d5d5799e7ea374153b3f70a4d05a6ecb85ce4401b12271a567722`。逐文件清单与测试身份见 [终局全量JSON](full-final.json)，最终静态/保护/Git核对见 [终局审计](final.audit.json)。

六份Schema和25项冻结边界、pyproject/版本0.1.0、三份规划原件、正式七文件以及31个P10辅助脚本均按开工清单逐项核对。本次终局实测正式树指纹与开工一致：`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。没有修改Assistant/Vio，没有Git写操作，没有新增workflow或远端CI PASS声明。

## 范围和限制

- 心智先为原C1/ThinkSession中的候选，只有原Action Gate/Evolution提交后才是当前状态；历史事实核验不恢复旧表达或新执行授权。
- 原生未完成Thinking不被猜成未执行而重试；模型级持久恢复继续使用正常C1/E5-A。本期不声称任意生产Adapter的exactly-once或跨进程并发执行保证。
- 结构化experience是本期可复现语义入口；任意自然语言理解继续依赖Thinking能力，不冒称已接真实Provider。当前保留长期倾向，不提前建设P15完整人格/关系形成生命周期。
- Desire显式生命周期变换是内部候选机制；act标签不是Adapter执行证明。记录容量和局部轨迹有明确界限，容量耗尽失败关闭，不静默删除历史。
- Owner身份Port与权限的组合在本地TEST/Fake验证；完整生产认证/加密/UI、常驻Runtime、真实外部能力仍NOT_READY。实验结束、额外观察日志保留、封存/删除及云端发送策略仍待用户决定。

## 复核入口

从Engine仓库运行：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python docs/project_memory/p14_evidence/run.py review-p14-01 test_p14_
python -m continuity_engine.testing.p14_mind_fixture
python docs/project_memory/p14_evidence/run.py review-full-01
```

证据label须使用新的值，runner拒绝覆盖旧结果。所有运行使用隔离Fixture；不要给Golden传正式数据根。原始实际命令已在各JSON的command内，不能将上面的未来复核命令当作已运行。

[十二项矩阵](../68_P14_规划施工测试验收矩阵.md) · [详细机制与恢复语义](../69_P14_心智连续演化恢复与实验观察语义.md) · [完整失败历史](failure-history.md) · [精确待提交与排除清单](final.pending-files.md)。

本轮施工已实现，等待规划独立复核及用户确认；不自行验收，不提交推送，不进入P15。

## 本次收尾只读核查（2026-09-08）

本次未运行专项或全量，也未修改运行代码和测试。重新逐文件核对当前220个源码/测试/资源文件，与最终54项专项、85项相关兼容和1124项全量各自的执行前后清单完全一致；全部1070个原测试身份保留。上表是已有施工实跑记录的本次身份核验引用，不是规划监工独立复核。

终局审计：210个Python文件AST通过；825个本地链接检查无失效；敏感模式检查无命中；git diff --check通过。63项保护文件、三份规划、正式七文件和31个P10排除脚本无变化，原测试文件无变化。LF/CRLF提示为Git行尾提示，不是测试失败。

精确P14待提交清单共157个文件：16个源码、3个新增测试、20个说明/索引档案及118个证据/审计文件。另31个P10本地辅助脚本原样排除。main和本地origin/main仍为b02d8c9cc894b3060089d7cc24e06afaeab89ebf，ahead/behind为0/0，暂存区为空；没有Git写操作。本次不重新联网核查或声明CI结果。

未发现新的源码、测试或保护边界问题。当前剩余事项是规划独立复核、用户正式验收，以及上述尚未开放的生产能力和待定策略；不登记D-065，不进入P15。
