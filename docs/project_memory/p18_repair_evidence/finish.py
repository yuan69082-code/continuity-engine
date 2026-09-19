"""Compile P18 repair documentation only after the selected runs finish."""
from pathlib import Path
import hashlib,json,runpy,sys

OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=DOC.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source():return {p.relative_to(ROOT).as_posix():sha(p) for d in ('src','tests') for p in sorted((ROOT/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def main():
    assert not (OUT/'final-report.md').exists(),'never replace a delivered report'
    selection=read(OUT/'selected-runs.json');current=source();b=read(OUT/'before.json')
    unresolved_full='--record-unresolved-full' in sys.argv
    runs={kind:read(OUT/(label+'.json')) for kind,label in selection.items()}
    for kind,r in runs.items():
        assert r['status']=='FINISHED',kind
        assert r['exitCode']==0 or (kind=='full' and unresolved_full),kind
        assert r['sourceBefore']==r['sourceAfter']==current,kind
    full=runs['full'];new=sorted(set(full['testIdentities'])-set(b['testIdentities']))
    assert set(b['testIdentities'])<=set(full['testIdentities'])
    if full['failures'] or full['errors']:
        assert unresolved_full and (OUT/'full-timeout-investigation.json').is_file()
    config=runpy.run_path(str(DOC/'p18_evidence/finalize.py'))
    status=('P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；'
        'P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072追加返修事实，D-073未创建/未使用。'
        'PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，R1待独立确认，H1根因UNKNOWN；本轮全量新增F1超时亦未闭合，不自行关闭。')
    evidence=['| 验证 | 标签 | RUN | PASS | SKIP | FAIL/ERROR | runner秒 |','|---|---|---|---|---|---|---|']
    for kind,r in runs.items():
        evidence.append(f"| {kind} | [{selection[kind]}]({selection[kind]}.json) | {r['run']} | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']} |")
    table='\n'.join(evidence)
    short=(f"本轮最终P18 {runs['p18']['passed']} PASS；正式返修 {runs['formal']['passed']} PASS；原独立探针 {runs['independent']['passed']} PASS；"
        f"兼容 {runs['compatibility']['passed']} PASS；最终全量 {full['run']}项={full['passed']} PASS+{len(full['skips'])}既有1314 SKIP，{len(full['failures'])} FAIL/{len(full['errors'])} ERROR，退出码{full['exitCode']}。"
        f"原1424身份保留，新增{len(new)}项；各组有包含关系，不重复相加。")
    for name in ['README.md',*['docs/project_memory/'+p for p in config['TOP']]]:
        p=ROOT/name;old=p.read_text(encoding='utf8');assert '<!-- P18_REPAIR_CURRENT_START -->' not in old
        prefix='docs/project_memory/' if name=='README.md' else ''
        block=(f'<!-- P18_REPAIR_CURRENT_START -->\n{status}\n\n{short}\n\n'
            'R1以专用checkpoint有界等待、宿主退避、控制修订绑定和退出诊断边界处理；owner单宿主锁仍明确拒绝竞争者。'
            'H1没有证据证实根因，新增清理STOP前诊断与受控正向不覆盖原超时。正常start仍默认持续运行，正式部署与联系策略未开放。\n\n'
            f'[返修完整报告]({prefix}p18_repair_evidence/final-report.md) · [审计与清单]({prefix}p18_repair_evidence/final.audit.json)。'
            '下方初版64/1424、旧兼容及此前“本轮未重跑”的段落均为当时历史，本轮已按修复后源码重新验证；所有失败和旧UNKNOWN保留。\n'
            '<!-- P18_REPAIR_CURRENT_END -->\n\n')
        p.write_text(block+old,encoding='utf8')
    matrix=read(DOC/'p18_evidence/matrix-test-map.json')
    for test in new:
        keys=['P18-08']
        if any(s in test for s in ('control','cas','permission','observation','resume')):keys.append('P18-01')
        if 'process' in test or 'long_busy_host' in test or 'start_waits' in test:keys.append('P18-02')
        if 'h1_' in test:keys.extend(['P18-03','P18-12'])
        if 'resource_wait' in test:keys.append('P18-06')
        if 'paused' in test or 'stop' in test:keys.append('P18-07')
        if 'effect' in test:keys.append('P18-09')
        if 'error' in test or 'permission' in test:keys.append('P18-11')
        for key in keys:matrix[key]['testIdentities']=sorted(set(matrix[key]['testIdentities'])|{test})
    with (OUT/'matrix-test-map.json').open('x',encoding='utf8') as f:json.dump(matrix,f,ensure_ascii=False,indent=2);f.write('\n')
    matrix_rows=['| 项目 | 现行状态 | 最终正式测试覆盖 |','|---|---|---|']
    failed_ids={t for t,_ in full['failures']+full['errors']}
    for key,row in matrix.items():
        blocked=set(row['testIdentities'])&failed_ids
        result='全量有未闭合FAIL：'+','.join(sorted(blocked)) if blocked else '所列身份在专项与全量中通过'
        matrix_rows.append(f"| {key} | IMPLEMENTED_NOT_ACCEPTED | {len(row['testIdentities'])}项（可交叉归属），{result} |")
    supplements=[
        'R1最小范围：json_runtime_repository.py、persistent_runtime_service.py；新增正式竞争测试，原process测试只追加清理前安全诊断。没有修改Scheduler/Resource/C1业务、冻结契约或正式数据。首次入队和既有任务权威继续复用。',
        '\n'.join(matrix_rows)+'\n\n[逐项测试身份](p18_repair_evidence/matrix-test-map.json)。初版矩阵与64项证据保留为历史。',
        'checkpoint事务锁与owner运行锁分开：每次事务至多等待0.25秒（线程锁与OS锁共用期限），锁竞争等待间隔25ms。仅专用RUNTIME_CHECKPOINT_BUSY触发本地退避；其他错误不会冒充锁忙。长期竞争不报告控制成功、不追加命令，不新增派发/扣费；控制调用明确拒绝，释放后相同合法身份可以重新请求。宿主按原可中断等待继续控制循环，忙区间仅输出一次静态诊断。query的checkpoint_busy为只读瞬时观察，其余状态是最后持久状态。观察核对原控制修订，不能覆盖较新的RESUME/PAUSE/STOP。退出写盘忙时只输出静态诊断并释放owner锁，保留原错误及旧owner供下次核实，不自动重启。具体首次attachment行为与验证见返修报告。',
        "复核先运行 `python docs/project_memory/p18_repair_evidence/run.py independent-check-01 --independent-probe`，再用新标签运行 `python docs/project_memory/p18_repair_evidence/run.py p18-check-01 test_p18_` 和 `python docs/project_memory/p18_repair_evidence/run.py full-check-01`。PowerShell先设置PYTHONPATH=src、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1。标签不可覆盖；无自动Git/部署/验收。"
    ]
    for name,extra in zip(config['STAGE_FILES'],supplements):
        p=DOC/name;old=p.read_text(encoding='utf8')
        p.write_text('# P18 R1返修与H1调查：当前交付\n\n'+status+'\n\n'+short+'\n\n'+extra+
            '\n\n[本轮报告](p18_repair_evidence/final-report.md) · [本轮终局审计](p18_repair_evidence/final.audit.json)。下方原版本文字和结果保留为历史。\n\n---\n\n'+old,encoding='utf8')
    for name,title in [('03_施工日志.md','P18 R1返修及H1调查完成，交回独立复核'),('04_决策记录.md','D-072续记：用户授权R1返修和H1调查，不是验收决定'),('10_档案修订记录.md','P18返修档案同步'),('CHANGELOG.md','P18本地控制竞争返修（版本不变）'),('工程总档案.md','P18返修成果与证据入口')]:
        with (DOC/name).open('a',encoding='utf8') as f:f.write('\n### '+title+'\n\n'+status+'\n\n'+short+'\n\n[本轮真实报告](p18_repair_evidence/final-report.md)。所有首次失败及H1 UNKNOWN保留，无用户验收或Git写操作。\n')
    history=[];coverage={}
    for p in sorted(OUT.glob('*.json')):
        r=read(p)
        if 'startedAt' not in r or 'status' not in r:continue
        after=r.get('sourceAfter',{})
        coverage[p.stem]=dict(status=r['status'],sourceStable=r.get('sourceBefore')==after,
            matchesFinal=after==current,
            differingFiles=sorted(n for n in set(after)|set(current) if after.get(n)!=current.get(n)))
        history.append(f"| [{p.stem}]({p.name}) | {r['status']} | {r.get('run','—')} | {r.get('passed','—')} | {len(r.get('skips',[]))} | {len(r.get('failures',[]))}/{len(r.get('errors',[]))} | {r.get('seconds','—')} |")
    with (OUT/'test-source-coverage.json').open('x',encoding='utf8') as f:json.dump(coverage,f,ensure_ascii=False,indent=2);f.write('\n')
    report=f'''# P18 R1返修 / H1历史超时调查交付

{status}

## 实际改动与责任边界

R1已实现：checkpoint事务采用线程锁与OS锁共用的0.25秒获取期限及25ms等待；仅专用RuntimeCheckpointBusy进入宿主可中断退避。owner运行锁继续立即拒绝第二宿主。忙锁不是未执行证明，原Scheduler/Wake/Thinking/Action/Evolution/E5-A身份及结果仍是原权威；没有新账本。观察等待期间核对最新控制修订，不覆盖已提交RESUME。退出诊断无法写入时不再争用同一锁覆盖原异常；保留静态诊断及原owner，后续按PRIOR_HOST_LOST核实。

运行实现仅修改[仓储](../../../../src/continuity_engine/storage/json_runtime_repository.py)及[宿主](../../../../src/continuity_engine/services/persistent_runtime_service.py)。新增[正式回归](../../../../tests/test_p18_runtime_contention.py)；原[真实进程测试](../../../../tests/test_p18_runtime_process.py)仅增加可信时间、next_check_at、活动、任务/尝试、资源、宿主生存与退出信息的清理前诊断，原断言与超时阈值未放宽。只输出结构和静态错误码，不记录私密正文、凭据或任意异常repr。

## R1证据与修复过程

- 规划原5项3PASS/2FAIL（同一个R1）的报告、探针、stdout/stderr/result和身份审计等10份原件已逐文件复制并核对SHA-256，见[来源清单](before.json)。规划侧原件不改。
- 本轮原样independent-before-01：3PASS/2FAIL，6.990秒；第一版修复后independent-after-01为5PASS/9.695秒。原五项代码未变。
- 正式first17PASS后，检查发现RUNNING/资源等待用例可能仍处于next_check_at之前，未实际争锁。增强为显式推进到期时间并断言RUNTIME_CHECKPOINT_BUSY诊断，增加长锁与效果后观察竞争，strengthened19PASS。未将较弱版本冒充最终覆盖。
- observation-before-01真实1FAIL：短等待后旧PAUSED观察覆盖已提交RESUME显示状态。同属R1“不得覆盖较新控制”；已添加控制修订绑定并保留失败。后续正式与全量验证其关闭，未替换旧输出。
- 本轮最终组和各自命令、源码前后清单见下表及同标签原始stdout/stderr；中间结果不能冒充最终身份。

{table}

原1424个身份保留，本轮新增{len(new)}项；最终全量{full['run']}项={full['passed']}PASS、{len(full['skips'])}既有Windows symlink权限1314 SKIP、{len(full['failures'])}FAIL/{len(full['errors'])}ERROR，退出码{full['exitCode']}。不能报告全量通过。独立5项单列，不增加Engine正式测试数。P18和定点及兼容均包含在全量中，不重复相加。所有最终组均实际执行；未引用旧1423PASS冒充本轮全量，没有远端CI实跑声明。[各轮源码覆盖及逐文件差异](test-source-coverage.json)明确哪些中间结果不对应最终版本。

## H1：仍为UNKNOWN

历史p18-final-04为57PASS/1FAIL，原宿主仍存活且后来STOP退出0，无强制清理；与R1无STOP退出2不同，没有证据将二者合并。旧sourceBefore/sourceAfter一致，但与原final07已有6文件身份变化。已读取的历史运行材料保留hash清单，未提供完整的当时变更文件正文快照，不能伪称已精确重建历史版本。

STOP前后可用记录：token_used=0、pending_tasks=1、unconfirmed_tasks=0、observations=2、last_time=09:01；STOP已覆盖activity/reason/next_check_at。缺少超时发生时逐任务状态、时钟读点、水位及资源预检结果，无法验证当时交错。

当前受控验证覆盖在维护观察写入时推进时钟，以及故意让测试控制器超时后在STOP之前保存完整安全诊断；这些是当前正向与证据设施验证，不是历史根因修复。未增加原超时阈值、未减少断言、未循环运行直到绿。见[结构化调查及原始来源](h1-investigation.json)。剩余风险是历史资源等待观察的间歇问题尚不能排除，独立复核必须保留UNKNOWN或显式评估残余证据限制。

## F1：本轮全量新观察，仍未闭合

原 `test_idle_and_subject_silence_do_not_end_process` 在暂停/恢复后的第二轮等待revision推进超时，full-final-01真实1FAIL。STOP前新增诊断捕获宿主alive、checkpoint_busy=false、activity=WAITING_VERIFICATION、cognition任务UNKNOWN/attempt_count=1，token_used=640，可信时间10:02:00，next_check_at=10:02:05。STOP退出0、无forcedCleanup、所有子进程已回收。

这不是R1的无STOP退出2，也不能与H1零模型消耗/无未确认任务的旧现场合并。未捕获失败时原ThinkSession/Action/Capability的异常栈，原隔离Fixture在保存诊断和STOP后按测试规程清理。只做两次固定诊断：同步双轮ADVANCED（2.404秒）；原进程流程仅包装静态异常位置采样，1PASS（11.296秒）。均未复现，不能用它们覆盖全量FAIL。见[完整调查与原始hash入口](full-timeout-investigation.json)、[同步诊断](resume-diagnostic-01.json)、[进程诊断](resume-process-diagnostic-01.json)。

没有证据支持继续修改C1、权限、回执或UNKNOWN语义来“修好”F1；本轮停止无依据的实现变动，交回独立复核继续定位这个新阻断。全量之后源码与正式测试未变，没有再次跑全量。当前不能声称P18全部验证通过。

## 运行语义、限制与复核命令

正常start默认持续运行；无人发消息、沉默、队列为空或单项额度不足都不是停机理由。事务锁忙不伪报控制成功；资源、权限、Context、P15生命周期和STOP仍由原链处理。长期锁持有时每次操作有界拒绝/延后，宿主等待而不忙循环、不假称在思考；checkpoint_busy是瞬时只读诊断，其他查询字段是最后提交的记录。

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python docs/project_memory/p18_repair_evidence/run.py independent-check-01 --independent-probe
python docs/project_memory/p18_repair_evidence/run.py p18-check-01 test_p18_
python docs/project_memory/p18_repair_evidence/run.py full-check-01
```

必须选未占用标签。正常持续启动与控制命令仍见[86号入口](../86_P18_测试索引与验收入口.md)。本轮仅隔离本地TEST/Fake，不安装常驻服务、自启动或外部自动重启，不启用正式联系/费用政策、生产凭据或供应商；Assistant/Vio未修改，生产恢复仍NOT_READY，不宣称生产exactly-once。

## 完整本轮测试历史

| 标签 | 状态 | RUN | PASS | SKIP | FAIL/ERROR | 秒 |
|---|---|---|---|---|---|---|
{chr(10).join(history)}

首轮P18专项与兼容因一次工具轮询误处理重叠34.674秒，使用独立Fixture、源码未变，已记录auxiliary-errors.log；不声称该两组严格串行。最终全量仅在其他测试全部结束后单独运行。只读rg路径错误等辅助记录保留，不算Engine缺陷。所有前期P00—P18 FAIL/ERROR/SKIP与P09 segment10 UNKNOWN保留，原p18_evidence不改。

## 身份、保护、Git与交付

最终来源为{len(current)}份源码/测试/资源，完整路径和SHA-256、原1424身份及旧测试断言核对、63保护文件/六份Schema/外部契约、三份规划、正式七文件及树、版本/pyproject、32排除项、链接/敏感内容/差异/进程清理及完整Git状态见[终局审计](final.audit.json)。完整P18成果与本轮新增材料分别列于[逐文件及排除清单](final.pending-files.md)，不以旧164项限制新增必要证据数量。

本轮无暂存、commit、push、分支、tag或release；HEAD仍5a3247a5d23ff17de2b4ba12bc327594b492e725，实际远端未查询，无CI PASS。测试子进程由各自控制器回收；记录命令、退出码、是否forcedCleanup及清理前诊断。最终只读进程观察另存证据。D-073未创建，不自行验收，完成后停在P18交回独立复核。
'''
    # Report sits three directories below the repository root.
    report=report.replace('../../../../src/','../../../src/').replace('../../../../tests/','../../../tests/')
    with (OUT/'final-report.md').open('x',encoding='utf8') as f:f.write(report)
    with (OUT/'test-history.md').open('x',encoding='utf8') as f:f.write('# P18返修完整测试历史\n\n'+table+
        '\n\n## 全部本轮标签\n\n| 标签 | 状态 | RUN | PASS | SKIP | FAIL/ERROR | 秒 |\n|---|---|---|---|---|---|---|\n'+
        '\n'.join(history)+'\n\n详见[完整报告](final-report.md)的首次失败、中间结果、辅助错误和H1 UNKNOWN说明。\n')
    with (OUT/'continuation.md').open('a',encoding='utf8') as f:f.write('\n## 当前交付（含未闭合全量失败）\n\n'+status+'\n\n'+short+'\n\nR1已实现，H1及F1原因UNKNOWN；测试已实际执行但全量未通过。最终报告、矩阵和现行档案已同步，仅剩终局审计/逐文件核对。独立复核入口为本目录final-report.md和final.audit.json，不执行旧测试session。\n')
    print(json.dumps(dict(status='IMPLEMENTED_NOT_ACCEPTED',sourceCount=len(current),newTests=len(new),full=full['run']),ensure_ascii=False))

if __name__=='__main__':main()
