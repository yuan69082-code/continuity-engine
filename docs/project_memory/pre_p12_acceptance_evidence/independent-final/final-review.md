# P12 前 R01—R08 修复最终独立复核

日期：2026-09-06。审查对象：Engine `main` 的当前修复工作区，HEAD `5f25d0cef3798aa380d457ae670db30ee1b47407`。

## 结论

**本轮独立复核通过，建议用户验收。**上次 R05/R06 的三个失败场景均已关闭，没有发现本轮修复范围内仍需返工的已复现问题。R01—R08 可在用户确认后统一办理本轮验收收口，无需撤回或重新实现其他六项成果。

这是技术复核建议，不是代替用户登记正式验收。本轮没有修改 Engine 的阶段状态、EVIDENCE_CONFLICT、验收档案或决策记录；没有提交、push 或进入 P12。

## R05/R06 的闭合证据

R05：[事务内身份检查](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/storage/json_resource_repository.py:129)由允许分配和拒绝决定共同调用，两者都在既有 `_RESOURCE_WRITE_LOCK` 内读当前文档并检查稳定 request_id/已分配 session。

- 同一请求并发批准/拒绝：只保留首个决定，后来者明确身份冲突拒绝；只有一次资源扣减。
- 同一请求并发拒绝/拒绝：只保存一条拒绝决定，不再留下重复身份记录。
- 正常新身份请求、拒绝后重新申请、原分配重启结算继续通过；没有新建账本或删除历史。

R06：[共用置信度公式](C:/Users/Administrator/Documents/continuity-engine/src/continuity_engine/services/learning_service.py:425)保留既有 max、平均值、证据数量加分和六位舍入规则，验证与固化不再使用两种相互矛盾的判定。

- 原反例 `0.95/0.2/0.2` 在证据未变时可以立即固化，结果置信度仍为 0.95。
- 当前支持被否决、撤回、重复、缺失、内容改变或确实不足时，仍拒绝且无持久化副作用。
- `0.6/0.6/0.6` 验证后不重复加分；支持变弱但仍充分时如实记录 0.75；确认门、历史和后续 Evolution 边界保留。
- 额外进行了 4608 组纯公式对照，新提取的公式与既有数学政策一致。这是公式等价检查，不冒充 4608 项端到端测试。

## 测试与证据来源

| 验证 | 来源 | 结果 | 耗时 |
| --- | --- | --- | --- |
| 上轮独立探针，脚本未改 | 本轮独立实跑 | 21/21 PASS，原三个失败均通过 | 1.485 秒 |
| 两轮正式定点 55 项＋原 Resources/Learning 兼容 19 项 | 本轮独立实跑 | 74/74 PASS，0 FAIL/ERROR/SKIP | 4.317 秒 |
| 完整 Engine 回归 | 核验修复方已有原始日志及当前源码身份，本轮未重复执行全量 | 894 项：893 PASS、1 SKIP，0 FAIL/ERROR | 日志记录 425.134 秒 |

全量证据不只核对末尾 PASS：检查了命令、工作目录、退出码、中断标志、快照/运行/审计时间顺序，并将日志逐项身份与当前测试发现结果和稳定清单对照。三份身份集合均为相同的 894 项；当前 193 个源码/测试文件 SHA-256 与全量前稳定快照全部匹配。测试发现无导入错误。因此可以引用这次完整回归，而不把它误称为本轮独立重新运行的全量。

唯一 SKIP 仍为 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`，Windows 未授予 symlink 创建权限，错误码 1314。该环境限制未消失，未计入 PASS，也没有新增跳过项。

## 未扩大范围、未改变现场

相对上一轮 192 文件稳定清单，只有 `learning_service.py` 和 `json_resource_repository.py` 两个既有运行文件变化；新增一份补修测试。其他六项修复和既有测试没有变化。

当前 63 个保护文件与 P11 原验收基线全部匹配，包括六份 Schema、冻结接口边界、正式七文件及原有 P10 辅助脚本。版本、Authority 和单一账本边界未改变。

本次独立复核前后，Engine 976 个已跟踪/未跟踪、未忽略文件的路径＋SHA-256 聚合一致，Git 状态一致。仍为 24 个 tracked 修改、130 个 untracked，暂存区空；HEAD 与本地 origin/main 的 ahead/behind 为 0/0，未联网刷新远端。原有 31 个 P10 辅助脚本保留，`git diff --check` 通过。

没有修改 Engine/Assistant 代码或业务档案，没有 Git 写操作；新增复核材料仅位于本规划工作区，业务测试数据位于隔离 Temp/Fake 中。本结论不扩展为生产 Adapter、真实 Provider、多进程/多机一致性或“引擎已不存在任何未知 bug”的保证。

## 原始材料

- [本轮 21 项独立输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-final-review-20260906/independent-probes.log)
- [本轮 74 项定点与兼容输出](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-final-review-20260906/targeted-and-compatibility.log)
- [全量证据、测试身份及公式对照核验](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-final-review-20260906/evidence-verification.json)
- [核验脚本](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-final-review-20260906/verify_evidence.py)
- [结束时哈希与 Git 核对](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/engine-pre-p12-final-review-20260906/after.json)
- [修复方全量逐项原始日志](C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p12_r05_r06_evidence/final-full.stderr.log)

本轮辅助核验过程有三个非引擎问题，均保留、未计入业务测试结果：首次按旧清单形状读取新 stable-source 的五个元数据字段，形成无效匹配结果，随后改为读取 sourceTest，193 项全部匹配；测试发现入口最初错误地将 namespace tests 目录要求为普通包，改为与实际全量命令一致；日志解析最初重复拼接了新版 unittest 已包含的方法名，修正后逐项身份完全匹配。原始 before.json 及两份辅助错误日志保留，正确结果见 before-corrected.json、evidence-verification.json 和 after.json。

## 下一步建议

用户确认本轮验收后，可登记这次整体修复收口，按精确清单处理档案及后续 Git 收尾；是否由引擎提交/push，应另有明确授权。P12 应在该验收收口之后开始。本轮复核本身没有执行上述动作。
