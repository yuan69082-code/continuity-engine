# P17 R1/R2当前停止点

P17 R1/R2补修已实现，等待独立复核；P17 / Engine side / P17-01—P17-12 IMPLEMENTED_NOT_ACCEPTED。P00—P16 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，监工阻断待独立确认，本轮不自行关闭。D-070仅追加返修事实，D-071未创建/未使用。无Git写操作。

本轮P17专项：74项，74 PASS / 0 SKIP / 0 FAIL / 0 ERROR，128.466秒，exit=0；最终全量：1360项，1359 PASS / 1 SKIP / 0 FAIL / 0 ERROR，1171.401秒，exit=0。原1348测试身份与断言保留，新增12项单列。独立原探针另报，不增加Engine正式测试数。下方初版与旧全量仅为修前历史，不覆盖此次阻断。

[报告](final-report.md) · [清单](final.pending-files.md) · [审计](final.audit.json)。以下为此前接续原文。

# P17 R1/R2 当前任务

用户授权P17 R1/R2合并返修；不回P16、不重做P17、不进入P18；不Git写操作、不D-071、不验收。开工身份全部匹配，独立原件已逐字节复制并hash归档。接下来先复现独立7项，再增加正式回归，最小修复最终资源检查期间撤权和Fake cost计费一致性。P17保持IMPLEMENTED_NOT_ACCEPTED；EVIDENCE_CONFLICT=PRESENT直到独立复核确认。

## 2026-09-10 当前施工进度

修前原探针7项：3 PASS/4 FAIL，8.132秒。补修只改execution_service.py和p17_execution_fixture.py；正式新增test_p17_repair_edges.py，12项。原独立探针未修改，修后7/7 PASS，6.759秒；新增正式12/12 PASS，18.846秒；完整P17 74/74 PASS，128.466秒；直接兼容224/224 PASS，169.793秒。

full-final-01正在运行，尚未写入完成结果。源码自formal-after-02后保持稳定；待全量完成核对身份，然后执行本目录finalize.py与audit.py完成报告和清单。原1348项、原32排除、原136项P17成果完整保留；当前增量与全部成果分开列。

首轮新测试辅助错误保留：失败回执缺少类型前置断言（修前已更正并保留有效FAIL）；R1复权测试误以为UNKNOWN会自动retry（改为证明不自动重发，再走原明确retry=True）。未改原恢复契约或原断言。EVIDENCE_CONFLICT=PRESENT，不D-071、不Git写、不进入P18。
