"""Finalize only this repair's documentation after complete, matching runs."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(OUT))
from run import source_hashes

def main():
    source=source_hashes()
    labels={'cross':'combined-02','independent':'independent-final-01',
            'compatibility':'compatibility-01','full':'full-final-01'}
    results={k:json.loads((OUT/(v+'.json')).read_text(encoding='utf8')) for k,v in labels.items()}
    for kind,data in results.items():
        assert data['status']=='FINISHED' and data['exitCode']==0,kind
        assert data['sourceBefore']==source==data['sourceAfter'],kind
    baseline=json.loads((OUT/'before.json').read_text(encoding='utf8'))
    full=results['full'];old=set(baseline['testIdentities']);ids=full['testIdentities']
    assert old<=set(ids) and len(set(ids))==len(ids)
    digest='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    added=sorted(set(ids)-old)
    def write(name,text):
        with (OUT/name).open('x',encoding='utf8') as f:f.write(text)
    write('selected-runs.json',json.dumps(labels,indent=2)+'\n')
    write('final-source.json',json.dumps({'source':source,'sourceHash':digest,
        'baselineTests':len(old),'addedTests':added,'testIdentities':ids},ensure_ascii=False,indent=2)+'\n')
    table=['| 集合 | PASS | SKIP | FAIL/ERROR | 秒 | 退出码 |','|---|---:|---:|---:|---:|---:|']
    for kind,label in labels.items():
        r=results[kind]
        table.append(f"| [{label}]({label}.json) | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']:.3f} | {r['exitCode']} |")
    body='''# P19前主体自主性边界 A1/A2/A3 补修交付

本轮补修已实现，等待独立复核。IMPLEMENTED_NOT_ACCEPTED；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT。P00—P18历史验收及D-073保留，P19—P23 NOT_STARTED；无新增验收决定、暂存、提交、push、真实服务或Assistant/Vio操作。

## 根因与实际改动

- **A1**：表达专属确认/现实拒绝原先在内部Evolution前抛错。现在只将明确的表达投递门拒绝保存为已有PLATFORM_DENIED空artifact；不吞生成错误、损坏或当前Context错误。合法内部授权仍须原Action/Evolution、权限、来源、生命周期及revision检查。普通C1先形成原Choice/精确确认后评估表达，mind路径在拒绝时不派发；旧非mind顺序保持。native原Evolution事件metadata可附已绑定的空拒绝artifact，解决内部提交后中断而从未建立执行请求的事实恢复；不新建账本、不改变事件版本或外部Schema，不以拒绝作为执行成功证明。
- **A2**：旧投影只看contact/tool两标志，漏掉expression.emit及查询路由。现在根据原Choice和实际CapabilityBinding的CONTACT_USER/USE_TOOL/REQUEST_MEMORY识别本轮外部执行/结果依赖。原ThinkSession中的模型提案完整保留；当前混合轮只提交Engine有来源的独立心智/成长提案，不扫描成功等文本。当前回执即使成功也不倒签Provider早先提案；后续无新外部请求的认知可在原Router/Composer重新核验回执后形成新的合法判断。真正UNKNOWN仍查原事实、不重派、不重复计费。
- **A3**：旧ended条件把旧desires全部结束当成永久无需求。现在采纳原MindDynamics的当前投影，允许已满足后重新出现的需要，同时排除明确abandon旧目标作为唤醒依据。最低间隔、rest/hold复议、预算、背压、生命周期、PAUSE/STOP均保留；Scheduler不创建欲望。

相对补修起点，增量运行文件仅5个：[continuity_core_service.py](../../../src/continuity_engine/services/continuity_core_service.py)、[continuity_interaction_service.py](../../../src/continuity_engine/services/continuity_interaction_service.py)、[expression_policy_service.py](../../../src/continuity_engine/services/expression_policy_service.py)、[runtime_cognition.py](../../../src/continuity_engine/services/runtime_cognition.py)、[wake_perception_thinking_action_service.py](../../../src/continuity_engine/services/wake_perception_thinking_action_service.py)。新增正式测试[test_pre_p19_supplement.py](../../../tests/test_pre_p19_supplement.py)；原1551项测试身份及其既有测试文件、有效断言未改。既有R1—R4修复成果保留，原失败和调查档案未改写。没有扩大权限、资源计费、D1/D2/D3生产政策或主体目标。

## 当前版本真实验证

'''+ '\n'.join(table)+f'''

原{len(old)}个正式身份全部保留，新增{len(added)}项，当前{len(ids)}项。原独立8项由施工方原样复跑，单列、不增加Engine正式数量，也不代表本次独立监工已确认闭合；交叉/兼容/全量有交集，不重复相加。SKIP仍为既有Windows符号链接权限1314，非PASS。表内耗时为证据runner总耗时，unittest自身计时保留在原始stderr。以上均为本轮实际运行；旧R1—R4的1551项全量只作历史引用，没有远端CI run或CI PASS声明。

当前{len(source)}份源码/测试/资源，指纹 `{digest}`；以上所有组的执行前后均与当前一致，见[最终源码](final-source.json)。

## 失败、修复与限制

修前原八项4PASS/4FAIL（6.803秒），A1两条、A2/A3各一条，见[independent-before-01](independent-before-01.json)。原件副本hash见[archives.json](archives.json)，规划侧原件未改。

formal-01的22PASS/1FAIL是新测试在合法MAINTENANCE tick上要求认知的辅助假设错误；[定向观察](followup-scheduling-diagnostic.json)证明下一次既定机会完成认知，未放宽超时或修改Scheduler。recovery-before-01保留了A1派发前拒绝、内部提交后中断的unconfirmed恢复缺口；expression-order-before-01记录本轮初稿普通C1精确确认顺序回归；query-route-before-01记录A2纯memory.lookup遗漏。对应正式断言均保留并已通过，未用后续PASS覆盖首次失败。所有中间结果及分类详见[补修记录](notes.md)。

这不是在判断思想真伪：限制的是当前执行/结果依赖的入账，不清除原始模型提案、倾向、Will或合法内部认知。混合提案按已有来源保守分离，未引入自然语言关键词审查；未建设新的逐句效果依赖标注格式。正式隐私、联系时段/频率、费用及生产接入仍NOT_READY。持续运行无固定轮数/时长或无消息停机条件；测试由控制器有界观察并STOP。

历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧FAIL/ERROR/SKIP及缺失证据不变。本次三项不得倒推为旧案根因。最终是否闭合仍由独立复核确认。

## 审计与入口

[逐项矩阵](matrix.md) · [命令与全部运行索引](test-index.md) · [最终审计](final.audit.json) · [完整待提交及排除清单](final.pending-files.md) · [进程清理记录](process-cleanup.json)。

审计逐文件检查63项保护、六Schema及外部契约、三份规划、正式七文件/树hash、版本0.1.0/pyproject和原32排除项；额外检查原测试、已有证据、源码AST、本地链接、敏感材料与Git差异。实际数量及格式告警以审计为准，不改写旧原始日志。HEAD和暂存区须与补修起点一致，所有成果留在工作区交复核。
'''
    write('final-report.md',body)
    write('matrix.md','''# A1/A2/A3 复核矩阵

各项当前IMPLEMENTED_NOT_ACCEPTED；测试通过不等于用户验收。测试文件[正式新增回归](../../../tests/test_pre_p19_supplement.py)。

| 项目 | 实现与正反/恢复入口 | 结果范围 |
|---|---|---|
| A1 | ExpressionIndependenceTests：native确认/现实/恢复条件拒绝；普通C1表达开启及合法确认；内部权限/晚撤权/过期Context/失效来源；原Evolution之后崩溃且无执行请求时重开恢复 | combined-02；independent-final-01；兼容及全量 |
| A2 | RoutedProposalTests：contact/expression.emit/execution.read/memory.lookup路由；拒绝/UNKNOWN/真回执；不提交先于效果的模型提案；真实回执经后续Composer消费后的新判断；纯内部反思正常 | 同上 |
| A3 | RenewedNeedTests：原Dynamics outcomes act→recur；无足够新需要不调用；abandon不强制复活；临时抑制；原持久化状态重开、PAUSE/资源等待/恢复/认知实际推进/STOP不复活 | 同上 |
| 原成果 | 原34项R1—R4，及直接相关P09/P13/P14/P15/P17/P18/Action/Permission/Resources/Learning | combined-02及compatibility-01；最终full-final-01 |

集合真实结果及原始输出见[test-index.md](test-index.md)，最终源码见[final-source.json](final-source.json)。不另算独立八项为正式测试增长。
''')
    lines=['# 命令与运行历史','','所有标签唯一，原始stdout/stderr与JSON并存；旧记录不覆盖。','',
        '```powershell',"$env:PYTHONDONTWRITEBYTECODE='1'","$env:PYTHONUTF8='1'",
        "$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'",
        "& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-new-01 test_pre_p19_",
        "& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-independent-new-01 --review-class test_independent_boundaries.IndependentBoundaries",
        "& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-compatibility-new-01 test_p09 test_p13 test_p14 test_p15 test_p17 test_p18 test_action test_permissions test_resources test_learning",
        "& 'E:/Adobe/python.exe' -B 'C:/Users/Administrator/Documents/continuity-engine/docs/project_memory/pre_p19_supplement_evidence/run.py' review-full-new-01",
        '```','','全量不传测试前缀。复核须使用尚未占用标签，配置PYTHONPATH以供现有子进程继承；runner对独立探针仅隔离观察输出路径，不改代码/断言。','',
        '| 记录 | 状态/数量 | 秒 | 退出码 | 原始输出 |','|---|---|---:|---:|---|']
    for path in sorted(OUT.glob('*.json')):
        r=json.loads(path.read_text(encoding='utf8'))
        if not isinstance(r,dict) or 'run' not in r:continue
        label=path.stem
        lines.append(f"| [{label}]({path.name}) | {r['status']}: {r['run']} / {r['passed']}PASS / {len(r['skips'])}SKIP / {len(r['failures'])}FAIL / {len(r['errors'])}ERROR | {r['seconds']:.3f} | {r['exitCode']} | [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |")
    lines+=['','最终选择及身份匹配见[selected-runs.json](selected-runs.json)；中间版本PASS不等于最终版本覆盖。','']
    write('test-index.md','\n'.join(lines))
    history={}
    docs=['README.md',*[f'docs/project_memory/{name}' for name in (
        '01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','CHANGELOG.md','工程总档案.md')]]
    for name in docs:
        path=ROOT/name;original=path.read_bytes()
        assert hashlib.sha256(original).hexdigest()==baseline['priorPending'][name],name
        link=('docs/project_memory/' if name=='README.md' else '')+'pre_p19_supplement_evidence/final-report.md'
        heading=f'''<!-- PRE_P19_A1_A2_A3_20260920 -->
## 当前批次：P19前A1/A2/A3补修已实现，等待独立复核

用户授权在R1—R4成果上补齐三项漏口；本批次IMPLEMENTED_NOT_ACCEPTED / EVIDENCE_CONFLICT=PRESENT，PLANNING_CONFLICT=NONE。未登记验收、未执行Git写操作、未进入P19；P00—P18历史ACCEPTED及D-073不变，P19—P23 NOT_STARTED。

已分离表达专属拒绝与合法内部Evolution，按实际绑定能力处理未获结果支持的混合提案，并恢复已满足需要经原动力学再次出现的认知路径。保留当前权限、来源、Context、生命周期、预算、PAUSE/STOP和无重复效果/计费边界；原失败与历史F1/H1/F2 UNKNOWN不变。

本轮施工方原样复跑独立探针8PASS，交叉{results['cross']['run']}PASS，兼容{results['compatibility']['run']}PASS；最终完整回归{full['run']}项={full['passed']}PASS/{len(full['skips'])}既有Win1314 SKIP、0FAIL/ERROR，{full['seconds']:.3f}秒，exit0。集合交叠不相加；旧1551全量属于此前版本。详见[补修报告、限制与复核入口]({link})。

下文保留为此前发生时的记录，不代替本批次状态。

'''.encode('utf8')
        path.write_bytes(heading+original)
        history[name]={'offset':len(heading),'originalHash':hashlib.sha256(original).hexdigest()}
    write('document-history.json',json.dumps(history,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'continuation.md').open('a',encoding='utf8') as f:
        f.write('\n## 最终测试与档案已完成\n\n所有选定组已完整结束，前后源码一致；报告/矩阵/索引与七份直接档案已同步。只剩final审计与清单核对，不重复测试，不修改源码。当前仍待独立复核，不验收、不Git写入、不进入P19。\n')
    print(json.dumps({'sourceCount':len(source),'sourceHash':digest,'finalTests':len(ids),'addedTests':len(added),'documents':docs},ensure_ascii=False))

if __name__=='__main__':main()
