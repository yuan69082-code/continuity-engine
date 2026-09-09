# P17 R1/R2测试历史

数值来自同名JSON，耗时为runner含发现的时间；stderr保留unittest自身计时。独立原件的两轮3 PASS/4 FAIL为历史监工实跑，本轮重新执行另有标签。

| 标签 | 本轮真实结果 | 原始输出 |
|---|---|---|
| compatibility-final-01 | 224项，224 PASS / 0 SKIP / 0 FAIL / 0 ERROR，169.793秒，exit=0 | [JSON](compatibility-final-01.json) / [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) |
| formal-after-01 | 12项，9 PASS / 0 SKIP / 0 FAIL / 3 ERROR，16.591秒，exit=1 | [JSON](formal-after-01.json) / [stdout](formal-after-01.stdout.log) / [stderr](formal-after-01.stderr.log) |
| formal-after-02 | 12项，12 PASS / 0 SKIP / 0 FAIL / 0 ERROR，18.846秒，exit=0 | [JSON](formal-after-02.json) / [stdout](formal-after-02.stdout.log) / [stderr](formal-after-02.stderr.log) |
| formal-before-01 | 12项，6 PASS / 0 SKIP / 5 FAIL / 1 ERROR，17.552秒，exit=1 | [JSON](formal-before-01.json) / [stdout](formal-before-01.stdout.log) / [stderr](formal-before-01.stderr.log) |
| formal-terminal-before-02 | 1项，0 PASS / 0 SKIP / 1 FAIL / 0 ERROR，1.853秒，exit=1 | [JSON](formal-terminal-before-02.json) / [stdout](formal-terminal-before-02.stdout.log) / [stderr](formal-terminal-before-02.stderr.log) |
| full-final-01 | 1360项，1359 PASS / 1 SKIP / 0 FAIL / 0 ERROR，1171.401秒，exit=0 | [JSON](full-final-01.json) / [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |
| independent-after-01 | 7项，7 PASS / 0 SKIP / 0 FAIL / 0 ERROR，6.759秒，exit=0 | [JSON](independent-after-01.json) / [stdout](independent-after-01.stdout.log) / [stderr](independent-after-01.stderr.log) |
| independent-before-01 | 7项，3 PASS / 0 SKIP / 4 FAIL / 0 ERROR，8.132秒，exit=1 | [JSON](independent-before-01.json) / [stdout](independent-before-01.stdout.log) / [stderr](independent-before-01.stderr.log) |
| p17-final-01 | 74项，74 PASS / 0 SKIP / 0 FAIL / 0 ERROR，128.466秒，exit=0 | [JSON](p17-final-01.json) / [stdout](p17-final-01.stdout.log) / [stderr](p17-final-01.stderr.log) |

原独立7项逐字节未改：修前3 PASS/4 FAIL，修后7 PASS。R1第三次capacity定位仍有效；R2固定每效果1积分前提保留，无需改变原断言。
formal-before-01中的5 FAIL覆盖R1三项及R2两项；另1 ERROR为新失败回执测试未先检查返回类型，已增加类型断言，在实现修改前formal-terminal-before-02重新保存有效FAIL。
formal-after-01中R1拒绝零效果断言已通过，3 ERROR来自新测试将恢复权限误当作自动retry。原ActionPlanningService._resume在attempts存在且retry=False时返回原结果。只修正新对照：先证明自动submit仍不重发，再调用原planner.run(...,retry=True)，验证完成重放；不改原契约。
其他辅助工具错误见[记录](auxiliary-errors.log)。所有首次输出保留；旧P17/P16失败、8处历史格式告警、Windows 1314 SKIP及P09 segment10 UNKNOWN不改写。
