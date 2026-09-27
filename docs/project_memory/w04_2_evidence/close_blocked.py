"""Document observed validation blocker without claiming missing full regression."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
assert not (HERE/'final-report.md').exists()
fp=json.loads((HERE/'frozen-source.json').read_text(encoding='utf-8'))['fingerprint']
runs=[]
for path in HERE.glob('w04-2-*.json'):
    r=json.loads(path.read_text(encoding='utf-8'))
    if 'command' not in r:continue
    stderr=path.with_suffix('.stderr.log').read_text(encoding='utf-8')
    ran=re.search(r'^Ran (\d+) tests? in ([\d.]+)s$',stderr,re.M)
    end=re.findall(r'^(?:OK(?: \(.*\))?|FAILED \(.*\))$',stderr,re.M)
    assert r['status']=='COMPLETED' and ran and end,path.name
    counts={k:int(re.search(k+r'=(\d+)',end[-1]).group(1)) if re.search(k+r'=(\d+)',end[-1]) else 0
            for k in ('failures','errors','skipped')}
    r.update(total=int(ran.group(1)),counts=counts,passed=int(ran.group(1))-sum(counts.values()),
        unittest_seconds=float(ran.group(2)),summary=end[-1],result=path.name,
        stdout=path.with_suffix('.stdout.log').name,stderr=path.with_suffix('.stderr.log').name)
    runs.append(r)
runs.sort(key=lambda r:r['started_at'])
selected=[next(r for r in runs if r['label']==label) for label in ('w04-2-special-final-01','w04-2-compat-final-01')]
assert all(r['source_before']==r['source_after']==fp for r in selected)
spec,compat=selected
summary=dict(source_fingerprint=fp,source_count=314,all_runs=runs,selected=selected,
    full_regression={'status':'NOT_RUN','gate':'BLOCKED','reason':'Public compatibility failures reproduced on original HEAD and current; pending targeted investigation scope'},
    original_test_identity_count=1802,new_test_identity_count=42,original_tests='113 original test files byte unchanged; no claim all executed on this version',
    evidence_conflict='PRESENT',planning_conflict='PRESENT',all_selected_passed=False,
    source='施工方本轮实跑；不是规划窗口独立实跑或远端CI；集合重叠不相加')
(HERE/'final-test-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# W04-2 真实测试索引','',summary['source'],'',
       '固定源码：`'+fp+'`。**兼容未通过，最终全量未启动**，不能写成全批验证通过。', '',
       '| 标签 | PASS / FAIL / ERROR / SKIP | runner秒 / unittest秒 | exit | 原始输出 |','|---|---|---|---|---|']
for r in runs:
    c=r['counts']
    lines.append(f"| {r['label']} | {r['passed']} / {c['failures']} / {c['errors']} / {c['skipped']} | {r['duration_seconds']} / {r['unittest_seconds']} | {r['exit_code']} | [命令与hash]({r['result']}) · [stdout]({r['stdout']}) · [stderr]({r['stderr']}) |")
lines+=['','专项71项=本批新增42项+W04-1原29项。原1802项身份和113份旧测试字节保留，未宣称本轮完整运行。',
        '有界原HEAD/当前对照各4项、各0 PASS/1 FAIL/3 ERROR，独立报告不与专项或兼容相加，见[对照记录](recall-paired-diagnostic-01.json)。',
        '三个隔离链路样例exit 0、80.321秒，不计正式测试数量，见[样例执行记录](sample-run-01.json)及[链路引用](chain-examples.json)。',
        '本轮没有执行最终全量；既有1801 PASS/1 Win1314 SKIP仅为历史基线引用，不能充当本轮结果。',
        '原失败与辅助问题见[failure-history.md](failure-history.md)，当前阻断见[conflict-report.md](conflict-report.md)。','']
(HERE/'test-index.md').write_text('\n'.join(lines),encoding='utf-8')
text=f'''# W04-2 实现交付与公共验证阻断报告

**实现状态：IMPLEMENTED_NOT_ACCEPTED；公共验证及最终全量：BLOCKED。** W04整体IN_PROGRESS，W04-3未开工。D-088仅为开工决定。本批未完成全部验证门，不能验收。PLANNING_CONFLICT/PRESENT限本批验证依赖的处理范围待决定，EVIDENCE_CONFLICT=PRESENT；不是倒改任何历史验收。

## 实际能力

模拟界面已完成受控观察、定位、点击、输入、滚动、保存、发送、再观察；绑定主体、环境、设备/应用/账号/会话、当前页面/焦点、连接代次、权限与时限。CLICKED不会当成SAVED/SENT；不确定结果留UNKNOWN，先查询原事实。

模拟身体传感进入原Perception；动作经原ActionPlanning、Capability/Permission/Resource/Recoverability/Reality到隔离Body Adapter，核验回执进入原E5-A/Outbox。正常原始消息C1和后续Thinking/Action/Evolution吸收有正式测试，Adapter不直接写SubjectState。无身体、换身体、撤权、断线、过期、取消和真实跨进程恢复分别验证。

局部历史模拟查询使用原HistoryScope，经原结果源、Router/Composer提供带根、版本、范围和当前权限的候选；同源重读不增加独立依据，撤销/过期阻止新消费而保留旧回执。硬件TEST_SIMULATED、Somatic、Dream严格分源；未施工Dream。

实现及公共影响：[implementation-notes.md](implementation-notes.md)；规划对应：[matrix.md](matrix.md)、[coverage-map.md](coverage-map.md)；可追溯三条隔离样例：[chain-examples.json](chain-examples.json)。样例是工程链证明，不是任意真实设备、语言质量或W04-4跨入口总联验。

## 实跑与未完成项

固定314项源码/测试/资源：`{fp}`。原1802项测试身份、原113份测试文件未改，新增42项。

| 集合 | 真实结果 | runner秒 | exit |
|---|---|---|---|
| 本批+W04-1专项 | 71 PASS，0 FAIL/ERROR/SKIP | {spec['duration_seconds']} | 0 |
| P08/P16/P17/P18/W02/W03兼容 | 414项：407 PASS、1 FAIL、6 ERROR、0 SKIP | {compat['duration_seconds']} | 1 |
| 原HEAD定向诊断（一次） | 4项：0 PASS、1 FAIL、3 ERROR | 69.321 | 1 |
| 当前版定向诊断（一次） | 4项：0 PASS、1 FAIL、3 ERROR | 47.433 | 1 |
| 最终完整回归 | 未启动；前置公共兼容阻断，待用户决定调查范围 | — | 无 |

全部是施工方本轮实跑或明确未运行；集合有交集，不相加。规划窗口尚未对本批独立复核，无远端CI结果。历史Win1314 SKIP保留，不算PASS；旧全量仅作历史引用。真实命令、源码前后身份、stdout/stderr和全部中间结果见[test-index.md](test-index.md)。

## 当前阻断与下一步决定

五项W02用例触及未改的1000毫秒；P18一项BUSY诊断数量不符、一项STOP控制事务遇忙。对照原HEAD也复现同类异常，不能认定本批引入，也不能据此认定本批完全无影响或唯一归因为机器性能。相关子进程最终退出0、无强制清理。完整事实、缺失证据、公共文件候选与选项见[STOP CURRENT ITEM说明](conflict-report.md)。

建议用户另行确认对这些W02/P18异常作定向根因调查；先保留时限和断言、测量后再提最小修补范围。本轮不擅自改原回忆或控制锁策略，也不启动全量碰运气取得绿灯。当前验证阻断必须保留，历史F1/H1/F2仍UNKNOWN。

## 范围与保护

本批7份实现/测试文件：3份旧公共运行文件（ActionSpecification、ExecutionService、ExecutionContextSource）定点接线，新增设备契约/服务、隔离Fixture及正式测试。没有第二主体或请求结果账本。旧数据和非设备路径保持原契约，专项通过不能替代未通过的公共兼容。

六份共享档案仅新增本轮段落，保留D-085及全部旧历史。70份保留材料（原57加13份不重叠的D-085材料）不计本批成果。63项保护、正式7文件、现行3份规划及保留材料终局核对见[final.audit.json](final.audit.json)；精确成果/hash见[final.pending-files.md](final.pending-files.md)，进程收尾见[process-cleanup.json](process-cleanup.json)。Git行尾转换提示原样记录，不改旧证据。

## 后置及限制

模拟编辑控件、位置感知/动作和有限历史页不代表通用视觉/真实语言能力。W04-3自主发现、W04-4跨入口总联验、W05自然记忆/再理解/梦、P19完整页面、P20/P21生产恢复、P22真实设备仍未完成。本批不接真实桌面/账号/硬件/服务。W02原1000毫秒不变，当前已再次实测超时，不能保证原负载或更大负载在任何环境稳定通过。

未验收、暂存、提交、push或进入下一批。实现交回独立复核，公共验证待决定；不能把本报告描述成W04-2全量通过交付。
'''
(HERE/'final-report.md').write_text(text,encoding='utf-8')
matrix=HERE/'matrix.md';text=matrix.read_text(encoding='utf-8')
text=text.replace('开工阶段均 IN_PROGRESS，不是验收。','本批功能实现 IMPLEMENTED_NOT_ACCEPTED；公共验证 BLOCKED，不是验收。正式用例定位见[coverage-map.md](coverage-map.md)，真实结果见[test-index.md](test-index.md)。')
text=text.replace('| IN_PROGRESS |','| IMPLEMENTED_NOT_ACCEPTED |')
text=text.replace('最终同版全量 | IMPLEMENTED_NOT_ACCEPTED |','最终同版全量 | BLOCKED：兼容407 PASS/1 FAIL/6 ERROR；全量未启动，见conflict-report.md |')
matrix.write_text(text,encoding='utf-8')
entry=HERE/'review-entry.md';text=entry.read_text(encoding='utf-8').replace('实际最终结果与交付清单在收尾时另行生成，未完成运行不可算通过。','当前公共兼容失败、全量未启动；先看[阻断说明](conflict-report.md)、[交付报告](final-report.md)及[真实测试索引](test-index.md)。不得把本批当作全部验证通过。')
entry.write_text(text,encoding='utf-8')
failure=HERE/'failure-history.md';old=failure.read_text(encoding='utf-8')
failure.write_text(old+'\n## 最终兼容新失败（不覆盖上表）\n\n414项为407 PASS/1 FAIL/6 ERROR，原结果及基线对照见[阻断说明](conflict-report.md)。两版同类失败不证明唯一根因，本轮未修原W02/P18逻辑。另一次只读定位误用不存在的p16_fixture.py/w02_fixture.py文件名，rg返回缺文件；改读实际p16_provider_fixture.py，未影响源码或测试结果。\n\nfinish.py和summarize.py是此前准备的全通过收尾分支，本轮未运行；实际阻断交付由close_blocked.py根据完成记录生成，不能将未运行脚本视为证据。\n',encoding='utf-8')
common=('W04-2功能实现为IMPLEMENTED_NOT_ACCEPTED，公共兼容收口/最终全量BLOCKED，W04整体IN_PROGRESS，W04-3未开工。'
        'D-088仅开工。专项71 PASS；兼容414项为407 PASS/1 FAIL/6 ERROR；原HEAD与当前版各一次4项对照均1 FAIL/3 ERROR。'
        '最终全量未启动，不借用旧全量。原1000毫秒/旧断言未改，历史F1/H1/F2仍UNKNOWN，未取得远端CI结果。'
        'PLANNING_CONFLICT=PRESENT（验证依赖/处理范围待决定），EVIDENCE_CONFLICT=PRESENT；不倒改历史验收。')
for name in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md'):
    p=ROOT/'docs/project_memory'/name;old=p.read_text(encoding='utf-8')
    assert '<!-- W04_2_BLOCKED_DELIVERY -->' not in old
    prefix=('<!-- W04_2_BLOCKED_DELIVERY -->\n## W04-2 模拟闭环实现与公共验证阻断\n\n'+common+'\n\n'
        f'314项源码指纹 `{fp}`。新增42项，原1802身份及原113份测试文件字节保留。新设备/身体/历史查询复用原Action/P17/E5-A、Perception及Router/Composer，未造第二权威。'
        '三项公共接线文件之外未改运行实现；出现原W02/P18异常后做一次有界对照，不擅自改预算/锁策略。只暂停受影响验证项；请求用户决定后续定向调查范围。\n\n'
        '[交付报告](w04_2_evidence/final-report.md) · [逐项矩阵](w04_2_evidence/matrix.md) · [测试原件](w04_2_evidence/test-index.md) · '
        '[阻断与选项](w04_2_evidence/conflict-report.md) · [精确审计](w04_2_evidence/final.audit.json)。\n\n'
        '本轮未验收、暂存、提交、push。70份保留材料和保护边界单列核对，历史失败/辅助错误/中断/SKIP不改写。以下均为发生时历史记录。\n\n')
    p.write_text(prefix+old,encoding='utf-8')
continuation=HERE/'continuation.md';old=continuation.read_text(encoding='utf-8')
continuation.write_text('## 当前安全停点\n\n'+common+'\n\n原兼容会话1545、诊断98533和样例12008均已完成，不得盲恢复或重复启动。源码未改。下一步为用户决定W02/P18定向调查范围；不启动W04-3。终局审计与进程记录见final.audit.json/process-cleanup.json。以下为旧进度，不代表进程仍运行。\n\n'+old,encoding='utf-8')
print(json.dumps({'status':'IMPLEMENTED_NOT_ACCEPTED','validation':'BLOCKED','source':fp},ensure_ascii=False))
