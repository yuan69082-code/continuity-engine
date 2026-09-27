# W04-2 逐项施工矩阵

Planning Item → Code Change → Test → Acceptance Result。本批功能实现 IMPLEMENTED_NOT_ACCEPTED；公共验证 BLOCKED，不是验收。正式用例定位见[coverage-map.md](coverage-map.md)，真实结果见[test-index.md](test-index.md)。

| Planning Item | 现有入口与缺口／代码位置 | 计划正式验证 | 状态 |
|---|---|---|---|
| N13/T27 | ActionPlanning→P17→E5-A 已有；新增 DeviceCommand/DeviceOperationService 和模拟 UI 实际定位、输入、滚动、保存、发送、再观察 | 正常消息产生 Context，正式动作链执行；CLICKED ≠ SAVED/SENT；结果进 Composer | IMPLEMENTED_NOT_ACCEPTED |
| N12/N13/T28/T29 | W04-1 绑定已有；补页面、焦点、观察期限、锁屏、离线和接管检查 | 当前观察到投递前变化、零效果/费用、恢复重新观察、取消 | IMPLEMENTED_NOT_ACCEPTED |
| N10/T22/T85 | W04-1 Body/Sensor 契约已有；补 Perception 与模拟执行闭环 | 无身体仍存在、合法零/未知、传感→Perception、act→原回执 | IMPLEMENTED_NOT_ACCEPTED |
| N10/T86 | 复用连接代次/有效能力和原 E5-A 恢复 | 换身体旧观察失效、撤权、断线、失败、UNKNOWN、回执丢失/重开/重复不重复效果 | IMPLEMENTED_NOT_ACCEPTED |
| N10/T87 | 已有三源枚举；本批模拟硬件入口拒绝 Somatic/Dream 冒充 | 三源隔离、未知与零、单位/范围/时效；W05 梦实现未开工 | IMPLEMENTED_NOT_ACCEPTED |
| N21/T66/T67/T72 | HistoryScope 已有；补 UI 有界查询及 ExecutionContextSource→Router/Composer | 明确范围/意愿、权限前后复核、来源版本、只读零推进、查询重开 | IMPLEMENTED_NOT_ACCEPTED |
| T37 | 原 material/Action/Reality 门禁保持；设备内容不产生权限 | 恶意外部指令只为观察；被拒动作不换路绕行；合法技术替代正例 | IMPLEMENTED_NOT_ACCEPTED |
| T18 | 原 outbox/E5-A 是唯一请求/结果；新增参数随原请求持久化 | 局部失败、成功返回丢失、真实 UNKNOWN、跨进程恢复、同身份冲突 | IMPLEMENTED_NOT_ACCEPTED |
| 公共兼容 | 新可选设备路径，旧契约和执行不变 | W04-1 三处修补、P16/P17/P18/W02/W03；原 1000ms 回归；最终同版全量 | BLOCKED：兼容407 PASS/1 FAIL/6 ERROR；全量未启动，见conflict-report.md |

边界：跨入口完整续接 W04-4，梦与自然记忆联动 W05，生产恢复/真实接入 P20—P22；这些不能代替表内本批义务。
