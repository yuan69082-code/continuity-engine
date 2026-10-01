"""Publish factual delivery documents only after all frozen validation completes.

Only documents are written. Historical output files and shared-document suffixes
are never rewritten. No test, service, process, or Git mutation is performed.
"""
import datetime,json,pathlib,re,runpy
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
BASE=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
F=json.loads((HERE/'frozen-source-final-01.json').read_text(encoding='utf8'))
snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
assert snap['source']()==F['source']
def put(name,text):
    with (HERE/name).open('x',encoding='utf8',newline='\n') as out:out.write(text)
def dump(name,value):put(name,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def prepend(path,text):path.write_bytes(text.encode('utf8')+path.read_bytes())
def append(name,text):
    with (HERE/name).open('a',encoding='utf8',newline='\n') as out:out.write('\n'+text+'\n')
def result(path):
    r=json.loads(path.read_text(encoding='utf8'))
    if not isinstance(r,dict) or 'command' not in r or 'source_before' not in r:return None
    log=HERE/(path.stem+'.stderr.log');t=log.read_text(encoding='utf8') if log.exists() else ''
    summaries=re.findall(r'Ran (\d+) tests? in ([0-9.]+)s',t)
    finals=re.findall(r'^(OK(?: \([^\r\n]+)?|FAILED \([^\r\n]+)\s*$',t,re.M)
    detail=finals[-1] if finals else ''
    n=int(summaries[-1][0]) if summaries else None
    counts={k:int(v) for k,v in re.findall(r'(failures|errors|skipped|expected failures|unexpected successes)=(\d+)',detail)}
    complete=r.get('status')=='COMPLETED' and n is not None and bool(finals)
    passed=n-sum(counts.values()) if complete else None
    return {k:r.get(k) for k in ('label','status','command','started_utc','duration_seconds','exit_code','hash_before','hash_after')}|dict(
        tests=n,passed=passed,counts=counts,unittest_seconds=float(summaries[-1][1]) if summaries else None,
        summary=detail,has_completed_test_summary=complete,record=path.name,
        skip_lines=re.findall(r'^test_[^\r\n]+\bskipped [^\r\n]+',t,re.M),
        stdout=path.stem+'.stdout.log',stderr=path.stem+'.stderr.log',
        same_final_source=r.get('hash_before')==F['fingerprint']==r.get('hash_after'))
labels=['targeted-final-01','w04-final-01','public-final-01','full-final-01']
finals=[result(HERE/(label+'.json')) for label in labels]
assert all(r['status']=='COMPLETED' and r['exit_code']==0 and r['same_final_source'] and
    r['has_completed_test_summary'] and not r['counts'].get('errors') and not r['counts'].get('failures') for r in finals)
assert finals[-1]['tests']==len(F['test_ids'])
assert finals[-1]['counts'].get('skipped',0)==1,'Investigate any change to the single existing Windows SKIP'
assert len(finals[-1]['skip_lines'])==1 and 'test_symlink_component_rejected_without_writes' in finals[-1]['skip_lines'][0] and '1314' in finals[-1]['skip_lines'][0]
assert not (HERE/'final-report.md').exists(),'Do not overwrite a previous delivery'
rows=[]
for p in sorted(HERE.glob('*.json')):
    r=result(p)
    if r:
        if not r['has_completed_test_summary']:r['classification']='诊断或辅助输出；没有正式完成汇总，不记PASS'
        elif r['exit_code']!=0 or r['counts'].get('errors') or r['counts'].get('failures'):r['classification']='原始失败/ERROR，保留；具体业务与辅助原因见续接、调查报告及原栈'
        elif not r['same_final_source']:r['classification']='中间版本实跑/诊断，不能代替最终覆盖'
        elif r['label'] in labels:r['classification']='冻结最终版本正式实跑'
        else:r['classification']='同版有限定向对照，不代替完整组'
        rows.append(r)
dump('test-index.json',dict(final_fingerprint=F['fingerprint'],no_sum=True,runs=rows,
    original_test_count=len(BASE['test_ids']),new_test_count=len(F['new_tests']),final_test_count=len(F['test_ids']),
    planning_window='Read-only review only; no independent Engine execution claimed',ci='NOT_VERIFIED'))
table=['| 标签 | PASS / SKIP / FAIL / ERROR | 测试/外层秒 | 退出码 | 最终同版 |','|---|---|---|---:|---|']
for r in rows:
    c=r['counts'];counts=f"{r['passed']} / {c.get('skipped',0)} / {c.get('failures',0)} / {c.get('errors',0)}" if r['has_completed_test_summary'] else '无正式最终汇总'
    table.append(f"|[{r['label']}]({r['record']})|{counts}|{r['unittest_seconds']} / {r['duration_seconds']}|{r['exit_code']}|{r['same_final_source']}|")
put('test-index.md','# W04-4 全部运行索引\n\n施工窗口实跑/诊断，与规划窗口只读复核、远端CI分开。集合有交集，不能相加。退出0的诊断包装不等于测试通过；FAILED汇总即使包装退出0仍保留失败。没有最终汇总不计算PASS。精确命令、前后源hash及原始stdout/stderr在同名文件，详细分类见[test-index.json](test-index.json)。\n\n'+'\n'.join(table)+'\n\n原1923身份保留，新增49，共1972；原测试文件字节未改。原1000ms/2048/每轮两need未变；Windows1314 SKIP不算PASS。历史不同版成功不代替最终同版结果。\n')
test_table=['| 最终集合 | PASS | SKIP | FAIL/ERROR | 测试秒 | 外层秒 |','|---|---:|---:|---|---:|---:|']
for r in finals:test_table.append(f"|[{r['label']}]({r['record']})|{r['passed']}|{r['counts'].get('skipped',0)}|0/0|{r['unittest_seconds']}|{r['duration_seconds']}|")
summary='；'.join(f"{r['label']} {r['passed']} PASS/{r['counts'].get('skipped',0)} SKIP" for r in finals)
report=f'''# D-092 / W04-4 与 W04 包级贯通交付

状态：**IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。本次完成施工及同版验证，交回独立复核，不自行验收或关闭复核阻断。D-091及W04前三批验收、所有旧失败保持。W05未启动，未暂存、提交或push。

## 做成了什么

同一主体可以凭可信入口绑定接续具体问题与原事项；原生认知形成新的联系意图，经原表达、Action、P17和E5-A发送。API及模拟UI分别走通A选店问题→无用户新消息的原生续问→B回复→原事项。只认同名不授权；同人多事项分开，群聊收件人、自发回显和三类时间有独立对照。

收到、查到、发送、送达、已读、未答和UNKNOWN保留不同含义。当前允许转用的旧材料才能进入B，输入、原生Event/ThinkSession生成的Memory和普通UI查询资料均沿原根复核；撤权后不能借派生记录绕行。只读inspect不触发观察、模型、学习、派发或revision。

包级因果用例在同一主体/原账本上串起绑定、P16发现、连接/核验、历史查询、原始问题、原生续问、B回复、模拟身体动作/感知、旧身体失权、临时工具清理。它不是前三批旧PASS的拼接；具体ID和模拟成本见[链路样例](readonly-chain-example.md)。

## 修前证据、修改及公共影响

- 原P13当前精确确认与requires_confirmation判断冲突，以及相关C1先投递后表达的问题，已按用户明确授权补修；旧待确认快照保留，当前不再等待相同批准。正常精确确认、拒绝、撤权、历史拒绝不升级均有正式回归。
- `native-related-memory-before-01`证实受限A经原生Event/Memory进入B；修补原始ThinkSession及上下文根追溯。最新UI查询反例`queried-entry-before-01`为1 PASS/1 FAIL；查询没有发送关联仍须追溯原DeviceCommand设备/账号/会话绑定，`queried-entry-repair-01`2 PASS，最终定向集再次覆盖。
- 联系暂停原先在选择阶段抛错，连带阻断独立心智提交；`contact-pause-internal-before-01` FAIL，修后发送/费用0且合法内部revision推进。现实发送仍经过原P17当前和最终检查。
- 正常原生B回复和包级负载曾触发RECALL_TIMEOUT。逐站测量将重复工作定位到环境读取/安全路径、原E5-A解析和副本、来源祖先追溯、结果核验及纯值指纹。只复用当前字节完整验证结果与同次准备内纯值，不缓存授权；逐次读字节、完整日志损坏校验、路径/来源/当前权限与独立返回副本保留。选择在原Router/Composer及原预算内完成。详见[调查记录](package-investigation-20261001.md)和[范围/限制](final-scope-and-limits.md)。
- UNKNOWN旧发送不永久冻结有可靠关联的独立新询问，原发送不重放；未知身体动作不能套用该例外。模拟端若所有查询均不可观察，新发送仍如实等待。没有承诺任意平台exactly-once。

旧公共调用通过可选入口接线保持；内部ContactIntent/entry_record未提供时沿旧格式与路径。SubjectState/Event/ThinkSession、Learning/Evolution、原请求/E5-A仍为唯一权威。事项采纳经公开的adopt_matter调用原W03链，不声称每条消息自动建立事项，也不静默重绑旧Context。具体文件和兼容责任见[文件职责](implementation-map.md)、[最终矩阵](final-matrix.md)及[精确清单](final.pending-files.md)。

## 最终同版测试

源码/测试/资源 **{F['count']}项**：`{F['fingerprint']}`。原1923测试身份和旧测试文件保留，新增49，共1972。以上都由施工窗口实际运行，规划窗口的旧只读检查不是独立实跑；本次尚待新的独立复核。无远端CI证据。

{chr(10).join(test_table)}

各集合交叠，不相加。正式运行期间源码冻结；对应前后hash相同。原始完整命令、退出码、输出、测试身份与耗时见[测试索引](test-index.md)和[frozen-source-final-01.json](frozen-source-final-01.json)。公共范围补充原P03/P04/P05/P06/P08/P09，见[事前清单](public-scope-addendum-01.json)。Windows/Python与隔离配置见[环境记录](validation-environment-20261001.json)。

## 未被本次证明的范围

真实平台、生产凭据/设备、任意自然语言质量、更大/无界负载性能未验证。1000ms回忆与2048上下文未增加；重度剖析超时及所有中间失败原样保留，不承诺以后永不超时。新TEST辅助初始化/类型/错误模块名、历史运行中源码变化均在索引和续接中明示，不冒充行为通过。

W05自然记忆/人格联动/再理解/Dream、P19完整页面、P20/P21生产恢复及P22真实接入仍未开放。历史F1/H1/F2 UNKNOWN不改变；Windows1314 SKIP保留。原70份保留材料、63保护、正式7及三份规划保持，D-085本地档案不冒称已提交。最终逐项保护、历史日志、语法、链接、敏感信息、进程与只读Git见[终局审计](final.audit.json)。

下一步仅独立复核与用户决定，不自行启动W05。
'''
put('final-report.md',report)
chain=None
for line in (HERE/'targeted-final-01.stdout.log').read_text(encoding='utf8').splitlines():
    try:value=json.loads(line)
    except ValueError:continue
    if isinstance(value,dict) and all(k in value for k in ('subject','discovery','connection','history','matter','native','body','cleanup')):chain=value
assert chain is not None
dump('readonly-chain-example.json',dict(source_run='targeted-final-01',source_fingerprint=F['fingerprint'],
    observed=chain,simulation_only=True,not_a_new_execution=True))
put('readonly-chain-example.md',f'''# 同一主体的实际只读链路样例

来自 [targeted-final-01.stdout.log](targeted-final-01.stdout.log) 的本轮实际结果，结构化引用见 [readonly-chain-example.json](readonly-chain-example.json)。本页不启动Engine或重新执行业务。

| 环节 | 原记录身份 |
|---|---|
|Subject|`{chain['subject']}`|
|P16发现|`{chain['discovery']}`|
|临时连接|`{chain['connection']}`|
|指定历史查询|`{chain['history']}`|
|A原始选店消息|`{chain['input']}`|
|原W03事项|`{chain['matter']}`|
|原生Wake/ThinkSession来源|`{chain['native']}`|
|B发送请求|`{chain['delivery']['request_id']}`|
|B用户回复|`{chain['reply']}`|
|Body动作|`{chain['body']}`|
|临时连接清理|`{chain['cleanup']}`|

断言从原始消息的最终Context中查到查询请求，原生接续通过原Thinking产生表达、E5-A保留投递回执；B回复后投递投影为ANSWER_RECORDED，同一事项/主体。Body动作造成模拟值2后进入原Perception，旧身体附件及错误代次被拒绝，工具清理为CLOSED。

发送时快照为SENT、送达/已读NO_EVIDENCE、UNANSWERED；这是该发送时点，不把随后回复倒写成原发送时已读。独立DeliveryEvidenceTests另测有效查询证据提升及失效拒绝。包级TEST实际成本：A {chain['costs']['a']}，B {chain['costs']['b']}，Body {chain['costs']['body']}；是模拟账本单位，不是人民币或生产价格。相同请求恢复不追加费用的证据见正式回归，不从本页重复执行来证明。

对已构造的Engine服务可调用 `entries.inspect(original_request_id)`；要投影送达/已读，仅传已有、当前可读的指定查询请求 `evidence_requests=(query_id,)`。这两个只读入口不生成查询、不调用模型或派发。当前绑定/来源不可用仍拒绝，不能把历史查询副本当永久授权。P19完整页面未施工。
''')
matrix='''# W04-4 与包级最终逐项矩阵

每行都是 IMPLEMENTED_NOT_ACCEPTED，不是用户验收。以下为冻结版本施工实跑；开工/中间矩阵保留在 matrix.md，原待批准冲突已获用户决定并落实，EVIDENCE_CONFLICT仍PRESENT等待复核。

| Planning Item | Code Change / 既有权威入口 | Test（正式方法/模块） | Acceptance Result / 边界 |
|---|---|---|---|
|N15/T33可信身份、群聊、主体回显|cross_entry值对象、Environment原绑定、C1原operation；私聊/群目标与收发账号分开|CrossEntryTests.test_wrong_sender_and_same_display_name_do_not_grant_identity；EntryBoundaryTests群聊/自发回显；W04-1旧身份回归|IMPLEMENTED_NOT_ACCEPTED；同人绑定不扩大共享|
|N15/T35具体事项、多话题、歧义|CrossEntryService.adopt_matter/item + W03 UnfinishedItem原Action/Evolution；原输入根|ContinuationTests.test_same_user_two_matters_and_ambiguous_reference_stay_separate；DeliveryEvidenceTests事项重开/幂等|IMPLEMENTED_NOT_ACCEPTED；不自动为每个想法立项|
|N15/T36当前转用、派生材料|EntryPermission、origins、entry_context_source、input_context_source；原Event/ThinkSession/Memory和DeviceCommand根|test_related_native_memory_cannot_bypass_entry_transfer_withdrawal；UI查询允许/撤权双对照；读取回调中绑定变化；重开查询|IMPLEMENTED_NOT_ACCEPTED；未查到不等于不存在，撤权不删历史|
|N16/T34原生API/UI全链|原P18 Wake/Thinking的ContactIntent、P08/P13确认、C1表达前置、P17设备发送/E5-A|CrossEntryTests API/UI 两条question_followup_reply_same_engine_and_matter；7项EntryExpressionTests|IMPLEMENTED_NOT_ACCEPTED；Fake模型只证明所覆盖工程链|
|N16/T37技术替代与现实拒绝|EntryDecisionPolicy技术route_available；DeviceOperation原当前/最终权限和Reality|UI全链在API不可用时成功；表达前撤权/权限拒绝零效果；W04-2外部指令与观察原专项|IMPLEMENTED_NOT_ACCEPTED；被拒绝效果不能借替代路线执行|
|N15/T38三类时间、迟到/镜像/回显|EntryMessage原始时区及不确定性；原消息根和操作去重|ContinuationTests.test_late_timezone_message_preserves_three_times_and_mirror_root；mirror_deduplicates；subject_echo|IMPLEMENTED_NOT_ACCEPTED；同源不增加独立经历|
|N15/T39、T18并发/恢复|原C1 admission锁、revision、原ThinkSession/operation和E5-A|A/B并发BUSY未提交后原身份续接；test_loss_after_effect_reopens_original_thinking_and_send；原请求重开0新增调用/效果/revision|IMPLEMENTED_NOT_ACCEPTED；不是生产分布式恢复|
|N16/T40投递事实/UNKNOWN|inspect/delivery_evidence只读原回执/查询；P17独立新询问例外严格绑定|4项DeliveryEvidenceTests；test_native_new_inquiry_can_send_when_original_remains_unknown；unknown_body_effect反例|IMPLEMENTED_NOT_ACCEPTED；发送不冒充送达已读，UNKNOWN不盲重放|
|N16/T42统一联系暂停、Owner控制|原Environment用户级contact_pause；P17最终控制；原P18|A暂停阻止B；独立native心智推进0效果；Owner PAUSE/STOP与沉默；旧P18全兼容|IMPLEMENTED_NOT_ACCEPTED；局部现实拒绝不是主体关闭|
|N10/N21、T18/26—32/41/60/72/85—87适用范围及包级|W04前三批原Binding/工具/Body/局部查询 + 新入口接线|W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities；同版W04全专项|IMPLEMENTED_NOT_ACCEPTED；T66/67仅本批查询契约，不提前实现W05|
|C01—C15、T25/T43/T45|原只读业务记录/权限/成本与源hash；无新页面|inspect重开无推进；包级真实ID与TEST费用；原公共兼容/完整回归|IMPLEMENTED_NOT_ACCEPTED；完整中文观察页面P19，实际平台P22|
|当前字节/损坏/副本/纯值复用兼容|原environment/SubjectState/Thinking/integration/outbox仓储、temporary_tool_service、action_planning|5类投影/副本/损坏/值突变新回归；原P03—P18/W02/W03/自主性兼容|IMPLEMENTED_NOT_ACCEPTED；写入、CAS、权限与数据格式未被缓存替代|

方法全名、精确身份与执行结果以 frozen-source-final-01.json 和 test-index.json 为准，表中短名便于查阅；不增加新的测试数量。全矩阵共同绑定 final-report.md 的最终源码。
'''
put('final-matrix.md',matrix)
append('matrix.md','## 2026-10-01最新事实\n\n最终逐项证据移至[final-matrix.md](final-matrix.md)，历史表保持原时点。W04-4/包级为IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT；P13/C1已获授权并完成，不再等待同一决定。\n')
append('continuation.md',f'''## 最终交回独立复核（2026-10-01）

D-092继续有效；W04-4及W04包级 IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT。P13/C1已获授权，不再等待相同批准。源码{F['count']}项，{F['fingerprint']}。

{summary}；各集合不相加。原1923测试/断言文件字节保持，新49，总1972；全部最终前后hash一致。此前所有ERROR/诊断/不同版PASS均只作历史，不替代最终结果。

原生及UI查询来源撤权、正常API/UI链、读取中绑定变化、独立新询问与身体UNKNOWN边界、四批因果包级已纳入最终正式集。旧Context不静默重绑，事项采纳走原W03公开入口。代码冻结后未修改源码或测试。

恢复入口为[final-report.md](final-report.md)、[final-matrix.md](final-matrix.md)、[test-index.md](test-index.md)、[final.audit.json](final.audit.json)。不要重新启动已完成全量。进程与清理最终观察另见process-final-01.json。未验收、暂存、提交、push，不W05；远端CI未验证，历史F1/H1/F2 UNKNOWN保留。
''')
append('package-investigation-20261001.md',f'''## 后续定位与最终版本（原记录保留）

package-reply-stations-01：B回复1088.187ms；环境读取292次/391ms，operation155次/168.5ms，origins233次/113.6ms；Router726.86和Composer221.44为嵌套统计，不相加。按一次来源检查复用初始完整环境文档，回调后重读并比较绑定；不缓存授权。package-binding-batch-01后续错误是新增TEST错误地把单独身体更换与host代次推进混用，原OLD_HOST_FENCED正确；隔离测试改走原disable/register身体附件，再核旧身体及错误代次拒绝，未改变host语义。

w04-entry-development-01中间45PASS之后，又用两条正式查询反例验证普通UI资料绕转用问题；before为1PASS/1FAIL，repair为2PASS。新增原生UNKNOWN发送可独立新问与未知身体动作不可重放两项，同版定向通过。最终source为{F['fingerprint']}，最终结果见test-index而非这些中间标签。

辅助：续作一次CIM进程详情查询被系统拒绝，随后用已知exec会话和Get-Process核实原进程；一次Windows rg通配路径无效后改用-g。不是Engine测试失败，不隐藏。任何重度剖析/轻量计时与无插桩正式测试分列。没有为性能改1000ms、2048或减少包级负载。
''')
append('stage-brief.md','## 最终实际文件范围\n\n实际源码/测试逐路径及hash见final.files.json，公共影响与旧数据兼容见final-scope-and-limits.md。前述候选及待授权时点保留；最终P13/C1已获确认。未修改63保护、正式7、规划、版本、70保留或旧测试文件。最终每组验证保持同版，W04-4及包级仅IMPLEMENTED_NOT_ACCEPTED，不启动W05。\n')
for name in ('continuation.md','matrix.md','stage-brief.md','final-scope-and-limits.md'):
    prepend(HERE/name,f'''<!-- W04_4_LATEST_DELIVERY_20261001 -->
当前状态（2026-10-01）：W04-4及包级 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。最终定向、W04、公共兼容及全量已同版完成；实际结果见[交付报告](final-report.md)与[测试索引](test-index.md)。P13/C1同一批准已生效，不再待确认。以下开工、验证进行中或待确认字样均为保留的历史快照。未验收、暂存、提交、push，不W05。

''')
for relative in BASE['shared_hashes']:
    path=ROOT/relative;prefix='docs/project_memory/w04_4_evidence/' if relative=='README.md' else 'w04_4_evidence/'
    text=f'''<!-- W04_4_FINAL_D092_20261001 -->
## D-092：W04-4及包级施工交回独立复核

W04-4与W04包级均为 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**，不是用户验收；前三批D-087/D-089/D-091不改。P13/C1两处公共修补已有用户明确确认并实施，下面的“等待同一批准”仅为历史时点，不再代表现行状态。

已完成可信入口/事项接续、原生API及模拟UI续问回流、当前转用和Event/Memory/UI查询追溯、投递证据/UNKNOWN独立新问、统一暂停及四批因果组合。来源撤权初始FAIL与回忆超时、中间辅助错误均保留；优化逐次读当前字节并核权限，不改变1000ms/2048/两need或唯一账本。

施工窗口最终同版实跑：{summary}，交叠不相加。源码{F['count']}项 `{F['fingerprint']}`；原1923测试身份/旧断言文件不变，新增49。不是规划窗口实跑或远端CI PASS。

历史F1/H1/F2 UNKNOWN、Windows1314 SKIP、旧FAIL/ERROR/格式提示保留。真实服务/设备/生产凭据、W05、P19页面、P20/21恢复和P22实接未开放；未验收、暂存、提交或push。下一步仅规划窗口独立复核和用户决定。

[交付报告]({prefix}final-report.md) · [逐项矩阵]({prefix}final-matrix.md) · [测试索引]({prefix}test-index.md) · [精确清单]({prefix}final.pending-files.md) · [终局审计]({prefix}final.audit.json) · [支持范围]({prefix}final-scope-and-limits.md)。以下全部历史正文原字节保留，本段不生成新决策编号。

'''
    assert b'W04_4_FINAL_D092_20261001' not in path.read_bytes()
    prepend(path,text)
print(json.dumps({'status':'documents_created','results':summary,'source':F['fingerprint']},ensure_ascii=False))
