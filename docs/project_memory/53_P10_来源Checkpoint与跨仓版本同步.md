# P10 来源 Checkpoint 与跨仓版本同步

> P10 现行门：P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。 D-056 与最终依据见 [最终复核及验收记录](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md#p10-accepted)。Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`；Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`；[CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 为 794/794 PASS、0 SKIP、0 FAIL。历史 FAIL、SKIP、旧 CI failure、辅助错误及 P09 segment 10 stderr 缺失/根因 UNKNOWN 原样保留。

| 项目 | 固定值 |
|---|---|
| 已验收 upstreamCoreCommit | `9d58b427ffaca2e64a268640979337e4c759d49d` |
| Engine 来源 | `C:/Users/Administrator/Documents/continuity-engine` |
| Engine main / origin/main | 上述固定 C1，开工 0/0 且干净；P10 不提交或推送 Engine main |
| Engine checkpoint 分支引用 | `continuity-assistant-fenzhi`，固定指向上述 C1 |
| Assistant 独立本地仓库 | `C:/Users/Administrator/Documents/continuity-assistant` |
| Assistant 工作分支 | `continuity-assistant-fenzhi` |
| Assistant 独立远程 | [yuan69082-code/continuity-assistant](https://github.com/yuan69082-code/continuity-assistant)，PRIVATE |
| 版本与许可证 | Engine/Core 0.1.0；Assistant 骨架 0.1.0；不新增开源许可证，保留原来源/版权/依赖声明 |

用户确认的 C1 来源是 P09 验收后自行提交并 push 的新事实；D-054 当时的“尚未提交/稳定 SHA 待定”作为历史保留。不能使用 P08 的 `fb8713…` 或其他后续 Human-like Subject 提交冒充共同祖先。

## 已执行的派生方式

1. 只读确认目标目录、同名 Engine 分支及私有远程均不存在。
2. `git branch continuity-assistant-fenzhi 9d58b427ffaca2e64a268640979337e4c759d49d`，不切换 Engine main。
3. `git clone --no-local --single-branch --branch continuity-assistant-fenzhi --config core.autocrlf=false <Engine> <Assistant>`；保留完整 27 个提交，独立 `.git` 和对象数据库，不使用 worktree/alternates，不复制未跟踪工作区内容。
4. 新仓 origin 改为指定 Assistant URL；通过已登录 GitHub 账户创建 PRIVATE 空仓库，不自动创建 README/许可证等无关祖先。

原始操作见 [建仓日志](p10_evidence/start-2026-09-04/repository-creation.jsonl)。初始化提交/推送及 Assistant 最终 HEAD 完成后在 [54](54_P10_测试索引与验收入口.md)追加实际证据，不预填 SHA。

## 可复核的祖先关系

在 Assistant 或其远程干净克隆中执行：

```powershell
git cat-file -t 9d58b427ffaca2e64a268640979337e4c759d49d
git merge-base --is-ancestor 9d58b427ffaca2e64a268640979337e4c759d49d HEAD
git diff 9d58b427ffaca2e64a268640979337e4c759d49d -- src/continuity_engine tests
git rev-parse --is-shallow-repository
```

对原建仓提交，要求分别为 commit、退出码 0、空差异、false。当前授权补丁使工作区差异非空；旧来源门仍保留，不将非空差异记录为旧 C1 逐字节一致。Assistant `docs/assistant/core-source-manifest.json` 保留 187 个原 Core/测试文件逐项 SHA-256，并与原 Git blob 再比较。用户禁止 tag/release，明确分支引用、固定 SHA 与来源元数据共同构成 checkpoint。

## 后续版本同步规程（本轮未执行）

两仓分别维护；不自动跟随 Engine main，不重新合仓。未来共享变更先取得针对具体上游 SHA/范围的授权，比较已登记版本并复核 Authority、Schema、恢复、许可和数据边界，再选择可审计 cherry-pick、merge 或版本化共享包。分别运行两仓回归，保存失败，记录来源 SHA、双方 HEAD、测试与用户决定后才更新 source manifest/upstreamCoreCommit；Git 操作仍须对应授权且每次 push 前核实 Assistant remote。

P10 不改变 Engine 的 Human-like Subject 目标，不引入未来产品功能，不接 Vio/真实 Provider/生产 Adapter，不扩大 E5-A 或增加 Authority/账本。Assistant 的 `.assistant-data` 只是独立配置中保留的目录，P10 不创建正式主体或 Runtime。


## 首次推送后的固定记录

Assistant HEAD：`c6dd2c0cab17337a445b64fb8611d317190242c6`，直接父提交 `9d58b427ffaca2e64a268640979337e4c759d49d`。13 个初始化文件，真实提交并首次推送到指定 PRIVATE 仓库及分支；默认分支相同。远程干净克隆的 HEAD 与 merge-base 已实测匹配。原始 Git 操作与后续克隆/CI 测试见 [54](54_P10_测试索引与验收入口.md)。本轮没有标签或发布，也没有 Engine main 提交、推送或历史改写。


**验收布局与未修反例：** 原 P08 FakeActionAdapter 只接受 OS Temp 后代，其测试假设源码 checkout 在 Temp 外。首个 Temp 内克隆触发反例并生成空 TEST 回执，原样保留；另在 `C:/Users/Administrator/Documents/continuity-assistant-p10-clean-20260904` 克隆同一远程/提交验证。布局变更不是 Core 修复，EVIDENCE_CONFLICT=PRESENT 待独立判断，详见 54。没有因此改变 C1 来源、追加提交或推送。

## P10 授权 P08 Fixture 路径返修（2026-09-04）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT：本地路径反例已修复并验证，原 P10 来源/数量门保留失败，补丁尚待新 checkpoint、远端验证与独立复核。

用户本次仅授权同步修复 `src/continuity_engine/testing/p08_action_fixture.py`，新增 `tests/test_p08_fixture_paths.py`，两仓字节一致。共享只读 guard 在 Fake 回执与 P08 上游 Fixture 初始化前执行；检查 Temp 范围、源码/当前/目标仓库、正式目录及显式 formal_data_roots/protected_paths 的祖先/后代重叠，保留链接/重解析点拒绝，独立 Temp Fixture 仍合法。原 770 项断言均保留，新增 18 项单列；未修改生产业务、Authority、E5-A 或账本。

旧 C1 `9d58b427ffaca2e64a268640979337e4c759d49d` 与首次 Assistant 提交 `c6dd2c0cab17337a445b64fb8611d317190242c6` 保持原父子关系；当前补丁是两仓未提交成果，不得声称修改后的 Core 与旧 C1 逐字节相同。旧 core-source-manifest / upstreamCoreCommit、P10 test_02 / test_04、CI 配置和 harness 均未改。新 checkpoint 最终 SHA、提交后来源验证、远程干净克隆与新 CI 等待用户另行授权 Git 操作。本轮未执行 Git 写操作。旧远程 CI 仅证明旧提交。

本次真实数量、耗时和全部首次失败见 [54 本次返修记录](54_P10_测试索引与验收入口.md)。原 Temp 克隆 770 项两个 subTest FAIL（448.707 秒）、两份空 TEST 回执及全部历史证据原样保留。本次红灯输出独立保存，未覆盖旧失败；实际 Temp 模块导入和保留失败克隆上的拒绝均检查零写入，没有用 Temp 外通过替代 Temp 内验证。P09 segment 10 stderr 缺失、根因 UNKNOWN 不变。本轮环境依赖查询曾发现未单独安装 wheel 包；setuptools 83 的既有构建后端实际离线构建结果另列，该查询不是 Engine 回归失败。首次来源清单辅助审计误把既有 CRLF/LF 表示差异当成变更，原 FAIL 报告保留；只修正该辅助审计，清单和原来源断言不改。见 [辅助观察及字节证据](p10_evidence/fixture-repair-20260904/helper-observations.md)。 首次离线安装命令 exit 0 但因 PYTHONPATH=src 中的构建元数据误判而跳过，随后安装包导入实际 ModuleNotFoundError 已保存。只清除安装环境源码路径并在仓库外重新安装既有 wheel，导入及补丁 hash 通过；未改 Core、未重建 wheel、未追加全量。符号链接单项另以 verbose 保留实际 WinError 1314 原因。

## P10 TEST Fixture Windows 大小写定点返修（2026-09-04）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT：本轮真实 Windows 大小写阻断已最小修复并完成本地回归，仍须独立复核，不能表述为只剩 Git 授权；旧来源门与新 checkpoint / 远端 CI 另行后置。

仅在两仓 `src/continuity_engine/testing/p08_action_fixture.py` 将 `parent.name == name` 改为 `Path(parent.name) == Path(name)`，加一条解释注释。使用原生平台路径比较：Windows 不因名称大小写变化放行，POSIX 保留其路径拼写规则；未全局无条件小写化。只在原 `tests/test_p08_fixture_paths.py` 追加 6 个测试方法，覆盖大写、混合大小写、目录本身/子目录、两个入口、实际 samefile 别名与小写对照；同时核对拒绝、写入调用为零、完整目录/文件内容清单不变。32 个 Windows 子场景包含原 24 个失败场景与 8 个小写对照。前轮 18 项和既有所有断言原样保留，现有路径定点共 24 项。Linux 分支保留对应合法大小写不同路径测试，但本轮只实跑 Windows，不声称已完成 Linux/远端 CI。

旧 C1 `9d58b427ffaca2e64a268640979337e4c759d49d`、首次 Assistant `c6dd2c0cab17337a445b64fb8611d317190242c6`、共同祖先、原 core-source-manifest/upstreamCoreCommit 及 P10 严格检查全部保持。当前工作区已包含两轮授权 TEST 补丁，不是旧 C1 字节副本。本轮没有重建 wheel、重跑 P10 工程套件或执行远端 CI；旧 788/770 来源门失败、旧 wheel/CI 均属当时记录，不能冒充当前补丁结果。新 checkpoint 最终 SHA、提交后来源验证与新远端 CI 等待另行 Git 授权，本轮未执行暂存、提交、推送、合并、变基、标签或发布。

保留前轮所有 76/788、红灯/辅助错误/安装跳过记录和更早 P08/P09 历史，包括 segment 10 stderr 缺失、根因 UNKNOWN。前轮“路径反例已修复”只能覆盖其当时验证范围，本次独立发现的大小写漏项及修复前 24 个失败子用例不得归为仅待 Git，也不被后续 PASS 倒写。

独立原失败、本次红灯/修复/回归数字和最终核查分别见 [54 本轮记录](54_P10_测试索引与验收入口.md)。

## P10 两仓 Git 收尾首次验证失败（2026-09-05）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT：两仓 checkpoint 已提交推送，当前 Assistant 本地及 CI 的新统计入口在测试导入阶段失败，尚未完成当前 Core 全量、Temp 内干净克隆及最终独立复核。

Engine 两文件测试 checkpoint `0115733d75f854e0d7c39062d8cb328a97995354` 已推送；Assistant 保存原成果并真实合入该 checkpoint，提交 `664530c2c6faae7f37dd90bc73463d8dfb66b490` 已推送至原私有分支。原 C1/首次初始化历史保留，当前 188 文件来源和原 770 + 新增 24 身份校验通过。当前本地/CI 的构建、安装、导入、P10 12 项及 Golden 通过；本次新增统计入口在测试导入阶段失败，794 项未执行。按用户停止条件未继续修复、克隆、验收或档案提交。正式数据、冻结边界和版本不变。全部命令、耗时、Git 范围、首次失败及待办见 [停止报告](p10_evidence/closeout-20260904/STOPPED_REPORT.md)。历史 segment 10 stderr 缺失、根因 UNKNOWN 保留。

## P10 统计入口返修与当前提交验证（2026-09-05）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（当前验证已通过，等待最终规划监工独立核对）。

Assistant `90f112b8be4617feb2d6387ceb2f77603302cee6` 已仅提交并推送统计入口和两项工程启动回归；Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354` 未重做，来源元数据、Core、原测试及冻结文件均未改。快速发现零导入错误、770 + 24 身份精确匹配；修复工作区、当前提交 Temp 内干净克隆、当前真实 CI 均通过构建/安装/导入/Golden、14 项工程及 Core 794 验证。PASS/SKIP、时间、原始输出、历史辅助失败、Git 明确范围及待独立核对事项见 [最终复核报告](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md)。当前不是用户已验收，D-056 未登记。

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
