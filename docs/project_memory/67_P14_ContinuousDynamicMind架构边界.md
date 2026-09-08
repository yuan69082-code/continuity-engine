<!-- P14_ACCEPTED_START -->
> 2026-09-08 用户正式验收P14（D-065），覆盖初版及R1/R2。P00—P14 ACCEPTED；P14 / Engine side / P14-01—P14-12 ACCEPTED；P14 Vio dependency=NONE；P15—P23 NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示本轮已知阻断闭合。
>
> 独立实跑7/7、67/67、4/4 PASS（有包含关系）；全量仅核验引用施工1137项：1136 PASS、1既有Windows symlink1314 SKIP，0 FAIL/ERROR，runner898.290秒。本次未重跑测试。P14尚未提交/push，当前HEAD仍为P13基线b02d8c9cc894b3060089d7cc24e06afaeab89ebf。
>
> [用户授权、验收依据及准确清单](P14_用户正式验收_20260908.md)。下方此前等待复核/验收、PRESENT、未使用D-065及各次失败为历史快照；全部保留，P09 segment10 UNKNOWN不变。未进入P15。
<!-- P14_ACCEPTED_END -->

<!-- P14_REPAIR_CURRENT_START -->
> 2026-09-08 当前：P14 R1/R2补修已实现，等待独立复核。P14/Engine side/十二项保持IMPLEMENTED_NOT_ACCEPTED；P00—P13 ACCEPTED；P15—P23 NOT_STARTED；P14 Vio dependency=NONE。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，等待返修后独立复核；D-065未使用。原54/1124项及旧NONE为返修前历史结果，不能覆盖独立三项失败。见[本轮有效范围、进度和证据](P14_独立复核返修_R1-R2.md)。
<!-- P14_REPAIR_CURRENT_END -->

# P14 Stage Brief：Continuous Dynamic Mind 与情绪动力

日期：2026-09-08。决定 D-064；用户已在规划任务明确确认开工。本文件先于任何运行代码修改形成。

## STAGE

P14 / Engine side / P14-01—12 = IN_PROGRESS；P00—P13 ACCEPTED；P15—P23 NOT_STARTED；Vio dependency=NONE。最高交付 IMPLEMENTED_NOT_ACCEPTED；D-065 留待未来正式用户验收，本轮不创建、不使用。没有 Git 写操作授权。

## SOURCE OF TRUTH

用户本次授权与规划交接 → 2026-08-26 v1.1 的 P14 和最终 Override/Keep → v6.7 第十二/十二-A、附录 C/D/E → 真实代码与 D-063。三份原件及经原件 hash 验证的文本缓存见 [开工清单](p14_evidence/before.json) 和 [规划文本](p12_evidence/planning-source.json)。交接原件位置记在清单 kickoffSource；只读，不修改原件。

实测 main、HEAD/本地 origin/main 均 b02d8c9cc894b3060089d7cc24e06afaeab89ebf，ahead/behind=0/0；跟踪文件和暂存区干净，31个排除脚本不变。P13 的“尚未提交/P12 HEAD”是当时验收快照；本段追加提交后的事实，不覆盖旧记录。没有 Engine workflow，不宣称 CI PASS。

## ORIGINAL REQUIREMENTS

v1.1 P14（规划缓存 blocks 189—196）：连续心理状态、合法 Psychological Conflict、内生欲望/意志、Persistent/Recurring Thought、Subjective Time、Attention、Somatic、Affective Episode、Drive、Arousal、Action Tendency、Regulation/failure 必须真实进入正常 C1。不同 ThinkSession 和重启共享一个主体；无 Observation 可形成欲望；客观 Event 时间不变。详细实验观察已由本次用户决定开放给可信 Owner，不等待 Vio 展示。

## V6.7 DETAILS

第十二/十二-A（165—194）及 C2、D1—D9：先内部状态，再认知选择，最后表达。Episode 保留对象、根来源、解释、未决点、时间、轨迹与 resolution；道歉本身不清零。长期情感倾向与短期情绪分离，HATE 的长期形成不能用单次事件或累计分数替代多源经历和认知依据。LOVE/HATE、靠近/逃离并存，不删除较弱项。

Drive 保留 intimacy/exploration/sexual/solitude/expression/protection/rest 以及源规划列出的其他维度；Arousal、紧绷/放松/躁动/沉重/兴奋/发热的内部 Somatic 表征进入注意、耐心、等待体验与审慎/冲动倾向。Desire 覆盖 arise/intensify/weaken/persist/suppress/fail_to_suppress/disappear/recur/conflict/transform/act/abandon。Will 为关联欲望、价值/承诺、反向理由、替代方案和推进/暂缓/放弃依据的评估结构，不是 priority 或分数开关。

Persistent Thought 保存引擎明确形成的内部内容和关联理由，不保存 Provider 隐藏推理。机制级反事实对照需证明内部状态变动改变真实注意、合法召回、解释、Thinking、Decision/Action Tendency/Expression，不能靠 Fake 预填台词。可信时间驱动有界、确定性计算，不使用 sleep 或后台线程。

## AMENDMENT OVERRIDES

采用 v1.1 347—416、v6.7 C/D/最终 E 的有效覆盖。简单行动仍为 Direct，复杂行动才 Planner；唯一 E5-A 请求账本/回执恢复不变。P01—P21 Engine 独立，生产适配器后置。现实门只能控制已形成行动的现实效果，不反向压抑或删除心智。

## KEEP RULES

当前心智是 SubjectState 的内部扩展，由原 Event/Action Gate/Evolution/revision 保存，不另建 MindStore 或操作账本。可序列化的本轮心智输入/候选和关联证据置于原 C1/ThinkSession checkpoint，均不构成已提交事实。既有记录缺少扩展时保持旧序列化/恢复；新记录缺绑定失败关闭。旧已提交事实核实与当前新执行授权分离。

Context/Memory 继续经过 P05/P06 的权限、独立预算、exact reference、版本/hash/根来源及 P12 生命周期。心智不是事实证据，不能把内部解释交给 P07 强行消解或升级为事实。只读观察使用可信宿主身份解析与既有 PermissionService，详细度/导出许可与额外日志保留分离；不创建平行认证库。

## DEPENDENCIES

P03/P04 Event/Memory、P05/P06 Router/Composer、P07 认识性矛盾、P08 唯一执行恢复、P09 正常 C1、P11 计算机会、P12 当前生命周期、P13 已形成决定的表达；复用 P01 隔离 Fixture 与可信冻结时钟。当前 Source/Test 212 个文件 hash 和 1070 个测试身份均核对一致，原全量1069 PASS/1 SKIP仅引用。

## NOT READY

生产 Provider/Adapter/设备/联系/支付、Vio/Assistant 接入、P15 全套人格关系与自我叙事、P18 常驻、P19 全套 UI、P20/P21 生产恢复/认证/加密均不在本轮。生产部署身份保证不以本地 Fake 冒充。实验结束、封存/删除、云端发送及额外长期观察日志策略仍待用户决定。本轮不改公开/fork/许可设置，不以意识/身体哲学问题缩减机制。

## FILES ALLOWED

以下为候选允许范围，实际精确增量以终局清单为准；未需要的文件不修改。

- `src/continuity_engine/domain/dynamic_mind.py`
- `src/continuity_engine/domain/models.py`
- `src/continuity_engine/domain/evolution.py`
- `src/continuity_engine/domain/continuity_core.py`
- `src/continuity_engine/domain/thinking.py`
- `src/continuity_engine/services/dynamic_mind_service.py`
- `src/continuity_engine/services/mind_projection_service.py`
- `src/continuity_engine/services/mind_ports.py`
- `src/continuity_engine/services/context_router_service.py`
- `src/continuity_engine/services/context_material_resolvers.py`
- `src/continuity_engine/services/continuity_core_service.py`
- `src/continuity_engine/services/continuity_core_runtime.py`
- `src/continuity_engine/services/thinking_service.py`
- `src/continuity_engine/services/wake_perception_thinking_action_service.py`
- `src/continuity_engine/services/continuity_interaction_service.py`
- `src/continuity_engine/services/expression_policy_service.py`
- `src/continuity_engine/testing/p14_mind_fixture.py`
- `src/continuity_engine/testing/c1_snapshot.py`
- `src/continuity_engine/testing/sandbox.py`
- `tests/test_p14_dynamic_mind.py`
- `tests/test_p14_mind_recovery.py`
- `tests/test_p14_mind_visibility.py`

档案：README.md；docs/project_memory 下00/01/02/03/04/05（完成与架构）/06/07/10/11/12/13、CHANGELOG.md、工程总档案.md；本阶段67—70；p14_evidence/ 内必要基线、测试输出、审计与清单（尽量复用一个 runner）。旧测试只读保留身份和断言；P14 新测试可修正真实开发缺陷，首次输出不覆盖。

## FILES FORBIDDEN

六份 Schema、完整25项冻结边界、interfaces/、pyproject.toml、版本0.1.0、正式七文件和树指纹、三份规划原件、Assistant、31个P10排除脚本与所有历史证据；.git及任何 Git 写操作。本轮不接真实外部运行能力。

## TESTS REQUIRED

先新增行为定点/反例及正向机制对照；P14 专项→真正受影响兼容组合→稳定后一次全量。保留1070身份/断言、所有新旧FAIL/ERROR/SKIP和工具错误；Windows symlink 1314 SKIP 不算PASS。报告命令、身份、源码清单、stdout/stderr、退出码和耗时。只读终局保护核对、AST、链接、敏感信息、差异和精确清单；只改档案不重跑全量。

## PLANNING CONFLICT

当前未发现规划冲突，PLANNING_CONFLICT=NONE。尚未实现或验证的条目均为 IN_PROGRESS，不预填通过。若出现需要扩张冻结契约/其他阶段的真实问题，停受影响项并保存证据。


### FILES ALLOWED 开工内补充：无 Observation 的既有入口

2026-09-08，接线阅读确认正常无外部输入路径已经是 WakePerceptionThinkingActionService；在修改该文件前将其加入允许范围，仅增加可选 C1 心智接线、稳定Wake/Think/Evolution身份及原记录恢复。默认分支原样保持；不创建新的 Runtime、请求账本或唤醒系统。当前心智落在 SubjectState.intentions.dynamic_mind，属于已有允许 Thinking proposal 的 intentions 分区，不扩张 Thinking 的长期人格/关系写入范围。

2026-09-08 恢复施工补充：P14 Owner 实验授权复用了 JsonPermissionRepository，但新 Fixture 产生的授权记录尚未进入 P01/C1 Snapshot 物理清单，新增分支对照真实报 SNAPSHOT_INCOMPLETE。先将 testing/c1_snapshot.py、testing/sandbox.py 加入允许范围，仅补 TEST C1 对既有权限文件的精确清单和逻辑内容映射；不放宽未映射文件拒绝、不修改生产恢复或权限语义。原无权限文件的 Snapshot 保持原格式。

## 本轮收尾状态

2026-09-08：上方STAGE的IN_PROGRESS为开工快照。当前P14/Engine side/十二项IMPLEMENTED_NOT_ACCEPTED，源码和54项专项、1124项全量已形成，等待独立复核及用户确认。D-065未使用。结果、限制及逐文件身份见 [70](70_P14_测试索引与验收入口.md)。

## R1/R2 本轮允许文件补充

用户合并定点返修授权：`src/continuity_engine/services/dynamic_mind_service.py`、必要内部`src/continuity_engine/domain/dynamic_mind.py`、新增正式回归`tests/test_p14_review_repair.py`，以及P14相关档案和p14_repair_evidence。原1124身份与旧断言保留；不是全阶段重构。
