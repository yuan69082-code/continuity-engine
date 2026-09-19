# P18 持久化链定向调查：当前有效任务

用户已授权定位 F2，并比较 F1/H1；形成明确反例后可在 P18 内最小修复。不是重新开工。P18 IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT；不 D-073、不 Git 写、不 P19。

开工：main / HEAD 5a3247a5d23ff17de2b4ba12bc327594b492e725；265 源码/测试/资源与上轮最终审计完全一致；1466 原测试身份、354 既有成果、32 排除项已固定到 before.json。旧证据不修改。本目录新标签独立运行，禁止调用旧 validate.py 或覆盖旧 run。

预定有界实验：

1. 原 F2 用例一次，结果无论通过/失败均保留，不能证明历史根因。
2. 用子进程握手保持实际 SubjectState 读取句柄，验证同根原子替换；记录真实异常类型/errno/winerror、操作与 hash。正常无句柄对照；读到旧完整快照合法，不能半写。
3. 在原 Native 链动作成功后、状态替换前控制失败，故障解除后推进原时钟与查询；验证同一会话、回执、效果和费用不重复。
4. 状态已经保存但返回丢失、权限变化/PAUSE/STOP/CAS/真正 UNKNOWN 对照；重开恢复。
5. 在相关阶段注入非占用 OS 错误，不能无条件重试；诊断失败有限兜底不覆盖主异常。

候选：Windows 读取句柄共享删除语义；写事务/CAS；后续事实恢复与被冻结的测试时钟水位；全量状态污染。没有证据前不预设原因。F1缺失败时会话/调用阶段；H1缺清理前水位，均不自动关闭。

当前已读 SubjectStateRepository/Service、ActionEvolution、RuntimeCognition、Native Wake、Runtime/Scheduler 控制链。原 Native query 对已完成 Thinking 本来会尝试原事实恢复，先实验验证，不盲目重做恢复系统。

验证：先修前定点和正常对照，固定实现后 P18 / 受影响兼容 / 单独一次全量。若全量新失败先保留清理前现场，不自动启动下一轮。

## 2026-09-13 当前进度（定点完成后）

已复现：真实 Windows 子进程持有 JsonSubjectStateRepository 读取句柄，原 os.replace 抛 PermissionError / errno=13 / winerror=5；DELETE-access 探针确认当前 sharing violation=32。原记录完整，临时文件在 replace 失败后清理。Native 同样在已执行一次效果后卡在未提交状态；解除故障、推进可信查询水位后，原恢复链能复用原事实，不需要新增账本。

采用最小 P18 opt-in 有界替换等待（0.25秒上限，25ms让出），仅对已核实共享竞争；每次重试重查当前 Context/控制及目标文件完整字节版本。STOP/PAUSE/撤权/CAS拒绝，不重发已成功动作。普通访问拒绝、路径/磁盘错误不重试。写/flush/fsync失败临时路径登记及清理异常覆盖主异常的已复现缺口一并最小修复。

本轮源码增量：json_repository.py、wake_perception_thinking_action_service.py、p18_runtime_fixture.py；新增 p18_persistence_diagnostics.py 和 test_p18_persistence.py。旧测试文件未改。267文件最终身份固定到 frozen-source.json；原1466身份+14新增=1480。

已完成：formal-final-02 14/14 PASS，11.493秒。old-writer-confirm-01 使用精确归档 writer 与当前握手测试重建，2/2 FAIL，证明原缺口；它不是旧版本全量。修前/中间结果及辅助错误全部保留。p18-final-01 已启动；必须读取结果后再启动兼容与单独全量。不得盲目恢复旧session，先看新标签状态和进程。

F2实际历史缺OS码，当前同阶段/同症状可复现风险已修；不能把受控Win5倒写为历史实测OS码。F1/H1均UNKNOWN。EVIDENCE_CONFLICT=PRESENT，D-073未创建/未使用，不Git写。下一步只完成已授权验证与档案；源码已固定，不无依据改代码。

## 最终全量已启动

本目录 p18-final-01 完成120/120 PASS，174.733秒；compatibility-final-01完成605/605 PASS，841.034秒。三组（含formal-final-02）sourceBefore/sourceAfter均与267文件冻结清单一致。

2026-09-13本地22:50后，新独立目录的full-final-01仅启动一次。必须读取JSON状态、stdout/stderr、匹配进程和完成汇总，不盲目重开；该标签与旧p18_r2_evidence/full-final-01不是同一运行。若完成FAIL先保存原因链，不自动重跑全量。若完成PASS且源码仍固定，可执行本目录finalize.py生成实际报告/现行档案，再保存终局进程检查、执行audit.py新标签。finalize.py只归档不测试，旧目录脚本不要重执行。

## 当前施工完成

本轮新增正式14项；P18 120 PASS；兼容 605 PASS；最终全量 1480 项=1479 PASS、1既有1314 SKIP、0 FAIL/ERROR，1284.129秒，exit=0。原1466身份及断言保留，各组有交集，不重复相加。

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加调查/返修事实；D-073未创建/未使用。 F1/H1 UNKNOWN；F2同阶段风险已修，历史排他原因未证实。最终结果索引selected-runs.json；源码固定，不再启动测试。完成审计后交回独立复核。

本地2026-09-13 23:12全量已结束，无需再运行或恢复旧session。只读查询相关Python进程为0，预审无错误。final-report.md已写入真实全量1480项=1479PASS+1既有1314SKIP、1284.129秒；所有既有与新增失败原样保留。完成final审计与逐件核验后即交付，不继续调查扩项或改源码。
