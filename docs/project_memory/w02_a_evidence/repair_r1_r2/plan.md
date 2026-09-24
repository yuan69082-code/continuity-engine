# W02-A R1/R2 定向补修（2026-09-24）

本轮用户授权只处理 R1 部分失败查询与 R2 有限中文解释。W02-A 保持 IMPLEMENTED_NOT_ACCEPTED；补修 IN_PROGRESS。不验收、不暂存/提交/push，不进入 W02-B/C、W03、P19。

## 基线及依据

现行归档：总施工规划 v1.5、最终新增规划 v1.5、长期能力规划 v6.9；[版本索引](../../现行规划版本索引.md)、[已批准开工说明](../../w01_planning_v15_20260923/w02-a-proposed-brief.md)。沿用 W02/N01 的输入理解、逐站回执、部分失败可读及 T01/T02/T05/T18/T24 的拒绝与只读要求。

开工核对：main，HEAD/local origin 为 ce6f4771140c4b6bdb0f5ae81d4c68bfc8653e88，ahead/behind 0/0，暂存空；282 源码/测试/资源、1621 测试身份。原95份可直接比对的交付文件 hash、63项保护、3份旧规划、正式7文件及32排除项一致；未触网查询远端。[baseline.json](baseline.json) 保存本轮实测与原审计。旧完整测试只作历史引用。

## 修改范围及公共影响

实现限六文件：services/input_processing_service.py、services/input_context_source.py、services/continuity_core_service.py、services/continuity_interaction_service.py、domain/integration_results.py、storage/json_integration_repository.py（均位于 src/continuity_engine）。测试在现有三个 test_w02_input_* 文件中增补。仅补必要现行档案与本目录证据。

R1：在原 operation journal 中保存尚未完成的输入准备快照，独立于完成感知标志；读入口经来源、身份、版本、当前许可及成功回执验证后展示结构化进度。查询不恢复、不执行、不写入。完整快照、旧请求及 gate 关闭行为保持兼容；缺可信准备材料的旧部分记录仍失败关闭，显式重提才可重建。

R2：新输入采用版本化、有界词法判断；旧解释按旧规则核验及恢复，不改写旧回执。否定范围、引用、指代无法可靠判定时保留不确定性。解释仍为候选，不产生事实权威。

公共调用方：正常 C1 入站、原请求恢复、input_outcome 只读查询及 Router/Composer 当前输入源。仅启用 W02 输入门时增加内部准备字段；不改变冻结外部契约、权限政策、SubjectState Authority、模型/Action/Evolution 分工、PAUSE/STOP、持续运行或计费。

## 验证矩阵

|规划项/补修|实现目标|定点验证|验收状态|
|---|---|---|---|
|N01/T18/R1|失败也能查询可信逐站进度|真实入站部分失败、重开、重复只读查询、独立站成功与等待原因|IN_PROGRESS|
|T18/R1|只恢复失败步骤|恢复成功、完成站不重复、原请求重放、效果/费用/revision不重复|IN_PROGRESS|
|T24/R1|当前授权及完整性|撤权、途中撤权、损坏、跨主体/环境、版本漂移、假回执、零写入|IN_PROGRESS|
|N01/T01/T02/T05/R2|中文普通否定与词内“他”|我不喜欢苹果/我喜欢其他颜色，经正式入站到Thinking上下文|IN_PROGRESS|
|N01/R2|不确定范围及历史兼容|正向、他人、引用、转述、双重否定/分句、旧v1恢复|IN_PROGRESS|
|W02施工门|组合及旧调用兼容|W02-A全部、C1/感知/表达/心智/恢复相关组合、最终完整回归|NOT_STARTED|

## 首次实跑

[reproduction-before-01.json](reproduction-before-01.json)：4 项、0 PASS、4 FAIL、0 ERROR/SKIP，退出1，3.069秒。两项R1通过正式查询复现PENDING_PERCEPTION/无记录；两项R2在实际Thinking上下文中复现错误解释。此前线索是静态判断，本次才确认为真实反例。[原始输出](reproduction-before-01.stderr.log) 原样保留。

首次工具辅助错误：PowerShell 不支持本次误用的花括号路径展开，读取命令报 ParserError；未执行写入、非 Engine 行为失败。之后改用明确路径读取，不覆盖该事实。

下一步只限本矩阵修复、验证和独立复核。历史 F1/H1/F2 UNKNOWN、所有验收历史和未开放生产能力保持原状。
