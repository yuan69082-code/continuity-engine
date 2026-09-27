# W04-2公共验证续修

本次授权包含两条公共链的证据化最小补修，不再停在只调查。最终仍交IMPLEMENTED_NOT_ACCEPTED，不验收/Git写入/W04-3。

基线已核验，见baseline.json。第一轮有限诊断方案见protocol.md；原始七项未插桩失败在旧w04_2_evidence，原件不动。

recall-profile-01为辅助导入错误：直接执行脚本时PYTHONPATH遗漏仓库根，五项FailedTest没有运行Engine用例。原日志保留；仅修runner路径，recall-profile-02才是计划的五用例测量。未修改源码、原测试及1000ms。

锁诊断脚本通过本次子进程专属环境加载，不更改产品或安装全局模块；读取/控制原测试原样执行，进程结束缓冲记录独立写入。本轮未开始正式修补或全量。

## 后续实际进度（前文保留为历史）

- 唯一运行修补：json_external_provider_repository.py 的_safe，同次三次元数据查询改为一次当前lstat；不改变1000ms和授权/来源。新增tests/test_w04_2_registry_recheck.py七项。
- 固定源码315项，1a0f355a…，1851测试身份，原1802保留。见frozen-source-01.json。
- 修前/修后诊断和7项回归已完成；special-final-01为48PASS/2ERROR，其中1个真正W04-2历史查询组装错误、1个模块名辅助错误。W04-1随后单独29PASS。不覆盖失败。
- 新错误单次原样诊断通过但揭示预算裁剪，history-pair-01在同一数据根各查两份真实回执稳定一成功一拒绝；两次均无注册仓储_safe调用。详见history-new-blocker.md。
- P18两原例本次诊断PASS；受控占用复现测试断言冲突，见p18-test-conflict.md。两项授权问题已通过异步问题发给用户；未经回答不改P18原测试或新查询接线。
- compatibility-current-01已启动，使用原414项模块列表，2026-09-27 17:19:39 UTC启动，观察到runner21416/测试10668。恢复前必须重新核对JSON是否COMPLETED、进程及日志；不要盲目重用旧会话68619或重启测试。
- 最终全量未启动。finish_pending.py已准备、尚未执行；只在当前兼容完成及进程清理核对后执行一次以产生真实阶段报告/清单/审计，不伪装全部修复完成。
- 辅助记录另含两次不存在文件路径读取、一次完成前读取尚未生成trace；没有把这些当Engine错误。保留工具执行记录和本说明。
- 临时只读保护核对脚本首次未指定UTF-8，以GBK读取baseline.json时报UnicodeDecodeError（position38528）；改为显式UTF-8后核对所有保护组无变化、70保留材料无变化。未运行Engine、未改数据，不当行为失败。

## 当前安全停点

正式/诊断进程均已结束（核对process-cleanup.json）。唯一新增运行改动为外部注册仓储_safe；新正式测试7项。当前315项身份见frozen-source-01.json。公共兼容已完成，结果见repair-report.md；完整回归未启动，P18测试同步与W04-2定向查询新缺口待用户确认。不要重新开工、覆盖旧证据、重复启动完成标签或擅自改原测试。
