# W03 Engine 施工交付：待独立复核

状态：`IMPLEMENTED_NOT_ACCEPTED`。本报告只覆盖用户授权的 N03、N04、N06 与 T04/T07/T08/T09/T12、适用 T18；D-082 是开工决定，不是验收。W02/D-081 仍 `ACCEPTED`，W04/W05/P19 均未启动。本轮无 Git 暂存、提交或推送。

## 实际交付与可核对入口

| 要求 | 实际入口 | 证据及限制 |
| --- | --- | --- |
| N03 长期认识 | `src/continuity_engine/services/recognition_service.py` 沿原 Event、P15 Learning、Action Gate、Evolution 将经独立根核验的主体主观认识写入原 `relationship.objects`。同名不同归属分开，反例可争议、更正或撤回，旧演化理由仍可只读重建。`subject_growth_service.py` 消除同一根在同轮 Timeline/Memory 中重复捕获。 | `tests/test_w03_recognition.py`；原消息进入 W02 事件链后形成候选、验证、提交的隔离 TEST 成功对照。注解是真实内部输入中的受控解释假设，不代表自然语言模型在生产中已达到同等语义质量。 |
| N04 必要核心 | `continuity_core_service.py` 的内部 `essential_core` Gate 启用时，经原 Context Router/Composer 在 Thinking 前提供身份、关系和版本化保护片段；缺失、过期或预算不足显式拒绝。`core_status` 只读呈现核心、长期、临时层。 | `tests/test_w03_core_context.py`；旧 Gate 关闭路径和模型替换沿同一 Thinking 输入契约均有对照。正式启用配置与常驻运行全链留待 W05。 |
| N06 未完事项 | `domain/unfinished_item.py`、`services/unfinished_item_service.py` 在原 SubjectState 可选内部字段中保持唯一事项集合；更新经 Action Gate/Evolution/CAS，完成需事项绑定的内部事实或原 E5-A 成功回执。`ready` 按可执行、紧迫、到期及 aging 有界排序，阻塞急事不占住其它机会；`read` 不推进业务。 | `tests/test_w03_unfinished_items.py`；旧 JSON 缺字段可读且不无故补写。W05 才验完整持续运行联动，不宣称另有 Scheduler 队列或生产 exactly-once。 |

两处最小只读入口是 `RecognitionService.read(context)`、`UnfinishedItemService.read(context)`，核心提供状态是 `ContinuityCoreService.core_status(context)`。查询经当前 Context、身份和 revision 复核，不调用模型、不提交学习或事项。实际实施位置与验收项逐条对应见[矩阵](matrix.md)；原始测试命令、前后源码指纹、退出码、耗时和失败见[测试索引](test-index.md)。[版本兼容说明](version-compat.md)记录旧状态映射及后置能力。

## 失败与修复历史

修前核心缺失、事项来源撤销、同一事件根双重学习捕获及期限误作最早开始时刻有真实反例；修补后相应正式测试通过。TEST 注入位置、Windows 测试根路径过长、测试断言保护层计数和一次导入环境缺失作为辅助错误单列保留。没有删除旧断言、改时限或重写历史输出。

固定 W03 源码/测试/资源指纹 `sha256:fb18d1c75f80219939ac0acb7c2099e2a7653be3115810ad3b6b687a8641bb7f`：

- W03 专项 `w03-special-final-02`：25 PASS、0 SKIP，101.762 秒，退出码 0。
- 受影响兼容 `w03-compat-final-02`：176 项中 175 PASS、1 ERROR，378.054 秒，退出码 1。ERROR 是原 W02 两独立根及派生材料联验在既有 1000 毫秒回忆时限触发 `RECALL_TIMEOUT`。没有将其写成兼容通过。
- 较早源码 `full-final-01`：1755 项中 1753 PASS、1 既有 Windows 1314 SKIP、1 同类 ERROR，1990.323 秒，退出码 1；其指纹是 `sha256:faf867faf3c9eeb4d9cb03698a30e931e9a67e5858ba7821529e19ba4065115e`，不能冒充最终版全量。
- 最终源码完整回归 `full-final-02`：1761 项中 **1759 PASS、1 既有 Windows 1314 SKIP、1 ERROR**，2013.319 秒，退出码 1。唯一 ERROR 仍是原 W02 `test_partial_derived_withdrawal_invalidates_integrated_reply_and_support` 的 `RECALL_TIMEOUT`。源码前后均为上述 `fb18d1…` 指纹。这是完整运行的真实失败，不能写为全量通过或用旧结果覆盖。

在隔离 Windows Temp 中从 Git HEAD 解出旧 `src/tests`，原 W02 单测也报相同 `RECALL_TIMEOUT`（`head-w02-deadline-01`）。限时诊断显示超时前有 16 项候选，原截止点约 1034—1036 毫秒；新事项解析累计仅 2.58 毫秒。由此不能断言该兼容错误是 W03 引入，也不能证明 W03 绝无影响。旧 W02 四份资料负载超时风险继续存在；本轮当前兼容尚未全通过，`EVIDENCE_CONFLICT=PRESENT` 交独立复核。历史 F1/H1/F2 根因仍 `UNKNOWN`，与本轮现象不合并。

## 范围与停止位置

本轮只在原 SubjectState、Learning、Context 和可读调度机会职责内施工。SubjectState 仍是当前主体状态权威，Event/Learning/Evolution 保留历史，E5-A 管现实事实；没有第二人物库、事项队列、请求账本、心理内容纠错或内部逐项审批。正式数据、六份外部 Schema、外部契约、三份规划、版本、63 项保护及 57 项排除材料须以终局审计核对。真实模型效果、P19 页面、P20/P21 正式恢复和 P22 服务仍 `NOT_READY`。

最终交回[终局审计](final.audit.json)与[精确成果/排除清单](final.pending-files.md)。全量的同一时限错误仍须独立复核：新功能专项通过，但不能宣称全部既有兼容与全量门槛通过；`EVIDENCE_CONFLICT=PRESENT`。本轮不自行验收或执行 Git 写操作。

终局只读检查：源码/测试/资源 303 项，指纹与最终专项、兼容和全量前后相同；63 项保护、正式七文件、三份现行规划及原 57 项排除材料均与开工清单一致。Python AST 解析 293 文件通过；所检 637 个本地文档链接无断链；新成果的常见凭据模式未命中；`git diff --check` 退出 0，但 Git 给出 LF/CRLF 转换提示，原始历史日志格式不改写。两项本轮测试进程已退出，未强制清理（[进程记录](process-final.json)）。

当前分支和本地 HEAD/`origin/main` 均保持开工 SHA `ec9c59054a599d028e39a80134abec6aa9802eba`；暂存区为空，已跟踪差异与新增文件均列在精确清单。终局实际远端只读查询返回 `SEC_E_NO_CREDENTIALS`，因此本轮不能再次证实远端 `main` 的实时 SHA，也没有可核验 CI 结果；开工时的远端核对仅作为当时事实保留。
