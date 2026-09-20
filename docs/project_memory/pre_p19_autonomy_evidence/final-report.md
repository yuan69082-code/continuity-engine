<!-- PRE_P19_ACCEPTED_D074_20260920 -->
## 当前批次正式验收：D-074

用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。

[验收依据、逐项状态与最终清单](../pre_p19_acceptance_evidence/acceptance-report.md)。

## 以下为发生时的历史记录

下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。

# P19 前 R1—R4 合并返修交付

本轮修复已实现，等待独立复核。批次状态 IMPLEMENTED_NOT_ACCEPTED；PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=PRESENT。P00—P18 历史 ACCEPTED / D-073 保留，P19—P23 NOT_STARTED；没有新的用户验收、Git写操作或P19开工。

起点 main / HEAD / 本地origin：cb528d74884990915737b491ca6a9f2c35cc512a。原1517个测试身份完整保留，新增34项；当前274份源码/测试/资源，最终指纹 `sha256:e58eceb0c28b1f753ce9be059ff22b6bd4d5cf1562d64737b6f5cd318908cc93`。文件及测试身份见[final-source.json](final-source.json)。

## 实际修改与责任

- **R1**：CoreDecisionPolicy的旧Action approval曾阻止意图形成，未完成世界执行又在独立Evolution前抛错。现由原C1/native链分别保留候选、内部授权与外部结果；当前Context、状态权限、revision和生命周期仍核验。含外部意图的混合提案仅提交Engine生成的独立心智/成长字段，模型其他提案保留原ThinkSession，不提前成为效果成功事实。内部已完成只释放认知队列；真正世界UNKNOWN仍留在E5-A/Outbox，并阻止换认知ID重发同能力/目标的未确认效果。
- **R2**：移除target包含critical的风险提升。保留ActionType最低风险（USE_TOOL仍HIGH）、明确更高风险及所有确认/权限/资源门。不把显示名称或模型自报LOW当可信资产证据，也未实施D1完整风险体系。
- **R3**：正常Composer经历经当前来源和独立根检查，形成可修订TRUST/DOUBT理解，经原Action/Evolution持久化；非Fixture直接预填。旧Will的有效承诺/支持进入下轮，当前相反经历可形成QUESTION并修订承诺，不简单消除矛盾。未选或撤回的根不再充当当前支持，但历史主观理解不因检索缺失被删除；缺证据理由可追溯。不自动制造LOVE/HATE，不扩原四字段Learning和rollback权限。
- **R4**：RuntimeCognition除驱力变化外，依据已有未决关注/有效Will提出有界复议。保留最低间隔与原稳定任务身份；hold/DEFER/rest较晚再评估，明确放弃/无需求不强制Provider。预算不足、STOP、主体生命周期、UNKNOWN和原防重复门保持。Scheduler不创造心理内容。

运行修改只在7个services文件：action_evaluators.py、continuity_core_service.py、continuity_interaction_service.py、dynamic_mind_service.py、execution_service.py、runtime_cognition.py、wake_perception_thinking_action_service.py。新增4份test_pre_p19_autonomy测试，纠正2份旧测试中的错误目标预期；无Schema、公共权限接口、计费、存储格式或权威归属变更。细节与限制见[实现记录](implementation-notes.md)，逐项入口见[矩阵](matrix.md)。

## 真实验证与失败历史

本轮正式定点/交叉 combined-04：34/34 PASS，103.701秒；最后兼容 compatibility-final-02：175项，175PASS、0SKIP、0FAIL/ERROR，196.425秒。

最终固定版本完整回归 full-final-02：1551项，1550PASS、1SKIP、0FAIL/ERROR，1765.117秒，退出码0。SKIP原因逐项保留原JSON（Windows symlink权限1314）；不算PASS。上述三组运行前后源码均与最终版本一致，集合重叠不相加。没有远端CI实跑或CI PASS声明。

修前R1为1PASS/6FAIL，R2为3个失败用例（8条subTest失败），R3为1PASS/4FAIL，R4为2PASS/3FAIL。首次辅助错误、测试设置错误、旧兼容revision预期失败、初稿队列占用与倾向消失反例均完整保留，未用新PASS覆盖。两个旧测试的修正依据及新增等效保护详见实现记录；没有删测试或跳过导入错误。

第一轮完整回归full-final-01为1550项：1548PASS、1既有SKIP、1FAIL，1718.557秒。失败证实本轮R1移除早退后漏保留原Action拒绝的派发拦截（Fake调用2次）。已在同一core入口最小修正，原P13零效果断言未改，修前全量与修后原用例均保留；新增反例也证明候选保留、零效果/费用及重启不派发。新增测试最初两次因临时根路径过长ERROR，单列为辅助问题。当前完整回归是修正后新标签的实际执行，不把第一轮失败抹去。

全部唯一标签、实际命令、stdout/stderr、退出码、时间和覆盖身份见[测试索引](test-index.md)。独立原诊断副本不变：修后观察现实允许时内部revision与效果各一次；现实拒绝时内部revision推进、世界效果及实际费用为零。诊断不冒充正式测试数量。

## 原始目标与限制

已经实测无新聊天仍有真实内部认知；自然进入稳定区及合成饱和、休息/延后、资源耗尽再恢复、跨进程续接、显式STOP及停止后再开不复活。真正执行UNKNOWN、回执丢失、内部写入前后中断、权限/Context变化与小容量队列有定点检查；原锁竞争、存储修补与生命周期恢复由最终兼容及全量覆盖。没有新增运行时长/轮数/概率性停机条件，测试控制器明确STOP并回收自己的进程。

仍未开放真实服务/凭据/部署、正式联系频率/费用政策，D1/D2/D3的风险、深思和全量固化授权改革未施工。倾向生产者仅处理现有结构化经历词汇；当前支持不足会保守要求重新理解，不等于任意自然语言心理解释已实现。有限本地Fake幂等不代表生产Adapter exactly-once。历史F1/H1/F2仍UNKNOWN，未补造原系统证据或宣称唯一归因。本轮是否闭合由独立复核决定。

## 审计与交接

保护63项、规划3份、正式7文件、版本0.1.0/pyproject、原32项排除材料与独立原件逐文件检查结果见[最终审计](final.audit.json)。正式数据预期指纹为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，只有逐文件一致才沿用该树身份。源码静态、文档链接、敏感材料及差异检查亦在审计中；历史原件/失败日志格式告警原样保留。

[精确待提交与排除清单](final.pending-files.md)列出本轮源码、测试、直接档案和必要证据；清单与审计自引用hash规则写明。暂存区为空，HEAD不变，完整只读Git状态存于审计。进程检查见[process-cleanup.json](process-cleanup.json)。本批次交回独立复核，不提交、不push、不进入P19。

## 补充正常逐步推进（源码未变，单列场景）

[progressive-02](progressive-02.json)及[stdout](progressive-02.stdout.log)/[stderr](progressive-02.stderr.log)：15轮，每轮6逻辑小时加60秒调度推进，总90小时15分的逻辑跨度；默认need_delta=0.02未改变，TEST时钟跃进容许量明确设86400秒。第7—15轮数值变化低于该门槛仍实际调用并提交，15次Provider调用对应15次revision推进，token_used=4800，世界效果/执行/credits均0；显式STOP，成功Fixture已清理。99.468秒、exit0，前后源码与最终全量一致。不是90小时真实持续负载测试，不计入Engine正式1551项。

[progressive-01](progressive-01.json)及[stderr](progressive-01.stderr.log)保留辅助AttributeError：观察脚本误用host.status()（正确API为query()），诊断和STOP后读取也触发同类错误，未得到完整观察数据；STOP调用位于错误读取前。保留失败根与日志，未修改引擎。修正观察脚本后使用新标签，仅补该场景，未重跑全量。
