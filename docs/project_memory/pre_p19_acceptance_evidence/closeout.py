"""Documentation-only acceptance and read-only precommit audit; no Git mutations."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REVIEW = Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/pre-p19-supplement-independent-20260920')
OLD = ROOT / 'docs/project_memory/pre_p19_supplement_evidence'
sys.path[:0] = [str(OLD), str(ROOT / 'src')]
from run import source_hashes
from continuity_engine.testing.persistence import tree_inventory_hash


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf8'))
def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, stderr=subprocess.DEVNULL).decode('utf8')
def paths():
    return set(filter(None, (git('diff', '--name-only', '-z') +
        git('ls-files', '--others', '--exclude-standard', '-z')).split('\0')))
def save(name, obj):
    with (OUT / name).open('x', encoding='utf8') as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def prepare():
    supplied = read(OLD / 'final.audit.json')
    protected = read(OLD / 'before.json')
    identity = read(REVIEW / 'identity-audit.json')
    assert git('branch', '--show-current').strip() == 'main'
    assert git('rev-parse', 'HEAD').strip() == identity['head'] == supplied['head']
    assert not git('diff', '--cached', '--name-only').strip()
    assert source_hashes() == supplied['source']
    assert all(h == 'SELF_NOT_HASHED' or sha(ROOT / p) == h for p, h in supplied['pending'].items())
    assert all(sha(ROOT / p) == h for p, h in supplied['excluded'].items())
    assert all(sha(ROOT / p) == h for group in protected['protected'].values() for p, h in group.items())
    self_path = Path(__file__).relative_to(ROOT).as_posix()
    assert paths() == set(supplied['pending']) | set(supplied['excluded']) | {self_path}
    decisions = ROOT / 'docs/project_memory/04_决策记录.md'
    assert 'D-074' not in decisions.read_text(encoding='utf8')
    independent = {n: read(REVIEW / (n + '.json')) for n in ('original-01', 'formal-01', 'extra-01')}
    for n, r in independent.items():
        assert r['engineUnchanged'] and not r['failures'] and not r['errors'] and not r['skips'], n
    docs = ['README.md', *['docs/project_memory/' + n for n in (
        '01_当前状态.md', '03_施工日志.md', '04_决策记录.md', '05_已完成模块.md',
        '06_未完成事项.md', '07_待确认事项.md', 'CHANGELOG.md', '工程总档案.md')]]
    # Existing report/matrix/index bodies remain byte-identical historical records.
    for directory in ('pre_p19_autonomy_evidence', 'pre_p19_supplement_evidence'):
        docs += [f'docs/project_memory/{directory}/{n}' for n in ('final-report.md', 'matrix.md', 'test-index.md')]
    before = {'at': datetime.now(timezone.utc).isoformat(), 'head': supplied['head'],
        'source': source_hashes(), 'sourceHash': supplied['sourceHash'],
        'priorPending': {p: sha(ROOT / p) for p in supplied['pending']},
        'excluded': supplied['excluded'], 'protected': protected['protected'],
        'formalTreeHash': protected['formalTreeHash'], 'pyproject': sha(ROOT / 'pyproject.toml'),
        'index': sha(ROOT / '.git/index'), 'documentBefore': {p: sha(ROOT / p) for p in docs},
        'remote': 'https://github.com/yuan69082-code/continuity-engine.git',
        'actualRemoteBefore': supplied['head'], 'remoteObservation': 'git ls-remote --heads origin refs/heads/main; exit 0',
        'workflowPresent': (ROOT / '.github/workflows').exists()}
    save('before.json', before)
    destination = OUT / 'independent'
    destination.mkdir()
    names = ['review-report.md', 'identity-audit.json', 'test_extra_controls.py',
        'original-01.json', 'original-01.log', 'formal-01.json', 'formal-01.log',
        'extra-01.json', 'extra-01.log', 'independent-observations.jsonl', 'extra-observations.jsonl']
    archives = []
    for name in names:
        source = REVIEW / name
        copy = destination / ('review-report.original.md' if name == 'review-report.md' else name)
        copy.write_bytes(source.read_bytes())
        assert sha(copy) == sha(source)
        archives.append({'original': str(source), 'copy': copy.relative_to(ROOT).as_posix(),
                         'sha256': sha(copy), 'kind': 'EXACT_COPY'})
    report = (REVIEW / 'review-report.md').read_text(encoding='utf8')
    for name in names:
        if name != 'review-report.md': report = report.replace((REVIEW / name).as_posix(), name)
    report = report.replace(ROOT.as_posix() + '/src/', '../../../../src/')
    note = '# 归档阅读版\n\n只修正链接；独立报告正文结论未改。逐字节原件见[原件副本](review-report.original.md)，原件及副本 hash 见[归档清单](../archives.json)。本报告发生时尚待用户验收；当前决定见[D-074验收入口](../acceptance-report.md)。原独立运行器依赖规划目录旧 runner，保留原链接作为来源，不在归档目录直接复跑以免追加原观察日志。\n\n'
    (destination / 'review-report.md').write_text(note + report, encoding='utf8')
    archives.append({'original': str(REVIEW / 'review-report.md'),
        'copy': 'docs/project_memory/pre_p19_acceptance_evidence/independent/review-report.md',
        'originalSha256': sha(REVIEW / 'review-report.md'),
        'sha256': sha(destination / 'review-report.md'), 'kind': 'LINK_ADAPTED_READING_COPY'})
    # Original eight-item probe is already archived exactly; no duplicate history bundle.
    probe = OLD / 'independent/test_independent_boundaries.py'
    original_probe = REVIEW.parent / 'pre-p19-repair-independent-20260920/test_independent_boundaries.py'
    assert sha(probe) == sha(original_probe)
    archives.append({'original': str(original_probe), 'copy': probe.relative_to(ROOT).as_posix(),
                     'sha256': sha(probe), 'kind': 'EXISTING_EXACT_COPY'})
    save('archives.json', archives)
    common = '''用户于2026-09-20正式验收“P19开工前主体自主性边界R1—R4合并返修及A1/A2/A3补修”，并授权本批次按精确清单普通提交、普通push至现有Engine origin/main。该决定是D-074；不是重做P18验收，也不是P19开工。

本批次R1—R4及A1/A2/A3 = ACCEPTED。P00—P18历史ACCEPTED与D-073保留；P19—P23 = NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本批次已知阻断依独立复核及用户确认闭合，不保证不存在其他缺陷。历史F1/H1/F2仍UNKNOWN，用户此前接受的不确定性、旧失败、辅助错误、中断、原始格式告警与SKIP不改写。

本轮独立实跑：原八项8PASS（6.640秒）、正式交叉63PASS（120.684秒）、额外恢复/权限8PASS（10.708秒），均0FAIL/ERROR/SKIP。施工方最终全量1580项=1579PASS、1既有Windows符号链接权限1314 SKIP、0FAIL/ERROR，1687.548秒；该全量经独立核验后引用，本次归档没有重跑。独立额外探针不增加Engine正式测试数量，集合交叠不相加。

维持默认持续运行、主体自主性、当前权限/资源/生命周期、现实效果限制与唯一权威通道。真实服务、生产凭据、正式联系/费用/隐私政策及原NOT_READY能力不开放。提交与推送实际结果另由操作后的Git/真实远端核查报告，不预填成功。
'''
    history = {}
    for name in docs:
        p = ROOT / name
        raw = p.read_bytes()
        relative = Path(os.path.relpath(OUT / 'acceptance-report.md', p.parent)).as_posix()
        prefix = ('<!-- PRE_P19_ACCEPTED_D074_20260920 -->\n## 当前批次正式验收：D-074\n\n' + common +
            f'\n[验收依据、逐项状态与最终清单]({relative})。\n\n'
            '## 以下为发生时的历史记录\n\n下方旧“待复核/未验收/禁止Git”及测试结果保留原貌，不代替本次明确的验收和收尾授权。\n\n').encode('utf8')
        p.write_bytes(prefix + raw)
        suffix = b''
        if name.endswith('04_决策记录.md'):
            suffix = ('\n\n## D-074：用户正式验收P19前主体自主性边界R1—R4及A1/A2/A3，并授权精确提交与push\n\n' + common +
                '\n本条来源为用户本轮明确指令。D-073不覆盖；不得强推、改写历史、夹带32项排除材料或开始P19。核对通过后一次普通提交，网络问题仅可核查后重试同一提交；实现或远端分叉等新阻断须停止报告。\n\n'
                '[验收报告](pre_p19_acceptance_evidence/acceptance-report.md) · [独立复核阅读版](pre_p19_acceptance_evidence/independent/review-report.md) · [最终精确清单](pre_p19_acceptance_evidence/final.pending-files.md)。\n').encode('utf8')
            with p.open('ab') as f: f.write(suffix)
        history[name] = {'offset': len(prefix), 'length': len(raw), 'originalHash': sha_bytes(raw), 'suffixBytes': len(suffix)}
    save('document-history.json', history)
    matrix = '\n'.join(f'| {item} | ACCEPTED | D-074，独立报告及原正式回归；实现边界未扩展 |' for item in ('R1','R2','R3','R4','A1','A2','A3'))
    save('acceptance-report.md', '# P19前主体自主性边界修复正式验收（D-074）\n\n' + common + '''
## 验收分项

| 项目 | 当前状态 | 依据 |
|---|---|---|
''' + matrix + '''

R1/A1分离表达或现实拒绝与合法内部Evolution；R2取消名称风险启发式但保留明确风险门；R3保留有来源的倾向与Will成长；R4/A3由原动力学及未决关注支持有界认知复议；A2依实际绑定能力与来源保守区分混合提案。没有逐句效果依赖的新体系，不将全部模型提案自动写入；真实回执可供后续合法认知重新形成判断。权限、资源、STOP及世界效果限制不放宽。

## 身份与测试口径

验收代码身份：275份源码/测试/资源，`sha256:37ca50a9b21595f1e31067d88fefe95d1b4ffcf02e9095ef3393d3afcd4c36f1`。1580个正式测试身份=补修前1551项+新增29项。提交前父基线为`cb528d74884990915737b491ca6a9f2c35cc512a`。

| 来源 | 结果 | 秒 | 原始证据 |
|---|---|---:|---|
| 本轮监工独立实跑 | 原探针8PASS | 6.640 | [JSON](independent/original-01.json) / [输出](independent/original-01.log) |
| 本轮监工独立实跑 | 正式交叉63PASS | 120.684 | [JSON](independent/formal-01.json) / [输出](independent/formal-01.log) |
| 本轮监工独立实跑 | 额外边界8PASS | 10.708 | [JSON](independent/extra-01.json) / [输出](independent/extra-01.log) |
| 施工方实跑，经独立核验引用 | 完整兼容538PASS | 1152.693 | [JSON](../pre_p19_supplement_evidence/compatibility-01.json) |
| 施工方实跑，经独立核验引用 | 全量1579PASS、1SKIP、0FAIL/ERROR，exit0 | 1687.548 | [JSON](../pre_p19_supplement_evidence/full-final-01.json) / [原始输出](../pre_p19_supplement_evidence/full-final-01.stderr.log) |

本次验收操作只执行身份、保护、链接、敏感模式、范围及Git核查；没有新行为测试，没有远端CI PASS声明。本地无Actions workflow，远端CI/check是否取得以最终交付报告为准，不新建workflow。

## 历史与档案

[独立复核报告](independent/review-report.md) · [身份审计](independent/identity-audit.json) · [原件/副本hash](archives.json)。原八项探针复用[既有精确归档](../pre_p19_supplement_evidence/independent/test_independent_boundaries.py)，额外探针见[test_extra_controls.py](independent/test_extra_controls.py)。只在阅读版修正链接；逐字节原件副本另存。规划侧原件未写入。

原R1—R4、A1/A2/A3报告及矩阵增加当前验收入口，原文保留为历史，原始日志/测试结果不改写。历史F1/H1/F2与P09 segment 10原因UNKNOWN均不变；本批次闭合不能倒推旧案根因。

63项保护、三份规划、正式七文件、0.1.0/pyproject和32排除项逐文件核对；正式树保持`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。

[验收文档变更与原历史hash](document-history.json) · [最终审计](final.audit.json) · [最终提交及排除清单](final.pending-files.md)。清单包括既有220项成果及必要验收增量，计数以实际清单为准；未纳入32项排除材料。暂存严格使用精确路径，推送仅现有Engine origin/main。提交自身SHA不伪造自引用，最终SHA、父提交与推送核查结果由操作后的最终回复报告。
''')
    save('checks-notes.md', '# 本次归档检查说明\n\n首次只读搜索发现仓库不存在.github目录，rg报路径不存在；这是工具查询范围问题，不是Engine测试失败。已核对本地未配置Actions workflow，不新增配置。既有Git LF→CRLF提示与原始证据行尾空格分别保留；最终检查记录不把提示冒称为功能失败。\n')
    print(json.dumps({'prepared': True, 'decision': 'D-074', 'documents': len(docs), 'archives': len(archives)}, ensure_ascii=False))


def sha_bytes(value): return hashlib.sha256(value).hexdigest()


def audit():
    before = read(OUT / 'before.json')
    source = source_hashes()
    assert source == before['source']
    assert not git('diff', '--cached', '--name-only').strip()
    assert sha(ROOT / '.git/index') == before['index']
    assert git('rev-parse', 'HEAD').strip() == before['head']
    protected = {g: {'count': len(items), 'mismatches': [p for p, h in items.items() if sha(ROOT / p) != h]}
                 for g, items in before['protected'].items()}
    assert all(not x['mismatches'] for x in protected.values())
    history = read(OUT / 'document-history.json')
    assert all(sha_bytes((ROOT / p).read_bytes()[v['offset']:v['offset']+v['length']]) == v['originalHash'] for p, v in history.items())
    old_changed = [p for p, h in before['priorPending'].items() if p not in history and sha(ROOT / p) != h]
    assert not old_changed, old_changed
    archives = read(OUT / 'archives.json')
    assert all(sha(ROOT / r['copy']) == r['sha256'] and sha(Path(r['original'])) == r.get('originalSha256', r['sha256']) for r in archives)
    excluded = before['excluded']
    assert all(sha(ROOT / p) == h for p, h in excluded.items())
    pending = paths() - set(excluded)
    allowed_new = set(history) | {p for p in pending if p.startswith('docs/project_memory/pre_p19_acceptance_evidence/')}
    assert not (pending - set(before['priorPending']) - allowed_new)
    errors=[]; links=0; broken=[]; secrets=[]; warnings=[]
    for p in sorted(pending):
        file=ROOT/p
        if file.suffix not in {'.py','.md','.json','.jsonl','.log'}: continue
        body=file.read_text(encoding='utf8')
        if file.suffix=='.py':
            try: ast.parse(body, filename=p)
            except SyntaxError as e: errors.append((p,e.lineno))
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',body):secrets.append(p)
        for number,line in enumerate(body.splitlines(),1):
            if line.rstrip(' \t')!=line:warnings.append({'path':p,'line':number,'rawEvidence':p.endswith('.log') or '/independent/' in p})
        if file.suffix!='.md' or p.endswith('.original.md'):continue
        for target in re.findall(r'\]\(([^\n]+?)\)',body):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^(https?://|mailto:|app:)',target):continue
            target=re.sub(r':\d+$','',target)
            path=Path(target);path=path if path.is_absolute() else file.parent/path
            links+=1
            if not path.resolve().exists() and path.resolve() not in {OUT/'final.audit.json',OUT/'final.pending-files.md'}:broken.append((p,target))
    check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    save('diff-check.log',check.stdout+check.stderr)
    assert not errors and not broken and not secrets,(errors,broken,secrets)
    assert check.returncode==0
    assert not [w for w in warnings if not w['rawEvidence']]
    selfnames = [OUT / n for n in ('final.audit.json','final.pending-files.md','git-paths.txt')]
    pending = sorted((paths()-set(excluded)) | {p.relative_to(ROOT).as_posix() for p in selfnames})
    forbidden=[p for p in pending if Path(p).suffix.lower() in {'.pyc','.whl','.zip','.exe','.dll'} or any(x.lower() in {'__pycache__','.continuity-data','.assistant-data','sandbox','build','dist'} for x in Path(p).parts)]
    assert not forbidden,forbidden
    save('git-paths.txt','\n'.join(pending)+'\n')
    special={p.relative_to(ROOT).as_posix() for p in selfnames[:2]}
    manifest=['# D-074 最终精确提交及排除清单','',f'本批次待提交 {len(pending)} 项；原排除32项另列。只用于本次Engine main普通提交/push。',
        '本清单及审计自身不循环自哈希；审计记录本清单最终hash，复核方可独立计算审计hash。','', '| 路径 | SHA-256 |','|---|---|']
    manifest += [f'| `{p}` | {"SELF_NOT_HASHED" if p in special else sha(ROOT/p)} |' for p in pending]
    manifest += ['', '## 原样排除（32项）','', '| 路径 | SHA-256 |','|---|---|']
    manifest += [f'| `{p}` | {h} |' for p,h in sorted(excluded.items())]
    save('final.pending-files.md','\n'.join(manifest)+'\n')
    formal=tree_inventory_hash(ROOT/'.continuity-data')
    assert formal==before['formalTreeHash'] and sha(ROOT/'pyproject.toml')==before['pyproject']
    result={'at':datetime.now(timezone.utc).isoformat(),'decision':'D-074','batchStatus':'ACCEPTED',
        'planningConflict':'NONE','evidenceConflict':'NONE','historicalF1H1F2':'UNKNOWN',
        'headBefore':before['head'],'originBefore':git('rev-parse','origin/main').strip(),
        'sourceCount':len(source),'sourceHash':before['sourceHash'],'source':source,
        'testsRerunForAcceptance':False,'protection':protected,'formalTreeHash':formal,
        'formalFileCount':len([p for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()]),
        'version':'0.1.0','pyprojectUnchanged':True,'oldEvidenceUnchanged':not old_changed,
        'priorDocumentsPreserved':True,'archiveHashesMatch':True,'astErrors':errors,'localLinks':links,
        'brokenLinks':broken,'highConfidenceSecretHits':secrets,'formatWarnings':warnings,
        'diffCheckExit':check.returncode,'forbiddenArtifacts':forbidden,'stagedBefore':[],
        'pendingCount':len(pending),'pending':{p:('SELF_NOT_HASHED' if p==selfnames[0].relative_to(ROOT).as_posix() else sha(ROOT/p)) for p in pending},
        'excludedCount':len(excluded),'excluded':excluded,'workflowPresent':before['workflowPresent'],
        'remoteCI':'NO_RESULT_OBTAINED','gitStatusBeforeStage':git('status','--porcelain=v1','--untracked-files=all'),
        'gitWriteOutcome':'NOT_PREFILLED; final commit/push verification reported after execution'}
    save('final.audit.json',result)
    print(json.dumps({k:result[k] for k in ('pendingCount','excludedCount','sourceCount','sourceHash','localLinks','formatWarnings','diffCheckExit')},ensure_ascii=False))


if __name__ == '__main__':
    {'prepare':prepare,'audit':audit}[sys.argv[1]]()
