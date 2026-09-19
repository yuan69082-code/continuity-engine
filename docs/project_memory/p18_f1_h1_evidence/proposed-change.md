# 公共实现最小补修范围：等待用户明确确认

本次用户要求：公共 Scheduler、C1、公共仓储等共用实现修改前，先说明必要性、文件、影响和兼容验证，等待明确确认。本文件是待确认方案，不是已完成修复；当前没有修改运行源码或正式测试。

## 已有反例为什么需要改实现

1. F1 同流程：真实读句柄阻止第二次 SubjectState 原子替换；操作系统返回 PermissionError / errno 13 / winerror 5。读者在错误分类前关闭句柄，现行 `_replace_contended` 的 DELETE 探测已成功，返回 False，原子写入退出。随后同一任务 UNKNOWN，运行时 WAITING_VERIFICATION，revision 2 / token_used 640。Frozen Clock 仍为10:02，查询水位10:02:05，原测试不会再推进时间，因而超时。补推进5秒可通过原事实恢复，不产生第二次模型调用或扣费。
2. H1 同流程：运行时 checkpoint 合法读者阻止 WAITING_RESOURCES 的替换。写回失败被 `_tick` 当作 WORK_PORT_UNAVAILABLE，随后 BACKOFF 保存成功，next_check_at 为当前时间+5秒。原冻结时间的观察器等不到资源等待。当前这个读取/写入函数与历史H1源码存档的函数AST一致。

不能通过改观察超时或推进测试时钟消除这些反例，也不能把完整 UNKNOWN 一律当成未执行。应处理已确认的文件竞争/可写性复核边界。

## 只拟修改的运行文件

- `src/continuity_engine/storage/json_repository.py`：补齐现有 P18 显式启用的原子替换处理在“短占用已经解除”时的判别缺口。保持有界等待、旧文件字节/CAS核对、每次重试前现行授权回调；重新核对目标及自建临时文件的适用访问条件。不得只因 errno13 就重试，普通权限拒绝、路径/磁盘错误仍拒绝，不无限重试。没有显式 retry guard 的其他阶段调用保留原行为。
- `src/continuity_engine/storage/json_runtime_repository.py`：仅将P18 checkpoint的原子替换接入经验证的有界处理，保持同一事务锁、generation、revision及控制内容绑定。重试的是同一份checkpoint写入，不重派发工作、不重新扣费、不改STOP。状态冲突与损坏仍失败关闭。

不拟修改公共 Scheduler、C1、Thinking、ResourceManager、权限、状态格式或外部契约；不新增任何权威或账本。若具体实现必须改变上述限定，先再报告。

## 影响和验证

公共SubjectState存储文件虽然跨阶段使用，但新增处理继续限定在显式P18调用授权内；P18内部checkpoint另有原控制锁。必须实测保持无guard旧路径、普通拒绝、同一事件重放、CAS和旧格式兼容，不能仅根据限定声称没有影响。

准备将本目录有效反例纳入正式P18测试（`tests/test_p18_persistence.py`及必要新增P18观察持久化测试文件）。原测试断言、25秒观察期限、原1480测试身份全部保留。新增测试单列。

验证顺序：本目录相同反例/正向对照 → 真实进程原F1/H1流程 → 短/长期占用、权限拒绝、目标/临时文件变化、STOP/PAUSE、CAS、状态提交返回丢失、零重复效果/扣费 → R1/R2及P18专项 → SubjectState/Evolution/事件并发、Awakening、资源、C1、P08/P09/P17受影响兼容 → 最终代码固定后一次完整回归。失败先保留，禁止反复全量碰运气。

## 历史结论边界

这是当前真实可复现机制和必要修复范围。即使新反例修后通过，也不补写历史F1/H1缺失的原始系统证据，不自动宣称历史已经唯一归因；F2亦不被预设为同一事件。P18 IMPLEMENTED_NOT_ACCEPTED、EVIDENCE_CONFLICT=PRESENT；不D-073、不Git写、不P19。
