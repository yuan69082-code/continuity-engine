<!-- W04_4_LATEST_DELIVERY_20261001 -->
当前状态（2026-10-01）：W04-4及包级 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。最终定向、W04、公共兼容及全量已同版完成；实际结果见[交付报告](final-report.md)与[测试索引](test-index.md)。P13/C1同一批准已生效，不再待确认。以下开工、验证进行中或待确认字样均为保留的历史快照。未验收、暂存、提交、push，不W05。

# W04-4 当前有效任务

## 2026-10-01 当前有效停点：最终全量发现两处超时，继续定点调查

### 后续补修与第二版固定验证（同日新增，不覆盖下文首次失败）

full-errors-repair-01原UI/包级及来源副本对照PASS，两个新增测试的外层异常预期错误已保留，改为核验原C1包装和内部真实原因；full-errors-guards-02三项PASS。full-errors-stations-after-01两项PASS，回忆准备UI787.441ms、包级827.428ms，均轻量诊断并非整轮回答耗时；原1000ms/负载保持。详见final-timeout-investigation-02.md。

最终源码重新固定为331项 `sha256:63b8189dda6bca9a7cb5985cfeded9e0d920aca284500d32bdded91040307261`；原1923身份及旧文件字节保留，新增52，共1975。与首版冻结差异仅cross_entry_service.py、json_environment_repository.py及新增test_w04_4_boundaries.py的3个正式对照；旧final-01结果仅覆盖旧版。

verification-sequence-02.py按预定顺序运行targeted-final-02、w04-final-02、public-final-02、full-final-02，任何非零即停，不自动重试。主exec会话4916，原实际子进程/日志须再次核验；不能仅凭本记录预填完成。不在测试期间修改源码。pre-final-02.audit.json核验保护63/正式7/三规划/70保留/旧测试/历史正文/原首次全量失败均无变，暂存仍空。

P13/C1同一授权已获用户批准，不等待重复确认。以下旧日期段落均为历史快照。

冻结版331项 `sha256:2e910dd2cd8a4dfe19e8ec64485f26daa3cbc64b2e1aeef6843f88f7202919f9`：targeted-final-01 49 PASS；w04-final-01 196 PASS；public-final-01 1144 PASS/1既有SKIP。full-final-01实际1972项、1969 PASS/1既有Windows1314 SKIP/2 ERROR，退出1，2253.815秒（unittest）。两处均为B回复的RECALL_TIMEOUT：模拟UI完整链和W04包级组合。集合重叠，不相加；不能交付全量通过。原始三件及hash见full-final-01-failure-preservation.json；旧session12473已结束，不再续等或重复启动。

full-errors-stations-01按事先声明两场景各一次：UI链PASS，回忆855.962ms；包级ERROR，保存RECALL_TIMEOUT/1098.926ms/检索17项（外层含失败保存1142.175ms）。环境记录读取256次390.091ms，原操作记录161次189.123ms；均嵌套统计，不能相加。观察记账开销约2.662ms、GC约0.034ms，不据此断言全量当时的唯一原因。正在单次full-errors-copy-stations-01拆分环境路径检查/副本及账本副本成本；原负载、1000ms与断言不变，没有重跑全量。无源码修改发生在这两次诊断期间。

当前IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT。下一步证据定位后最小优化、原反例及权限/来源/私有副本对照，再固定新源码完成必要同版验证。未验收、不暂存/提交/push、不W05；历史F1/H1/F2 UNKNOWN保留。

2026-09-29，D-092开工：实现本批及W04包级贯通，不验收/暂存/提交/push/W05。baseline已核对c910be8、321项aa96381b…、70保留、63保护、正式7及3规划，实际远端一致。授权进程核查无Python。尚无运行源码修改、无测试启动。

已读取：现行索引/阶段映射、总施工W04正文、最终新增C01—15/N15/N16/T33—42、原D-091/初版及返修矩阵；正在定位共用链。候选文件见stage-brief和matrix。下一步完成内部版本化入口/转用/投递设计，保存正式入口缺口证据后施工。原测试1923身份在baseline。

注意protected interfaces/local_integration_app.py不可修改；通过core factory已有可选参数接线。原operation record可加内部可选字段，原EnvironmentRepository可复用绑定配置但不得建第二业务账本。完整原消息→C1→表达/Action→P17/E5-A，TEST替身只提供外界。

## 最新安全停点：2026-09-29（上文是开工历史）

当前不是“无源码修改/无测试”，而是已形成16份源码/测试改动的开发版；当前指纹 sha256:7f6ed84a73215ccac21d6a4c2b1578a36970943f51952fa83bd25891a56fc34b，共326份源码/测试/资源。原321路径均保留，旧测试文件不变，新增test_w04_4_continuity.py 13项。

完成证据：independent-scope-01 8 PASS（施工窗口，不是独立复核）；compatibility-interim-01 153 PASS/退出0/279.081秒外层，前后hash同当前。会话83610已取回最终退出码，不盲目续接。2026-09-28T18:58:27.7243308Z CIM显示Python0，不留本轮后台进程。

N16遇PLANNING_CONFLICT并已通过异步问题请求用户确认P13/C1两处公共判定/顺序修补；截至本记录尚无答复。不要将一般施工授权代替该待决修改。其他8项边界已取证；尚未完成内容见interim-report-01。未跑最终全量，无包级通过证据。

恢复时先核用户决定、interim.audit-01.json及interim.files-01.json、当前源hash、Git和进程。若批准，则在原P13/C1职责内最小修补并覆盖decide/verify当前与历史，保留旧拒绝和独立内部提交；不能绕过CONTACT_USER确认。随后补真正native续接、API/UI全链、投递状态、UNKNOWN新询问、权限/恢复及包级集成，固定最终源码再完整专项/兼容/全量。

新证据使用新标签，保留全部旧ERROR/辅助错误/剖析输出。既有1000ms/2048/2need不变。不验收、不暂存/提交/push，不启动W05。


## 用户已确认两处公共补修（2026-09-29）

用户本轮“确认”承接上一轮明确方案，授权P13确认判定与相关C1表达先于投递的最小修补；不重新开工、不验收或写Git。原冲突提出和待确认时点原样保留。停点指纹7f6ed84a…与90项清单、70份保留hash均一致，main/HEAD c910be8未变、暂存空。

已修改expression_policy_service.py及continuity_interaction_service.py：精确确认满足原requires_confirmation，拒绝不被绕过；原绑定artifact记录确认核验理由，历史核验与当前消费分开；仅相关新入口在派发前生成/核验表达，旧默认接线不变。删除新EntryDecisionPolicy的临时重复预检，恢复与当前派发由原C1/P13分别核验。新增test_w04_4_expression.py七项正式回归。

confirmation-repair-01已越过原P13冲突，后在新入口读取W03有界事项投影时ERROR；保留原件，修正本批scoped_state/Fixture读取格式，未改W03原状态或预算。expression-repair-01运行新定点、P13及自主性兼容，尚以最终JSON为准，不预填通过。

辅助记录：本轮一次PowerShell不支持的花括号路径组合引发ParserError；一次读取不存在test_p13_expression.py后改用已存在policy/recovery两模块，均非Engine测试缺陷。

仍按原授权完成自主Wake/Thinking→联系闭环。预计新增可选内部ContactIntent保存在原ThinkSession结果，未提供时旧序列化字节不变；新字段只是主体意图，不是权限。沿原native Wake/Action/E5-A接线，旧接口/Schema和第二账本不动。具体兼容补测必须覆盖旧Thinking/P14/P18。


## 2026-09-29 续作事实（第二记录）

expression-repair-01 已完成60 PASS/退出0/87.888秒；仅绑定当时09c6b635…，后续版本不能借用。七项新增P13回归与旧表达/自主性兼容一起执行。

新增内部ThinkingResult.contact_intent、原native Wake/Thinking/P18接线正在实现；不以伪造用户消息驱动主体联系。C1 receive拒绝SUBJECT_CONTINUATION，native原ThinkSession保存主体意图，原E5-A保存请求/效果，不新增请求账本。

native-chain-01是新TEST控制器推进水位不足，native-chain-02是TEST时间格式解析错误；已改为原15分钟驱力推进和P18原时间解析，不改产品寿命/阈值。native-chain-03及native-recall-diagnostic-01记录原生入口RECALL_TIMEOUT，后者1142.770/1089.196ms。native-read-measure-01一次诊断记录183次环境load合计676ms，能力账本未进入复用范围；native-path-measure-01证明补上capability scope后解析约22ms，但288次环境load/安全路径检查分别1031/778ms，不能只修一个热点就称完成。

已在新入口Core.prepare复用原逐次当前字节operation/capability解析；JsonEnvironmentRepository只合并同一次路径检查的重复lstat/resolve，仍每次检查各级路径/重解析点、正式根与仓库禁入和当前字节。native-path-repair-01回忆881/896ms READY后，被P14正确拒绝新EntryStateSource错误改写未变字段版本；已仅对实际变化投影加entry版本。native-version-repair-01已发B模拟消息并完成状态提交，后失败为空tuple与list的新测试类型不一致；修正新增测试类型，不改变“零外部用户消息”断言。

native-chain-04 API/UI各已主动发送，第三轮B回复回忆均TIMEOUT，尚无全链通过。reply-measure-01保留嵌套计时（不相加）：672次environment.load合计1137ms，112次origins/119次状态历史读取；诊断尾部last_trace为None引发辅助AttributeError，不覆盖业务超时。已将新投影内同一来源的逐字段重复授权合为一次投影检查（不跨调用/请求缓存授权）；环境require复用本次初始文档，外部回调后仍重读当前文档并核对原附件/host/generation/入口绑定/暂停设置。原调用参数和拒绝语义保留，待兼容回归。

entry-read-repair-01期间发生本轮已知追加代码修改，before37555d…/after943ae7…不同；2ERROR原件保留，不作为任何同版覆盖或成功证据。此后验证期间不再编辑源码。entry-root-work-01用于验证确证的无根/非Event来源多余全历史扫描修正，运行状态查看其JSON和实际进程，不能凭本记录预填结果。

当前仍IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT。原N16 P13/C1冲突已获用户明确授权并实施，不再等待相同批准。尚需：正常native/API/UI完整链、UNKNOWN新询问与原请求分离、投递状态证据、群聊/多话题/并发/权限/来源恢复、W04因果包级、最终同版专项/兼容/全量。原1923测试文件保留，不验收、不Git写、不W05。

## 2026-09-30 恢复施工：当前事实（历史快照保留）

D-092 继续 IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT。P13精确表达确认、相关C1表达先于投递两处最小公共补修已获用户明确确认，已实施；不再等待同一授权。未验收、不写Git、不启动W05。

恢复核对：main/HEAD c910be8ff65f1384c4942c980fc4087c1b595a87，328项指纹5f41c792…与native-related-memory-repair-01前后完全一致。63保护、正式7、规划、70保留及旧测试文件均无变化，暂存空，未见旧Python测试进程。原native-related-memory-repair-01为1PASS/1ERROR，不能当整体完成。

本次一次轻量测量provenance-stations-before-01：检索686.814ms、Composer212.820ms、补充授权88.956ms（嵌套统计不可任意相加），原1000ms保持。新增来源追溯同次walk复用原记录/祖先投影，无跨请求授权缓存；每次独立来源检查仍读取当前原件。补读取回调后绑定版本核验。provenance-repair-03三项PASS：API/UI正常链及读取中撤权；此前相关native Memory撤权反例已PASS。尚须同最终版集中验证。

新增投递观察只读投影：从原P17 query/E5-A及当前来源核验取得送达/已读证据，发送回执不能冒充已读；delivery-observation-02四项PASS。尝试把事项采纳直接追加在C1返回之后会使原Context过期，已撤下该接线尝试，保留失败；事项仍由原W03入口根据已形成的Thinking意图、当前核验和同一命令采纳/恢复，旧Context不得静默重绑。

contact-pause-internal-before-01实际FAIL：联系暂停在选路时抛错阻断独立native心智提交。定点改为选路只核验读取/身份，实际发送仍由原P17当前与最终关口检查联系权限；repair-01同反例PASS，发送与费用0、独立心智revision推进。相应新增草稿测试从要求异常改为同时断言零发送与合法内部推进；原1923项测试文件未改。

迟到时区入站元数据原误用UTC-only事实解析器，已在新增EntryMessage职责内解析带时区RFC3339并保留原文，冻结事实时间格式不改。并发入站测试改为识别原INPUT_ADMISSION_BUSY且验证未持久化，再沿原身份续接。原STOP命令幂等重放与新RESUME身份分别核验。包级组合第一轮因跨core旧Context不一致被正确拒绝；改为新后续步骤取得自己的当前Context，不改原请求绑定。

辅助记录：恢复清单脚本将planning列表误当映射；两条新测试启动类名错误；新增断言用了错误异常层；模拟观察expires_at遗漏字符串格式；若干只读候选路径不存在。均保留原输出/说明，不当作已证实Engine行为缺陷。首次失败/ERROR不删除。当前专项、公共兼容、全量尚未固定最终版运行，不能借用旧PASS。

下一步：完成包级因果组合、剩余权限/恢复验证，固定源码，再专项、受影响公共兼容及一次全量。历史F1/H1/F2 UNKNOWN、SKIP及无远端CI证据照留。

## 第二版全量开始时的真实进度（2026-10-01）

targeted-final-02：52 PASS/306.026秒；w04-final-02：199 PASS/662.495秒；public-final-02：1144 PASS/1既有Windows1314 SKIP/1666.164秒。三组退出0、前后hash均63b8189d…，集合不相加。full-final-02已开始，当前没有完成汇总，不能计PASS。sequence主exec会话4916仍有效；中断后先检查该记录、日志和实际进程，不重复启动。代码/测试冻结331项、1975身份。进度原始快照verification-progress-02-02.json。

## 最终交回独立复核（2026-10-01）

D-092继续有效；W04-4及W04包级 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT。P13/C1已获授权，不再等待相同批准。源码331项，sha256:63b8189dda6bca9a7cb5985cfeded9e0d920aca284500d32bdded91040307261。

targeted-final-02 52 PASS/0 SKIP；w04-final-02 199 PASS/0 SKIP；public-final-02 1144 PASS/1 SKIP；full-final-02 1974 PASS/1 SKIP；各集合不相加。原1923测试/断言文件字节保持，新52，总1975；全部最终前后hash一致。此前所有ERROR/诊断/不同版PASS均只作历史，不替代最终结果。

原生及UI查询来源撤权、正常API/UI链、读取中绑定变化、独立新询问与身体UNKNOWN边界、四批因果包级已纳入最终正式集。旧Context不静默重绑，事项采纳走原W03公开入口。代码冻结后未修改源码或测试。

恢复入口为[final-report.md](final-report.md)、[final-matrix.md](final-matrix.md)、[test-index.md](test-index.md)、[final.audit.json](final.audit.json)。不要重新启动已完成全量。进程与清理最终观察另见process-final-02.json。未验收、暂存、提交、push，不W05；远端CI未验证，历史F1/H1/F2 UNKNOWN保留。

