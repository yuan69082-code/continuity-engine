# P10 Assistant 建仓架构与 Stage Brief

> P11 现行门：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-058 已登记用户正式验收。监工独立原反例 2/2 PASS、P11 45/45 PASS（8.371 秒）；39/833 全量等修复前结果继续作为历史保留。本次仅验收归档，不运行全量。[P11 验收入口](58_P11_测试索引与验收入口.md#p11-accepted)。

日期：2026-09-04。用户已授权 P10 实际建仓和限定 Git 操作。开工决定见 [D-055](04_决策记录.md#d-055)。本页开工事实不代表实现完成或用户验收。

| Stage Brief 字段 | 本轮依据与边界 |
|---|---|
| STAGE | P10 Continuity Assistant 实际分支与独立仓库初始化；P00—P09 已 ACCEPTED，P11—P23 NOT_STARTED |
| SOURCE OF TRUTH | 真实源码/测试、D-054、本次用户授权；固定 C1 `9d58b427ffaca2e64a268640979337e4c759d49d`；三份 2026-08-26 同步规划 |
| ORIGINAL REQUIREMENTS | v1.1 P10 正文：实际分支、独立仓库及推送；upstreamCoreCommit、README、模块边界、构建、最小 CI、兼容回归与版本同步；干净远程克隆可构建/测试且保留真实共同祖先 |
| V6.7 DETAILS | P10 正文及附录 E：已验收 C1 是派生点；共同能力以后显式跨仓同步；不反向删除后续 Human-like 能力来制造来源；不提前开发完整 Assistant 产品 |
| AMENDMENT OVERRIDES | 两规划六项 Override 与 2026-08-26 覆盖已读：Direct/Optional Planner、宿主中立 Reality Port、Engine Runtime 所有权及阶段门均保持；旧“不实际 Fork/继续等待”无效；P10 不依赖 Vio |
| KEEP RULES | 八项 Keep 已读：唯一 SubjectState/事实 Authority、合法 Evolution/revision、P01 测试恢复限定、简化 C1 情绪、测试身份/数据隔离、必要结构 Trace 且无隐藏思维链；保留 Human-like Subject 主线目标 |
| DEPENDENCIES | D-054 正式验收；187 源码/测试与验收清单一致；开工 main/HEAD/origin/main 固定、0/0、工作树/暂存区干净；本次实际全量 770/770 PASS（unittest 487.094 秒，进程墙钟 487.927 秒） |
| NOT READY | Assistant 产品能力、生产 Runtime/Adapter、Task/Goal/Workflow/Calendar/Mail/Device、P11—P23；P10 实现仍须独立复核与用户验收 |
| FILES ALLOWED | Assistant 独立仓库初始化、包/配置/构建/CI、独立 P10 检查和说明；Engine 必要 P10 档案与指定分支引用 |
| FILES FORBIDDEN | Engine 运行源码、原测试、六份冻结 Schema、外部接口/契约、正式数据、规划源、pyproject/0.1.0、main 提交与历史；Vio 与真实 Provider/生产 Adapter |
| TESTS REQUIRED | 开工全量；Assistant 本地及其远程干净克隆的构建/安装/原 770 项回归；新增 P10 检查单列；真实最小 CI；祖先、数据/秘密、Git 元数据/配置隔离、Engine 不变项与档案检查 |
| PLANNING CONFLICT | 开工已读范围未发现实质冲突。用户指定分支名覆盖建议名；用户禁止标签，使用固定提交和分支引用建立 checkpoint。环境或权限阻断另行如实登记，不据此扩大授权 |

## 规划原文和开工证据

只读解析了三份 DOCX 的正文及表格：v1.1 P10、统一十项验收门、Architecture Amendment v4/Keep 及最终同步；v6.7 P10、附录 C/E；Assistant v0.1 全文。原文件名、逐文件 SHA-256、187 源码/测试、25 项冻结边界、正式 7 文件及开工 Git 状态保存在 [修改前清单](p10_evidence/start-2026-09-04/engine-before.json)。规划源未重新保存。

实际开工命令 `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 python -m unittest discover -s tests -q`。见 [结果](p10_evidence/start-2026-09-04/engine-baseline.result.json)、[stderr](p10_evidence/start-2026-09-04/engine-baseline.stderr.log)、[stdout](p10_evidence/start-2026-09-04/engine-baseline.stdout.log)。不是 P09 历史 770 项结果。

固定 C1 的 27 个提交、953 个唯一文件对象已检查：未发现正式数据/缓存历史路径或所检查的高特异性秘密签名；此扫描不等于对所有可能秘密的数学证明。见 [历史扫描](p10_evidence/start-2026-09-04/history-scan.json)。只继承版本化源码、合成 Fixture 与脱敏工程证据，不复制工作区正式数据、未跟踪文件、Sandbox、缓存或活动 Runtime。

## 初始化设计

Engine 指定分支引用保持在固定 C1；Assistant 通过完整历史独立 clone 派生，有自己的 `.git`，不使用 worktree 或对象 alternates。Assistant origin 只指向 `https://github.com/yuan69082-code/continuity-assistant.git`，每次推送前重新核实。远程 PRIVATE，不自动初始化 README/许可证，不创建标签/Release。

继承 `src/continuity_engine` 和 `tests`，保留全部原测试。独立 Assistant 包仅提供来源/配置检查入口，默认 Runtime 关闭，数据目录为 Assistant 仓库内 `.assistant-data`，不继承 Engine 数据目录环境变量。P10 不创建正式主体或新 Authority/账本，不扩展 E5-A；验证只使用原 Fixture/Fake 和独立临时根。幂等证据仍限于已验证本地 Fake，不能宣称生产 exactly-once。

## 历史与当前的区分

D-054 及 P09 原 40/740、56/756、70/770、全部失败/中断/辅助错误原样保留。历史 segment 10 stderr 缺失、根因 UNKNOWN 不变。用户后续提交并 push 后，本次核定的稳定 C1 是 `9d58b427ffaca2e64a268640979337e4c759d49d`；这是新事实，不倒写旧档案当时的“尚未提交”。D-056 保留给未来用户正式验收，本轮不创建、不使用。

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

## P10 统计入口返修与当前提交验证（2026-09-05）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（当前验证已通过，等待最终规划监工独立核对）。

Assistant `90f112b8be4617feb2d6387ceb2f77603302cee6` 已仅提交并推送统计入口和两项工程启动回归；Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354` 未重做，来源元数据、Core、原测试及冻结文件均未改。快速发现零导入错误、770 + 24 身份精确匹配；修复工作区、当前提交 Temp 内干净克隆、当前真实 CI 均通过构建/安装/导入/Golden、14 项工程及 Core 794 验证。PASS/SKIP、时间、原始输出、历史辅助失败、Git 明确范围及待独立核对事项见 [最终复核报告](p10_evidence/launcher-repair-20260905/REVIEW_REPORT.md)。当前不是用户已验收，D-056 未登记。

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
