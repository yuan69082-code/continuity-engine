# P09 第一轮返修的独立复核

本轮只读检查 Engine；额外故障注入仅发生在临时 P01 TEST 沙盒。未修改 Engine 文件、未执行 Git 写操作。

## 已闭合的原反例

正式新增回归实跑 16/16 PASS，15.765 秒，其中包括上轮四反例与两个合法对照：Context 过期/撤权阻止首次状态写入；原 C1 Context 删除/动作开关翻转被拒绝；合法当前更新和已提交 Evolution 的恢复继续可用。

## 残留阻断：evolution=null 仍能关闭原状态事实核验

独立新探针 2 项全部 FAIL，1.502 秒，见 [脚本](p09_repair_review_probes.py) 和 [原始输出](p09_repair_review_probes.final.log)。

步骤：正常 C1 Thinking 提出合法 continuity.current_focus 变更，完成 Action/Evolution 后取得成功结果。仅将临时 operation journal 的 evolution 字段改为 null；保留 domain.approved_state_action、ThinkSession、Action、完成结果及 SubjectState。重启后，在既有 Evolution 事实查询 Port 模拟原授权不匹配或原事实缺失。

- 完整 checkpoint 对照能正确拒绝不匹配/缺失的事实。
- checkpoint 置空后 submit 返回同一 FirstRoundSuccessResult，事实查询次数 0。
- checkpoint 置空后 query_request 返回 COMPLETED，事实查询次数 0。

原因：`src/continuity_engine/services/continuity_interaction_service.py:1005` 仅在 `operation.evolution is not None` 时校验已提交事实。`domain/integration_results.py` 允许 COMPLETED + approved_state_action + evolution=None，且启动和完成结果交叉校验没有补齐该分支。缺失字段再度被解释为无需验证。

应从原 Action 授权、稳定 operation/event 身份、ThinkSession 和完成结果的状态更新证据共同判定需核实的事实，而不能由可置空的 checkpoint 控制。缺失/冲突必须失败关闭；如果支持由真实原记录恢复缺失 checkpoint，也必须先核实全部绑定。不能破坏尚未完成、Evolution 已落盘但 checkpoint 未保存的合法崩溃恢复，不能重复推进 revision。

## 历史 long 子进程 ERROR 与证据保留

原 `repair-01/final-p09.log` 确实为 56 项、106.759 秒、1 ERROR；它只有 segment 10 失败摘要和已不存在的临时根路径，没有子进程 stderr 或 return code。因此无法由现有材料断言原错误是代码缺陷，也无法断言其完全由中断引起。后续 PASS 不覆盖这条未知历史。

只读检查确认：`testing/p09_core_runner.py:110` 把子进程 stdout/stderr 写入传入根后抛出仅含路径的 RuntimeError；`tests/test_p09_long_run.py:19` 的 TemporaryDirectory 在异常退出时删除该根。独立受控探针让 subprocess 返回 91 与 synthetic-child-failure，父级异常不含 stderr，测试作用域退出后日志根消失，见 [受控证据保留检查](p09_repair_review_retention.log)。这只证明保留机制缺口，不证明原 segment 10 的历史根因。

建议仅完善测试 harness 的失败/中断证据保留：清理前在独立证据位置保存命令、阶段、退出码、stdout/stderr 和时间，明确区分受控中断、子进程失败与完成运行，不隐式重试。保留/清理只作用于明确的测试根；不触碰正式数据。

## 探针辅助错误记录

新探针第一次使用较长临时目录前缀，在最初正常写入步骤发生 FileNotFoundError，尚未到达目标反例。缩短前缀后复现上述两项断言失败。首次输出单独保留在 [初次路径错误](p09_repair_review_probes.initial-path-error.log)，不计入 Engine 两项断言失败，也不用于推断历史 long 子进程错误。

## 复现

在 Engine 根目录设置 PYTHONPATH=src、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1：

```powershell
python 'C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/work/p09_repair_review_probes.py'
```

当前复核结论：原四项反例已闭合，但 Evolution 缺失分支仍有阻断。P09 继续 IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT 保持 PRESENT。D-054 不创建，不进入 P10。

## 最终实跑与只读边界

独立完整回归 `python -m unittest discover -s tests -q`：756/756 PASS，485.573 秒，退出码 0，见 [全量输出](p09_repair_review_full.log)。包括 P09 56 项以及真实进程长期场景；没有中断、失败后重试或改动源码/测试。该通过记录不能抵消另行构造的两项失败反例，也不解释历史 segment 10 ERROR 的根因。

复核前后 src/tests/docs/README/pyproject/正式数据共 304 个非 pyc 文件清单与逐文件 SHA-256 完全一致，无新增、删除或内容改变；175 个源码/测试 Python 文件按 3.11 语法解析通过。正式数据仍为 7 文件，树指纹 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。pyproject hash 为 `40703a155ab1c1626901d1b61363384e49b5c64e58303cc110fe499ff6c25419`。

六份冻结外部 Schema、pyproject 与正式数据相对 HEAD 无 diff；interfaces 文件相对首轮监工复核无内容变化（P09 首版内部组装增量仍存在）。git diff --check 通过，暂存区空；main / HEAD / 本地 origin/main 均保持 fb8713ccb049ca082079cf820d06956be0954af9、0/0；工作区仍为 58 tracked 修改、70 untracked 文件。未执行 Git 写操作，未改写 Engine 的验收状态或工程档案。
