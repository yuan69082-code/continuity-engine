# P09 独立复核：两项阻断，尚不可验收

日期：2026-09-04。Engine 基线为 main / fb8713ccb049ca082079cf820d06956be0954af9，本地 origin/main 相同，0/0。复核未修改 Engine 文件、未进行 Git 写操作；所有额外反例只操作临时 P01 TEST sandbox。

## 实跑结果

- 仓库原测试：`python -m unittest discover -s tests -q`，740/740 PASS，396.807 秒。
- 独立探针：6 项，4 FAIL、2 PASS，3.212 秒。原始输出见 [最终探针日志](p09_independent_probes.final.log)。
- 两个通过对照为当前合法 Context 的正常状态更新，以及 Evolution 已实际提交后的过期/撤权恢复；后者不应被返修误伤。
- 探针第一次使用了不存在的字段 `continuity.current_activity`，出现 3 个测试辅助错误；核对 `FIELD_RULES` 后改用合法字段 `continuity.current_focus`（字符串列表）。辅助错误不计为 Engine 缺陷，也不替代上述修正后实测失败。

## 阻断一：失效 Context 仍能授权首次 Evolution 提交

步骤：正常 C1 Fixture，Thinking 返回合法的 `continuity.current_focus` SET proposal；在 `after_thinking_completed` 中断，确认 revision 仍为 1。分别推进 11 分钟使 Context 过期，或撤销 exact-reference 许可。重新打开应用，确认 `core.current(context) == False` 后重提原请求。

两种情况下均返回 `FirstRoundSuccessResult`，revision 变为 2，Thinking 新调用为 0。这是新的状态提交，并不是恢复之前发生的状态事实。

定位：`services/continuity_interaction_service.py:672` 只在首次 Thinking 前验证 Context；`services/continuity_core_service.py:42` 对 UPDATE_STATE 返回 None；`services/continuity_interaction_service.py:1302` 在未找到原 Evolution 时直接进行首次提交，缺少 C1 当前有效性/授权检查。

修复须区分未发生的新执行与已经落盘的原事实。不可让旧的 Action 批准或旧时间戳成为永久许可；也不可用当前过期 Context 阻塞真实已提交 Evolution 的幂等恢复。

## 阻断二：C1 checkpoint 可降级并绕过回执核验

步骤：完成一条 C1 Direct 请求。未改动 checkpoint 时，Adapter query=UNKNOWN 会正确拒绝完成结果重放。随后仅在临时 operation journal 中 (a) 将 `domainProgress.perception.continuity_context.actions_enabled` 改为 false，或 (b) 移除同一位置的 `continuity_context`。ThinkSession、ActionContext、capability ledger、result ledger 和真实回执保持原样。

重启后，两种改动均返回与原来相同的 `FirstRoundSuccessResult`，Adapter query 调用为 0。持久化字段缺失或单一标志变更被用来绕过已有 C1 历史的独立事实核验。

定位：`services/continuity_core_service.py:280` 根据 checkpoint 的 actions_enabled 直接返回；`services/continuity_interaction_service.py:969` 根据单处 Context 是否存在决定是否验证；`services/continuity_interaction_service.py:1215` 的恢复观察一致性检查没有覆盖新增 C1 Context。应将原 C1 归属/启用状态与已有请求、ThinkSession、Action 和 E5-A 记录一致绑定，不因字段缺失而降级为 legacy。真正旧记录和原本关闭动作的合法记录仍须兼容。

## 复现命令

在 Engine 根目录中，设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，运行：

```powershell
python 'C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/work/p09_independent_probes.py'
```

## 只读边界核对

复核前后 src/tests/docs/README/pyproject/正式数据共 281 个非 pyc 文件逐项 hash 一致，无新增、删除或改变。工作区仍为 53 tracked 修改、47 untracked 文件，暂存区空。六份冻结 Schema、pyproject 和正式数据相对 HEAD 无 diff；git diff --check 通过，仅有原 LF/CRLF 配置提示。

正式数据 7 文件，树指纹为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

复核建议：P09 维持 IMPLEMENTED_NOT_ACCEPTED；当前证据冲突为 PRESENT（本报告结论，未改写 Engine 档案）。只在 P09 接线/恢复边界内返修，保留 40/740 的原通过历史和本轮独立失败事实。不创建 D-054、不进入 P10、不执行 Git 写操作。完成后再独立复核。
