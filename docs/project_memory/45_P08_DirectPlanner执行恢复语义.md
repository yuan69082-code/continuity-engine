# P08 Direct / Planner / 同通道恢复语义

> P11 现行门：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-058 已登记用户正式验收。监工独立原反例 2/2 PASS、P11 45/45 PASS（8.371 秒）；39/833 全量等修复前结果继续作为历史保留。本次仅验收归档，不运行全量。[P11 验收入口](58_P11_测试索引与验收入口.md#p11-accepted)。

> 下文的 P08 收口与后续未授权状态均为当时记录；D-053 是后续独立授权，不改变 P08 十二项 ACCEPTED 或原有限泛化边界。

> P08 验收时的快照（历史保留）：当前 P08 / Engine side / 十二项均 `ACCEPTED`，用户于 2026-09-04 正式验收（D-052）；D-051 的有限授权与历史仍有效。本文件不修改外部 Capability v1，不扩大方案 A、不代表生产 exactly-once，也不授权生产 Adapter、P09/P17 或 Git 操作。P08 Vio dependency=NONE，P09—P23=NOT_STARTED。

## 1. 身份与输入

choice 密封 subject/environment、producer/decision、snapshot hash/revision、合法 fragment IDs、trigger、步骤 DAG、时间和 planning requirement。每个 request 绑定父 choice 全量 canonical 输入、step/plan、Adapter ID 和能力 policy hash。operation 身份不含内容 hash：同身份不同正文会冲突而不是另建执行。各 step 的 operation/request 唯一，不能覆盖兄弟步骤。producer 独立登记的 choice 必须精确匹配；原 P06 必须 COMPLETE，snapshot/trace subject/environment/revision/route/manifest 一致。当前 Context 有效性是新执行门，不是已发生事实的抹除门。

首次保存全部 request 身份后才允许执行。每个新执行前再次验证 Context，防止步骤间失效。计划只有不可变结构和引用；所有等待、完成、失败均从唯一 capability attempt 历史派生。

## 2. 恢复顺序

1. 加载原账本及精确 request，全部历史重新验证内部状态/证据约束。执行成功或失败必须有 receipt，先查询原绑定 Adapter 并逐字段比较；无回执 EXPIRED 必须查询得到类型化 NOT_EXECUTED。只有经相应证据核实的终态才返回原 result；不读新时钟、不再 execute、不改 result hash。缺失、UNKNOWN、不可查询、漂移或本地停止决定与真实执行冲突的历史拒绝消费，也不能放行依赖。
2. 未完成：先 query 原 request、原 Adapter，不先假定失败。
3. 有可验回执：检查 request hash、subject/environment、step、Adapter 与完成时间，并由可信 query 再验，追加成功或 terminal result。
4. query UNKNOWN、查询异常或非协议查询值：保存 UNKNOWN，保留等待；即使显式 retry 或 choice 已过期也不 execute、不推断 NOT_EXECUTED。
5. query NOT_EXECUTED：有先前 attempt 时必须显式受控 retry；重试及新步骤都要求当前 Context 有效且所有执行门通过。旧 request 可以在 Context 失效时查询，但不能据此获得新 execute 权限。
6. 所有门通过：保存 PROPOSED，再调用 Fake；结果再次核验后追加同一账本。
7. Fake 已写 receipt、Engine 尚未保存 result 时崩溃：重启 query 找原 receipt，不再 execute、不再计 synthetic credit。

8. 当前 Context 失效：原请求身份与可信恢复归属验证不变；允许归档原已执行回执、返回经核实的原终态，UNKNOWN 继续等待。未登记 request 不可新增；后续未执行步骤被阻断。权限/确认/资源/Recoverability/Reality Boundary 当前变化不阻止原事实归档，但继续阻止新执行。

重复结果按完整 result hash 返回原 attempt；成功及 terminal 后不接受新结果。跨 request/step/type/subject/environment 的结果均拒绝。没有无限重试、sleep、Scheduler 或生产补偿引擎。

## 3. 门禁与事实

PermissionProvider、RiskEvaluator、ResourceEvaluator 沿用既有 Action 实现。拒绝确认、权限、预算、恢复、Reality Boundary 时 Fake effect 数必须为零。预算同时检查整个选择的 step 数和成本以及单步 ResourceLimits；不是人格、思想或意志约束。确认绑定 request 的 idempotency key，不是公共输入 verified=true。未知执行证据不能被删除或当成未执行；Adapter/policy 漂移触发 identity conflict，不能换一个 Adapter 盲重试。

`p08-fake-receipts.json` 只保存 Fake 已发生的原子 synthetic effect/receipt；请求、attempt、失败、重试和完成事实归既有 Engine capability ledger。Fake 的 effect 与 receipt 同一个原子写入，测试验证的是这一明确能力，不推广为任意生产 Adapter exactly-once。不存在真实联系、工具、费用、供应商或网络调用。

## 4. 外部与历史

旧 model.generate 请求/结果继续使用原 JSON 和六份冻结 Schema；其 originatingSessionType 仍为 thinking，恢复原 ThinkSession。内部请求的 internalVersion 无法通过冻结 external validator，内部类型分派只在 Engine 本地协调/存储端口使用。旧格式 1 和混合格式 2 的兼容测试只使用临时目录，不读取或迁移正式主体数据。

不重新路由、不全库扫描、不创建 Context/Memory/事实权威；不让 P07 contested/isolated 结果变为执行授权。本阶段不做状态变化；任何未来合法状态变化仍须由既有 Action/Evolution 唯一路径完成。

## 5. 本次语义替代与历史

初版“已有终态直接返回”及“入口一律要求 Context 当前有效”在 36/678 已通过测试之外被监工反例推翻。2026-09-04 两个正式回归先得到 2/2 FAIL（0.487 秒），随后最小修复并保持原失败断言。现行规则是“历史独立验真后重放”和“恢复事实不等于授权执行”，不得把本节写成首次即正确。

## 6. 无回执终态与本地停止决定（第二轮返修）

| 内部状态 | 结构约束 | 追加/重载消费的独立证据 |
|---|---|---|
| PROPOSED | READY_TO_EXECUTE、无 receipt | 只表示执行前 proposal，不能放行依赖或证明效果 |
| UNKNOWN | 无 receipt，不允许假称 VERIFIED_RECEIPT/CHOICE_EXPIRED/READY_TO_EXECUTE | 保持等待；查询失败、非协议值不是未执行证明 |
| SUCCEEDED | VERIFIED_RECEIPT；匹配请求、状态和时间的 ActionReceipt | 原绑定 Adapter query 返回完全相同 receipt |
| FAILED_TERMINAL | 与成功相同的执行证据要求，receipt 状态必须失败 | 原绑定 Adapter query 返回完全相同失败 receipt；不能用 receipt=None 假定失败 |
| EXPIRED | CHOICE_EXPIRED、同名 gate、完成时间不早于 choice 到期、无 receipt | 原 Adapter 必须明确返回 ReceiptQuery.NOT_EXECUTED；字符串同名值、UNKNOWN 或异常均不够 |
| CANCELLED / FAILED_RETRYABLE / 其他 | INTERNAL_ACTION_STATUS_UNSUPPORTED | 本阶段拒绝，不建设新取消或通用执行系统；外部/模型状态枚举不变 |

领域结构拒绝使用 `EXECUTION_RESULT_REQUIRES_RECEIPT`、`INVALID_LOCAL_EXPIRY_DECISION` 等稳定错误；协调器使用 `EXECUTION_FACT_UNVERIFIED_OR_DRIFTED`、`EXECUTION_FACT_UNVERIFIABLE`、`LOCAL_STOP_NOT_EXECUTED_UNVERIFIED`、`LOCAL_STOP_CONFLICTS_WITH_EXECUTION_FACT` 区分失败。构造与反序列化、InternalActionAttempt 保存、历史消费和终态/依赖恢复均遵守同一约束。重算 JSON hash 不会绕过语义或可信查询门。

过期只撤销未来执行资格。尚未归账的实际成功即使在当前 Context 失效、所有新执行门关闭时仍可恢复原回执；不得因过期写成“之前未执行”。合法零效果过期保持成立，重复查询确认 NOT_EXECUTED 后精确返回原终态；不新增 effect/credit，不读新 clock。历史 EXPIRED 与真实 SUCCEEDED/FAILED_TERMINAL 冲突时拒绝消费、不原地改写。未知状态不消失，后续步骤仍不能执行。

本轮先记录 2/2 FAIL（0.467 秒）：无回执 FAILED_TERMINAL 被接受、重启 FAILED；重算 hash 的 EXPIRED 重启 FAILED/query=0，二者真实 effect=1。此为原 46/688 通过之外的新漏洞，失败历史与修复后的定点矩阵保留在施工日志和测试索引。

## P10 正式验收收尾（2026-09-05，D-056）

P00—P10 = ACCEPTED；P10 / P10 Engine side / P10-01—P10-12 = ACCEPTED；P10 Vio dependency = NONE；P11—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行 P10 验收阻断已闭合）。

规划监工最终独立核对确认 Engine checkpoint `0115733d75f854e0d7c39062d8cb328a97995354`、Assistant 最终代码提交 `90f112b8be4617feb2d6387ceb2f77603302cee6`、P10 工程检查 14/14 PASS、原 770 项与新增 24 项身份完整，以及 [CI run 33896418682](https://github.com/yuan69082-code/continuity-assistant/actions/runs/33896418682) 794/794 PASS、0 SKIP、0 FAIL。Temp 内远程干净克隆的构建、安装、Golden、来源和两个 Fixture 入口的路径隔离验证通过；冻结边界、正式 7 文件及版本 0.1.0 未变。

D-056 登记的是用户此前给出的条件式验收在独立核对通过后生效。当前冲突归零不改写历史：首次 Temp 失败、Windows 大小写漏项、旧 CI failure、统计入口导入失败、辅助工具错误、各次 SKIP，以及 P09 segment 10 stderr 缺失且根因 UNKNOWN 均保留。P11—P23 未开始；不创建标签或发布。
