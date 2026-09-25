# W03/N06 定点返修与 W02 回忆时限诊断

状态：`IMPLEMENTED_NOT_ACCEPTED`；`EVIDENCE_CONFLICT=PRESENT`。本报告保留 W03 原交付及全部修前记录，不登记验收。

## 修前事实与处理

- `n06-repair-before-01`：连续终结第 65 个事项时，原当前集合达到 64 项，原 Evolution 校验报 `W03_ITEM_RECORDS_INVALID`。同轮另有旧格式测试夹具的事件分类错误、Memory 的 `ACTIVE` 大小写入口拒绝，以及 Windows 临时路径过长辅助错误，均作为原始证据保留，不冒充四个产品缺陷。
- `n06-repair-before-02`：修正夹具后，旧事项缺少明确迁移命令；合法 Memory 因原服务将 `ACTIVE` 与 `active` 比较而无法入站。
- `n06-source-before-04`：只修正上述入站状态比较后，真实局部反例显示不可用 Memory 仍被列为可推进；外部派生资料准备的夹具材料列表第一次未满足其原 canonical hash 约束，属于辅助错误。
- `n06-external-before-05`：保留根版本和原文、只撤销派生材料后，重开后的 `ready` 仍返回该事项；为本轮 W02-C 来源失效的有效修前反例。

修补限定在原 `UnfinishedItemService`：终态不再占用当前 64 项集合，原 Evolution 事件保留终态和原因，旧命令重放沿用原摘要；旧字符串事项只在主体明确提供列表位置、标题、列表 hash 且当前 revision 一致时，与新结构化事项在同一原 Evolution 事务中迁移（可在创建或已有结构化事项的合法转换时绑定），不按同名自动合并；Memory 可用性、原 Event/Memory 链及 W02-C 外部根和具体材料当前证明在推进前复核。只读结果在返回前复查来源变化。没有新队列、来源权威或请求账本。

## W02 同条件诊断

`w02-paired-diagnostic-01.json` 用同一 Python、相同长度隔离源码路径和同一 W02 用例分别运行旧 HEAD 和当时 W03 工作版，各一次。旧版第三次回忆 `1062.669 ms / RECALL_TIMEOUT / retrieved_count=16`；W03 版 `1049.201 ms / RECALL_TIMEOUT / retrieved_count=16`。两者均在 `associative_recall_service._prepare` 停止，模型和外部调用均为零。W03 版相关事项解析调用在先前诊断中累计约 2.58 ms。该单次对照未显示 W03 增加本链耗时，也未证明历史超时的唯一原因；W02 原 1000 ms 时限保持原样，当前兼容阻断需据最终运行如实记录。任何 W02 逻辑、预算或原断言均未更改。

## 验证索引

- 当前最终源码专项 `w03-n06-special-final-04`：32/32 PASS，155.062 秒，源码身份 `sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf`，前后一致。较早 `special-final-02/03` 的 31/31、32/32 PASS 仅覆盖各自当时源码，作为历史保留。
- 中断的 `w03-n06-compat-final-01.started.json` 仅为开始记录。发现旧命令摘要兼容风险后主动停止，没有完整结果，不计 PASS。
- `n06-existing-legacy-before-01`：已有结构化事项完成时才显式认领同名旧字符串的有效反例。首次实现拒绝合法绑定；补修只允许在原事项合法转换且精确旧列表指纹一致时同步移除。因发现该覆盖缺口，已开始的 `w03-n06-full-final-01` 被主动中断，只有 STARTED，未产生最终数量或退出码，不计 PASS/FAIL。
- `n06-memory-permission-before-01`：Context 未选中该条 Memory，细粒度撤销 `engine.memory` 来源权限时，原事项仍进入 `ready`。当前修补在 N06 来源核验中复用原 P05 权限端口，不更改公共权限政策。`n06-memory-permission-after-01` 是我输入错误测试方法名的辅助 ERROR，`after-02` 为正确命令 1/1 PASS；二者记录均保留。中途 `w03-n06-compat-final-02` 是更早源码的完整运行（175 PASS/1 W02 ERROR），不能用于最终源码；后续 `w03-n06-compat-final-03` 仅有 STARTED，被主动停止以加入细粒度权限反例，均不倒写。
- 最终兼容 `w03-n06-compat-final-04`：176/176 PASS，350.243 秒，退出码 0；最终全量 `w03-n06-full-final-02`：1768 项，1767 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1883.314 秒，退出码 0。两组与专项交叠，不相加；均为同一最终源码 `sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf`，运行前后相同。原 1761 项测试身份保留，新增 7 项。
- [终局审计](final.audit.json)：304 份源码/测试/资源；63 项保护清单、正式数据、三份现行规划及 57 项排除材料与开工清单一致，暂存区空。[精确成果与排除清单](final.pending-files.md)。本轮仅修补 N06 服务并新增正式测试；W03 原其余成果保持待复核。

终局静态核对：294 份 Python 源码及测试均可 AST 解析；本次相关文档 393 个本地链接均存在；明显密钥格式扫描无命中；`git diff --check` 退出 0（既有工作区换行转换提示保留）。审计清单列 270 项 W03 累计成果（含两份自引用清单），另 57 项排除材料原样保留。本轮测试子进程已退出。`main` 的本地 HEAD 和本地 `origin/main` 均为 `ec9c59054a599d028e39a80134abec6aa9802eba`、暂存区空；本轮实际远端只读查询因 `SEC_E_NO_CREDENTIALS` 失败，不能声称远端状态已核实。未进行任何 Git 写操作。

## 仍需独立复核

最终兼容与全量通过不抹去先前 W02 `RECALL_TIMEOUT`：旧 HEAD 与当时 W03 版同条件各一次均超时，单次对照不能证明最终版永不超时，也不能唯一归因。回忆逻辑、1000 毫秒时限和原断言未动；若要改 W02，须另行确认。旧同名字符串缺可靠身份时保持独立显示，不凭标题自动合并；明确绑定命令可在原 Evolution 链迁移。历史 F1/H1/F2 的原因继续为 UNKNOWN；Windows 1314 SKIP 不计 PASS；没有远端 CI 结果。本轮未验收、暂存、提交或推送，未启动 W04。
