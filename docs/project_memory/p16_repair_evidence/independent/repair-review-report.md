# P16 R1/R2/R3 返修独立复核 — 2026-09-09

结论：**本轮独立复核通过，原三项已知阻断在已验证范围内闭合，可以交由用户正式验收。** 未发现本次修复带来的新增阻断。这不是“保证无任何缺陷”，也不代替用户验收、Git 授权或后续阶段授权。

本任务没有修改 Engine 源码、测试、档案或阶段状态，没有执行暂存、提交、push，没有创建 D-069，没有进入 P17。Engine 档案仍为 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT；后续可在用户授权的验收记录中引用本报告登记已知阻断闭合。

## 一、独立运行

| 独立执行 | 真实结果 | unittest 耗时 | 包装器耗时 |
|---|---|---|---|
| 原九项探针 `repair-independent-01` | 9 PASS，0 SKIP/FAIL/ERROR | 6.849 秒 | 7.455 秒 |
| 当前完整 P16 专项 `repair-p16-01` | 78 PASS，0 SKIP/FAIL/ERROR | 112.062 秒 | 112.712 秒 |
| 本任务新增四项 `repair-controls-01` | 4 PASS，0 SKIP/FAIL/ERROR | 3.843 秒 | 4.657 秒 |
| 独立身份核对 `repair-identity-01` | 22/22 检查通过 | 不属于行为测试 | 2.038 秒 |

原九项以字节相同的副本包含在正式 78 项中，不能重复相加。新增四项只在规划工作区执行，不增加 Engine 正式测试总数。

各次包装器运行前后扫描 Engine 1949 个文件，均 `changed=[]`。独立探针写入的只是自建短路径临时 TEST Fixture；没有触碰正式数据。全部原始命令、退出码、stdout/stderr、运行前后快照留在本报告同目录。

## 二、逐项复核结论

### R1：回执材料遗漏 — 通过

已阅读 `_Adapter.query`、`_Adapter.execute`、`check_receipt` 及原 E5-A 恢复接线。完整回执的 to_dict 在进入原账本前交给 Broker，不仅检查编号；原结构、请求绑定与恢复核验保留。

验证结果：

- 原“秘密放在回执编号后写进 capability ledger”的反例已通过。
- 正式回归对完整回执各字段、执行与查询出口进行检查。
- 拒绝执行回执后保留 UNKNOWN，不将其解释为未执行或擅自重发。
- 本任务换用另一条独立合成标记和自定义 Broker 判定，仍被拒绝且不持久化；同一请求重复恢复没有增加执行次数。
- 清除测试注入后，原安全事实可恢复，累计仍只执行一次。
- 普通自定义回执编号及正常重复恢复继续通过。

### R2：查询检查晚于持久化 — 通过

已阅读 ThinkingService 的可选 result_validator 与 ContinuityInteractionService 的 P16 接线。原模型结果在 processor 和首次成功保存之前检查；processor 输出再检查；等待结果完成、已完成会话重放、C1 CapabilityResult 入账与相应 checkpoint 恢复也检查材料。P16 关闭时不调用这条可选外部检查。

验证结果：

- 原“查询拒绝，但 ThinkSession/operation journal 已保存秘密”的反例已通过。
- 正式回归验证首次保存、processor 之前拒绝、等待恢复、旧结果重新读取与模型 CapabilityResult 首次 E5-A 入账。
- 新增独立测试让 processor 在初次检查后才产生另一条禁止材料，二次检查仍在 ThinkSession 保存前阻断；无外部调用、无 SubjectState 变化。
- 安全的等待结果恢复、原结果身份/hash、合法模型结果重放与 P16 关闭时旧路径均通过。
- 原普通心理、不同意见和私人实验内容查询正向对照仍通过。修复没有新增按情绪、观点或“是否友好”的审核规则。

### R3：外部端口异常原文泄漏 — 通过

已阅读 `_port` 及 material_allowed、authorize_reference、authorize_permission 的调用。外部异常转换为静态错误码并抑制标准显示的原始异常链；只有明确 True 才视为允许，不把非布尔真值或异常当成授权。

验证结果：

- 原三个 Broker/Permission 异常探针均通过。
- 正式回归覆盖注册、执行、消费、恢复，检查标准 traceback、实际输出与运行目录。
- 本任务使用不同异常标记，在注册和缓存消费时仍不泄漏原文，文件不变，原调用次数不增加。
- 新增独立测试验证 `1`、`'true'`、非空列表不会冒充授权或材料允许；恢复正常 True 后合法查询仍可执行。
- 既有 Provider 异常防护与普通拒绝继续通过。

上述材料均为明确标注的合成测试标记；没有读取或使用真实密钥。本结论也不表示任意宿主、任意生产 Adapter 或所有未知秘密模式都已验证。

## 三、证据与保护项独立核对

见 [repair-identity-check.json](repair-identity-check.json)，22/22 检查通过：

- 当前 243 个源码/测试/资源文件与修复专项、兼容、全量四份引用记录的运行前后 hash 一致；233 个 Python 文件解析有效。
- 修复基线与上一轮独立失败探针后的实际源码快照一致。
- 仅三份原服务实现与两份新增正式测试发生本轮源码/测试增量；原测试文件字节不变。
- 原 1261 项测试身份完整保留，恰新增 25 项，最终 1286 项；正式九项副本与独立原件字节一致。
- 63 项受保护文件、三份规划、正式七文件与正式数据树 hash、31 个 P10 脚本和旧 P14 接续报告未变。
- 78 个历史证据文件未变；30 个独立材料原件及施工归档副本 hash 一致。
- 原 118 项 P16 成果保留，完整待提交清单现为 192 项；与原 32 个排除项合计精确覆盖当前工作区。审计记录的 191 项待提交 hash 均匹配（审计自身不自哈希）。
- 当前 Git：main，HEAD 与本地 origin/main 均为 `a41a733635b0f5978c19b287274b4c63925b8979`，本地 ahead/behind 0/0，暂存区空；29 个 tracked 修改、195 个 untracked 文件。
- 当前 `git diff --check` 通过，不抹去旧证据中的历史格式告警。

正式数据树：`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

## 四、引用结果，不冒充独立重跑

施工方本次兼容结果为 675 PASS / 1 SKIP，501.254 秒；最终全量为 1285 PASS / 1 SKIP、0 FAIL/ERROR，1072.026 秒。本任务已核对原始 JSON、stderr、方法身份、计数与当前源码，但没有再跑这两组。

唯一 SKIP 是既有 Windows 符号链接权限不足 1314，不计为 PASS。没有查询远端、执行 CI 或声称远端 CI 通过。真实服务、生产凭据、生产隐私政策及 P17/P22 内容仍不在本轮交付范围。

## 五、可引用入口

- [原九项独立结果](repair-independent-01.result.json) / [原始 stderr](repair-independent-01.stderr.log)
- [完整 P16 独立结果](repair-p16-01.result.json) / [原始 stderr](repair-p16-01.stderr.log)
- [额外四项探针源码](test_repair_independent_controls.py) / [结果](repair-controls-01.result.json) / [原始 stderr](repair-controls-01.stderr.log)
- [独立身份审计](repair-identity-check.json)
- [上轮失败报告](review-report.md)，原失败证据全部保留

下一步仅建议：用户确认正式验收及是否允许提交/push 后，再提供对应精确收尾指令。不自动开展 P17。
