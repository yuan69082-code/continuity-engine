# P18 额度中断后续接（2026-09-12）

用户说明：此前因额度用完中断，现在已有额度。本次续接原 P18 实现/测试/档案任务，不重新开工，不是验收或 Git 写授权。由用户转发 Engine，规划侧没有跨任务派单。

执行仓库：`C:/Users/Administrator/Documents/continuity-engine`。

继续遵循已由用户澄清的默认持续运行要求及本目录整合后的 `implementation-brief.md`：没有用户消息、空闲、沉默和单项额度不足不停止整个运行时；资源等待与整体停止分离；正常持续入口与限时测试分离。不要退回 P17，不重复创建 D-072，不进入 P19。

## 本轮只读续接核对发现

规划侧没有运行任何行为测试，也没有修改 Engine。实际读取现有 JSON/原始 stderr 并重算当前源码 hash：

- `docs/project_memory/p18_evidence/p18-final-07.json` 已 FINISHED：64 PASS，0 SKIP/FAIL/ERROR，runner 94.627 秒。
- `docs/project_memory/p18_evidence/full-final-03.json` 已 FINISHED：1424 项，1423 PASS，1 既有 Windows symlink 1314 SKIP，0 FAIL/ERROR，退出码 0，runner 1036.819 秒；2026-09-10 23:21:51（+08:00）完成。原始 stderr 为 `Ran 1424 tests in 1036.097s`、`OK (skipped=1)`。
- 当前 263 个源码/测试/资源文件与以上两次运行的 sourceBefore/sourceAfter 全部匹配，没有增加、缺失或 hash 漂移。因此额度中断不代表最后全量也被中断，无需仅为续接而再跑一次全量。
- `compatibility-scheduler-final-01` 已 110 PASS，12.683 秒；它早于最终 STOP 修补，仅 `src/continuity_engine/services/persistent_runtime_service.py` 与 `tests/test_p18_runtime_recovery.py` 和当前来源不同。该时间差须如实说明，不宣称这次旧兼容在最终全部源码上重新执行；核实其测试身份是否已被最终全量覆盖。
- `full-final-01` 是补强前历史：1417 PASS + 1 SKIP，1121.067 秒。`full-final-02` 是控制器主动中断的 INTERRUPTED 记录，不是完整测试通过或测试失败统计。
- `continuation.md` 最新记录仍停在“正在跑 p18-final-07，再跑 full-final-03”，已落后于实际完成结果。
- `final-report.md` 和 `final.audit.json` 当前均不存在，正式档案收尾尚未交付。
- HEAD 与本地 origin/main 均为 `5a3247a5d23ff17de2b4ba12bc327594b492e725`，本地 ahead/behind 0/0，暂存区为空；逐文件 Git 查询为 21 个 tracked 修改、165 个 untracked 文件。本轮未查询远端。
- 正常主机权限下仅只读筛选 Python 命令行中 `p18_evidence|p18_runtime|persistent_runtime|test_p18`，未发现匹配进程；这是有范围的进程观察，不是检查所有系统进程，也未终止任何进程。首次受限查询拒绝访问，不能将其空结果当作无进程依据。

辅助工具说明：首次 Git 数量汇总误用了 PowerShell 的 `??*` 通配符且未展开未跟踪目录，已弃用该统计；上面 21/165 来自独立的 `git diff --name-only` 和 `git ls-files --others --exclude-standard`。Git 输出了现有 LF/CRLF 提示，未修改文件。这些不是 Engine 行为测试失败。

## 接下来执行

1. 先读当前 Stage Brief、continuation、以上最终原始记录和实际相关脚本，再重新只读确认当前来源、进程与 Git 现场。保持已有成果、原 before.json、失败证据及排除材料，不新造开工基线，不盲目使用旧 exec session 或重启已完成测试。
2. 以上最终结果若仍完整且源码身份相同，接续档案收尾：检查现有 finalize.py/audit.py 的输入和覆盖行为后再使用，更新真实阶段进度、架构/控制/资源等待语义、矩阵、测试历史与复跑入口，生成完整报告、终局审计、逐文件/排除清单和进程清理说明。旧标签不覆盖；新审计若失败，另留唯一标签记录。
3. `p18-final-04` 的资源等待进程超时根因此前仍为 UNKNOWN。保留原失败、可用诊断及“清理前观察被 STOP 覆盖”的限制；不能因为单项、专项和最终全量后来通过就把原因写成已解决。资源公平性和 STOP 终态修复的因果范围分别记录，不能无证据拿它们解释原超时。EVIDENCE_CONFLICT 保持 PRESENT 交独立复核，不能为了档案全绿删证据、改超时阈值或重写原断言。
4. 仅档案变化且代码与最终运行匹配时，不再修改行为代码或机械重跑专项/全量。若发现实际新失败、代码漂移或结果不完整，明确列出依据和所需工作，再在原授权范围内进行必要处理；涉及扩范围须先询问用户。不得只因额度中断就清空现场从头运行。
5. 核对原 1360 项身份保留、P18 新增 64 项计数以及各测试来源；SKIP 不算 PASS，施工记录不冒充独立复核或远端 CI。核对 63 项保护、三份规划、正式七文件/数据树、冻结契约、版本/pyproject 及原 32 个排除项；不改 Assistant。
6. 交付 P18 的实际实现、正常持续入口/控制方法、无消息运行及局部资源等待证据、用户待定正式政策、已知 UNKNOWN/NOT_READY、精确清单、完整 Git 状态和独立可复跑命令。完成后保持 IMPLEMENTED_NOT_ACCEPTED，D-073 不创建，不暂存/commit/push，不进入 P19。

本次只完成原施工任务的剩余收尾并交回独立复核。用户此前 P17 的验收与 push 授权不延用到 P18。
