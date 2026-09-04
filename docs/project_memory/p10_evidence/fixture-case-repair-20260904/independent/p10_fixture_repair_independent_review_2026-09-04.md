# P10 Fixture 返修独立复核（2026-09-04）

## 结论

原 Temp 仓库根与仓库内正式目录的缺口已通过本轮定点复核；但新补丁仍存在 Windows 保留目录名称大小写漏项，因此不能认定当前只剩 Git/checkpoint 收尾。P10 保持 IMPLEMENTED_NOT_ACCEPTED、EVIDENCE_CONFLICT=PRESENT。D-056 不创建，P11 不开始。

## 新阻断：保留目录名称按区分大小写的字符串比较

位置：两仓 src/continuity_engine/testing/p08_action_fixture.py 第 43 行：
`parent.name == name`。

在当前 Windows 文件系统中，以大写名称创建的 `.CONTINUITY-DATA` 和 `.ASSISTANT-DATA` 可通过对应小写路径访问，独立测试先以 Path.samefile 验证它们确为同一目录。但 _validate_fixture_root 的保留名称扫描没有按 Windows 路径语义比较。对这两个保留目录的子目录调用 FakeActionAdapter 或 P08Fixture，均未拒绝，并发生 TEST 写入。

复现仅使用新建的独立 Temp 测试树，无真实主体数据：

- Assistant：2 个方法，1 个方法内 4 个失败 subTest，0.453 秒。
- Engine：2 个方法，1 个方法内 4 个失败 subTest，0.455 秒。
- 小写目录的四个对照全部拒绝且零写入。
- 仓库标记保护的根、正式目录与普通子目录，两个入口均拒绝且零写入。
- 大写目录：FakeActionAdapter 每例新增 2 个路径条目；P08Fixture 每例新增 11 个路径条目；四例都生成了 TEST 回执。
- 保留目录分别为 C:\Users\Administrator\AppData\Local\Temp\p10r2-independent-b2ojby04 和 C:\Users\Administrator\AppData\Local\Temp\p10r2-independent-2bn548zf。
- 本次不主张真实正式数据受损，也不主张生产运行逻辑出现新问题。

## 其他独立检查

- Engine P08：76 项，75 PASS、1 SKIP，22.269 秒。
- Assistant P08：76 项，75 PASS、1 SKIP，21.742 秒。
- Assistant P10 原严格检查：12 项，10 PASS、2 FAIL，1.606 秒。
  - test_02：当前多出 tests/test_p08_fixture_paths.py，旧 C1 文件集合门失败；
  - test_04：788 != 770，旧精确数量门失败。
  两项失败真实存在，不能报作通过；新的大小写缺口独立于这两项待来源同步检查。
- 两仓 Fixture 补丁与新增回归文件的 SHA-256 完全相同。
- Engine 187 个原源码/测试文件中，仅获授权的 Fixture 文件变化；25 个边界文件、7 个正式数据文件均与开工快照一致。
- 本轮前后原仓库文件清单及 hash 无变化：Engine 543/543，Assistant 367/367。
- 没有修改两仓、Git 写操作、推送、新 checkpoint 或远端 CI。
- 本轮未重复执行两仓 788 项全量，也未重新构建 wheel。

## 建议

在用户已授权的 TEST Fixture 范围内继续定点返修：保留目录名称比较遵循平台路径大小写语义，并补大写、混合大小写和子目录的拒绝且零写入测试；同时保留 Linux/其他平台正确语义及合法独立 Temp 对照。两仓同步同一补丁，不修改生产业务或冻结契约。

定点和 P08 通过、代码稳定后，再各跑一次必要全量；不要先提交再处理这个可复现缺口。新 checkpoint、来源清单和 CI 继续等待单独 Git 授权。原 C1、原 770 个用例及历史失败保持可追溯，不放宽断言制造通过。

## 复核辅助错误

首次独立大小写探针把两个 synthetic owner 目录也命名为仅大小写不同，导致 4 个 FileExistsError（WinError 183），在调用 Fixture 前即失败。之后仅改为不同数字编号，保留断言。该辅助错误单独记录于 p10_fixture_repair_probe_initial_helper_error.md，不计作 Engine 缺陷。

原始日志与探针均位于本目录：

- p10_fixture_repair_review_probe.py
- p10_fixture_repair_review_assistant_probe.log
- p10_fixture_repair_review_engine_probe.log
- p10_fixture_repair_review_engine_p08.log
- p10_fixture_repair_review_assistant_p08.log
- p10_fixture_repair_review_p10_strict.log
