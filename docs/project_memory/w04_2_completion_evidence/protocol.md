# W04-2 两项获准续修方案

本次用户明确批准原待确认的两项；不是验收或新阶段。main/HEAD fc185843…、315项源码1a0f355a…、194成果、70保留与保护组已逐路径核对一致；baseline.json保留修改前清单。原报告/失败/cProfile输出不改，原P18测试全文另存before.txt。

## 精确范围及复用

- tests/test_p18_runtime_contention.py：只调整获准两个测试的同步与计数区间，增加专用观察/STOP重试辅助及受控回归。通过正式runtime.main启动；TEST事务hook只用于在attach提交后明确通知，及可控地持锁。stderr仍是产品原诊断。每段连续占用精确1 BUSY、释放后1 AVAILABLE；停止在原15秒观察期限内以同一身份重试，限RuntimeCheckpointBusy，忙时验证未落盘。产品0.25秒和运行实现不变。
- src/continuity_engine/services/device_operation_service.py：将指定回执身份绑定到原Router request_id，采用固定长度摘要，不扩公共契约。
- src/continuity_engine/services/execution_context_source.py：识别该只读查询绑定，原E5-A当前结果仍全量核验；先选目标再按原限额保留其他候选，目标提高查询相关性/激活、其余降低本次相关性，经原Router排序、Composer保护核心及2048预算。非定向调用保持原行为；不新增事实或授权，不借同根替代目标。
- tests/test_w04_2_history_selection.py：双目标/顺序/合法标识、预算不足、撤权/途中撤权、过期、同根、重开、重复只读与旧非定向路径。
- 本目录及必要共享工程档案；保留已有_safe优化。本次不改Router/Composer、P18运行代码、原W04测试、时限、保护/正式数据/规划/70保留。

## 逐项矩阵与预定有限验证

| Planning Item | Code Change | Test | Acceptance Result |
|---|---|---|---|
| P18持续运行/控制有限等待 | 只改两个测试及受控观察，不改产品 | 原两个、连续两段忙、attach持锁STOP拒绝后同身份成功、非忙错误透传、STOP不复活 | IN_PROGRESS |
| W04/N21/T66/T67/T72、T18 指定回执 | 设备查询与原执行来源排序接线 | 双查询修前一次，修后新正式正反；原同根/来源撤回/过期/重开 | IN_PROGRESS |
| W02/N02/T03—T06 | 保留已做文件检查优化 | 无cProfile：原5失败场景各一次；原两种负载再各一次（专项中有交集另报）。不再重复重度profile | IN_PROGRESS |
| 同版交付门 | 固定源码再验证 | 新定点；W04-1/W04-2专项；原414项公共兼容；最后一次unittest discover全量 | NOT_STARTED |

先用新增双查询回归保存修前失败一次；P18修前两个受控反例引用已保存原始输出与原测试hash，不机械重建已证明交错。每次新失败先分析，不循环到绿。全量前不并行运行其他测试，不改变对应源码。

PLANNING_CONFLICT：此前两个待授权选择已由本次用户解决，尚待实现与验证；不是证据验收。EVIDENCE_CONFLICT仍PRESENT直到独立复核。W04-3、生产设备、页面、后续长期联动均未开工。历史F1/H1/F2 UNKNOWN与1314 SKIP保留。

辅助读取记录：本次首次搜索误用了三个不存在的Router文件名，搜索工具报文件不存在；随后定位到实际context_router_service.py/context_composer_service.py并阅读。未执行Engine，不算行为失败。

新增测试history-before-01首次使用过长TEST根前缀，临时awakening文件路径超过Windows常见260字符边界，setUp中FileNotFoundError，尚未到历史查询反例。仅缩短新测试目录前缀，与原w04-2夹具一致；不改公共存储、不把该辅助错误计为本次目标反例。原输出保留，以新标签取得真正修前证据。

history-before-02使用了带斜线的新增测试身份，现有action_planning.identifier仅允许字母/数字/下划线/点/冒号/连字符（160字符内），正确拒绝。修正新测试数据为合法不同标识，保留该辅助错误，不扩大身份契约。

history-before-03有效修前反例：1个正式测试的2个子断言ERROR（同一回执正序/反序均未就绪），其余目标正常；不能将两个子错误写成两个独立测试。

targeted-after-01：30测试，26PASS/4ERROR。四个新增拒绝测试预期了EnvironmentAccessError，但原P17消费边界正确将过期/撤权/来源变化映射为ExecutionError(DEVICE_SOURCE_NOT_CURRENT)。仅修正新测试为该确切类型与静态码，不改变实现或原断言；不是吞异常。P18原20及新增2均PASS。另增真正持锁拒绝后自动释放的受控测试，专门证明STOP辅助重试分支使用同一身份、忙时未提交，非靠时延猜测。

targeted-after-02为31PASS。固定最终代码前进一步按“保留其他冲突材料”核对选择契约：最终方案只给当前指定目标设置查询相关性/重要性/激活为1，其他候选仍保持原.95/.8/0，不降低到阈值边缘；原Router权重使目标最低.8高于其他执行候选最高.7875，Composer必要核心仍优先。该优先级只属于本次检索候选，不改事实内容/置信度/SubjectState。普通查询不计算目标绑定摘要。新增一项从正式入口观察原候选集合和保留值的测试。此后所有最终结果重绑定新源码，前31PASS仅作中间结果。
