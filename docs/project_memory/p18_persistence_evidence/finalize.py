"""Archive actual completed results only; never run tests or rewrite old evidence."""
import hashlib
import json
from pathlib import Path
import runpy

OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=DOC.parents[1]
STATE='P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加调查/返修事实；D-073未创建/未使用。'
SELECTED={'formal':'formal-final-02','p18':'p18-final-01','compatibility':'compatibility-final-01','full':'full-final-01'}
CONFIG=runpy.run_path(str(DOC/'p18_evidence/prepare.py'))
DOCS=['README.md',*['docs/project_memory/'+n for n in CONFIG['TOP']+CONFIG['STAGE_FILES']]]

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(path,text):
    with path.open('x',encoding='utf8') as f:f.write(text.rstrip()+'\n')

def main():
    frozen=read(OUT/'frozen-source.json')
    current=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
    assert current==frozen['sourceTest']
    results={k:read(OUT/(name+'.json')) for k,name in SELECTED.items()}
    for k,r in results.items():
        assert r['status']=='FINISHED' and r['exitCode']==0,(k,'do not archive failure as passing')
        assert r['sourceBefore']==r['sourceAfter']==current,k
    full=results['full'];b=read(OUT/'before.json')
    assert set(b['testIdentities'])<=set(full['testIdentities'])
    assert set(full['testIdentities'])==set(frozen['testIdentities'])
    write_new(OUT/'selected-runs.json',json.dumps(SELECTED,indent=2))
    coverage={}
    history=[]
    for path in sorted(OUT.glob('*.json')):
        r=read(path)
        if 'command' not in r:continue
        coverage[path.stem]={'status':r['status'],'run':r.get('run'),'passed':r.get('passed'),
            'failures':len({x[0].split(' (')[0] for x in r.get('failures',[])}),
            'failureEntries':len(r.get('failures',[])),'errors':len(r.get('errors',[])),
            'skips':r.get('skips',[]),'seconds':r.get('seconds'),'exitCode':r.get('exitCode'),
            'sourceUnchangedDuringRun':r.get('sourceBefore')==r.get('sourceAfter'),
            'matchesFinalSource':r.get('sourceBefore')==r.get('sourceAfter')==current,
            'changedAgainstFinal':[p for p in set(current)|set(r.get('sourceAfter',{})) if current.get(p)!=r.get('sourceAfter',{}).get(p)],
            'evidenceHashes':{p.name:sha(p) for p in (path,path.with_suffix('.stdout.log'),path.with_suffix('.stderr.log'))},
            'reconstructedArchivedWriter':path.stem=='old-writer-confirm-01'}
        history.append(f"| {path.stem} | {r.get('run','UNKNOWN')} | {r.get('passed','UNKNOWN')} | {len(r.get('skips',[]))} | {len(r.get('failures',[]))}/{len(r.get('errors',[]))} | {r.get('seconds','UNKNOWN')} | {r.get('exitCode','UNKNOWN')} | [记录]({path.name}) · [输出]({path.stem}.stdout.log) · [诊断]({path.stem}.stderr.log) |")
    write_new(OUT/'test-source-coverage.json',json.dumps(coverage,ensure_ascii=False,indent=2))
    write_new(OUT/'test-history.md','# 本轮全部唯一标签与源码覆盖\n\n失败栏按unittest失败记录计；子用例可能多于失败方法，不能减去记录数伪算PASS。旧writer重建使用归档方法替换，不能作为当前实现PASS。辅助错误见 [说明](auxiliary-errors.md)。\n\n| 标签 | RUN | PASS | SKIP | FAIL记录/ERROR | 秒 | exit | 证据 |\n|---|---|---|---|---|---|---|---|\n'+'\n'.join(history)+'\n\n[逐次源码差异和输出hash](test-source-coverage.json)。所有标签不相加为正式测试总数；原探针/组间交集保留。')
    table='| 本轮实际执行组 | RUN | PASS | SKIP | FAIL/ERROR | 秒 | 证据 |\n|---|---|---|---|---|---|---|\n'
    for k,r in results.items():
        label=SELECTED[k]
        table+=f"| {k} | {r['run']} | {r['passed']} | {len(r['skips'])} | {len(r['failures'])}/{len(r['errors'])} | {r['seconds']:.3f} | [JSON]({label}.json) · [stdout]({label}.stdout.log) · [stderr]({label}.stderr.log) |\n"
    summary=f"本轮新增正式14项；P18 {results['p18']['passed']} PASS；兼容 {results['compatibility']['passed']} PASS；最终全量 {full['run']} 项={full['passed']} PASS、{len(full['skips'])}既有1314 SKIP、0 FAIL/ERROR，{full['seconds']:.3f}秒，exit=0。原1466身份及断言保留，各组有交集，不重复相加。"
    report=f'''# P18 持久化与恢复链定向返修交付

{STATE}

{summary}

本轮修复已实现，等待独立复核。没有自动验收、D-073、Git写操作、Assistant修改或P19施工。持续运行入口、资源局部等待及Owner/Subject停止要求不变。

## 实际完成

真实Windows仓储读句柄与SubjectState原子替换竞争已稳定复现：受控实验 PermissionError/errno13/winerror5，DELETE-access探针32。P18在现有Evolution写入作用域内对已确认短时共享冲突有界等待，重试前重查Context/控制及原文件字节版本；不无条件重试文件错误。写/flush/fsync失败的临时路径登记及清理错误覆盖主异常亦已实测并最小修复。详见 [根因调查](investigation.md)。

只改3个既有源码文件，新增1份TEST诊断和1份正式测试，完整路径见 [精确清单](final.pending-files.md)。原Runtime/Scheduler资源及单宿主R1修复、ThinkSession调用阶段R2修复保留，未新增账本或状态权威。原ActionEvolution仍持有合法状态演化责任。

已执行事实恢复使用原回执与ThinkSession：未提交状态可在故障解除、查询到期后续接；已经提交返回丢失不重复revision；重开后Provider不重复调用、效果/credits各1，usage身份不变且合法结算。真正UNKNOWN仍保守，不把错误字符串当未执行证明。

## 证据与验证

修前有效两项读竞争反例、同流程正常对照，旧writer精确重建两项FAIL；修复过程及辅助错误完整保存于 [测试历史](test-history.md)。原F2用例修前单跑1 PASS不构成历史关闭。原14项新增定点包括读句柄、长期占用、非共享错误、保存步骤、诊断兜底、清理原因链、版本变化、控制与权限、重启和幂等恢复。

{table}

上表都是本轮新执行，不冒称独立复核或远端CI。只有最终源码固定后的一次全量；原1466的历史全量仍是1464 PASS/1 SKIP/1 FAIL。原R2专项106与兼容490属于旧版本历史，源码变更后没有借用为本轮覆盖。原五组独立/施工记录、未完成全量及F1/H1全部原样保留。

最终源码/测试/资源267份，指纹 `{frozen['sourceHash']}`。每组运行前后与frozen-source一致；原1466正式测试文件均未改，新增14另计。[逐组覆盖](test-source-coverage.json)明确中间版本差异。既有Windows符号链接1314为SKIP，未新增跳过。

## F2、F1、H1分别结论

- F2：同阶段、同外部事实已完成但状态未保存的风险已稳定复现并最小修复；当前有真实OS5及共享探针32证据。历史F2本身缺异常类型/系统码和句柄身份，不能声称已唯一确定那次具体原因。当前防护覆盖这个风险，等待独立确认。
- F1：缺历史失败时ThinkSession阶段、完整异常链，继续UNKNOWN。不能据第二轮token640或UNKNOWN推断与F2/R2同源。
- H1：缺清理前可信时间/next_check_at/任务水位，继续UNKNOWN。不能据当前PASS、Windows性能或软件中断归因。

没有充分依据关闭历史问题；EVIDENCE_CONFLICT保持PRESENT。本轮诊断在STOP/清理之前保存受控相对路径、hash/revision、OS类型与码、原因链、身份、PID/线程和锁状态；独立stderr有一次有限兜底，不泄漏异常正文或改变对外脱敏。长占用超过0.25秒仍真实失败；若清理被OS拒绝可能留下一个自建tmp，生产清除/备份恢复不在本轮范围。未承诺任意Adapter exactly-once。

## 保护与交付入口

[终局审计](final.audit.json)核对63保护、3规划、正式7文件、版本0.1.0/pyproject、32排除项、旧354成果及所有历史证据；正式树仍为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。源码范围、原断言、AST、链接、敏感候选、git diff --check、精确待提交清单和完整Git状态分别记录，旧日志格式告警原样保留。

本轮测试进程由控制器STOP/退出后回收，细节在stdout和 [终局进程核查](process-check.json)，不清理无关目录或进程。main/HEAD/localorigin保持P17基线；没有Git写、没有联网远端查询、没有新CI结果，不宣称CI PASS。

在Engine根设置PYTHONPATH=src、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1，用未占用标签执行：

```powershell
python docs/project_memory/p18_persistence_evidence/run.py review-formal-01 test_p18_persistence
python docs/project_memory/p18_persistence_evidence/run.py review-p18-01 test_p18_
```

兼容与全量的准确实际命令见上表JSON。旧writer反例的独立重建入口为 `run.py review-old-writer-01 --review-class old_writer_probe.OldWriterEvidence`，预期两项FAIL，只可在TEST根复现。正常启动/控制仍见 [P18入口](../86_P18_测试索引与验收入口.md)。完成后停在P18，交回独立复核。
'''
    write_new(OUT/'final-report.md',report)
    matrix=read(DOC/'p18_r2_evidence/matrix-test-map.json')
    added=set(frozen['added']);p18ids=set(results['p18']['testIdentities'])
    for key,row in matrix.items():
        ids=set(row['testIdentities'])
        if key in {'P18-05','P18-08','P18-09','P18-11','P18-12'}:ids|=added
        row.update(testIdentities=sorted(ids),evidence=[SELECTED['p18'],SELECTED['full']],status='IMPLEMENTED_NOT_ACCEPTED',
                   limitation='F2受控风险已修，历史排他根因未证实；F1/H1 UNKNOWN；独立复核待完成')
    assert set().union(*(set(v['testIdentities']) for v in matrix.values()))==p18ids
    write_new(OUT/'matrix-test-map.json',json.dumps(matrix,ensure_ascii=False,indent=2))
    newtable='| 项目 | 现行状态 | 交叉测试身份 | 当前覆盖 |\n|---|---|---|---|\n'+''.join(f"| {key} | IMPLEMENTED_NOT_ACCEPTED | {len(row['testIdentities'])} | 本轮P18及全量通过；历史证据限制不关闭 |\n" for key,row in matrix.items())
    for name in DOCS:
        p=ROOT/name;old=p.read_text(encoding='utf8');prefix='docs/project_memory/' if name=='README.md' else ''
        marker='<!-- P18_PERSISTENCE_CURRENT -->'
        assert marker not in old,name
        block=marker+'\n'+STATE+'\n\n'+summary+'\n\nF2同阶段共享竞争风险已复现并最小修复；历史具体OS码/句柄缺失不补写。F1/H1仍UNKNOWN。当前不自行关闭独立复核阻断。\n\n[本轮调查/完整报告]('+prefix+'p18_persistence_evidence/final-report.md) · [终局审计与逐文件清单]('+prefix+'p18_persistence_evidence/final.pending-files.md)。\n\n'
        if p.name.startswith('84_'):block+=newtable+'\n[本轮矩阵身份映射](p18_persistence_evidence/matrix-test-map.json)。\n\n'
        if p.name.startswith('83_'):block+='本次用户追加授权限定P18持久化/恢复根因调查与最小修复。FILES ALLOWED增量：src/continuity_engine/storage/json_repository.py、services/wake_perception_thinking_action_service.py、testing/p18_runtime_fixture.py、testing/p18_persistence_diagnostics.py、tests/test_p18_persistence.py及本轮证据/直接档案；services/testing项均在src/continuity_engine下。冻结/正式数据/规划/版本/排除项禁止修改。\n\n'
        block+='## 下方为此前阶段记录与历史证据\n\n'
        p.write_text(block+old,encoding='utf8')
    with (DOC/'04_决策记录.md').open('a',encoding='utf8') as f:
        f.write('\n### D-072追加：P18持久化与恢复链定向调查返修（非验收）\n\n用户授权固定F2现场、比较F1/H1并按可复现证据做最小修复。当前共享竞争有界重试、当前门禁/版本复核及TEST诊断/保存阶段清理修复已实现；原R1/R2保留。'+summary+' 历史F2具体系统码缺失，F1/H1继续UNKNOWN；EVIDENCE_CONFLICT=PRESENT，D-073未创建/未使用，不Git写、不P19。证据见 [完整报告](p18_persistence_evidence/final-report.md)。\n')
    with (OUT/'continuation.md').open('a',encoding='utf8') as f:
        f.write('\n## 当前施工完成\n\n'+summary+'\n\n'+STATE+' F1/H1 UNKNOWN；F2同阶段风险已修，历史排他原因未证实。最终结果索引selected-runs.json；源码固定，不再启动测试。完成审计后交回独立复核。\n')
    print(json.dumps({'docs':len(DOCS),'source':len(current),'full':full['run'],'passed':full['passed']}))

if __name__=='__main__':main()
