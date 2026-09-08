# P15 全量发现的 Context 身份兼容缺口

2026-09-08。本轮 `full-final` 运行中出现旧测试 `test_p09_boundaries.P09BoundaryTests.test_cross_subject_and_environment_contexts_fail_closed` ERROR。不修改原断言，不把此前299项兼容PASS或39项P15 PASS覆盖到此场景。

原 `ContinuityCoreService.current(context)` 先比对snapshot的subject/environment再访问绑定来源；P15新增生命周期检查放在该比对之前，错主体名因此先进入SubjectState加载。应保持原身份拒绝顺序，再执行新生命周期检查；不放松暂停/归档门禁，不捕获任意异常冒充成功。

本条记录时全量尚未结束，最终数量、堆栈和真实耗时以同目录 `full-final.json`、`full-final.stderr.log` 为准。本条不是修复后结果。该缺口暂为待闭合的施工证据冲突；允许范围内定点修复后追加实际证据。

## 全量落盘与局部修复

首轮[full-final](full-final.json)完整1176项：1174 PASS、1既有Windows symlink1314 SKIP、0 FAIL、1 ERROR，runner1012.898秒（unittest1012.154秒）。堆栈明确为`current(context)`提前加载`different-subject`并抛出`StateNotFoundError`。

只调整 `src/continuity_engine/services/continuity_core_service.py` 的 `current` 顺序：snapshot主体/环境先比对，匹配后仍执行生命周期活跃检查。没有宽泛捕获异常，没有改动任何原测试文件或断言。

原单项定点：[修复前](context-identity-before.json)0 PASS/1 ERROR，1.349秒；[修复后](context-identity-after.json)1 PASS，1.432秒，均无SKIP。所有原始stdout/stderr同名保留。最终专项、兼容和全量另用`-2`标签，必须核对最终源码；前一版39/299项PASS不能冒称相同源码。是否完整通过以这些完成记录和最终审计为准。
