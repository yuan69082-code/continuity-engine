# P13 独立复核结果

2026-09-08。结论：发现两项需要返修的权限与来源边界问题，P13 暂不具备验收条件。此报告是规划侧只读复核，不是引擎修改、返修授权、阶段验收或 Git 授权。P12 已验收不受影响，P14 不开工。

## R1 表达授权撤销后仍能首次物化并返回正文

优先级 P1。位置：Engine `src/continuity_engine/services/expression_policy_service.py:52`、`:66`、`:116`；`continuity_interaction_service.py:441`、`:457`。

`decide()` 重验的是 `core.current(context)` 和原 ActionDecision。当前 Context 的来源许可有效，并不代表当前 `expression:emit` 许可仍有效。`denied` 使用旧 `action.decision.approved/requires_confirmation`，没有重新核对表达所依赖的当前授权。`verify(current=True)` 又复用这一判断。

三个独立失败反例：

1. 原 C1 Action 执行完成后、首次进入表达前，撤销同一 PermissionProvider 中真实存在的 `expression:emit` grant。首次表达仍调用 Port、完成并返回正文。
2. 纯呈现 Port 调用期间撤销该 grant。调用后的二次核对仍通过，保存并返回正文。
3. 已完成请求重启后撤销该 grant，再次 submit 原请求。仍返回旧正文，而没有阻止当前消费。

正向对照：在 Action 执行前撤销同一 grant，既有通路确实拒绝，呈现调用与 Fake effect 均为 0。这证明不是探针撤错权限，也不是不存在的许可规则。另一个对照确认 Context exact 权限撤销仍能拒绝，缺口是表达授权与来源许可被当成同一件事。

修复建议（尚未授权执行）：分开“验证已发生事实”和“授权当前表达消费”。利用既有权威许可、确认/资源接口，绑定正确主体与表达行为，在首次物化、Port 返回后及当前读取入口核验当前授权；历史成功回执不可充当新授权。不得为了拒绝当前正文而抹去旧真实效果、原账目或增加第二账本；不能重新执行已发生的动作。

## R2 表达层直接使用本次 Context 未纳入且未获准的关系材料

优先级 P1。位置：Engine `src/continuity_engine/services/expression_policy_service.py:54` 至 `:65`。

`decide()` 在 Context 检查后直接加载完整 SubjectState，并从中读取 identity 和 relationship 偏好。`core.current()` 只对 route.manifest 中的实际候选调用 source/reference 授权；材料若未入选，就不会在这里被核验。表达层重新从完整状态读取，绕开了这个选择与许可边界。

独立失败反例：在隔离 Fixture 中通过合法 TEST Event 设置 `relationship.interaction_preferences=['formal']`。为有效的有界 SubjectState Source 配置一个不返回 relationship 的批次，同时将该关系条目的 exact-reference 许可设为拒绝。其他材料和 Context 仍正常。请求成功，manifest 确实不含 relationship，表达却仍选择 `quoted` 并用 `> ` 格式输出；原因正是直接读取了不在获准 Context 中的 `formal`。

探针允许两种安全结果：缺少必要表达依据时明确拒绝；或者不使用该关系偏好，保持不依赖它的默认样式。当前两者均未做到。这不是要求新增关系权限制度，而是要求 Expression 不绕开现有来源/引用授权。

修复建议（尚未授权执行）：表达样式使用当前可信且获准的 Context 片段/精确投影，或通过现有授权与 resolver 明确取得缺失材料后再使用。不能因同属 SubjectState 或 revision 相同就跳过选择/授权；缺失数据不能默认取得使用权。核对 identity、relationship、emotion 三类表达输入的相邻路径，并保留各自来源、绑定、失效与最小化 Trace。

## 实际执行与证据

| 独立执行 | 结果 | unittest 耗时 | 原始证据 |
|---|---|---|---|
| 引擎原 P13 专项 | 38 PASS，0 SKIP/FAIL/ERROR | 34.137 秒 | `original-p13-01.stderr.log` |
| 首次新探针 | 3 FAIL、2 PASS、1 ERROR，共 6 项 | 3.351 秒 | `probes-01.stderr.log` |
| 辅助错误修正及增加对照后 | 4 FAIL、3 PASS、0 ERROR，共 7 项 | 4.319 秒 | `probes-02.stderr.log` |

首次 ERROR 是规划侧探针误用了 `_sources`，实际成员为 `_bindings`，不是引擎问题。已经改正且原断言保留；详见 `helper-history.md`。没有把后续结果覆盖原失败记录。

四个失败对应 R1 的三个时点及 R2 的一个来源遗漏，不是四个独立根因。三个通过的对照分别为执行前撤销表达授权、Context exact 撤权和合法重启零新效果。

复现当前七项：

```powershell
$env:PYTHONPATH = 'C:\Users\Administrator\Documents\continuity-engine\src;C:\Users\Administrator\Documents\continuity-engine\tests'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& 'E:\Adobe\python.exe' 'C:\Users\Administrator\Documents\Codex\2026-08-24\https-github-com-yuan69082-code-continuity\reviews\p13-independent-review-20260908\review_probes.py'
```

`run_review.py` 可以用新标签包装上述命令，将输出和前后 hash 保存在本目录；旧标签拒绝覆盖。探针只写独立临时 TEST Fixture。三次执行前后都核对了 Engine 的 1311 个非 Git、非 bytecode 文件，变化清单均为空。

## 证据与保护核对

`identity-check.json` 的 17 项核对全部通过：当前 211 个源码/测试及资源文件与施工最终全量记录一致；原 1011 测试身份和旧测试文件保留；当前全量身份 1049 项无重复。施工记录 1048 PASS、1 个既有 Windows symlink 1314 SKIP、0 FAIL/ERROR、596.249 秒，此项为引用而非本轮重跑。没有新远程 CI 验证或 CI PASS 声明。

63 个保护文件、正式七文件、三份规划源、31 个 P10 排除脚本及施工审计中全部待提交文件 hash 无漂移。正式数据树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

Engine `main` / HEAD / 本地 `origin/main` 仍为 `7afceba17635a8d9fd915bf09fa9df68f3ff3974`，本地 ahead/behind 0/0，暂存区空。本轮未联网核实远端；119 个待提交文件与 31 个排除脚本保留。没有修改 Engine、Assistant、正式数据或 Git。

施工侧旧全量通过与本轮新反例失败不矛盾：原测试没有覆盖这两处边界。规划侧当前独立复核阻断为 PRESENT；Engine 档案仍保留原施工送审状态，本次未擅自改写。等待用户确认后，才能安排这两项有界返修，不得自行验收、push 或推进 P14。
