# P18 持久化与恢复链定向返修交付

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加调查/返修事实；D-073未创建/未使用。

本轮新增正式14项；P18 120 PASS；兼容 605 PASS；最终全量 1480 项=1479 PASS、1既有1314 SKIP、0 FAIL/ERROR，1284.129秒，exit=0。原1466身份及断言保留，各组有交集，不重复相加。

本轮修复已实现，等待独立复核。没有自动验收、D-073、Git写操作、Assistant修改或P19施工。持续运行入口、资源局部等待及Owner/Subject停止要求不变。

## 实际完成

真实Windows仓储读句柄与SubjectState原子替换竞争已稳定复现：受控实验 PermissionError/errno13/winerror5，DELETE-access探针32。P18在现有Evolution写入作用域内对已确认短时共享冲突有界等待，重试前重查Context/控制及原文件字节版本；不无条件重试文件错误。写/flush/fsync失败的临时路径登记及清理错误覆盖主异常亦已实测并最小修复。详见 [根因调查](investigation.md)。

只改3个既有源码文件，新增1份TEST诊断和1份正式测试，完整路径见 [精确清单](final.pending-files.md)。原Runtime/Scheduler资源及单宿主R1修复、ThinkSession调用阶段R2修复保留，未新增账本或状态权威。原ActionEvolution仍持有合法状态演化责任。

已执行事实恢复使用原回执与ThinkSession：未提交状态可在故障解除、查询到期后续接；已经提交返回丢失不重复revision；重开后Provider不重复调用、效果/credits各1，usage身份不变且合法结算。真正UNKNOWN仍保守，不把错误字符串当未执行证明。

## 证据与验证

修前有效两项读竞争反例、同流程正常对照，旧writer精确重建两项FAIL；修复过程及辅助错误完整保存于 [测试历史](test-history.md)。原F2用例修前单跑1 PASS不构成历史关闭。原14项新增定点包括读句柄、长期占用、非共享错误、保存步骤、诊断兜底、清理原因链、版本变化、控制与权限、重启和幂等恢复。

| 本轮实际执行组 | RUN | PASS | SKIP | FAIL/ERROR | 秒 | 证据 |
|---|---|---|---|---|---|---|
| formal | 14 | 14 | 0 | 0/0 | 11.493 | [JSON](formal-final-02.json) · [stdout](formal-final-02.stdout.log) · [stderr](formal-final-02.stderr.log) |
| p18 | 120 | 120 | 0 | 0/0 | 174.733 | [JSON](p18-final-01.json) · [stdout](p18-final-01.stdout.log) · [stderr](p18-final-01.stderr.log) |
| compatibility | 605 | 605 | 0 | 0/0 | 841.034 | [JSON](compatibility-final-01.json) · [stdout](compatibility-final-01.stdout.log) · [stderr](compatibility-final-01.stderr.log) |
| full | 1480 | 1479 | 1 | 0/0 | 1284.129 | [JSON](full-final-01.json) · [stdout](full-final-01.stdout.log) · [stderr](full-final-01.stderr.log) |


上表都是本轮新执行，不冒称独立复核或远端CI。只有最终源码固定后的一次全量；原1466的历史全量仍是1464 PASS/1 SKIP/1 FAIL。原R2专项106与兼容490属于旧版本历史，源码变更后没有借用为本轮覆盖。原五组独立/施工记录、未完成全量及F1/H1全部原样保留。

最终源码/测试/资源267份，指纹 `sha256:f4b599136c70d5cec14a56617b17f99f848bd2b88c762df23298871c5452352a`。每组运行前后与frozen-source一致；原1466正式测试文件均未改，新增14另计。[逐组覆盖](test-source-coverage.json)明确中间版本差异。既有Windows符号链接1314为SKIP，未新增跳过。

## F2、F1、H1分别结论

- F2：同阶段、同外部事实已完成但状态未保存的风险已稳定复现并最小修复；当前有真实OS5及共享探针32证据。历史F2本身缺异常类型/系统码和句柄身份，不能声称已唯一确定那次具体原因。当前防护覆盖这个风险，等待独立确认。
- F1：缺历史失败时ThinkSession阶段、完整异常链，继续UNKNOWN。不能据第二轮token640或UNKNOWN推断与F2/R2同源。
- H1：缺清理前可信时间/next_check_at/任务水位，继续UNKNOWN。不能据当前PASS、Windows性能或软件中断归因。

没有充分依据关闭历史问题；EVIDENCE_CONFLICT保持PRESENT。本轮诊断在STOP/清理之前保存受控相对路径、hash/revision、OS类型与码、原因链、身份、PID/线程和锁状态；独立stderr有一次有限兜底，不泄漏异常正文或改变对外脱敏。长占用超过0.25秒仍真实失败；若清理被OS拒绝可能留下一个自建tmp，生产清除/备份恢复不在本轮范围。未承诺任意Adapter exactly-once。

## 保护与交付入口

[终局审计](final.audit.json)核对63保护、3规划、正式7文件、版本0.1.0/pyproject、32排除项、旧354成果及所有历史证据；正式树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。源码范围、原断言、AST、链接、敏感候选、git diff --check、精确待提交清单和完整Git状态分别记录，旧日志格式告警原样保留。

本轮测试进程由控制器STOP/退出后回收，细节在stdout和 [终局进程核查](process-check.json)，不清理无关目录或进程。main/HEAD/localorigin保持P17基线；没有Git写、没有联网远端查询、没有新CI结果，不宣称CI PASS。

在Engine根设置PYTHONPATH=src、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1，用未占用标签执行：

```powershell
python docs/project_memory/p18_persistence_evidence/run.py review-formal-01 test_p18_persistence
python docs/project_memory/p18_persistence_evidence/run.py review-p18-01 test_p18_
```

兼容与全量的准确实际命令见上表JSON。旧writer反例的独立重建入口为 `run.py review-old-writer-01 --review-class old_writer_probe.OldWriterEvidence`，预期两项FAIL，只可在TEST根复现。正常启动/控制仍见 [P18入口](../86_P18_测试索引与验收入口.md)。完成后停在P18，交回独立复核。

## 终局实际检查补记

预审 `preflight-01.audit.json`：268个Python文件解析、1355个本地链接核对通过，原1466测试文件/断言未改，四个最终运行均对应同一267文件指纹；63保护、3规划、7正式文件与32排除项均未变。敏感候选扫描无命中，新增可编辑文件无行尾告警，git diff --check退出0。保留P16旧8处、P17旧3处、两份P18旧日志格式告警；本轮save-stages-before-01.stderr.log第3行也有原始失败输出行尾空格，不改写。补丁中的空上下文前缀是统一差异格式，另列，不当作可编辑源码告警。Git对7个既有工作区文件提示未来LF→CRLF转换，仅记录提示，没有据此改文件。

最终只读进程查询于2026-09-13 15:12:34 UTC得到匹配数0；正式/P18/全量stdout分别有2/30/30条已回收记录，没有额外强制清理。兼容组没有该统一字段，不能凭0条记录声称它逐条有相同格式，但完整runner已退出0，终局匹配进程为0。没有清理无关进程或文件。

本轮5文件精确源码差异见 `implementation-diff.patch` / `implementation-identity.json`；新的诊断行号索引为 `diagnostic-index-v2.json`，旧分类索引保留并注明更正。完整待提交及排除列表、逐文件hash、tracked/untracked原始Git状态以final.audit.json与final.pending-files.md为准；这包含此前P18未提交成果，不将全部文件冒称为本次新增。

本轮文件竞争验证面向当前Windows；没有执行其他平台或远端CI。F2历史排他根因未证实，F1/H1继续UNKNOWN，交回独立复核，不自行关闭EVIDENCE_CONFLICT，不创建D-073，不暂存/提交/push，不进入P19。
