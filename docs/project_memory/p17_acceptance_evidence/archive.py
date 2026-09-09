"""P17 acceptance documentation and read-only identity audit; no Git mutations."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import re
import runpy
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DOC = OUT.parent
REPAIR = DOC / 'p17_repair_evidence'
REVIEW = Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p17-independent-review-20260909')
BASE = '0c440b0476b07723abafe93777fe895b64fd8d0e'
REMOTE = 'https://github.com/yuan69082-code/continuity-engine.git'
ENTRY = DOC / 'P17_用户正式验收_20260910.md'
TOP = ['00_项目总览.md', '01_当前状态.md', '02_工程路线图.md', '03_施工日志.md', '04_决策记录.md',
       '05_核心模块架构.md', '05_已完成模块.md', '06_未完成事项.md', '07_待确认事项.md',
       '08_未来扩展.md', '10_档案修订记录.md', '11_P00_全周期能力与阶段基线.md',
       '12_P00_规划施工测试验收矩阵.md', '13_P00_档案与测试索引.md', 'CHANGELOG.md', '工程总档案.md']
CURRENT_DOCS = [ROOT / 'README.md', *(DOC / n for n in TOP),
                *(next(DOC.glob(n + '_P17_*.md')) for n in ('79', '80', '81', '82'))]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from continuity_engine.testing.persistence import tree_inventory_hash


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT).decode('utf-8').strip()


def source():
    return {p.relative_to(ROOT).as_posix(): sha(p) for folder in ('src', 'tests')
            for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def save(p, value):
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def status():
    return dict(branch=git('branch', '--show-current'), head=git('rev-parse', 'HEAD'),
                originMain=git('rev-parse', 'origin/main'), remote=git('remote', 'get-url', 'origin'),
                aheadBehind=git('rev-list', '--left-right', '--count', 'HEAD...origin/main'),
                staged=git('diff', '--cached', '--name-only'),
                tracked=list(filter(None, git('diff', '--name-only', '-z').split('\0'))),
                untracked=list(filter(None, git('ls-files', '--others', '--exclude-standard', '-z').split('\0'))))


STATE = ('2026-09-10 用户正式验收 P17 初版及 R1/R2 返修（D-071）。'
         'P00—P17 ACCEPTED；P17 / Engine side / P17-01—P17-12 ACCEPTED；'
         'P17 Vio dependency=NONE；P18—P23 NOT_STARTED。'
         '现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示独立复核覆盖范围内已知阻断闭合，不保证不存在其他缺陷。')
EVIDENCE = ('监工独立实跑：完整 P17 74 PASS（unittest 101.169 秒），原探针及额外检查共 11 PASS（9.246 秒），'
            '均为 0 SKIP/FAIL/ERROR；24/24 身份与保护检查通过。'
            '全量仅引用已核验的施工方 1360 项：1359 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1171.401 秒。'
            '12 项返修正式测试已包含在 74 项中，独立探针不增加 Engine 正式测试数；本次归档未重跑行为测试。')
BOUNDARY = ('验收范围为隔离 Research/Test World 与本地 Fake；生产 Adapter、真实凭据、生产恢复及正式策略仍 NOT_READY。'
            '保留唯一 E5-A 通道，不宣称生产 exactly-once，不修改 Assistant，不进入 P18。'
            '用户已授权本阶段精确清单普通提交及推送；提交身份与实际推送结果在完成后另行报告，不预填成功。'
            '下方旧状态、未验收/无 Git 授权说明和全部 FAIL/ERROR/SKIP、辅助错误、P09 segment 10 UNKNOWN 均为历史，不倒改。')


def prepare():
    assert not (OUT / 'before.json').exists() and not ENTRY.exists(), 'preserve existing acceptance work'
    a = read(REPAIR / 'final.audit.json'); b = read(REPAIR / 'before.json'); s = status(); current = source()
    assert s['head'] == s['originMain'] == BASE and s['branch'] == 'main' and not s['staged']
    assert s['remote'] == REMOTE and s['aheadBehind'] == '0\t0'
    own = Path(__file__).relative_to(ROOT).as_posix()
    assert (set(s['tracked'] + s['untracked']) - set(a['excluded']) - {own}) == set(a['pending'])
    assert current == a['sourceTest']
    assert all(sha(ROOT / p) == h for p, h in a['pendingHashes'].items())
    snap = read(REVIEW / 'repair-p17-01.after.json')
    assert all((ROOT / p).is_file() and sha(ROOT / p) == h for p, h in snap.items())
    for key in ('protected', 'plans', 'formalFiles', 'excludedP10', 'otherPreserved'):
        assert all((ROOT / p).is_file() and sha(ROOT / p) == h for p, h in b[key].items()), key
    assert tree_inventory_hash(ROOT / '.continuity-data') == b['formalTreeHash']
    decisions = DOC / '04_决策记录.md'
    assert not re.search(r'^## D-071[：:]', decisions.read_text(encoding='utf-8'), re.M)
    before = dict(at=datetime.now(timezone.utc).isoformat(), git=s, sourceTest=current,
                  reviewedPending=a['pending'], pendingHashes={p: sha(ROOT / p) for p in a['pending']},
                  excluded=a['excluded'], independentSnapshotFile='repair-p17-01.after.json',
                  independentSnapshotCount=len(snap), independentSnapshotMatches=True,
                  formalTreeHash=b['formalTreeHash'], pyproject=sha(ROOT / 'pyproject.toml'))
    for key in ('protected', 'plans', 'formalFiles', 'excludedP10', 'otherPreserved'):
        before[key] = b[key]
    save(OUT / 'before.json', before)
    names = ['acceptance-push-brief.md', 'repair-review-report.md', 'repair-identity-check.json',
             'test_independent_edges.py', 'test_repair_extra.py', 'verify_repair_evidence.py', 'run_review.py']
    names += [label + suffix for label in ('repair-p17-01', 'repair-independent-01')
              for suffix in ('.result.json', '.stdout.log', '.stderr.log', '.before.json', '.after.json')]
    target = OUT / 'independent'; target.mkdir(exist_ok=False)
    copies = {}
    for name in names:
        src = REVIEW / name; dest = target / name
        with dest.open('xb') as f:
            f.write(src.read_bytes())
        assert sha(dest) == sha(src)
        copies[name] = dict(source=str(src), destination=dest.relative_to(ROOT).as_posix(), sha256=sha(src))
    save(OUT / 'archive-map.json', copies)
    save(OUT / 'tool-observations.json', dict(
        observations=[
            dict(command='git ls-remote origin refs/heads/main', environment='restricted sandbox', exitCode=1,
                 outcome='schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)',
                 classification='tool environment error; not an Engine test failure'),
            dict(command='git ls-remote origin refs/heads/main', environment='authorized host execution', exitCode=0,
                 stdout=BASE + '\trefs/heads/main\n', outcome='actual remote baseline matches local HEAD and origin/main'),
            dict(command='rg --files --hidden -g AGENTS.md ...', exitCode=1, outcome='no applicable AGENTS.md found; actual .agents/workflow.md read')],
        behaviorTestsRunThisCloseout=False, gitWritesAtThisSnapshot=False))
    archive_lines = ['# 独立复核归档清单', '', '17 个必要原件逐字节复制，规划侧原件只读。来源和 SHA-256 见 [机器清单](archive-map.json)。', '',
                     '| 副本 | SHA-256 |', '|---|---|']
    for name, row in copies.items():
        archive_lines.append('| [' + name + '](independent/' + name + ') | `' + row['sha256'] + '` |')
    (OUT / 'archive-index.md').write_text('\n'.join(archive_lines) + '\n', encoding='utf-8')
    for p in CURRENT_DOCS:
        old = p.read_text(encoding='utf-8')
        assert '<!-- P17_ACCEPTED_START -->' not in old
        link = ('docs/project_memory/' if p == ROOT / 'README.md' else '') + ENTRY.name
        block = '<!-- P17_ACCEPTED_START -->\n' + STATE + '\n\n' + EVIDENCE + '\n\n' + BOUNDARY
        block += '\n\n[正式验收依据、审计与精确提交清单](' + link + ')。\n<!-- P17_ACCEPTED_END -->\n\n'
        p.write_text(block + old, encoding='utf-8')
    with decisions.open('a', encoding='utf-8') as f:
        f.write('\n### D-070 追加：由 D-071 正式验收收口\n\n2026-09-10 用户确认初版及 R1/R2 返修验收；开工和返修原始决定保留，验收事实见下条。\n\n'
                '## D-071：用户正式验收 P17 初版及 R1/R2 返修\n\n' + STATE + '\n\n' + EVIDENCE + '\n\n' + BOUNDARY + '\n\n'
                '依据[独立复核报告](p17_acceptance_evidence/independent/repair-review-report.md)与[用户转发收尾授权](p17_acceptance_evidence/independent/acceptance-push-brief.md)，'
                '允许 Engine main 对明确 P17 清单一次普通提交及推送现有 origin/main。不得扩展生产能力或启动 P18。'
                '验收源码由 253 文件 hash 标识，接受决定不等于已经提交或推送，实际 Git 结果单独核对。\n')
    matrix = next(DOC.glob('80_P17_*.md')); text = matrix.read_text(encoding='utf-8')
    text, count = re.subn(r'^(\| P17-\d{2} \|[^\n]*\| )IMPLEMENTED_NOT_ACCEPTED( \|)$', r'\1ACCEPTED\2', text, flags=re.M)
    assert count == 12
    text += ('\n## 2026-09-10 用户验收与独立结论\n\n十二项现行状态已由 D-071 登记 ACCEPTED。上方补充矩阵中的“监工确认待办”及初版“尚未进行”属于当时记录。'
             '当前 R1/R2 均在独立复核覆盖范围内闭合；资源检查期间撤销授权无新增效果/实际扣费，估计 cost=0 不再绕过 Fake 固定 1 TEST credit 上限。'
             '专项独立 74 PASS，原探针与额外检查共 11 PASS，24 项身份保护通过。'
             '历史 FALSE/FAIL/ERROR、未验收及 PRESENT 状态保留。见[验收依据](P17_用户正式验收_20260910.md)。\n')
    matrix.write_text(text, encoding='utf-8')
    for filename, title in [('03_施工日志.md', 'P17 正式验收归档'), ('10_档案修订记录.md', 'P17 验收档案修订'), ('CHANGELOG.md', 'P17 accepted; version remains 0.1.0')]:
        with (DOC / filename).open('a', encoding='utf-8') as f:
            f.write('\n## 2026-09-10 ' + title + '\n\n' + STATE + '\n\n' + EVIDENCE + '\n\n'
                    '本次仅新增验收材料、同步现行档案和矩阵，不修改已验证源码/测试，不重跑全量。原 196 项 P17 成果完整纳入精确清单，32 项旧材料排除且保留。'
                    '实际暂存/提交/推送按用户授权在审计后执行，最终 SHA 及远端状态在交付报告中核实，不预填。'
                    '见[完整入口](P17_用户正式验收_20260910.md)。\n')
    ENTRY.write_text('# P17 用户正式验收及 Git 收尾（2026-09-10）\n\n' + STATE + '\n\n'
        '## 验收依据与实际实现\n\n'
        '用户转发[收尾授权原件副本](p17_acceptance_evidence/independent/acceptance-push-brief.md)，在[独立复核报告](p17_acceptance_evidence/independent/repair-review-report.md)'
        '通过后明确验收并 push；[24 项身份检查](p17_acceptance_evidence/independent/repair-identity-check.json)与当前现场再次比对。'
        'D-070 开工及返修过程保留，正式验收决定为 [D-071](04_决策记录.md)。\n\n'
        '已实现宿主中立 Execution/World/Capability、原 E5-A 唯一请求结果通道的 Outbox 可靠投递、独立回执查询与恢复、取消/停止、补偿和替代路线。'
        '正常 C1 支持 Direct 和 Optional Planner，经本地 Fake 可核验效果到 Result Observation，再由原 Router/Composer/Thinking/Action/Evolution 合法吸收。'
        'UNKNOWN 先核实，不能盲目换路线重发；补偿是独立事实，不能擦除原效果。\n\n'
        'R1：投递准备的资源/原 gate 计算完成后，在同一 Outbox 事务内读取当前 Broker、Reality、恢复条件及生命周期；独立撤销反例无新增效果和实际扣费。'
        'R2：以实际效果投影统一容量检查、写入和回执，保持原成功 1 TEST credit/失败 0 的合成契约；route.cost 是估计，不把合法 cost=0 当作 Fake 免费效果。\n\n'
        '## 结果来源（本次没有重跑行为测试）\n\n'
        '| 执行方与证据 | 真实结果 | unittest / runner 秒 |\n|---|---|---|\n'
        '| 监工独立 [P17](p17_acceptance_evidence/independent/repair-p17-01.result.json) / [stderr](p17_acceptance_evidence/independent/repair-p17-01.stderr.log) | 74 PASS，0 SKIP/FAIL/ERROR | 101.169 / 102.077 |\n'
        '| 监工独立 [原探针加额外检查](p17_acceptance_evidence/independent/repair-independent-01.result.json) / [stderr](p17_acceptance_evidence/independent/repair-independent-01.stderr.log) | 11 PASS，0 SKIP/FAIL/ERROR | 9.246 / 9.948 |\n'
        '| 核验引用施工方 [正式返修](p17_repair_evidence/formal-after-02.json) | 12 PASS，0 SKIP/FAIL/ERROR | 18.846（施工记录） |\n'
        '| 核验引用施工方 [专项](p17_repair_evidence/p17-final-01.json) | 74 PASS，0 SKIP/FAIL/ERROR | 128.466（施工记录） |\n'
        '| 核验引用施工方 [兼容](p17_repair_evidence/compatibility-final-01.json) | 224 PASS，0 SKIP/FAIL/ERROR | 169.793（施工记录） |\n'
        '| 核验引用施工方 [最终全量](p17_repair_evidence/full-final-01.json) / [stderr](p17_repair_evidence/full-final-01.stderr.log) | 1360 项：1359 PASS，1 SKIP，0 FAIL/ERROR | 1171.401（施工记录） |\n\n'
        '12 项正式返修已含在 P17 74 项和全量 1360 项中；独立 11 项不增加 Engine 测试总数。原 1348 身份和断言保留。'
        '唯一既有 SKIP 为 test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes，Windows 符号链接权限 1314，不计 PASS。'
        '独立两次执行前后均为 2158 文件且 changed=[]；归档前当前 253 个源码/测试/资源文件与独立快照及全部五次施工终局证据一致。\n\n'
        '## 边界、历史与 Git 交付\n\n' + BOUNDARY + '\n\n'
        '冻结六份 Schema、外部契约及 63 项保护清单、三份规划、正式七文件、版本 0.1.0/pyproject 和 32 项排除材料均按 hash 核对。'
        '正式数据树为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。'
        '不宣称分布式原子撤权或任意生产 Adapter exactly-once；生产恢复不能由 P01 测试快照代替。\n\n'
        '提交前基线 main / HEAD / origin/main / 实际远端 main 为 `'+BASE+'`。'
        '用户授权一次普通提交 `feat: implement and accept P17 execution and world boundaries`，目标仅现有 `'+REMOTE+'` 的 main。'
        '本清单为待执行授权范围，最终 SHA、直接父提交和实际推送结果由提交后的只读核对报告给出；不为将提交自身 SHA 写入档案而追加提交或 amend。'
        '当前仓库没有已配置 Actions workflow；本次未运行远端 CI，不宣称 CI PASS。\n\n'
        '首次受限远端查询遇到 SEC_E_NO_CREDENTIALS，正常主机权限下只读查询成功、同一基线已确认；见 [工具记录](p17_acceptance_evidence/tool-observations.json)。'
        '旧八处格式告警及初版 P17 三处原始日志行尾空格保留，新编辑档案单独检查；不改写日志清除告警。\n\n'
        '## 完整入口\n\n'
        '- [逐文件提交与排除清单](p17_acceptance_evidence/final.pending-files.md)、[终局身份/保护/链接/敏感材料审计](p17_acceptance_evidence/final.audit.json)。\n'
        '- [17 份独立原件归档及 hash](p17_acceptance_evidence/archive-index.md)、[归档前现场](p17_acceptance_evidence/before.json)。\n'
        '- [十二项矩阵](80_P17_规划施工测试验收矩阵.md)、[恢复语义](81_P17_Outbox世界恢复补偿与结果吸收语义.md)、[正常入口及可复跑命令](82_P17_测试索引与验收入口.md)。\n'
        '- [初版历史](p17_evidence/final-report.md)、[返修历史](p17_repair_evidence/final-report.md)、[全部首次失败及辅助错误](p17_repair_evidence/test-history.md)。\n\n'
        '完成 P17 收尾后停止，P18—P23 NOT_STARTED，等待用户另行确认。\n', encoding='utf-8')
    print(json.dumps(dict(prepared=True, archived=len(copies), currentDocuments=len(CURRENT_DOCS), sourceCount=len(current)), ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']:
        prepare()
    else:
        raise SystemExit('Use prepare only once; audit is a separate read-only entry.')
