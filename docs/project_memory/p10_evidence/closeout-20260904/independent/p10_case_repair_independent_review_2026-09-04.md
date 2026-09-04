# P10 Windows 大小写返修独立复核（2026-09-04）

## 结论

本轮所复核的 Temp 仓库根保护与 Windows 保留目录大小写缺口均已闭合。可以结束这两项代码返修，申请进入来源 checkpoint 同步、提交后构建与远端 CI 验证。此结论不是 P10 用户验收，也不将待来源验证的工程检查记为通过。

P10 保持 IMPLEMENTED_NOT_ACCEPTED；在新来源 checkpoint 和远端验证完成前，整体 EVIDENCE_CONFLICT=PRESENT 保留。P00—P09 既有验收历史、原 C1 与首次 Assistant 提交保持；D-056 不创建，P11 不开始。

## 独立实跑

| 检查 | Engine | Assistant |
|---|---|---|
| 原独立反例探针（不修改断言） | 2/2 PASS，0.099 秒 | 2/2 PASS，0.101 秒 |
| 当前 P08 专项 | 81 PASS、1 SKIP，20.849 秒 | 81 PASS、1 SKIP，21.583 秒 |
| P10 原严格工程检查 | 未重复执行（该检查属于 Assistant） | 10 PASS、2 FAIL，1.406 秒 |

大小写探针验证了两个入口、小写对照、大写保留目录以及仓库根/正式目录/子目录。所有受保护目标均拒绝且零写入；先前失败的四个子用例本次均通过。P08 中 24 个路径测试覆盖新增的混合大小写、目录本身、子目录和 samefile 别名。SKIP 为已有符号链接创建权限项，不计为 PASS；真实 Windows junction 测试未跳过。

本轮仅实跑 Windows，未主张 Linux 测试通过。

## 补丁与档案核实

- 修复采用 Path(parent.name) == Path(name)，沿用平台原生路径名称比较；改动局限于 TEST Fixture 与必要测试，没有改生产领域/服务或账本。
- 两仓补丁完全一致，且与实现方稳定测试快照相符：
  - src/continuity_engine/testing/p08_action_fixture.py：6509bf7097fa2f528f8194446f228ca910f00abf73a7900287aee3a79b7b520e
  - tests/test_p08_fixture_paths.py：376e68d7709324943d2827901a416c32c1aa82df22caa124dfa9caa0641ba8e6
- 已检查两仓实现方全量报告及原始 stdout/stderr，日志 SHA-256 均与报告一致：
  - Engine：794 项，793 PASS、1 SKIP，434.732 秒。
  - Assistant：794 项，793 PASS、1 SKIP，412.882 秒。
- 上述全量是实现方证据；本轮没有再次独立执行 794 项全量，没有重新构建 wheel，也未执行新远端 CI。
- Engine 原 187 个源码/测试文件只有获授权的 Fixture 文件发生变化；原有测试文件保持不变。新增 24 项不替代原 770 项。
- 25 个冻结边界文件、7 个正式数据文件与 P10 开工快照一致。
- 两仓 git diff --check 均为 0；Engine 47 条输出均为换行配置 warning。
- 本轮前后文件清单及 hash 完全一致：Engine 593/593，Assistant 368/368。没有修改两仓。
- Engine main HEAD 保持 9d58b427ffaca2e64a268640979337e4c759d49d；Assistant continuity-assistant-fenzhi HEAD 保持 c6dd2c0cab17337a445b64fb8611d317190242c6。暂存区均空，双方相对本地 upstream 均 0/0。本轮未查询新的远端分支状态。

## 仍待完成

P10 两项严格检查实际仍失败：

1. 旧 C1 文件集合/字节清单：当前新增 tests/test_p08_fixture_paths.py，且 Fixture 有明确授权差异。
2. 旧数量断言：794 != 770。

它们不能通过简单放宽断言或把旧 CI 当成新 CI 解决。需要独立、真实、可追溯的新修复 checkpoint，并据此同步 Assistant 来源记录、清单和工程校验；保留旧 C1 和原 770 项测试身份，不只修改一个数字制造通过。

建议下一次明确 Git 授权涵盖：
- Engine 仅提交并推送已复核的 Fixture 与新增回归两个文件，生成测试修复 checkpoint；其他未验收 P10 档案不自动一并暂存。
- Assistant 从该真实 checkpoint 做有记录的来源同步，保留历史与独立仓库边界，更新必要的来源/测试校验及相关档案。
- 仅推送到各自确认的目标（Engine main、Assistant continuity-assistant-fenzhi），再做提交后的来源检查、重新构建安装、干净克隆和真实 CI。
- 不强推、不重写既有历史；冲突或保护规则需要明确处理，不自动绕过。
- CI/独立复核完成后再交用户正式验收，不提前创建 D-056。

## 本轮日志

- p10_case_repair_review_engine_probe.log
- p10_case_repair_review_assistant_probe.log
- p10_case_repair_review_engine_p08.log
- p10_case_repair_review_assistant_p08.log
- p10_case_repair_review_p10_strict.log
- p10_case_repair_review_checks.json
