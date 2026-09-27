# Planning Item → Code Change → Test → Acceptance Result

| Planning Item | Code Change | Test | Acceptance Result |
|---|---|---|---|
| P18有限等待/持续宿主/STOP | 两项获准测试同步与BUSY区间修正；新增3受控；产品不变 | targeted-final；compatibility-final；full-final，原锁反例记录保留 | IMPLEMENTED_NOT_ACCEPTED，待独立复核 |
| W04/N21指定历史回执、T66/T67/T72/T18 | 原Router request_id绑定及执行来源目标排序；不扩2048预算 | history-before-03修前；新9项正反及原42项中的同根/撤回/恢复 | IMPLEMENTED_NOT_ACCEPTED |
| N13/N10、T27—T29/T37/T85—T87 | 原W04-2实现保留 | W04-2原42项同版专项及全量 | IMPLEMENTED_NOT_ACCEPTED |
| W02/N02/T03—T06 | 保留_safe单次当前元数据检查优化 | 五原失败场景、原四资料与第三轮16检索；原1000ms | IMPLEMENTED_NOT_ACCEPTED，本机正式链通过，不宣称任意负载 |
| W04-1已验收三处边界 | 无改动 | 专项原29项及全量 | D-087历史ACCEPTED保留 |
| 旧模块/唯一权威/来源/权限/恢复 | 不改公共Router/Composer及P18运行语义 | 公共兼容及完整回归 | 本轮证据待复核，不新增历史验收 |

无新规划冲突；本次用户已批准前轮两项待决定方案。EVIDENCE_CONFLICT继续PRESENT直到独立确认。原矩阵与中间结果不覆盖。
