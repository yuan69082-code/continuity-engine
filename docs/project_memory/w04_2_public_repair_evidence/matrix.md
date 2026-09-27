# 本轮逐项矩阵

| Planning Item | Code Change | Test / Evidence | Acceptance Result |
|---|---|---|---|
| W02/N02/T03—T06 当前来源核验及性能 | JsonExternalProviderRepository._safe同次元数据合并，当前读取不缓存 | registry-before-01→registry-after-01；原五场景、两次额外固定负载；compatibility-current-01；同工具CPU修后1PASS/1ERROR | IMPLEMENTED_NOT_ACCEPTED，仅已证实放大机制，插桩四份负载仍超时 |
| P16来源、权限、隔离与原W02恢复 | 不改权限/账本/回执，读取仍原入口 | 新7项、原P16/W02公共兼容 | 本次兼容结果见索引，非验收 |
| P18控制有限等待、唯一宿主、PAUSE/STOP | 原运行实现和原测试未改 | locks-profile-01；locks-controlled-01及原始跨进程锁时序 | BLOCKED，测试同步/区间断言需确认 |
| W04-1原三处返修 | 无修改 | w04-1-final-01 29 PASS | 原D-087验收保持 |
| W04-2模拟闭环/同根历史查询 | 本轮原实现未动 | special-final-01正式49项中48PASS/1ERROR，另1导入辅助ERROR；history-pair-01稳定定位预算选择 | BLOCKED，新接线缺口待授权 |
| 同版完整回归 | 未启动 | 先处理两个冲突/缺口，禁止碰运气重复全量 | BLOCKED |

原71/71专项是本轮开始前旧版本证据，不能替代当前专项；历史矩阵保持原文。
