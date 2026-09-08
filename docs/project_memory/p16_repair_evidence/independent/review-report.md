# P16 独立复核报告 — 2026-09-09

结论：**暂不建议验收或 push，需三项定点返修。** P16 继续停在 IMPLEMENTED_NOT_ACCEPTED；本复核发现新的证据阻断，建议施工档案据实登记 EVIDENCE_CONFLICT=PRESENT。本任务没有修改 Engine 档案或状态，没有代替用户授权返修、验收、Git 写操作或 P17。

这不是推翻 P16。四类本地查询、原 C1/E5-A 接线、历史事实恢复、候选分层等原有专项独立重跑通过。新增阻断集中在已承诺的“密钥类秘密不进入引擎持久化或诊断”边界；不是对心理内容、实验可见性或将来外部行动能力增设限制。

## 一、证据身份与范围

- Engine：`C:\Users\Administrator\Documents\continuity-engine`。
- 分支 main，HEAD 与本地 origin/main 均为 `a41a733635b0f5978c19b287274b4c63925b8979`；本地 ahead/behind 0/0，暂存区空。本轮未联网核实远端，不把本地引用当成已查询远端。
- 当前 241 个源码/测试/资源文件与施工终局审计、专项、兼容、完整回归的运行前后 hash 完全一致。
- 原 1208 个测试身份保留，恰新增 53；原测试文件字节未改。
- 63 项受保护文件、三份规划、正式七文件及树 hash、31 个 P10 辅助脚本与旧 P14 接续报告均未变化。
- 118 个 P16 待提交文件及原 32 个排除项与实际工作区精确对应；施工记录的待提交 hash 均匹配。
- 231 个 Python 文件解析有效，当前 `git diff --check` 通过。这不抹去历史档案中已登记的格式告警。
- 独立身份检查 **16/16 通过**，见 [identity-check.json](identity-check.json)。身份一致不等于行为验收。

## 二、真实运行与引用结果

| 证据 | 结果 | 耗时 | 性质 |
|---|---|---|---|
| `p16-original-01` | 53 PASS，0 FAIL/ERROR | unittest 87.614 秒；含包装器 88.715 秒 | 本任务独立运行原 P16 专项 |
| `independent-edges-02` | 7 项，2 PASS / 5 FAIL，0 ERROR | unittest 5.538 秒 | 新增独立探针 |
| `independent-edges-03` | 9 项，4 PASS / 5 FAIL，0 ERROR | unittest 7.239 秒 | 同五条反例再次复现，增加两个正常对照 |
| 施工 `p16-final` | 53 PASS | 86.849 秒 | 核对原始记录与当前源码，未冒充独立运行 |
| 施工 `compatibility-final` | 537 PASS / 1 既有 SKIP | 362.200 秒 | 引用并核对身份 |
| 施工 `full-final` | 1260 PASS / 1 既有 SKIP，0 FAIL/ERROR | 1081.872 秒 | 引用并核对身份；本任务没有再跑全量 |

独立探针首次 `independent-edges-01` 存在本任务自己的 TEST 临时根前缀过长问题，触发 Windows 长路径错误，7 项中 1 ERROR。其他探针有在目标路径到达前即异常的情况，**该次不能证明 P16 边界正确**。已缩短临时根、补充到达目标端口/真实原因的断言后，以新标签运行；首次 stdout/stderr 和结果原样保留，不覆盖。

所有包装器运行前后扫描 Engine **1877 个文件**，均 `changed=[]`。独立测试只在短路径临时 TEST Fixture 写入数据，测试结束清理其自身临时目录；原始失败诊断、文件相对路径和运行快照留在本规划工作区。

## 三、返修项

### R1 / 高：外部回执元数据绕过秘密检查，写入唯一 E5-A 账本

位置：Engine `src/continuity_engine/services/external_capability_service.py:18` 的 `_Adapter.query` 与 `:24` 的 `_Adapter.execute`。

现状：查询与执行返回的 `ActionReceipt` 只校验请求身份、时间等结构绑定，没有像 `ProviderResult` 一样经过 Broker 的 material 检查。合法字符串形式的回执编号仍可含禁止持久化的秘密；随后原 E5-A 的 `accept_action_result` 将它保存到结果账本。

独立复现：在正常本地 Provider 的 `query_receipt` 与 `execute_query` 两个返回口，一致地将回执编号替换为现有 Fixture 已识别并禁止的合成秘密标记。请求、状态、输出 hash、时间和其他绑定均保持原样。Provider 自己的 Fake 原始事实文件仍保留安全编号，未被修改、未含该标记。

实际结果：Engine 的 `integration/capability-ledger.v1.json` 出现合成标记。不是仅在测试工具输出里出现，也不是篡改引擎账本后再声称泄漏。

失败测试：`test_secret_receipt_identifier_must_not_be_persisted_by_engine`。

返修要求：在 P16 回执进入原结果账本之前覆盖执行、独立查询、恢复入口的材料边界。拒绝不安全材料时，不保留原秘密文本到错误详情，不把未确认执行改成 NOT_EXECUTED 并自动重发，不新增第二本账，不通过抹掉历史失败来“修复”。正常自定义回执编号及原成功事实的无重复执行恢复必须保留。

正常对照：`test_positive_safe_provider_receipt_id_remains_recoverable` 使用普通自定义编号，首次成功，缓存可读，再放同一请求仍只有一次实际执行；当前 PASS。

### R2 / 高：查询在 P16 被拒绝前，已进入 ThinkSession 与操作日志

位置：Engine `src/continuity_engine/services/external_capability_service.py:46` 的查询 material 检查；与原 `thinking_service.py`、`continuity_interaction_service.py` 的先保存结果、后执行 `after_action` 顺序有关。

独立复现：正常 C1 的 Information Need 返回 `memory:` 加同一合成秘密标记。原 FakeBroker 将其判定为禁止材料，没有修改 Broker 的拒绝规则。

实际结果：正常抛出 `EXTERNAL_INPUT_REJECTED`，外部执行次数为 0；但该内容已经存在于两个持久化位置：

- `integration/operation-journal.first-round-v1.json`；
- `thinking/sessions/.../<session>.json`。

因此“没有发给 Provider”成立，“没有保存秘密”不成立。只在 `_Policy.choose` 拦截太晚。

失败测试：`test_denied_external_query_is_not_copied_into_new_persistent_material`。

返修要求：为启用 P16 的外部查询材料提供首次持久化前的边界检查，并覆盖相应的新执行/恢复入口。失败只能记录安全原因和必要身份，不能先落原文再清理；不得静默修改已持久化事实、旧结果 hash 或旧请求身份。若需要扩展原 Thinking/C1 的可选内部接线，应说明最小范围、保持 P16 关闭时旧行为及原外部契约不变；超出已授权范围的部分需先确认。

这项**不是心理审查**：只处理 Broker 已明确判定的凭据类禁止材料，不按情绪、观点、亲密内容、实验内容或“是否友好”过滤。正常对照 `test_positive_ordinary_psychological_query_is_not_censored` 的愤怒、悲伤、不同意见及私人实验笔记查询正常执行并可缓存；当前 PASS。

### R3 / 中：Broker 与权限端口的原始异常泄漏到标准诊断

位置：Engine `src/continuity_engine/services/external_capability_service.py:46`、`:67`、`:99`、`:100`、`:119` 附近的 Broker/Permission 外部端口调用。

现状：Provider 查询、执行、结果读取已有静态错误转换并抑制原始异常链，但 Broker 的 `authorize_reference`、`material_allowed` 及 Permission 的 `authorize` 没有同等边界。

独立复现：上述三个端口分别抛出包含合成秘密的 RuntimeError，走正常 C1。顶层 IntegrationExecutionError 的简短消息虽是通用提示，但其异常链保留原异常；Python 标准 `traceback.format_exception` 原样输出合成秘密。运行 stderr 中已实际复现。

失败测试：

- `test_broker_authorization_exception_must_not_leak_in_diagnostics`；
- `test_broker_material_exception_must_not_leak_in_diagnostics`；
- `test_permission_port_exception_must_not_leak_in_diagnostics`。

这是**诊断出口**泄漏证据，不声称这三个用例已经把秘密写入 SubjectState、公开网络或 Git。没有使用真实密钥，也没有发现真实凭据泄漏的证据。

返修要求：统一 P16 外部端口异常边界，覆盖注册、选择、执行、消费与恢复涉及的调用；保留可定位的静态错误码，不将任意原始异常字符串、repr 或显示的异常链带出。异常必须按失败/未确认处理，不能被吞成授权成功。不要修改或删掉原始反例日志；这些日志只含已注明的合成测试标记。

正常对照：`test_positive_provider_result_exception_is_sanitized` 对 Provider.read_result 抛出相同标记，现有防护确实不输出原秘密；当前 PASS。

## 四、明确未认定为此次缺陷的事项

- 本地四类 Fake 能调用，不等于真实服务/生产凭据已经接通；施工 NOT_READY 的说明是正确的。
- 当前权限失效后仍可核验旧成功事实，与禁止再次消费旧资料并不矛盾。
- UNKNOWN 不擅自重发；原单账本、显式重试上限和不重复执行语义必须保留。
- 缓存 256 条上限、未提供生产自动清理、并发只声明本地线程级能力等已记录限制，不在此次私自扩大为 P17/P22 工作。
- 本地 Windows 1314 既有 SKIP 不等同于 PASS，也不把它改成此次新缺陷。

## 五、复跑入口

独立探针位于本报告同目录 [test_independent_edges.py](test_independent_edges.py)。包装器会将该目录及 Engine src/tests 加入 PYTHONPATH，并禁止字节码写入。标签必须新建，避免覆盖失败证据：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'E:\Adobe\python.exe' 'C:\Users\Administrator\Documents\Codex\2026-08-24\https-github-com-yuan69082-code-continuity\reviews\p16-independent-review-20260909\run_review.py' p16-repair-independent-01 -m unittest test_independent_edges -v
```

只有用户确认返修后才执行相应代码更改。建议修后先复跑本九项反例/正常对照，再 P16 专项和受影响兼容；代码稳定后一次完整回归。保留原 1261 个测试身份及全部历史，不机械三轮全量。最终仍交回独立复核和用户决定，不自行验收、push 或进入 P17。

核心证据：[原专项结果](p16-original-01.result.json)、[独立九项原始 stderr](independent-edges-03.stderr.log)、[独立九项运行快照结果](independent-edges-03.result.json)、[身份审计](identity-check.json)。
