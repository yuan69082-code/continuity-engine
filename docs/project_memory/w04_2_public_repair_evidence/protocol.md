# W04-2 公共验证阻断续修协议

用户本次明确授权调查并最小修补 W02/P18 公共实现；替代旧报告仅调查的停止点。不是新阶段，不改历史验收，不授权 Git 写入或 W04-3。基线见 baseline.json：314 项源码指纹 61bb34…；原91成果、70保留材料、保护项未变。

## 预先限定的第一轮诊断

1. 原五个 W02 失败用例各一次，断言、负载、1000ms不变。插桩覆盖每次准备中的 Router、Composer、来源/权限复核、候选解释、操作日志和能力账本读字节、解析、完整校验及副本。记录作用域和命中次数；嵌套时间不能相加。测量有开销，与旧未插桩失败分列。
2. 原两个 P18 用例各一次，跨进程记录 owner/checkpoint 锁申请、取得、释放及保存、控制提交时序。记录安全状态字段，不记录私密正文。用进程内缓冲避免每个事件写盘改变持锁时间，退出时独立落盘。核对 BUSY/AVAILABLE 对应区间及 STOP 是否持久化。原等待和断言不变。
3. 新实验必须回答新问题，先登记目的和有限次数；不反复运行求绿。若断言本身存在实质矛盾，停受影响项，提交证据等待用户决定。

## 逐项矩阵（调查中）

| Planning Item | 现有入口/候选范围 | Code Change | Test | Acceptance Result |
|---|---|---|---|---|
| W02/N02/T03—T06、适用T18，D-084 | AssociativeRecallService、InputContextSource、JsonIntegrationResultLedger、Router/Composer及实际来源复核 | 证据定位前不修改 | 五个原反例一次分段测量；随后同例及权限、撤销、损坏、恢复对照 | IN_PROGRESS，未验收 |
| P18控制与恢复 | JsonRuntimeRepository.file_lock/transaction/save、PersistentRuntimeService控制/运行/观察 | 证据定位前不修改 | 两个原反例一次跨进程时序；随后唯一宿主、CAS、幂等、PAUSE/STOP对照 | IN_PROGRESS，未验收 |
| W04-2同版门 | 原专项71、兼容414、最终全量 | 不改旧测试/时限 | 定点完成后固定同版验证 | BLOCKED，先定位公共失败 |

禁止修改保护文件、数据、规划、版本、70保留材料，不改变授权/计费/单一账本/持续运行。具体修法及公共影响须先记录后实施。历史F1/H1/F2 UNKNOWN和全部失败照留。
