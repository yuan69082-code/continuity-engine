# P15 R1/R2/R3 返修独立复核：通过，等待用户正式验收

复核日期：2026-09-09。对象为 Engine 当前工作区，基线 HEAD 为 `f1185d20da06f52e7e85015bc6b963cf9769d08c`。

## 结论与授权边界

本轮独立复核未发现新的阻断问题；原 P15-R1、R2、R3 在本次检查和实跑覆盖范围内已闭合，可交用户正式验收。该结论不是保证软件不存在其他缺陷，也不替代尚未建设的生产认证、备份恢复或删除政策。

本报告只记录规划侧独立结论。没有修改 Engine 源码、测试或档案，没有发送跨任务指令，没有登记 D-067，没有执行暂存、提交、push，没有修改 Assistant，也没有进入 P16。Engine 当前仍是 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT；正式验收及状态归档等待用户授权后，由用户转发提示词给施工任务完成。本报告可作为关闭原独立复核阻断的证据，不自动改写 Engine 状态。

## 本次真正独立运行的测试

| 验证 | 结果 | unittest 耗时 | runner 耗时 |
| --- | --- | --- | --- |
| 原有效 8 项探针，原文件及断言未修改 | 8 PASS，0 SKIP/FAIL/ERROR | 9.457 秒 | 10.413 秒 |
| 完整 P15 专项（含原探针的正式回归副本） | 71 PASS，0 SKIP/FAIL/ERROR | 199.876 秒 | 200.922 秒 |
| 新增独立边界与正向对照 | 8 PASS，0 SKIP/FAIL/ERROR | 25.741 秒 | 26.686 秒 |
| 源码、证据、保护范围与 Git 身份核对 | 21 项全部通过 | 非行为测试 | 不计入测试总数 |

原 8 项探针已经包含在正式 71 项中，不能相加冒充互不重复的覆盖。新增独立 8 项仅位于规划工作区，不增加 Engine 正式回归的 1208 项统计。

每轮测试均由规划侧 runner 启动，工作目录为 Engine；所有状态损坏、撤权和中断注入只针对隔离 TEST Fixture。每轮执行前后快照中的 Engine 1757 个文件均完全一致，没有 Engine 文件增删改。

## 修复核查

### R1：生命周期当前值与原 Evolution 历史一致

核对入口：`C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_repository.py` 的 `_validate_history`（171 行）及 `_advance_lifecycle`（209 行）。读取和写入均校验当前生命周期与原管理命令、mutation/change、主体、环境、Owner、revision 和合法状态转换；不是仅凭当前字段判断 ACTIVE。

原两个反例——暂停后丢失字段、删除后覆盖旧 ACTIVE 片段——均拒绝；真正旧格式、普通同名旧 Event、合法暂停恢复和历史重放仍可用。新增独立测试确认命令 revision 漂移零写入拒绝，以及主体暂停意图在 Owner 暂停/恢复后仍可原事实重放，不改变当前状态。

修复过程中曾错误地强制生命周期 Port 时间不晚于 Evolution Port 时间；施工方已去除此额外假设，保留自身历史时间及命令绑定。第一次专项 1 ERROR 和后续单项/稳定专项结果均保留，原兼容测试未修改。

### R2：准备、真实提交、终止替换分开记录

核对入口：`C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/subject_growth_service.py` 的 `_submit`（112 行）、`_preparation_event`（214 行）、`_actual_fact`（229 行）、`_finish_record`（247 行），及 Learning 类型、服务和原仓储的 resolution 交叉校验。

新准备记录为 GROWTH_PREPARED。SOLIDIFY 在 Evolution 前不激活 Trait；ROLLBACK 在实际提交前保留原贡献。已提交判断仍核对原 Evolution Event 与变化，不把 Learning 摘要当成第二权威。新的合法确认可在当前 revision 终止未提交旧命令并继续；旧命令和后来无关状态均保留。

原“中断后出现无关新状态，重新确认仍无法固化”探针通过；正式测试覆盖 SOLIDIFY/ROLLBACK、旧格式、权限及来源撤销、替换后中断、事实缺失拒绝。新增独立测试另确认：

- 已完成回滚后重放最早固化命令，只返回原事实，不复活旧 Trait，零写入。
- 回滚已提交但审计未完成时中断，之后撤权仍可完成原事实恢复；再次重放零写入，不再次推进主体 revision。
- 替换记录已落盘但新准备尚未写入时中断，同一新命令 ID 不能换内容；原合法命令仍可继续，后来无关值保留。
- 准备之后、Evolution 之前撤权，主体状态不改变、待固化 Trait 不激活；重新取得明确确认后才完成。

### R3：成长详情返回前重验当前状态与权限

核对入口：`C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/mind_projection_service.py:49` 的 `read_growth`。

出口重读完整状态 hash，核对 subject/environment/Owner/可见性策略绑定，再重查当前身份、Permission 与 export。原读取途中撤权反例通过；正式测试覆盖 EXPIRED、revision 变化、同 revision 内容变化、export 撤销和合法零写入观察。新增独立测试确认读取途中可见性从 DETAILED 改为 SUMMARY，或 Owner 绑定变化，均拒绝交付旧详情且观察不写状态。

## 施工方全量证据核对（引用，不冒称独立重跑）

当前 232 个源码/测试/资源文件逐文件 hash，与施工方 independent-stable、targeted-stable、p15-stable、compatibility-final、full-final 的执行前后及 final.audit 全部一致。原始 stderr 的运行项数和结束结果与 JSON 逐一一致，测试身份无重复、无遗漏、无导入错误。

- 原探针：8 PASS，10.804 秒。
- 定点与对照：32 PASS，86.372 秒。
- P15：71 PASS，181.709 秒。
- 受影响兼容：293 PASS，212.998 秒。
- 全量：1208 项，1207 PASS、1 SKIP、0 FAIL/ERROR，1024.585 秒。

本次未机械重跑整套全量，也没有远程 CI PASS 声明。唯一 SKIP 为既有 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`，原因 `OS does not grant symlink creation: 1314`，没有计作通过。

原 1176 项测试身份和所有原测试文件未变；正式新增 32 项。原独立材料 11 文件、Engine 中的逐字节副本、原 P14/P15 历史证据均未变化。原有效 4 FAIL、首次辅助 Fixture ERROR、施工阶段中间失败及第一次完整 P15 的 1 ERROR 均保留，后续通过没有覆盖历史。

## 保护范围与 Git

独立检查全部通过：63 项保护文件、三份规划、正式七文件及树指纹、31 个 P10 排除脚本均未变。当前 222 个 Python 文件语法解析通过。源码增量严格为批准的六个实现文件与两个新增测试文件；没有改原测试断言。暂存区为空，`git diff --check` 通过。

- 分支 `main`。
- HEAD 与本地 `origin/main` 均为 `f1185d20da06f52e7e85015bc6b963cf9769d08c`；本地 ahead/behind 为 0/0。本次没有查询实际远端。
- 37 个已跟踪修改、213 个未跟踪文件，共 250 个路径。
- P15 精确成果 218 文件；其余为 31 个原 P10 脚本与 1 个旧 P14 接续报告。清单和 217 项已记录文件 hash 匹配；审计文件自身不自我 hash。
- 正式数据树指纹仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

## 证据与复跑入口

规划工作区：`C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity`。

本报告同目录保留：

- `repair-original-probes-20260909-01.{before.json,after.json,result.json,stdout.log,stderr.log}`。
- `repair-p15-20260909-01.{before.json,after.json,result.json,stdout.log,stderr.log}`。
- `repair-extra-probes-20260909-01.{before.json,after.json,result.json,stdout.log,stderr.log}`。
- `p15_repair_review_probe.py`：新增独立 8 项的完整代码。
- `verify_repair_evidence.py` 与 `repair-identity-check-20260909.json`：独立 21 项检查。
- `repair_final_check.py` 与 `repair-final-check-20260909.json`：报告形成后的 Engine 文件终检。初次终检单行辅助命令误从 runner 顶层导入 `snapshot` 导致 ImportError；实际入口为 `base.snapshot`，纠正后单独核对。此为规划侧辅助调用错误，没有运行或改变 Engine，不计为业务测试失败；原错误文字保留在该 JSON 中。
- 原 `review-report.md`、`p15_review_probe.py` 及原失败日志保持不变。

在规划工作区运行以下命令，必须给 runner 使用新的唯一标签，不能覆盖本报告已引用证据。环境由 runner 设置，写盘仅在规划报告目录和临时 TEST Fixture。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:\Adobe\python.exe' 'reviews/p15-independent-review-20260908/run_review.py' '<新的唯一标签>' -m unittest -v p15_review_probe
& 'E:\Adobe\python.exe' 'reviews/p15-independent-review-20260908/run_review.py' '<另一个新的唯一标签>' -m unittest discover -s tests -p 'test_p15*.py' -v
& 'E:\Adobe\python.exe' 'reviews/p15-independent-review-20260908/run_review.py' '<第三个新的唯一标签>' -m unittest -v p15_repair_review_probe
```

最终建议：由用户决定正式验收；确认后再登记验收决定、同步状态与证据并按重新核对的精确清单收尾。没有得到新的明确授权前，不提交、push 或进入 P16。
