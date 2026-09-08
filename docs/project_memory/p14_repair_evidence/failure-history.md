# P14 R1/R2 真实失败与修复过程

原监工历史：原专项54 PASS；confirmed 7项4 PASS/3 FAIL，21.522秒 unittest /22.437秒包装。探索两条未确认契约不作为本轮目标；深层Temp路径初次ERROR保留监工原件，其hash/位置在before.json。本轮不修改任何独立原件。

- confirmed-before：直接加载只读confirmed_probes，7项4 PASS/3 FAIL，20.352秒。两个旧支持误解决和一个transform冻结原样复现。
- formal-before：原确认断言加入正规test_p14_review_repair（不依赖外部目录），7项4 PASS/3 FAIL，21.750秒；原断言没有削弱。
- targeted-after：新增对照共13项，11 PASS/2 FAIL，69.579秒。原三项已通过；两处扩展结果继续保留。
- Composer逆序候选不同：同根RAW/Memory置信度不同，首次命中导致appraisal强度依赖遍历顺序。本轮R1同根保护内采用保守消费强度并排序根；不升级Memory权威，不增加投票数。
- 重开后后续支持仅processing：support-diagnostic.stdout.log显示实际Composer仅含新支持第二根，不能按两根宣称解决。根因是新测试f.reopen后丢失显式3000预算，回到Fixture默认。补回同一3000测试设置，保留原预算门禁和resolved断言；没有在Engine提高预算或降低置信度规则。

诊断仅为辅助读取/定位，不是验收测试；期间service文件完成同根排序补丁，诊断进程已加载旧模块，输出不用于最终源码身份证据。后续所有正式runner均保存执行前后源码hash，不混用。

辅助读取中PowerShell rg字面通配路径及长输出截断是工具读取问题，不计Engine缺陷。所有失败stdout/stderr/JSON均原样保留。旧P09 segment10 stderr缺失、根因UNKNOWN未改写。后续PASS不能覆盖本页失败。
