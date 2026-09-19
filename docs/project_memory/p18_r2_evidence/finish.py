"""Archive only completed observations; never replace older repair evidence."""
from pathlib import Path
import hashlib, json, runpy

OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=DOC.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,data):
    with p.open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
STATE='P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。R1既有独立定点结论保留；R2返修待独立复核；F1/H1分别为UNKNOWN；本次全量新增失败F2，原因UNKNOWN，等待确认，不自行续修。D-072追加事实，D-073未创建/未使用；不验收、不Git写入、不P19。'
def main():
    assert not (OUT/'final-report.md').exists()
    selected=read(OUT/'selected-runs.json');runs={k:read(OUT/(v+'.json')) for k,v in selected.items()}
    frozen=read(OUT/'frozen-source.json');full=runs['full']
    current=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
    assert current==frozen['sourceTest']
    assert all(r['status']=='FINISHED' and r['sourceBefore']==r['sourceAfter']==current for r in runs.values())
    interruption=read(OUT/'interruption-full-final-01.json')
    resume_check=read(OUT/'resume-identity-check.json')
    assert selected['full']==interruption['replacementRun']
    for name,row in interruption['originalFilesUnmodified'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==row['sha256']
    for kind,row in resume_check['completedGroups'].items():
        assert selected[kind]==row['label']
        assert hashlib.sha256((OUT/(row['label']+'.json')).read_bytes()).hexdigest()==row['evidenceSha256']
    history=[]
    for path in sorted(OUT.glob('*.json')):
        r=read(path)
        if 'sourceBefore' in r and 'status' in r:
            after=r.get('sourceAfter')
            history.append(dict(label=path.stem,**{k:r.get(k) for k in ('status','command','run','passed','skips','failures','errors','seconds','exitCode')},
                sourceAfterAvailable=after is not None,
                unchangedDuringRun=None if after is None else r['sourceBefore']==after,
                matchesFinal=None if after is None else after==current,
                laterChangedFiles=None if after is None else sorted(p for p in set(current)|set(after) if current.get(p)!=after.get(p))))
    save(OUT/'test-source-coverage.json',history)
    table='| 组别 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 | 原始证据 |\n|---|---|---|---|---|---|---|\n'
    for kind,r in runs.items():
        name=selected[kind]
        table+=f"| {kind} | {r['run']} | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']:.3f} | [记录]({name}.json) · [stdout]({name}.stdout.log) · [stderr]({name}.stderr.log) |\n"
    text='# P18 R2 本轮测试历史\n\n所有标签原样保留；表内相交集合不得相加为正式测试总数。实际命令和源码前后 hash 在各 JSON。\n\n'
    text+='| 标签 | 原记录状态 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 | 退出码 | 对应最终源码 |\n|---|---|---|---|---|---|---|---|---|\n'
    for r in history:
        finished=r['status']=='FINISHED'
        value=lambda key: r[key] if r.get(key) is not None else 'UNKNOWN'
        skipped=len(r.get('skips') or []) if finished else 'UNKNOWN'
        failed=f"{len(r.get('failures') or [])}/{len(r.get('errors') or [])}" if finished else 'UNKNOWN'
        identity=r['matchesFinal'] if r['sourceAfterAvailable'] else 'UNKNOWN（缺运行后清单）'
        text+=f"| [{r['label']}]({r['label']}.json) | {r['status']} | {value('run')} | {value('passed')} | {skipped} | {failed} | {value('seconds')} | {value('exitCode')} | {identity} |\n"
    text+='\nfull-final-01 保留原 STARTED 记录；现场确认未完成且无存活进程，归类 INCOMPLETE_INTERRUPTED。退出码/原因及最终计数 UNKNOWN，不计为 PASS 或 Engine 行为 FAIL。[中断说明与原件hash](interruption-full-final-01.json)。\n'
    (OUT/'test-history.md').write_text(text+'\n工具/新测试辅助错误见 [记录](auxiliary-errors.log)。修前合成Fixture对象的断言输出保留为反例证据；不是运行时诊断输出。\n',encoding='utf8')
    investigation=dict(F1=dict(rootCause='UNKNOWN',resolved=False,history='../p18_repair_evidence/full-timeout-investigation.json',
        historicalResult=dict(run=1444,passed=1442,skips=1,failures=1,errors=0),
        evidenceLimits=['Original failure-time ThinkSession/provider phase/exception chain missing; temporary root already cleaned.',
                        'Same token_used=640 and UNKNOWN are not causal proof of R2.'],
        currentPredeterminedCases=['original twelve fixed interleavings','formal after-Evolution pause/clock sequence',
                                   'original process case in P18 and one full regression'],
        diagnostics='Original assertions/timeouts retained; phase/context/action/capability/result hash/receipt identity captured before failure cleanup; TEST safe engine frames on exceptions.'),
        H1=dict(rootCause='UNKNOWN',resolved=False,history='../p18_repair_evidence/h1-investigation.json',
            limits=['Missing pre-STOP activity/watermark/precise interleaving.',
                    'Recorded alive host and later STOP exit0 differ from R1 no-STOP exit2.',
                    'Original source inventory exists; inspected materials lack full byte-exact changed source snapshots.']),
        currentProcessCases={})
    for kind in ('formal','p18','full'):
        rows=[]
        for line in (OUT/(selected[kind]+'.stdout.log')).read_text(encoding='utf8').splitlines():
            try:r=json.loads(line)
            except ValueError:continue
            if 'childrenReaped' in r or r.get('stage')=='bounded-f1-before-stop':rows.append(r)
        investigation['currentProcessCases'][kind]=rows
    save(OUT/'f1-h1-investigation.json',investigation)
    oldmatrix=read(DOC/'p18_repair_evidence/matrix-test-map.json')
    added=set(full['testIdentities'])-set(read(OUT/'before.json')['testIdentities'])
    full_failed={t for t,_ in full['failures']+full['errors']}
    for key,row in oldmatrix.items():
        row['status']='IMPLEMENTED_NOT_ACCEPTED'
        row['fullFailureHistory']='F1/H1 UNKNOWN retained; current PASS is not retrospective causal proof.'
        additions=set()
        if key=='P18-09':additions=added
        selectors={'P18-03':('clock','long_pause'),'P18-05':('reassess','second_cycle'),
            'P18-06':('budget','reservation','repeated_control','availability'),
            'P18-07':('pause','stop','cancel','revoke'),
            'P18-08':('reopen','child','crash','history','legacy'),
            'P18-11':('diagnostic','bound','context'), 'P18-12':('child','f1_')}
        additions|={t for t in added if any(w in t for w in selectors.get(key,()))}
        row['testIdentities']=sorted(set(row['testIdentities'])|additions)
        row['currentFullFailures']=sorted(set(row['testIdentities'])&full_failed)
        row['currentFullResult']='FAIL' if row['currentFullFailures'] else 'PASS'
        row['stageBlockingEvidence']='F2 full-resume-01 new failure; F1/H1 UNKNOWN; independent review required.'
    assert {t for row in oldmatrix.values() for t in row['testIdentities']}==set(runs['p18']['testIdentities'])
    save(OUT/'matrix-test-map.json',oldmatrix)
    summary=f"本轮最终专项 {runs['p18']['run']} PASS；新增正式 R2 {runs['formal']['run']} PASS；原12/4探针各自通过；兼容 {runs['compatibility']['passed']}/{runs['compatibility']['run']} PASS。最终全量 {full['run']}项：{full['passed']} PASS、{len(full['skips'])}既有1314 SKIP、{len(full['failures'])} FAIL/{len(full['errors'])} ERROR，{full['seconds']:.3f}秒，exit={full['exitCode']}。原1444身份保留，新增{len(added)}项；各组交叉包含，不能相加。"
    report=f'''# P18 R2 验证续接交付；全量新增 F2 失败，等待确认

{STATE}

本次缺失全量已补跑并完成，但未通过：{full['passed']} PASS、{len(full['skips'])} SKIP、{len(full['failures'])} FAIL、{len(full['errors'])} ERROR。新失败 F2 原始现场及清理记录见 [full-resume-01-failure.json](full-resume-01-failure.json)。没有再次运行测试、修改实现、放宽断言或超时。

## 实际实现

R2：原 Thinking 的通用异常路径没有区分调用前控制延后和调用已进入后的失败，Runtime 对未完成会话一律 UNKNOWN。现将内部执行阶段绑定到原 ThinkSession，保存 PREPARED 后方可检查控制/资源，调用前先保存 ENTERED，完整验证结果后 RETURNED。暂停留在可核验 PREPARED 并追加历史，恢复经原 Native Wake/Thinking/Action/Evolution 继续同一任务和会话，重查当前控制、权限、材料、资源、Provider 可用性及生命周期。没有新增请求账本/Authority。

当前输入失效时不修改旧 Perception/请求：明确未执行的旧会话留 ABANDONED 历史，经原 Scheduler NOT_DELIVERED 关闭；新评估由旧 task/think/阶段记录确定性派生并可追溯。原 Thinking 预留结算0，已经发生的 Wake 费用保留。普通取消/STOP、真正 UNKNOWN 不会据此生成新任务。预算 Port 内暂停的同类 R2 反例也已保存并最小修复。

R1 两个运行文件及原20项竞争测试 hash 未变。既有完整专项通过；本次全量中的资源等待控制竞争用例发生新失败 F2，不能宣称当前全量的 R1 组合全部通过，也不能据该超时认定原 R1 锁导致宿主退出的问题复发。正常入口持续运行要求不变，不安装服务、不启动自动重启、不访问生产系统。

实现位置与原理见 [实现记录](implementation-notes.md)；代码改动限定原 Thinking 类型/服务/仓储、RuntimeCognition/Native 接线、TEST诊断及新增正式回归。完整逐文件清单见 [final.pending-files.md](final.pending-files.md)。

## 修前、修复与实测

原样修前12项=11 PASS/1 FAIL，26.038秒；确认4项=1 PASS/3 FAIL，6.385秒。正式初5项=2 PASS/3 FAIL，7.379秒。同类预算内控制场景另1 FAIL，1.598秒。原独立脚本/依赖/输出已按 [before.json](before.json) 及 [补充来源清单](additional-archive.json) 逐件复制并核对原件hash，未改规划侧原件。

新增费用/配置假设2 FAIL以及持有锁文件读取1 ERROR属于本轮测试辅助问题，完整保存，见 [辅助记录](auxiliary-errors.log)。所有旧失败、工具错误、1314 SKIP、P09 segment10 UNKNOWN、P18 H1/F1原记录不动。

{table}

{summary}

本表为同一 P18 R2 施工过程的实际结果，非独立验收或远端CI。本次软件退出后的续接只新运行 `{selected['full']}`；前五组 formal-final-03、resume-final-02、confirmation-final-02、p18-final-02、compatibility-final-01 已完成，本次核对其运行前后源码与当前265文件一致后保留引用，未重复执行。见 [续接身份检查](resume-identity-check.json)。独立规划侧上轮 R1 5项/21项通过仅引用报告。

旧 `full-final-01` 开始于本地 2026-09-13 01:33:17，仅留下 STARTED。末尾停在 P09 三十逻辑日跨进程测试，无完成汇总；本次核对日志未增长、匹配的 Python 测试进程为零。JSON/stdout/stderr 原样及 SHA256 保留于 [中断说明](interruption-full-final-01.json)。实际退出码、原因、最终数量均 UNKNOWN，不算 PASS，也不据软件退出认定 Engine 行为 FAIL；没有使用旧 session75412 或重新运行 validate.py。最终索引改为实际完成的 `{selected['full']}`，旧标签作为未完成历史保留。

最后一次源码调整仅追加 TEST 诊断的结果hash/receipt_id；前五组和本次补跑均覆盖该固定版本。更早兼容/测试标签与最终源码差异在 [覆盖清单](test-source-coverage.json)，不冒称重新执行或全部历史结果对应最新文件。

## 本次 F2 与历史 F1 / H1 分别说明

F2：`test_resource_wait_process_control_competition` 在原15秒控制器阈值内未观察到 SubjectState revision==2。清理前宿主存活、checkpoint未忙、token_used=320；ThinkSession 为 COMPLETED/RETURNED，Context当前有效；能力记录 SUCCEEDED 且有回执，Fake效果/credits各1，状态提交ID仍为空。脱敏异常栈到达原 ActionEvolution / SubjectStateService / JsonSubjectStateRepository 的 `os.replace`。这足以定位实际观察的失败阶段，但没有原异常类型/系统错误码，具体根因仍UNKNOWN，不能猜为机器慢、权限或并发问题。宿主接受清理STOP并退出0，无强制清理；当前查询无匹配测试进程。完整原始输出不变，见 [新增失败证据](full-resume-01-failure.json)。本次只归档并报告，不追加试验或修实现，等待用户确认。

F1仍UNKNOWN，不能充分关闭：原全量1444=1442PASS/1SKIP/1FAIL。原失败缺 ThinkSession/阶段/异常链，临时根已按旧测试清理。本轮固定交错、原进程用例及最终全量结果不能倒推那次失败是R2。当前故障时将先记录会话阶段、身份、Context、Action/Capability/回执、静态错误/引擎栈、可信时间/水位/资源和进程退出信息，再STOP/清理。

H1仍UNKNOWN：旧58项57PASS/1FAIL，资源等待超时，token_used=0，无未确认任务；宿主活着，后续STOP退出0。缺关键清理前水位和精确旧交错，不能归因于R1、R2、F1、额度中断或机器性能。[独立调查与本次诊断](f1-h1-investigation.json) 保持两项未关闭。

## 身份、保护与限制

最终源码/测试/资源 {len(current)} 文件，指纹 `{frozen['sourceHash']}`；所有最终组选定 sourceBefore/sourceAfter 与该清单一致。原1444测试身份及原断言保留，新增{len(added)}另计。既有Windows符号链接权限1314跳过仍不算PASS。

63保护项、6 Schema/冻结契约、3规划源、正式7文件、版本0.1.0/pyproject和32排除项逐文件核验见 [审计](final.audit.json)。正式树预期与实测核对保留 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。本轮无Git写操作，main/HEAD/local origin保持P17基线；不联网查询远端、不声明CI PASS。

缺乏可靠阶段证据的旧 FAILED/不完整会话继续 UNKNOWN；不据错误文字迁移、不虚构未执行。ENTERED之后的无可靠结果继续待核实。生产部署、联系时段/频率/费用、真实Adapter与生产恢复仍NOT_READY。当前修复只证明本地TEST记录及既有回执能力，不承诺任意生产 exactly-once。

格式检查保留已登记的8处旧P16格式告警、3处P17原始失败日志行尾空格、1处P18旧中断日志告警；不为清告警改写历史。新增可编辑文件与新增原始证据告警分别列入审计。Git的LF/CRLF提示单列，不当作测试失败；敏感扫描与实际材料隔离回归分开记录。

## 复核命令

在 Engine 根设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`。使用未占用标签，不能覆盖原日志：

```powershell
python docs/project_memory/p18_r2_evidence/run.py review-resume-01 --review-class test_independent_resume.IndependentResumeTests
python docs/project_memory/p18_r2_evidence/run.py review-confirm-01 --review-class test_pause_resume_confirmation.PauseResumeConfirmation
python docs/project_memory/p18_r2_evidence/run.py review-formal-01 test_p18_runtime_resume
python docs/project_memory/p18_r2_evidence/run.py review-p18-01 test_p18_
```

正常完整运行入口和控制仍见 [P18测试/运行入口](../86_P18_测试索引与验收入口.md)。本轮测试控制器负责STOP及回收，进程清理记录在各stdout与 [终局进程检查](process-check.json)。施工到此停止，等待独立复核，不自行关闭 EVIDENCE_CONFLICT。
'''
    (OUT/'final-report.md').write_text(report,encoding='utf8')
    top=f'{STATE}\n\n{summary}\n\n本次验证续接核对并引用前五组完成结果，仅补跑 {selected["full"]}。旧 full-final-01 未完成，退出码/原因UNKNOWN，原记录保留；不据此记为Engine行为FAIL。\n\nR2通过原ThinkSession内的持久阶段区别未调用控制延后与真正UNKNOWN；同一会话恢复重验条件，过期材料有明确前驱的新评估。R1保留，F1/H1仍缺根因证据；后续PASS不关闭历史失败。正常start默认持续，不启用生产政策。\n\n'
    config=runpy.run_path(str(DOC/'p18_evidence/finalize.py'))
    for path in [ROOT/'README.md']+[DOC/p for p in config['TOP']+config['STAGE_FILES']]:
        old=path.read_text(encoding='utf8');assert '<!-- P18_R2_CURRENT_START -->' not in old
        link='docs/project_memory/p18_r2_evidence/final-report.md' if path==ROOT/'README.md' else 'p18_r2_evidence/final-report.md'
        block='<!-- P18_R2_CURRENT_START -->\n'+top+f'[本轮完整报告与复核入口]({link})。下方R1/初版和旧阶段的状态、PASS/FAIL/ERROR/SKIP均为当时历史，不倒改。\n<!-- P18_R2_CURRENT_END -->\n\n'
        if path.name.startswith('83_'):
            block+='本轮 Stage Brief 追加：STAGE=P18 R2返修；SOURCE OF TRUTH=用户2026-09-13续修授权及归档独立报告；ORIGINAL REQUIREMENTS/KEEP=默认持续运行、原单一权威及R1修复不变；AMENDMENT=可靠调用前阶段恢复与F1/H1分开调查；NOT READY=旧无阶段依据记录自动恢复、生产部署/联系策略；PLANNING CONFLICT=NONE。\n\nFILES ALLOWED：domain/thinking.py、services/thinking_service.py、services/runtime_cognition.py、services/wake_perception_thinking_action_service.py、storage/json_thinking_repository.py、testing/p18_runtime_fixture.py、tests/test_p18_runtime_process.py、tests/test_p18_runtime_resume.py及直接相关档案/新p18_r2_evidence。FILES FORBIDDEN：63保护项/冻结契约/正式数据/规划/版本/32排除项/Assistant。TESTS REQUIRED：原12/4类、22正式回归、完整P18、兼容、一次最终全量，实际结果见本轮报告。\n\n'
        if path.name.startswith('85_'):
            block+='现行恢复补充：PREPARED是原ThinkSession绑定的调用前事实，控制延后不再改为FAILED；ENTERED必须先于调用落盘，之后无结果保守UNKNOWN；RETURNED保留原Action/Evolution事实恢复。ABANDONED仅关闭明确未执行且需材料重评的输入，保留旧快照/历史和原Wake费用，通过确定性前驱关系形成新评估。缺失旧阶段字段不推断未执行，不改旧请求/结果。\n\n'
        if path.name.startswith('84_'):
            block+='| 项目 | 现行状态 | 身份覆盖 | 本次全量对应条目 |\n|---|---|---|---|\n'
            for key,row in oldmatrix.items():block+=f'| {key} | IMPLEMENTED_NOT_ACCEPTED | {len(row["testIdentities"])}个交叉身份 | {row["currentFullResult"]}；阶段仍受F2及F1/H1证据限制 |\n'
            block+='\n[逐项身份映射](p18_r2_evidence/matrix-test-map.json)。\n\n'
        path.write_text(block+old,encoding='utf8')
    decision=DOC/'04_决策记录.md';s=decision.read_text(encoding='utf8')
    start=s.index('## D-072');end=s.find('\n## ',start+1)
    if end<0:end=len(s)
    note='\n\n### 2026-09-13 P18 R2续修及软件退出后验证接续事实（非验收）\n\n用户授权R2与F1调查、保留H1限制；本轮结果与责任见 [R2返修报告](p18_r2_evidence/final-report.md)。前五组完成结果核对身份后引用，仅补跑缺失全量 full-resume-01：1466项、1464 PASS、1既有1314 SKIP、1 FAIL、0 ERROR，1376.330秒，exit1。新失败F2根因UNKNOWN，保留现场，未重跑或续修。旧full-final-01未完成，退出码和原因UNKNOWN，不计为PASS或Engine行为FAIL。R1既有独立定点结论保留；R2实现待独立复核；F1/H1分别UNKNOWN，EVIDENCE_CONFLICT=PRESENT。D-073未创建/使用，无Git写操作，不进入P19。\n'
    decision.write_text(s[:end]+note+s[end:],encoding='utf8')
    (OUT/'continuation.md').write_text('# P18 R2 当前接续状态\n\n'+STATE+'\n\n'+summary+'\n\n前五组已核对身份并引用，续接仅补跑 '+selected['full']+'。旧 full-final-01 未完成，退出码/原因UNKNOWN，原件保留。所有选定测试已完成，未留待恢复的测试session。源码固定，正在进行终局档案/保护/Git/进程审计；不重跑全量、不改实现。F1/H1仍UNKNOWN。完成审计后交回独立复核。\n',encoding='utf8')
    print(summary)
if __name__=='__main__':main()
