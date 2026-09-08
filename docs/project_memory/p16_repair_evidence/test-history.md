# P16 R1/R2/R3 全部运行历史

所有条目为本轮实跑。秒为 runner 计时（包含发现及记录），unittest 自身计时保留在原始 stderr。FAIL/ERROR 列是 unittest 失败记录数（含子用例），不是可与方法总数相加的人为总数；PASS 按独立方法剔除失败/错误/跳过计算。后续通过不覆盖首次失败。

| 唯一标签 | 方法数 | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | 退出码 | 原始输出 |
|---|---|---|---|---|---|---|---|---|
| [independent-before-01](independent-before-01.json) | 9 | 4 | 5 | 0 | 0 | 7.902 | 1 | [stdout](independent-before-01.stdout.log) / [stderr](independent-before-01.stderr.log) |
| [formal-before-01](formal-before-01.json) | 22 | 7 | 47 | 2 | 0 | 18.988 | 1 | [stdout](formal-before-01.stdout.log) / [stderr](formal-before-01.stderr.log) |
| [formal-after-01](formal-after-01.json) | 22 | 22 | 0 | 0 | 0 | 19.586 | 0 | [stdout](formal-after-01.stdout.log) / [stderr](formal-after-01.stderr.log) |
| [capability-before-01](capability-before-01.json) | 3 | 0 | 2 | 1 | 0 | 2.757 | 1 | [stdout](capability-before-01.stdout.log) / [stderr](capability-before-01.stderr.log) |
| [formal-after-02](formal-after-02.json) | 25 | 24 | 0 | 1 | 0 | 23.310 | 1 | [stdout](formal-after-02.stdout.log) / [stderr](formal-after-02.stderr.log) |
| [capability-after-01](capability-after-01.json) | 3 | 3 | 0 | 0 | 0 | 2.900 | 0 | [stdout](capability-after-01.stdout.log) / [stderr](capability-after-01.stderr.log) |
| [independent-after-01](independent-after-01.json) | 9 | 9 | 0 | 0 | 0 | 9.197 | 0 | [stdout](independent-after-01.stdout.log) / [stderr](independent-after-01.stderr.log) |
| [p16-final-01](p16-final-01.json) | 78 | 78 | 0 | 0 | 0 | 112.609 | 0 | [stdout](p16-final-01.stdout.log) / [stderr](p16-final-01.stderr.log) |
| [compatibility-final-01](compatibility-final-01.json) | 676 | 675 | 0 | 0 | 1 | 501.254 | 0 | [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) |
| [full-final-01](full-final-01.json) | 1286 | 1285 | 0 | 0 | 1 | 1072.026 | 0 | [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |

## 失败解释与证据局限

- independent-before-01：原九项，4 PASS / 5 FAIL，7.902 秒，原 R1/R2/R3 的有效修前复现。独立侧先前的首次 Temp 路径错误保留在 independent/independent-edges-01.*，不算 Engine 缺陷。
- formal-before-01：22 方法，7 PASS；47 条 FAIL 含完整回执 12 字段×2入口等子用例；2 ERROR 分别是新增测试误用 LocalIntegrationApp.coordination 属性，以及尚未实现的可选检查方法。首版诊断断言还可能把源码行里的预期错误码误当实际错误消息，已改为核实异常类型与真实 cause 消息，增强而未删除断言；相关早期 PASS 不能作为该入口关闭证据。
- formal-after-01：22/22；当时尚未加入模型结果首次 E5-A 持久化的三项组合，所以这是中间结果，不冒充最终覆盖。
- capability-before-01：3 方法，2 FAIL / 1 ERROR。FAIL 是未在 CapabilityResult 首次入账及旧结果恢复 checkpoint 前执行材料重查；ERROR 是新增测试的查询专用 Fixture 未注册原 C1 expression.emit。
- formal-after-02：24 PASS / 1 ERROR。新增正常模型结果对照补注册表达能力后，仍缺原 P09 明确权限和按原请求身份确认配置。最终复用 ConfirmedFixturePolicy 和已有 Fake 能力，未关闭 Action、削弱断言或修改原 Fixture。capability-after-01 三项均通过。
- 只读辅助命令曾使用不存在的文件名和 PowerShell rg 通配参数，结果已识别为路径查询错误；一次快照字段打印过多导致输出截断。未改变文件或被计作测试 PASS。
- 原 P16 p16_evidence 全部原件及 P09 segment 10 根因 UNKNOWN、既有 WinError 1314、P15 与此前历史失败不变。当前仅本地测试；没有远程 CI run/check。

