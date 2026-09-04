# P10 当前提交验证与独立复核报告（2026-09-05）

P00—P09 ACCEPTED；P10 / Engine side / P10-01—P10-12 IMPLEMENTED_NOT_ACCEPTED；P10 Vio dependency NONE；P11—P23 NOT_STARTED；D-056 未创建、未使用。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（当前验证已通过，等待最终规划监工独立核对）。

本报告供最终独立核对。用户已一次性授权本轮限定 Git 收尾及条件式验收，后续明确授权统计入口的局部修复；无需重新申请同一范围 Git 或验收授权。只有规划监工对最终提交、来源关系和证据核对通过后，条件式验收才满足。本报告不自行登记 ACCEPTED，也不预先登记 D-056。

## 当前仓库和真实来源

| 项目 | 实际值 |
|---|---|
| Engine 路径 / 分支 | C:/Users/Administrator/Documents/continuity-engine / main |
| Engine HEAD、origin/main、实际远端 main | `0115733d75f854e0d7c39062d8cb328a97995354`，三者一致，ahead/behind 0/0 |
| Engine 远端 | https://github.com/yuan69082-code/continuity-engine.git |
| Assistant 路径 / 分支 | C:/Users/Administrator/Documents/continuity-assistant / continuity-assistant-fenzhi |
| Assistant HEAD、本地 upstream、实际远端分支 | `90f112b8be4617feb2d6387ceb2f77603302cee6`，三者一致，ahead/behind 0/0 |
| Assistant 唯一 origin | https://github.com/yuan69082-code/continuity-assistant.git，PRIVATE 不变 |
| upstreamCoreCommit / 测试修复 checkpoint | `0115733d75f854e0d7c39062d8cb328a97995354` |
| 原已验收 C1 | `9d58b427ffaca2e64a268640979337e4c759d49d` |
| 首次 Assistant 初始化 | `c6dd2c0cab17337a445b64fb8611d317190242c6` |
| 本次远端 Temp 内干净克隆 | `C:\Users\Administrator\AppData\Local\Temp\p10-final-g0vhsy2o\repo`；HEAD `90f112b8be4617feb2d6387ceb2f77603302cee6`；独立完整 .git、非 shallow、无 alternates |

新 checkpoint 的直接父提交为原 C1，且只包含已独立复核的两份 TEST 文件。首次 Assistant 初始化的直接父提交仍为原 C1。来源合并提交 `664530c2c6faae7f37dd90bc73463d8dfb66b490` 保留 Assistant 已保存成果及 checkpoint 两条父历史。当前统计入口修复是其直接后继，不重新制造 checkpoint、合并或首次初始化；旧 C1、首次初始化、新 checkpoint 均为当前 Assistant 的真实祖先，merge-base 均返回相应 SHA。

当前 Core 及 tests 完整 188 文件集合/逐文件 hash 与 checkpoint Git blob 一致；全部原测试文件未变。原 187 文件清单另存，仍与首次 Assistant 提交精确一致。原 770 项和新增 24 项身份各自完整、去重后精确合计 794。既有严格来源、祖先、文件集合、hash 和身份断言保留，没有放宽阈值或删除失败模块。

## 本次最小修复及 Git 操作

仅修改 Assistant：

- `tools/p10_core_regression.py`：脚本启动时在发现前显式加入该 checkout 的仓库根和 src，保持原 unittest 导入上下文；保留 loader.errors 和精确身份断言。新增只发现模式仍先执行两项原校验，输出零导入错误、完整身份和实际模块来源，不执行 Core 用例。
- `p10_tests/test_p10_core_launcher.py`：新增两项工程回归，在仓库外、无 PYTHONPATH 及隔离解释器模式启动实际脚本，验证 770 + 24 身份和实际 repo/src 模块来源；独立临时工作目录无写入。

没有修改 tools/p10_verify.py、Core、原测试导入语句、来源元数据、清单、冻结契约、pyproject 或版本。两文件最终 hash 见 [稳定修复](stable-repair-v2.json)。完整本地流水线先通过，然后明确暂存这两个文件、提交并推送；[真实提交/推送摘要](published-repair.json)以及 repair-stage / repair-commit / repair-push 的 json/stdout/stderr 保存所有命令、退出码和耗时。

| 历次提交 | 文件范围 / 推送目标 |
|---|---|
| Engine `0115733d75f854e0d7c39062d8cb328a97995354` | 仅 src/continuity_engine/testing/p08_action_fixture.py、tests/test_p08_fixture_paths.py；Engine origin main:main；此前已完成，本轮未重做 |
| Assistant `2b1e500d9a5becde127f6c60d272def49bfc2e13` | 保存原 README、边界/两份返修说明、上述两 TEST 文件，共 6 项；此前随来源合并一起推送 |
| Assistant `664530c2c6faae7f37dd90bc73463d8dfb66b490` | 真实合并 checkpoint，来源/工程/文档 10 文件；原 Assistant origin 指定分支；[完整清单](../closeout-20260904/assistant-sync-files.json) |
| Assistant `90f112b8be4617feb2d6387ceb2f77603302cee6` | 本轮仅上述统计入口与新增工程回归两文件；原 PRIVATE Assistant origin，continuity-assistant-fenzhi:continuity-assistant-fenzhi |

每次推送均先核对目标和实际远端无分叉。没有 git add .、强推、变基、重置、改远端、改分支名、改可见性、标签或发布；没有将 Assistant 专属内容反向合入 Engine。Engine 验收档案尚未提交，须等待独立核对满足条件后另列清单提交。

## 当前修复的真实验证

本地完整结果对应提交前工作区：当时 HEAD `664530c2c6faae7f37dd90bc73463d8dfb66b490`，两份已测试文件 hash 与随后提交 `90f112b8be4617feb2d6387ceb2f77603302cee6` 精确一致。该本地结果不冒称提交后的运行。远端 CI 和 Temp 克隆则实际运行 `90f112b8be4617feb2d6387ceb2f77603302cee6`。当前 wheel 均在各自本次流水线重新构建安装，未使用旧提交的 wheel 或 CI 结果。

| 检查 | 本地修复工作区 | 当前提交 Temp 克隆 | 当前提交远端 CI |
|---|---|---|---|
| wheel 构建 | PASS / 4.653 秒 | PASS / 5.202 秒 | PASS / 5.881 秒 |
| 安装 | PASS / 2.238 秒 | PASS / 2.305 秒 | PASS / 11.097 秒 |
| 仓库外已安装包导入/资源 | PASS / 0.821 秒 | PASS / 0.800 秒 | PASS / 4.451 秒 |
| 已安装包 Golden | PASS / 4.194 秒 | PASS / 4.146 秒 | PASS / 10.985 秒 |
| P10 工程检查（原 12 + 新增 2） | 14 PASS / 15.516 秒 | 14 PASS / 16.678 秒 | 14 PASS / 33.854 秒 |
| Core 全量（合计 794） | 770 原项 PASS；新增 23 PASS / 1 SKIP；405.439 秒 | 770 原项 PASS；新增 23 PASS / 1 SKIP；402.846 秒 | 770 原项 PASS；新增 24 PASS / 0 SKIP；869.300 秒 |

以上 SKIP 单独记数，不属于 PASS。原 770 项在三处均全部执行并通过；新增 24 项中每个实际 SKIP 的身份和原因详列 core-results.json。Windows 本地已观察到的 SKIP 为既有 symlink 创建权限 WinError 1314；真实 junction 用例未跳过。P10 14 项与 Core 794 项分开统计，未增加无记录的跳过。

原始证据：[本地](assistant-local/report.json)、[本地 Core 分组](assistant-local/core-results.json)、[Temp 克隆](assistant-temp-clone/report.json)、[Temp Core 分组](assistant-temp-clone/core-results.json)、[当前 CI](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682)、[CI 完整报告](ci-33896418682/artifact/20260904T164022Z-1c9eaf12/report.json)。CI run `33896418682`，attempt 1，真实 conclusion success；对应旧失败 run 33893214984 仍保留 failure，没有重试覆盖。

快速发现 0.924 秒：loader_errors=[]、770 原身份及 24 新身份完整匹配，发现总数 794，不计作执行 794 项通过。两项启动工程回归 2/2 PASS，1.848 秒。首次快速诊断曾在身份核对后错误读取命名空间 tests.__file__，TypeError 原始输出保存于 [首次诊断失败](quick-discovery.stderr.log)；改查 tests.__path__ 后才得到上述第二次结果。

Temp 验证不是用 Temp 外结果替代：

- 真实远端 checkout 实测在系统 Temp 后代；actual-checkout probe 1/1 PASS，2.283 秒，含 10 个两个入口/仓库根/正式目录/子目录场景，逐项检查拒绝、atomic_write_json 零调用和完整树内容不变。
- 原独立反例脚本不改断言，使用当前 Temp 克隆 Core，2/2 PASS，0.100 秒；覆盖两个入口及 Windows samefile 大小写反例。
- 现有路径/大小写 24 项在该克隆单独运行，23 PASS、1 SKIP，0.989 秒；大写、混合大小写、目录自身/子目录、合法 Temp、链接保护及原断言保留。
- 随后的 Temp 全量再次覆盖全部 794 项；clone Git 干净，无 .continuity-data 或 .assistant-data，测试和构建证据仅在忽略的隔离位置。

Engine 代码未再改变，按授权复用已核实且 hash 一致的 Engine 全量 793 PASS / 1 SKIP、434.732 秒；没有机械重跑三轮，也不把历史 Engine 运行算作本次执行。此前全量、旧 Temp/大小写失败、首次 P10 10 PASS / 2 FAIL、辅助错误及 P09 segment 10 stderr 缺失 / 根因 UNKNOWN 均保留。

## 冻结边界与证据保留

[完整最终核查](verification-audit.json)通过：Engine 源码/测试内容未改，25 个冻结文件、六 Schema、外部契约、两仓 pyproject 和版本 0.1.0 不变；正式数据 7 文件逐项 hash 不变，tree inventory 仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。三份 2026-08-26 规划源未变。320 个已有工程证据文件 hash 保持。双方 Git 元数据、数据配置独立，无正式主体/活动 Runtime 复制，未访问 Vio、真实 Provider、生产 Adapter 或外部业务数据库。Authority、E5-A、账本及生产 exactly-once 边界未改变。

静态解析、Markdown 本地文件链接、敏感签名及 git diff --check 的具体数字见最终核查；扫描没有输出秘密值，私有 wheel/CI ZIP 仅保存于忽略目录或独立仓库外证据位置，不纳入 Git。源/清单比较不因文件换行差异放松：Assistant 与 Git blob 精确比较；Engine 原有三处 CRLF 表示按已保存原始文件 hash 保持，不人为格式化。

已保留本轮局部辅助错误：首次命名空间诊断 TypeError；提交后摘要与命令证据同名触发 FileExistsError（[说明](helper-collision.md)），随后仅只读补收据，未重复提交/推送；一次沙盒只读打开 owner 创建的 Temp 报告被拒，后续通过已授权 owner 只读工具取得，不修改 ACL、目录或测试结果。它们不计为 Core 测试失败，也未被后续 PASS 覆盖。

## 待独立复核与停止门

请规划监工聚焦当前提交身份、原/新 checkpoint 真实祖先、188 文件/770+24 身份、统计入口最小修复与新本地/Temp/CI 证据；已复核 Core 不重复施工。只有收到核对通过结论后，才依据用户既有条件式授权登记 D-056、同步 P10 及十二项 ACCEPTED，并另行明确提交推送收尾档案。若跨任务发送被拒，不绕过；完整报告在当前施工对话交付，不自行假定监工已通过。

当前两仓暂存区均空、相对 upstream 0/0，Assistant 干净。Engine 尚未提交的 P10 档案和证据由 final Git 清单逐项记录；它们不是本轮两文件修复提交的内容。P11—P23 未开始。

## 本次交付状态

跨任务转交再次被自动审批拒绝，消息未送达；[原始拒绝记录](handoff-result.md)保留。按照用户最新指定的替代方式，在当前施工对话交完整报告，不绕过限制。因此尚未取得规划监工最终核对通过结论，条件式验收还未满足；不登记 D-056、不更新 ACCEPTED、不提交推送验收档案。已经完成的验证和授权保留，不重新申请同一范围 Git 或验收授权。最新两仓状态和未提交文件见 [交付 Git 清单](delivery-state.json)。

<a id="p10-accepted"></a>

## P10 正式验收生效追加记录（2026-09-05，D-056）

规划监工最终独立核对已通过。核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL；Temp 干净克隆、构建、安装、Golden、来源、路径隔离、冻结边界、正式数据和版本均通过或未变。

用户此前授予的条件式验收因此生效，Engine 决定 D-056 登记 P10 正式验收。现行状态为 `P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。` 本报告前文是独立复核前的真实交付快照，其“等待复核”“D-056 未登记”和冲突 PRESENT 等表述继续作为历史记录，不被本追加记录删除或倒写。
