"""Archive exact P15 independent evidence and append the user acceptance; no Git writes."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
DOC=ROOT/'docs/project_memory'
OUT=Path(__file__).resolve().parent
REVIEW=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p15-independent-review-20260908')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8').strip()
def save(p,value):
    with p.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')

def main():
    a=read(DOC/'p15_repair_evidence/final.audit.json'); b=read(DOC/'p15_repair_evidence/before.json')
    assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==a['git']['head']
    assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
    for p,h in a['pendingHashes'].items():assert sha(ROOT/p)==h,p
    for k in ('protected','plans','formalFiles','excludedP10'):
        for p,h in b[k].items():assert sha(ROOT/p)==h,p
    assert all(read(REVIEW/'repair-identity-check-20260909.json')['checks'].values())
    assert read(REVIEW/'repair-final-check-20260909.json')['engineFilesStillUnchanged']
    decision=DOC/'04_决策记录.md';dt=decision.read_text(encoding='utf-8-sig')
    assert not re.search(r'^## D-067[：:]',dt,re.M)
    files=['repair-review-report-20260909.md','repair-identity-check-20260909.json','repair-final-check-20260909.json',
        'p15_repair_review_probe.py','verify_repair_evidence.py','repair_final_check.py']
    runs={}
    for label,count in [('repair-original-probes-20260909-01',8),('repair-p15-20260909-01',71),('repair-extra-probes-20260909-01',8)]:
        files.extend(label+'.'+suffix for suffix in ('result.json','stdout.log','stderr.log','before.json','after.json'))
        r=read(REVIEW/(label+'.result.json'))
        assert r['exitCode']==0 and r['changed']==[]
        assert read(REVIEW/(label+'.before.json'))==read(REVIEW/(label+'.after.json'))
        stderr=(REVIEW/(label+'.stderr.log')).read_text(encoding='utf-8-sig')
        assert f'Ran {count} tests in ' in stderr and stderr.rstrip().endswith('OK')
        runs[label]=r
    save(OUT/'before.json',{'at':datetime.now(timezone.utc).isoformat(),'head':a['git']['head'],
        'sourceTest':a['sourceTest'],'protected':b['protected'],'plans':b['plans'],
        'formalFiles':b['formalFiles'],'formalTreeHash':b['formalTreeHash'],'excludedP10':b['excludedP10'],
        'originalPending':{p:sha(ROOT/p) for p in a['pending']},'otherPreserved':a['otherPreserved'],
        'independentRuns':runs,'remotePreflight':'actual origin refs/heads/main matched f1185d20da06f52e7e85015bc6b963cf9769d08c',
        'transportHistory':[{'command':'git ls-remote --exit-code origin refs/heads/main','context':'sandbox','exitCode':1,
            'error':'schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)'},
            {'command':'git ls-remote --exit-code origin refs/heads/main','context':'authorized host','exitCode':0}],
        'testsRunThisTurn':False})
    copies=OUT/'independent';copies.mkdir(exist_ok=False)
    archive=[]
    for name in files:
        original=REVIEW/name;target=copies/name
        with target.open('xb') as f:f.write(original.read_bytes())
        assert sha(original)==sha(target)
        archive.append({'source':str(original),'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),'bytes':target.stat().st_size})
    save(OUT/'archive-index.json',archive)
    paths=[ROOT/'README.md',*[p for p in DOC.glob('*.md') if '<!-- P15_REPAIR_CURRENT_START -->' in p.read_text(encoding='utf-8-sig')],DOC/'P15_独立复核返修_R1-R3.md']
    for p in dict.fromkeys(paths):
        text=p.read_text(encoding='utf-8-sig');assert '<!-- P15_ACCEPTED_START -->' not in text
        link=('docs/project_memory/' if p.parent==ROOT else '')+'P15_用户正式验收_20260909.md'
        block=f'''<!-- P15_ACCEPTED_START -->
> 2026-09-09 用户正式验收P15（D-067），覆盖初版及R1/R2/R3返修。P00—P15 ACCEPTED；P15 / Engine side / P15-01—P15-12 ACCEPTED；P15 Vio dependency=NONE；P16—P23 NOT_STARTED。现行PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示独立复核覆盖范围内的已知阻断闭合，不保证不存在其他缺陷。
>
> 监工独立实跑8/8、71/71、额外8/8 PASS；原8项包含在71项中，不能重复相加；额外8项不增加Engine正式测试总数。全量核验引用施工方1208项：1207 PASS、1既有WinError 1314 SKIP、0 FAIL/ERROR，1024.585秒；本次只做归档检查，没有重跑测试。
>
> [正式验收、来源及精确提交清单]({link})。用户已授权本阶段精确清单普通提交并推送现有origin/main；实际提交身份与推送结果在完成后单独核对。下方此前IMPLEMENTED_NOT_ACCEPTED、PRESENT、未使用D-067及无Git授权说明为历史快照，全部失败、辅助错误和P09 segment 10 UNKNOWN保留。正式归档/删除/可见性政策仍NOT_READY，不进入P16。
<!-- P15_ACCEPTED_END -->

'''
        p.write_text(block+text,encoding='utf-8')
    decision.write_text(decision.read_text(encoding='utf-8')+'''\n\n## D-067：用户正式验收P15及R1/R2/R3返修

2026-09-09，用户明确确认P15正式验收并授权连续完成归档、按精确清单暂存、一次普通提交、推送Engine现有origin/main及核对；不需要对同一范围重复确认。D-066开工与返修事实保留并以本决定作为正式验收引用。

独立复核原探针8 PASS、完整P15 71 PASS、新增独立8 PASS，21项身份与保护检查通过。原探针已含在71项中，新增独立8项不计入Engine1208身份。施工方全量1207 PASS/1既有1314 SKIP/0 FAIL/ERROR为经核验引用，没有冒称独立全量或本轮重跑。

P15、Engine side和十二项ACCEPTED，P00—P15 ACCEPTED，P16—P23 NOT_STARTED，Vio dependency=NONE；现行两类conflict=NONE只表示已知阻断闭合。当前未开放的正式策略与Authority边界不变；不修改Assistant/Vio，不进入P16，不创建tag/release。原失败、旧状态、P09 segment 10 UNKNOWN完整保留。

验收入口及证据见[P15正式验收](P15_用户正式验收_20260909.md)。
''',encoding='utf-8')
    matrix=DOC/'72_P15_规划施工测试验收矩阵.md';text=matrix.read_text(encoding='utf-8')
    rows=re.findall(r'^\| P15-\d{2} \|[^\n]+',text,re.M);assert len(rows)==12
    accepted=[r.replace('| IMPLEMENTED_NOT_ACCEPTED |','| ACCEPTED |').replace('本轮PASS。','施工PASS，用户按D-067验收。') for r in rows]
    marker='<!-- P15_ACCEPTED_END -->'
    current='\n\n## 十二项现行正式验收矩阵（D-067）\n\n| 项 | 范围 | 状态 | 实现责任 | 实测入口 | 结果及边界 |\n|---|---|---|---|---|---|\n'+'\n'.join(accepted)+'\n\n## 以下为初版及返修历史矩阵与结论\n'
    text=text.replace(marker,marker+current,1);matrix.write_text(text,encoding='utf-8')
    print('archived',len(archive),'independent files; updated',len(dict.fromkeys(paths)),'current documents; D-067 registered')

if __name__=='__main__':main()
