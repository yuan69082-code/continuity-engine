# W02-B 全部运行历史（不覆盖原件）

按真实开始时间排列。PASS/FAIL/ERROR/SKIP分别计数；诊断脚本完成不等于产品验收。前版结果不能代替最终源码。每条链接中的原始命令、输出和前后源码保留原样；多个集合有交集，不相加。

| 标签 | 总数 / PASS / FAIL / ERROR / SKIP | 秒 / 退出码 | 前后源码一致 | 分类与处置 |
|---|---|---|---|---|
| [before-01](before-01.json) · [stderr](before-01.stderr.log) · [stdout](before-01.stdout.log) | 2 / 1 / 1 / 0 / 0 | 2.733 / 1 | True | 实现前缺少自动回忆记录的真实入口反例；旧流程正对照通过。不是旧阶段验收撤销。 |
| [development-01](development-01.json) · [stderr](development-01.stderr.log) · [stdout](development-01.stdout.log) | 3 / 3 / 0 / 0 / 0 | 2.672 / 0 | True | 早期接线小集合；仅当时版本。 |
| [development-02](development-02.json) · [stderr](development-02.stderr.log) · [stdout](development-02.stdout.log) | 5 / 4 / 0 / 1 / 0 | 4.365 / 1 | True | 新实现错误：候选类型无to_dict；保存原原因链后修复。 |
| [development-03](development-03.json) · [stderr](development-03.stderr.log) · [stdout](development-03.stdout.log) | 5 / 4 / 1 / 0 / 0 | 6.347 / 1 | True | 新实现不足：午饭历史投影被Context预算裁掉，T03断言失败。 |
| [development-04](development-04.json) · [stderr](development-04.stderr.log) · [stdout](development-04.stdout.log) | 5 / 5 / 0 / 0 / 0 | 7.104 / 0 | True | 前版T03小集合通过，不代替后续核心上下文/完整覆盖。 |
| [development-05](development-05.json) · [stderr](development-05.stderr.log) · [stdout](development-05.stdout.log) | 8 / 8 / 0 / 0 / 0 | 18.255 / 0 | True | 当时8项通过，后续增加边界。 |
| [development-06](development-06.json) · [stderr](development-06.stderr.log) · [stdout](development-06.stdout.log) | 22 / 20 / 0 / 2 / 0 | 30.233 / 1 | True | 实现接线：native必需心智Context缺失；辅助：EventReference漏target_subject_id。两种ERROR区分，不把后者算Engine缺陷。 |
| [development-07](development-07.json) · [stderr](development-07.stderr.log) · [stdout](development-07.stdout.log) | 22 / 20 / 2 / 0 / 0 | 32.777 / 1 | True | 保留必需主体核心后，预算排序与候选窗口仍不足；T03、T04真实失败。 |
| [development-08](development-08.json) · [stderr](development-08.stderr.log) · [stdout](development-08.stdout.log) | 22 / 21 / 1 / 0 / 0 | 34.926 / 1 | True | 候选窗口已修，T03仍失败；不掩盖未闭合。 |
| [budget-diagnostic-01](budget-diagnostic-01.json) · [stderr](budget-diagnostic-01.stderr.log) · [stdout](budget-diagnostic-01.stdout.log) | 1 / 1 / 0 / 0 / 0 | 4.497 / 0 | True | 诊断执行完成，不代表T03通过。观测片段与预算，不替代原断言。 |
| [budget-correction-01](budget-correction-01.json) · [stderr](budget-correction-01.stderr.log) · [stdout](budget-correction-01.stdout.log) | 1 / 0 / 1 / 0 / 0 | 4.581 / 1 | True | T03仍缺旧材料；继续按实际预算定位，保留失败。 |
| [relevance-correction-01](relevance-correction-01.json) · [stderr](relevance-correction-01.stderr.log) · [stdout](relevance-correction-01.stdout.log) | 22 / 6 / 1 / 15 / 0 | 10.828 / 1 | True | 本批新增排序误用reason_codes字段（实际explanation_codes），导致15ERROR及一次前置失败后的效果断言FAIL；属于本轮引入错误。 |
| [relevance-correction-02](relevance-correction-02.json) · [stderr](relevance-correction-02.stderr.log) · [stdout](relevance-correction-02.stdout.log) | 22 / 22 / 0 / 0 / 0 | 36.614 / 0 | True | 修正字段、压缩重复投影并调整相关性排序后22项通过，后续仍增加组合覆盖。 |
| [combinations-01](combinations-01.json) · [stderr](combinations-01.stderr.log) · [stdout](combinations-01.stdout.log) | 39 / 34 / 2 / 3 / 0 | 82.695 / 1 | True | 本批完整准备时延检查暴露重复日志解析超时；辅助场景一处期待无mutation事件推进revision，一处关联对象已在原terms内，无法代表新关联。改为合法state_change和新的面条对象，保持真实拒绝/展开断言。 |
| [combinations-02](combinations-02.json) · [stderr](combinations-02.stderr.log) · [stdout](combinations-02.stdout.log) | 39 / 38 / 0 / 1 / 0 | 86.773 / 1 | True | 辅助ImportError：不存在MutationOperation；38项通过不能把该ERROR算通过。 |
| [deadline-check-01](deadline-check-01.json) · [stderr](deadline-check-01.stderr.log) · [stdout](deadline-check-01.stdout.log) | 39 / 36 / 0 / 3 / 0 | 78.904 / 1 | True | 两处候选准备仍超时；另有辅助StateMutation缺reason。原1秒期限未延长。 |
| [deadline-profile-01](deadline-profile-01.json) · [stderr](deadline-profile-01.stderr.log) · [stdout](deadline-profile-01.stdout.log) | 1 / 0 / 0 / 1 / 0 | 6.831 / 1 | True | 有目的的同流程耗时观测，仍ERROR；最后准备约1.351秒、多次完整journal加载，定位重复解析成本。 |
| [deadline-optimization-01](deadline-optimization-01.json) · [stderr](deadline-optimization-01.stderr.log) · [stdout](deadline-optimization-01.stdout.log) | 4 / 3 / 0 / 1 / 0 | 20.896 / 1 | True | 一次调用内复用核验材料并在权限后重读；原同流程测得约0.875秒。辅助用FACT事件提交mutation被原Authority正确拒绝，不是放宽原Authority的理由。 |
| [extended-boundaries-01](extended-boundaries-01.json) · [stderr](extended-boundaries-01.stderr.log) · [stdout](extended-boundaries-01.stdout.log) | 8 / 7 / 0 / 1 / 0 | 20.075 / 1 | True | 辅助current_focus用了字符串（契约为list），原StateEvolution正确拒绝；改正测试构造，不改公共状态类型。 |
| [w02-b-candidate-01](w02-b-candidate-01.json) · [stderr](w02-b-candidate-01.stderr.log) · [stdout](w02-b-candidate-01.stdout.log) | 46 / 46 / 0 / 0 / 0 | 98.332 / 0 | True | 候选版46项通过；此后新增native持续运行控制测试，不能代替最终47项身份。 |
| [native-timing-01](native-timing-01.json) · [stderr](native-timing-01.stderr.log) · [stdout](native-timing-01.stdout.log) | 2 / 2 / 0 / 0 / 0 | 6.511 / 0 | True | 新增native控制及T03时序2项通过；仍由最终完整集合再次覆盖。 |
| [w02-b-final-01](w02-b-final-01.json) · [stderr](w02-b-final-01.stderr.log) · [stdout](w02-b-final-01.stdout.log) | 47 / 47 / 0 / 0 / 0 | 100.205 / 0 | True | 冻结版本01的47项专项，后续全量发生T04超时，本结果不能代替补修版本。 |
| [w02-a-compatibility-01](w02-a-compatibility-01.json) · [stderr](w02-a-compatibility-01.stderr.log) · [stdout](w02-a-compatibility-01.stdout.log) | 66 / 66 / 0 / 0 / 0 | 60.434 / 0 | True | 版本01的A66项通过；后续局部读取修补需要对应新版覆盖。 |
| [affected-compatibility-01](affected-compatibility-01.json) · [stderr](affected-compatibility-01.stderr.log) · [stdout](affected-compatibility-01.stdout.log) | 509 / 509 / 0 / 0 / 0 | 426.833 / 0 | True | 版本01的509项共享兼容通过，不冒充最后版本。 |
| [full-final-01](full-final-01.json) · [stderr](full-final-01.stderr.log) · [stdout](full-final-01.stdout.log) | 1693 / 1691 / 0 / 1 / 1 | 2182.85 / 1 | True | 真实完整全量：1693项中1691PASS/1既有SKIP/1ERROR（T04 RECALL_TIMEOUT），2182.850秒。不是全量通过；永久保留。 |
| [full-timeout-profile-01](full-timeout-profile-01.json) · [stderr](full-timeout-profile-01.stderr.log) · [stdout](full-timeout-profile-01.stdout.log) | 1 / 1 / 0 / 0 / 0 | 8.383 / 0 | True | 单次有目的诊断：第三轮准备0.966秒，完整流程53次load；该诊断通过不关闭全量超时。 |
| [timeout-correction-01](timeout-correction-01.json) · [stderr](timeout-correction-01.stderr.log) · [stdout](timeout-correction-01.stdout.log) | 4 / 3 / 1 / 0 / 0 | 22.931 / 1 | True | 两文件局部减少重复解析后原T04与来源撤销对照通过；新增辅助测试把updated_at字符串误当datetime，尚未到达注入点。profile第三轮0.730秒、40次load；未扩大1000ms期限。 |
| [consistency-diagnostic-01](consistency-diagnostic-01.json) · [stderr](consistency-diagnostic-01.stderr.log) · [stdout](consistency-diagnostic-01.stdout.log) | 1 / 0 / 1 / 0 / 0 | 5.106 / 1 | True | 补足辅助断言的原因信息，明确为字符串加timedelta的TypeError；不是Engine行为缺陷。 |
| [timeout-correction-02](timeout-correction-02.json) · [stderr](timeout-correction-02.stderr.log) · [stdout](timeout-correction-02.stdout.log) | 3 / 3 / 0 / 0 / 0 | 16.204 / 0 | True | 按既有字段类型修正测试构造；原T04及两个读取变化边界共3PASS。 |
| [w02-b-final-02](w02-b-final-02.json) · [stderr](w02-b-final-02.stderr.log) · [stdout](w02-b-final-02.stdout.log) | 49 / 49 / 0 / 0 / 0 | 102.096 / 0 | True | 冻结版本02的49项专项，实际结果见本表。 |
| [w02-a-compatibility-02](w02-a-compatibility-02.json) · [stderr](w02-a-compatibility-02.stderr.log) · [stdout](w02-a-compatibility-02.stdout.log) | 66 / 66 / 0 / 0 / 0 | 54.256 / 0 | True | 冻结版本02的原A兼容，非引用版本01。 |
| [affected-compatibility-02](affected-compatibility-02.json) · [stderr](affected-compatibility-02.stderr.log) · [stdout](affected-compatibility-02.stdout.log) | 509 / 509 / 0 / 0 / 0 | 397.72 / 0 | True | 冻结版本02的共享模块兼容。 |
| [full-final-02](full-final-02.json) · [stderr](full-final-02.stderr.log) · [stdout](full-final-02.stdout.log) | 1695 / 1689 / 1 / 4 / 1 | 2569.981 / 1 | True | 完整1695项：1689PASS/1SKIP/1FAIL/4ERROR，2569.981秒；四个超时ERROR及注入前超时FAIL，原读取减少不足；保留原件，不算全量通过。 |
| [semantic-before-01](semantic-before-01.json) · [stderr](semantic-before-01.stderr.log) · [stdout](semantic-before-01.stdout.log) | 4 / 0 / 4 / 0 / 0 | 10.104 / 1 | True | 四个原始入站反例均FAIL：普通偏好被标进食域，未修改旧断言。 |
| [full-timeout-details-01](full-timeout-details-01.json) · [stderr](full-timeout-details-01.stderr.log) · [stdout](full-timeout-details-01.stdout.log) | 1 / 0 / 0 / 1 / 0 | 5.662 / 1 | True | 一次预定cProfile诊断。定位重复原日志解析及hash成本；测量有额外开销，ERROR如实保留，不单凭它推定正常路径耗时。 |
| [semantic-correction-01](semantic-correction-01.json) · [stderr](semantic-correction-01.stderr.log) · [stdout](semantic-correction-01.stdout.log) | 6 / 4 / 0 / 2 / 0 | 21.353 / 1 | True | 四项新语义回归PASS；原T03/T04仍因准备超时ERROR，整组不是通过。 |
| [byte-identity-correction-01](byte-identity-correction-01.json) · [stderr](byte-identity-correction-01.stderr.log) · [stdout](byte-identity-correction-01.stdout.log) | 13 / 12 / 0 / 1 / 0 | 67.29 / 1 | True | 12项正式行为回归PASS，cProfile诊断第三轮超时ERROR（不能唯一归因于测量）。没有放宽期限，诊断结果单列。 |
| [byte-identity-correction-02](byte-identity-correction-02.json) · [stderr](byte-identity-correction-02.stderr.log) · [stdout](byte-identity-correction-02.stdout.log) | 13 / 13 / 0 / 0 / 0 | 68.784 / 0 | True | 局部复用当前字节完全一致的完整解析；只复制所需请求并保持缓存对绑定。12正式回归与1低开销诊断全部PASS，第三轮准备约0.511秒，不是生产性能承诺。 |
| [w02-b-final-03](w02-b-final-03.json) · [stderr](w02-b-final-03.stderr.log) · [stdout](w02-b-final-03.stdout.log) | 55 / 54 / 0 / 1 / 0 | 157.611 / 1 | True | 完整55项：54PASS/1ERROR（新增根场景准备超时），157.611秒；后续A/兼容/全量03未启动，不掩盖失败。 |
| [dependency-profile-01](dependency-profile-01.json) · [stderr](dependency-profile-01.stderr.log) · [stdout](dependency-profile-01.stdout.log) | 1 / 1 / 0 / 0 / 0 | 12.44 / 0 | True | 对原失败流程的一次预定低开销测量，第三轮约0.549秒；通过仅是诊断，不能关闭原专项失败。 |
| [input-projection-correction-01](input-projection-correction-01.json) · [stderr](input-projection-correction-01.stderr.log) · [stdout](input-projection-correction-01.stdout.log) | 13 / 13 / 0 / 0 / 0 | 69.774 / 0 | True | 按原input绑定排除Context后，12正式+1诊断PASS；第三轮约0.902秒，不宣称此次测量更快。 |
| [input-projection-correction-02](input-projection-correction-02.json) · [stderr](input-projection-correction-02.stderr.log) · [stdout](input-projection-correction-02.stdout.log) | 15 / 15 / 0 / 0 / 0 | 77.601 / 0 | True | 完整原文档校验后的独立输入投影；14正式与1诊断共15PASS，第三轮约0.585秒，时限未变。 |
| [w02-b-final-04](w02-b-final-04.json) · [stderr](w02-b-final-04.stderr.log) · [stdout](w02-b-final-04.stdout.log) | 57 / 57 / 0 / 0 / 0 | 164.63 / 0 | True | 最终冻结04专项，见实际完整结果。 |
| [w02-a-compatibility-04](w02-a-compatibility-04.json) · [stderr](w02-a-compatibility-04.stderr.log) · [stdout](w02-a-compatibility-04.stdout.log) | 66 / 66 / 0 / 0 / 0 | 91.768 / 0 | True | 最终冻结04的原A兼容。 |
| [affected-compatibility-04](affected-compatibility-04.json) · [stderr](affected-compatibility-04.stderr.log) · [stdout](affected-compatibility-04.stdout.log) | 509 / 509 / 0 / 0 / 0 | 644.3 / 0 | True | 最终冻结04受影响公共模块组合。 |
| [full-final-04](full-final-04.json) · [stderr](full-final-04.stderr.log) · [stdout](full-final-04.stdout.log) | 1703 / 1702 / 0 / 0 / 1 | 3191.57 / 0 | True | 最终源码稳定后的必要完整回归；不复用旧源码通过。 |

## 辅助工具观察及证据限制

勘查过程存在无效路径/PowerShell参数、Windows通配参数、尝试读取尚未FINISHED的结果字段、一次重复patch路径拒绝，以及当前权限下CIM只读查询拒绝；这些未伪报成测试通过或引擎行为失败。读取路径均按实际文件改正，未借错误覆盖任何已有成果。最终进程检查以实际工具记录为准。

诊断probe中的计时是当次TEST观测，不是生产性能承诺。新的准备全流程时延检查没有通过扩大期限掩盖超时；只减少同一次调用中重复的日志解析，当前权限之后仍重读核验，没有跨请求缓存授权。

原1646测试身份及旧测试文件未变。新增场景中的辅助构造错误修正为既有契约要求的事件类型、字段和参数；没有删除旧断言、修改原探针或将失败改为SKIP。所有当时文件身份在对应JSON中。

原历史F1/H1/F2继续UNKNOWN。本批任何成功不证明旧根因，不关闭旧记录。未取得远端CI，不宣称CI PASS。
