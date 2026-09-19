# P18 R2 验证续接交付；全量新增 F2 失败，等待确认

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。R1既有独立定点结论保留；R2返修待独立复核；F1/H1分别为UNKNOWN；本次全量新增失败F2，原因UNKNOWN，等待确认，不自行续修。D-072追加事实，D-073未创建/未使用；不验收、不Git写入、不P19。

本次缺失全量已补跑并完成，但未通过：1464 PASS、1 SKIP、1 FAIL、0 ERROR。新失败 F2 原始现场及清理记录见 [full-resume-01-failure.json](full-resume-01-failure.json)。没有再次运行测试、修改实现、放宽断言或超时。

## 实际实现

R2：原 Thinking 的通用异常路径没有区分调用前控制延后和调用已进入后的失败，Runtime 对未完成会话一律 UNKNOWN。现将内部执行阶段绑定到原 ThinkSession，保存 PREPARED 后方可检查控制/资源，调用前先保存 ENTERED，完整验证结果后 RETURNED。暂停留在可核验 PREPARED 并追加历史，恢复经原 Native Wake/Thinking/Action/Evolution 继续同一任务和会话，重查当前控制、权限、材料、资源、Provider 可用性及生命周期。没有新增请求账本/Authority。

当前输入失效时不修改旧 Perception/请求：明确未执行的旧会话留 ABANDONED 历史，经原 Scheduler NOT_DELIVERED 关闭；新评估由旧 task/think/阶段记录确定性派生并可追溯。原 Thinking 预留结算0，已经发生的 Wake 费用保留。普通取消/STOP、真正 UNKNOWN 不会据此生成新任务。预算 Port 内暂停的同类 R2 反例也已保存并最小修复。

R1 两个运行文件及原20项竞争测试 hash 未变。既有完整专项通过；本次全量中的资源等待控制竞争用例发生新失败 F2，不能宣称当前全量的 R1 组合全部通过，也不能据该超时认定原 R1 锁导致宿主退出的问题复发。正常入口持续运行要求不变，不安装服务、不启动自动重启、不访问生产系统。

实现位置与原理见 [实现记录](implementation-notes.md)；代码改动限定原 Thinking 类型/服务/仓储、RuntimeCognition/Native 接线、TEST诊断及新增正式回归。完整逐文件清单见 [final.pending-files.md](final.pending-files.md)。

## 修前、修复与实测

原样修前12项=11 PASS/1 FAIL，26.038秒；确认4项=1 PASS/3 FAIL，6.385秒。正式初5项=2 PASS/3 FAIL，7.379秒。同类预算内控制场景另1 FAIL，1.598秒。原独立脚本/依赖/输出已按 [before.json](before.json) 及 [补充来源清单](additional-archive.json) 逐件复制并核对原件hash，未改规划侧原件。

新增费用/配置假设2 FAIL以及持有锁文件读取1 ERROR属于本轮测试辅助问题，完整保存，见 [辅助记录](auxiliary-errors.log)。所有旧失败、工具错误、1314 SKIP、P09 segment10 UNKNOWN、P18 H1/F1原记录不动。

| 组别 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 | 原始证据 |
|---|---|---|---|---|---|---|
| formal | 22 | 22 | 0 | 0/0 | 38.321 | [记录](formal-final-03.json) · [stdout](formal-final-03.stdout.log) · [stderr](formal-final-03.stderr.log) |
| independent12 | 12 | 12 | 0 | 0/0 | 30.969 | [记录](resume-final-02.json) · [stdout](resume-final-02.stdout.log) · [stderr](resume-final-02.stderr.log) |
| independent4 | 4 | 4 | 0 | 0/0 | 8.340 | [记录](confirmation-final-02.json) · [stdout](confirmation-final-02.stdout.log) · [stderr](confirmation-final-02.stderr.log) |
| p18 | 106 | 106 | 0 | 0/0 | 197.842 | [记录](p18-final-02.json) · [stdout](p18-final-02.stdout.log) · [stderr](p18-final-02.stderr.log) |
| compatibility | 490 | 490 | 0 | 0/0 | 762.217 | [记录](compatibility-final-01.json) · [stdout](compatibility-final-01.stdout.log) · [stderr](compatibility-final-01.stderr.log) |
| full | 1466 | 1464 | 1 | 1/0 | 1376.330 | [记录](full-resume-01.json) · [stdout](full-resume-01.stdout.log) · [stderr](full-resume-01.stderr.log) |


本轮最终专项 106 PASS；新增正式 R2 22 PASS；原12/4探针各自通过；兼容 490/490 PASS。最终全量 1466项：1464 PASS、1既有1314 SKIP、1 FAIL/0 ERROR，1376.330秒，exit=1。原1444身份保留，新增22项；各组交叉包含，不能相加。

本表为同一 P18 R2 施工过程的实际结果，非独立验收或远端CI。本次软件退出后的续接只新运行 `full-resume-01`；前五组 formal-final-03、resume-final-02、confirmation-final-02、p18-final-02、compatibility-final-01 已完成，本次核对其运行前后源码与当前265文件一致后保留引用，未重复执行。见 [续接身份检查](resume-identity-check.json)。独立规划侧上轮 R1 5项/21项通过仅引用报告。

旧 `full-final-01` 开始于本地 2026-09-13 01:33:17，仅留下 STARTED。末尾停在 P09 三十逻辑日跨进程测试，无完成汇总；本次核对日志未增长、匹配的 Python 测试进程为零。JSON/stdout/stderr 原样及 SHA256 保留于 [中断说明](interruption-full-final-01.json)。实际退出码、原因、最终数量均 UNKNOWN，不算 PASS，也不据软件退出认定 Engine 行为 FAIL；没有使用旧 session75412 或重新运行 validate.py。最终索引改为实际完成的 `full-resume-01`，旧标签作为未完成历史保留。

最后一次源码调整仅追加 TEST 诊断的结果hash/receipt_id；前五组和本次补跑均覆盖该固定版本。更早兼容/测试标签与最终源码差异在 [覆盖清单](test-source-coverage.json)，不冒称重新执行或全部历史结果对应最新文件。

## 本次 F2 与历史 F1 / H1 分别说明

F2：`test_resource_wait_process_control_competition` 在原15秒控制器阈值内未观察到 SubjectState revision==2。清理前宿主存活、checkpoint未忙、token_used=320；ThinkSession 为 COMPLETED/RETURNED，Context当前有效；能力记录 SUCCEEDED 且有回执，Fake效果/credits各1，状态提交ID仍为空。脱敏异常栈到达原 ActionEvolution / SubjectStateService / JsonSubjectStateRepository 的 `os.replace`。这足以定位实际观察的失败阶段，但没有原异常类型/系统错误码，具体根因仍UNKNOWN，不能猜为机器慢、权限或并发问题。宿主接受清理STOP并退出0，无强制清理；当前查询无匹配测试进程。完整原始输出不变，见 [新增失败证据](full-resume-01-failure.json)。本次只归档并报告，不追加试验或修实现，等待用户确认。

F1仍UNKNOWN，不能充分关闭：原全量1444=1442PASS/1SKIP/1FAIL。原失败缺 ThinkSession/阶段/异常链，临时根已按旧测试清理。本轮固定交错、原进程用例及最终全量结果不能倒推那次失败是R2。当前故障时将先记录会话阶段、身份、Context、Action/Capability/回执、静态错误/引擎栈、可信时间/水位/资源和进程退出信息，再STOP/清理。

H1仍UNKNOWN：旧58项57PASS/1FAIL，资源等待超时，token_used=0，无未确认任务；宿主活着，后续STOP退出0。缺关键清理前水位和精确旧交错，不能归因于R1、R2、F1、额度中断或机器性能。[独立调查与本次诊断](f1-h1-investigation.json) 保持两项未关闭。

## 身份、保护与限制

最终源码/测试/资源 265 文件，指纹 `sha256:9781a89d4ab827c7e679916c07098a2ee931d6eccb71f0c4d4a9d9a99e46cda0`；所有最终组选定 sourceBefore/sourceAfter 与该清单一致。原1444测试身份及原断言保留，新增22另计。既有Windows符号链接权限1314跳过仍不算PASS。

63保护项、6 Schema/冻结契约、3规划源、正式7文件、版本0.1.0/pyproject和32排除项逐文件核验见 [审计](final.audit.json)。正式树预期与实测核对保留 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。本轮无Git写操作，main/HEAD/local origin保持P17基线；不联网查询远端、不声明CI PASS。

缺乏可靠阶段证据的旧 FAILED/不完整会话继续 UNKNOWN；不据错误文字迁移、不虚构未执行。ENTERED之后的无可靠结果继续待核实。生产部署、联系时段/频率/费用、真实Adapter与生产恢复仍NOT_READY。当前修复只证明本地TEST记录及既有回执能力，不承诺任意生产 exactly-once。

格式检查保留已登记的8处旧P16格式告警、3处P17原始失败日志行尾空格、1处P18旧中断日志告警；不为清告警改写历史。新增可编辑文件与新增原始证据告警分别列入审计。Git的LF/CRLF提示单列，不当作测试失败；敏感扫描与实际材料隔离回归分开记录。

## 复核命令

在 Engine 根设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`。使用未占用标签，不能覆盖原日志：

```powershell
python docs/project_memory/p18_r2_evidence/run.py review-resume-01 --review-class test_independent_resume.IndependentResumeTests
python docs/project_memory/p18_r2_evidence/run.py review-confirm-01 --review-class test_pause_resume_confirmation.PauseResumeConfirmation
python docs/project_memory/p18_r2_evidence/run.py review-formal-01 test_p18_runtime_resume
python docs/project_memory/p18_r2_evidence/run.py review-p18-01 test_p18_
```

正常完整运行入口和控制仍见 [P18测试/运行入口](../86_P18_测试索引与验收入口.md)。本轮测试控制器负责STOP及回收，进程清理记录在各stdout与 [终局进程检查](process-check.json)。施工到此停止，等待独立复核，不自行关闭 EVIDENCE_CONFLICT。

## 本次实际收口核查

前五组15份原始记录/输出的保留hash见 [输出身份](resume-reused-output-hashes.json)。新增全量的json/stdout/stderr及清理前现场hash见 [F2原始证据](full-resume-01-failure.json)。只读进程查询匹配数0。全量行为验证未通过，不能以静态检查或旧专项通过替代。

归档预审曾把两份已授权且与冻结测试版本一致的R2现行源码误列为历史漂移；已修正审计分类，未改源码/测试/旧证据。原预审及解释保留于 [preflight-01.audit.json](preflight-01.audit.json) 和 [辅助记录](auxiliary-errors.log)。最终审计继续明确保留本次全量失败，不能宣称全部检查通过。旧未完成full-final-01.stderr.log第721行的行尾空格原样保留；新增可编辑文件无此告警。
