# W02-A R1/R2 定向补修交付

本轮只完成 R1/R2 及必要验证。W02-A = IMPLEMENTED_NOT_ACCEPTED，W02 整体仍 IN_PROGRESS；W02-B/C、W03、P19 未开工。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（已知反例已在施工方关闭，尚待独立确认）。没有用户验收登记或 Git 写操作。

## 用大白话说明

现在一条消息处理中某一站失败，正式查询仍能告诉你哪些站已经处理、哪站失败、为什么等待、从哪里继续；重开同一数据根仍能查。查询不会偷偷继续业务。恢复时只补未完成站，不重复已成功的模型调用、效果、扣费或主体版本。

“我不喜欢苹果”会识别到否定，“我喜欢其他颜色”不会因为词里的“他”变成转述别人。引用、双重否定或不清楚的范围继续标明不确定；不是把有限规则冒充全能语言理解，也不是把输入直接变成记忆或主体事实。

## R1：原因与实际修改

原站点回执先于完整 Perception 保存；Core 遇到已捕获的站点错误仍会抛出，完成感知快照没有落盘。公开 input_outcome 因此提前返回 PENDING_PERCEPTION，临时输入材料也随调用结束丢失。回执存在并不等于可安全公开：旧查询确实缺少可重开验证的材料。

本次在原 operation journal 的 domainProgress 内增加可选 inputPreparation，保存原感知准备快照及已形成的 Context；不把它当作完整感知，不跳过失败站，也不新建账本。它与原请求/操作/主体/环境/观察/版本/原文 hash 绑定，原始输入不能改写；Context 只可从缺失补入一次，此后准备材料不可删除或替换。

查询先后核验当前许可，检查原来源/解释版本、回执与原 Context/Memory 事实、当前版本及完整性，返回前再次检查当前状态与日志没有变化。只输出结构记录，不输出准备快照正文；发现完成表有记录时，即使 domain 检查点缺失，也必须走原完成结果绑定核验，不能让孤立或错配结果冒称完成；待完成仍是 PENDING，并列 resume_stations。失败记录只表示这次处理失败，不能冒称记忆、事实或整轮完成。

旧完整记录继续回放；旧部分记录如果没有可核验的准备快照，仍只给 PENDING_PERCEPTION/record=None，不能凭旧日志自证。明确重提原请求时才允许从原材料补齐，而不是查询时写入。新流程的局部失败、重开及真实独立进程查询已经覆盖。

## R2：原因与实际修改

旧规则没有覆盖普通“不+谓词”，并将任意位置单字“他”视为他人。新 v2 规则先区分引用范围，使用有界主语位置和词法组合；记录否定片段及范围（偏移以去掉首尾空白的解释文本为坐标，原文仍完整保存），遇到双重否定、未闭合引用或不可靠转述范围返回不确定，不扫描心理内容作许可决定。

已存 v1 解释仍按保留的 v1 规则核验，恢复不重写旧 manifest、来源或回执；新消息使用 v2。本文不声称已经实现通用中文 NLU；复杂句、未覆盖词法和语用仍有边界，需要后续按正式规划独立验证，不能自动升级为事实。

## 文件及公共调用方

| 实现文件 | 最小责任 |
|---|---|
| [integration_results.py](../../../../src/continuity_engine/domain/integration_results.py) | 原内部进度增加可选准备快照、原身份/版本绑定及旧格式兼容 |
| [json_integration_repository.py](../../../../src/continuity_engine/storage/json_integration_repository.py) | 同一原日志内的准备记录单调性，禁止删除、改写 |
| [continuity_core_service.py](../../../../src/continuity_engine/services/continuity_core_service.py) | Context 成形时与原站点回执一道保存可核验准备材料 |
| [continuity_interaction_service.py](../../../../src/continuity_engine/services/continuity_interaction_service.py) | 原入站回调保存；正式只读查询部分进度与返回前复核 |
| [input_context_source.py](../../../../src/continuity_engine/services/input_context_source.py) | 重开后解析原准备快照，仍走原权限端口 |
| [input_processing_service.py](../../../../src/continuity_engine/services/input_processing_service.py) | 完整/部分回执区分验证；有界中文 v2 与旧解释恢复 |

正式测试只向原 [processing](../../../../tests/test_w02_input_processing.py)、[recovery](../../../../tests/test_w02_input_recovery.py) 增加测试类；第三份既有 integration 测试未改。原两份测试可移除新增类后重建为修前精确字节 hash，原断言未动。

公共影响限启用 W02 输入门的 C1 入站、恢复、进度查询与当前输入源，以及原日志可选字段验证。关闭开关的旧 native/C1、Thinking/Action/Evolution、表达、能力恢复、资源和 Runtime 由兼容与全量覆盖。没有修改公共权限政策、Scheduler、主体生命周期、有限重试或计费实现。正常持续运行、局部等待、PAUSE/STOP、现实边界及内部自主成长职责不变。

## 本轮实际运行

| 本轮实跑（集合有交集，不相加） | 结果 | 墙钟秒 / 退出码 | 原始证据 |
|---|---|---|---|
| 新增正式定点 | 25项：25 PASS、0 SKIP、0 FAIL、0 ERROR | 18.586 / 0 | [formal-final-02](formal-final-02.json) · [stdout](formal-final-02.stdout.log) · [stderr](formal-final-02.stderr.log) |
| W02-A 专项 | 66项：66 PASS、0 SKIP、0 FAIL、0 ERROR | 53.283 / 0 | [w02-final-02](w02-final-02.json) · [stdout](w02-final-02.stdout.log) · [stderr](w02-final-02.stderr.log) |
| 受影响兼容 | 218项：218 PASS、0 SKIP、0 FAIL、0 ERROR | 131.728 / 0 | [compatibility-final-02](compatibility-final-02.json) · [stdout](compatibility-final-02.stdout.log) · [stderr](compatibility-final-02.stderr.log) |
| 最终完整回归 | 1646项：1645 PASS、1 SKIP、0 FAIL、0 ERROR | 1659.112 / 0 | [full-final-02](full-final-02.json) · [stdout](full-final-02.stdout.log) · [stderr](full-final-02.stderr.log) |

原1621项身份全部保留，本轮新增25项，最终1646项。既有 Windows symlink 创建权限 WinError1314 SKIP 仍单列，不计 PASS。JSON seconds 是墙钟时长，stderr 的 unittest 时长另行保留。无独立复核新结论、无远端 CI 运行或 CI PASS 声明。

最终282份源码/测试/资源指纹：`sha256:1021239d8214b38493aa3ff8ea5011c7b27856966bfe3395545607a8c066c523`。上述四组的前后清单均一致，见 [最终冻结清单](frozen-source-02.json)。此前原 W02-A 41/813/1621 结果只作历史引用。本轮此前686项兼容全部通过、full-final-01的1645项为1644PASS/1SKIP（1649.505秒）；它们是真实实跑，但只覆盖 frozen-source.json 前一版。随后1行查询守卫及1个正式反例的增量使源码身份变化，故最终重跑定点、完整W02-A、查询/原日志/C1/表达及自主性兼容组合，再跑一次全量。前版结果不能冒充最终覆盖，也不是反复重跑取代解释失败。

## 失败历史与剩余事项

修前 [4项反例](reproduction-before-01.json) 全部真实 FAIL（3.069秒），不把静态线索冒称既往独立复现。修后第一组4PASS。后续 [45项组合](w02-intermediate-01.json) 出现本轮规则引入的1个真实回归：无主语的普通问句被额外送去核实站。未改旧断言，收窄规则后原问句以及最终完整专项/全量覆盖通过。详见 [运行历史](test-history.md)。

一次 PowerShell 花括号路径读取报 ParserError 属辅助工具问题，未写入源码；原始事实另记 [开工与矩阵计划](plan.md)。末轮核查又证实 R1 的完成表交叉绑定漏口：有效 [result-binding-before-02](result-binding-before-02.json) 为1 FAIL，最小查询条件补齐后 [result-binding-after-02](result-binding-after-02.json) 为1 PASS。前两次该探针在嵌套 TEST 路径创建临时文件时分别出现1个辅助 ERROR，尚未到达目标断言；改用独立短 Temp 根后才得到有效反例，未改断言。两份ERROR原件照存，不能当作Engine行为缺陷。详情 [核查结论](integrity-check-outcome.json)。本轮没有测试中断或新增SKIP。

历史 F1/H1/F2 仍 UNKNOWN，本轮问题不并入旧案。W02-A 仍待规划窗口独立复核及用户确认；自动回忆、外部资料完整可信吸收与最终贯通仍在 W02 后续子批次。尚未部署生产、接入真实服务或开放任何正式删除/隐私/外部能力。

## 复核入口与审计

[逐项对应矩阵](matrix.md) · [可运行复核命令](review-entry.md) · [施工日志](../../03_施工日志.md) · [终局审计](final.audit.json) · [累计及补修清单](final.pending-files.md) · [逐文件hash及排除清单](final.inventory.json) · [子进程核查](process-cleanup.json)。

终局审计已核对：六Schema/25冻结边界在原63项保护清单内全部一致；三份旧规划、三份现行规划原件与归档身份、正式7文件、版本0.1.0、32排除材料及25份原W01规划均未改。正式数据树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。原W02证据78份、原测试类正文及旧工程档案正文 hash 一致。

272份Python源码/测试静态解析通过；新增及直接相关文档链接检查无缺失；限定敏感材料与临时产物扫描未命中（不等于证明任何秘密都绝不可能存在）。`git diff --check` 退出0，有六条Git既有LF/CRLF转换提示；本批未新增行尾格式告警，旧阶段原始格式告警与日志继续保留。进程快照未发现本轮测试根进程或其后代存活，15条最终组的子进程结果可追溯；未清理无关进程或目录。

累计W02-A成果174文件，其中本次补修涉及91文件：六份运行实现、两份正式测试、七份直接工程档案和76份新增证据/报告/核查工具。原32排除项及25份W01/规划材料另列，不计入174。三份互相引用的终局审计文件不自填循环hash，其余均提供逐文件hash。完整Git状态以审计为准：main，HEAD/local origin仍为 `ce6f4771140c4b6bdb0f5ae81d4c68bfc8653e88`，本地ahead/behind为0/0，暂存区空；本轮未查询真实远端或CI，无Git写操作。

源码固定后仅补档案，不机械重跑全量。停止在独立复核交付处，不暂存、提交、push，不进入后续批次。
