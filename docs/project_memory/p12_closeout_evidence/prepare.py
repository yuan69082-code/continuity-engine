"""Prepare this one reviewed P12 closeout; no Git writes or implementation edits."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
os.chdir(root)
before=json.loads((directory/'before.json').read_text(encoding='utf-8'))
old=json.loads((root/'docs/project_memory/p12_second_repair_evidence/pending-files.json').read_text(encoding='utf-8'))
assert not (directory/'commit-files.json').exists(), 'Do not regenerate an approved manifest silently'
assert datetime.now(timezone.utc)<datetime.fromisoformat(before['deadline'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):
    p=subprocess.run(['git',*args],capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    return p.returncode,p.stdout.decode('utf-8').strip(),p.stderr.decode('utf-8').strip()
def paths(*args):
    rc,out,err=git(*args); assert rc==0,err
    return [x for x in out.split('\0') if x]
assert git('branch','--show-current')[1]=='main'
assert git('rev-parse','HEAD')[1]==git('rev-parse','origin/main')[1]==before['head']
assert not paths('diff','--cached','--name-only','-z')
for flag in ((),('--push',)):
    assert git('remote','get-url',*flag,'origin')[1]==before['remote']
for mapping in ('sourceTest','protected'):
    assert all(sha(root/p)==h for p,h in before[mapping].items()),mapping

names=['README.md',*['docs/project_memory/'+n for n in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
    '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md','59_P12_IntentionalForgetting架构边界.md',
    '60_P12_规划施工测试验收矩阵.md','61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md')]]
report_path='docs/project_memory/P12_独立复核与Git收尾_20260907.md'
for name in names:
    p=root/name; text=p.read_text(encoding='utf-8')
    text=text.replace('> P12 第二轮 F1/F2 返修现行状态','> P12 第二轮 F1/F2 返修送审历史状态',1)
    prefix='docs/project_memory/' if name=='README.md' else ''
    block=f'''<!-- P12_REVIEW_CURRENT_START -->
> P12 独立复核后现行状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE（本轮独立复核阻断已闭合，非用户正式验收）。监工实跑原 9 条 PASS（1.207 秒）、新 7 条 PASS（1.011 秒）、P12 117 PASS（27.198 秒）；核验引用施工全量 1011 项：1010 PASS、1 既有 SKIP、0 FAIL/ERROR，stderr 521.632 秒、结构化记录 521.633 秒。
>
> [独立复核与本次 Git 收尾范围]({prefix}P12_独立复核与Git收尾_20260907.md)。今晚一次性普通提交推送已获条件放行；此档为提交前记录，实际 SHA 和推送结果由 Git 记录及施工最终报告确认。没有创建 D-061，没有授权 ACCEPTED；下方全部 FAIL/ERROR/SKIP、证据冲突及 P09 segment 10 UNKNOWN 历史保留。
<!-- P12_REVIEW_CURRENT_END -->'''
    assert '<!-- P12_REVIEW_CURRENT_START -->' not in text
    index=text.index('\n')+1
    p.write_text(text[:index]+'\n'+block+'\n'+text[index:],encoding='utf-8')
for name,title in [('04_决策记录.md','D-060：独立复核闭合与今晚一次性 Git 收尾授权'),
                   ('03_施工日志.md','2026-09-07：P12 复核通过后的精确 Git 收尾'),
                   ('10_档案修订记录.md','2026-09-07：归档独立复核及提交前清单'),
                   ('CHANGELOG.md','P12 独立复核通过，正式验收仍待用户确认')]:
    p=root/'docs/project_memory'/name
    text=p.read_text(encoding='utf-8').rstrip()
    text+='\n\n## '+title+'\n\n'
    text+='规划监工已核对最终源码、测试、实际专项及全量引用证据，无剩余本轮阻断。放行编号 P12-TONIGHT-CLOSEOUT-20260907-01，仅允许本次现有 Engine main 普通提交和 push，截止 2026-09-07 08:00 Asia/Shanghai。没有正式阶段验收授权，不创建 D-061，P12 仍 IMPLEMENTED_NOT_ACCEPTED。所有原始失败、辅助错误和 SKIP 保留，不重跑未变化的全量。详见 [收尾档案](P12_独立复核与Git收尾_20260907.md)。\n'
    p.write_text(text,encoding='utf-8')

report='''# P12 独立复核与一次性 Git 收尾 — 2026-09-07

P12 / Engine side / P12-01—P12-12 = IMPLEMENTED_NOT_ACCEPTED。监工本轮独立复核已通过，EVIDENCE_CONFLICT=NONE 仅表示已发现阻断闭合；PLANNING_CONFLICT=NONE。P00—P11 ACCEPTED，P13—P23 NOT_STARTED，Vio dependency=NONE。没有正式用户验收决定，不创建 D-061。

## 授权与只读基线

规划监工在用户今晚一次性条件授权下发出 `P12-TONIGHT-CLOSEOUT-20260907-01`。允许精确暂存、一次普通提交和向原 origin/main 正常推送；不得晚于 2026-09-07 08:00 Asia/Shanghai 新执行 commit/push。禁止强推、改远端、合并/rebase、重写历史、分支/标签/release、Assistant 或 P13。收尾后恢复用户先确认模式。

实际开工 main，HEAD/本地 origin/main 为 `1b8020fbe687dafaaf83a629dbeee65d69a71d67`。暂存区空，25 tracked 修改、231 untracked：225 个 P12 路径与 31 个原 P10 排除脚本。205 个源码/测试、224 个前次审计内容文件和 63 保护文件与独立复核一致。只读 `git ls-remote --exit-code origin refs/heads/main` 成功，实际远端 main 与基线一致；现有 fetch/push URL 均为 `https://github.com/yuan69082-code/continuity-engine.git`。本次不修改运行代码或测试。

## 独立实跑与核验引用

| 证据 | 真实结果 | 耗时 |
|---|---|---|
| [监工原九条探针](p12_closeout_evidence/independent/tonight-20260907-original-01.stderr.log) | 9 PASS、0 FAIL/ERROR/SKIP | 1.207 秒 |
| [监工新七条探针](p12_closeout_evidence/independent/tonight-20260907-neighbors-01.stderr.log) | 7 PASS、0 FAIL/ERROR/SKIP | 1.011 秒 |
| [监工 P12 专项](p12_closeout_evidence/independent/tonight-20260907-p12-01.stderr.log) | 117 PASS、0 FAIL/ERROR/SKIP | 27.198 秒 |
| [监工核验的施工 full-final](p12_second_repair_evidence/full-final.tests.json) | 1011 项：1010 PASS、1 既有 SKIP、0 FAIL/ERROR | stderr 521.632 秒；结构化 521.633 秒 |

全量是施工方第二轮返修的实跑，本次监工及 Git 收尾仅核验引用，没有再执行全量。SKIP 仍为 Windows symlink 1314，不能计 PASS。原 992/894 测试身份、原测试断言完整保留。计时精度差异保留两个原值，不修改日志或结构化记录。

[监工报告原文副本](p12_closeout_evidence/independent/tonight-final-review.source.txt) 按字节归档，来源与 SHA-256 见 [来源清单](p12_closeout_evidence/independent/sources.json)。[只读独立原件](C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p12-recheck-20260907/tonight-final-review.md) 未修改。[核验脚本](p12_closeout_evidence/independent/verify_tonight.py) 和 [最终输出](p12_closeout_evidence/independent/tonight-20260907-evidence-03.stdout.log) 保留；脚本验证的是归档前送审快照，提交后分支/档案状态变化应按本次清单审计，不把旧脚本的快照断言当作新的功能故障。

监工曾误将 app.js 交给 Python AST，原 [SyntaxError 输出](p12_closeout_evidence/independent/tonight-20260907-evidence-01.stderr.log) 完整保留；修正筛选后对 195 个 Python 文件解析及全部 205 文件 hash 核验通过。这是辅助脚本错误，不是 Engine 失败。所有更早首次失败、修复、辅助错误、SKIP，以及 P09 segment 10 根因 UNKNOWN 继续保留。

## 精确范围与检查

[提交文件清单](p12_closeout_evidence/commit-files.md) 和 [逐文件 hash/分类](p12_closeout_evidence/commit-files.json) 是本次暂存依据。逐项保留 19 个实现/正式测试文件、直接档案、P12 各次失败/成功日志及测试身份清单；原始空 stdout 也是对应运行通道证据。历史 capture/run/audit/sync 辅助源码作为这些证据生成方式保留，非新增运行产品入口。规划提取来源仅保留已有 P12 Stage Brief 所引用的一份原始来源清单，不复制规划源或额外打包规划目录。

新增材料限本次独立报告副本、三份通过日志、一次辅助错误、最终核验输出/脚本与来源 hash，以及收尾清单和核查记录。原 31 个 P10 辅助脚本逐文件排除并保持原样；无正式数据、凭据、缓存、Temp 数据根、wheel、构建产物或无关文件进入范围。

[提交前静态与边界结果](p12_closeout_evidence/precommit-checks.json) 检查源码/测试 hash、63 保护项、三份规划源、监工原件、版本 0.1.0、AST、本地链接、敏感格式和状态。正式数据仍为七文件，树指纹 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。本轮仅档案变更，不机械重跑全量。

四个旧原始 stderr 在失败中断的进度行含尾空格：`p12_evidence/compatibility-01.stderr.log:16`、`p12_evidence/iterable-roots-red.stderr.log:3`、`p12_evidence/propagation-red-02.stderr.log:3`、`p12_repair_evidence/extended-01.stderr.log:14`。它们与监工已核验 hash 一致，必须按字节保留；暂存检查如报告这四条，作为历史日志格式单列，不能改写原始失败输出。其他新增格式问题仍须停止核实，不豁免代码、测试或普通档案。

## 提交与停止位置

提交说明：`feat: implement P12 memory lifecycle and reviewed repairs`。此档随提交归档，不能包含自身尚未生成的 SHA；实际提交身份、普通 push 结果、实际远端一致性及剩余文件由 Git 记录和本次施工最终报告确认，不预填成功。若 commit 成功而 push 失败，保留原提交，不重建、不改写历史。

当前 Engine 没有 Actions workflow，不存在本次远程 CI PASS；push 也不是测试或验收。生产自动遗忘策略、物理擦除、生产删除及备份清理仍未开放。提交后仍需用户单独正式验收 P12，停止等待，不进入 P13。
'''
(root/report_path).write_text(report,encoding='utf-8')

tracked=paths('diff','--name-only','-z'); untracked=paths('ls-files','--others','--exclude-standard','-z')
output_paths=['docs/project_memory/p12_closeout_evidence/'+x for x in ('precommit-checks.json','commit-files.md','commit-paths.txt','commit-files.json')]
selected=sorted((set(tracked+untracked)-set(before['excludedP10']))|set(output_paths))
allowed_new=lambda p:p==report_path or p.startswith('docs/project_memory/p12_closeout_evidence/')
assert all(allowed_new(p) for p in set(selected)-set(before['p12Before']))
drift=[p for p,h in before['reviewedContentHashes'].items() if sha(root/p)!=h]
assert not set(drift)-set(names),drift
assert all(sha(root/p)==h for p,h in before['sourceTest'].items())
assert all(sha(root/p)==h for p,h in before['protected'].items())
assert set(before['excludedP10']).issubset(untracked)
for info in before['independentSources'].values():assert sha(info['source'])==info['sha256']
plans=json.loads((root/'docs/project_memory/p12_evidence/planning-source.json').read_text(encoding='utf-8'))
assert all(sha(x['source'])==x['sha256'] for x in plans.values())
sources=[root/p for p in before['sourceTest'] if p.endswith('.py')]
for p in [*sources,*directory.rglob('*.py')]:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
pattern=re.compile(rb'(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
whitespace=[]
for p in selected:
    q=root/p
    if not q.exists():continue
    assert q.suffix in ('.md','.py','.json','.log','.txt'),p
    assert not any(x in q.parts for x in ('__pycache__','.continuity-data','dist','build','.venv')),p
    data=q.read_bytes(); assert not pattern.search(data),p
    text=data.decode('utf-8-sig')
    bad=[i for i,line in enumerate(text.splitlines(),1) if line.rstrip(' \t')!=line]
    if bad or text.endswith(('\n\n','\r\n\r\n')):
        whitespace.append({'path':p,'trailingWhitespace':bad,'blankAtEof':text.endswith(('\n\n','\r\n\r\n'))})
expected={('docs/project_memory/p12_evidence/compatibility-01.stderr.log',16),
    ('docs/project_memory/p12_evidence/iterable-roots-red.stderr.log',3),
    ('docs/project_memory/p12_evidence/propagation-red-02.stderr.log',3),
    ('docs/project_memory/p12_repair_evidence/extended-01.stderr.log',14)}
assert {(x['path'],i) for x in whitespace for i in x['trailingWhitespace']}==expected
assert not any(x['blankAtEof'] for x in whitespace)
markdown=[root/'README.md',*sorted((root/'docs/project_memory').glob('*.md'))]
links=[]; broken=[]
for p in markdown:
    for target in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^\n]+?)\)',p.read_text(encoding='utf-8')):
        target=unquote(target.strip().strip('<>')).split('#',1)[0]
        if not target or re.match(r'^(?:https?|mailto|app|codex|data):',target):continue
        target=target.replace('\\_','_').replace('\\ ',' '); resolved=(p.parent/target).resolve()
        links.append([str(p.relative_to(root)),target])
        if not resolved.exists() and resolved not in {(root/x).resolve() for x in output_paths}:broken.append(links[-1])
assert not broken,broken
for name in names:
    block=(root/name).read_text(encoding='utf-8').split('<!-- P12_REVIEW_CURRENT_START -->')[1].split('<!-- P12_REVIEW_CURRENT_END -->')[0]
    assert all(x in block for x in ('IMPLEMENTED_NOT_ACCEPTED','EVIDENCE_CONFLICT=NONE','P13—P23 NOT_STARTED'))
assert not re.search(r'^## D-061[：:]',(root/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8'),re.M)
diff=git('diff','--check'); assert diff[0]==0,diff
categories={}
for p in selected:
    if p.startswith(('src/','tests/')):category='已复核 P12 实现和正式测试'
    elif p in old['categories']['全 P12 档案和导航'] or p==report_path:category='P12 直接档案和导航'
    elif p in old['categories']['P12 及返修证据与本地辅助']:
        if p.endswith('.py'):category='P12 证据生成和复现辅助源码'
        else:category='P12 原始失败/通过/身份/来源/审计证据'
    else:category='本次独立复核及精确 Git 收尾记录'
    categories[p]=category
counts={c:sum(v==c for v in categories.values()) for c in sorted(set(categories.values()))}
checks={'capturedAt':datetime.now(timezone.utc).isoformat(),'status':'PASS_WITH_PRESERVED_RAW_LOG_WHITESPACE',
    'head':before['head'],'sourceTestFiles':len(before['sourceTest']),'sourceHashDrift':[],
    'protectedFiles':len(before['protected']),'protectedHashDrift':[],'planningSourceDrift':[],
    'pythonAstSourceFiles':len(sources),'markdownFiles':len(markdown),'localLinks':len(links),'brokenLinks':[],
    'sensitiveMatches':[],'trackedDiffCheck':{'exitCode':diff[0],'stdout':diff[1],'stderr':diff[2]},
    'preservedHistoricalWhitespace':whitespace,'reviewedDocsChanged':drift,'selectedCount':len(selected),
    'categories':counts,'excludedP10':before['excludedP10'],'sourceTest':before['sourceTest'],
    'noNewTestsRun':True,'noAcceptanceDecision':True,'currentEvidenceConflict':'NONE: independent review closed findings'}
(directory/'precommit-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# 本次 P12 精确提交清单','','授权 P12-TONIGHT-CLOSEOUT-20260907-01，仅当前 Engine main 普通提交并 push。',
    f'本清单共 {len(selected)} 个路径。禁止 git add .；按 commit-paths.txt 逐项暂存。',
    '运行代码和正式测试没有变化；31 个原 P10 脚本原样排除。全部原始日志保留，包括四个历史尾空格。',
    '本清单是提交前快照；本提交自身 SHA 与 push 结果见 Git 记录及最终施工报告。','']
for c,n in counts.items():
    lines+=['## '+c+f'（{n}）','']+['- `'+p+'`' for p in selected if categories[p]==c]+['']
lines+=['## 原 31 个 P10 排除项','']+['- `'+p+'` — sha256:'+h for p,h in sorted(before['excludedP10'].items())]+['']
(directory/'commit-files.md').write_text('\n'.join(lines),encoding='utf-8')
(directory/'commit-paths.txt').write_text('\n'.join(selected)+'\n',encoding='utf-8')
self_path=str((directory/'commit-files.json').relative_to(root)).replace('\\','/')
manifest={'authorization':before['authorization'],'deadline':before['deadline'],'baseHead':before['head'],'branch':'main',
    'remote':before['remote'],'message':'feat: implement P12 memory lifecycle and reviewed repairs',
    'files':[{'path':p,'category':categories[p],'sha256':None if p==self_path else sha(root/p)} for p in selected],
    'selfHashNote':'Self hash is verified during staging and represented by its commit blob; no circular fabricated hash.',
    'excludedP10':before['excludedP10'],'otherExcluded':[],'categories':counts}
(directory/'commit-files.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'selected':len(selected),'categories':counts,'excludedP10':len(before['excludedP10']),
    'pythonAst':len(sources),'markdown':len(markdown),'links':len(links),'preservedWhitespace':whitespace,
    'manifestSHA256':sha(directory/'commit-files.json')},ensure_ascii=False))
