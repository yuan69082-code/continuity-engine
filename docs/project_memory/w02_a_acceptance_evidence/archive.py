"""W02-A acceptance documents and read-only checks; never runs tests or Git writes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPAIR = ROOT/'docs/project_memory/w02_a_evidence/repair_r1_r2'
PREFIX = HERE.relative_to(ROOT).as_posix()+'/'
BASE = 'ce6f4771140c4b6bdb0f5ae81d4c68bfc8653e88'
SOURCE = 'sha256:1021239d8214b38493aa3ff8ea5011c7b27856966bfe3395545607a8c066c523'
ORIGIN = 'https://github.com/yuan69082-code/continuity-engine.git'
DOCS = ['README.md']+['docs/project_memory/'+x for x in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','05_已完成模块.md','06_未完成事项.md','CHANGELOG.md','工程总档案.md')]
SELF = [PREFIX+x for x in ('final.audit.json','final.inventory.json','final.pending-files.md','final.paths.txt')]
os.chdir(ROOT)
os.environ['GIT_OPTIONAL_LOCKS']='0'


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(name, data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def md(name, text): (HERE/name).write_text(text,encoding='utf-8')
def git(*args): return subprocess.check_output(['git','-c','core.quotepath=false',*args],encoding='utf-8').strip()
def paths(*args): return subprocess.check_output(['git',*args]).decode('utf-8').split('\0')[:-1]
def source(): return {p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}


def base_checks():
    inv=read(REPAIR/'final.inventory.json'); baseline=read(REPAIR.parent/'baseline.json')
    frozen=read(REPAIR/'frozen-source-02.json'); src=source()
    assert src==frozen['source'], 'SOURCE_DRIFT'
    assert 'sha256:'+hashlib.sha256(json.dumps(src,sort_keys=True,separators=(',',':')).encode()).hexdigest()==SOURCE
    protected={k:{p:sha(p)==h for p,h in v.items()} for k,v in baseline['protected'].items()}
    assert all(all(v.values()) for v in protected.values()), 'PROTECTED_DRIFT'
    excluded={**inv['exclusions'],**inv['preservedW01']}
    assert all(sha(ROOT/p)==h for p,h in excluded.items()), 'EXCLUDED_DRIFT'
    plans=read(ROOT/'docs/project_memory/w01_planning_v15_20260923/planning-sources.json')
    assert all(sha(x['original'])==x['sha256'].removeprefix('sha256:') for x in plans), 'PLAN_SOURCE_DRIFT'
    selected=read(REPAIR/'selected-runs.json'); runs={k:read(REPAIR/(selected[k]+'.json')) for k in ('formal','special','compatibility','full')}
    assert all(r['status']=='FINISHED' and r['exitCode']==0 and not r['loaderErrors'] and r['sourceBefore']==r['sourceAfter']==src for r in runs.values())
    assert runs['full']['run']==1646 and runs['full']['passed']==1645 and len(runs['full']['skips'])==1
    assert not runs['full']['failures'] and not runs['full']['errors']
    assert git('branch','--show-current')=='main' and git('rev-parse','HEAD')==BASE
    assert git('remote','get-url','origin')==ORIGIN
    return inv,baseline,protected,excluded,plans,runs


def snapshot():
    assert not (HERE/'baseline.json').exists()
    inv,b,protected,excluded,plans,runs=base_checks()
    assert not paths('diff','--cached','--name-only','-z'), 'INDEX_NOT_EMPTY'
    assert all(h is None or sha(ROOT/p)==h for p,h in inv['files'].items()), 'DELIVERY_DRIFT'
    changed=set(paths('diff','--name-only','-z')+paths('ls-files','--others','--exclude-standard','-z'))
    assert {p for p in changed if not p.startswith(PREFIX)}==set(inv['files'])|set(excluded), 'UNEXPLAINED_PATHS'
    decisions=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8')
    assert not re.search(r'^#{1,3} D-076[：: ]',decisions,re.M), 'DECISION_OCCUPIED'
    put('baseline.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=BASE,sourceHash=SOURCE,sourceCount=len(source()),
        reviewedFiles={p:sha(ROOT/p) for p in inv['files']},docBefore={p:sha(ROOT/p) for p in DOCS},indexHash=sha(ROOT/'.git/index'),
        protection=protected,excluded=excluded,plans=plans,decision='D-076',reviewKind='User-relayed planning read-only code/evidence review; no independent test rerun',
        remotePreflight=dict(first=dict(exitCode=1,error='schannel AcquireCredentialsHandle SEC_E_NO_CREDENTIALS (0x8009030e)',context='restricted execution'),second=dict(exitCode=0,sha=BASE,ref='refs/heads/main',context='normal user context'),configurationChanged=False)))
    put('exclusions.json',dict(original32=inv['exclusions'],planning25=inv['preservedW01'],all57=excluded))
    print('BASELINE_VERIFIED: 174 reviewed paths, 282 source files, 57 excluded paths; D-076 free')


def documents():
    b=read(HERE/'baseline.json'); base_checks()
    marker='<!-- W02_A_ACCEPTED_D076_20260924 -->'
    status='W02-A 初版及 R1/R2 补修 = ACCEPTED；W02 整体 = IN_PROGRESS。W02-B/C、W03、P19未开工；P00—P18历史ACCEPTED、D-073/D-074保持，P19—P23沿用NOT_STARTED。'
    review='规划窗口完成的是只读代码与证据复核，结论仅为本轮核查范围内未发现新的验收阻断、实现/正式测试/原始结果相互对应；没有重新运行测试，也不保证不存在其他缺陷。'
    tests='本次归档引用施工方最终实跑：新增25 PASS（18.586秒）、W02-A专项66 PASS（53.283秒）、兼容218 PASS（131.728秒）、全量1646项=1645 PASS/1既有Windows1314 SKIP/0 FAIL/ERROR（1659.112秒）。集合有交集不相加；原1621身份保留、新增25。本轮不重跑测试，不宣称远端CI PASS。'
    limits='复杂中文仍为有界理解；引用、歧义与不可靠否定范围保留不确定性。旧部分记录缺少可信准备材料时保守返回待完成，不公开未经核验内容；明确重提仍沿原身份恢复。自动回忆、外部资料完整可信吸收及最终贯通属于W02后续子批次。本次不开放真实服务、正式政策或其他NOT_READY能力。'
    conflict='本批现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，只关闭本批明确核验的已知问题；历史F1/H1/F2仍UNKNOWN，原失败、调查限制与D-073接受的遗留不确定性不改写。'
    for p in DOCS:
        if p.endswith('04_决策记录.md'): continue
        target=ROOT/p; raw=target.read_bytes(); assert marker.encode() not in raw
        link=('docs/project_memory/' if p=='README.md' else '')+'w02_a_acceptance_evidence/'
        block=f'''{marker}
## W02-A 正式验收（D-076，2026-09-24）

用户本轮明确验收W02-A初版及R1/R2补修，并授权精确暂存、一次普通提交和向现有Engine origin/main普通push；不是W02整体验收或下一批开工。{status}

{review}{tests}

R1已知缺口依据实际入站/重开只读查询、当前授权与身份完整性、原事实恢复及完成记录错配拒绝证据关闭；R2依据普通中文否定/指代、引用歧义范围及真实上下文正反对照关闭。{conflict}

{limits}原始失败、中间回归、辅助错误、SKIP及格式提示均按发生时记录保留，以下原记录不倒写。

源码/测试/资源282项保持`{SOURCE}`。本次仅修改验收档案，无实现及测试变更。[验收入口]({link}acceptance-report.md) · [逐项验收矩阵]({link}acceptance-matrix.md) · [测试证据口径]({link}test-evidence-index.md) · [精确清单]({link}final.pending-files.md)。提交/push尚未在本记录中预填成功，实际结果由执行后回复及Git/远端核对给出。

'''
        target.write_bytes(block.replace('\n','\r\n').encode()+raw)
    decision=ROOT/'docs/project_memory/04_决策记录.md'
    raw=decision.read_bytes(); assert b'## D-076' not in raw
    append=f'''\n### D-075 后续引用：由 D-076 正式验收

原开工和未验收记录保留为历史。用户现已正式验收本批初版及R1/R2补修，范围及Git授权见D-076；不扩大为整个W02已完成。

## D-076：用户正式验收 W02-A 初版及 R1/R2 补修，并授权精确提交与普通 push

2026-09-24，用户明确授权验收归档、按最终路径清单暂存、现有Engine main普通提交和普通push至原origin/main；禁止全仓兜底添加、强推、改写历史及后续批次开工。

{status}{conflict}

{review}{tests}

{limits}源码282项指纹`{SOURCE}`，与交付/四组最终测试前后清单一致。原始失败、辅助错误、SKIP、格式提示与全部历史保持。用户授权只纳入已复核174项和必要验收增量，32排除材料与25份W01/规划材料均原样排除；推送成功不预填。

[验收报告](w02_a_acceptance_evidence/acceptance-report.md) · [矩阵](w02_a_acceptance_evidence/acceptance-matrix.md) · [最终清单](w02_a_acceptance_evidence/final.pending-files.md)。
'''
    decision.write_bytes(raw+append.replace('\n','\r\n').encode())
    md('review-basis.md',f'''# 本次用户确认与复核口径

本文件记录2026-09-24用户在当前施工对话转达的复核结论和正式授权，不冒充规划窗口出具的新报告或测试原件。

{review}

用户正式验收W02-A初版及R1/R2补修，授权必要验收归档、精确暂存、一次普通提交与现有Engine origin/main普通push。验收条件是源码及关键证据仍与复核版本一致；发现漂移须停止，不自行补修后套用验收。

{tests}

现行依据为总施工v1.5、最终新增v1.5、长期能力v6.9及已批准W02-A说明，原名/hash/归档路径核查见[本次起点](baseline.json)。用户明确排除25份W01/规划材料，因此它们仅留本地，不通过复制改名夹带提交。相关历史链接在本地有效，但这些依赖不是本次提交的文件；需要另行归档时等用户指令。

{status}{conflict}
''')
    table=['|施工方既有实跑（本轮仅引用）|结果|墙钟秒|原始记录|','|---|---|---:|---|']
    inv,base,prot,exc,plans,runs=base_checks(); selected=read(REPAIR/'selected-runs.json')
    for name in ('formal','special','compatibility','full'):
        r=runs[name]; label=selected[name]
        table.append(f"|{name}|{r['run']}项：{r['passed']} PASS、{len(r['skips'])} SKIP、{len(r['failures'])} FAIL、{len(r['errors'])} ERROR|{r['seconds']:.3f}|[JSON](../w02_a_evidence/repair_r1_r2/{label}.json) · [stdout](../w02_a_evidence/repair_r1_r2/{label}.stdout.log) · [stderr](../w02_a_evidence/repair_r1_r2/{label}.stderr.log)|")
    md('test-evidence-index.md','# 验收引用的测试证据\n\n'+review+'本轮只做身份、保护、文档及Git检查，没有运行测试。\n\n'+'\n'.join(table)+'\n\n原1621测试身份保留，新增25；各组交集不累加。既有SKIP为test_p08_fixture_paths中Windows创建符号链接权限1314，非PASS。最终282文件源码指纹`'+SOURCE+'`。\n\n[修前失败及全部中间结果](../w02_a_evidence/repair_r1_r2/test-history.md) · [初版证据](../w02_a_evidence/final-report.md) · [补修证据](../w02_a_evidence/repair_r1_r2/final-report.md)。旧版通过仅覆盖各自版本，不能替代最终版本。\n')
    original=(REPAIR/'matrix.md').read_text(encoding='utf-8'); rows=[]
    for line in original.splitlines():
        if line.startswith('|A'):
            parts=line.split('|'); parts[-2]='ACCEPTED（D-076）；'+parts[-2].replace('待独立复核','用户已确认')
            rows.append('|'.join(parts))
    assert len(rows)==12
    md('acceptance-matrix.md','# W02-A 当前逐项验收矩阵\n\n仅验收W02-A初版及R1/R2补修，原交付矩阵原样保留。[D-076](../04_决策记录.md)为用户验收依据；'+review+'\n\n|Planning Item|Code Change / 原链入口|Test / 既有正式证据|Acceptance Result|\n|---|---|---|---|\n'+'\n'.join(rows)+'\n\n[最终测试索引](test-evidence-index.md)按真实版本绑定。N02回答前自动回忆、N11完整可信吸收等后续内容不因本表验收；W02整体IN_PROGRESS，W02-B/C、W03、P19未开工。历史F1/H1/F2仍UNKNOWN。\n')
    md('acceptance-report.md',f'''# W02-A 初版及 R1/R2 补修正式验收

用户于2026-09-24正式验收，决定 **D-076**。{status}

## 验收依据和范围

{review}本次用户明确验收和Git授权的归档见[复核与授权口径](review-basis.md)。实现、正式测试和关键交付文件与已复核版本逐项核对一致；起点main/HEAD/local origin及实际远端main均为`{BASE}`，暂存为空。[起点与逐文件hash](baseline.json)保留真实现场。

已交付原消息→既有入站/Perception/C1→相关站处置→当前Context及原合法内部链；收到材料不等于已经记住。R1使部分失败及重开后的正式查询可读可信站点状态，查询只读；恢复沿原请求和原成功事实，不重复事件、效果、扣费或revision。R2修正普通“不喜欢”与词内“他”的误判，保留原文、来源、引用/范围不确定性和旧v1解释恢复。

{limits}

## 状态与历史

{conflict}本次没有重做P18验收。原始4项失败、中间普通问句回归、完成记录错配反例、辅助路径/导入/工具错误、历史SKIP及格式提示均保留，不以后续PASS倒写。

## 验证口径

{tests}源码282项最终指纹：`{SOURCE}`。[逐项验收矩阵](acceptance-matrix.md) · [原始测试索引](test-evidence-index.md)。本轮只读审计核对完整源码、保护/规划/正式数据、历史材料、链接、敏感模式及提交范围；不修改已验收实现或测试。

## 提交与保留范围

以已复核174项为起点，加本次必要验收档案（含已完成模块索引），最终数量/路径/hash以[精确清单](final.pending-files.md)、[文件清单](final.inventory.json)、[路径文件](final.paths.txt)为准。[32项原排除材料和25份W01/规划材料](exclusions.json)不提交、不删除；它们的历史本地引用仍保留，不能声称已经随本次提交归档。

正式数据7文件树保持`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`；63保护、冻结契约、三份旧规划及三份现行规划、版本0.1.0均不变。当前保护结果和差异提示见[验收审计](final.audit.json)。不修改Assistant/Vio、不连接真实业务服务。

本文件在提交前保存，不预填提交SHA或push成功。计划仅现有Engine main一次普通提交、普通push，实际结果在执行后回复中按本地/跟踪/实际远端三处SHA核对。远端查询首次在受限环境发生schannel凭据上下文错误；正常用户上下文只读重试成功，未改任何Git/TLS配置。没有可验证CI结果不得声称CI PASS，不新增workflow。

完成本批Git收尾后停止，等待用户下一次明确授权。
''')
    print('D-076 and acceptance documents written; implementation/tests untouched')


def audit():
    inv,b,protected,excluded,plans,runs=base_checks(); snap=read(HERE/'baseline.json')
    assert not paths('diff','--cached','--name-only','-z'), 'INDEX_NOT_EMPTY_BEFORE_STAGING'
    changed=set(paths('diff','--name-only','-z')+paths('ls-files','--others','--exclude-standard','-z'))
    newdocs={p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()}
    pending=sorted(set(inv['files'])|set(DOCS)|newdocs|set(SELF))
    assert changed <= set(pending)|set(excluded) and set(pending)-set(SELF) <= changed, 'UNEXPECTED_SCOPE'
    preserved={p:sha(ROOT/p)==h for p,h in snap['reviewedFiles'].items() if p not in DOCS}
    assert all(preserved.values()), 'HISTORICAL_EVIDENCE_OR_SOURCE_CHANGED'
    olddocs={}
    for p,h in snap['docBefore'].items():
        raw=(ROOT/p).read_bytes()
        if p.endswith('04_决策记录.md'):
            old=raw.split('\r\n### D-075 后续引用：由 D-076'.encode())[0]
        else:
            marker=(b'<!-- PRE_P19_ACCEPTED_D074_20260920 -->' if p.endswith('05_已完成模块.md') else b'<!-- W02_A_REPAIR_R1_R2_CURRENT -->')
            old=raw[raw.index(marker):]
        olddocs[p]=hashlib.sha256(old).hexdigest()==h
    assert all(olddocs.values()), 'HISTORICAL_DOC_BODY_CHANGED'
    # Self-referential derived outputs are explicit, not fabricated hashes.
    hashes={p:(None if p in SELF else sha(ROOT/p)) for p in pending}
    (HERE/'final.paths.txt').write_text('\n'.join(pending)+'\n',encoding='utf-8')
    put('final.inventory.json',dict(files=hashes,selfHashExcluded=SELF,priorReviewed174=list(inv['files']),acceptanceAdded=sorted(set(pending)-set(inv['files'])),exclusions32=inv['exclusions'],preservedPlanning25=inv['preservedW01']))
    lines=['# W02-A 验收精确提交清单','','D-076：只按此路径清单暂存。本清单在提交前保存，不预填push成功。',f'合计{len(pending)}项：原已复核174项，加{len(pending)-174}项必要验收增量。原32排除项与25份W01/规划材料另列，不提交。','', '[逐文件hash](final.inventory.json) · [精确路径](final.paths.txt) · [排除路径/hash](exclusions.json)','', '|路径|归属|','|---|---|']
    for p in pending: lines.append(f"|`{p}`|{'验收新增档案' if p not in inv['files'] else '已复核W02-A成果（直接状态档案另加验收前言）'}|")
    lines+=['','## 32项排除材料','']+['- `'+p+'`' for p in inv['exclusions']]+['','## 25份W01/规划保留材料','']+['- `'+p+'`' for p in inv['preservedW01']]
    md('final.pending-files.md','\n'.join(lines)+'\n')
    links=[]; sensitive=[]; artifacts=[]; rawwhitespace=[]
    patterns={'privateKey':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','awsKey':r'\bAKIA[A-Z0-9]{16}\b','githubToken':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'}
    for p in pending:
        if p in SELF: continue
        q=ROOT/p; text=q.read_text(encoding='utf-8',errors='replace')
        if q.suffix in ('.zip','.whl','.pyc','.exe') or any(x in q.parts for x in ('__pycache__','build','dist','.continuity-data','node_modules')): artifacts.append(p)
        for name,pat in patterns.items():
            if re.search(pat,text): sensitive.append(dict(path=p,rule=name))
        if q.suffix=='.log':
            ws=[n for n,line in enumerate(text.splitlines(),1) if line.endswith((' ','\t'))]
            if ws: rawwhitespace.append(dict(path=p,lines=ws))
        if q.suffix!='.md': continue
        if p in DOCS:
            if p.endswith('04_决策记录.md'):
                text=text[text.index('## D-076：'):]
            else:
                old_marker='<!-- PRE_P19_ACCEPTED_D074_20260920 -->' if p.endswith('05_已完成模块.md') else '<!-- W02_A_REPAIR_R1_R2_CURRENT -->'
                text=text.split(old_marker)[0]
        elif not p.startswith(PREFIX):
            # Previously audited historical documents are unchanged, but check their local links too.
            pass
        text=re.sub(r'```.*?```','',text,flags=re.S)
        for dest in re.findall(r'(?<!!)\[[^\]\n]+\]\(([^\n]+?)\)',text):
            dest=dest.strip().strip('<>')
            if re.match(r'^(https?://|mailto:|#)',dest): continue
            target=(q.parent/unquote(dest.split('#')[0])).resolve()
            rel=target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target)
            links.append(dict(source=p,target=rel,exists=target.exists() or rel in SELF,excludedLocalReference=rel in excluded))
    broken=[x for x in links if not x['exists']]
    assert not sensitive and not artifacts and not broken, ('CONTENT_CHECK',sensitive,artifacts,broken)
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True,encoding='utf-8')
    assert diff.returncode==0, 'DIFF_CHECK'
    formal=[{'relativePath':p.relative_to(ROOT/'.continuity-data').as_posix(),'fileHash':'sha256:'+sha(p)} for p in sorted((ROOT/'.continuity-data').rglob('*')) if p.is_file()]
    formal_hash='sha256:'+hashlib.sha256(json.dumps(formal,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert formal_hash==b['formalTreeHash']
    result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),errors=[],sourceCount=len(source()),sourceHash=SOURCE,sourceMatchesFinalRuns=True,
        reviewedHistoryPreserved=preserved,historicalDocBodiesPreserved=olddocs,protected=protected,formalFiles=formal,formalTreeHash=formal_hash,
        excludedUnchanged=True,excluded32=len(inv['exclusions']),planning25=len(inv['preservedW01']),pendingCount=len(pending),pending=pending,
        sourceTestsRerun=False,reviewKind=snap['reviewKind'],testResults={k:{v:r[v] for v in ('run','passed','seconds','exitCode','failures','errors','skips')} for k,r in runs.items()},
        links=links,sensitiveScan=dict(patterns=list(patterns),hits=sensitive,limitation='Scoped pattern scan plus reviewed file identities; no universal secrecy guarantee'),artifactRisks=artifacts,
        rawEvidenceWhitespacePreserved=rawwhitespace,diffCheck=dict(exitCode=diff.returncode,stdout=diff.stdout,stderr=diff.stderr),
        git=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),localOrigin=git('rev-parse','origin/main'),aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),origin=git('remote','get-url','origin'),staged=[],indexHash=sha(ROOT/'.git/index'),status=git('status','--porcelain=v1','-uall')),
        scope='Pre-commit acceptance audit; no claim of completed commit/push or remote CI',selfHashExcluded=SELF)
    put('final.audit.json',result)
    print(json.dumps(dict(errors=[],pending=len(pending),preservedReviewed=len(preserved),links=len(links),localExcludedLinks=sum(x['excludedLocalReference'] for x in links),sourceHash=SOURCE),ensure_ascii=False))


def staged_check():
    inv,b,prot,exc,plans,runs=base_checks(); approved=read(HERE/'final.inventory.json')['files']
    staged=paths('diff','--cached','--name-only','-z')
    assert set(staged)==set(approved) and len(staged)==len(approved), 'STAGED_PATH_MISMATCH'
    wrong=[]
    for p in staged:
        expected=subprocess.check_output(['git','hash-object','--path='+p,'--stdin'],input=(ROOT/p).read_bytes()).decode().strip()
        actual=git('rev-parse',':'+p)
        if expected!=actual: wrong.append(p)
    assert not wrong, wrong
    assert all(h is None or sha(ROOT/p)==h for p,h in approved.items()), 'POST_AUDIT_DRIFT'
    assert not paths('diff','--name-only','-z'), 'UNSTAGED_TRACKED_CHANGE'
    assert set(paths('ls-files','--others','--exclude-standard','-z'))==set(exc), 'UNTRACKED_NOT_EXCLUDED'
    print(json.dumps(dict(stagedCount=len(staged),allBlobIdentitiesMatch=True,excludedCount=len(exc),sourceHash=SOURCE),ensure_ascii=False))


if __name__=='__main__':
    {'snapshot':snapshot,'documents':documents,'audit':audit,'staged-check':staged_check}[sys.argv[1]]()
