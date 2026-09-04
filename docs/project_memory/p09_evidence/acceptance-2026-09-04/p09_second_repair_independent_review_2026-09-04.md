# P09 第二轮定点返修独立复核

日期：2026-09-04。复核工作区：C:/Users/Administrator/Documents/continuity-engine。

## 结论

本轮独立技术复核通过，未发现需继续返修的现行验收阻断。上轮 Evolution 缺失 checkpoint 两条反例及测试证据保留缺口已经闭合，P09 可交由用户正式验收。

这不是用户正式验收。未修改 Engine 源码、测试、档案或验收状态；P09 / Engine side / 十二项在 Engine 档案中仍为 IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT 仍为 PRESENT。D-054 未创建，P10 未开始，最终稳定 C1 SHA 尚未确定。

## 本窗口实际执行

环境：PYTHONPATH=src，PYTHONDONTWRITEBYTECODE=1，PYTHONUTF8=1；Python 3.14.4。所有场景使用 TEST 临时根。

| 独立执行 | 结果 | 耗时 |
|---|---|---|
| 原监工脚本两条 Evolution 反例，脚本未修改 | 2/2 PASS | 1.381 秒 |
| 第二轮新增 14 项 + 第一轮原 16 项正式矩阵 | 30/30 PASS | 27.690 秒 |
| 完整 Engine 回归，含 P09 70 项、Golden 与 30 轮三进程长期场景 | 770/770 PASS | 484.753 秒 |

前两行不是新增 32 个互不重叠用例：原监工两条已纳入正式矩阵。完整回归本轮启动一次、没有中断或失败后重跑；退出码 0。

完整命令：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python 'C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/work/p09_repair_review_probes.py'
python -m unittest tests.test_p09_evolution_review tests.test_p09_evidence_retention tests.test_p09_review_regressions -v
python -m unittest discover -s tests -q
```

输出见 [定点回归](p09_second_repair_review_targeted.log) 与 [独立全量](p09_second_repair_review_full.log)。工具返回文本在本报告附属文件中统一为 LF；这些文本文件不冒充子进程原生流的逐字节副本。目标矩阵前一次工具输出因截断不可见，没有据此推断其结果；本表引用的是完整捕获的重新执行结果。

## 闭合依据

1. nullable Evolution checkpoint 不再决定是否查验原始事实。恢复检查联合原 Action 授权、持久化 ThinkSession、完成结果的状态投影，并以稳定 request/operation 身份查找实际 Evolution；缺失或不匹配拒绝。独立旧反例现均通过。
2. 正式矩阵覆盖 submit/query/retry/result callback，23 类事实缺失或绑定变化；合法首次更新、已提交但未保存 checkpoint 的恢复、过期后原事实只读重放、无状态更新与真实旧路径均保持通过。
3. Long runner 用文件接收子进程流，在失败或可捕获中断时保存到 Fixture 外的独立目录。没有引入 Engine 账本、隐式重试、生产恢复或额外 Authority。
4. 本窗口实跑产生的受控退出 91 与受控父级 KeyboardInterrupt，原 Fixture 均已清理；保存的 stdout/stderr/metadata 仍可读。未脱敏流的字节数、SHA-256 与元数据逐一匹配。
5. 独立读取 Engine 归档的 byte-fix-child-failure / byte-fix-parent-interrupt 两组证据，得到相同结论。父级中断由受控 KeyboardInterrupt 证明，不从 Windows 退出码 1 猜测中断。

详情见 [证据存活与字节核查](p09_second_repair_review_retention.json)。

## 历史 UNKNOWN 的处理

历史 repair-01/final-p09.log 的 56 项 / 106.759 秒 / 1 ERROR 原文仍存在；历史 segment 10 stderr 缺失，根因仍为 UNKNOWN。本轮不能补造、复原或把该历史改写为 PASS，也不能声称根因已查明。

当前可复现的 Evolution 缺口与证据保留缺口已经修复，并经独立回归验证。技术上本轮现行阻断可关闭；正式验收档案应同时保留历史 UNKNOWN 及证据缺失限制，而不是删改历史。是否正式验收由用户明确决定。

## 只读与冻结边界

- 本轮前后 src/tests/docs/README/pyproject/正式数据共 352 个非 pyc 文件清单和逐文件 SHA-256 完全一致；新增、删除、改动均为 0。
- 187 个源码/测试文件与 Engine 最后回归清单全部一致；54 份返修前历史证据的 hash 全部保留。
- 177 个 src/tests Python 文件通过 3.11 语法解析；实际执行解释器为 3.14.4，不代表已运行全部支持的 Python 版本。
- 57 份 Markdown、375 个内联本地文件链接核查通过；尾随空白和未闭合围栏为 0。本检查没有额外宣称重新核验所有锚点。
- 六份冻结 Schema、pyproject 与正式数据相对 HEAD 无 diff。25 个接口/pyproject 边界文件与第二轮返修冻结清单一致。local_integration_app.py 的 P09 首版内部组装差异仍存在，不能说整个 interfaces 相对 P08 HEAD 零差异。
- 三份 2026-08-26 规划源 DOCX 的 SHA-256 与登记值一致。
- 正式数据仍为 7 文件，各文件 hash 不变；树指纹：sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2。
- pyproject SHA-256：40703a155ab1c1626901d1b61363384e49b5c64e58303cc110fe499ff6c25419；版本 0.1.0。
- git diff --check 返回 0；仅 LF→CRLF 配置提示。
- main；HEAD = 本地 origin/main = fb8713ccb049ca082079cf820d06956be0954af9；本地 ahead/behind 0/0，暂存区空，67 tracked 修改、118 untracked 文件。没有 fetch 或其他远端状态验证，没有执行 Git 写操作。
- 本窗口仅在规划工作区保存复核产物，未改 Engine。修复的幂等与长期场景结论仍限本地 Fake/TEST 能力，不保证生产 Adapter exactly-once，也不等同生产长期稳定性证明。

静态/边界结果见 [检查记录](p09_second_repair_review_checks.json)，复核前后清单见 [文件清单核对](p09_second_repair_review_inventory.json)。

## 下一步

等待用户明确正式验收 P09。确认后才授权纯档案收口：登记 D-054、同步 P09/Engine/十二项的正式状态和现行冲突结论、保留所有失败与 UNKNOWN 历史。随后由用户提交并 push，核对实际提交后的稳定 C1 SHA，再单独授权 P10。本报告不授权上述写操作或后续施工。
