"""Acceptance-only archive and read-only identity audit; never run Engine/tests or Git writes."""
import datetime, hashlib, json, pathlib, re, runpy, subprocess
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).parent
PREFIX = HERE.relative_to(ROOT).as_posix()
OLD = ROOT / 'docs/project_memory/w04_2_completion_evidence'
EXPECTED = 'fc185843d7de815262d9efbcab4a04337c6f303d'
FINGERPRINT = 'sha256:bee6fabd77fcdad99521ddaefdb1bf9166bc0b908b418e485fa998eb5fed53b5'
SHARED = ['docs/project_memory/' + n for n in (
    '01_当前状态.md', '03_施工日志.md', '04_决策记录.md', '06_未完成事项.md',
    '10_档案修订记录.md', '工程总档案.md')]

def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
def write(name, text): (HERE / name).write_text(text, encoding='utf8', newline='\n')
def save(name, value): write(name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def git(*args):
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
                          capture_output=True, encoding='utf8', errors='replace')

assert not (HERE / 'baseline.json').exists(), 'DO_NOT_OVERWRITE_ACCEPTANCE'
old = read(OLD / 'final.audit.json'); prior = read(OLD / 'baseline.json')
snap = runpy.run_path(str(ROOT / 'docs/project_memory/w02_b_evidence/snapshot.py'))
source = snap['source']()
assert source == old['source'] and snap['fingerprint'](source) == FINGERPRINT
assert git('branch', '--show-current').stdout.strip() == 'main'
assert git('rev-parse', 'HEAD').stdout.strip() == EXPECTED
assert git('rev-parse', 'origin/main').stdout.strip() == EXPECTED
assert not git('diff', '--cached', '--name-only').stdout.strip()
assert git('remote', 'get-url', 'origin').stdout.strip() == 'https://github.com/yuan69082-code/continuity-engine.git'
for p, h in old['delivery_hashes_excluding_audit'].items(): assert sha(p) == h, p
for values in prior['protected'].values():
    for p, h in values.items(): assert sha(p) == h, p
for p, h in prior['retained'].items(): assert sha(p) == h, p
for row in prior['planning']: assert sha(row['archivePath']) == row['archiveSha256']
working = set(git('ls-files', '-m', '-o', '--exclude-standard').stdout.splitlines())
assert working - {PREFIX + '/prepare.py'} == set(old['delivery_paths']) | set(prior['retained'])
decision_text = (ROOT / SHARED[2]).read_text(encoding='utf8')
ids = sorted(set(map(int, re.findall(r'D-(\d{3})', decision_text))))
assert max(ids) == 88 and 89 not in ids
remote = git('-c', 'http.sslBackend=openssl', '-c', 'http.sslVerify=true',
             'ls-remote', '--exit-code', 'origin', 'refs/heads/main')
assert remote.returncode == 0 and remote.stdout.split()[0] == EXPECTED, remote.stderr
save('remote-precheck.json', dict(command=remote.args, exit_code=remote.returncode,
     stdout=remote.stdout, stderr=remote.stderr,
     checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
     earlier_default_backend_observation={'exit_code':1,
         'safe_error':'schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)',
         'source':'Earlier tool output this turn; localized suffix was not decoded reliably. No token read/copied.',
         'command':['git','ls-remote','--exit-code','origin','refs/heads/main']},
     configuration_changed=False, tls_verification=True))
baseline = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    head=EXPECTED, branch='main', source=source, fingerprint=FINGERPRINT,
    delivery={p:sha(p) for p in old['delivery_paths']}, retained=prior['retained'],
    protected=prior['protected'], planning=prior['planning'], decision_before=ids,
    remote_precheck_sha256=sha(PREFIX+'/remote-precheck.json'))
save('baseline.json', baseline)
save('exclusions.json', prior['retained'])

table='| 施工方既有同版实跑 | PASS / FAIL / ERROR / SKIP | unittest 秒 / runner 秒 | exit |\n|---|---|---|---|\n'
for row in old['runs']:
    label=row['label']; run=read(OLD/(label+'.json'))
    assert run['source_before']==run['source_after']==source and run['exit_code']==0
    table+=f"| [{label}](../w04_2_completion_evidence/{label}.json) | {row['pass']} / {row['fail']} / {row['error']} / {row['skip']} | {row['seconds']} / {row['runner_seconds']} | 0 |\n"
write('acceptance-report.md', f'''# D-089：W04-2 与明确公共补修正式验收

2026-09-28，用户明确验收 W04-2 模拟设备、模拟身体、局部历史查询，以及 W02 文件检查优化、P18 两项测试同步与区间断言修正、指定历史回执选择修补。核对现有决定最高编号 D-088（开工）后登记 D-089。本次另授权现有 Engine main 精确暂存、一次普通提交及普通 push 到既有 origin/main；不授权 W04-3。

W04-2 与上述补修为 **ACCEPTED**；W04 整体仍 **IN_PROGRESS**。W04-1/D-087、W02/D-081、W03/D-083、D-084、P00—P18 原验收保持。W04-3/4、W05/W06、P19—P23 按原阶段，未因本次授权开工或开放生产。

依据现行总施工 v1.6、最终新增 v1.6、长期能力 v6.10 的 W04 子批次二、N10/N12/N13/N21、T27—T29/T37/T18/T22/T85—T87 及 T66/T67/T72 本批适用部分。三份原字节归档、D-085 独有材料和现行索引继续留在排除清单；六份共享工程档案中的既有授权记录照留。旧报告、矩阵及冲突记录原样保存，本目录是新的验收入口，不能把旧时点状态改成当时已经通过。

## 验收依据与关闭范围

规划窗口独立只读核对了代码、原始输出和文件身份，**没有运行 Engine 或测试**。本次也仅核对和归档，未重跑。316 项源码/测试/资源仍为 `{FINGERPRINT}`；原1851项测试身份保留，新增12项，总1863项。

{table}

集合重叠不相加。全量1863项＝1862 PASS、1既有Windows1314 SKIP、0 FAIL/ERROR。原始输出、命令、退出码和前后源码见[施工测试索引](../w04_2_completion_evidence/test-index.md)。

| 原已知阻断 | 证据和处置 | 本次结论 |
|---|---|---|
| W02 回忆重复文件检查及公共兼容超时 | 保留 `_safe` 单次当前元数据查询优化；原1000ms/材料/权限及来源检查不变；五原场景、追加两负载与同版兼容/全量通过 | 本机正常正式TEST覆盖的补修 ACCEPTED；不声称所有插桩或任意负载低于1秒 |
| P18 两项测试把不同忙区间混计、owner存活误当attach完成 | 用户先前明确批准测试修正；逐实际区间恰好1 BUSY及恢复证据；attach释放同步、同身份STOP有限重试；产品0.25秒/CAS/权限/终态未改 | 已知测试同步及断言冲突关闭，原失败记录不删 |
| 指定历史回执被另一同根回执挤出预算 | 修前双查询正反序有效反例；定向选择经原Router/Composer，2048预算/核心保护不变；目标不可读或放不下仍拒绝 | 指定选择缺口及验证阻断关闭；不授权同根替换事实 |
| W04-2 公共同版验证缺口 | 最终32、87、417及一次全量绑定同一源码，静态复核与用户正式确认 | 本批 EVIDENCE_CONFLICT=NONE；不是所有潜在缺陷不存在的保证 |

本批 PLANNING_CONFLICT=NONE，既有选择已由用户授权处理。旧 PRESENT、初次 FAIL/ERROR、辅助路径/标识/异常类型错误、错误启动模块名、中断、cProfile 超时均是历史，不覆盖。cProfile 的重度观察超时未计PASS；历史耗时差异不作唯一归因。F1/H1/F2 原因仍 UNKNOWN。

## 实际效果与未开放能力

隔离 TEST 中已有模拟观察→Perception、动作→P17/E5-A→可核验结果，以及带范围的局部历史查询→Router/Composer；指令发出、点击和业务完成不混同。断开、旧连接、撤权、过期、UNKNOWN 和重开恢复按原边界处理。模拟效果不代表真实设备、账号、生产网络或硬件安全已验证。

W04-3 工具发现与临时接入、W04-4 跨入口接续及包级贯通尚待授权；W05 自然记忆/梦境、P19 页面、P20/P21 生产恢复、P22 实接仍 NOT_READY。更大材料、更大文件、其他设备、真实语言和生产性能没有通用保证。无远端 CI PASS 证据。

## 本轮归档与提交范围

只新增本验收目录并在六份共享档案前置本次记录，原字节尾部保留。原249项成果加必要验收增量，以[最终清单](final.pending-files.md)为准；[70项排除清单](exclusions.json)不暂存、不删除。运行实现、测试、保护文件、正式数据、规划原文和软件版本本轮不改。

精确暂存拟使用命令级 `core.autocrlf=false` 保持本次所有工作树字节（尤其原日志）原样入库，不改全局配置。暂存后逐文件 Git blob 与工作树字节核对；若属性导致不一致则停止，不静默规范化。历史格式提示保留，差异检查结果见审计。

提交前实际远端已核实为 `{EXPECTED}`，默认Schannel失败和单次OpenSSL成功均记录在[远端预检](remote-precheck.json)，证书校验保持开启。提交、push和提交后远端核验尚需实际执行，不在此预填成功；操作后结果在最终交付中如实报告。[验收矩阵](acceptance-matrix.md) · [终局审计](final.audit.json)。
''')
write('acceptance-matrix.md', '''# D-089 验收矩阵

Planning Item → Code Change → Test → Acceptance Result。依据用户正式验收及规划窗口只读复核；测试均引用施工方同版实跑，不重复计数。

| Planning Item | Code Change / 原链 | Test / 证据 | Acceptance Result |
|---|---|---|---|
| N13/N12 UI，T27—T29/T37 | device_operation、DeviceOperationService、隔离模拟Adapter；原Action/P17/E5-A | 原42项模拟测试、专项87及全量；[初版定位](../w04_2_evidence/coverage-map.md) | ACCEPTED，本机隔离模拟范围 |
| N10，T22/T85/T86 | W04-1 Body绑定复用，传感→Perception、动作→原回执 | NONE/合法零/未知、代次/到期/撤权/断开/未知/恢复，专项及全量 | ACCEPTED，本批模拟闭环；真实硬件未接入 |
| N10，T87 | 模拟硬件/Somatic/Dream分源契约 | 原模拟链及隔离反例 | ACCEPTED，本批分源；W05 Dream联动未实现 |
| N21，T66/T67/T72 | HistoryScope与原ExecutionContextSource→Router/Composer | 新9项指定回执测试、原历史查询/同源/权限与恢复 | ACCEPTED，本批局部模拟查询；不代替W05自然记忆 |
| T18/唯一结果权威 | 原操作身份、E5-A、当前来源和权限，不盲重放UNKNOWN | 重开/返回丢失/重复/取消，原模拟专项及全量 | ACCEPTED，本批适用恢复 |
| W02/N02/T03—T06 | json_external_provider_repository._safe优化，原1000ms不变 | 原5场景、追加2负载、公共417及全量 | ACCEPTED，本机正式负载；cProfile超时历史照留 |
| P18控制测试 | test_p18_runtime_contention获准两项修正及3项受控回归 | 定向32、公共417及全量；原断言全文与受控失败保留 | ACCEPTED，产品期限/CAS/控制语义未改 |
| 指定历史回执选择 | device_operation_service与execution_context_source目标选择；不扩2048预算 | history-before-03修前；新9项正反/预算/权限/同根/只读/重开 | ACCEPTED，不接受其他同根回执冒充 |
| W04-1/公共兼容 | 原权威、权限、生命周期、主体性及持续运行边界保留 | 专项87含W04-1原29；公共417；全量1862PASS/1SKIP | 本批兼容门通过；不重做D-087及其他历史验收 |

[同版结果及限定](acceptance-report.md)；[原施工矩阵](../w04_2_completion_evidence/matrix.md)保持当时状态。W04整体IN_PROGRESS；W04-3/4及后续未开工。
''')
summary=f'''<!-- W04_2_ACCEPTED_D089_20260928 -->
## D-089：W04-2 及明确公共补修正式验收

2026-09-28，用户正式验收模拟设备／模拟身体／局部历史查询，以及W02文件检查优化、P18两项测试同步与区间断言修正、指定历史回执选择修补；授权本批精确暂存、现有main一次普通提交和origin/main普通push。D-088开工记录不改。W04-2及上述补修=ACCEPTED；W04整体=IN_PROGRESS；W04-3/4未开工。W04-1/D-087、W02/D-081、W03/D-083、D-084及P00—P18历史验收保持。

规划窗口只读复核，未运行Engine/测试。本次引用施工方同版：定向32PASS、原回忆5PASS及追加2PASS、W04专项87PASS、公共417PASS、全量1863项=1862PASS/1原Windows1314SKIP/0FAIL/ERROR。集合重叠不相加；原1851身份保留，新增12；316项源码 `{FINGERPRINT}` 不变。本次仅归档与Git收尾，未改实现/测试、未重跑。

本批已知选择/验证阻断依据[验收报告](w04_2_acceptance_evidence/acceptance-report.md)逐项关闭，现行本批PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，不保证无其他缺陷。旧PRESENT、FAIL/ERROR/中断/辅助错误/cProfile超时及F1/H1/F2 UNKNOWN保留；1000ms、2048预算、P18产品0.25秒与原边界不改。不声明任意负载性能、真实设备或生产接入通过，无远端CI PASS证据。

70份保留材料（含D-085独有规划材料）排除；六份共享档案的D-085等旧记录保留。本次更新仅前置，以下历史原文不倒改。实际提交/push结果待操作后核验，不预填成功。

[验收矩阵](w04_2_acceptance_evidence/acceptance-matrix.md) · [精确清单](w04_2_acceptance_evidence/final.pending-files.md) · [审计](w04_2_acceptance_evidence/final.audit.json) · [施工原始测试](w04_2_completion_evidence/test-index.md)。下一步先完成本批Git收尾，完成后停止；W04-3/4、W05、P19及生产恢复/接入仍待各自授权。

'''
for p in SHARED:
    original=(ROOT/p).read_bytes()
    assert b'W04_2_ACCEPTED_D089_20260928' not in original
    (ROOT/p).write_bytes(summary.encode('utf8')+original)

# Prepare immutable manifest artifacts after all authorized documentation edits.
ledger={PREFIX+'/'+n for n in ('final.pending-files.md','final.files.json','final.audit.json')}
for n in ('final.pending-files.md','final.files.json','final.audit.json','diff-check.txt'):
    (HERE/n).touch(exist_ok=False)
diff=git('diff','--check');write('diff-check.txt','exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr)
paths=sorted(set(old['delivery_paths'])|{p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()})
assert not set(paths)&set(prior['retained'])
hashes={p:sha(p) for p in paths if p not in ledger}
write('final.pending-files.md','# D-089 精确提交清单\n\n累计'+str(len(paths))+'项＝原249项＋本次验收新增'+str(len(paths)-249)+'项。六份共享档案已列于原249中，本轮仅前置验收，不重复计数；其既有D-085授权记录照留。70项保留另见[exclusions.json](exclusions.json)，一律排除。\n\n原实现与测试不变。以下为工作树原字节SHA256；拟命令级关闭自动行尾转换后逐blob验证，无全局配置修改。清单自身及互引审计不作循环hash，final.audit包含前两份hash。提交后实际结果不预填。\n\n| 路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+hashes.get(p,'SELF_REFERENTIAL_MANIFEST')+'` |' for p in paths)+'\n')
save('final.files.json',dict(count=len(paths),paths=paths,hashes=hashes,self_reference_exclusions=sorted(ledger)))
links=[];secrets=[];suspect=[]
secret_pattern=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
for p in paths:
    text=(ROOT/p).read_text(encoding='utf8',errors='replace')
    if secret_pattern.search(text):secrets.append(p)
    if any(x.lower() in ('__pycache__','temp','sandbox','dist','build','.venv') for x in pathlib.PurePosixPath(p).parts) or pathlib.Path(p).suffix in ('.pyc','.whl','.zip','.exe'):suspect.append(p)
    if p.startswith(PREFIX) and p.endswith('.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',text):
            ref=unquote(ref.split('#')[0].strip('<>'))
            if ref and not ref.startswith(('http:','https:','mailto:')) and not (ROOT/p).parent.joinpath(ref).exists():links.append([p,ref])
working=set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision='D-089',stage='W04-2 ACCEPTED; W04 IN_PROGRESS; W04-3 NOT_STARTED',head=EXPECTED,
    source_fingerprint=snap['fingerprint'](snap['source']()),source_count=len(source),source_unchanged=snap['source']()==source,
    old_delivery_changes_outside_shared=[p for p,h in baseline['delivery'].items() if p not in SHARED and sha(p)!=h],
    shared_history_suffix_preserved={p:hashlib.sha256((ROOT/p).read_bytes()[len(summary.encode('utf8')):]).hexdigest()==baseline['delivery'][p] for p in SHARED},
    protected_mismatches={k:[p for p,h in v.items() if sha(p)!=h] for k,v in prior['protected'].items()},
    planning_mismatches=[p['archivePath'] for p in prior['planning'] if sha(p['archivePath'])!=p['archiveSha256']],
    retained_count=len(prior['retained']),retained_mismatches=[p for p,h in prior['retained'].items() if sha(p)!=h],
    missing_links=links,high_confidence_secret_findings=secrets,suspect_artifacts=suspect,diff_check_exit=diff.returncode,
    original_test_count=1851,new_test_count=12,final_test_count=1863,test_identity_evidence='../w04_2_completion_evidence/frozen-source-01.json',
    tests_executed_this_turn=False,test_results_referenced=old['runs'],remote_verified_precommit=remote.stdout.strip(),
    workflow_paths=git('ls-files','.github/workflows').stdout.splitlines(),ci='NO_REMOTE_RUN_OR_CHECK_RESULT_OBTAINED',
    delivery_count=len(paths),delivery_paths=paths,delivery_hashes_excluding_audit={p:sha(p) for p in paths if p!=PREFIX+'/final.audit.json'},
    unexpected_paths=sorted(working-set(paths)-set(prior['retained'])),missing_paths=sorted(set(paths)|set(prior['retained'])-working),
    staged_before=git('diff','--cached','--name-only').stdout.splitlines(),git_writes_at_this_audit=False)
# Explicitly parenthesize set union before subtraction.
audit['missing_paths']=sorted((set(paths)|set(prior['retained']))-working)
save('final.audit.json',audit)
checks=[not audit[k] for k in ('old_delivery_changes_outside_shared','planning_mismatches','retained_mismatches','missing_links','high_confidence_secret_findings','suspect_artifacts','unexpected_paths','missing_paths','staged_before')]
assert all(checks) and all(audit['shared_history_suffix_preserved'].values()) and all(not v for v in audit['protected_mismatches'].values()) and audit['source_unchanged']
print(json.dumps({k:audit[k] for k in ('decision','source_fingerprint','delivery_count','retained_count','diff_check_exit','unexpected_paths','missing_paths','workflow_paths')},ensure_ascii=False))
