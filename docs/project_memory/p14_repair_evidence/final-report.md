# P14 R1/R2 返修终局交付

2026-09-08：本轮R1/R2补修已实现，等待规划独立复核。P14/Engine side/P14-01—12保持IMPLEMENTED_NOT_ACCEPTED；P00—P13 ACCEPTED；P15—P23 NOT_STARTED；P14 Vio dependency=NONE。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，不代替监工关闭阻断。D-064追加返修事实，D-065未创建、未使用；没有Git写操作。

## 修复范围与责任边界

- R1：MindCognition.finalize原先聚合当前可读的所有同对象/期待支持，未区分哪次伤害。现以内部Episode.concern_basis绑定本次最新经历根和客观occurred_at，只接受此后、当前实际Composer包含的独立支持作为本次解决依据。旧支持仍保留；至少两根及消费置信度要求不变。同根RAW/Memory不双计，保守消费强度及根排序消除呈现顺序依赖。道歉、裁剪或缺失不冒充解决。
- R2：MindDynamics.advance原先按drive使用next，漏掉transform后共存的另一身份。现对所有匹配稳定身份演化，保留每项强度/时间/轨迹/Will/Thought，生成新身份时排序既有ID。不删、不强制合并旧欲望，不改十二种生命周期政策。
- 实现文件仅 [内部Mind类型](../../../src/continuity_engine/domain/dynamic_mind.py) 和 [认知/演化服务](../../../src/continuity_engine/services/dynamic_mind_service.py)；新增 [正式回归](../../../tests/test_p14_review_repair.py)。其余既有P14和P00—P13源码、原测试文件均保留。
- 沿用唯一SubjectState、Event、Thinking、Action Gate和Evolution；没有第二Authority/账本。未修改Scheduler、外部接口、Assistant/Vio或生产能力。Owner只读对照继续通过，未改其实现。

## 首次失败与修复过程

本轮直接读取原confirmed_probes：7项4 PASS/3 FAIL，20.352秒；正式化后同样4 PASS/3 FAIL，21.750秒。原三失败为旧支持解决新伤害、上一轮修复解决再次伤害、transform后另一欲望冻结。

扩展13项首次11 PASS/2 FAIL，69.579秒：一个揭示同根RAW/Memory消费顺序影响候选，已在R1根去重范围修复；另一个因新测试reopen后未恢复明确3000输入预算，实际Composer只消费到一根支持，故正确停在processing。恢复原定测试预算后保留resolved断言通过，未在Engine提高预算或降低门槛。[全部失败与诊断](failure-history.md)保留，不用新PASS覆盖。

监工原件/任务书/原始日志路径及hash在[开工核对](before.json)；未修改独立目录。未确认的两项探索断言不在返修范围，未扩修。P09 segment10 stderr缺失、根因UNKNOWN及全部旧FAIL/ERROR/SKIP仍保留。

## 本轮真实结果

| 施工方实跑 | 执行 | PASS | SKIP | FAIL/ERROR | runner秒 | unittest秒 |
|---|---:|---:|---:|---:|---:|---:|
| [正式定点](targeted-final.json) | 13 | 13 | 0 | 0/0 | 68.583 | 67.802 |
| [只读原确认矩阵](confirmed-final.json) | 7 | 7 | 0 | 0/0 | 22.075 | 21.658 |
| [完整P14](p14-final.json) | 67 | 67 | 0 | 0/0 | 117.910 | 117.217 |
| [直接兼容](compatibility-final.json) | 343 | 343 | 0 | 0/0 | 543.803 | 543.092 |
| [稳定全量（一次）](full-final.json) | 1137 | 1136 | 1 | 0/0 | 898.290 | 897.571 |

7项确认包含在13项正式定点中，13项包含在67项P14及全量中，不相加冒充互斥覆盖。原独立54 PASS和7项4 PASS/3 FAIL是返修前监工记录；上述原脚本复跑仍是施工方运行，不冒称新一轮独立复核。

唯一SKIP：test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes，Windows symlink创建权限1314；不是PASS，没有新增SKIP。原1124个测试身份全部保留，新增13个，当前1137个。原1124项全量仅为历史基线，本轮没有机械重复三轮。

正向覆盖：合法后续支持仍能解决；再次伤害重开后序列化/重启/重复消费不误解决，新支持仍能解决；批量实际事件顺序、同时间不足证明、RAW/Memory同根与低置信度；旧记录读取及非法basis拒绝；transform共存、连续机会、列表逆序、恢复和Will/Thought绑定；无transform及Owner读取/撤权对照。当前权限、预算、旧E5-A/C1恢复、P12生命周期、P13表达等由67项P14、343项兼容和完整全量共同保留。

## 身份、保护和工作区

全部最终运行的221个源码/测试/资源文件执行前后与当前逐字节相同。清单指纹：`sha256:0775243db59252ce545eefcf8cb4977d4865670b71f873121b536b9b26e26472`。三处源码/测试增量均属于R1/R2，原测试未变。详细逐项hash见[终局审计](final.audit.json)。

六份Schema/25冻结边界、版本0.1.0及pyproject、正式七文件、三份规划、31个P10脚本均按开工hash核对不变。正式树指纹：sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2。旧p14_evidence证据不改写；新增结果单独放在p14_repair_evidence。

HEAD/本地origin/main为b02d8c9cc894b3060089d7cc24e06afaeab89ebf，main、ahead/behind 0/0、暂存区空；没有本轮新commit SHA。没有远端核查或CI PASS声明，Engine仍无workflow。

[全部精确待提交与排除清单](final.pending-files.md)包含旧157项及本轮必要增量；审计分别列出newSinceRepairStart、modifiedSinceRepairStart，不把P10脚本计入P14。不清理旧缓存、Sandbox或未跟踪材料。静态、链接、敏感模式、diff及最终Git状态详见审计，不能把审计文件自含hash作为要求。

## 剩余限制与复核命令

- 旧Episode没有客观basis时保持兼容，并保守用最后appraisal时间；不猜测缺失事件顺序。同时间支持不足以证明后续解决。
- 本期仍为结构化TEST/Fake经验入口；没有生产认证、真实Provider/Adapter、永久后台或P15能力。观察数据保留/删除等原待定策略不在本轮决定。
- 未发现额外独立缺陷，但R1/R2须由监工再次复核，不能将本地通过等同验收。

从Engine仓库运行（使用全新label，runner拒绝覆盖旧证据）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p14_repair_evidence/run.py review-confirmed-02 --confirmed
python docs/project_memory/p14_repair_evidence/run.py review-p14-02 test_p14_
python docs/project_memory/p14_repair_evidence/run.py review-full-02
```

--confirmed只读加载本机规划目录原脚本（路径见runner/before.json）；可移植的等价确认及扩展已在tests/test_p14_review_repair.py。正式回归不依赖规划目录。全量后只做档案和只读核查，源码hash不变，不再次重跑。

本轮补修已实现，交回独立复核；不登记验收、不提交/push、不进入P15。
