"""Append second repair facts; preserve prior failures and historical results."""
import hashlib
import json
from pathlib import Path
import re
import sys

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
final=sys.argv[1:]==['final']
special=json.loads((directory/'p12-final.tests.json').read_text(encoding='utf-8'))
assert special['status']=='FINISHED' and not special['failures'] and not special['errors']
summary=f"本轮 P12 {special['run']}/{special['passed']} PASS，{special['seconds']:.3f} 秒；新 7 条与原 9 条探针均 PASS（1.090 / 1.327 秒）。"
if final:
    compat=json.loads((directory/'compatibility-final.tests.json').read_text(encoding='utf-8'))
    full=json.loads((directory/'full-final.tests.json').read_text(encoding='utf-8'))
    for run in (compat,full):
        assert run['status']=='FINISHED' and not run['failures'] and not run['errors']
        assert run['sourceTest']==special['sourceTest']
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in full['sourceTest'].items())
    summary+=f"兼容 {compat['run']} 项：{compat['passed']} PASS、{len(compat['skips'])} SKIP，{compat['seconds']:.3f} 秒；全量 {full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP、0 FAIL/ERROR，{full['seconds']:.3f} 秒。"
else:
    summary+='兼容及最终全量尚未全部结束，不预填结果。'
names=['README.md',*['docs/project_memory/'+n for n in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
    '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md','59_P12_IntentionalForgetting架构边界.md',
    '60_P12_规划施工测试验收矩阵.md','61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md')]]
for name in names:
    path=root/name; text=path.read_text(encoding='utf-8')
    prefix='docs/project_memory/' if name=='README.md' else ''
    text=text.replace('> P12 有界返修现行状态（2026-09-07，D-060）','> P12 第一轮返修历史状态（2026-09-07，D-060）',1)
    block='''<!-- P12_SECOND_CURRENT_START -->
> P12 第二轮 F1/F2 返修现行状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，等待独立复核。'''+summary+f'''
>
> [本轮修改、失败历史与复核入口]({prefix}P12_第二轮返修_F1-F2.md)。下方第一轮及初版结果均为历史，不能代替本轮。保留 117 项首次兼容失败、前轮全部 FAIL/ERROR/SKIP 和 P09 segment 10 UNKNOWN。没有用户验收决定，没有 Git 写操作。
<!-- P12_SECOND_CURRENT_END -->'''
    if '<!-- P12_SECOND_CURRENT_START -->' in text:
        text=re.sub(r'<!-- P12_SECOND_CURRENT_START -->.*?<!-- P12_SECOND_CURRENT_END -->',lambda _:block,text,count=1,flags=re.S)
    else:
        index=text.index('\n')+1; text=text[:index]+'\n'+block+'\n'+text[index:]
    path.write_text(text,encoding='utf-8')

facts={
    '04_决策记录.md':('D-060：2026-09-07 第二轮 F1/F2 返修事实补记',
        '本轮沿用用户明确同意的有界返修，仅修改 Memory 仓储当前消费投影和旧 Retriever，新增正式回归。未创建 D-061 或用户验收决定。今晚提交例外必须在规划监工另发独立复核通过及明确 Git 收尾通知后才能适用，且最迟 2026-09-07 08:00 Asia/Shanghai；当前没有该通知，不执行 Git 写操作，也不把它扩大为自行验收。'),
    '03_施工日志.md':('2026-09-07：P12 同根副本与旧检索入口第二轮返修',
        '修改前新监工探针 3 PASS/4 FAIL，1.155 秒；正式扩展 8 PASS/10 FAIL，3.108 秒。修复后扩展 19 PASS，5.065 秒；首次完整专项 116 PASS/1 FAIL，29.023 秒，暴露纯数值降权被误作同根摘要持久失效。保留旧 R5 断言，将扩展持久失效限定为停用/归档/删除/恢复后再跑专项和一次最终全量；所有首次输出原样保留。'),
    '59_P12_IntentionalForgetting架构边界.md':('P12-F1/F2 Stage Brief 范围补记',
        'FILES ALLOWED：本轮运行代码仅 src/continuity_engine/storage/json_memory_repository.py、src/continuity_engine/services/memory_service.py；新增 tests/test_p12_memory_second_review.py、P12_第二轮返修_F1-F2.md、p12_second_repair_evidence/，以及本档和直接导航 18 份档案。SOURCE OF TRUTH 为本轮授权、只读 p12-recheck-20260907 报告及原七条探针；其他原 Stage Brief 和 NOT READY 边界继续适用。先验证旧 204 文件与前轮全量 hash 一致，未重跑修改前全量。'),
    '60_P12_规划施工测试验收矩阵.md':('第二轮 F1/F2 与十二项的对应',
        'F1 对应 P12-04/05/06/07/08/10/12，F2 对应 P12-01/03/04。新增 19 项包括原七条监工探针与十二条摘要、exact、旧窗口、当前恢复、拒绝零写入、旧温度及正常 C1 组合；原 98 项专项和 992 项全量身份保留。每项仍 IMPLEMENTED_NOT_ACCEPTED，不把测试 PASS 当作验收。'),
    '61_P12_生命周期恢复删除与传播语义.md':('第二轮同根当前可用性与兼容处理',
        '显式 inactive/archived/deleted 将同根消费上限设为零；当前可用性重验应用此投影。停用/归档/删除/恢复使同根依赖摘要持久失效，旧摘要须重建；纯数值降权仍使用当前权重及窗口指纹，合法非零摘要不被误排除。显式父版本子链仍按原绑定校验。旧 Retriever 在评分前排除不可用项，minimum_relevance=0 保持合法。历史召回不能绕过已 deleted 的根；允许的 archive 审计和原始 Event 历史仍保留。'),
    '62_P12_测试索引与验收入口.md':('第二轮定点、兼容与最终全量入口',
        '所有新命令/退出码/起止时间/测试身份/源码 hash/stdout/stderr 在 p12_second_repair_evidence。原探针及历史证据只读，真实 Windows symlink 1314 SKIP 不计 PASS；Engine 没有 Actions workflow，不报告远程 CI。'),
    '10_档案修订记录.md':('2026-09-07：F1/F2 第二轮证据与导航',
        '新增第二轮报告及独立证据目录，同步当前状态、D-060、59—62、索引、README 与汇总。第一轮原报告、审计、精确清单及所有原始日志不改。'),
    'CHANGELOG.md':('2026-09-07 P12 第二轮修复（未提交、未验收）',
        '修复治理前同根副本绕过生命周期，以及零权重副本经旧 MemoryService 被选中；保留非零降权、授权恢复、独立新证据和旧数据兼容。版本保持 0.1.0。'),
}
for name,(title,fact) in facts.items():
    path=root/'docs/project_memory'/name; text=path.read_text(encoding='utf-8')
    block='<!-- P12_SECOND_FACT_START -->\n\n## '+title+'\n\n'+fact+' '+summary+' [第二轮证据](P12_第二轮返修_F1-F2.md)。\n<!-- P12_SECOND_FACT_END -->'
    if '<!-- P12_SECOND_FACT_START -->' in text:
        text=re.sub(r'<!-- P12_SECOND_FACT_START -->.*?<!-- P12_SECOND_FACT_END -->',lambda _:block,text,count=1,flags=re.S)
    else:
        text=text.rstrip()+'\n\n'+block+'\n'
    path.write_text(text,encoding='utf-8')
print('Updated 18 navigation documents; runtime/tests unchanged.')
