# P18 用户正式验收归档（D-073，2026-09-19）

用户正式验收当前已交付、已独立复核的 P18 成果，并明确接受历史 F1/H1/F2 原因无法唯一确定的遗留不确定性。本次仅归档；没有修改运行源码、正式测试、运行配置或政策，没有执行 Git 写操作。

P00—P18 = ACCEPTED；P18 / Engine side / P18-01—P18-12 = ACCEPTED；P18 Vio dependency = NONE；P19—P23 = NOT_STARTED。验收决定见 [D-073](../04_决策记录.md)，逐项实现、测试身份和验收范围见 [十二项映射](accepted-matrix.json) 与 [现行矩阵](../84_P18_规划施工测试验收矩阵.md)。

## 验收范围与现行阻断

验收覆盖已交付的默认持续运行入口、同一主体身份与跨会话连续性、原认知链、控制与生命周期门禁、局部资源等待、双进程保护、持久化与事实恢复，以及 R1/R2、有限存储重试和异常原因链保留补修。依据为 [2026-09-19 独立复核报告原件副本](independent/review-report.md) 与用户本次明确决定。

异常链缺口已按独立证据关闭。沿用 D-071 等既有档案对“现行阻断”的定义，PLANNING_CONFLICT = NONE、EVIDENCE_CONFLICT = NONE：已知实现阻断有复核证据，历史不确定性有用户明确接受决定。这不代表历史根因已查明、不保证不存在其他缺陷，也不把以前的 PRESENT 改写为 NONE。没有新增状态枚举或改变运行中的状态格式。

正常入口仍默认持续运行；无消息、空闲、沉默和单项资源不足不是自动关闭条件。单次存储提交有界尝试不限制主体运行寿命。PAUSE/STOP、权限、事实恢复、防重复执行与计费均未改变。

生产部署、系统服务/自启动、真实外部能力和凭据、正式联系时段/频率/费用政策、生产恢复能力及原 NOT_READY 项保持原边界。本次验收不开放这些能力，不修改 Assistant/Vio，不授权 P19 或 Git 收尾。

## 历史未知的明确保留

| 历史事件 | 仍缺失的原始证据 | 本次处理 |
|---|---|---|
| F1：暂停/恢复后 UNKNOWN / WAITING_VERIFICATION | 当时 ThinkSession 调用阶段、完整原生异常链与系统码 | 原失败和调查保留，原因 UNKNOWN；用户接受无法唯一归因的遗留不确定性 |
| H1：资源等待观察超时 | 清理前活动、可信时间/水位及系统错误现场 | 原失败和调查保留，原因 UNKNOWN；不无依据归因于性能或额度中断 |
| F2：状态保存阶段失败后等待超时 | 当时原生系统错误码及读句柄证据 | 当前读句柄机制已复现修补，但历史该次原因仍 UNKNOWN |

当前可复现机制的修补不构成三者同源证明，也不构成历史唯一归因。它们因用户接受遗留不确定性而不再阻挡本次验收，调查记录本身不删改、不标成 PASS 或“已查明”。

原始入口：[F1 调查](../p18_repair_evidence/full-timeout-investigation.json)、[H1 原失败](../p18_evidence/p18-final-04.json)、[H1 调查](../p18_repair_evidence/h1-investigation.json)、[F2 清理前现场](../p18_r2_evidence/full-resume-01-failure.json)、[定向调查报告](../p18_f1_h1_evidence/investigation-report.md)、[持久化机制调查](../p18_persistence_evidence/investigation.md)。全部历史 FAIL、ERROR、SKIP、辅助错误和未完成运行原样保留，P09 segment 10 的 stderr 缺失与 UNKNOWN 也不变。

## 测试引用与本次检查

下表为监工 2026-09-19 **独立实跑**，本归档轮核对并引用；不是本轮重新运行。耗时列为 unittest 原始汇总，runner 墙钟耗时另见各 result.json。组间有交集，不相加为正式测试总数。

| 独立组 | PASS | SKIP / FAIL / ERROR | unittest 秒 | 原始结果 |
|---|---:|---|---:|---|
| 原六项探针，断言未改 | 6 | 0 / 0 / 0 | 0.679 | [result](independent/original-six-01.result.json)、[stderr](independent/original-six-01.stderr.log) |
| 完整 P18 专项 | 157 | 0 / 0 / 0 | 209.852 | [result](independent/p18-01.result.json)、[stderr](independent/p18-01.stderr.log) |
| 旧恢复、存储及真实进程组合 | 35 | 0 / 0 / 0 | 101.595 | [result](independent/prior-35-01.result.json)、[stderr](independent/prior-35-01.stderr.log) |
| 额外异常边界 | 4 | 0 / 0 / 0 | 0.149 | [result](independent/exception-edges-01.result.json)、[stderr](independent/exception-edges-01.stderr.log) |

四组退出码均为 0；每组 2878 项运行前后快照相同，changed=[]。独立身份与保护核验 [21/21](independent/identity-check.json) 通过。额外独立检查不增加 Engine 正式测试总数。

施工方 2026-09-14 实跑的 [最终全量](../p18_exception_evidence/full-final-01.json) 为 **1517 项：1516 PASS、1 既有 Windows symlink 1314 SKIP、0 FAIL/ERROR，退出码 0**；runner 1384.364 秒，unittest 1383.481 秒。受影响 [公共兼容 605 PASS](../p18_exception_evidence/compatibility-final-01.json)、其他施工组及原命令见 [交付报告](../p18_exception_evidence/final-report.md) 和 [结果索引](../p18_exception_evidence/selected-runs.json)。监工和本归档轮均核验引用这些结果，没有重跑全量。

当前 270 份源码/测试/资源与独立复核及上述六组施工结果的运行前后身份完全一致：

`sha256:e56fcd1d6e2f6d467a708b72866c807eca536fece20af9e881d2a23aba30cfec`

正式测试保持 1517 项：上轮 1507 身份保留，异常链修补新增 10 项。本归档轮新增正式测试 0 项、运行行为测试 0 项。未读取实际远端、未运行或取得 CI，不宣称 CI PASS。

本次实际检查：源码与结果身份、独立原始汇总和退出码、既有成果逐文件 hash、原件/副本 hash、保护与数据、现行状态和编号、文档链接、特定秘密特征扫描及 git diff --check。详细结果见 [终局审计](final.audit.json)。秘密扫描仅核对有限 key 特征，不是穷尽秘密识别；明确标注的 TEST 反例证据保留。四份旧原始日志行尾空白继续保留，不将其误记为新行为失败。

## 档案、保护和未提交成果

已同步 21 份直接相关现行文档，保留其原历史正文；[逐文档清单](documentation-files.json)。独立报告、身份核验、探针、四组完整原始输出与前后清单、进程观察共 26 份原件按明确清单归档，逐文件核对 SHA-256，见 [归档溯源](independent-archive.json)。规划侧原件未修改，归档的审计脚本仅作为证据，没有在本轮执行。

63 项保护文件、三份规划、六份 Schema/冻结外部契约、正式七文件、pyproject.toml、版本 0.1.0、31 个 P10 辅助脚本及一个旧 P14 接续报告保持不变。正式数据树：

`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`

[最终精确待提交清单及 32 项排除清单](final.pending-files.md) 包含全部已有 P18 成果与本次归档增量；[本轮变化](document-changes.json) 与 [修改前现场](before.json) 可逐项比对。此清单不构成暂存或提交授权。

分支 main；本地 HEAD 与本地 origin/main 仍为 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地 ahead/behind 为 0/0。该 SHA 是原基线，不冒称为已验收 P18 的提交；当前 P18 成果尚未提交。暂存区为空，Git index 未变；本轮不启动测试进程，不需清理测试根或子进程。独立复核的 [进程观察](independent/process-observation.json) 仅作为当时快照引用。

验收归档完成后停止，等待用户另行确认提交与 push；P19—P23 不开工。
