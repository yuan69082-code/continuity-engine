# R1/R2 续接记录

2026-09-29，用户授权两项定点返修，不验收、不暂存/提交/push/W04-4。基线核对全部一致（baseline.json），无测试Python进程遗留。

静态线索经施工方 before-02 实跑证实，2 FAIL /0 ERROR；before-01 含夹具提前启用宿主控制的1 ERROR及观察尚未跨next_check的早期FAIL，单独保留、不当作两条有效机制的充分证据。

R1：原RuntimeWork每轮重复提交同一个等待工具，未入队的其他事项永远不获机会；native也被固定截首。修补只投递原Scheduler尚未拥有的需求，按due_at/原priority/身份最多两项；排队、退避、未知查询、资源、取消终态仍由原Scheduler负责。没有私有队列或游标。

R2：原len(closes)<3是永久总数门槛。移除后每次advance仍最多一个清理；默认沿P18 RuntimePolicy.retry_seconds=5秒，参数可配置。退避由上一份RETRY_CLEANUP原回执completed_at计算，重开不清零；首次显式清理失败原有立即续做行为保留。条件不具备不生成新清理请求，UNKNOWN仅查询原事实，成功不重做。

after-01 R2通过、R1的工具及维护通过，新增认知测试在尚未产生认知需求的短时点错误期待模型调用（1 FAIL），保留。按原P18测试的3600秒可信推进取证；after-02两项PASS。未修改原断言、负载、产品时限或旧测试。

当前进一步扩展隔离正式验证，结果尚未固定，不引用旧PASS作为最终。公共运行修改仅temporary_tool_service.py；新tests/test_w04_3_repairs.py。辅助读取路径/PowerShell语法错误均未改变运行数据。旧142成果/日志/各历史UNKNOWN保留。

## 续接更新：最终验证已启动

以上段落是早期进度，不倒写。targeted-final-01已14 PASS（runner167.125秒）；源码固定于frozen-source-01.json：321文件，sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506，1923身份=原1909+14，旧测试文件无变化。

validate.py于2026-09-29本地00:24启动；控制session为83807。顺序固定为w04-3-final-01、w04-12-final-01、compatibility-final-01、full-final-01，遇失败立即停，不重复启动。w04-3-final-01已60 PASS，324.797秒unittest/325.487秒runner。后续组是否完成以各JSON的COMPLETED、exit_code及stderr最终汇总为准，不因日志片段判PASS。

若软件中断，先检查该进程是否仍存在、日志增长及各JSON，不能盲目恢复session或重跑validate.py。未完成记录原样保留，需补跑只用新标签；运行期间源码和正式测试不得改变。当前仅写工程档案，终局finalize.py须所有最终集合真实完成且同版才可运行。

## 2026-09-29 本地00:44更新

w04-12-final-01已87 PASS（runner160.000秒）；compatibility-final-01已417 PASS（runner701.916秒）；所有前后hash仍与frozen-source-01相同。full-final-01已启动，尚无最终汇总；不得将STARTED或局部日志算PASS。控制仍为同一validate.py session83807，没有重复启动。

## 最终完成记录

2026-09-28T17:24:24.452748+00:00：上述最终五组均已COMPLETED、exit0、同版，实际计数见test-index.md。finalize.py依据完成记录生成交付，不将早期运行中状态倒改。测试进程收尾见process-cleanup.json；后续只等待独立复核，不再启动测试或下一批。
