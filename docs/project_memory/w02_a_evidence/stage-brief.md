# W02-A 开工记录

本文件保留开工时的 IN_PROGRESS 记录；当前交付状态及最终结果见 [交付报告](final-report.md)。

状态：IN_PROGRESS。用户已确认本批施工；不是整个 W02、W03 或 P19 开工。D-075 仅登记施工授权，非验收。

- STAGE：W02-A 输入理解与逐站处置记录。
- SOURCE OF TRUTH：[已确认开工说明](../w01_planning_v15_20260923/w02-a-proposed-brief.md)、[现行三规划](../现行规划版本索引.md)、本次用户确认。
- ORIGINAL REQUIREMENTS：原始消息经原入站、Perception、C1、Router/Composer、Thinking、Action/Evolution；接收与已记住分开。
- V6.9 DETAILS：本批主责 N01，提供 N02 当前输入、N11 处置结构前置；不预填完整自动回忆或外部可信吸收。
- AMENDMENT OVERRIDES：合法内部处理不逐条人工审批；现实执行限制不抹掉内部认知；工程审批不植入主体循环。
- KEEP RULES：原唯一权威链、当前权限/来源/版本/资源/生命周期、E5-A 回执和 UNKNOWN 语义；原持续运行、P00—P18 验收及 F1/H1/F2 UNKNOWN。
- DEPENDENCIES：原 operation journal、Consolidation、Context 扩展端口与已验收 C1。
- NOT READY：W02-B/C、W03、W05、P19 页面与后置生产能力。
- FILES ALLOWED：严格使用已确认开工说明第 3 节的逐文件清单；不自动修改其他运行模块。
- FILES FORBIDDEN：保护项、正式数据、规划原件及旧归档、版本、32 排除项、Assistant/Vio。
- TESTS REQUIRED：新反例→定点/交叉→受影响兼容→最终固定版本完整回归；不把历史 1580 项结果当新运行。
- PLANNING CONFLICT：开工尚未发现实质矛盾；若实际接线需要清单之外修改，停止对应项报告。

## 基线与验证矩阵

本轮 [baseline.json](baseline.json) 实测 main / HEAD ce6f4771140c4b6bdb0f5ae81d4c68bfc8653e88，275 源码/测试/资源，57 个既有未跟踪文件原样保留；暂存和已跟踪工作区空。原 1580 身份保留；历史 1579 PASS、1 既有 1314 SKIP 仅引用。

实现顺序：先验证原扩展端口能承载本轮临时材料；输入解释/站点进度附在原 operation；再接原业务站及恢复。Trace 只记录结构和身份，不作为提交事实。

| 组 | 定点内容 | 不变量 |
|---|---|---|
| 输入 | 原文、否定、愿望、他人、时间/歧义 | 不捏造事件、权限或已记住 |
| 处置 | 临时/候选/待证据/引用/提案/不采用/失败 | 仅相关站；引用原业务事实 |
| C1 | 临时 source 经原 Router/Composer 到 Thinking | 非权威、预算和当前来源重验 |
| 恢复 | 局部失败、返回丢失、重复/冲突、重开 | 不重发模型/效果/扣费/revision |
| 兼容 | 关闭开关、旧序列化、P01/P09 快照、P16/P17、P18 | 旧行为和原断言保留 |
| 交付 | 固定源码完整回归、保护/链接/差异/进程核查 | 不 Git 写、不验收、不进入后续批次 |

工程中的当前状态后续只追加真实进度。完整 W02 不能由 A 代替。
