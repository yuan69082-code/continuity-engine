# 补修记录

- independent-before-01：原八项4PASS/4FAIL，6.803秒；对应A1两项、A2/A3各一项。independent-after-01：8PASS，6.924秒，中间版本。
- formal-01：23项22PASS/1FAIL，28.280秒。新测试在第一轮后的首次tick要求认知，但该次依法执行MAINTENANCE；followup-scheduling-diagnostic.json显示下一次60秒调度机会完成认知，原始断言未弱化、未加超时，测试补齐确定调度顺序。
- recovery-before-01：新加强恢复断言1FAIL，2.196秒。表达拒绝无E5-A请求，内部提交后中断时原恢复试图查询不存在请求，留下unconfirmed任务。A1范围内把空拒绝artifact附于原Evolution事件的已有metadata，保留绑定、不新增账本，不要求未派发效果提供成功回执；实际执行历史仍须原查询。formal-02：23PASS，30.523秒。
- 观察输出归档修正：独立探针会追加自身目录的independent-observations.jsonl。规划侧原件未动；最初副本作为运行观察保留，另存original-independent-observations.jsonl作为逐字节原件副本。archives-created.json保留初始清单，archives.json明确原副本与追加输出关系。后续runner为每标签指定独立观察目录，不改探针内容或断言。
- 一次只读rg使用Windows不支持的命令行glob路径，改为rg -g后读取；不是引擎失败。
- 实现时只读检查发现错误的新增import，运行前改为实际module，并补齐digest导入；未将其记录为已运行Engine失败。

- combined-01：原R1—R4与首批补修61/61PASS、125.598秒。之后新增两个精确边界，旧结果不冒充最终源码覆盖。expression-order-before-01为1FAIL、1.465秒：本轮表达先检查的初稿顺序漏了普通C1原Choice的精确确认步骤，误报PLATFORM_DENIED；现只对mind路径先形成Choice再检查表达/派发，旧非mind顺序保持。query-route-before-01为1FAIL、1.538秒：REQUEST_MEMORY同样是尚未得到结果的路由；将其纳入按实际绑定能力识别，不依赖contact/tool标志，不扫描正文。

- combined-02：63/63PASS，126.864秒，包含原34与新增29，非互不相交组相加。independent-final-01原8/8PASS，7.349秒。后续兼容和全量仍须以最终源码实跑，不能引用旧1551全量覆盖补修。
- A1原Evolution事件metadata新增可选c1_expression_refusal，保存已有格式的空ExpressionArtifact；绑定原Context/Thinking/Action、模式和内容hash。既有事件/仓储版本及冻结Schema不变，已有实际执行请求仍须独立回执验证。此证据只证明派发前拒绝，不代表现实成功。
