"""D-091 documentation and read-only audit. No Engine/tests or Git mutations."""
import datetime
import hashlib
import json
import os
import pathlib
import re
import runpy
import subprocess
import time
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).parent
PREFIX = HERE.relative_to(ROOT).as_posix()
OLD = ROOT / 'docs/project_memory/w04_3_repair_evidence'
EXPECTED = 'f64fb797ae4defae2dfd16278f38e89c8b13cd66'
FINGERPRINT = 'sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506'
SHARED = ['README.md'] + ['docs/project_memory/' + n for n in (
    '01_当前状态.md', '03_施工日志.md', '04_决策记录.md', '06_未完成事项.md',
    '10_档案修订记录.md', 'CHANGELOG.md', '工程总档案.md')]
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
os.environ['GIT_TERMINAL_PROMPT'] = '0'


def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
def write(name, text): (HERE / name).write_text(text, encoding='utf8', newline='\n')
def save(name, value): write(name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def git(*args):
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
                          capture_output=True, encoding='utf8', errors='replace', timeout=60)
def lines(*args):
    p = git(*args)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip().splitlines()


assert not (HERE / 'baseline.json').exists(), 'DO_NOT_OVERWRITE_ACCEPTANCE'
prior = read(OLD / 'baseline.json')
old = read(OLD / 'final.files.json')
audit_old = read(OLD / 'final.audit.json')
frozen = read(OLD / 'frozen-source-01.json')
snap = runpy.run_path(str(ROOT / 'docs/project_memory/w02_b_evidence/snapshot.py'))
source = snap['source']()
assert source == frozen['source'] and snap['fingerprint'](source) == FINGERPRINT
assert len(source) == 321
assert lines('branch', '--show-current') == ['main']
assert lines('rev-parse', 'HEAD') == lines('rev-parse', 'origin/main') == [EXPECTED]
assert not lines('diff', '--cached', '--name-only')
assert lines('remote', 'get-url', 'origin') == ['https://github.com/yuan69082-code/continuity-engine.git']
for p, h in old['hashes'].items(): assert sha(p) == h, p
assert sha('docs/project_memory/w04_3_repair_evidence/final.files.json') == audit_old['files_json_sha256']
assert sha('docs/project_memory/w04_3_repair_evidence/final.pending-files.md') == audit_old['pending_files_sha256']
assert sha('docs/project_memory/w04_3_repair_evidence/final.audit.json') == '0c4d08f4c0b44279f482b7d6e1ca54c13e0642636cb24cc8ca9a218bf3d05666'
for values in prior['protected'].values():
    for p, h in values.items(): assert sha(p) == h, p
for p, h in prior['retained'].items(): assert sha(p) == h, p
for row in prior['planning']: assert sha(row['archivePath']) == row['archiveSha256']
formal = {p.relative_to(ROOT).as_posix() for p in (ROOT / '.continuity-data').rglob('*') if p.is_file()}
assert formal == set(prior['protected']['formalFiles'])
working = set(lines('ls-files', '-m', '-o', '--exclude-standard'))
assert working - {PREFIX + '/prepare.py'} == set(old['paths']) | set(prior['retained'])
ids = sorted(set(map(int, re.findall(r'D-(\d{3})', (ROOT / SHARED[3]).read_text(encoding='utf8')))))
assert max(ids) == 90 and 91 not in ids
started = time.monotonic()
remote = git('-c', 'http.sslBackend=openssl', '-c', 'http.sslVerify=true',
             'ls-remote', '--exit-code', 'origin', 'refs/heads/main')
assert remote.returncode == 0 and remote.stdout.split()[0] == EXPECTED, remote.stderr
save('remote-precheck.json', dict(command=remote.args, exit_code=remote.returncode,
    stdout=remote.stdout, stderr=remote.stderr, seconds=round(time.monotonic()-started, 3), checked_utc=now(),
    earlier_default_backend_observation=dict(command=['git', 'ls-remote', '--exit-code', 'origin', 'refs/heads/main'],
        at_utc='2026-09-28T17:40:51.487144+00:00', exit_code=128,
        safe_error='schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)',
        source='Tool output in this acceptance turn; localized suffix was not decoded reliably; not reconstructed.'),
    earlier_openssl_success_utc='2026-09-28T17:40:52.411373+00:00',
    configuration_changed=False, tls_verification=True, credentials_read_or_copied=False))
baseline = dict(at_utc=now(), head=EXPECTED, branch='main', source=source, fingerprint=FINGERPRINT,
    delivery={p:sha(p) for p in old['paths']}, retained=prior['retained'],
    protected=prior['protected'], planning=prior['planning'], decision_before=ids,
    index_sha256=sha('.git/index'), status=git('status','--short','--untracked-files=all').stdout,
    remote_precheck_sha256=sha(PREFIX+'/remote-precheck.json'))
save('baseline.json', baseline)
save('exclusions.json', prior['retained'])
save('auxiliary-history.json', dict(at_utc=now(), engine_or_test_runs=False, observations=[
    dict(kind='DOCUMENT_SEARCH_HELPER_ERROR', command='rg ... docs/project_memory/planning_v16_20260927/planning/*.md',
         result='Windows literal wildcard path: os error 123; no file mutation. Corrected to rg -g *.md on directory; clauses subsequently read.'),
    dict(kind='READ_ONLY_REMOTE_DEFAULT_TLS_ERROR', evidence='remote-precheck.json', result='Single-command OpenSSL succeeded with TLS verification retained.')]))

refs = []
table = '| 施工方既有同版运行 | PASS / FAIL / ERROR / SKIP | unittest 秒 / runner 秒 | exit |\n|---|---|---|---|\n'
for row in audit_old['runs']:
    label = row['label']; run = read(OLD / (label + '.json'))
    assert run['source_before'] == run['source_after'] == source and run['exit_code'] == 0
    err = (OLD / (label + '.stderr.log')).read_text(encoding='utf8')
    assert re.search(r'Ran ' + str(row['total']) + r' tests?', err) and 'OK' in err
    refs.append(dict(summary=row, evidence={n:sha('docs/project_memory/w04_3_repair_evidence/'+label+n)
        for n in ('.json','.stdout.log','.stderr.log')}, command=run['command']))
    table += f"| [{label}](../w04_3_repair_evidence/{label}.json) | {row['pass']} / {row['fail']} / {row['error']} / {row['skip']} | {row['seconds']} / {row['runner_seconds']} | 0 |\n"
assert len(frozen['test_ids']) == 1923 and set(prior['test_ids']) <= set(frozen['test_ids'])
assert not frozen['old_test_changes'] and not frozen['original_1909_missing']
assert len(frozen['new_ids']) == 14
save('test-references.json', dict(source_fingerprint=FINGERPRINT, test_ids=frozen['test_ids'], new_ids=frozen['new_ids'],
    old_count=1909, final_count=1923, tests_executed_this_turn=False,
    planning_review='Independent read-only code/evidence/identity review; no Engine test execution', runs=refs))

write('acceptance-report.md', f'''# D-091：W04-3 初版及 R1/R2 正式验收

2026-09-29，用户正式验收 W04-3 工具发现、授权与缺项检查、临时接入、验证、使用、结束及恢复，以及 R1 等待首项不持续排除其他可执行事项、R2 取消累计三份清理请求的永久终止门槛。核查决定最高编号 D-090（开工），本次登记 **D-091**，不改写原决定。用户同时授权本批精确暂存、现有 Engine main 一次普通提交及向既有 origin/main 普通 push；不授权 W04-4。

**W04-3 = ACCEPTED；W04 整体 = IN_PROGRESS；W04-4 = NOT_STARTED。** W04-1/D-087、W04-2/D-089及全部既有阶段验收不重做。依据现行总施工 v1.6、最终新增 v1.6、长期能力 v6.10 的 W04 子批次三、N14/T30—T32/T41、C11、适用T18及N21查询衔接；三份规划原文及现行索引属于70份本地保留材料，不修改、不提交，不宣称D-085独有材料已推送。

## 本次验收依据

规划窗口独立只读复核了代码、原始输出、测试身份、源码指纹、交付清单和保护范围，**没有运行 Engine 或测试**。本次也只做验收归档和Git收尾，不重跑测试。321项源码/测试/资源逐文件与五组前后清单一致：`{FINGERPRINT}`。原1909项身份和旧测试文件保留，新增14项，共1923项。

{table}

集合有交集，不相加。全量1923项＝1922 PASS、1个既有Windows1314 SKIP、0 FAIL/ERROR；SKIP不算PASS。命令、输出、时长和退出码见[原始测试索引](../w04_3_repair_evidence/test-index.md)，本次核对的原件hash见[test-references.json](test-references.json)。没有取得远端CI run/check结果，不能声称CI PASS。

## 已知阻断关闭依据及保留历史

| 本批已知事项 | 具体依据 | 本次状态 |
|---|---|---|
| 初版发现至退出的接线及验证 | 初版46项正式回归纳入最终W04-3的60项；发现≠授权≠接通≠当前可用，单次/限时/持续、当前资格及UNKNOWN按原P08/P16/P17/P18/E5-A处理；[初版矩阵](../w04_3_evidence/matrix.md)与原始记录对应 | 本批已交付初版ACCEPTED |
| R1 固定首项截取使后项不能入队 | before-02真实宿主反例FAIL；只为原Scheduler尚未拥有的需求提供最多两个入队名额，原native认知/维护不关闭；同反例及多事项、恢复、暂停/停止、UNKNOWN正式回归通过 | 已知入队饥饿缺口及其复核阻断关闭 |
| R2 全生命周期三次清理封顶 | before-02三份失败后不能续做FAIL；每次advance仍最多一份清理，后续自动清理由上一份原回执时间退避、默认复用P18的5秒；重开、部分失败、UNKNOWN/返回丢失、撤权与隔离正反对照通过 | 已知永久终止门槛及其复核阻断关闭 |
| 返修后同版与兼容证据待复核 | 最终14/60/87/417及全量均绑定上列源码；规划窗口只读复核和用户本次明确确认 | 本批现行EVIDENCE_CONFLICT=NONE；不代表无其他潜在缺陷 |

本批现行PLANNING_CONFLICT=NONE。旧IMPLEMENTED_NOT_ACCEPTED、旧EVIDENCE_CONFLICT=PRESENT、修前FAIL、辅助ERROR、中断、原SKIP、格式/行尾提示及重度剖析超时保留原字节；未把旧时点改成已验收。历史F1/H1/F2仍为UNKNOWN，本次验收不证明其历史唯一根因。详见[原返修报告](../w04_3_repair_evidence/final-report.md)、[调查记录](../w04_3_repair_evidence/investigations.md)。

## 效果与未开放边界

本机隔离TEST中，等待登录/依赖/核实/清理的工具不持续占掉所有新任务入口，原认知与维护仍可推进；清理失败超过三份后，当前条件恢复且资格有效时可沿原连接续做。UNKNOWN先查询原事实、成功清理不重复；原请求/费用/状态权威不另建。

旧Context失效仍正确拒绝，不自动重绑旧请求；合法后续步骤须经原链取得当前Context。不保证任意无界负载公平性、所有场景清理必能成功或生产性能。原W02的1000毫秒、历史查询2048预算、P18控制等待及每轮两个need上限均不变。主体持续运行、Owner PAUSE/STOP、当前权限/host/generation、生命周期及内部认知与现实行动边界保持。

真实服务、账号、设备、生产凭据仍未开放。W04-4跨入口接续与包级贯通、W05自然记忆/梦境、P19完整页面、P20/P21正式恢复及P22真实接入仍按原阶段待授权/未就绪。本次不是W04整体验收。

## 档案与Git范围

本轮只新增本验收目录，并在README及七份工程档案前置当前验收入口；原完整历史后缀逐字节核对。共享档案中已有D-085等授权记录保留，但70份独立保留材料不纳入。原227项加本次必要增量，实际路径与数量见[精确清单](final.pending-files.md)、[hash清单](final.files.json)，[排除清单](exclusions.json)列70份原件hash。源码、正式测试、原始测试日志、63保护、规划、正式七文件和版本本轮不改。

暂存使用命令级 `core.autocrlf=false`，不修改全局配置，逐文件比对Git blob与工作树原字节，尤其保留旧日志。若发生其他属性转换或范围不符则停下；不通过改写日志清除行尾提示。检查结果见[审计](final.audit.json)。

提交前实际远端已查询为 `{EXPECTED}`；默认TLS凭据错误与单次OpenSSL核验见[远端预检](remote-precheck.json)，证书验证开启。本文不预填提交或push成功；实际操作和推送后核验单独在最终回复及明确标注的本地记录报告，不擅自追加第二提交。

[正式验收矩阵](acceptance-matrix.md) · [施工只读链路示例](../w04_3_repair_evidence/chain-example.md) · [原恢复语义](../w04_3_repair_evidence/recovery-semantics.md)。完成本批Git收尾即停止。
''')

write('acceptance-matrix.md', '''# D-091 正式验收矩阵

Planning Item → Code Change → Test → Acceptance Result。测试引用施工方最终同版实跑；规划窗口只读复核，用户正式验收。原初版、返修矩阵保持当时状态，本表是当前验收结果。

| Planning Item | Code Change / 原链 | Test / 证据 | Acceptance Result |
|---|---|---|---|
| N14/T30 候选发现、核对和合法选路 | temporary_tools.ToolOffer；temporary_tool_service.candidates/offer；P16/E5-A | discovery_is_real_p16_and_not_current_availability、missing_discovery_and_untrusted_material_are_not_callable、technical_api_unavailable_may_select_ui_but_denial_and_unknown_do_not | ACCEPTED；资料不授予权限；缺入口诚实拒绝 |
| N14/T31 授权内接入、缺项等待 | ToolLease、conditions、原P08/P17、advance | authorized_connect_verify_use_cleanup_and_readonly、missing_login_resumes_same_connection_without_discovery_or_cost_repeat、conditions_identify_new_scope_budget_dependency_without_creating_connection | ACCEPTED；不逐步人工审批，购买/扩权不从普通授权推导 |
| N14/T32 单次/限时/持续结束及续期 | 当前租约、原Action/P17回执、Device可选门禁 | single_use_cannot_run_second_business_action、timed_task_completes_then_expiry_cleanup_uses_original_connection、explicit_renewal_uses_new_valid_grant_and_new_connection_identity | ACCEPTED；续期新有效条件，过期使用不复活 |
| N14/T41 退出中断、部分清理/未知/失败 | query/inspect/advance，原E5-A与P17事实 | lost_cleanup_response_recovers_without_duplicate_removal、cleanup_unknown_does_not_claim_closed_or_start_another_cleanup、cleanup_preserves_other_connection_and_subject_files | ACCEPTED；待清理不是断净，原失败不删除 |
| N14/T18 原请求续接及未接入取消 | connect最终门禁、原操作身份/取消与事实查询 | cross_process_lost_connection_recovery_and_replay、cancel_before_connection_reopen_and_replay_never_opens_it、cancel_during_connect_before_native_commit_is_fenced | ACCEPTED；不重复发现、连接、业务效果或费用 |
| N21 查询衔接 | 原DeviceOperation、指定回执Router/Composer | history_query_reuses_original_receipt_router_composer及W04-1/2专项 | ACCEPTED；2048预算不改，不代替W05自然记忆 |
| C11/N14/T31 R1 入队饥饿 | TemporaryToolRuntimeWork.needs复用Scheduler已有身份，最多两个新need | before-02修前FAIL；waiting_first_does_not_starve_second_or_native_work、both_native_needs_and_two_tools_obtain_real_dispatch、dependency_wait_and_pending_cleanup_do_not_block_ready | ACCEPTED；认知/维护仍真实推进；有限测试不保证无界负载 |
| C11/N14/T32/T41 R2 三次永久封顶 | advance每次最多一个清理；原回执completed_at退避，正有限配置默认5秒 | before-02修前FAIL；three_failed_cleanup_facts_can_resume_via_host、automatic_partial_cleanup_survives_three_failures_and_reopen、cleanup_backoff_is_receipt_bound_readonly_and_configurable | ACCEPTED；失败次数不永久撤销恢复资格，不无限快重试 |
| 当前权限、身份、控制与Context | W04绑定、原guard/current条件；旧Context不重绑 | cleanup_revocation_pause_stop_and_other_connection_isolation、current_host_and_scope_denial_prevent_new_cleanup、old_context_is_not_rebound_after_native_revision | ACCEPTED；PAUSE/STOP/host/环境隔离保持 |
| 秘密及只读边界 | 原P16/P17材料检查、静态诊断、inspect前后授权 | credential_secret_rejected_before_ledger_write_and_traceback_safe、view_rechecks_permission_at_return、connection_fact_corruption_refuses_read_and_has_no_effect | ACCEPTED；凭据仅受控引用；只读不触发业务或成长 |
| 兼容与完整回归 | 原P08/P16/P17/P18/W02/W03及W04-1/2 | 定点14、W04-3 60、W04-1/2 87、公共417、全量1922PASS/1SKIP；全组同版 | 验收范围内兼容证据通过；集合交叠不相加，CI未取得 |

测试名位于[初版测试](../../../tests/test_w04_3_tools.py)及[返修测试](../../../tests/test_w04_3_repairs.py)。源路径：[工具域](../../../src/continuity_engine/domain/temporary_tools.py)、[工具服务](../../../src/continuity_engine/services/temporary_tool_service.py)、[Action接线](../../../src/continuity_engine/domain/action_planning.py)、[Device门禁](../../../src/continuity_engine/services/device_operation_service.py)。

[原初版矩阵](../w04_3_evidence/matrix.md)、[原返修矩阵](../w04_3_repair_evidence/matrix.md)、[同版原始证据](../w04_3_repair_evidence/test-index.md)、[本次验收限定](acceptance-report.md)。W04整体IN_PROGRESS；W04-4及后续未开工，F1/H1/F2仍UNKNOWN。
''')

summary = f'''<!-- W04_3_ACCEPTED_D091_20260929 -->
## D-091：W04-3 初版及 R1/R2 正式验收

2026-09-29，用户正式验收W04第三子批次工具发现、临时接入/等待、使用、结束及恢复，以及R1等待首项入队饥饿、R2累计三份清理请求永久封顶两项返修；授权本批精确暂存、现有main一次普通提交及既有origin/main普通push。D-090开工记录保持。W04-3=ACCEPTED；W04整体=IN_PROGRESS；W04-4=NOT_STARTED，不启动下一批。

规划窗口完成代码、原始证据、身份和保护范围的独立只读复核，未运行Engine或测试。本次引用施工方最终同版：定点14PASS、W04-3专项60PASS、W04-1/2专项87PASS、公共417PASS、全量1923项=1922PASS/1既有Windows1314SKIP/0FAIL/ERROR。集合重叠不相加；原1909项身份和旧测试保留，新增14。源码321项 `{FINGERPRINT}`；本轮只归档，不改实现/测试或重跑。

本批已知复核阻断依据验收报告逐项关闭：原真实宿主before-02的两条反例同场景修后通过，并由同版兼容/全量、规划窗口只读复核及用户确认支持。当前本批EVIDENCE_CONFLICT=NONE、PLANNING_CONFLICT=NONE，不保证无其他缺陷。旧PRESENT、IMPLEMENTED_NOT_ACCEPTED、FAIL/ERROR/辅助错误/中断/格式提示及F1/H1/F2 UNKNOWN原样保留。旧Context失效仍拒绝、不自动重绑；原两个need/1000ms/2048/P18控制及权限/费用/E5-A边界不变。

仅本机隔离TEST验证；不保证任意无界负载公平性或生产性能。真实账号、服务、设备、凭据未开放，未取得远端CI结果。70份保留材料含D-085独有规划档案/现行索引继续排除，不冒称已推送；共享档案的既有授权记录保留。63保护、规划原文、正式七文件、版本及原始测试日志本轮不变。

[验收报告](w04_3_acceptance_evidence/acceptance-report.md) · [逐项验收矩阵](w04_3_acceptance_evidence/acceptance-matrix.md) · [精确清单](w04_3_acceptance_evidence/final.pending-files.md) · [审计](w04_3_acceptance_evidence/final.audit.json) · [原测试索引](w04_3_repair_evidence/test-index.md)。实际提交/push结果在操作后单独核验，不预填成功。以下全部旧时点记录原样保留。

'''
for p in SHARED:
    original = (ROOT/p).read_bytes()
    assert b'W04_3_ACCEPTED_D091_20260929' not in original
    prefix = summary.replace('](w04_', '](docs/project_memory/w04_') if p == 'README.md' else summary
    (ROOT/p).write_bytes(prefix.encode('utf8') + original)

ledger = {PREFIX+'/'+n for n in ('final.pending-files.md','final.files.json','final.audit.json')}
for n in ('final.pending-files.md','final.files.json','final.audit.json','diff-check.txt'):
    (HERE/n).touch(exist_ok=False)
diff = git('diff','--check')
write('diff-check.txt', 'exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr)
paths = sorted(set(old['paths']) | {p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()})
assert not set(paths) & set(prior['retained'])
hashes = {p:sha(p) for p in paths if p not in ledger}
write('final.pending-files.md', '# D-091 精确提交清单\n\n累计'+str(len(paths))+'项＝原227项＋本次新增'+str(len(paths)-227)+'项。八份共享文档在原227项内，本次只前置验收记录，不重复计数；D-085等历史原文保留，D-085独有文件及70份保留材料仍排除。\n\n[70项排除及hash](exclusions.json)；[验收范围](acceptance-report.md)。下面为工作树原字节SHA256，暂存须逐blob核对；不自动规范化原始日志。三份互引清单自身不做循环hash，审计记录其余最终hash。\n\n| 路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+hashes.get(p,'SELF_REFERENTIAL_MANIFEST')+'` |' for p in paths)+'\n')
save('final.files.json', dict(count=len(paths), paths=paths, hashes=hashes, self_reference_exclusions=sorted(ledger)))
broken=[]; secrets=[]; suspect=[]
pattern=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
for p in paths:
    content=(ROOT/p).read_text(encoding='utf8',errors='replace')
    if pattern.search(content): secrets.append(p)
    if any(x.lower() in ('__pycache__','temp','sandbox','dist','build','.venv') for x in pathlib.PurePosixPath(p).parts) or pathlib.Path(p).suffix.lower() in ('.pyc','.whl','.zip','.exe'): suspect.append(p)
    if p.startswith(PREFIX) and p.endswith('.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',content):
            ref=unquote(ref.split('#')[0].strip('<>'))
            if ref and not ref.startswith(('http:','https:','mailto:')) and not (ROOT/p).parent.joinpath(ref).exists(): broken.append([p,ref])
suffix={}
for p in SHARED:
    prefix=summary.replace('](w04_', '](docs/project_memory/w04_') if p=='README.md' else summary
    suffix[p]=hashlib.sha256((ROOT/p).read_bytes()[len(prefix.encode('utf8')):]).hexdigest()==baseline['delivery'][p]
working=set(lines('ls-files','-m','-o','--exclude-standard'))
audit=dict(at_utc=now(),decision='D-091',stage='W04-3 ACCEPTED; W04 IN_PROGRESS; W04-4 NOT_STARTED',head=EXPECTED,
    source_count=len(source),source_fingerprint=snap['fingerprint'](snap['source']()),source_unchanged=snap['source']()==source,
    original_delivery_changes_outside_shared=[p for p,h in baseline['delivery'].items() if p not in SHARED and sha(p)!=h],
    shared_history_suffix_preserved=suffix,
    protected_counts={k:len(v) for k,v in prior['protected'].items()},
    protected_mismatches={k:[p for p,h in v.items() if sha(p)!=h] for k,v in prior['protected'].items()},
    planning_mismatches=[p['archivePath'] for p in prior['planning'] if sha(p['archivePath'])!=p['archiveSha256']],
    formal_tree_exact=formal==set(prior['protected']['formalFiles']),
    retained_count=len(prior['retained']),retained_mismatches=[p for p,h in prior['retained'].items() if sha(p)!=h],
    missing_links=broken,high_confidence_secret_findings=secrets,suspect_artifacts=suspect,
    sensitive_scan_scope='Bounded credential/private-key patterns, not a universal detection guarantee; synthetic TEST evidence retained.',
    diff_check_exit=diff.returncode,diff_check_evidence='diff-check.txt',
    old_test_count=1909,new_test_count=14,test_count=1923,test_identity_evidence='../w04_3_repair_evidence/frozen-source-01.json',
    tests_executed_this_turn=False,test_results_referenced=audit_old['runs'],actual_remote_precommit=remote.stdout.strip(),
    workflow_paths=lines('ls-files','.github/workflows'),ci='NO_REMOTE_RUN_OR_CHECK_RESULT_OBTAINED',
    delivery_count=len(paths),delivery_paths=paths,delivery_hashes_excluding_audit={p:sha(p) for p in paths if p!=PREFIX+'/final.audit.json'},
    unexpected_paths=sorted(working-set(paths)-set(prior['retained'])),missing_paths=sorted((set(paths)|set(prior['retained']))-working),
    staged_before=lines('diff','--cached','--name-only'),git_writes_at_this_audit=False,
    intended_staging='Exact manifest paths; command-level core.autocrlf=false; verify all index blobs byte-for-byte before commit',
    historical_warnings='Original logs/whitespace and LF/CRLF notices preserved; staged checks recorded separately before commit.')
save('final.audit.json',audit)
assert all(not audit[k] for k in ('original_delivery_changes_outside_shared','planning_mismatches','retained_mismatches','missing_links','high_confidence_secret_findings','suspect_artifacts','unexpected_paths','missing_paths','staged_before'))
assert all(suffix.values()) and all(not v for v in audit['protected_mismatches'].values()) and audit['source_unchanged']
print(json.dumps({k:audit[k] for k in ('decision','source_fingerprint','delivery_count','retained_count','diff_check_exit','workflow_paths')},ensure_ascii=False))
