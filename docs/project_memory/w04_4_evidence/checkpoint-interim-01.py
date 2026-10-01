"""Document the partial W04-4 stop point; no Engine execution or Git mutation."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
BASE = json.loads((HERE / 'baseline.json').read_text(encoding='utf8'))
SNAP = runpy.run_path(str(ROOT / 'docs/project_memory/w02_b_evidence/snapshot.py'))
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT)


def put(name, text):
    with (HERE / name).open('x', encoding='utf8', newline='\n') as stream:
        stream.write(text)


def json_put(name, value):
    put(name, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def append(name, text):
    with (HERE / name).open('a', encoding='utf8', newline='\n') as stream:
        stream.write('\n' + text + '\n')


assert not (HERE / 'interim.audit-01.json').exists(), 'Unique checkpoint label required'
source = SNAP['source']()
fingerprint = SNAP['fingerprint'](source)
assert fingerprint == 'sha256:7f6ed84a73215ccac21d6a4c2b1578a36970943f51952fa83bd25891a56fc34b'
raw = {p.name: sha(p) for p in HERE.iterdir()
       if p.name.endswith(('.stdout.log', '.stderr.log')) or
       (p.suffix == '.json' and 'command' in json.loads(p.read_text(encoding='utf8')))}
json_put('interim.raw-records-01.json', {'at_utc': NOW, 'hashes': raw})

explanations = {
    'before-entry-01': '辅助脚本误用 str 代替 Path；非 Engine 缺陷，未进入目标链。',
    'before-entry-02': '修前旧 C1 不接受 entry_message 的真实入口缺口证据；诊断退出0不等于正式测试PASS。',
    'entry-draft-01': '新增入口检查重复工作触发 RECALL_TIMEOUT；1 ERROR，原1000ms未改。',
    'entry-profile-01': '有开销的 cProfile 定位环境配置重复读取；unittest 1 ERROR，包装进程0不得算PASS。',
    'entry-draft-02': 'TEST fixture 未接入既有 expression.emit 授权视图；1 ERROR，后来补接但原件保留。',
    'entry-draft-03': 'C1完成核验报 C1_ACTION_HISTORY_WITH_DENIED_EXPRESSION；1 ERROR。未保存当次效果计数正文，不能把路径推断冒充直接计数。',
    'entry-scope-01': '3项中2 PASS/1 ERROR：跨入口第二轮 RECALL_TIMEOUT，旧结果不覆盖当前版本。',
    'scope-profile-01': '有开销的 cProfile 定位原操作日志重复完整解析；unittest 1 ERROR，包装进程0非PASS。',
    'scope-02': '第二轮仍 RECALL_TIMEOUT，1 ERROR；保留该次优化不足的证据。',
    'scope-light-01': '轻量计时诊断；回忆准备794.51ms/检索11项，非全链时间，也不是最终版专项PASS。',
    'independent-scope-01': '本施工窗口实跑8/8 PASS；标签指不依赖冲突项的集合，不是规划窗口独立实跑。',
    'confirmation-conflict-01': '诊断未到目标路径；异常被诊断捕获故退出0，不能计PASS。',
    'confirmation-conflict-02': '诊断记录 NamedTemporaryFile/FileNotFoundError，未到模型，未证明唯一原因；不能计PASS。',
    'confirmation-conflict-03': '短TEST根路径到达目标：精确确认true，Action approved/require-confirmation均true，P13仍PLATFORM_DENIED；新增守卫下模型1次、A/B效果及费用均0。是冲突证据，不是通过测试。',
    'compatibility-interim-01': '施工窗口153/153 PASS，unittest278.354秒；中间兼容，不是最终全套兼容或全量。',
}
runs = []
for path in sorted(HERE.glob('*.json')):
    record = json.loads(path.read_text(encoding='utf8'))
    if 'command' not in record:
        continue
    label = path.stem
    stderr = (HERE / (label + '.stderr.log')).read_text(encoding='utf8')
    runs.append({k: record.get(k) for k in ('label', 'status', 'command', 'started_utc',
        'exit_code', 'duration_seconds', 'hash_before', 'hash_after')} | {
        'test_summary': re.findall(r'Ran \d+ tests? in [^\r\n]+|FAILED \([^\r\n]+|^OK$', stderr, re.M),
        'classification': explanations[label],
        'matches_current_source': record.get('hash_before') == fingerprint == record.get('hash_after'),
        'record': path.name, 'stdout': label + '.stdout.log', 'stderr': label + '.stderr.log'})
json_put('interim.test-index-01.json', {'source': fingerprint, 'runs': runs,
    'no_total_summing': True, 'final_full_regression': 'NOT_STARTED'})
lines = ['# W04-4 中间测试索引（不是最终交付）', '',
         '全部为施工窗口本轮实跑/诊断，未取得规划窗口独立实跑或远端CI结果。各集合不得相加。完整命令、源码前后身份和原始输出见同名JSON及日志。', '',
         '| 标签 | 退出码 | 外层耗时秒 | 当前源码匹配 | 真实结论 |', '|---|---:|---:|---|---|']
for record in runs:
    label = record['label']
    lines.append(f"|[{label}]({label}.json)|{record['exit_code']}|{record['duration_seconds']}|{record['matches_current_source']}|{record['classification']}|")
lines += ['', '源码仍是开发中间版；8项及153项通过不代表W04-4完成。API/UI主动联系完整链、包级贯通及最终全量尚未完成。', '']
put('interim.test-index-01.md', '\n'.join(lines))

put('interim-report-01.md', '''# W04-4 中间进度与待确认冲突

2026-09-29，D-092施工继续有效；本文件不是完成交付。W04-4 IN_PROGRESS；N16相关项 BLOCKED / PLANNING_CONFLICT；W04包级贯通尚未完成。EVIDENCE_CONFLICT=PRESENT。D-091及前三批验收不改。

## 当前已完成的局部工作

在原Environment绑定配置和C1操作日志加入可选、版本化入口元数据；区分用户与主体发送账号，保存具体入口和转用范围；沿原Router/Composer加入当前读取核验和来源投影。原请求、Thinking、SubjectState、Event和E5-A仍是权威。旧入口不传新字段时维持旧接线。

新增DeviceCommand消息投递类型接到原P17/E5-A及W04-2隔离Fake设备，实际模拟API/UI动作、回执和费用仍沿原路径。尚不能据此宣称两条完整主动联系链通过。

8项新正式反例/对照通过：错误账号、镜像去重、受限A材料与合法B材料分离、配置副本隔离与坏字节拒绝、当前权限重验、主体回显不当用户回复、重开只读查询、不在线及过期拒绝。153项选定旧兼容通过。都不是整批完成或最终全量。

新增检查曾导致两轮回忆超时，原1000ms未改。依据重复读取/解析诊断，环境配置只复用完全相同当前字节的已验证解析结果，仍检查路径、重新读取字节、返回独立副本；原操作/能力日志仅复用既有按当前字节核验的受控读取范围，不缓存授权。轻量测量与剖析开销分开，不能保证更大负载或真实环境性能。

## N16必须先决定的公共接线冲突

原要求是主体在现有有效授权内，经原Thinking/P08/P13形成新表达并合法投递。真实隔离入口中Action的CONTACT_USER保留requires_confirmation=True；本次精确表达确认已为True，但P13仍直接据该标记判PLATFORM_DENIED。普通C1非mind分支先after_action、后compose表达，完成恢复检查随后报C1_ACTION_HISTORY_WITH_DENIED_EXPRESSION。

直接证据：[confirmation-conflict-03](confirmation-conflict-03.stdout.log)。这里已加W04-4自身的投递前原P13拒绝预检，模型1次、A/B模拟效果0、费用0。公共P13尚未修改。早期[entry-draft-03](entry-draft-03.stderr.log)只保存异常栈及清理前文件哈希，没有独立的效果计数正文；它证明执行/完成判定不一致，不能将“路径推断有一次发送”写成当次直接观测计数。

建议在 services/expression_policy_service.py 修正decide及verify：识别本次精确确认是否满足必要条件，仍核验原Action拒绝、当前权限、资源、Reality、Context及生命周期；历史拒绝不自动变成授权。services/continuity_interaction_service.py 对相关新入口在外部投递前形成并核验表达，不覆盖原内部独立提交及事实恢复。新增正常/无确认/撤权/回执丢失/已执行不重发及旧C1/P13/自主性兼容。

这会改变公共确认判定与执行顺序，已按用户冲突规则请求确认；未获答复前不实施。替代为继续保持本项BLOCKED。不能关闭表达策略、清掉原requires_confirmation、假称普通回答或放开所有联系。

## 尚未完成，不能用局部通过代替

- API/UI完整A提问→主体自主决定续问→B新表达→B回复→原事项闭环，包含多话题和必要澄清。
- 当前开发夹具的SUBJECT_CONTINUATION仍经user_message形式，不能证明自主唤起。必须接回原Native Wake/Thinking/P18路径，不能将主体自己的思考伪装成用户新消息；现有草稿不是满足该要求的证据。
- 已发送/送达/已读的外部证据提升；当前只读投影能保守显示SENT/NO_EVIDENCE，尚未覆盖全部状态。
- 旧发送UNKNOWN下合法独立新询问，以及未知付款等不可伪装新询问。P17原未确认同资产阻断是待验证风险，目前未正式复现，不能称为已定位缺陷。
- 群聊、跨时区迟到、A/B并发、断线队列、故障后按原事实恢复，以及所有入口/派生材料/历史回查的转用与当前权限交错验证。
- 身体更换、工具等待及历史查询的四批因果包级贯通，同固定最终源码专项/公共兼容/完整回归。

## 公共影响与保护

具体文件职责见[追加范围](stage-brief.md)，路径和哈希见[中间清单](interim.pending-files-01.md)。开发中修改与既有70份保留材料单列；不修改规划、冻结接口、正式七文件、63项保护和旧正式测试。旧源码变更仍需最终回归，当前兼容只证明所列集合。

测试进程已结束；2026-09-28T18:58:27.7243308Z的只读CIM快照中Python进程0。没有强制终止；TEST数据由测试控制器清理，失败先保存既有fixture摘要。历史辅助错误、超时、FAIL/ERROR及退出0但未到目标的诊断全部保留。

F1/H1/F2 UNKNOWN、Windows1314 SKIP历史、P19/P20—22/W05后置边界保留。未接真实服务/账号/设备，未验收、暂存、提交、push或启动W05，未取得远端CI结果。

恢复入口：[continuation.md](continuation.md)。先核源码、清单、进程和用户对冲突的决定，不重跑已完成中间结果充当最终结果。
''')

append('planning-conflict-n16-01.md', '''## 补充核验与证据口径校正（2026-09-29）

原段“先产生一次模拟发送”是从执行/完成路径推断，entry-draft-03仅存栈及文件摘要，未保存计数正文；不应表述成当次直接测得一次效果。该原描述保留，本段明确收窄其证据结论，不改原始日志。

confirmation-conflict-03在当前版直接记录：Action approved=True、requires_confirmation=True、精确表达确认=True、P13 PLATFORM_DENIED；新入口投递前预检使两端效果及费用均0。前两次confirmation诊断未到目标，不计PASS。详见interim-report-01及完整测试索引。

建议修改范围包含P13 decide/verify历史与当前校验、C1相关入口的表达先于外部派发；原拒绝、独立内部成长及旧事实恢复需保留。公共P13尚未改，等待用户明确决定。
''')

append('stage-brief.md', '''## 2026-09-29实际开发范围与停点（保留上方开工快照）

实际新增：domain/cross_entry.py（入口/角色/来源绑定值对象），services/cross_entry_service.py（原链入口与转用/投递绑定及只读投影），services/entry_context_source.py（原SubjectState按当前入口授权投影，无第二状态存储），testing/w04_cross_entry_fixture.py（隔离外界/确定性模型输入），tests/test_w04_4_continuity.py（13项开发中测试）。

实际修改：domain/device_operation.py、integration_results.py（旧字段兼容的内部可选元数据）；storage/json_environment_repository.py（沿原环境配置持久绑定/联系设置，同当前字节解析复用不缓存授权）；json_integration_repository.py（原操作身份绑定及最小投影）；services/continuity_core_service.py、continuity_core_runtime.py、continuity_interaction_service.py（可选入口接线）；device_operation_service.py（原P17投递当前性及效果核验）；input_context_source.py（原输入来源投影）；unfinished_item_service.py（仅启用新入口时沿原授权/Context支持input根）；testing/w04_device_fixture.py（模拟发送操作）。未使用的候选文件不要求修改。

这些公共变化均仍为开发版，旧正式测试文件字节保持，已实跑153项选择兼容但最终回归未做。冻结external Schema、原63保护/正式7/规划/版本/70保留不动。

新增冲突：N16为BLOCKED / PLANNING_CONFLICT，理由与请求修改范围见planning-conflict-n16-01.md。原P13表达策略尚未改；C1仅有已授权入口字段接线，尚未改表达/派发顺序。API/UI完整主动链和包级集成不得报告IMPLEMENTED_NOT_ACCEPTED或PASS。
''')

append('matrix.md', '''## 2026-09-29中间核验（不覆盖开工矩阵）

| Planning Item | Code Change（实际） | Test / 原始证据 | Acceptance Result |
|---|---|---|---|
|N15/T33入口身份与自发自收|cross_entry + 原C1/Environment可选元数据|independent-scope-01账号/镜像/回显通过；群聊完整正反尚缺|IN_PROGRESS|
|N15/T35具体事项|原unfinished_item增加当前合法input根，entry关联草稿|主动联系前置被P13冲突阻断；native续接未完成|IN_PROGRESS，依赖N16 BLOCKED|
|N15/T36转用|EntryPermission/InputContextSource/原状态投影|8项集中的受限A与合法B对照通过；全派生/历史/UI和交错仍缺|IN_PROGRESS|
|N16/T34新表达|原P08/P13/P17接线，新增入口拒绝预检|entry-draft-03 ERROR；confirmation-conflict-03直接确认冲突且守卫效果/费用0|BLOCKED / PLANNING_CONFLICT|
|N16/T37路线替代|原DeviceCommand/DeviceOperation及Fake发送草稿|API/UI完整主动链未完成|BLOCKED（同上）|
|N15/T38三类时间、同源|EntryMessage及原输入记录|镜像/主体回显正反通过；迟到时区/并发未完成|IN_PROGRESS|
|N15/T39/T18恢复|原请求元数据绑定、最小只读投影|重开只读通过；副作用恢复与并发未完成|IN_PROGRESS|
|N16/T40投递与新问|E5-A只读投影及原结果事实|SENT/NO_EVIDENCE有限对照；送达/已读与UNKNOWN独立新问未完成|IN_PROGRESS，依赖N16 BLOCKED|
|N16/T42统一暂停|新入口沿原当前权限，用户级联系暂停配置|有效完整联系前置未通过，不能认定该项完成|IN_PROGRESS|
|N10/N21及包级|本批入口草稿，前三批原实现保持|153旧兼容PASS不等于包级；新因果贯通未完成|NOT_STARTED（包级正式验证）|
|C06/T43/T25/T45|inspect只读+原费用回执、计时证据|8项集中重开只读通过；轻量794.51ms只覆盖当次回忆准备|IN_PROGRESS|

各项均未验收；8项与153项是施工窗口实跑且集合不可累计成最终总数；原1923项旧身份由旧测试文件逐字节保留核对，当前新增13项并非13项全部通过。
''')

append('continuation.md', '''## 最新安全停点：2026-09-29（上文是开工历史）

当前不是“无源码修改/无测试”，而是已形成16份源码/测试改动的开发版；当前指纹 sha256:7f6ed84a73215ccac21d6a4c2b1578a36970943f51952fa83bd25891a56fc34b，共326份源码/测试/资源。原321路径均保留，旧测试文件不变，新增test_w04_4_continuity.py 13项。

完成证据：independent-scope-01 8 PASS（施工窗口，不是独立复核）；compatibility-interim-01 153 PASS/退出0/279.081秒外层，前后hash同当前。会话83610已取回最终退出码，不盲目续接。2026-09-28T18:58:27.7243308Z CIM显示Python0，不留本轮后台进程。

N16遇PLANNING_CONFLICT并已通过异步问题请求用户确认P13/C1两处公共判定/顺序修补；截至本记录尚无答复。不要将一般施工授权代替该待决修改。其他8项边界已取证；尚未完成内容见interim-report-01。未跑最终全量，无包级通过证据。

恢复时先核用户决定、interim.audit-01.json及interim.files-01.json、当前源hash、Git和进程。若批准，则在原P13/C1职责内最小修补并覆盖decide/verify当前与历史，保留旧拒绝和独立内部提交；不能绕过CONTACT_USER确认。随后补真正native续接、API/UI全链、投递状态、UNKNOWN新询问、权限/恢复及包级集成，固定最终源码再完整专项/兼容/全量。

新证据使用新标签，保留全部旧ERROR/辅助错误/剖析输出。既有1000ms/2048/2need不变。不验收、不暂存/提交/push，不启动W05。
''')

for relative in BASE['shared_hashes']:
    path = ROOT / relative
    is_readme = relative == 'README.md'
    prefix = 'docs/project_memory/w04_4_evidence/' if is_readme else 'w04_4_evidence/'
    text = f'''<!-- W04_4_INTERIM_CONFLICT_01 -->
## W04-4 中间进度：N16表达确认接线待决定

2026-09-29：D-092施工中，W04-4 IN_PROGRESS；N16相关项BLOCKED / PLANNING_CONFLICT，W04包级尚未完成，EVIDENCE_CONFLICT=PRESENT。当前源码326项、指纹7f6ed84a…；施工窗口8项新边界及153项选定旧兼容通过，均为中间验证，最终全量未运行。原P13在精确确认已true时仍按requires_confirmation拒绝，普通C1表达/执行顺序有冲突；新增入口仅作投递前拒绝守卫，A/B效果及费用0的诊断已存。修改公共P13/C1判定与顺序已请求用户决定，尚未实施。

已保存首次ERROR、辅助错误、带开销剖析及安全停点。自主native续接、API/UI完整主动链、完整投递状态、UNKNOWN新询问及四批因果贯通仍未完成。历史D-091等验收、F1/H1/F2 UNKNOWN及Windows1314 SKIP不改。未验收、暂存、提交、push或启动W05，无远端CI结果。

[中间报告]({prefix}interim-report-01.md) · [真实测试索引]({prefix}interim.test-index-01.md) · [矩阵]({prefix}matrix.md) · [清单]({prefix}interim.pending-files-01.md) · [续接]({prefix}continuation.md)。以下保留原开工及历史时点记录，不将旧“尚未运行”等快照冒充现状。

'''
    assert b'W04_4_INTERIM_CONFLICT_01' not in path.read_bytes()
    path.write_bytes(text.encode('utf8') + path.read_bytes())

protected = {group: {p: sha(ROOT / p) for p in items} for group, items in BASE['protected'].items()}
plans = {p['archivePath']: sha(ROOT / p['archivePath']) for p in BASE['planning']}
retained = {p: sha(ROOT / p) for p in BASE['retained']}
history = {p: (ROOT / p).read_bytes().endswith(git('show', 'HEAD:' + p)) for p in BASE['shared_hashes']}
old_tests = {p: source.get(p) == h for p, h in BASE['source'].items() if p.startswith('tests/')}
syntax = {}
for p in source:
    if p.endswith('.py'):
        try:
            ast.parse((ROOT / p).read_text(encoding='utf-8-sig'), filename=p)
        except Exception as exc:
            syntax[p] = {'type': type(exc).__name__, 'line': getattr(exc, 'lineno', None)}
raw_preserved = all(sha(HERE / p) == h for p, h in raw.items())
assert protected == BASE['protected'] and retained == BASE['retained']
assert all(plans[p['archivePath']] == p['archiveSha256'] for p in BASE['planning'])
assert all(history.values()) and all(old_tests.values()) and not syntax and raw_preserved
assert SNAP['source']() == source
assert sha(ROOT / '.git/index') == BASE['index_hash']
assert not git('diff', '--cached', '--name-only').strip()

tracked = git('diff', '--name-only', '-z').decode('utf8').split('\0')
untracked = git('ls-files', '--others', '--exclude-standard', '-z').decode('utf8').split('\0')
paths = sorted(({p for p in tracked + untracked if p}) - set(retained))
artifacts = ['interim.audit-01.json', 'interim.files-01.json', 'interim.pending-files-01.md']
all_paths = sorted(set(paths) | {f'docs/project_memory/w04_4_evidence/{p}' for p in artifacts})
index = ['# W04-4 中间成果清单：非提交授权', '',
         f'共{len(all_paths)}个当前施工路径，另70份保留材料独立排除。尚未完成本批；不得暂存、提交或push。', '',
         '源/测试指纹：`' + fingerprint + '`。逐文件hash见interim.files-01.json。清单文件自身hash不递归；审计文件明确排除自身与清单循环。', '',
         '| 路径 | 归属 |', '|---|---|']
for p in all_paths:
    scope = '共享档案（新记录在前、HEAD历史原字节后缀不变）' if p in BASE['shared_hashes'] else ('源码/测试开发草稿' if p.startswith(('src/', 'tests/')) else 'W04-4新证据/文档')
    index.append(f'|`{p}`|{scope}|')
index += ['', '排除70项详见[exclusions.json](exclusions.json)，全部hash与baseline相同。D-085独有材料及现行规划索引不混称本批成果。', '']
put('interim.pending-files-01.md', '\n'.join(index))

checks = git('diff', '--check').decode('utf8', errors='replace') if False else subprocess.run(
    ['git', '-c', 'core.quotepath=false', 'diff', '--check'], cwd=ROOT,
    capture_output=True, text=True, encoding='utf8')
audit = dict(at_utc=NOW, stage='W04-4 IN_PROGRESS / N16 BLOCKED',
    planning_conflict='PRESENT', evidence_conflict='PRESENT',
    source=source, fingerprint=fingerprint, source_count=len(source),
    head=git('rev-parse', 'HEAD').decode().strip(), branch=git('branch', '--show-current').decode().strip(),
    local_origin=git('rev-parse', 'origin/main').decode().strip(),
    actual_remote={'reference': 'baseline.json#/actual_remote', 'queried_at_baseline_only': True,
                   'not_requeried_for_this_interim': True},
    staged=[], index_hash_unchanged=True, protected_unchanged=True,
    protected_counts={k: len(v) for k, v in protected.items()}, current_plans=plans,
    formal_data_unchanged=True, retained_count=len(retained), retained_unchanged=True,
    old_shared_history_byte_suffix=history, old_test_files_unchanged=old_tests,
    original_test_identities=BASE['test_ids'], original_count=len(BASE['test_ids']),
    new_test_file='tests/test_w04_4_continuity.py', new_test_count=13,
    python_ast_errors=syntax, original_raw_runs_unchanged=raw_preserved,
    source_changed_vs_baseline={p: h for p, h in source.items() if BASE['source'].get(p) != h},
    missing_baseline_source=sorted(set(BASE['source']) - set(source)),
    tracked_paths=[p for p in tracked if p], untracked_paths=[p for p in untracked if p],
    pending_paths=all_paths, pending_count=len(all_paths),
    diff_check={'exit_code': checks.returncode, 'stdout': checks.stdout, 'stderr': checks.stderr},
    process_observation={'checked_at_utc': '2026-09-28T18:58:27.7243308Z', 'method': 'read-only Win32_Process CIM python.exe/pythonw.exe',
        'python_count': 0, 'matching_count': 0, 'terminated_processes': 0},
    tests={'new_selected': '8 PASS', 'selected_compatibility': '153 PASS', 'full': 'NOT_STARTED',
           'source_before_after_match': True, 'no_count_summing': True},
    final_delivery_ready=False, acceptance=False, git_mutations=False, ci='NOT_VERIFIED',
    deferred_checks=['final behavioral/full regression', 'full new-document sensitive/link audit at completion'],
    hashes_exclude_self_and_manifest=True)
json_put('interim.audit-01.json', audit)
manifest = {p: sha(ROOT / p) for p in all_paths if not p.endswith('/interim.files-01.json')}
json_put('interim.files-01.json', dict(at_utc=NOW, paths=all_paths, hashes=manifest,
    self_hash_omitted='docs/project_memory/w04_4_evidence/interim.files-01.json',
    retained=retained, source_fingerprint=fingerprint, not_final_delivery=True))
print(json.dumps({'pending': len(all_paths), 'retained': len(retained), 'source_count': len(source),
    'fingerprint': fingerprint, 'protected_unchanged': True, 'old_tests_unchanged': True,
    'history_unchanged': True, 'diff_check_exit': checks.returncode}, ensure_ascii=False))
