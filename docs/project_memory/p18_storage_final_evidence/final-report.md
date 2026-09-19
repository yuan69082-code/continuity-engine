# P18 统一有限存储尝试：返修交付

P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加本次授权/返修事实，D-073未创建/未使用。

新增正式27项，原1480项身份及断言保留。P18 147 PASS；公共兼容 605 PASS；本轮最终全量 1507项=1506 PASS、1既有Windows 1314 SKIP、0 FAIL/ERROR，1319.841秒，exit 0。各组重叠，不相加。

当前两个读句柄机制有修前失败、同流程修后通过。历史F1/H1/F2仍缺原现场证据，不能唯一归因或合并结案；详见[因果调查及首次失败分类](investigation-notes.md)。当前实现交独立复核，不构成验收。

## 实际修改与公共影响

仅两个运行文件：`src/continuity_engine/storage/json_repository.py`、`src/continuity_engine/storage/json_runtime_repository.py`；新增两份P18测试文件。其余运行实现和旧测试文件与开工hash一致。

SubjectState沿用显式P18授权；完整操作绑定、原payload/临时inode、目标字节/身份、目录、当前权限/属性及版本检查通过后，在原0.25秒预算内继续同一次原生替换。完整绑定固定WinError5可以有限尝试；无绑定错误、无授权旧路径不取得此资格。当前允许尝试不证明过去一定发生共享冲突。运行实现不改ACL/只读属性、不提权，不另换写入方式。

Checkpoint沿用原OS事务锁和CAS，事务资格绑定实例、线程及活动生命周期；原owner/generation/control文档受当前检查约束。合格尝试耗尽用静态内部类型保留失败并交原宿主等待处理，不能误写BACKOFF、伪报提交或终止主体；真实拒绝、损坏及冲突仍失败。保留原生与清理异常链。

## 原始目标与持续运行语义核对

- 已实测：无聊天、沉默和空闲继续运行；真实进程长读占用超过提交预算后仍存活、可查询，释放后Frozen时间下重获资源等待观察；资源恢复后无需聊天推进。
- 已实测：PAUSE阻止新执行，RESUME恢复；STOP终态不复活；R1单宿主/锁/CAS与R2调用阶段保护继续覆盖。
- 已实测：SubjectState局部等待时独立Memory维护仍推进；原已执行事实恢复不重调用模型、不重派动作、不重扣credits，不重复revision。保存成功返回丢失重放原记录。
- 限制：关键状态不可信仍明确拒绝；本轮不承诺任意存储故障都能推进其他任务、不承诺生产exactly-once。真实常驻部署、自启动、供应商/凭据、生产恢复和正式联系政策仍未开放。没有新增引擎运行时长、tick数量或随机停机规则。

## 本轮实际验证

| 组 | PASS | SKIP | FAIL/ERROR | 秒 | 原始记录 |
|---|---:|---:|---|---:|---|
| boundaries-final-04 | 27 | 0 | 0/0 | 23.097 | [boundaries-final-04.json](boundaries-final-04.json) |
| originals-final-03 | 4 | 0 | 0/0 | 37.523 | [originals-final-03.json](originals-final-03.json) |
| advancing-final-02 | 2 | 0 | 0/0 | 19.278 | [advancing-final-02.json](advancing-final-02.json) |
| prior-boundaries-final-01 | 8 | 0 | 0/0 | 9.011 | [prior-boundaries-final-01.json](prior-boundaries-final-01.json) |
| native-denial-final-02 | 4 | 0 | 0/0 | 0.589 | [native-denial-final-02.json](native-denial-final-02.json) |
| p18-final-01 | 147 | 0 | 0/0 | 215.15 | [p18-final-01.json](p18-final-01.json) |
| compatibility-final-01 | 605 | 0 | 0/0 | 892.095 | [compatibility-final-01.json](compatibility-final-01.json) |
| full-final-01 | 1506 | 1 | 0/0 | 1319.841 | [full-final-01.json](full-final-01.json) |

上述最终组运行前后均匹配[最终源码身份](frozen-source-02.json)。标准输出/错误输出与同名JSON在本目录，命令在每个JSON内。SKIP按上表及原始记录实录，与PASS分开；允许引用的既有原因仅Windows符号链接权限1314。没有远程CI运行，不能声称CI PASS。

## 修前及中间记录

修前原对照/反例4项=2PASS/2FAIL，79.248秒，是开工核对一致的上轮实际运行引用，不冒充本轮重跑。当前完整运行和旧记录严格分开。新TEST长路径3FAIL、三项守卫反例、过期事务Context ERROR、辅助缩进错误均保留；详细[测试历史](test-history.json)。旧full-final-01中断、H1/F1/F2失败、P09 segment10 UNKNOWN及历次SKIP不改写。

新发现分类：初次临时文件未绑定原payload/inode是原有遗漏；跨线程/过期Context携带事务资格，以及新包装异常的原生原因被清理错误覆盖，是本轮初版补修引入的边界回归，均以反例保存后局部修正。261字符TEST路径与测试类误插位置是测试/辅助工具问题。历史F1/H1/F2的唯一原因仍尚未确定。

`original-flows-after-01`运行期间新增了另一份正式测试文件，因此其前后整体源码清单不一致；没有把这份中间结果算作最终源码覆盖。最终采用的八组记录均与第二份冻结逐文件一致。

终局只读检查：270份Python文件解析、988个本地文档链接和git diff --check通过；密钥格式特征扫描无命中（扫描范围有限，见审计）。正式数据树为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。63项保护、3规划、正式7文件、0.1.0版本与32项排除材料未变。真实进程观察无残留，所选结果中35条持续进程记录均已回收且无强制清理。

格式单列：本次未提交材料扫描有4份原始日志含行尾空格，3份是既有记录；新增一处在 `new-guards-before-01.stderr.log:2`，来自unittest子用例失败的原始输出。保留日志原文，不为格式清理改写失败证据；这与git diff --check通过并不矛盾。先前已知的8处历史格式告警继续保留。首版终局审计保留为文档补注前的快照，最终清单与审计使用02版。

## 可复跑入口

在Engine根设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，使用未占用标签：

```powershell
& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-storage-01 test_p18_storage_
& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-originals-01 --review-class original_suites.baseline_suite
& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-p18-01 test_p18_
```

不重执行已用标签或整个旧validate脚本。若独立复核需要全量，用新标签且不带测试前缀。

## 清单、保护与停止位置

[终局审计](final.audit-02.json)记录63项保护、三规划、正式七文件、版本/pyproject与32项排除材料，及原件/副本hash。[完整P18未提交清单](final.pending-files-02.md)区分开工已有成果、本轮增量和排除项；[本轮逐文件变化](turn-changes-02.json)。没有Git写操作。保持未验收，等待独立复核，不进入P19。
