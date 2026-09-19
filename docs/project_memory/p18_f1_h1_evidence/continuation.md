# P18 F1/H1 继续追查：当前有效任务

用户授权继续P18定向调查与局部修复；不能因通过或暂未复现而结案。保留F2/R1/R2及全部既有成果。P18 IMPLEMENTED_NOT_ACCEPTED、EVIDENCE_CONFLICT=PRESENT；不D-073、不Git写、不P19。

新增约束：公共Scheduler/C1/公共仓储等共用实现修改前必须说明必要性、文件、影响和兼容验证并等待用户确认。可先只读调查及在TEST编写反例；未获确认不能自行改共用实现。

已读工作流程、当前状态及主链。开工按prepare.py固定267源码/测试/资源、1480测试身份、450已有成果、32排除项；原件及快照hash见before.json。旧结果只引用，不在本轮冒称实跑。

F1与H1分开：F1第二轮UNKNOWN/token640，但缺原会话阶段与异常链；H1token0、无UNKNOWN，缺清理前水位。F2共享竞争仅当前受控机制确定，不能预设三项同源。

第一组有界实验方向：追踪每次可信时钟读取与控制checkpoint采样，检查控制器推进Frozen Clock是否穿过同一tick的不同阶段；以握手控制暂停/恢复、Provider返回、Context构建、资源预检和观察发布，分别比较固定时间/中途跃进。复查共享文件锁与当前查询水位，不把UNKNOWN强行清零。每个失败在STOP/清理前存脱敏诊断，保留原始错误与系统码。

新证据仅本目录唯一标签；不重执行旧validate/finalize，不并行重复全量。若需要共用实现修改，固定反例与当前进度后等待必要确认，继续不依赖该项的调查。


## 当前真实进度（2026-09-14本地00:16后）

原267源码和1480正式测试完全未变。本目录形成当前两个真实Windows读句柄机制：H1 checkpoint替换失败后BACKOFF；F1短占用在DELETE探测前消失使P18原提交不重试。有效定点及真实进程失败、无故障对照已落盘，见investigation-report.md。辅助ImportError/ValueError原样保留，不能作为机制证据；有效进程标签是h1-original-process-before-03、f1-original-process-before-02。

下一步必须等用户确认公共实现修改（json_repository.py及其P18 checkpoint调用json_runtime_repository.py），方案见proposed-change.md。不能误认已获该项明确确认。待确认前只做档案/身份核验，不修改运行代码、不启动全量。F1/H1历史原始异常仍缺失，不能唯一归因；不清EVIDENCE_CONFLICT，不D-073，不Git写，不P19。

最近匹配进程只读检查于本地2026-09-14T00:16:27.2843040+08:00，相关Python为0；子进程各自清理记录在原stdout。恢复时仍需重新核实，不盲目使用旧session或重跑validate。
