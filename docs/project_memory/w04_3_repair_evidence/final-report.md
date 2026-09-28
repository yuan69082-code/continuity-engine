# W04-3 R1/R2 定点返修交付

状态 **IMPLEMENTED_NOT_ACCEPTED**。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，等待独立复核与用户决定，未自行关闭阻断。W04整体IN_PROGRESS，W04-4未启动；D-090仍仅开工授权。

## 根因与实际修复

静态复核线索经施工方before-02两个真实宿主反例复现：首个缺登录工具使后项永不入队；三份明确失败清理后自动路径不再续做。修前2 FAIL/0 ERROR，STOP前的任务、原请求、回执、效果和费用保存在原stdout。同反例修后通过，新增14项覆盖同时native工作、重开、UNKNOWN、部分清理、退避、控制和当前权限。

R1删除固定native首项/工具首项截取，读取原Scheduler已拥有身份，只为尚未入队的原需求提供本轮最多两个名额；原Scheduler仍管理既有等待、派发、资源和恢复。R2去掉连接全生命周期三次清理上限，每次advance最多一个清理，用上一份自动清理原回执时间退避，默认复用P18的5秒，可配置；条件变化、原授权和原资源逐次重查。UNKNOWN查询原事实，成功不重复，失败历史不删除。

运行只改temporary_tool_service.py，新增tests/test_w04_3_repairs.py；原测试文件、Scheduler、P18控制、资源/费用及其他运行文件相对本轮开工版无改动。没有第二队列、状态权威、请求或结果账本。原初版142成果全部保留。详细条目见[矩阵](matrix.md)、[恢复语义](recovery-semantics.md)。

## 同版验证

源码/测试/资源321项，`sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506`。正式身份1923，原1909保留，新增14。以下均为本轮施工方实跑，集合重叠不相加；不是规划窗口独立实跑或远端CI。

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-01](targeted-final-01.json) | 14 / 0 / 0 / 0 | 166.421 / 167.125 | 0 |
| [w04-3-final-01](w04-3-final-01.json) | 60 / 0 / 0 / 0 | 324.797 / 325.487 | 0 |
| [w04-12-final-01](w04-12-final-01.json) | 87 / 0 / 0 / 0 | 159.335 / 160.0 | 0 |
| [compatibility-final-01](compatibility-final-01.json) | 417 / 0 / 0 / 0 | 701.162 / 701.916 | 0 |
| [full-final-01](full-final-01.json) | 1922 / 0 / 0 / 1 | 2390.489 / 2391.61 | 0 |


命令、原始stdout/stderr、退出码、时长、运行前后逐文件hash见[测试索引](test-index.md)。修前失败及中间辅助ERROR、正确Context拒绝、未知结果均见[调查记录](investigations.md)，没有被后续PASS覆盖。最终完整回归一次，Windows1314 SKIP不计PASS。

## 保留边界与限制

同时存在native认知、维护与工具的正向场景实际取得认知revision和工具结果；不是关闭native或手工逐个advance冒充调度。旧Context在认知推进后仍正确拒绝。正常新步骤由原Wake/Perception/C1取得当前Context，不能靠本修补自动重绑旧请求。测试新生产器曾选入随后失效的临时结果而正确阻断，这些失败与辅助错误原样保留；任意调用方仍需提供当前有效Context。

等待/退避不会关闭整个主体；PAUSE/STOP、旧host失权与生命周期照旧。没有固定运行寿命或忙循环。原Scheduler容量、预算与当前资格仍可阻断，本机有限组合不证明任意无界任务公平性、生产性能或真实服务质量。

清理失败可在当前条件满足后继续，不代表无条件必能清理或过期使用复活。本机TEST业务效果/费用各一次，清理0成本为明确隔离配置；不替用户制定现实预算。真实账号、设备、生产凭据/服务、W04-4、W05及P19未开放。

历史F1/H1/F2仍UNKNOWN；原cProfile超时、旧失败/中断/格式提示和既有SKIP全部保留。原W02 1000毫秒、指定历史2048预算、P18控制等待未放宽。W04-1/2及其他历史验收不改。

## 复核入口与现场

[精确累计清单](final.pending-files.md) · [hash清单](final.files.json) · [本轮增量](repair-delta.json) · [70项保留](exclusions.json) · [终局审计](final.audit.json) · [进程收尾](process-cleanup.json) · [真实链路](chain-example.md)。

HEAD/main仍为f64fb797ae4defae2dfd16278f38e89c8b13cd66；未验收、未暂存、未提交或push。实际远端只引用初版remote-read-01的当时查询，本返修未取得新的远端/CI结果，不以本地origin/main冒充实时远端，也不宣称CI PASS。下一步仅独立复核。
