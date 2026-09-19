# P18 R1返修 / H1历史超时调查交付

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072追加返修事实，D-073未创建/未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，R1待独立确认，H1根因UNKNOWN；本轮全量新增F1超时亦未闭合，不自行关闭。

## 实际改动与责任边界

R1已实现：checkpoint事务采用线程锁与OS锁共用的0.25秒获取期限及25ms等待；仅专用RuntimeCheckpointBusy进入宿主可中断退避。owner运行锁继续立即拒绝第二宿主。忙锁不是未执行证明，原Scheduler/Wake/Thinking/Action/Evolution/E5-A身份及结果仍是原权威；没有新账本。观察等待期间核对最新控制修订，不覆盖已提交RESUME。退出诊断无法写入时不再争用同一锁覆盖原异常；保留静态诊断及原owner，后续按PRIOR_HOST_LOST核实。

运行实现仅修改[仓储](../../../src/continuity_engine/storage/json_runtime_repository.py)及[宿主](../../../src/continuity_engine/services/persistent_runtime_service.py)。新增[正式回归](../../../tests/test_p18_runtime_contention.py)；原[真实进程测试](../../../tests/test_p18_runtime_process.py)仅增加可信时间、next_check_at、活动、任务/尝试、资源、宿主生存与退出信息的清理前诊断，原断言与超时阈值未放宽。只输出结构和静态错误码，不记录私密正文、凭据或任意异常repr。

## R1证据与修复过程

- 规划原5项3PASS/2FAIL（同一个R1）的报告、探针、stdout/stderr/result和身份审计等10份原件已逐文件复制并核对SHA-256，见[来源清单](before.json)。规划侧原件不改。
- 本轮原样independent-before-01：3PASS/2FAIL，6.990秒；第一版修复后independent-after-01为5PASS/9.695秒。原五项代码未变。
- 正式first17PASS后，检查发现RUNNING/资源等待用例可能仍处于next_check_at之前，未实际争锁。增强为显式推进到期时间并断言RUNTIME_CHECKPOINT_BUSY诊断，增加长锁与效果后观察竞争，strengthened19PASS。未将较弱版本冒充最终覆盖。
- observation-before-01真实1FAIL：短等待后旧PAUSED观察覆盖已提交RESUME显示状态。同属R1“不得覆盖较新控制”；已添加控制修订绑定并保留失败。后续正式与全量验证其关闭，未替换旧输出。
- 本轮最终组和各自命令、源码前后清单见下表及同标签原始stdout/stderr；中间结果不能冒充最终身份。

| 验证 | 标签 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 |
|---|---|---|---|---|---|---|
| independent | [independent-final-01](independent-final-01.json) | 5 | 5 | 0 | 0/0 | 9.14 |
| formal | [formal-final-01](formal-final-01.json) | 20 | 20 | 0 | 0/0 | 40.574 |
| p18 | [p18-final-01](p18-final-01.json) | 84 | 84 | 0 | 0/0 | 140.075 |
| compatibility | [compatibility-final-01](compatibility-final-01.json) | 254 | 254 | 0 | 0/0 | 485.865 |
| full | [full-final-01](full-final-01.json) | 1444 | 1442 | 1 | 1/0 | 1233.659 |

原1424个身份保留，本轮新增20项；最终全量1444项=1442PASS、1既有Windows symlink权限1314 SKIP、1FAIL/0ERROR，退出码1。不能报告全量通过。独立5项单列，不增加Engine正式测试数。P18和定点及兼容均包含在全量中，不重复相加。所有最终组均实际执行；未引用旧1423PASS冒充本轮全量，没有远端CI实跑声明。[各轮源码覆盖及逐文件差异](test-source-coverage.json)明确哪些中间结果不对应最终版本。

## H1：仍为UNKNOWN

历史p18-final-04为57PASS/1FAIL，原宿主仍存活且后来STOP退出0，无强制清理；与R1无STOP退出2不同，没有证据将二者合并。旧sourceBefore/sourceAfter一致，但与原final07已有6文件身份变化。已读取的历史运行材料保留hash清单，未提供完整的当时变更文件正文快照，不能伪称已精确重建历史版本。

STOP前后可用记录：token_used=0、pending_tasks=1、unconfirmed_tasks=0、observations=2、last_time=09:01；STOP已覆盖activity/reason/next_check_at。缺少超时发生时逐任务状态、时钟读点、水位及资源预检结果，无法验证当时交错。

当前受控验证覆盖在维护观察写入时推进时钟，以及故意让测试控制器超时后在STOP之前保存完整安全诊断；这些是当前正向与证据设施验证，不是历史根因修复。未增加原超时阈值、未减少断言、未循环运行直到绿。见[结构化调查及原始来源](h1-investigation.json)。剩余风险是历史资源等待观察的间歇问题尚不能排除，独立复核必须保留UNKNOWN或显式评估残余证据限制。

## F1：本轮全量新观察，仍未闭合

原 `test_idle_and_subject_silence_do_not_end_process` 在暂停/恢复后的第二轮等待revision推进超时，full-final-01真实1FAIL。STOP前新增诊断捕获宿主alive、checkpoint_busy=false、activity=WAITING_VERIFICATION、cognition任务UNKNOWN/attempt_count=1，token_used=640，可信时间10:02:00，next_check_at=10:02:05。STOP退出0、无forcedCleanup、所有子进程已回收。

这不是R1的无STOP退出2，也不能与H1零模型消耗/无未确认任务的旧现场合并。未捕获失败时原ThinkSession/Action/Capability的异常栈，原隔离Fixture在保存诊断和STOP后按测试规程清理。只做两次固定诊断：同步双轮ADVANCED（2.404秒）；原进程流程仅包装静态异常位置采样，1PASS（11.296秒）。均未复现，不能用它们覆盖全量FAIL。见[完整调查与原始hash入口](full-timeout-investigation.json)、[同步诊断](resume-diagnostic-01.json)、[进程诊断](resume-process-diagnostic-01.json)。

没有证据支持继续修改C1、权限、回执或UNKNOWN语义来“修好”F1；本轮停止无依据的实现变动，交回独立复核继续定位这个新阻断。全量之后源码与正式测试未变，没有再次跑全量。当前不能声称P18全部验证通过。

## 运行语义、限制与复核命令

正常start默认持续运行；无人发消息、沉默、队列为空或单项额度不足都不是停机理由。事务锁忙不伪报控制成功；资源、权限、Context、P15生命周期和STOP仍由原链处理。长期锁持有时每次操作有界拒绝/延后，宿主等待而不忙循环、不假称在思考；checkpoint_busy是瞬时只读诊断，其他查询字段是最后提交的记录。

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python docs/project_memory/p18_repair_evidence/run.py independent-check-01 --independent-probe
python docs/project_memory/p18_repair_evidence/run.py p18-check-01 test_p18_
python docs/project_memory/p18_repair_evidence/run.py full-check-01
```

必须选未占用标签。正常持续启动与控制命令仍见[86号入口](../86_P18_测试索引与验收入口.md)。本轮仅隔离本地TEST/Fake，不安装常驻服务、自启动或外部自动重启，不启用正式联系/费用政策、生产凭据或供应商；Assistant/Vio未修改，生产恢复仍NOT_READY，不宣称生产exactly-once。

## 完整本轮测试历史

| 标签 | 状态 | RUN | PASS | SKIP | FAIL/ERROR | 秒 |
|---|---|---|---|---|---|---|
| [compatibility-final-01](compatibility-final-01.json) | FINISHED | 254 | 254 | 0 | 0/0 | 485.865 |
| [formal-final-01](formal-final-01.json) | FINISHED | 20 | 20 | 0 | 0/0 | 40.574 |
| [formal-first-01](formal-first-01.json) | FINISHED | 17 | 17 | 0 | 0/0 | 34.224 |
| [formal-strengthened-01](formal-strengthened-01.json) | FINISHED | 19 | 19 | 0 | 0/0 | 39.016 |
| [full-final-01](full-final-01.json) | FINISHED | 1444 | 1442 | 1 | 1/0 | 1233.659 |
| [independent-after-01](independent-after-01.json) | FINISHED | 5 | 5 | 0 | 0/0 | 9.695 |
| [independent-before-01](independent-before-01.json) | FINISHED | 5 | 3 | 0 | 2/0 | 6.99 |
| [independent-final-01](independent-final-01.json) | FINISHED | 5 | 5 | 0 | 0/0 | 9.14 |
| [observation-before-01](observation-before-01.json) | FINISHED | 1 | 0 | 0 | 1/0 | 2.331 |
| [p18-final-01](p18-final-01.json) | FINISHED | 84 | 84 | 0 | 0/0 | 140.075 |
| [resume-process-diagnostic-01](resume-process-diagnostic-01.json) | FINISHED | 1 | 1 | 0 | 0/0 | 11.296 |

首轮P18专项与兼容因一次工具轮询误处理重叠34.674秒，使用独立Fixture、源码未变，已记录auxiliary-errors.log；不声称该两组严格串行。最终全量仅在其他测试全部结束后单独运行。只读rg路径错误等辅助记录保留，不算Engine缺陷。所有前期P00—P18 FAIL/ERROR/SKIP与P09 segment10 UNKNOWN保留，原p18_evidence不改。

## 身份、保护、Git与交付

最终来源为264份源码/测试/资源，完整路径和SHA-256、原1424身份及旧测试断言核对、63保护文件/六份Schema/外部契约、三份规划、正式七文件及树、版本/pyproject、32排除项、链接/敏感内容/差异/进程清理及完整Git状态见[终局审计](final.audit.json)。完整P18成果与本轮新增材料分别列于[逐文件及排除清单](final.pending-files.md)，不以旧164项限制新增必要证据数量。

本轮无暂存、commit、push、分支、tag或release；HEAD仍5a3247a5d23ff17de2b4ba12bc327594b492e725，实际远端未查询，无CI PASS。测试子进程由各自控制器回收；记录命令、退出码、是否forcedCleanup及清理前诊断。最终只读进程观察另存证据。D-073未创建，不自行验收，完成后停在P18交回独立复核。

## 本次实际终局检查（与行为通过区分）

closeout-check-01审计的文件/文档检查errors为空，但因全量F1未闭合，审计真实退出码为1，behavioralBlockers明确保存原失败。不得将“身份核对无差异”写成“全量通过”。最终审计采用同样规则。

264份源码/测试/资源与最终所选五组运行前后清单一致；源码映射的排序紧凑JSON指纹为 `sha256:15994f619573701c5bc77b1fe8d8649f887cc82aea7c89d393a06a5278d47e81`。254个Python源码/测试文件可解析。原1424项身份保留，原process测试的assert/fail调用AST和方法/超时默认值均不变；其他原测试逐文件hash不变。矩阵P18-02/P18-12含F1失败身份，已明确标注，未把所有条目写成全量PASS。

63项保护（含六份Schema和外部契约）、三份规划、正式七文件、31个P10脚本和1份P14旧报告逐文件hash不变。正式数据树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。版本0.1.0，pyproject SHA-256仍为 `40703a155ab1c1626901d1b61363384e49b5c64e58303cc110fe499ff6c25419`。独立原件/副本10份hash匹配；原p18_evidence及更早不可改历史无漂移。

预检1276个本地链接无断链，敏感模式无命中，未发现本轮可编辑档案格式问题；最终数量以final.audit.json为准。git diff --check退出0，有四个既有修改文件的LF/CRLF提示。原八处历史格式告警、P17三处原始日志告警及P18旧中断日志一处行尾空格继续保留，未为“全绿”改原日志。F1摘要首次提取因CLI记录不含stage字段出现KeyError，已保留辅助错误说明，修正提取后存档，不计作引擎缺陷。

正式定点、P18和全量的P18进程记录均childrenReaped=true，未使用forcedCleanup；全量失败后原控制器先保存诊断，再STOP退出0。补充诊断的进程也已退出。[最终只读进程检查](process-check.json)匹配0个限定P18 Python进程，未执行终止操作。已忽略的旧缓存/正式数据/历史材料只作清点，不清理、不混入清单；不扩展声明所有系统进程均已审计。

Git仍为main，HEAD与本地origin/main均 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地ahead/behind=0/0、暂存区空。21个已跟踪修改是整个未提交P18成果的一部分，本轮没有Git写操作。完整未跟踪数量与最终新增档案计数在终局清单和审计中逐项记录，32项排除全部保留。实际远端未查询，无已跟踪Actions workflow及本次CI run/check，不声称CI PASS。

当前交付是“R1已实现，H1及F1原因仍未知，等待独立复核”，不是P18已通过全部验收。下一步需定位F1失败时原ThinkSession、Context、Action及回执绑定为何进入UNKNOWN；没有足够证据时不擅自改动这些权威和恢复规则。
