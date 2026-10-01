"""Publish factual final documentation only after every frozen run completed."""
import datetime,json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent
version=sys.argv[1] if len(sys.argv)>1 else 'final-02'
frozen=json.loads((HERE/('frozen-source-'+version+'.json')).read_text(encoding='utf8'))
labels=['lineage-prefix-repair-09']+[group+'-'+version for group in ('w04','public','full')]
results=[]
for name in labels:
    run=json.loads((HERE/(name+'.json')).read_text(encoding='utf8'))
    assert run['status']=='COMPLETED' and run['exit_code']==0
    assert run['hash_before']==run['hash_after']==frozen['fingerprint']
    stderr=(HERE/(name+'.stderr.log')).read_text(encoding='utf8')
    found=re.search(r'Ran (\d+) tests? in ([0-9.]+)s\s+OK(?: \(skipped=(\d+)\))?\s*$',stderr)
    assert found, name
    total=int(found[1]); skipped=int(found[3] or 0)
    results.append(dict(label=name,total=total,passed=total-skipped,skipped=skipped,
        failures=0,errors=0,exit_code=0,unittest_seconds=float(found[2]),
        controller_seconds=run['duration_seconds'],hash=run['hash_after'],command=run['command']))
assert [(r['total'],r['skipped']) for r in results]==[(17,0),(215,0),(1145,1),(1991,1)]
process=json.loads((HERE/'process-final.json').read_text(encoding='utf-8-sig'))
assert process['owned_python_count']==0
def put(name,text):
    with (HERE/name).open('x',encoding='utf8',newline='\n') as out:out.write(text)
def jsonput(name,value):put(name,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
jsonput('selected-runs.json',dict(final=labels,results=results,
    previous_delivery='w04_4_evidence/full-final-02: 1974 PASS / 1 SKIP; historical version only',
    source_fingerprint=frozen['fingerprint'],source_count=frozen['source_count'],
    overlapping_groups_not_added=True,independent_review='static only',ci='NOT_VERIFIED'))
table=['|集合|PASS|SKIP|FAIL/ERROR|退出码|unittest / 控制器秒|','|---|---:|---:|---|---:|---|']
for r in results:
    table.append(f'|[{r["label"]}]({r["label"]}.json)|{r["passed"]}|{r["skipped"]}|0 / 0|0|{r["unittest_seconds"]} / {r["controller_seconds"]}|')
table='\n'.join(table)
report=f'''# D-092 / W04-4 两项独立复核返修交付

状态：**IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。R1/R2在本机隔离TEST形成修前反例并完成最小补修，同版验证见下表；交规划窗口独立复核及用户决定，不自行关闭复核阻断或验收。W04前三批验收不改，不W05，不暂存、提交或push。

## R1：状态值及派生内容的入口来源

原按整个字段最后一个C1写入入口过滤，保留在APPEND/SET中的A值被B末次写入掩盖；无C1映射的原生更新也缺少来源处理。修前真实原始消息经过C1、Thinking、Action、Evolution把A私有标记写入current_focus；撤转用后B追加合法值，再次响应中A标记同时进入最终Context和模拟表达。重开仍复现，正常授权对照通过。

`services/cross_entry_service.py`现在按原StateUpdateRecord.changes重建仅供当前读取的逐值来源；不变的值保留旧来源，新值继承原Event及原ThinkSession实际获得的片段，按片段历史revision追溯。来源关系包括engine.subject-state；原生/间接更新不再因缺C1映射被跳过。原权威State及Event历史不删除，不建立第二来源账本。当前转用与绑定每次重核；当前投影、Resolver与版本/内容核验保持。

列表逐值保留可读成员。原结构化字段的有界投影不能证明细粒度来源时保守保留该字段完整来源；事项则按实际提供的next项身份追溯，不能把已隐藏项当作模型读过的材料而挡住B合法表达。原生及普通C1派生、SET保留值、重开、读取中绑定变化、只读查询、重复旧请求不重复提交均有正式回归。

## R2：最后观察和回调后的入口许可

原入口检查在观察前，后续附件/能力检查不能替代入口绑定、read_from和联系暂停检查。修前在模拟port持设备事务锁的final guard最后一次observe内改变上述条件，页面和附件不变，实际B发送效果与credits各1。三种交错均有有效反例；绑定辅助输入错误另存，未冒充产品FAIL。

`services/device_operation_service.py`在原同步派发边界的observe/connection回调之后再次调用原delivery_current；后者所有回调结束后重读原控制文档，任何期间变化拒绝。修后三种观察交错及剩余连接/权限回调均零发送、零费用；权限未变仍一次合法发送/一次费用。原P17/E5-A请求、回执、设备事务、UNKNOWN及重放规则不改，不承诺任意生产并发下的瞬时撤权保证。

联系暂停/绑定变化对照仍验证独立原生心智提交。转用撤销导致旧Context真正失效时保留拒绝和WAITING_VERIFICATION，不静默重绑；以新的B原始消息取得当前Context，证明合法内部提交仍可进行。失效旧请求重开/重复仍核验原Event、revision与效果/费用不增加。

## 同版施工实跑

{table}

这些集合相交，不能相加。源码/测试/资源{frozen['source_count']}项：`{frozen['fingerprint']}`；原1975项身份及旧测试文件原字节保持，新增16项，共1991。规划窗口提供的是静态只读意见，未独立运行这些测试；本次以上各组为施工窗口实跑。既有Windows1314 SKIP不计PASS。没有远端CI结果。

原331项/63b8189d…的1974 PASS/1 SKIP仍是旧交付的有效历史证据，不能作为新版本覆盖。修前、辅助错误、修补引入的过度过滤、首轮修后失败及全部诊断在[test-index.md](test-index.md)和[repair-progress.md](repair-progress.md)逐项列出，未覆盖、删改或循环全量求绿。

## 公共影响与范围

本轮运行差异为CrossEntryService、同职责EntryStateSource/Resolver及DeviceOperationService；新增正式测试只有test_w04_4_review_repairs.py。旧P13/C1已批准补修保留。来源投影用于原Router/Composer、回忆、Event/Memory派生及投递当前检查；最终入口再核验用于已有设备发送链。外部Schema、权限政策、费用、主体性、调度、生命周期及运行寿命未改变；1000ms与2048配置、原断言和时限不改。

首轮冻结版W04专项213 PASS/2 ERROR，原包级与新六轮SET触发RECALL_TIMEOUT，原日志不改。逐站测量证实每个状态候选重复过滤六分区；改为当前所需分区后仍完整验证原记录，并递归查实际祖先。一次投影复用开始控制文档，回调后再次读取当前文档；授权不跨检查保存。R2重复消费回执检查改为全部回调后一次完整核验，发送仍保留观察前和最终两次。同一来源walk按真实after_revision复用已重建前缀及子节点来源集合，不跨读取保存授权。详见repair-progress；旧失败和插桩结果不能冒充最终正常性能。本次未放宽时限、缩减负载或修改旧断言。

验证只证明当前本机TEST负载及明确交错，不能推出真实平台、真实模型语义、无界历史负载或生产性能。旧Context失效仍拒绝；没有删除历史或把真正UNKNOWN改成成功。历史F1/H1/F2仍UNKNOWN，原有中断/超时/辅助错误/行尾提示照留。P19页面、P20/21正式恢复、P22真实接入、W05梦境等仍未开放。

## 复核入口

[逐项矩阵](matrix.md) · [测试索引](test-index.md) · [冻结身份](frozen-source-{version}.json) · [原静态意见副本](independent-readonly-review.json) · [原件/副本hash与开工身份](baseline.json) · [终局审计](final.audit.json) · [累计精确清单](final.pending-files.md) · [逐文件hash](final.files.json) · [70项排除](exclusions.json) · [只读链路样例](read-only-examples.md)。

63项保护、7份正式数据、三份规划原文、70份保留和旧历史后缀是否一致，以终局审计实测为准；审计必须全部满足后才交付。Git只读，实际远端本次未重新查询；不把本地origin/main冒充远端或宣称CI PASS。
'''
put('final-report.md',report)
put('matrix.md','''# 两项定点返修逐项矩阵

全部Acceptance Result均为IMPLEMENTED_NOT_ACCEPTED，等待独立复核；EVIDENCE_CONFLICT=PRESENT，不登记用户验收。现行v1.6/v1.6/v6.10，沿D-092。

|Planning Item|Code Change|Test / evidence|Acceptance Result|
|---|---|---|---|
|N15/T36：A受限值不能被B末次写入洗去来源|cross_entry_service.scoped_state / _state_lineage / _lineage_node|counterexamples-before-01有效FAIL；test_state_append_withdrawal_*、授权对照、SET；最终Context和实际表达|IMPLEMENTED_NOT_ACCEPTED|
|N15/C来源：原生及间接状态传递|_fragment_origins / _state_origins / origins；原Event/ThinkSession/历史revision|test_indirect_state_derivation_*、test_native_*；原State保留、重开、正常对照|IMPLEMENTED_NOT_ACCEPTED|
|N15：合法B材料不被全面屏蔽|当前投影hash校验、仅实际提供的事项来源|test_redacted_matter_does_not_block_independent_b_expression；selected-state-before-05 ERROR与repair-06 PASS|IMPLEMENTED_NOT_ACCEPTED|
|N16/T42：最后观察后入口权限有效|device_operation_service._current末端delivery_current；原控制文档回调后比对|三种final_observation拒绝及正常1/1对照；原始final guard请求/页面hash、效果/credits记录|IMPLEMENTED_NOT_ACCEPTED|
|N16/C边界：剩余回调不能绕过暂停|delivery_current最终原控制文档再读|remaining_connection_callback / remaining_permission_callback，零效果与费用|IMPLEMENTED_NOT_ACCEPTED|
|T18：恢复及独立合法内部认知|原请求/原Event不重建，失效Context仍拒绝|state_query_and_same_request_reopen；transfer撤回后新合法Context，binding/pause原生心智提交|IMPLEMENTED_NOT_ACCEPTED|
|只读/权限变化|scoped_state回调后重读、原入口拒绝|state_read_binding_change / state_query，模型、效果、费用、revision不推进|IMPLEMENTED_NOT_ACCEPTED|
|W04包级及公共兼容|两个原补修文件及同职责entry_context_source单分区重验；不缓存授权|同版W04、公共及完整回归；见test-index.md|IMPLEMENTED_NOT_ACCEPTED|

修前5 FAIL含辅助问题，不能称五个Engine缺陷；具体分类见repair-progress.md。旧规划/旧失败/历史验收原样保留。下一步仅独立复核与用户决定。
''')
index=['# 本轮测试原始证据索引','',table,'',
       '命令、UTC时间、控制器退出码及运行前后逐文件源码在各同名JSON；原始输出在同名stdout.log/stderr.log。',
       '所有隔离TEST，无真实设备/网络/账号；本轮仅当前四组可作为最终同版覆盖。','',
       '## 全部运行历史（不覆盖旧标签）','', '|标签|状态/退出码|控制器秒|源码前后相同|','|---|---|---:|---|']
for file in sorted(HERE.glob('*.json')):
    d=json.loads(file.read_text(encoding='utf-8-sig'))
    if not isinstance(d,dict) or 'command' not in d or 'label' not in d:continue
    name=d['label']; index.append(f'|[{name}]({name}.json)|{d.get("status")} / {d.get("exit_code")}|{d.get("duration_seconds")}|{d.get("hash_before")==d.get("hash_after")}|')
index+=['','诊断脚本退出0不等于Engine正式测试PASS；原生诊断只解释夹具路线，不用于最终计数。原始汇总为准。',
        'counterexamples-before-01的绑定夹具错误、首次修后旧Context断言、可选片段预算、包装异常和辅助属性错误逐项见repair-progress.md。',
        '原旧最终全量1974 PASS/1 SKIP仅引用；未重新写成当前版本测试。F1/H1/F2 UNKNOWN、Windows1314 SKIP及原始超时/中断保留。','',
        '复跑：设置PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1、PYTHONPATH包含src与tests；使用run.py的未占用新标签和冻结JSON的groups。不得重用已有标签或同时启动全量。',
        '本次已完成最终验证，交付后不自动再跑。','']
put('test-index.md','\n'.join(index))
put('read-only-examples.md','''# 可定位的真实链路与只读复核

R1：原始“记下关注：A_PRIVATE_FOCUS_812”→C1处理→TEST Provider提出APPEND→原Action/Evolution/Event→current_focus；撤销A→B→B原始追加→原字段保留双方值。随后B原始回顾→当前逐值来源投影→原Router/Composer→实际Provider输入→模拟B表达。修前A与B均出现，修后只有B可见；权威State和原Event仍有A。原始观察见lineage-prefix-repair-09.stdout.log内state-append记录，包括original_event、Context/表达布尔值及revision。

原生/间接：原ThinkSession实际获得A材料，提出关联判断，经原链提交；撤转用后B追加自己的独立原始材料。重开后读取最终Context和表达：派生A不可用，独立B仍可用。历史来源按原片段revision追溯，不能用今日最后写入者代替。

R2：A实际问题→原事项→真实Runtime认知/表达→P17/E5-A请求→B模拟port事务内final guard→最后observe保持页面但变更入口许可→末端再核验→无效果、无credits。原始输出final-observation含guard_request与observed_hash/after_observation，证明触发位置；未变对照1效果/1credits。

仅阅读上述JSON/stdout、matrix和冻结清单不会启动Engine。已有entries.scoped_state/inspect只读能力仍沿当前权限；正式测试证明重复查询不触发模型、学习、动作或revision。旧Context失效后原请求不被重绑，新合法内部步骤另经当前C1准备。这里不提供P19页面，也不让读者启动生产主体。
''')
shared=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))['shared_hashes']
marker='<!-- W04_4_REVIEW_REPAIR_FINAL_20261001 -->'
for relative in shared:
    file=ROOT/relative; old=file.read_bytes()
    assert marker.encode() not in old
    link=('docs/project_memory/' if relative=='README.md' else '')+'w04_4_review_repair_evidence/'
    text=f'''{marker}
## D-092：两项独立复核返修交回

W04-4及W04包级为 **IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT**。本轮两处静态意见已以真实链复现并最小补修：状态逐值/原生派生来源保留；最后设备观察和剩余回调后重核入口许可。合法B材料及内部提交保持，失效旧Context不重绑。涉及两个补修文件和同职责entry_context_source；旧测试和历史验收不改。

施工方最终同版：定向17 PASS（新增16及原包级1），W04专项215 PASS，公共1144 PASS/1既有SKIP，全量1990 PASS/1既有SKIP，0 FAIL/ERROR，集合不相加。源码332项`{frozen['fingerprint']}`；原1975测试保留，新增16。规划窗口是静态复核，没有独立实跑；无远端CI PASS证据。旧1974 PASS/1 SKIP属于旧版，原FAIL/ERROR/辅助错误/中断/行尾提示及F1/H1/F2 UNKNOWN全留。

[交付报告]({link}final-report.md) · [矩阵]({link}matrix.md) · [测试索引]({link}test-index.md) · [精确清单]({link}final.pending-files.md) · [终局审计]({link}final.audit.json)。1000ms/2048/原调度与权限不变；不承诺无界负载/生产性能或任意并发撤权保证。未验收、暂存、提交、push，W05未启动；下一步仅独立复核。以下是历史时点，原字节保留，本轮不新增验收决定。

'''
    file.write_bytes(text.encode('utf8')+old)
continuation=HERE/'continuation.md'
old_continuation=continuation.read_bytes()
continuation.write_bytes(('# D-092 本轮交付续接\n\n最终四组同版完成，详情final-report.md / selected-runs.json；源码不再修改。尚须或已完成的终局审计看final.audit.json存在及checks，不能仅凭本文宣称审计通过。精确清单final.files.json，70项保留，旧证据原样。无测试继续后台运行；进程记录process-final.json。\n\n保持IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，下一步仅独立复核和用户决定，不验收/暂存/提交/push/W05。以下保留各历史时点原记录。\n\n').encode('utf8')+old_continuation)
print(json.dumps({'final_results':results,'source':frozen['fingerprint']},ensure_ascii=False))
