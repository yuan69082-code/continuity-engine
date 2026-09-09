# P17当前接续状态

施工/必要验证与档案已完成，停在IMPLEMENTED_NOT_ACCEPTED。当前有效任务P17，不返回P16、不进入P18，不Git写操作。

[完整交付](final-report.md)、[全部失败历史](test-history.md)、[最终审计](final.audit.json)、[清单](final.pending-files.md)。

以下保留此前施工接续原文，仅为历史，不覆盖当前结论。

# P17 当前施工接续

当前有效任务始终为P17；用户已授权Engine实现、测试和档案，未授权Git写操作或验收。不返回P16收尾、不进入P18。

开工核对已完成：0c440b0476b07723abafe93777fe895b64fd8d0e，243源码身份、1286测试身份、63保护、正式七文件、32排除全部匹配。D-070和79 Stage Brief已登记，D-071未使用。

目前：正常C1的Execution桥、原E5-A请求/结果、仅投递索引Outbox、OS跨进程锁、World/Broker/Reality门、当前Context与生命周期、取消/替代/补偿、候选Context来源已实现。新测试已跑Direct/Planner及33项恢复组合（32 PASS/1 FAIL），真实三进程Golden通过。缺少补偿link仍能执行的反例已补执行前核验。

16项边界初跑14 PASS，1个测试包含4个原因混同FAIL，1个测试包含2个Fixture生命周期操作ERROR。已补可选P17 preflight保留静态原因；Fixture改用原SUSPEND及归档后DELETE合法链。`p17-second-01`为这轮修后49项，具体结果以同名JSON为准。

全部首错保留。首次2项模块未实现ERROR；初接线UTC未以Z结尾导致两项ERROR；随后新增测试将FirstRoundSuccessResult当dict、将外部completed误作内部COMPLETED的辅助错误，均按真实契约修正而不改变原测试。独立诊断日志direct-diagnostic-01.log保留。

待办：继续完善当前范围的跨进程双worker、取消竞争、补偿恢复、首次持久化秘密与故障结果语义验证；定点/P17通过后跑P08/E5-A/P09/P11/P12/P15/P16受影响兼容，最终代码稳定后一次全量。同步80—82及现行档案、保护审计和精确清单。所有测试使用p17_evidence/run.py唯一标签，环境PYTHONPATH=src/PYTHONDONTWRITEBYTECODE=1。不得覆盖先前标签或机械全量多轮。


## 新发现：TEST存储限额边界（收口前必须修复）

storage-probe-before-02在独立短Temp根实测：原世界文档1193字节，限制2217字节，第二动作成功后2333字节，固定+1024估算不足。首个长路径探针FileNotFoundError未到断言，仅辅助错误，原输出和脚本均保留。当前full-final-01仍运行且源码尚未改变，应作为补修前历史；不得据此提交最终通过结论。

接下来待该轮结束保留完整记录，再最小修复P17 FakeBoundary按实际序列化增量检查storage_bytes，正式加入拒绝与精确边界正向测试。生产服务无需更改。补修后专项、必要独立探针，再一次真正稳定源码全量；旧645兼容与58专项应说明发生在此TEST补修前，不伪称新源码同一身份。当前本地该缺口PRESENT；不验收、不Git写操作。

## 末次局部补修后进度（历史记录，最终状态见后续交付）

full-final-01已完成：1344项，1343 PASS、1既有SKIP，1035.059秒，属于补修前历史。补修前已固化存储与TEST Adapter绑定反例及late-boundary-formal-before-01（3方法失败，含多个subTest）。补修后4/4 PASS、5.944秒，完整P17为62/62 PASS、76.336秒；原短路径存储探针及Adapter探针分别退出0，1.469/1.669秒。

最终全量full-final-02正在运行，不预填结果；源码从p17-final-03起未再变，当前仅编辑档案和审计工具。尚须核对全量完成状态，运行finalize.py同步现行档案，再运行audit.py生成final.audit.json和final.pending-files.md。兼容645项的前后身份差异仅4个新增P17文件，终局全量再次覆盖全部原645项身份。P17未验收，不Git写操作，不进入P18。
