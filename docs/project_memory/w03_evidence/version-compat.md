# W03 内部记录与旧版兼容

- `continuity.item_records` 是原 `SubjectState` 下的**可选内部字段**。旧 JSON 不含它时按空事项集合读取，重新序列化仍不补写空字段；原 `continuity.unfinished_items` 字符串列表继续读取。事项变化只经原 Action Gate、Evolution、revision 和单一 SubjectState 仓储。
- W03 没有新建 Scheduler 队列。`UnfinishedItemService.ready` 只计算有来源、未终结、愿意推进且等待条件已满足的机会；`due_at` 表示期限、影响排序，不是开始许可。正式常驻运行联动由 W05 核验。历史成功动作仍从原 E5-A 回执核实，不声明生产 Adapter 的 exactly-once。
- 当前认识仍放在原 P15 `relationship.objects` 主观解释文档，文档结构和版本 `p15-relationships-v1` 不变。W03 认识对象、别名、同源独立根、反证和变更理由是从当前 Learning/Event 及原 Evolution 历史重建的视图，不成为第二事实源。旧 P15 内容不具备 W03 注解时照旧可读，不被误称为新式认识。
- 必要核心使用内部 `ContinuityCoreGates.essential_core`。显式启用时，正常 C1 `prepare` 和 `before_thinking` 在提供 Thinking 输入前核对身份、关系、当前 revision 与 Composer protected 片段；缺失、过期、预算不足不能默默省略。关闭时保留原接口和已验收旧路径，后续 W05 核验持续运行入口的启用配置。模型替换沿既有 Thinking 输入接口，未修改模型权重。
- 所有新 TEST 仅用隔离 Fake 和可信测试时钟；正式七文件、六份冻结外部 Schema、外部接口、`pyproject.toml` 与版本 `0.1.0` 未授权改动。生产恢复、人物页面和真实设备/账号仍为后置能力。
