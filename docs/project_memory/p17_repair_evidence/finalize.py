"""P17 R1/R2 documentation, gated on finished matching test evidence."""
from pathlib import Path
import hashlib
import json
import re
import runpy

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DOC=OUT.parent
TOP=runpy.run_path(str(DOC/'p17_evidence/finalize.py'))['TOP']
LABELS=('formal-after-02','independent-after-01','p17-final-01','compatibility-final-01','full-final-01')
IMPLEMENTATION={'src/continuity_engine/services/execution_service.py','src/continuity_engine/testing/p17_execution_fixture.py'}
NEW_TEST='tests/test_p17_repair_edges.py'

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source():
    return {p.relative_to(ROOT).as_posix():sha(p) for base in ('src','tests') for p in sorted((ROOT/base).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def summary(r):
    return f"{r['run']}项，{r['passed']} PASS / {len(r['skips'])} SKIP / {len(r['failures'])} FAIL / {len(r['errors'])} ERROR，{r['seconds']:.3f}秒，exit={r['exitCode']}"

def main():
    assert not (OUT/'final-report.md').exists(),'preserve prior report'
    current=source();before=read('before.json');runs={label:read(label+'.json') for label in LABELS}
    for label,r in runs.items():
        assert r['status']=='FINISHED' and r['exitCode']==0,label
        assert r['sourceBefore']==r['sourceAfter']==current,label
    full=runs['full-final-01'];old=set(before['testIdentities']);new=set(full['testIdentities'])-old
    assert old<=set(full['testIdentities'])
    assert all(current[p]==h for p,h in before['sourceTest'].items() if p.startswith('tests/'))
    block=('P17 R1/R2补修已实现，等待独立复核；P17 / Engine side / P17-01—P17-12 IMPLEMENTED_NOT_ACCEPTED。'
        'P00—P16 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，'
        '监工阻断待独立确认，本轮不自行关闭。D-070仅追加返修事实，D-071未创建/未使用。无Git写操作。\n\n'
        '本轮P17专项：'+summary(runs['p17-final-01'])+'；最终全量：'+summary(full)+'。原'+str(len(old))+'测试身份与断言保留，新增'+str(len(new))+'项单列。'
        '独立原探针另报，不增加Engine正式测试数。下方初版与旧全量仅为修前历史，不覆盖此次阻断。')
    for p in [ROOT/'README.md',*[DOC/name for name in TOP]]:
        text=p.read_text(encoding='utf-8')
        link=('docs/project_memory/' if p.name=='README.md' else '')+'p17_repair_evidence/final-report.md'
        marker='<!-- P17_REPAIR_CURRENT_START -->\n'+block+'\n\n[返修报告与复核入口]('+link+')。\n<!-- P17_REPAIR_CURRENT_END -->'
        text=re.sub(r'<!-- P17_REPAIR_CURRENT_START -->.*?<!-- P17_REPAIR_CURRENT_END -->',lambda _:marker,text,flags=re.S)
        p.write_text(text,encoding='utf-8')
    for number in ('79','80','81','82'):
        p=next(DOC.glob(number+'_P17_*.md'));text=p.read_text(encoding='utf-8')
        prefix='> R1/R2现行状态：IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT，等待独立复核；下方初版内容及其测试为历史。见[返修报告](p17_repair_evidence/final-report.md)。\n\n'
        p.write_text(prefix+text,encoding='utf-8')
    with (DOC/'79_P17_Execution与World架构边界.md').open('a',encoding='utf-8') as f:
        f.write('\n## R1/R2返修范围追加（2026-09-10）\n\n用户授权范围保持不变。FILES ALLOWED增量仅execution_service.py、p17_execution_fixture.py、tests/test_p17_repair_edges.py及相关档案/证据。冻结契约与原1348项测试文件不变，不重新建设P17，不D-071、不P18。首次入队/权限历史与本次返修分开记录。\n')
    with (DOC/'80_P17_规划施工测试验收矩阵.md').open('a',encoding='utf-8') as f:
        f.write('\n## R1/R2当前复核补充矩阵\n\n十二项仍为IMPLEMENTED_NOT_ACCEPTED；P17-09/P17-10为此次直接修复项，其余由完整专项及兼容验证保留。\n\n'
            '| 对应项 | 实现 | 正式回归及对照 | 本地结果 / 独立状态 |\n|---|---|---|---|\n'
            '| P17-09 / R1 | current()先资源/原gate计算，再读取授权、生命周期及恢复条件；最终调用位于Outbox事务内 | FinalAdmissionRepairTests：最终资源检查撤销Broker/Reality/Recoverability，零效果/零扣费，静态原因、显式retry、历史恢复 | 5/5 PASS；监工确认待办 |\n'
            '| P17-10 / R2 | capacity复用projected_document；实际credits来自原ActionReceipt；存储与计数交叉检查 | ActualChargeRepairTests：cost=0、默认费用、恰好够用、超限、重复、请求/消息/存储和失败回执 | 7/7 PASS；监工确认待办 |\n\n'
            '[完整原始结果](p17_repair_evidence/formal-after-02.json)，两组共12项，含在本轮P17专项中，不重复相加。原独立7项另运行且逐字节未修改。\n')
    with (DOC/'81_P17_Outbox世界恢复补偿与结果吸收语义.md').open('a',encoding='utf-8') as f:
        f.write('\n## R1/R2修正后的投递与计费语义\n\n'
            'capacity及原Context/ActionGate是投递准备，可能触发同步的资源状态变化；这些工作完成后才读取当前readiness、主体生命周期、Broker授权、Reality授权和Recoverability。最终检查在同一Outbox事务内，并仅授权紧随其后的本地同步投递，不保存可跨请求复用的许可。没有增加固定检查次数或重试循环；原三次capacity定位探针全部通过。\n\n'
            '授权读取端口应无写副作用；此边界解决已复现的本地同步资源回调变更，不承诺任意异步外部系统的瞬时撤权。Outbox锁不等于跨系统授权事务。后续每次新执行仍重新检查；原事实查询恢复不走新执行额度门。直接ExecutionError保留静态拒绝原因；原Planner未收到回执时仍按原E5-A记录UNKNOWN，不能将其说成真实执行失败。当前重新授权也不会自动重发UNKNOWN；需明确NOT_EXECUTED及既有显式retry。\n\n'
            '本Fake继续遵循现有ActionReceipt合成契约：一次成功效果=1 TEST credit，失败=0；WorldCapability.cost是原ActionGate的estimated_resource_cost，不会改写Adapter回执中的实际合成积分。cost=0仍是合法估计并能执行，但不代表该Fake的效果免积分。容量检查使用与实际写入相同的projected_document，按预计完整文档的credits/facts/effects/字节量判断，不再以route.cost替代真实积分。实际累计credits来自receipt.test_credits；读取核对事实回执、效果identity和累计积分。不改ActionReceipt/冻结契约或另建账本。\n\n'
            '补偿、取消、UNKNOWN查询、心理内容/沉默、秘密检查及旧结果撤权后排除保留。仅隔离TEST积分，不涉及真实支付；生产Adapter/恢复仍NOT_READY。\n')
    with (DOC/'82_P17_测试索引与验收入口.md').open('a',encoding='utf-8') as f:
        f.write('\n## R1/R2独立复核命令\n\n从Engine根目录运行；下列标签须未占用。所有运行使用独立Temp Fixture，原规划脚本副本不修改。\n\n```powershell\n'
            "$env:PYTHONPATH='src'\n$env:PYTHONDONTWRITEBYTECODE='1'\n$env:PYTHONUTF8='1'\n"
            'python docs/project_memory/p17_repair_evidence/run.py review-original-01 --independent-probe\n'
            'python docs/project_memory/p17_repair_evidence/run.py review-formal-01 test_p17_repair_edges\n'
            'python docs/project_memory/p17_repair_evidence/run.py review-p17-01 test_p17_\n'
            'python docs/project_memory/p17_repair_evidence/run.py review-full-01\n```\n\n'
            '[本轮报告](p17_repair_evidence/final-report.md) · [首次失败和辅助错误](p17_repair_evidence/test-history.md) · [审计](p17_repair_evidence/final.audit.json) · [精确清单](p17_repair_evidence/final.pending-files.md)。\n')
    history=['# P17 R1/R2测试历史','','数值来自同名JSON，耗时为runner含发现的时间；stderr保留unittest自身计时。独立原件的两轮3 PASS/4 FAIL为历史监工实跑，本轮重新执行另有标签。','','| 标签 | 本轮真实结果 | 原始输出 |','|---|---|---|']
    for p in sorted(OUT.glob('*.json')):
        r=json.loads(p.read_text(encoding='utf-8'))
        if 'run' in r and 'exitCode' in r:
            history.append(f'| {p.stem} | {summary(r)} | [JSON]({p.name}) / [stdout]({p.stem}.stdout.log) / [stderr]({p.stem}.stderr.log) |')
    history.extend(['','原独立7项逐字节未改：修前3 PASS/4 FAIL，修后7 PASS。R1第三次capacity定位仍有效；R2固定每效果1积分前提保留，无需改变原断言。',
        'formal-before-01中的5 FAIL覆盖R1三项及R2两项；另1 ERROR为新失败回执测试未先检查返回类型，已增加类型断言，在实现修改前formal-terminal-before-02重新保存有效FAIL。',
        'formal-after-01中R1拒绝零效果断言已通过，3 ERROR来自新测试将恢复权限误当作自动retry。原ActionPlanningService._resume在attempts存在且retry=False时返回原结果。只修正新对照：先证明自动submit仍不重发，再调用原planner.run(...,retry=True)，验证完成重放；不改原契约。',
        '其他辅助工具错误见[记录](auxiliary-errors.log)。所有首次输出保留；旧P17/P16失败、8处历史格式告警、Windows 1314 SKIP及P09 segment10 UNKNOWN不改写。',''])
    (OUT/'test-history.md').write_text('\n'.join(history),encoding='utf-8')
    report=['# P17 R1/R2返修交付','',block,'',
        'R1根因：Broker/Reality/Recoverability读取早于最终capacity同步回调，Outbox锁没有使旧授权自动保持有效。修复仅调整current()顺序，将资源和原gate工作放在授权读取前，最终投递在原事务内读取当前条件。正式测试用事务边界定位，验证三种撤销零新增效果/实际扣费、文件不变、合法显式retry及历史事实恢复。',
        'R2根因：route.cost估计被当作实际Fake积分，而原合成回执固定每成功效果1积分。修复复用实际效果投影，统一预检、文档写入和回执累计；合法cost=0保留，固定1积分语义明确，未改原ActionReceipt契约。覆盖零/默认估计、满额、重放、其他上限和失败0积分。',
        '', '实际代码增量仅：[ExecutionService](../../../src/continuity_engine/services/execution_service.py)、[P17 Fake](../../../src/continuity_engine/testing/p17_execution_fixture.py)；新增[12项正式回归](../../../tests/test_p17_repair_edges.py)。原1348项测试文件与断言逐字节保留。',
        '', '| 本轮实跑 | 结果 | 原始证据 |','|---|---|---|']
    for label,r in runs.items():report.append(f'| {label} | {summary(r)} | [JSON]({label}.json) / [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |')
    report.extend(['','P17专项包含原62项及新增12项；原独立7项单独运行，不增加Engine正式测试数，也不重复相加。前一轮1348项/1347 PASS/1 SKIP/1100.490秒仅为修前历史，本轮全量是新的实际运行。原1314 SKIP如实保留。',
        '限制：同步本地投递、无写副作用的授权读取端口、确定性Fake效果/回执和本机OS锁；没有跨系统原子撤权或生产exactly-once保证。生产Adapter/凭据/恢复及P18持续运行仍NOT_READY。正常心理内容不纳入现实边界筛查。',
        '', '[监工报告原件副本](independent/review-report.md) · [完整返修简报](independent/repair-brief.md) · [原探针](independent/test_independent_edges.py) · [全部失败历史](test-history.md) · [矩阵](../80_P17_规划施工测试验收矩阵.md) · [复跑命令](../82_P17_测试索引与验收入口.md) · [终局审计](final.audit.json) · [精确清单及排除项](final.pending-files.md)',
        '', '保护核对、源码身份和完整Git状态见终局审计。EVIDENCE_CONFLICT=PRESENT，交回独立复核，不自行验收、不创建D-071、不Git写、不进入P18。',''])
    (OUT/'final-report.md').write_text('\n'.join(report),encoding='utf-8')
    for name,title in (('03_施工日志.md','P17 R1/R2补修完成'),('04_决策记录.md','D-070 R1/R2完成事实追加（非验收）'),('10_档案修订记录.md','P17 R1/R2返修档案'),('CHANGELOG.md','P17 R1/R2工作区补修，版本仍0.1.0')):
        heading='### ' if name=='04_决策记录.md' else '## '
        with (DOC/name).open('a',encoding='utf-8') as f:f.write('\n\n'+heading+title+'（2026-09-10）\n\n'+block+'\n\n[完整返修证据](p17_repair_evidence/final-report.md)。原首次FAIL/ERROR保留，不关闭独立阻断。\n')
    previous=(OUT/'continuation.md').read_text(encoding='utf-8')
    (OUT/'continuation.md').write_text('# P17 R1/R2当前停止点\n\n'+block+'\n\n[报告](final-report.md) · [清单](final.pending-files.md) · [审计](final.audit.json)。以下为此前接续原文。\n\n'+previous,encoding='utf-8')
    print(summary(full))

if __name__=='__main__':main()
