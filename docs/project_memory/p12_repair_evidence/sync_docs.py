"""P12 repair navigation only; preserve initial implementation and raw evidence."""
from pathlib import Path
import hashlib
import json
import re
import sys

root=Path(__file__).resolve().parents[3]
directory=Path(__file__).resolve().parent
final=sys.argv[1:]==['final']
special=json.loads((directory/'p12-stable-02.tests.json').read_text(encoding='utf-8'))
assert special['status']=='FINISHED' and not special['errors'] and not special['failures']
summary=f"本轮 P12 专项 {special['run']}/{special['run']} PASS（{special['seconds']:.3f} 秒）。"
if final:
    compat=json.loads((directory/'compatibility-affected-02.tests.json').read_text(encoding='utf-8'))
    full=json.loads((directory/'full-stable-02.tests.json').read_text(encoding='utf-8'))
    for run in (compat,full):
        assert run['status']=='FINISHED' and not run['errors'] and not run['failures']
        assert run['sourceTest']==special['sourceTest']
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in full['sourceTest'].items())
    summary+=f"兼容 {compat['run']} 项：{compat['passed']} PASS、{len(compat['skips'])} 既有 SKIP，{compat['seconds']:.3f} 秒；稳定全量 {full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP，0 FAIL/ERROR，{full['seconds']:.3f} 秒。"
else:
    summary+='兼容组合与稳定全量尚未完成，不预填结果。'
names=['README.md',*['docs/project_memory/'+n for n in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
    '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md','59_P12_IntentionalForgetting架构边界.md',
    '60_P12_规划施工测试验收矩阵.md','61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md')]]
for name in names:
    p=root/name; text=p.read_text(encoding='utf-8')
    prefix='docs/project_memory/' if name=='README.md' else ''
    text=text.replace('> P12 现行施工状态（2026-09-06，D-060）','> P12 初版施工历史状态（2026-09-06，D-060）',1)
    text=re.sub(r'\n> 2026-09-07 P12 有界返修现行状态：[^\n]*\n','\n',text,count=1)
    block='''<!-- P12_REPAIR_CURRENT_START -->
> P12 有界返修现行状态（2026-09-07，D-060）：P00—P11 ACCEPTED；P12 / Engine side / P12-01—12 IMPLEMENTED_NOT_ACCEPTED；P12 Vio dependency=NONE；P13—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT（独立复核阻断待监工确认关闭）。'''+summary+f'''
>
> [五项返修、原始失败及独立复核入口]({prefix}P12_独立复核返修_R1-R5.md)。初版 71/965 与其 NONE 状态作为历史保留，不能代替本轮结果。不登记用户验收，不执行 Git 写操作，不进入 P13；生产自动策略/物理删除仍未开放。
<!-- P12_REPAIR_CURRENT_END -->'''
    if '<!-- P12_REPAIR_CURRENT_START -->' in text:
        text=re.sub(r'<!-- P12_REPAIR_CURRENT_START -->.*?<!-- P12_REPAIR_CURRENT_END -->',lambda _:block,text,count=1,flags=re.S)
    else:
        index=text.index('\n')+1; text=text[:index]+'\n'+block+'\n'+text[index:]
    p.write_text(text,encoding='utf-8')

facts={
 '04_决策记录.md':('D-060：2026-09-07 有界返修事实补记', '用户经规划监工明确同意本轮五项返修；本轮不是验收。现场 202 项源码/测试 hash 对应原稳定全量，保留完整 P12 工作区。修改前原探针实际 3 PASS、6 FAIL，1.081 秒，已据此登记 EVIDENCE_CONFLICT=PRESENT。仅五个运行文件、必要正式回归和相关档案；不得沿用旧 Git 授权，不创建 D-061。'),
 '59_P12_IntentionalForgetting架构边界.md':('P12-R1—R5 Stage Brief 范围补记', 'FILES ALLOWED 在原列表内限定五个运行文件：domain/memory.py、services/memory_lifecycle_service.py、services/memory_consolidation_service.py、storage/json_memory_repository.py、services/context_router_service.py；新增 tests/test_p12_memory_review_regressions.py 和 tests/test_p12_memory_weight_windows.py、p12_repair_evidence/ 和五项返修说明。其他原文件只同步直接档案。原件、旧测试、已有证据和保护边界均不变；NOT READY 策略不变。'),
 '60_P12_规划施工测试验收矩阵.md':('本轮返修与原十二项的对应', 'R1 对应 P12-02/05，R2 对应 01/06/10，R3 对应 10，R4 对应 04/07/08/10，R5 对应 03/07/08/12。原十二项继续 IMPLEMENTED_NOT_ACCEPTED；初版测试身份映射仅表示初版实测，不覆盖本轮新反例。原 71 项保留，新增原探针 9 项、扩展 16 项及 R5 窄窗口 2 项共同验证。'),
 '61_P12_生命周期恢复删除与传播语义.md':('返修后的交付边界', '来源 Port 返回后及历史正文发放前重验授权、目标和来源；P12 后继版本不得丢弃已存在治理字段。嵌套合法提交保留，外层文档改变明确失败，不自动重试。首次 consolidation alias 在仓储事务和结果交付边界分别重验；历史事实不等于当前材料授权。同根消费上限由当前同一 Memory 文档投影，不序列化 consumption_weight、不改事实 confidence 或旧 canonical hash；独立新根不受无关根降权影响。'),
 '62_P12_测试索引与验收入口.md':('返修证据现行入口', '本轮新增正式回归 test_p12_memory_review_regressions.py；规划原探针原件继续可直接运行。初版 run_suite/audit/清单保留历史，不覆盖旧日志；当前命令、源清单、逐项结果与限制见五项返修说明。'),
 '03_施工日志.md':('P12 独立复核五项有界返修', '保存修前原探针六条 FAIL，再修复 R1—R5。扩展验证真实记录过严字段连续性检查造成的兼容失败，以及测试构造错误；没有删除断言或把 ERROR 改 SKIP。'),
 '05_已完成模块.md':('P12 五项边界补修已实现、未验收', '补历史召回交付检查、治理字段连续性、重入文档保护、首次 alias 当前性及同根消费权重投影；完整证据等待独立复核。'),
 '05_核心模块架构.md':('P12 补修责任边界', '仍使用唯一 JsonMemoryRepository 文档和 lineage；只读消费权重投影不是新权威，回调后的重读比较不是新账本，不改已有 Action/Evolution/E5-A 边界。'),
 '06_未完成事项.md':('P12 返修待复核', '五项本地修复与验证结果提交独立复核；监工尚未确认关闭前 EVIDENCE_CONFLICT=PRESENT，未登记用户验收。P13—P23 NOT_STARTED。'),
 '07_待确认事项.md':('P12 策略与验收仍待定', '本轮用户同意的是返修，不是阶段验收。正式遗忘阈值、归档年限和删除确认策略不变；不启用生产删除或自动清理。'),
 '10_档案修订记录.md':('P12 返修档案追加', '保留所有原证据，新增 p12_repair_evidence/、正式回归及五项返修说明；将初版现行导航标明为历史，并追加本轮当前状态。'),
 'CHANGELOG.md':('P12 五项有界修复（未验收，版本 0.1.0）', '修复召回后授权/状态变化、治理后继字段丢失、重入成功提交被覆盖、首次 consolidation alias 交错和同根降权绕过。'),
 '工程总档案.md':('P12-R1—R5 当前交付', '本轮仅修复独立复核发现的五项，不重新开展阶段建设。初版历史和旧全量引用保持；用户验收尚未发生。'),
}
for name,(title,body) in facts.items():
    p=root/'docs/project_memory'/name; text=p.read_text(encoding='utf-8')
    marker='<!-- P12_REPAIR_FACT -->'
    block=marker+'\n\n## '+title+'\n\n'+body+' '+summary+' [本轮入口](P12_独立复核返修_R1-R5.md)。\n<!-- P12_REPAIR_FACT_END -->'
    if marker in text:
        text=re.sub(marker+'.*?<!-- P12_REPAIR_FACT_END -->',lambda _:block,text,count=1,flags=re.S)
    else: text+='\n'+block+'\n'
    p.write_text(text,encoding='utf-8')
if final:
    p=root/'docs/project_memory/P12_独立复核返修_R1-R5.md'; text=p.read_text(encoding='utf-8')
    text=text.replace('等待本轮验证和独立复核','本轮验证已完成，等待独立复核')
    text=text.replace('兼容组合与最终稳定全量完成后追加真实结果；不预填通过数量。',
        summary+' [最终受影响兼容记录](p12_repair_evidence/compatibility-affected-02.tests.json)、[最终稳定全量记录](p12_repair_evidence/full-stable-02.tests.json)。全量 SKIP 为原 Windows symlink 1314，不计 PASS；Engine 无 Actions workflow，不报告远程 CI。')
    p.write_text(text,encoding='utf-8')
print(json.dumps({'final':final,'navigationFiles':len(names),'summary':summary},ensure_ascii=False))
