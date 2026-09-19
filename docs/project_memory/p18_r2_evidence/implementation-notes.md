# P18 R2 / F1 / H1 接续与实现记录

本轮仅用户已授权的 P18 继续返修。P18 IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT；不验收、不 D-073、不 Git 写操作、不 P19。R1 锁竞争成果已获规划侧定点复核，本轮保留。正常 start 仍默认持续运行，无消息、沉默、空闲及单项资源不足不结束宿主。

## 当前实现

- 在原 ThinkSession 增加可选内部 provider_execution：原 think/wake/subject/provider、时间、预算、Observation、不可变 Perception 的绑定 hash，以及追加式 PREPARED、ENTERED、RETURNED、ABANDONED 阶段。不是新的请求账本。旧格式没有该字段，仍读取兼容，绝不据旧 error 字符串推断未执行。
- P18 原生调用先保存 PREPARED；控制延后保留未完成会话及 CONTROL_DEFERRED 历史。真正调用前先保存 ENTERED；此后失败/中断一律保守 UNKNOWN。ENTERED 落盘与真实调用之间的崩溃也不能凭未观察到调用自动重发。
- Runtime 对可核验 PREPARED 经原 Native Wake/Thinking 路径继续，复用原任务/attempt/wake/ThinkSession 和资源预留。重新核对 Owner/STOP/生命周期、Context/权限/材料、Provider 可用性和资源；不再次扣预留，完成后原用量结算。
- 明确未执行但 Context 已失效时，原会话保留原输入并记 ABANDONED，原 Thinking 用量按 0 实际结算，原 Scheduler 经 NOT_DELIVERED 关闭。新评估 task identity 从原 task、think_id 和阶段证据确定性派生，能追溯前驱；不因普通 CANCELLED、STOP 或 UNKNOWN 另造任务。已经发生的原 Wake 费用仍保留。
- 检查同类入口时证实预算 Port 内的控制延后也会制造 FAILED：budget-control-before-01 真实 1 FAIL。仅 P18 显式阶段接线下，尚无会话/调用时的 RuntimeDeferred 原样向上延后；原预算失败、旧接口语义保留。
- 测试清理前诊断补充 ThinkSession 状态/阶段、原身份、Context 当前性、Action/Capability/效果、可信时间/水位/资源。TEST Native 异常仅输出静态码及引擎栈位置，不含异常文本、repr、正文或凭据。

## 修改范围

原内部类型、ThinkingService、JsonThinkingRepository、RuntimeCognition、Native Wake 接线；P18 Fixture/原进程测试的脱敏诊断，以及新增正式 test_p18_runtime_resume.py。R1 的 JsonRuntimeRepository/PersistentRuntimeService/竞争测试不变。冻结外部 Schema/契约未涉及。

## 已保留的首次记录

原样 12 项修前 11 PASS/1 FAIL；原样 4 项修前 1 PASS/3 FAIL。正式初五项 2 PASS/3 FAIL。扩展测试中的两处原费用/配置假设和锁文件读取辅助 ERROR 均原样记录，具体见 auxiliary-errors.log；没有调整既有生产资源政策或旧断言。

## F1 / H1 预定调查与限制

F1 原全量 1444=1442 PASS/1 SKIP/1 FAIL，不能改成通过。原现场 token_used=640、认知 UNKNOWN、宿主 alive，不足以证明 R2。旧临时根已被原控制器清理，缺 ThinkSession/调用阶段/异常链。

本轮保留原进程断言和 25 秒等待阈值；预定：原 12 项的九个时钟交错及普通/两个暂停点；正式“首轮 Evolution 完成时 PAUSE、推进时间、恢复”的有界场景；原失败进程用例在完整专项及最终全量中各执行一次。失败前均取扩展诊断，不因通过倒推历史根因，不做跑到绿循环。

H1 仍 UNKNOWN：旧 p18-final-04 57 PASS/1 FAIL，token_used=0、无未确认任务，STOP 后正常退出0。缺清理前活动/水位、精确交错及所检查旧材料中的完整版本正文。与 R1 无 STOP 退出2不同；本轮没有重建缺失历史，也不据后续成功关闭 H1。

各组最终结果和源码覆盖由后续 final-report.md / final.audit.json 如实登记；此处不是预填通过。
