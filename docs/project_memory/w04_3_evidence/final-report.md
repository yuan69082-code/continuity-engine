# W04-3 工具发现与临时接入交付

状态 **IMPLEMENTED_NOT_ACCEPTED**，交规划窗口独立复核和用户验收。D-090仅为开工授权；W04整体IN_PROGRESS，W04-4未启动。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，未自行关闭独立复核门。

## 实际完成

从原P16已授权发现入口取得真实候选回执，验证来源/版本/用途/依赖，通过原P08/P17/E5-A接入、核验、使用及结束。缺登录/新范围/预算/依赖时保留原任务等待；条件补齐后不再发现、不新建主体或第二连接。工具资料不能授权；发送/购买不会从普通工具权限推导。

单次、限时、持续连接各有结束规则。动作及纯观察均检查当前资格，失效不继续使用。清理失败/部分/未知分别保留待清理和原因，恢复先查原事实。技术不可用可走合法API/UI替代，权限拒绝和未知效果不能绕行。N21经原device.query、指定回执Router/Composer回流。P18可选work适配经原Scheduler继续等待任务，暂停/停止有效；不安装服务，不改变引擎寿命。

运行代码新增域契约与服务两文件、隔离Fixture一文件；只修改两处旧运行文件：ActionSpecification增tool.*内部参数核验，DeviceOperationService增可选临时资格门禁。旧调用未接guard时保持旧行为。新增46正式测试，旧正式测试文件和断言无修改。凭据只受控引用，使用事实仍在唯一E5-A，未增加Memory/SubjectState/请求账本。公共影响、恢复细节见[语义说明](recovery-semantics.md)。

## 同版验证

源码/测试/资源 320 项，`sha256:ddb85f6a7e49f8bf61c39717ea0e51c73ccb8efbd391aab17813ff6ead6a88a3`。正式身份 1909，原1863保留、新增46。以下是施工方本轮实跑，交叠不相加，不是规划窗口实跑或远端CI：

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-02](targeted-final-02.json) | 46 / 0 / 0 / 0 | 155.642 / 156.263 | 0 |
| [special-final-02](special-final-02.json) | 87 / 0 / 0 / 0 | 161.742 / 162.382 | 0 |
| [compatibility-final-02](compatibility-final-02.json) | 417 / 0 / 0 / 0 | 697.07 / 697.779 | 0 |
| [full-final-01](full-final-01.json) | 1908 / 0 / 0 / 1 | 2184.956 / 2186.189 | 0 |


原命令、stdout/stderr、退出码、耗时、执行前后完整源码分别在[索引](test-index.md)和各JSON。唯一SKIP为原Windows1314，不算PASS。完整回归一次，没有自动反复跑绿。原W02负载与1000ms、指定历史回执2048、P18控制测试在同版集合中保留。

## 失败与局限

新UNKNOWN收集接线、Fixture候选过长、纯观察到期门禁缺口均保留修前结果；探针observe-before/after展示同一反例修复。另有cancel-before真实复现待接入取消后原连接仍能创建：本批connect提交前补原close事实门禁，明确未执行/终态允许原清理闭合；cancel-after-final同探针通过，新增3项覆盖重开、提交交错、失败后清理。嵌套清理原锁EXECUTION_BUSY如实等待，不伪报CLOSED。诊断长路径、初次身份导入环境错误单独记录，不算Engine缺陷。全部过程见[调查记录](investigations.md)，旧历史未覆盖。

本机TEST接入/验证/清理设置成本0，模拟业务动作按原回执实际扣1 TEST credit；三进程返回丢失恢复及重放仍是一次效果、一次扣费、新发现0、新模型0。不是现实价格策略，也不证明真实服务质量或任意负载时延。

有界自动清理最多三份关联清理动作，仍失败则待清理；UNKNOWN先查询、不重发。旧host失权后不允许冒用清理权限，真实生产迁移/清理仍待P20/21。新续期必须有新有效条件及新连接；用户明确暂停/停止不自动复活。可选P18接线的实测聚焦单个待接入事务，每轮提供首个native need和首个工具need，多个同时待接入事务的公平推进尚未取证；不能据此宣称完整跨入口装配通过。真实账号/安装/订阅/设备/凭据/P22、W04-4、W05、P19均未开放。没有完整插件自动编写工程，也不是本批前置。

历史F1/H1/F2仍UNKNOWN，既有cProfile超时及原失败/SKIP照留。保留先前W02/W03/P00—P18、W04-1/2验收，不以本批通过倒改历史。

## 复核入口

[逐项矩阵](matrix.md) · [链路样例](chain-example.md) · [只读状态和恢复](recovery-semantics.md) · [固定源码与身份](frozen-source-03.json) · [精确成果清单](final.pending-files.md) · [70项排除材料](exclusions.json) · [终局审计](final.audit.json) · [进程清理](process-cleanup.json)。

本轮只读远端查询见[remote-read-01](remote-read-01.json)，当时main与本地基线f64fb797一致；不是push结果。无暂存/提交/push，未取得CI run/check，不宣称CI PASS。
