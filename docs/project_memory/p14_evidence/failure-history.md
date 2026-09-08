# P14 失败、辅助错误与版本边界

本文件说明原因和后续处置，不覆盖原始 JSON、stdout/stderr 或历史结论。各轮完整数量见最终报告的逐轮表；不能把不同源码版本的 PASS 相加为同一轮，也不把受控故障注入的预期异常计为 Engine 新缺陷。

## 恢复接续

`resume-affective-before` 的源码清单与暂停前 `affective-chain-first.sourceAfter` 完全一致；恢复时 HEAD 仍为 b02d8c9cc894b3060089d7cc24e06afaeab89ebf。先实际复现6项中5 PASS/1 ERROR，随后施工。原31个P10脚本、冻结/正式数据和规划原件无变化，见 resume-audit 与终局审计。没有覆盖或回退已有 P14 成果。

## 已确认的实现问题

| 问题 | 首次或诊断入口 | 处置与对应正式测试 |
|---|---|---|
| 同一来源同时间重复 appraisal 仍改变躯体积分 | lifecycle-detail-red | 先按已见根过滤，再处理零 elapsed；duplicate_appraisal 对照 |
| weaken 只改标签；未知嵌套推理字段未拒绝 | lifecycle-detail-red | 改变实际 need/strength，严格嵌套形状和引用验证 |
| transformed desire 后产生相同 identity | remaining-mechanisms-red | 保留转化身份，新形成欲望使用确定性不冲突身份 |
| 新伤害没有重开已 resolved Episode | remaining-mechanisms-red | 新根恢复 unresolved，旧 resolution 留在既有 Evolution 历史 |
| Will/Thought 未绑定内部引用 | remaining-mechanisms-red | 构造/加载/序列化检查所属 Desire/Conflict、时间和类型 |
| 调节与 Information Need 未接入正常 C1 | remaining-mechanisms-red | 反复 concern 形成可失败调节；真实 request_more_memory / Direct 请求 |
| Information Need 未给必需 query | remaining-mechanisms-first | 根据当前注意主题提供有界查询，保持 ThinkingResult 原校验 |
| E5-A 完成分支未接内部处理 | c1-recovery-extended-red | 原 complete_capability_wait 增加可选处理器，原模型结果验证先行 |
| P14 source reference 使用了另一种 JSON hash 规范 | body-binding-diagnosis | 尤其0.0出现不同hash；引用统一使用原 P05/P06 source hash，未改旧 hash 规范 |
| 解释器忽略实际 Composer 选择的单根 Memory | resolution-source-diagnosis | 按原 authority 消费已组成 Memory，保留权重，按 Event 根去重；不改预算或让摘要当事实 |
| 新 TEST Owner permission 文件未纳入 Snapshot | observation-golden-red | 先登记两项测试设施文件边界，再做精确权限文件/逻辑清单；未知文件仍拒绝 |
| P14关闭时原生入口仍读取恢复记录 | gate-off-native-red | 只有 core.mind 启用时进入新分支；正式 spy 断言零调用 |
| 通用驱力覆盖明确 REFUSE/SILENCE/CONFRONT | explicit-subject-decision-diagnosis、explicit-decisions-red | 三项正式反例均先 FAIL；保留明确的 Thinking 选择，欲望不等于必须推动它 |

## 测试构造及辅助错误

- `initial-red`、`integration-red`、`native-opportunity-red`、`owner-visibility-red`、`affective-chain-red`、`observation-golden-red` 的部分 ERROR 是新增模块/入口尚未实现，不伪称旧引擎回归。
- `integration-first` 对旧表达重放的期望过窄，参见 [契约核对](integration-contract-clarification.md)。P13 原门禁和断言未改。
- 情感 Fixture 最初借通用 C1 `event()`，只标 continuity；与 peer 的经历缺少正确 interaction/relationship 元数据，P05 以相关性不足拒绝。`affective-routing-diagnosis` 保留原 trace。改为真实测试经历元数据后 `resume-affective-scoped` 六项通过。没有直接塞入 anger，也没有降低相关性门槛。
- 相同 Frozen Clock 的 Genesis 与新事件会发生合法稳定排序；普通预算允许未选中材料。调节对照改为真实稍后事件，认知解决对照显式提供足够有界预算容纳两个当前支持来源。未组成证据不使用，裁剪不能冒充支持齐全。
- 身体对照最初把带 mutation 的 TEST seed 标成 FACT，原 Event 门正确拒绝。改为显式 TEST STATE_CHANGE，之后的普通 C1 仍走 Action/Evolution。没有让 FACT 获得状态写权。
- 新测试曾误用 `intent_kind`/`expression_mode` 成员名及 ValueError 异常类型；依实际类型改为 trigger/mode/SandboxOperationError，未改运行契约来迁就测试。
- Windows 下同一临时父目录的大小写同名目录会在 mkdir 报 WinError183；改为各自独立父目录，保留每个大小写入口的拒绝且零写入断言，P08保护实现未改。
- 路径导航、输出截断、编码名误写等另见 [辅助错误记录](opening-tool-errors.md)。旧 P09 segment 10 stderr 缺失，根因仍 UNKNOWN；没有改成 PASS 或“确定只是中断”。

## 最后版本差异

`compatibility-final` 的741项运行完成后才追加明确选择的三项反例和最小修复。与最终版本相比，仅 dynamic_mind_service.py 和新增的 test_p14_mind_recovery.py 有后续差异。该运行不是最终源码逐字节相同的证据；最终 `p14-final-2`、`targeted-compatibility-final` 和 `full-final` 绑定最终源码。终局审计还检查741项兼容身份全部被最终全量包含。

所有全量/专项/兼容结果均为施工方本地结果，未冒称规划方独立复核。原1070项P13完整基线只引用已验收证据；本次完整回归有自己的源文件清单、日志和耗时。既有 Windows symlink 1314 SKIP 仍单列。
