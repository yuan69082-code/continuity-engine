# P16 R1/R2/R3 返修交付（等待独立复核）

P16 / Engine side / P16-01—P16-12 = IMPLEMENTED_NOT_ACCEPTED；P00—P15 ACCEPTED；P17—P23 NOT_STARTED；Vio dependency = NONE。PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = PRESENT，已知复核阻断等待监工独立确认，本轮不关闭、不验收、不创建 D-069、不 Git 写操作。

## 实际修复

| 项 | 根因与责任边界 | 实际变化及验证 |
|---|---|---|
| R1 | P16 Adapter 只验证 ActionReceipt 结构/绑定，遗漏回执材料 | [external_capability_service.py](../../../src/continuity_engine/services/external_capability_service.py) 在执行返回、独立 query、历史恢复共同 Adapter 出口，把整份 to_dict 原材料交给 Broker；保留全部 12 字段、原回执与事实文件，不改写编号/hash。拒绝返回静态码，原 E5-A 保留 UNKNOWN；查询后恢复事实，不自动重发。正式回归逐字段检查两入口，正常自定义 ID 与恢复继续通过。 |
| R2 | Information Need 在 P16 Policy 选择时才检查，Thinking 及模型结果可能先入账 | [thinking_service.py](../../../src/continuity_engine/services/thinking_service.py) 增加可选 result_validator，先检查原结果再运行 P14/P15 processor、首次保存；失败只保存通用失败结果及安全原因。等待恢复先检查后 resume 写入；已完成结果返回前重查。[continuity_interaction_service.py](../../../src/continuity_engine/services/continuity_interaction_service.py) 仅 P16 开启时接线，C1 CapabilityResult 首次 E5-A 入账、结果/ThinkSession 重放及 checkpoint 恢复检查同一材料边界。原结果身份、hash、历史事实不修改；P16 关闭不调用外部检查。普通心理/实验内容对照不受审查。 |
| R3 | Broker/Permission 异常通过标准异常链泄漏任意原文 | ExternalCapabilityService 统一 material_allowed / authorize_reference / authorize_permission 静态错误边界，异常使用 from None，不转存 repr/原文。覆盖注册、选择、执行、消费、恢复；必须明确 True 才获准，异常不是成功。原 Provider 异常防护保留。正式回归检查真实异常消息、标准 traceback 及重定向 stdout/stderr，运行目录没有合成秘密泄漏。 |

本轮只改三个现有服务文件，新增两个正式回归文件；未改变冻结接口、Authority、E5-A 账本或业务主体定位。旧 1261 项身份及测试断言完整保留，新加 25 项（原九项探针副本 + 16 项边界组合）；原独立九项已包含在正式 P16 中，不再相加计数。

## 真实验证

- [independent-after-01](independent-after-01.json)：9 项，9 PASS、0 SKIP、0 FAIL、0 ERROR，9.197 秒，退出码 0。[stdout](independent-after-01.stdout.log) / [stderr](independent-after-01.stderr.log)。
- [p16-final-01](p16-final-01.json)：78 项，78 PASS、0 SKIP、0 FAIL、0 ERROR，112.609 秒，退出码 0。[stdout](p16-final-01.stdout.log) / [stderr](p16-final-01.stderr.log)。
- [compatibility-final-01](compatibility-final-01.json)：676 项，675 PASS、1 SKIP、0 FAIL、0 ERROR，501.254 秒，退出码 0。[stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log)。
- [full-final-01](full-final-01.json)：1286 项，1285 PASS、1 SKIP、0 FAIL、0 ERROR，1072.026 秒，退出码 0。[stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log)。

上述均是本轮修复方实跑，包括执行原独立脚本副本；不是新的监工独立核验。秒为 runner 计时（包含发现与记录），unittest 自身计时保留在 stderr。原监工 53 PASS 与九项 4 PASS / 5 FAIL 属于修前历史。[全部首次失败和辅助错误](test-history.md)保留。原 P16 全量 1260 PASS / 1 SKIP 仅作历史，未冒充返修后结果。

本轮完整回归的既有 SKIP：[["test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes", "OS does not grant symlink creation: 1314"]]。SKIP 不计 PASS。每次原始 JSON 保存命令、完整方法身份、UTC 起止时间、耗时、退出码和执行前后源码 SHA-256。

## 独立复核入口

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p16_repair_evidence/run.py review-r16-probes --independent-probe
python docs/project_memory/p16_repair_evidence/run.py review-r16-formal test_p16_repair_edges test_p16_review_regressions
python docs/project_memory/p16_repair_evidence/run.py review-r16-p16 test_p16_
python docs/project_memory/p16_repair_evidence/run.py review-r16-full
python docs/project_memory/p16_repair_evidence/audit.py review-r16
```

必须使用未占用标签，runner 拒绝覆盖输出；顺序运行，不同时启动全量。原始独立材料逐文件 hash 来源见 [before.json](before.json)，[报告副本](independent/review-report.md)、[探针副本](independent/test_independent_edges.py)及所有原始日志/快照保持原样。

## 保护、清单与剩余事项

[最终只读审计](final.audit.json)记录当前源码身份、原 1261 身份、63 保护项、三份规划、正式七文件、版本和 32 排除项；[完整 P16 待提交及排除清单](final.pending-files.md)包括已有 P16 成果，不仅是本轮增量。正式树预期 sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2。最终实测值以审计为准。

剩余：三项阻断待独立确认；P16 未用户验收。真实服务、生产凭据与隐私策略、生产接入未开放；不声称任意 Adapter exactly-once。本轮不访问外网，既有 HTTP 回归仅本机 loopback；不访问 Assistant/Vio，不运行或配置 CI，不提交/push。历史格式问题仅列明，不修写原始日志。
