"""Create a truthful blocked handoff after completed bounded runs; no Git writes."""
import ast,datetime,hashlib,json,pathlib,re,runpy,subprocess
from urllib.parse import unquote
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
S=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8')
base=read(HERE/'baseline.json');frozen=read(HERE/'frozen-source-01.json');source=S['source']()
if source!=frozen['source']:raise RuntimeError('source changed; re-assess verification')
compat=read(HERE/'compatibility-current-01.json')
if compat['status']!='COMPLETED':raise RuntimeError('compatibility still unfinished')
cleanup=read(HERE/'process-cleanup.json')
if cleanup['remaining_test_processes']:raise RuntimeError('test processes still present')
if (HERE/'handoff.audit.json').exists():raise RuntimeError('immutable audit label exists')
runs=[]
for p in sorted(HERE.glob('*.json')):
    value=read(p)
    if not isinstance(value,dict) or 'hash_before' not in value:continue
    err=(HERE/(value['label']+'.stderr.log')).read_text(encoding='utf8')
    count=re.findall(r'Ran (\d+) tests? in ([0-9.]+)s',err)
    failed=re.findall(r'FAILED \(([^)]+)\)',err)
    values={k:int(v) for k,v in re.findall(r'(failures|errors|skipped)=(\d+)',failed[-1] if failed else err.split('OK')[-1])}
    row=dict(label=value['label'],status=value['status'],exit=value.get('exit_code'),seconds=value.get('duration_seconds'),
        before=value['hash_before'],after=value.get('hash_after'),instrumented=any(s in value['label'] for s in ('profile','cpu','controlled','diagnostic','pair')))
    if count:
        n=int(count[-1][0]);row.update(total=n,fail=values.get('failures',0),error=values.get('errors',0),skip=values.get('skipped',0))
        row['pass']=n-row['fail']-row['error']-row['skip']
    else:row['total']=None
    runs.append(row)
with (HERE/'test-index.md').open('x',encoding='utf8') as out:
    out.write('# 公共阻断续修测试与诊断索引\n\n各集合有交集，不相加。所有结果为施工方实跑；规划窗口未在本轮运行这些测试。原始失败与辅助错误保留。最终全量未启动：P18原测试冲突及新W04-2组装错误需先获授权处理。\n\n')
    out.write('| 标签 | PASS/FAIL/ERROR/SKIP | exit | runner秒 | 源码前后相同 | 原始输出 |\n|---|---|---|---|---|---|\n')
    for r in runs:
        counts='/'.join(str(r[k]) for k in ('pass','fail','error','skip')) if r['total'] is not None else '诊断场景，非测试总数'
        label=r['label'];out.write(f'| [{label}]({label}.json) | {counts} | {r["exit"]} | {r["seconds"]} | {r["before"]==r["after"]} | [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |\n')
    out.write('\n特别口径：recall-profile-01是五个FailedTest导入错误，未执行业务；registry-before-01含一个重复元数据查询反例失败和一个未命中旧实现路径的辅助注入失败，后者在registry-denial-before-02修正注入位置后旧实现通过。special-final-01含49条正式测试（48 PASS/1 ERROR）和1条错误模块名造成的FailedTest，W04-1后用正确模块单独29/29通过，没有重跑49条抹掉错误。recall-cpu-01为cProfile插桩，开销会触发时限，不能冒充正式性能；locks-controlled-01为明示0.40秒持锁交错，不冒充历史现场耗时。\n\n')
    out.write('recall-profile-after-01与recall-bounded-after-01的运行文件等于现版本，但随后新增测试文件仅补非Windows兼容分支，集合指纹从fd7c10…变为当前1a0f35…；其计时为该次诊断引用，不冒充最终同版全量。special-final-01、w04-1-final-01、compatibility-current-01及两次新历史查询诊断绑定当前固定源码。\n')
    out.write('\nrecall-cpu-after-01也绑定当前固定源码；1 PASS/1 ERROR，四份资料在cProfile下仍超时，不算全部通过。[同条件插桩对照及限制](cpu-comparison.md)。\n')
compatrow=next(r for r in runs if r['label']=='compatibility-current-01')
compat_summary=f'{compatrow.get("pass")} PASS / {compatrow.get("fail")} FAIL / {compatrow.get("error")} ERROR / {compatrow.get("skip")} SKIP，{compatrow["seconds"]}秒，exit {compatrow["exit"]}'
report=f'''# W04-2 公共验证续修阶段交付（未完成全部收口）

W04-2与本次局部实现保持 IMPLEMENTED_NOT_ACCEPTED；公共最终收口 BLOCKED，EVIDENCE_CONFLICT=PRESENT。本轮没有验收/Git写入/W04-3。两项具体授权确认未完成前，不宣布本轮全部修复完成、不用当前PASS抹掉历史失败。

## W02：已证实机制与实际修补

D-084账本解析复用实际生效；当前来源复核路径的外部注册仓储却对同一祖先顺序做三次元数据I/O。第三轮CPU诊断该检查108次/338.007ms；Router512/Composer248ms的轻量测量及各类读字节/解析/副本计数见原始trace。最小修改只在 `src/continuity_engine/storage/json_external_provider_repository.py`：一次当前不跟随链接的lstat同时判定软链接/目录连接。每次访问、每个祖先仍重查，不跨请求缓存权限/来源，不改账本、解析校验、1000ms或任何效果/费用/恢复语义。

新增 `tests/test_w04_2_registry_recheck.py` 7项覆盖重复读取、返回隔离、撤销/重开、文档损坏、缺能力、真实TEST目录连接、元数据拒绝及有限I/O。修前重复探测反例失败，修后7 PASS。详情见 [具体修法与影响](w02-repair-plan.md)。

原五场景轻量测量：修前本次5 PASS、修后5 PASS；不是声称本次轻量修前又有五项失败。旧五项超时及旧HEAD对照保持历史。修后四份负载prepare约459.7ms、第三轮423.9ms；预定另两次运行产品自身elapsed四份459.441/465.252ms，第三轮16项417.132/432.095ms。三次诊断同一运行代码、原1000ms/材料不变，不是整轮回答耗时、不承诺所有设备/负载不超时。历史那轮瞬时差异的全部原因仍缺当时逐段系统资料，重复I/O是当前可证实放大机制，不能唯一倒推旧现场。

最后预定同工具CPU对照 `recall-cpu-after-01` 为1 PASS/1 ERROR；四份负载仍在cProfile下超时，完整prepare从1421.379降为1195.871ms，同85次_safe累计278.491降为95.649ms；第三轮本次通过，源码绑定当前1a0f35…。这证明所修机制实际减量，也证明不能宣称所有测量场景都已通过。没有调大1000ms或重复求绿。更多开销与停止点差异见 [同条件插桩对照](cpu-comparison.md)，该未关闭观察单独保留。

W04-2公共改动影响核查：原HEAD和施工版之前各一次失败对照已存在；本次热点仓储、Router/Composer原代码与HEAD一致，先前两版回忆内ActionSpecification计数均18。CPU较完整第三轮该校验30次总约2.436ms（含调用者，不能等同新增分支自身开销），未执行ExecutionService.current等W04接线。说明本轮性能热点与新设备执行入口分开，不把“旧版也失败”当作没有任何公共影响的证明。

## P18：需要用户确认的原测试边界

原样两项带时序本次PASS；受控真实事务延迟对照1FAIL/1ERROR复现：PAUSE锁2.334秒与随后STOP锁0.426秒属于不同区间，宿主每段只报一次BUSY；另一项owner已持有但attach仍在持锁，STOP按原0.25秒正确拒绝且未持久化，清理重试才成功。两例宿主最终正常exit0，无强制清理。没有修改P18运行实现或原断言。

这证明原“整段进程BUSY总数恰好1”与“host_alive后单次STOP必成”不能覆盖合法慢事务。原历史缺锁时序，不唯一归因。按用户限制 STOP CURRENT ITEM / PLANNING_CONFLICT，已提交 [证据、保留原方案代价与建议](p18-test-conflict.md)：按占用区间验诊断，用同一STOP身份在原观察期限内处理正确忙拒绝，产品0.25秒与安全语义不变。待明确确认，不擅自改测试。

## 新发现：历史查询目标被预算裁剪

special-final-01共50条记录：48 PASS/2 ERROR，其中一条是启动命令模块名错误；另一条原W04-2同根查询Context未就绪。没有重跑该集合到绿。原样单次诊断虽通过，显示2048 token只能保留两个各931 token回执中的一个。随后在同一TEST根执行两次query、各读取一次Context，稳定出现一个RETURNED/另一个NOT_READY。两次全局排序相同，指定目标可能被裁剪；不是同根去重。零注册仓储_safe调用，排除本次唯一运行修改直接造成该变化；前后revision1/效果0/费用0。原失败现场已被原测试清理的限制也保留。

新问题属于W04-2查询选择接线，超过本轮W02/P18定点修补。见 [新阻断与最小范围](history-new-blocker.md)，待用户确认，不改预算、不接受其他旧回执冒充当前目标。

## 同版验证和边界

当前315项源码/测试/资源：`{frozen['fingerprint']}`；正式测试身份1851（原1802保留、原W04-2新增42、本轮新增7），没有删原测试或断言。W04-1 29/29 PASS；本次公共兼容：{compat_summary}。专项中的已知业务ERROR尚未关闭。最终全量未启动，待两项决定及对应修补后固定源码执行，不借用旧完整回归。

[全部测试/诊断原始索引](test-index.md) · [逐项矩阵](matrix.md) · [固定源码/测试身份](frozen-source-01.json) · [终局审计](handoff.audit.json) · [累计精确清单](handoff.pending-files.md)。集合有重叠不相加，所有运行都是施工方本轮实跑；规划窗口只读复核与远端CI不能混称。此前414项407PASS/1FAIL/6ERROR仍保留，F1/H1/F2仍UNKNOWN，旧Windows1314 SKIP不改PASS。

## 恢复入口

先读continuation.md和两份冲突报告，确认用户新增决定；不得自动重跑任何已完成标签。保留本轮唯一存储修改、新测试及全部旧成果。下一步仅处理得到确认的项，再重判受影响验证，最终交独立复核。W04-3不启动。
'''
with (HERE/'repair-report.md').open('x',encoding='utf8') as f:f.write(report)
matrix='''# 本轮逐项矩阵

| Planning Item | Code Change | Test / Evidence | Acceptance Result |
|---|---|---|---|
| W02/N02/T03—T06 当前来源核验及性能 | JsonExternalProviderRepository._safe同次元数据合并，当前读取不缓存 | registry-before-01→registry-after-01；原五场景、两次额外固定负载；compatibility-current-01；同工具CPU修后1PASS/1ERROR | IMPLEMENTED_NOT_ACCEPTED，仅已证实放大机制，插桩四份负载仍超时 |
| P16来源、权限、隔离与原W02恢复 | 不改权限/账本/回执，读取仍原入口 | 新7项、原P16/W02公共兼容 | 本次兼容结果见索引，非验收 |
| P18控制有限等待、唯一宿主、PAUSE/STOP | 原运行实现和原测试未改 | locks-profile-01；locks-controlled-01及原始跨进程锁时序 | BLOCKED，测试同步/区间断言需确认 |
| W04-1原三处返修 | 无修改 | w04-1-final-01 29 PASS | 原D-087验收保持 |
| W04-2模拟闭环/同根历史查询 | 本轮原实现未动 | special-final-01正式49项中48PASS/1ERROR，另1导入辅助ERROR；history-pair-01稳定定位预算选择 | BLOCKED，新接线缺口待授权 |
| 同版完整回归 | 未启动 | 先处理两个冲突/缺口，禁止碰运气重复全量 | BLOCKED |

原71/71专项是本轮开始前旧版本证据，不能替代当前专项；历史矩阵保持原文。
'''
with (HERE/'matrix.md').open('x',encoding='utf8') as f:f.write(matrix)
with (HERE/'exclusions.json').open('x',encoding='utf8') as f:json.dump(base['retained'],f,ensure_ascii=False,indent=2)
shared=['docs/project_memory/'+n for n in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md')]
section=f'''<!-- W04_2_PUBLIC_REPAIR_HANDOFF_PENDING -->
## W04-2 公共续修阶段结果与待确认项

W02当前路径重复I/O已最小修补，7项新增边界回归及原五场景/固定两次负载验证通过；1000ms、当前权限/来源/账本不变。固定315项源码 `{frozen['fingerprint']}`，保留1851项身份（原1802+W04-2原42+本轮7）。W04-1同版29PASS，公共兼容{compat_summary}。

最后预定同工具CPU对照为1PASS/1ERROR，四份资料在cProfile下仍超时（完整prepare1195.871ms），减量生效不等于所有负载/观察条件都通过。原输出及观察开销限制见本轮报告，不能由兼容PASS抹掉。

不能宣称全部收口：当前专项50条记录为48PASS/2ERROR（49正式中1业务ERROR，另1错误模块名辅助ERROR）；新发现历史查询目标被原2048token预算中的其他回执挤出，稳定双查询对照已保留。P18受控时序证明两段真实占用可报两次BUSY，STOP可在attach事务中正确忙拒绝，原测试绝对断言需确认。两个受影响项停住，原断言、P18产品未改，最终全量未启动。PLANNING_CONFLICT=PRESENT/EVIDENCE_CONFLICT=PRESENT，W04-2 IMPLEMENTED_NOT_ACCEPTED，未自行验收。

[阶段报告](w04_2_public_repair_evidence/repair-report.md) · [矩阵](w04_2_public_repair_evidence/matrix.md) · [原始证据索引](w04_2_public_repair_evidence/test-index.md) · [P18待确认](w04_2_public_repair_evidence/p18-test-conflict.md) · [新增查询缺口](w04_2_public_repair_evidence/history-new-blocker.md)。70保留材料、保护项、规划/正式数据不改；原FAIL/ERROR、辅助错误、SKIP、历史F1/H1/F2 UNKNOWN照留，未取得远端CI。无暂存/提交/push/W04-3。以下历史记录保持发生时状态。

'''
for name in shared:
    p=ROOT/name;text=p.read_text(encoding='utf8')
    if '<!-- W04_2_PUBLIC_REPAIR_HANDOFF_PENDING -->' in text:raise RuntimeError('already recorded')
    p.write_text(section+text,encoding='utf8',newline='')
with (HERE/'continuation.md').open('a',encoding='utf8') as f:
    f.write('\n## 当前安全停点\n\n正式/诊断进程均已结束（核对process-cleanup.json）。唯一新增运行改动为外部注册仓储_safe；新正式测试7项。当前315项身份见frozen-source-01.json。公共兼容已完成，结果见repair-report.md；完整回归未启动，P18测试同步与W04-2定向查询新缺口待用户确认。不要重新开工、覆盖旧证据、重复启动完成标签或擅自改原测试。\n')
status=git('status','--short','--untracked-files=all');diff=git('diff','--check')
(HERE/'handoff.git-status.txt').write_text(status.stdout+status.stderr,encoding='utf8')
(HERE/'handoff.diff-check.txt').write_text(f'exit={diff.returncode}\n'+diff.stdout+diff.stderr,encoding='utf8')
paths=sorted(set(base['prior_delivery'])|set(shared)|{'src/continuity_engine/storage/json_external_provider_repository.py','tests/test_w04_2_registry_recheck.py'}|{p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()}|{(HERE/n).relative_to(ROOT).as_posix() for n in ('handoff.audit.json','handoff.pending-files.md')})
for p in paths:
    if p in base['retained']:raise RuntimeError('retained material included')
pending=HERE/'handoff.pending-files.md'
pending.write_text('# W04-2累计交付清单（未暂存）\n\n原91项成果保留；新增公共续修单列目录及1运行文件/1测试文件，共'+str(len(paths))+'项。70保留材料另见exclusions.json，禁止夹带。本清单及审计也属于交付，自身不作循环hash。\n\n| 路径 | SHA256 |\n|---|---|\n'+ '\n'.join('| `'+p+'` | `'+sha(ROOT/p)+'` |' for p in paths if (ROOT/p).exists() and p!=pending.relative_to(ROOT).as_posix())+'\n',encoding='utf8')
working=set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
syntax=[];links=[];secrets=[]
pattern=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
for p in source:
    if p.endswith('.py'):
        try:ast.parse((ROOT/p).read_text(encoding='utf8'))
        except (SyntaxError,UnicodeError) as e:syntax.append([p,type(e).__name__])
for p in paths:
    if not (ROOT/p).exists():continue
    text=(ROOT/p).read_text(encoding='utf8',errors='replace')
    if pattern.search(text):secrets.append(p)
    if p.startswith(HERE.relative_to(ROOT).as_posix()) and p.endswith('.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',text):
            ref=unquote(ref.split('#',1)[0].strip('<>'))
            if ref and not ref.startswith(('http:','https:','mailto:')) and not (ROOT/p).parent.joinpath(ref).exists() and not ref.startswith('handoff.audit.json'):links.append([p,ref])
historical={p:(ROOT/p).read_text(encoding='utf8').replace('\r\n','\n').endswith(git('show',base['head']+':'+p).stdout.replace('\r\n','\n')) for p in shared}
data=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=git('rev-parse','HEAD').stdout.strip(),branch=git('branch','--show-current').stdout.strip(),
    local_origin=git('rev-parse','origin/main').stdout.strip(),actual_remote='NOT_QUERIED_THIS_REPAIR; previous query retained, not current claim',
    staged=git('diff','--cached','--name-only').stdout.splitlines(),source=source,source_fingerprint=S['fingerprint'](source),source_count=len(source),source_matches_frozen=source==frozen['source'],test_identity_count=frozen['test_count'],original_test_ids_missing=frozen['old_1802_missing'],
    original_test_files_changed=[p for p,h in base['source'].items() if p.startswith('tests/') and source.get(p)!=h],
    original_runtime_changed=[p for p,h in base['source'].items() if p.startswith('src/') and source.get(p)!=h],
    protected_mismatches={k:[p for p,h in values.items() if sha(ROOT/p)!=h] for k,values in base['protected'].items()},
    plans_changed=[r['archivePath'] for r in base['planning'] if sha(ROOT/r['archivePath'])!=r['archiveSha256']],retained_count=len(base['retained']),retained_changed=[p for p,h in base['retained'].items() if sha(ROOT/p)!=h],
    previous_evidence_changed=[p for p,h in base['prior_delivery'].items() if p not in shared and sha(ROOT/p)!=h],historical_shared_tails_unchanged=historical,
    syntax_errors=syntax,missing_links=links,high_confidence_secret_findings=secrets,diff_check_exit=diff.returncode,
    delivery_count=len(paths),delivery_paths=paths,delivery_hashes_excluding_audit={p:sha(ROOT/p) for p in paths if (ROOT/p).exists()},unexpected_working_paths=sorted(working-set(paths)-set(base['retained'])),
    runtime_source_changes=1,new_tests=7,full_regression='NOT_STARTED_BLOCKED_PENDING_USER_DECISIONS',runs=runs,process_cleanup=cleanup,git_write_operations=False,remote_ci='NOT_VERIFIED')
with (HERE/'handoff.audit.json').open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
print(json.dumps({k:data[k] for k in ('source_fingerprint','source_count','delivery_count','staged','retained_changed','protected_mismatches','previous_evidence_changed','syntax_errors','missing_links','unexpected_working_paths')},ensure_ascii=False))
