# W04-4 中间测试索引（不是最终交付）

全部为施工窗口本轮实跑/诊断，未取得规划窗口独立实跑或远端CI结果。各集合不得相加。完整命令、源码前后身份和原始输出见同名JSON及日志。

| 标签 | 退出码 | 外层耗时秒 | 当前源码匹配 | 真实结论 |
|---|---:|---:|---|---|
|[before-entry-01](before-entry-01.json)|1|0.538|False|辅助脚本误用 str 代替 Path；非 Engine 缺陷，未进入目标链。|
|[before-entry-02](before-entry-02.json)|0|0.876|False|修前旧 C1 不接受 entry_message 的真实入口缺口证据；诊断退出0不等于正式测试PASS。|
|[compatibility-interim-01](compatibility-interim-01.json)|0|279.081|True|施工窗口153/153 PASS，unittest278.354秒；中间兼容，不是最终全套兼容或全量。|
|[confirmation-conflict-01](confirmation-conflict-01.json)|0|1.427|True|诊断未到目标路径；异常被诊断捕获故退出0，不能计PASS。|
|[confirmation-conflict-02](confirmation-conflict-02.json)|0|1.427|True|诊断记录 NamedTemporaryFile/FileNotFoundError，未到模型，未证明唯一原因；不能计PASS。|
|[confirmation-conflict-03](confirmation-conflict-03.json)|0|2.532|True|短TEST根路径到达目标：精确确认true，Action approved/require-confirmation均true，P13仍PLATFORM_DENIED；新增守卫下模型1次、A/B效果及费用均0。是冲突证据，不是通过测试。|
|[entry-draft-01](entry-draft-01.json)|1|2.769|False|新增入口检查重复工作触发 RECALL_TIMEOUT；1 ERROR，原1000ms未改。|
|[entry-draft-02](entry-draft-02.json)|1|2.974|False|TEST fixture 未接入既有 expression.emit 授权视图；1 ERROR，后来补接但原件保留。|
|[entry-draft-03](entry-draft-03.json)|1|8.607|False|C1完成核验报 C1_ACTION_HISTORY_WITH_DENIED_EXPRESSION；1 ERROR。未保存当次效果计数正文，不能把路径推断冒充直接计数。|
|[entry-profile-01](entry-profile-01.json)|0|3.531|False|有开销的 cProfile 定位环境配置重复读取；unittest 1 ERROR，包装进程0不得算PASS。|
|[entry-scope-01](entry-scope-01.json)|1|27.485|False|3项中2 PASS/1 ERROR：跨入口第二轮 RECALL_TIMEOUT，旧结果不覆盖当前版本。|
|[independent-scope-01](independent-scope-01.json)|0|31.523|True|本施工窗口实跑8/8 PASS；标签指不依赖冲突项的集合，不是规划窗口独立实跑。|
|[scope-02](scope-02.json)|1|7.96|False|第二轮仍 RECALL_TIMEOUT，1 ERROR；保留该次优化不足的证据。|
|[scope-light-01](scope-light-01.json)|0|11.932|False|轻量计时诊断；回忆准备794.51ms/检索11项，非全链时间，也不是最终版专项PASS。|
|[scope-profile-01](scope-profile-01.json)|0|32.805|False|有开销的 cProfile 定位原操作日志重复完整解析；unittest 1 ERROR，包装进程0非PASS。|

源码仍是开发中间版；8项及153项通过不代表W04-4完成。API/UI主动联系完整链、包级贯通及最终全量尚未完成。
