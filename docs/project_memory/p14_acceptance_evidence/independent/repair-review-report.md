# P14 R1/R2 返修后独立复核：通过，等待用户正式验收

2026-09-08。此记录接续本目录的原独立复核报告与返修任务书，不覆盖原失败结论和证据。

结论：已确认的 R1、R2 在当前送审版本中修复，原反例及正向对照均通过；本轮定点审查和相邻检查未发现新的验收阻断。建议关闭这两项独立复核阻断，提交用户决定是否正式验收 P14。

本报告不是用户正式验收，不授权任何 Git 写操作或 P15；未代替 Engine 登记 D-065 或修改状态档案。

## 修复判断

### R1：新伤害不会被旧修复证明直接关闭

复核 [认知服务](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/dynamic_mind_service.py) 与 [内部 Mind 类型](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/domain/dynamic_mind.py)：Episode 增加可选的根身份和客观发生时间依据 `concern_basis`，相应类型验证保留旧映射兼容。正常 C1 只用该次 concern 之后、实际进入 Composer 的同对象/期待支持形成解决候选；旧支持仍保留，不因当前可读就被认作本次修复。

已核实：

- 原“先有旧支持、再发生伤害”及“已和好后再次伤害”两个反例均通过。
- 合法后续支持仍可解决；不是靠永远不准 resolved 来通过反例。
- RAW/Memory 同根不翻倍，消费置信度采用保守值；材料顺序不会放大同一根的强度。
- 既有正式扩展包含再次伤害后的重启、重复消费、新支持解决以及同时间支持不被冒认为后来证据。
- 新增独立检查：晚到的旧正向材料不会变成本次新修复；晚到的更早伤害不会把最新 concern 的客观时间向前倒退，且旧伤害根仍被保留。
- 新增独立旧记录对照：去掉可选 basis 的旧映射原样可读，正常后续支持仍可形成解决候选；纯候选计算不提交 SubjectState。

### R2：同驱力共存的欲望都能继续演化

服务由每个 drive 只取首项，改为处理全部匹配的稳定 Desire 身份；新身份生成对既有 ID 排序。没有删除或强行合并原欲望。

已核实：

- 原 transform 后另一条欲望冻结的反例通过，两者的数值、时间和轨迹均继续更新。
- 正式扩展中的列表逆序、连续机会、序列化恢复及 Will/Thought 引用对照通过。
- 新增独立检查把 intimacy 和 solitude 都转为 exploration，与原 exploration 共存；三条稳定身份在重载、逆序及两个后续机会中均保留并持续更新，按身份比较的结果一致。

## 本窗口独立实跑

| 本轮独立运行 | 结果 | unittest 秒 | runner 秒 |
| --- | --- | ---: | ---: |
| 原确认矩阵，原断言未改 | 7 PASS，0 SKIP/FAIL/ERROR | 20.694 | 21.408 |
| 完整 P14 四模块 | 67 PASS，0 SKIP/FAIL/ERROR | 113.783 | 114.767 |
| 新增相邻检查 | 4 PASS，0 SKIP/FAIL/ERROR | 12.558 | 13.273 |

7 项确认的等价正式回归已包含于 67 项 P14；不相加冒充互斥覆盖。67 项中包含本轮新增的 13 项正式回归。

原始证据：

- [原确认矩阵结果](repair-confirmed-01.result.json) / [逐项日志](repair-confirmed-01.stderr.log)
- [完整 P14 独立结果](repair-p14-01.result.json) / [逐项日志](repair-p14-01.stderr.log)
- [相邻检查结果](repair-adjacent-01.result.json) / [逐项日志](repair-adjacent-01.stderr.log) / [检查源码](repair_adjacent_probes.py)

复现方式：在规划工作区运行 `run_review.py`，使用全新标签，保持 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`。运行器自动为子进程配置规划探针、Engine/src、Engine/tests 的导入路径，并将日志保存在本目录，拒绝覆盖旧记录。

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& 'E:\Adobe\python.exe' '.\reviews\p14-independent-review-20260908\run_review.py' user-confirm-repair-02 -m unittest -v confirmed_probes
& 'E:\Adobe\python.exe' '.\reviews\p14-independent-review-20260908\run_review.py' user-confirm-p14-02 -m unittest -v test_p14_dynamic_mind test_p14_mind_recovery test_p14_mind_visibility test_p14_review_repair
& 'E:\Adobe\python.exe' '.\reviews\p14-independent-review-20260908\run_review.py' user-confirm-adjacent-02 -m unittest -v repair_adjacent_probes
```

本轮没有新增测试失败或测试 ERROR。原探索阶段的长 Temp 路径错误和两个未确认接口假设仍为历史，不被本次 PASS 覆盖，亦未扩大成返修要求。

## 核验引用的施工结果，不冒称独立全量

[独立身份检查](repair-identity-check.json) 的 20 项检查全部通过；源码见 [verify_repair_evidence.py](verify_repair_evidence.py)。

施工原确认 7 项、正式定点 13 项、P14 67 项、直接兼容 343 项和最终全量 1137 项这五轮记录，其 before/after 源码 hash 均与当前 221 个源码/测试/资源文件一致；完成状态、计数、测试身份和 FAIL/ERROR 记录一致。

本窗口仅核验引用施工全量：1136 PASS、1 既有 Windows symlink 1314 SKIP、0 FAIL/ERROR，runner 898.290 秒。未重新执行全量，未声称远程 CI 通过。原 1124 个测试身份全保留，新增加 13 个，没有新增 SKIP。

这说明本次独立定点结果和已有全量证据属于同一代码版本；不保证不存在任何尚未发现的问题。

## 范围、历史和边界

- 相对返修开工基线，源码/测试仅有两处实现文件修改和一个新增正式测试文件；其余原测试文件字节未变。
- 原 118 个 `p14_evidence` 文件与上次独立审查快照逐项 hash 相同；返修结果单独保留。开工记录中的 28 个规划复核原件 hash 均未变。
- 63 个受保护文件、3 份规划源、7 个正式数据文件和 31 个既有 P10 排除脚本逐项 hash 均未变。
- 正式数据树指纹仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。
- 211 个 Python 文件独立 AST 解析通过；`git diff --check` 退出 0。LF→CRLF 提示属于配置提醒，不是差异检查失败，原输出见 [收口检查](repair-closeout-check.json)。
- 192 个 P14 待提交路径与施工清单一致，191 个内容 hash 吻合；审计文件不自含 hash。另有 31 个排除脚本，未清理、未纳入提交。
- Engine main / HEAD / 本地 origin/main 仍为 `b02d8c9cc894b3060089d7cc24e06afaeab89ebf`，本地 ahead/behind 0/0，暂存区空；27 个已跟踪修改、196 个未跟踪路径。没有联网核实实际远端。
- 三轮独立运行前后各比较 1551 个 Engine 文件，变更集合均为空；本轮第一份快照到最后一份快照也无变化。快照不含 `.git` 和 Python 缓存。

全部测试使用隔离 TEST/Fake Fixture。未改 Engine、Assistant、Vio 或正式数据，未调用真实 Provider/Adapter，未派发后续施工、验收或 Git 指令。

## 交回用户决定

本轮 R1/R2 独立复核通过，可以进入用户正式验收。Engine 档案仍保持 `IMPLEMENTED_NOT_ACCEPTED` / `EVIDENCE_CONFLICT=PRESENT` 的送审状态；这不是新增代码故障，而是尚未登记本次独立结果和用户正式决定。

待用户明确验收后，才安排相应验收档案与状态同步。提交/push 和 P15 仍需用户授权。本报告不自行执行这些动作。
