"""Synchronize only P12 current navigation; retain dated earlier evidence."""
from pathlib import Path
import hashlib
import json
import re
import sys

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
final=sys.argv[1:] == ['final']
state='IMPLEMENTED_NOT_ACCEPTED' if final else 'IN_PROGRESS'
target=json.loads((directory/'p12-final-code.tests.json').read_text(encoding='utf-8'))
compat=json.loads((directory/'compatibility-final.tests.json').read_text(encoding='utf-8'))
full=json.loads((directory/'full-final.tests.json').read_text(encoding='utf-8'))
if final:
    assert full['status']=='FINISHED' and not full['failures'] and not full['errors']
    assert target['sourceTest']==full['sourceTest']==compat['sourceTest']
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in full['sourceTest'].items())
    assert not compat['failures'] and not compat['errors']
    full_summary=f"{full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP、0 FAIL/ERROR，{full['seconds']:.3f} 秒"
else:
    full_summary='稳定版完整回归进行中，未预填结果'
summary=f"专项 {target['run']}/{target['run']} PASS（{target['seconds']:.3f} 秒）；兼容 {compat['run']} 项：{compat['passed']} PASS、{len(compat['skips'])} 既有 SKIP（{compat['seconds']:.3f} 秒）；{full_summary}。"
general=['README.md',*['docs/project_memory/'+n for n in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
    '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md')]]
for name in general:
    p=root/name; content=p.read_text(encoding='utf-8')
    prefix='docs/project_memory/' if name=='README.md' else ''
    conflict='NONE' if final else 'PRESENT（施工验证尚未全部完成）'
    block=f'''<!-- P12_CURRENT_START -->
> P12 现行施工状态（2026-09-06，D-060）：P00—P11 = ACCEPTED；P12 / Engine side / P12-01—P12-12 = {state}；P12 Vio dependency = NONE；P13—P23 = NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT={conflict}。{summary}本轮只施工、测试和档案同步；不自行验收、不执行 Git 写操作、不修改 Assistant、不进入 P13。
>
> [P12 Stage Brief]({prefix}59_P12_IntentionalForgetting架构边界.md) · [十二项矩阵]({prefix}60_P12_规划施工测试验收矩阵.md) · [生命周期/恢复/删除语义]({prefix}61_P12_生命周期恢复删除与传播语义.md) · [独立复核与证据入口]({prefix}62_P12_测试索引与验收入口.md)。正式遗忘阈值、归档年限、永久删除确认方式未决定；生产自动策略未配置，物理擦除 NOT_READY。历史失败、SKIP 和 P09 segment 10 UNKNOWN 原样保留。
<!-- P12_CURRENT_END -->'''
    content=content.replace('> 当前验收（2026-09-06，D-059）','> P12 开工前验收历史（2026-09-06，D-059）',1)
    content=content.replace('> P11 现行门：','> P11 验收时历史门：',1)
    content=content.replace('> P12 开工现行状态（D-060）','> P12 开工历史快照（D-060）',1)
    if '<!-- P12_CURRENT_START -->' in content:
        content=re.sub(r'<!-- P12_CURRENT_START -->.*?<!-- P12_CURRENT_END -->',lambda _:block,content,count=1,flags=re.S)
    else:
        index=content.index('\n')+1
        content=content[:index]+'\n'+block+'\n'+content[index:]
    if name=='README.md':
        content=content.replace('可解释 HOT/WARM/COLD/ARCHIVED 生命周期','可解释 HOT/WARM/COLD/ARCHIVED 温度',1)
    p.write_text(content,encoding='utf-8')

if final:
    p=root/'docs/project_memory/60_P12_规划施工测试验收矩阵.md'
    text=p.read_text(encoding='utf-8').replace('| IN_PROGRESS |','| IMPLEMENTED_NOT_ACCEPTED |')
    text=text.replace('当前施工验证进行中，未验收','当前十二项施工与规定验证已完成，状态 IMPLEMENTED_NOT_ACCEPTED，等待独立复核及用户验收')
    text+='\n终局实跑：'+summary+' 所有矩阵项引用同一组真实测试身份，不重复计数。现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE；这表示已发现的施工失败均已闭合，不代表用户验收。\n'
    p.write_text(text,encoding='utf-8')
    p=root/'docs/project_memory/62_P12_测试索引与验收入口.md'; text=p.read_text(encoding='utf-8')
    text=text.replace('施工验证进行中，尚未正式验收','施工与验证已完成，IMPLEMENTED_NOT_ACCEPTED，等待独立复核及用户正式验收',1)
    text=text.replace('兼容组合和稳定完整回归完成后追加真实结果，不预填数量或 PASS。',
        f"[兼容终局](p12_evidence/compatibility-final.tests.json)：{compat['run']} 项，{compat['passed']} PASS、{len(compat['skips'])} 既有 SKIP，0 FAIL/ERROR，{compat['seconds']:.3f} 秒；[本轮唯一稳定全量](p12_evidence/full-final.tests.json)：{full_summary}。两者 SKIP 都是原 Windows symlink 1314，不计 PASS。全量保存完整测试身份与源码 hash，原 894 身份和原测试文件完整保留。")
    text+='\n## 终局复核档案\n\n[只读审计](p12_evidence/final-audit.json) · [精确工作区清单](p12_evidence/pending-files.md)。基线和终局正式七文件、25 冻结边界（包含六 Schema 和 pyproject）、版本 0.1.0、三规划源和 31 个原有 P10 脚本逐项核对；既有原始证据没有修改。\n\nP12 / Engine side / P12-01—12 = IMPLEMENTED_NOT_ACCEPTED；Vio dependency=NONE；P00—P11 ACCEPTED，P13—P23 NOT_STARTED。没有本阶段用户验收决定，没有 Git 写操作。\n'
    p.write_text(text,encoding='utf-8')
    for name,title,body in (
        ('03_施工日志.md','P12 施工与验证收口',summary+' 原始失败、兼容修正、辅助错误及长期观察详见 62；保持 IMPLEMENTED_NOT_ACCEPTED，交回独立复核。'),
        ('05_已完成模块.md','P12 已实现、尚未验收', '已有 Memory/lineage 内的生命周期命令、当前授权/来源绑定、显式确定性衰减、普通检索排除、有限历史召回、不可恢复逻辑删除、Summary/Context/Learning 失效传播及正常 C1 入口已实现。'+summary),
        ('06_未完成事项.md','P12 现行待办', 'P12 实现与本轮测试已完成；等待规划监工独立复核和用户正式验收。正式策略、物理删除/备份清除仍未开放。之前 P11 与前审查记录中的等待 P12 开工属于历史；本轮已由用户授权开工。P13—P23 未开始。'),
        ('07_待确认事项.md','P12 用户策略待定', '遗忘阈值、归档年限、永久删除确认方式仍待用户决定。TEST 数值不是正式默认；生产自动策略未配置/关闭。P12 独立复核及正式验收尚待完成；不创建验收决定。'),
        ('05_核心模块架构.md','P12 Memory 生命周期接线', 'MemoryLifecycle 与 MemoryStatus/Temperature 分离；原 JsonMemoryRepository 的同一文档承载版本及 lifecycle lineage。Memory/传递来源/Summary 的当前可用性贯穿 Router、Composer、正常 C1 和 Learning；不新增 Authority，不写 Event/SubjectState，不接生产删除。'),
        ('10_档案修订记录.md','P12 本轮档案同步', '新增 59—62 专题、D-060、逐项矩阵与 p12_evidence；同步现行导航，保留历史验收及所有原始失败。纯档案调整后核对稳定源码 hash，不机械重复全量。'),
        ('CHANGELOG.md','P12 Intentional Forgetting（未验收，0.1.0 不变）', '实现 Memory 生命周期、确定性权重及跨 Summary/Context/Learning 传播；复用原 lineage/仓储和正常 C1。'+summary+' 生产自动策略/物理删除未开放。'),
        ('工程总档案.md','P12 当前工程交付', 'Stage Brief 与十二项矩阵、生命周期语义、可运行 TEST 入口及证据分别位于 59—62。'+summary+' P12 IMPLEMENTED_NOT_ACCEPTED；等待独立复核，不提交、不启动后续阶段。'),
        ('04_决策记录.md','D-060 本轮施工结果补记（非用户验收）',summary+' 十二项 IMPLEMENTED_NOT_ACCEPTED；当前两类 conflict 均 NONE。生产策略仍待用户决定；不创建本阶段用户验收决定，不执行 Git 写操作。')
    ):
        p=root/'docs/project_memory'/name
        content=p.read_text(encoding='utf-8')
        content+='\n\n## '+title+' — 2026-09-06\n\n'+body+' [P12 独立复核入口](62_P12_测试索引与验收入口.md)。\n'
        p.write_text(content,encoding='utf-8')
print(json.dumps({'phase':'final' if final else 'in_progress','generalFiles':general,'summary':summary},ensure_ascii=False))
