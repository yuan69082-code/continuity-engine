"""D-093 documentation only; verify reviewed bytes before adding acceptance records."""
import datetime, hashlib, json, os, pathlib, re, runpy, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
REPAIR = ROOT / 'docs/project_memory/w04_4_review_repair_evidence'
REVIEW = pathlib.Path('C:/Users/Administrator/Documents/Codex/2026-09-24/continuity-engine-2026-09-24-continuity-4/reviews/w04_4_d092_repair_readonly_review_20261002.json')
HEAD = 'c910be8ff65f1384c4942c980fc4087c1b595a87'
FP = 'sha256:d77fb9e525eae8bd5d09796db3703029ce3e759ca0eee9207db52f1347ab596c'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(pathlib.Path(path).read_text(encoding='utf-8-sig'))
def git(*args): return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT).decode('utf8')
def put(name, value):
    with (HERE / name).open('x', encoding='utf8', newline='\n') as out:
        out.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')

manifest = read(REPAIR/'final.files.json'); old_audit = read(REPAIR/'final.audit.json')
frozen = read(REPAIR/'frozen-source-final-02.json'); review = read(REVIEW)
snapshot = runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
source = snapshot['source']()
assert source == frozen['source'] and snapshot['fingerprint'](source) == FP
assert git('branch', '--show-current').strip() == 'main'
assert git('rev-parse', 'HEAD').strip() == git('rev-parse', 'origin/main').strip() == HEAD
assert git('remote', 'get-url', 'origin').strip() == 'https://github.com/yuan69082-code/continuity-engine.git'
assert not git('diff', '--cached', '--name-only').strip()
assert all(sha(ROOT/p) == h for p, h in manifest['hashes'].items())
assert all(sha(ROOT/p) == h for p, h in manifest['retained'].items())
assert all(sha(ROOT/p) == h for rows in old_audit['protected'].values() for p, h in rows.items())
assert all(sha(ROOT/p) == h for p, h in old_audit['planning'].items())
decisions = (ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf8')
assert max(map(int, re.findall(r'D-(\d{3})', decisions))) == 92 and 'D-093' not in decisions
paths = set(filter(None, (git('diff', '--name-only', '-z') + git('ls-files', '--others', '--exclude-standard', '-z')).split('\0')))
prefix = HERE.relative_to(ROOT).as_posix() + '/'
assert {p for p in paths if not p.startswith(prefix)} == set(manifest['paths']) | set(manifest['retained'])
assert review['source_fingerprint'] == FP and review['conclusion'].startswith('NO_NEW_BLOCKING_FINDINGS')

remote_command = ['git', '-c', 'http.sslBackend=openssl', 'ls-remote', 'origin', 'refs/heads/main']
remote = subprocess.run(remote_command, cwd=ROOT, capture_output=True)
remote_record = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), command=remote_command,
                     exit_code=remote.returncode, stdout=remote.stdout.decode('utf8'), stderr=remote.stderr.decode('utf8'))
put('remote-before.json', remote_record)
assert remote.returncode == 0 and remote_record['stdout'].split() == [HEAD, 'refs/heads/main']

shared = read(REPAIR/'baseline.json')['shared_hashes']
baseline = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), decision='D-093', head=HEAD,
    branch='main', source=source, source_fingerprint=FP, source_count=len(source),
    reviewed_paths=manifest['paths'], reviewed_hashes={p:sha(ROOT/p) for p in manifest['paths']},
    retained=manifest['retained'], protected=old_audit['protected'], planning=old_audit['planning'],
    shared_hashes={p:sha(ROOT/p) for p in shared}, index_hash=sha(ROOT/'.git/index'),
    review_original=str(REVIEW), review_original_sha256=sha(REVIEW), review_copy='independent-readonly-review.json',
    remote_before=remote_record, test_ids=frozen['test_ids'], tests_executed_this_turn=False,
    git_writes_at_baseline=False, retained_count=70, reviewed_count=496)
put('baseline.json', baseline)
with (HERE/'independent-readonly-review.json').open('xb') as out: out.write(REVIEW.read_bytes())
assert sha(HERE/'independent-readonly-review.json') == sha(REVIEW)
put('exclusions.json', manifest['retained'])
selected = read(REPAIR/'selected-runs.json')
refs=[]
for label in selected['final']:
    r=read(REPAIR/(label+'.json'))
    assert r['status']=='COMPLETED' and r['exit_code']==0 and r['hash_before']==r['hash_after']==FP
    match=re.search(r'Ran (\d+) tests? in ([0-9.]+)s\s+OK(?: \(skipped=(\d+)\))?\s*$',(REPAIR/(label+'.stderr.log')).read_text(encoding='utf8'))
    assert match
    total=int(match[1]); skip=int(match[3] or 0)
    refs.append(dict(label=label, total=total, passed=total-skip, skipped=skip, failures=0, errors=0,
        exit_code=0, test_seconds=float(match[2]), controller_seconds=r['duration_seconds'],
        hash_before=r['hash_before'], hash_after=r['hash_after'], command=r['command'],
        evidence={suffix:sha(REPAIR/(label+suffix)) for suffix in ('.json','.stdout.log','.stderr.log')}))
assert [(r['passed'],r['skipped']) for r in refs]==[(17,0),(215,0),(1144,1),(1990,1)]
put('test-references.json', dict(source_fingerprint=FP, source_count=332, test_count=1991,
    results=refs, reference_only=True, reviewer_ran_engine=False, current_turn_ran_tests=False,
    overlapping_not_added=True, ci='NOT_VERIFIED'))

report=f'''# D-093：W04-4 与 W04 包级正式验收

2026-10-02（Asia/Shanghai）用户正式验收 W04-4 初版、R1/R2 返修及 W04 包级贯通，并授权现有 Engine main 精确暂存、一次普通提交和向既有 origin/main 普通 push。本文件登记验收事实；提交和推送结果在操作后另行核验，不预填成功。

**W04-4 = ACCEPTED；W04 整体 = ACCEPTED。** W04-1/D-087、W04-2/D-089、W04-3/D-091 历史验收保持，D-092仍是开工及施工记录。W05未开工，本授权不延伸到后续阶段。权威规划仍为总施工v1.6、最终新增v1.6、长期能力v6.10；本次不是规划变更或生产开放。

## 依据与覆盖

独立依据为[规划窗口只读复核原字节副本](independent-readonly-review.json)，原件/副本SHA-256为 `{sha(REVIEW)}`；原路径及归档身份见[开工基线](baseline.json)。规划窗口只读检查代码、原始输出、源码与测试身份、清单和保护范围，没有运行Engine测试，也不保证不存在其他缺陷。

本次覆盖N15/N16跨入口身份和具体事项、原生API/模拟UI自主续问与回复回流、转用与派生来源、投递事实和UNKNOWN、新询问与原发送重试、统一联系暂停、恢复；覆盖N10/N21跨入口历史锚点、模拟身体与工具/查询链在四批同版上的因果贯通。T33—T40/T42及适用T18/T26—T32/T41/T60/T72/T85—T87，C01—C15的本包适用内部边界见[验收矩阵](acceptance-matrix.md)。T66/T67只验W04查询契约，不把W05自然记忆/人格/梦境联动算作完成。

|同版施工方实跑（本轮仅引用）|PASS|SKIP|FAIL/ERROR|退出码|unittest秒|
|---|---:|---:|---|---:|---:|
|lineage-prefix-repair-09（新增16+原包级1）|17|0|0/0|0|277.089|
|w04-final-02|215|0|0/0|0|904.839|
|public-final-02|1144|1|0/0|0|1605.812|
|full-final-02（共1991）|1990|1|0/0|0|2460.921|

四组运行前后均绑定332项源码/测试/资源 `{FP}`；原1975测试身份及旧测试文件保留，新增16。集合交叠不能相加。Windows1314 SKIP不算PASS。[原始证据索引](../w04_4_review_repair_evidence/test-index.md)和[本次引用核对](test-references.json)记录命令、退出码、时长及原件hash。本轮没有修改实现/正式测试，也没有重新运行测试；没有远端CI通过证据。

## 已知阻断的关闭依据

|事项|证据与处置|当前验收结果|
|---|---|---|
|R1：A私有列表值被B末次写入掩盖来源；原生/间接状态来源漏检|counterexamples-before-01有效反例；按原FieldChanges/Event/ThinkSession实际片段重建逐值来源，APPEND/SET保留旧来源；lineage-prefix-repair-09及同版四组验证最终Context/表达、重开和合法B对照；独立复核R1已解决|本批已知阻断关闭|
|R2：最后设备观察/剩余回调后入口许可未重核|counterexamples-before-01、binding-before-02有效反例；原port持锁最终guard内末端入口核验及控制文档再读；三类观察交错和剩余回调零效果/零费用，正常对照1/1；独立复核R2已解决|本批已知阻断关闭|
|此前原生Event/Memory派生转用、P13精确确认及C1投递顺序|原D-092用户授权与修前失败保留，原矩阵对应实现、原正常API/UI链及同版全量被本次复核和验收覆盖|本批现行等待复核关闭，不倒改旧待批准记录|
|补修中的过度过滤与重复来源展开超时|全部中间ERROR及逐站诊断保留；当前投影只核所需分区，同一读取内复用已验证历史来源前缀；当前字节、完整校验和每次权限复查不省略；同版原包级/新增边界/专项/全量通过|当前已复核负载阻断关闭；不宣称无界负载永不超时|

当前本批 **EVIDENCE_CONFLICT=NONE / PLANNING_CONFLICT=NONE**，仅表示上述已知验收阻断闭合，不清除旧时点PRESENT、不保证没有其他缺陷。历史F1/H1/F2仍UNKNOWN；原FAIL/ERROR、辅助错误、中断、重度剖析超时、行尾提示及SKIP原样保留。原初版/返修报告和矩阵保留原状态，本次验收矩阵是新的当前结果。

## 保持的边界与未完成事项

原1000毫秒回忆限制、2048上下文预算、P18调度及控制、当前权限/费用/回执、Subject Authority及内部认知与现实行动边界不变。旧Context失效继续拒绝，不自动重绑；真正UNKNOWN不盲目重放。未知结构化来源采用保守核验，不能证明的材料不升格为可读事实。

验收仅限本机隔离TEST和明确交错；不是任意平台、真实模型语义、无界历史负载、生产性能或任意并发撤权保证。W05、W06、P19完整页面、P20/P21正式恢复和运行权、P22真实账号/设备/服务及P23总验收仍待各自授权；没有新增生产能力。

## 精确归档与Git范围

以已核对496项交付为起点，仅新增本目录验收材料、八份共享档案顶部验收记录。旧报告/原始日志不改；共享档案完整旧字节作为后缀保留。70份保留材料继续排除，含D-085独有规划档案/现行规划索引，不声称这些本地文件已推送。63项保护文件、三份规划原文、七份正式数据和版本不动。

[最终逐路径清单](final.pending-files.md) · [逐文件hash](final.files.json) · [排除清单](exclusions.json) · [终局审计](final.audit.json)。原件、源码、测试及保护范围以审计实测为准。按明确路径暂存，使用命令级core.autocrlf=false保留Git blob与工作树原字节，不修改全局配置或改写原日志消除格式提示。

实际远端开工查询见[remote-before.json](remote-before.json)：单次OpenSSL后端，证书验证保持，main为{HEAD}。提交前再次查询；普通提交和push后的实际结果在独立本地核验记录及最终回复中报告，不冒称已包含在这次提交内。完成后停止，不W05。
'''
put('acceptance-report.md',report)

matrix=['# D-093 正式验收矩阵','',
    'Planning Item → Code Change → Test → Acceptance Result。由用户本次正式验收；以下新表不覆盖原初版和返修矩阵。施工方同版实跑引用，规划窗口未独立运行测试。','',
    '## W04-4及包级','', '|Planning Item|Code Change / 原权威链|Test / 已核验证据|Acceptance Result|','|---|---|---|---|']
for line in (ROOT/'docs/project_memory/w04_4_evidence/final-matrix.md').read_text(encoding='utf8').splitlines():
    if line.startswith('|') and 'IMPLEMENTED_NOT_ACCEPTED' in line:
        matrix.append(line.replace('IMPLEMENTED_NOT_ACCEPTED','ACCEPTED'))
matrix += ['', '## R1/R2逐项补修','', '|Planning Item|Code Change|Test / 已核验证据|Acceptance Result|','|---|---|---|---|']
for line in (REPAIR/'matrix.md').read_text(encoding='utf8').splitlines():
    if line.startswith('|') and 'IMPLEMENTED_NOT_ACCEPTED' in line:
        matrix.append(line.replace('IMPLEMENTED_NOT_ACCEPTED','ACCEPTED'))
matrix += ['', '上表原初版测试在最终修补版W04专项及全量中再次覆盖；不拼接不同源码PASS。当前四组为17 PASS、215 PASS、1144 PASS/1 SKIP、1990 PASS/1 SKIP，均退出0，集合不相加。', '',
    'W04-1/D-087、W04-2/D-089、W04-3/D-091历史验收不改；W04-4及W04包级ACCEPTED。W05未开工；P19—P23后置能力不冒称完成。', '',
    '[原初版矩阵](../w04_4_evidence/final-matrix.md) · [原返修矩阵](../w04_4_review_repair_evidence/matrix.md) · [原始测试](../w04_4_review_repair_evidence/test-index.md) · [同版引用核对](test-references.json) · [验收范围与限制](acceptance-report.md)', '']
put('acceptance-matrix.md','\n'.join(matrix))

marker='<!-- W04_ACCEPTED_D093_20261002 -->'
for p in shared:
    file=ROOT/p; old=file.read_bytes(); assert sha(file)==baseline['shared_hashes'][p]
    link=('docs/project_memory/' if p=='README.md' else '')+'w04_4_acceptance_evidence/'
    text=f'''{marker}
## D-093：W04-4 初版、R1/R2 及 W04 包级正式验收

2026-10-02用户明确正式验收并授权精确暂存、现有main一次普通提交及既有origin/main普通push。**W04-4=ACCEPTED；W04整体=ACCEPTED**。D-092开工记录、前三批D-087/D-089/D-091、W02/W03及P00—P18历史验收保持。W05未开工，不自动进入后续阶段。

规划窗口完成代码、原始输出、身份和清单的独立只读复核，未运行Engine测试。本次归档引用施工方同版定向17PASS、W04专项215PASS、公共1144PASS/1SKIP、全量1990PASS/1SKIP，均0FAIL/ERROR、退出0，集合交叠不相加。源码332项`{FP}`，原1975测试保留、新增16；本轮不改实现/测试、不重跑。

R1按原字段变更及Event/ThinkSession保留逐值/原生派生来源；R2在最后观察及剩余回调后重核入口许可。修前真实失败、修后最终Context/表达、零效果/零费用及正常对照、同版兼容/全量、规划窗口只读结论与用户确认共同支持本批已知阻断关闭。当前本批EVIDENCE_CONFLICT=NONE、PLANNING_CONFLICT=NONE，不保证无其他缺陷。旧PRESENT和失败历史不改，F1/H1/F2仍UNKNOWN。

原1000ms、2048预算、调度/权限/费用/持续运行边界保持；失效旧Context不自动重绑。验收仅本机隔离TEST，不保证无界负载、真实语言质量、任意生产并发撤权或真实平台性能。Windows1314 SKIP、辅助错误、中断、重度剖析超时及行尾提示照留，无远端CI PASS证据。生产服务/账号/设备未开放；W05/W06及P19—P23待各自授权。

[验收报告]({link}acceptance-report.md) · [逐项验收矩阵]({link}acceptance-matrix.md) · [测试引用]({link}test-references.json) · [精确清单]({link}final.pending-files.md) · [审计]({link}final.audit.json)。70份保留材料（含D-085独有规划及现行索引）继续排除，不冒称已推送；共享档案旧字节后缀保持。提交/push尚须实际操作后核验，不预填成功。以下均为历史时点，原正文保留。

'''
    file.write_bytes(text.encode('utf8')+old)
print(json.dumps({'decision':'D-093','acceptance':'W04-4 and W04 ACCEPTED','source':FP,'review_hash':sha(REVIEW),'shared_updated':list(shared)},ensure_ascii=False))
