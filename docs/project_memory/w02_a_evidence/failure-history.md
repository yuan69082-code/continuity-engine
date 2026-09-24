# W02-A 首次失败与中间记录

所有标签原样保留；本文件只解释分类，不替代原始 JSON、stdout/stderr。最终结果见 selected-runs.json；集合存在交叠，不相加。

| 标签 | 当时结果/分类 | 处理与证据边界 |
|---|---|---|
| feature-before-01 | 1 FAIL：新增开关尚未实现 | 新行为的首条红测试；不是旧阶段已验收回归 |
| targeted-01 | 6 项，5 PASS / 1 FAIL | 测试误要求 Memory 全空，原 C1 合法巩固 Genesis。保留旧失败；改为精确拒绝“把新消息伪造为记忆/事件”，且仍核对主体字节不变 |
| targeted-02 | 27 PASS | 当时源码中间结果，不替代最终版 |
| targeted-03 | 34 项，33 PASS / 1 FAIL | 材料拒绝测试的 Broker lambda 参数少一个，属辅助问题；同时定位 W02 原始消息未在首次 operation 写入前调用原材料门禁的接线缺口。端口签名纠正且在允许的 C1 文件补接现有门禁；不修改 P16 原实现或原测试 |
| targeted-04 | 34 PASS | 对应上述补修后的中间版本 |
| targeted-05 | 37 PASS | 加入跨线程/跨进程 admission 和真实进程重启；中间版本 |
| receipt-before-01 | 2 FAIL | 新处置记录若单独被改写，曾能伪称 Memory 成功或不存在的 Context 片段。补核原 Memory 历史、原 Context 实际片段及独立 ThinkSession 绑定，不能只信 journal 标签 |
| targeted-06 | 39 PASS | 回执核验补修后的中间版本 |
| targeted-final-01 | 39 PASS | 当时固定版本，之后因 admission 新反例而变更；不用于最终源码覆盖 |
| admission-before-01 | 1 FAIL | 新 admission 的 catch 范围曾包含业务体，误改下游原 RuntimeBoundaryError。修成只分类锁获取失败，业务原异常保留 |
| targeted-final-02 | 40 PASS，29.735 秒 | frozen-source-02；随后兼容核对发现原 native 轻量 operation 缺新字段的差异，仍需补修验证 |
| compatibility-final-01 | 761 次方法运行，77 个 FAIL 记录、9 ERROR、1 SKIP；退出 1；616.420 秒 | W02 对旧 native 轻量 operation 的开关属性作了强制访问，阻断原认知并造成派生超时/空记录断言。另 3 个加载错误及 2 个运行时裸模块导入错误来自 runner 缺 tests 搜索路径。原 stderr 完整保留；子用例可产生多个 FAIL 记录，旧 runner 的减法 passed 字段不作为准确通过方法数 |
| native-before-01 | 1 ERROR，0 PASS，0.933 秒 | 用新增正式对照直接定位旧 native 原路径缺可选字段的 AttributeError；只在本批获准 CoreService 中按旧缺省 False 读取，不改 P18/原测试 |
| targeted-final-03 | 41 PASS，31.325 秒；exit 0 | 冻结版本 frozen-source-03；新增 1 项原 native 正常链对照。run-v1-preserved.py 保留旧 runner；新版补 tests 导入路径并以 unittest addSuccess 统计通过，未跳过 loader.errors |

辅助工具记录：初次定位用了不存在的 p09_continuity_fixture.py，随后用实际 p09_core_fixture.py；一次补丁因代码段顺序未匹配而拒绝，未落入部分修改；PowerShell 通配路径传给 rg 的只读搜索报路径格式错误；进程 WMI 查询拒绝访问、备用 psutil 未安装，未安装依赖或提权。后续用 Get-Process 和运行器自身 PID/结果跟踪。本轮工具错误不计作 Engine 行为测试失败。

历史 F1/H1/F2、P09 segment 10 UNKNOWN、旧 FAIL/ERROR/中断/SKIP 都保留原结论；本批问题不并入旧案，不用后续通过倒推历史根因。

## 最终全量启动时的验证快照（历史）

- compatibility-final-02 已完成：813 项，812 PASS、1 既有 Windows 1314 SKIP，0 FAIL/ERROR，613.244 秒，退出 0；已恢复完整原模块导入。
- pre-full-check.json：282 份源码/测试/资源与 frozen-source-03 一致；272 份 Python AST 通过；105 次分组保护 hash 对照及原 57 份未跟踪材料一致。前一次辅助检查误拼 utf8-sig，记录 audit-helper-error-01；纠正为 utf-8-sig 后完成，不是 Engine 行为缺陷。
- full-final-01 正在固定源码上执行，未结束前不预填通过。最终状态以后续追加及 selected-runs.json 为准。

辅助只读定位补记：查询旧长期 runner 时曾使用不存在的 p09_long_run.py 路径，随即按正式测试导入定位到 p09_core_runner.py；没有修改旧测试或运行模块。进程查询遇到已自然结束的 PID 返回不存在，属于点时观察，不记为测试失败。

## 最终固定版本结果

full-final-01 完成：1621 项，1620 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，墙钟1545.244秒，unittest 1544.312秒，退出0。运行前后与 frozen-source-03 完全一致。上述历史失败及执行中记录不倒改，本地补修通过交回独立复核，不自行验收。
