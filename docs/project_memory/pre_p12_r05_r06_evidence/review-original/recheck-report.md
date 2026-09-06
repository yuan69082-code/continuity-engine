# R01—R08 修复后的独立复核

日期：2026-09-06。Engine HEAD：`5f25d0cef3798aa380d457ae670db30ee1b47407`，审查对象包含当前未提交的修复工作区。

## 结论

**本轮暂不建议验收或进入 P12：R05、R06 仍各有一项需要补修。其他六项在本轮范围内通过独立复核。**

不是八项全部返工。原先已复现的 15 项场景，经下述两处必要的测试机制适配后均通过；新增六项边界检查中三项失败，归属于两个根因。原有已修好的并发写入、收缩权限、零预算恢复、UNKNOWN 公平性、部分记忆合并和 TEST 跨主体唤醒不应被撤回。

| 项目 | 本轮结论 |
| --- | --- |
| R01 并发事件 | 通过；独立检查不同事件、同事件真实 update ID、同 ID 不同内容冲突 |
| R02 权限限制 | 通过；禁止扩权/恢复撤销，合法收缩保留；旧权限测试调整有依据 |
| R03 模型预算恢复 | 通过；原零预算反例不再执行 Provider，已有事实恢复仍有回归覆盖 |
| R04 调度 UNKNOWN | 通过；30/60 秒轮询时健康任务前进，冲突退避与多任务查询有覆盖 |
| R05 资源请求身份 | **未完全闭合：拒绝决策分支的并发身份检查仍缺失** |
| R06 学习固化 | **出现兼容性退化：刚验证通过且证据未变的记录被固化拒绝** |
| R07 部分重叠记忆 | 通过；新增根进入结果，别名来源链和伪造根拒绝保留 |
| R08 TEST 主体绑定 | 通过；A 引用 B 的 cycle 被拒绝，B 的唤醒与资源副作用均为零 |

本报告是独立复核意见，没有改写任何 Engine 验收状态、决策编号或历史 ACCEPTED。

## 发现一：R05 拒绝分支仍可为同一请求写入重复/矛盾决定（P2）

位置：[JsonResourceRepository.save_decision](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_resource_repository.py:112)，调用处：[ResourceManager.request_resources](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/resource_manager.py:114)。

服务入口先查 request_id/session，但该预检查在仓储事务锁外。允许分配分支 `save_allocation` 已在锁内重复检查稳定身份；拒绝分支 `save_decision` 却只检查新生成的 decision_id，没有在锁内复查 request_id，或服务入口要求的已分配 session 约束。

独立复现采用两个正常 ResourceManager/Repository 实例，只在策略调用边界同步线程，实际策略、申请内容、文件持久化均使用原实现。

| 场景 | 当前结果 | 应有结果 |
| --- | --- | --- |
| 相同 request_id/session，同时申请两次超额额度 | 两次均返回普通 denied，同一 request_id 保存两条 decision；扣费 0 | 仅一个稳定请求记录，重复调用明确冲突拒绝 |
| 相同 request_id/session，一份申请 10、一份申请 10000；确保允许分配先写入 | 返回 allocated 与 denied，同一 request_id 同时保存批准和拒绝两条记录；实际扣费 10 | 首个结果保留，第二份同身份不同内容请求应身份冲突拒绝，不能追加相反决定 |

对照：相同身份并发申请两次 10，当前已有修复可以做到一次分配、一次明确拒绝，只有一条 decision/usage。因此问题不是“所有并发分配仍双扣费”，而是**拒绝写入分支漏掉相同的事务内稳定身份校验**。

本次没有复现额外资源扣费；准确影响是请求历史失去唯一性，同一请求身份出现互相矛盾的政策决定。它违反本轮选定的“重复请求明确拒绝”方案，不能仅因扣费正确就宣称 R05 全部闭合。

补修方向：在既有仓储写事务内，对拒绝决定同样检查稳定 request_id 和适用的已分配 session 约束；两类保存路径的身份规则保持一致。不删除旧记录、不新增账本，不以在服务入口再加一次无锁检查代替事务保护。

对应探针：

- `test_extra_concurrent_denied_resource_requests_reject_duplicate_identity`
- `test_extra_concurrent_conflicting_resource_request_cannot_append_denial`
- 正向对照：`test_extra_concurrent_allowed_resource_requests_allocate_once`

## 发现二：R06 验证和固化采用不同置信度规则，拒绝未变化的合法验证（P2）

位置：[validate_learning 既有计算](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:240)、[新增 _verify_current_support](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:402)，尤其第 417 行。

验证入口保留 `max(target.confidence, learned_confidence)` 的既有语义；新增固化重查却只使用“平均置信度＋独立证据加分”，没有按相同规则处理目标本身的有效置信度。

独立场景：三个来源独立、内容一致的候选，置信度分别为 `0.95、0.2、0.2`。调用正常 validate 后返回 VALIDATED、confidence=0.95。没有撤回证据、没有改根、没有降低置信度，也没有任何并发变更，立即显式 confirmed=True 调用 solidify。

- 新代码：重算 `(0.95 + 0.2 + 0.2) / 3 + 0.2 = 0.65`，抛出 `current support no longer meets validation requirements`，trait_count=0。
- 修复前对照：从既有 HEAD 只读获取旧 LearningService，在内存中加载，运行同一探针，正常创建一个 trait。没有 checkout、回退或修改 Engine 文件。

这不是要求放过已失效证据，也不是要求跳过用户确认。它说明新增防护同时改变了未变化合法输入的处理规则，使验证和固化两个入口自相矛盾。要改变既有置信度政策需要明确说明并取得决定，不能悄悄作为“重验支持证据”引入。

补修方向：核实当前支持仍有效后，按一致、可解释的既有置信度规则判断。保留拒绝已否决支持、根重叠、数量不足、真实置信度下降的测试；不能简单恢复盲信旧聚合置信度来让此反例通过。

对应探针：`test_extra_freshly_validated_learning_with_unchanged_support_can_solidify`。

## 实际运行结果

下列前三项是在当前 Engine 工作区独立运行，不是引用修复方截图中的测试数字。

| 验证 | 结果 | unittest 耗时 |
| --- | --- | --- |
| 修复方正式定点测试 | 39 PASS，0 FAIL/ERROR/SKIP | 3.609 秒 |
| 原有完整 Engine 回归 | 878 项：877 PASS、1 既有 SKIP，0 FAIL/ERROR | 413.707 秒 |
| 独立原场景＋扩展边界 | 21 项：18 PASS、3 FAIL，0 ERROR/SKIP；失败归属 R05/R06 | 1.443 秒 |
| 旧 LearningService 的同输入对照 | 1 PASS | 0.041 秒 |

全量仍绿不能消除额外反例。既有 SKIP 是 Windows symlink 创建权限限制，未将其计为 PASS。

原 15 项场景的两个适配：

1. R01 原 barrier 位于现已加锁的写入点，会等待被锁挡住的另一线程，且原成功集合可能为空。本轮独立探针改为第一写入暂停、主线程有界释放，要求确有成功返回且所有 update ID 均在持久历史中，不依赖修复方测试的输出。
2. R05 用户明确允许拒绝重复。本轮接受准确的 ResourceValidationError，同时断言第二次零写入、首笔仍可结算为 8，而不是强制实现精确结果重放。

其余 13 项原探针代码通过继承保持不变。额外六项包括并发同事件/冲突身份、资源允许/拒绝/混合并发和学习合法输入对照。

旧 `test_permissions.py` 中 45 个断言 AST 与 HEAD 相同。两处 Fixture 原本把精确 scope `memory_manager` 替换为另一个精确名称 `memory_manager:project-only`；当前权限实现没有冒号层级语义。改为先明确授予两个范围、再缩小到一个范围是合法对照修正，不是删除或弱化原断言。

修复方首次全量的 3 ERROR 和历史辅助失败原件仍存在；没有以其后来 PASS 覆盖旧事实。本轮自身也有一次定点启动目录错误：在规划目录用 `python -m unittest tests.test_pre_p12_repairs` 导致 tests 导入失败；改在 Engine 根目录运行后 39 项通过。这是复核入口错误，不计为第三项引擎缺陷，原输出保留。

## 文件安全与范围

本轮只读核对 933 个已跟踪/未跟踪、未忽略文件，其路径＋SHA-256 清单聚合在检查前后完全一致。192 个最终源码/测试文件与修复方 stable-source-02 清单匹配；63 项保护文件与原 P11 验收基线匹配，无缺失或变化。

HEAD 未变；本地 origin/main ahead/behind 为 0/0，未联网确认实时远端。Git 仍为 24 个 tracked 修改、87 个 untracked，暂存区为空；其中本轮修复 80 文件、原有 P10 辅助脚本 31 文件的总数关系一致。`git diff --check` 通过。未暂存、提交、push、改分支、清理文件或修改 Assistant；测试业务数据仅在隔离 Temp/Fake 中生成。

复核前首次尝试输出全部哈希明细时，工具输出长度限制导致 JSON 截断、解析失败，未启动测试或写入 Engine；随后改为完整文件清单的聚合哈希并成功比较。发现无关 testdeps 目录不可读后未改权限，也未把目录扫描错误解释为引擎错误。

## 证据入口与重跑

- [独立反例源码](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/recheck_probes.py)
- [21 项独立输出，包含三个失败栈](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/independent-probes-01.log)
- [39 项正式定点输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/engine-targeted.log)
- [878 项全量输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/engine-full.log)：本轮捕获的完整非 verbose 合并输出，不冒充逐项命名日志。
- [旧版学习行为对照脚本](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/baseline_learning_check.py)、[通过输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/baseline-learning.log)
- [只读哈希与 Git 核对](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-recheck-20260906/readonly-audit.json)

任意目录下运行独立反例（PowerShell）：

```powershell
$env:PYTHONPATH = 'C:\Users\Administrator\Documents\continuity-engine\src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python 'C:\Users\Administrator\Documents\Codex\2026-08-24\https-github-com-yuan69082-code-continuity\reviews\engine-pre-p12-recheck-20260906\recheck_probes.py'
```

## 建议交回范围

仅对 R05 拒绝分支的事务内身份校验、R06 验证/固化置信度一致性作定点补修。保留其余六项成果、本轮全部失败及修复方历史记录。先补正式反例，再定点修复和兼容验证，最终代码稳定后一次必要全量回归。

不重新开启全面重构，不放宽六份 Schema、外部契约、正式数据、版本、Authority 或单一账本边界，不进入 P12/P17，不接生产 Adapter。完成后再交独立复核；本报告没有授权任何源码或 Git 写操作。
