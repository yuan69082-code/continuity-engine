<!-- W03_ACCEPTED_D083_20260926 -->
## W03 正式验收现行层（D-083）

用户已正式验收 N03、N04、N06 及 N06 三处返修，现行 W03 = `ACCEPTED`。完整 `Planning Item → Code Change → Test → Acceptance Result` 见[验收矩阵](../w03_acceptance_evidence/acceptance-matrix.md)，验收及后置限制见[报告](../w03_acceptance_evidence/acceptance-report.md)。下方初版 `IMPLEMENTED_NOT_ACCEPTED`、兼容/全量 ERROR 和返修中待复核均是发生时的历史证据，不倒改。W02 四份资料负载时限风险与 F1/H1/F2 `UNKNOWN` 继续保留。

---

# W03 施工矩阵（待独立复核）

本矩阵只记录 W03/N03、N04、N06 的 Engine 实施与隔离 TEST 证据。W02 的 D-081 验收及历史失败不因本轮改写。W03 不自行登记 ACCEPTED。

| Planning Item | 代码入口与责任 | 正反及恢复验证 | 当前结果与限制 |
| --- | --- | --- | --- |
| N03 / T04 | `SubjectGrowthService.capture` 沿原 Event → Context → Learning 捕获候选；同根 Timeline/Memory 片段一轮只建一个候选。`RecognitionService.validate` 使用原独立根和当前支持核验。 | `test_w03_recognition.py`：三独立事件、W02 原消息路径、同一根重复、同名不同对象。 | 专项已通过；TEST 事件注解只代表受控解释假设，真实模型语义质量未验收。 |
| N03 / T07 / T08 | `RecognitionService.commit/withdraw/read`；当前主观认识只写 `SubjectState.relationship.objects`，历史由原 Evolution 记录保存；当前来源/版本/权限、反证和修正关系逐次重查。 | 初次形成、单条反证争议、三独立反证撤回、更正结论、旧更新重放、来源撤销后状态降为待复核、只读变化理由。 | `w03-special-final-02` 通过；真实语义仍限 TEST 注解，不宣称通用语言理解。 |
| N04 / T09 | `ContinuityCoreGates.essential_core` 与正常 `ContinuityCoreService.prepare/before_thinking`，保留原 Router/Composer 的保护片段和预算。 | `test_w03_core_context.py`：日常 C1、缺核心、预算不足、关闭 Gate 的旧路径、Capability 模型替换。 | 专项已通过。内部状态随请求提供，不声称修改模型权重；完整生产运行策略属后续。 |
| N06 / T12 | `UnfinishedItem` 作为 `SubjectState.continuity` 可选内部字段；`UnfinishedItemService` 沿 Action Gate/Evolution/CAS 保存；`ready` 给 P11/P18 计算机会入口，非第二队列。 | `test_w03_unfinished_items.py`：旧记录、提交/重放、急事等待、普通事推进、aging、改期/取消/完成、当前来源撤销、只读查询。 | 专项已通过；W05 才核验完整常驻运行联动。 |
| N06 / T18 | 稳定命令 ID、原更新历史回放、原 E5-A 可靠回执与内部结果事实、原子保存失败。 | 重开、重复提交、事实不符拒绝且零写入、已完成不倒退、存储失败无部分写入。 | 专项已通过；生产 Adapter 的 exactly-once 不在本包声明。 |
| 兼容边界 | P09 C1、P11/P18 唤醒、P14 心智、P15 学习、W02 入站/回忆/外部资料原链。 | `w03-compat-final-02`、`full-final-02`；`head-w02-deadline-01` 为 HEAD 旧版隔离对照。 | 固定 W03 版兼容 176 项中 175 PASS、1 ERROR；全量 1761 项中 1759 PASS、1 既有 SKIP、1 同类 ERROR。原 W02 1000ms 回忆时限触发；HEAD 旧版在隔离 Temp 的同一测试也触发 `RECALL_TIMEOUT`，不能归因为 W03 独有；但当前兼容和全量仍未全通过，需独立复核。 |

首次失败包括新测试注入点笔误、Windows TEST 路径过长辅助错误、真实同根重复学习捕获、既有 W02 回忆时限触发；均保留原始输出，后来的通过不倒改。最终运行、保护审计及 W03 状态在终局报告中补齐。矩阵所有 W03 项最高为 `IMPLEMENTED_NOT_ACCEPTED`，测试通过不等于验收。

## 2026-09-25 N06 独立复核后定点返修增量

| Planning Item | 代码增量 | 正反/恢复证据 | 验收结果 |
| --- | --- | --- | --- |
| N06 / T12 终态下沉 | `UnfinishedItemService.submit/read`：完成、取消从当前 64 项集合退出，原 Evolution 事件保留终态记录；原命令摘要与重放保持兼容。 | `n06-repair-before-01` 第 65 项真实失败；`test_completed_and_cancelled_sink_without_exhausting_64_current_slots`、`test_original_w03_command_hash_replays_without_new_revision`。 | `IMPLEMENTED_NOT_ACCEPTED`，待最终同版回归及独立复核。 |
| N06 / T12 旧事项绑定 | 同一次原 Evolution 更新仅在显式旧列表位置、标题、列表 hash 和 revision 绑定后移除一条旧字符串；创建时或已有结构化事项合法状态转换时可绑定。同名但无命令不自动合并。 | `n06-repair-before-02`、`n06-existing-legacy-before-01`；`test_same_title_needs_explicit_version_bound_legacy_migration`、`test_existing_structured_item_can_bind_legacy_on_terminal_transition`、无绑定歧义对照。 | `IMPLEMENTED_NOT_ACCEPTED`；旧数据身份不明时保留 `LEGACY_UNSTRUCTURED`。 |
| N06 / T18 来源与权限 | `UnfinishedItemService._verify_roots` 复用原 Memory 可用性、Timeline 根、P16/W02-C 外部根/具体材料和原 P05 来源授权；就绪与只读返回前均重查。 | `n06-source-before-04`、`n06-external-before-05`、`n06-memory-permission-before-01`；正式本地 Memory 撤销、跨主体、外部派生材料部分撤回、重开、权限、零写入对照。 | `IMPLEMENTED_NOT_ACCEPTED`，待最终同版回归及独立复核。 |
| W02 1000ms 时限诊断 | 不改 W02。 | [同条件旧 HEAD/工作版诊断](../w03_n06_repair_evidence/w02-paired-diagnostic-01.json)：两版同在回忆准备站 `RECALL_TIMEOUT`，16 项检索、模型/外部调用 0；旧约 1063ms，新约 1049ms。 | 兼容阻断仍 `PRESENT`；不能据此声称四份负载风险已解决或历史原因唯一查明。 |

上述增量的**最终同版验证**：[N06 返修测试索引](../w03_n06_repair_evidence/test-index.md)记录专项 32/32 PASS（155.062 秒）、兼容 176/176 PASS（350.243 秒）、完整回归 1768 项中 1767 PASS／1 既有 Win1314 SKIP／0 FAIL/ERROR（1883.314 秒）。三个集合交叠，不相加；源码/测试/资源 304 项指纹 `sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf`，各次运行前后相同。旧兼容及全量 ERROR、中断和辅助错误仍是有效历史，W02 超时风险没有通过改预算消除。N06 三项仍仅为 `IMPLEMENTED_NOT_ACCEPTED`、`EVIDENCE_CONFLICT=PRESENT`，待规划窗口独立复核。
