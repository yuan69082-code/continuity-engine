# W04-3 R1/R2 定点返修

STAGE：W04-3 返修 IN_PROGRESS；不是 W04-4。用户授权实现、隔离验证、档案；不验收、不写 Git。
SOURCE OF TRUTH：现行索引及 v1.6/v1.6/v6.10 三份原文。具体 W04 子批次三、N14、T30—T32/T41、C11；N21 既有接线保留。
BASELINE：main / f64fb797ae4defae2dfd16278f38e89c8b13cd66；320项 ddb85f6…；142旧成果逐hash一致，70保留、63保护、3规划、7正式文件一致，暂存为空。详见 baseline.json。
ORIGINAL REQUIREMENTS：等待不阻塞其他合法工作，原身份续做；清理失败真实待清，当前条件恢复可继续，无未经确认永久次数上限。
FILES ALLOWED：temporary_tool_service.py；必要隔离夹具（优先放新增 tests/test_w04_3_repairs.py）；本证据目录和必要现行档案。旧 tests/test_w04_3_tools.py 等正式测试按原字节保留。
FILES FORBIDDEN：Scheduler/P18运行实现、规划/保护/正式数据、旧原始证据、70保留材料、版本、其他项目。若证明需改公共边界则暂停冲突项。
KEEP：原2need/轮、P18等待与PAUSE/STOP、W02 1000ms、Context2048、E5-A唯一请求结果、当前身份/授权/来源/资源；UNKNOWN先查、不重放。
TESTS REQUIRED：先2个真实宿主反例，再同场景对照及多事项/原认知维护/重开/权限/未知/控制/退避回归；固定代码后W04-3、W04-1/2、公共兼容和一次全量。每次唯一标签，保留全部结果。
PLANNING CONFLICT：目前NONE；EVIDENCE_CONFLICT=PRESENT。静态发现尚非实跑结论。

| Planning Item | 现有入口/疑点 | 拟修改/需证据后确定 | Test | Acceptance Result |
|---|---|---|---|---|
|R1/N14/T31/T18|RuntimeWork.needs 固定首项|复用原Scheduler已入队身份区分未入队，有限公平接纳，保留原调度|真实宿主两工具+native维护/认知，等待/恢复/重开/控制|IN_PROGRESS|
|R2/N14/T32/T41/C11|advance 清理总量3|每轮有界，原回执推导退避，当前条件恢复继续；不加业务账本|至少3次失败后自动续做，UNKNOWN/返回丢失/撤权/隔离|IN_PROGRESS|

调查有限计划：两项原反例各一次；遇辅助错误先保留并修夹具后以新标签取有效证据，不循环求绿。旧结果只引用为历史。
