"""Complete P17 documentation only after actual stable test evidence exists."""
from pathlib import Path
import json
import re
import hashlib

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DOC=OUT.parent
FINAL_P17='p17-final-03'
FINAL_FULL='full-final-02'
COMPAT='compatibility-final-01'
LATE_FILES={'src/continuity_engine/services/execution_service.py',
            'src/continuity_engine/services/execution_ports.py',
            'src/continuity_engine/testing/p17_execution_fixture.py',
            'tests/test_p17_boundaries.py'}
TOP=['00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
     '05_核心模块架构.md','05_已完成模块.md','06_未完成事项.md','07_待确认事项.md',
     '08_未来扩展.md','10_档案修订记录.md','11_P00_全周期能力与阶段基线.md',
     '12_P00_规划施工测试验收矩阵.md','13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md']

def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))

def result_summary(r):
    return f"{r['run']}项：{r['passed']} PASS、{len(r['skips'])} SKIP、{len(r['failures'])} FAIL记录、{len(r['errors'])} ERROR记录；{r['seconds']:.3f}秒，退出码{r['exitCode']}"

def main():
    labels=(FINAL_P17,COMPAT,FINAL_FULL)
    records={label:read(label+'.json') for label in labels}
    source={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    for label,r in records.items():
        assert r['status']=='FINISHED' and r['exitCode']==0,label
        assert r['sourceBefore']==r['sourceAfter'],label
        if label==COMPAT:
            assert {p for p in set(source)|set(r['sourceAfter']) if source.get(p)!=r['sourceAfter'].get(p)}==LATE_FILES
        else:
            assert source==r['sourceBefore'],label
    baseline=read('before.json')
    full=records[FINAL_FULL];original=set(baseline['testIdentities']);current=set(full['testIdentities'])
    assert original<=current
    assert set(records[COMPAT]['testIdentities'])<=current
    assert all(source[p]==h for p,h in baseline['sourceTest'].items() if p.startswith('tests/'))
    short='；'.join(name+'：'+result_summary(records[label]) for name,label in
        (('最终专项',FINAL_P17),('末次局部补修前兼容（终局全量再次覆盖其全部身份）',COMPAT),('最终全量',FINAL_FULL)))
    block=('当前P17施工、测试及档案已完成（D-070），P17 / Engine side / P17-01—P17-12 IMPLEMENTED_NOT_ACCEPTED，交回独立复核；'
           'P00—P16 ACCEPTED；P17 Vio dependency=NONE；P18—P23 NOT_STARTED。D-071未创建/未使用，不自行验收、不Git写操作。'
           'PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅指本地已知施工缺口已闭合，不保证没有其他缺陷。\n\n'+short+
           '。原1286测试身份及断言保留，新增'+str(len(current-original))+'项单列；既有Windows symlink1314 SKIP不算PASS。'
           '生产世界/恢复/凭据/供应商及Research到Main生产晋升NOT_READY。下方此前状态与全部FAIL/ERROR/SKIP、辅助错误、P09 segment10 UNKNOWN均为历史。\n\n')
    for path in [ROOT/'README.md',*[DOC/name for name in TOP]]:
        link=('docs/project_memory/' if path.name=='README.md' else '')+'82_P17_测试索引与验收入口.md'
        prefix='<!-- P17_CURRENT_START -->\n'+block+'[独立复核与证据入口]('+link+')。\n<!-- P17_CURRENT_END -->\n\n'
        text=path.read_text(encoding='utf-8-sig')
        text=re.sub(r'<!-- P17_CURRENT_START -->.*?<!-- P17_CURRENT_END -->\s*','',text,flags=re.S)
        path.write_text(prefix+text,encoding='utf-8')
    for number in ('79','80','81','82'):
        path=next(DOC.glob(number+'_P17_*.md'))
        text=path.read_text(encoding='utf-8')
        if number=='80':
            text=text.replace('| IN_PROGRESS |','| IMPLEMENTED_NOT_ACCEPTED |')
            text=text.replace('58项专项已完成；兼容及完整回归仍以实际结果为准，不预填PASS。','专项、兼容与完整回归均已完成，具体原始证据如下。')
            text=text.replace('p17-final-02',FINAL_P17).replace('58项结果',str(records[FINAL_P17]['run'])+'项结果').replace('新58项单列','新'+str(len(current-original))+'项单列')
        if number=='82':
            text=text.replace('兼容及全量后续结果须核对完成状态后登记，STARTED不是PASS。','兼容及全量已核对FINISHED/exitCode=0，见本页现行结果和最终报告。')
            text=text.replace('p17-final-02',FINAL_P17).replace('58/58 PASS，76.180秒',str(records[FINAL_P17]['passed'])+'/'+str(records[FINAL_P17]['run'])+' PASS，'+str(records[FINAL_P17]['seconds'])+'秒')
        prefix='> P17现行状态：IMPLEMENTED_NOT_ACCEPTED，等待独立复核；D-070开工，不使用D-071。下方Stage Brief的IN_PROGRESS等表述为开工历史。\n\n'
        path.write_text(prefix+text,encoding='utf-8')
    with (DOC/'04_决策记录.md').open('a',encoding='utf-8') as stream:
        stream.write('\n\n### D-070 施工完成追加（不构成验收）\n\n'+block+'见[完整报告](p17_evidence/final-report.md)。本轮仅追加内部Execution与C1接线，不改冻结契约或正式数据。\n')
    with (DOC/'03_施工日志.md').open('a',encoding='utf-8') as stream:
        stream.write('\n\n## 2026-09-09 P17施工及测试收口\n\n'+short+'。保留所有首次失败，详见[测试历史](p17_evidence/test-history.md)。full-final-01为末次局部补修前历史；发现P17存储上界和TEST Adapter绑定缺口后，保存反例并补修，代码重新稳定后运行full-final-02。未机械重复三轮，无提交或push。\n')
    with (DOC/'10_档案修订记录.md').open('a',encoding='utf-8') as stream:
        stream.write('\n\n## 2026-09-09 P17档案\n\n新增79—82及p17_evidence，同步现行状态、入口和D-070；保留全部历史证据。D-071未使用，P18未开始。\n')
    with (DOC/'CHANGELOG.md').open('a',encoding='utf-8') as stream:
        stream.write('\n\n## P17工作区成果（2026-09-09，版本仍0.1.0）\n\n新增宿主中立Execution/World端口、原E5-A投递索引、取消/替代/补偿和C1候选结果吸收。仅本地Fake；IMPLEMENTED_NOT_ACCEPTED，无Git写操作。\n')
    test_history=['# P17完整测试与失败历史','',
        '所有表项来自同名原始JSON。PASS为测试方法计数；FAIL/ERROR为unittest原始记录数，含subTest时不得与方法数简单相加。后续通过不覆盖首次失败。','',
        '| 标签 | 状态与结果 | 原始输出 |','|---|---|---|']
    for path in sorted(OUT.glob('*.json')):
        r=json.loads(path.read_text(encoding='utf-8'))
        if 'testIdentities' not in r or 'exitCode' not in r or 'run' not in r:continue
        test_history.append(f"| {path.stem} | {result_summary(r)} | [JSON]({path.name}) / [stdout]({path.stem}.stdout.log) / [stderr]({path.stem}.stderr.log) |")
    test_history.extend(['','原因说明：requirements-before-01是新增模块尚未实现；direct-planner-first-01为P17新接线UTC格式不匹配；second/third为新增测试返回类型/大小写辅助错误。',
        'execution-recovery-first-01首次发现无link补偿能执行；boundaries-first-01含拒绝原因混同四个subTest FAIL及两个生命周期Fixture误用ERROR。context-binding-before-01、cancel-index-before-01分别固化旧请求重绑新Context、取消索引丢失后重派发。对应after及最终专项保留通过证据。',
        '末次审计发现两项P17缺口：固定+1024字节估算不足，实际世界文件可能超限；只用adapter_id绑定允许接入其他主体的TEST Adapter。late-boundary-formal-before-01为3方法失败（含多个subTest），修后4方法通过；并增加精确限额正向对照。按实际完整序列化字节预检，核实Adapter的subject/environment/world/version和世界文件绑定，原探针无需弱化即通过。',
        '辅助读取路径/glob错误见[原记录](auxiliary-read-errors.log)，接线诊断见[原输出](direct-diagnostic-01.log)。这些不是旧阶段缺陷。历史P16八处格式告警和P09 segment10 UNKNOWN不改写。',''])
    test_history.extend(['## 原始边界探针（不与正式测试数量相加）','','| 标签 | 退出码 / 秒 | 原始证据 |','|---|---|---|'])
    for label in ('storage-probe-before-01','storage-probe-before-02','storage-probe-after-01','adapter-binding-before-01','adapter-binding-after-01'):
        r=read(label+'.json')
        test_history.append(f"| {label} | {r['exitCode']} / {r['seconds']:.3f} | [JSON]({label}.json) / [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |")
    test_history.extend(['','storage-probe-before-01在长Temp路径下出现FileNotFoundError，未到目标断言，仅为辅助运行错误，不作为存储缺陷证据；原脚本和原输出保留。短路径before-02实际复现超限；adapter-binding-before-01实际复现跨主体TEST写入。',
        '[补修前源码存档清单](late-boundary-source-before.json)对应full-final-01；此轮全量1344项中1343 PASS、1既有SKIP不覆盖随后发现的新反例，也不是最终源码的全量结果。645项兼容源码与终局仅上述四个P17新增文件有差异，全部原模块不变，最终全量再次包含其全部645身份。',''])
    (OUT/'test-history.md').write_text('\n'.join(test_history),encoding='utf-8')
    report=['# P17施工交付与独立复核','',block,
        '实际交付：正常C1 Direct和Optional Planner→ExecutionService→原E5-A/Outbox索引→独立本地World效果与回执→原Router/Composer的RESULT_OBSERVATION→后续Thinking/Action/Evolution。三进程Golden证明一次效果、一次TEST积分和一次吸收revision；双worker进程竞争保留同一request身份。',
        '', '实现位置：domain/execution.py；services/execution_service.py、execution_ports.py、execution_context_source.py；storage/json_execution_outbox.py；testing/p17_execution_fixture.py。现有源码仅局部修改action_planning_service、continuity_core_runtime、continuity_core_service、continuity_interaction_service四文件。',
        '', '| 本轮实跑 | 真实结果 | 证据 |','|---|---|---|']
    for label,r in records.items():report.append(f'| {label} | {result_summary(r)} | [JSON]({label}.json) / [stderr]({label}.stderr.log) / [stdout]({label}.stdout.log) |')
    report.extend(['','开工行为基线仅引用P16施工方1286项、1285 PASS/1 SKIP/1072.026秒，不是本轮开工实跑。当前最终全量是本轮实际执行；没有远端CI、没有Git写操作。',
        'compatibility-final-01为本轮末次局部补修前实跑；其源码差异严格限于P17新增execution_service、execution_ports、p17_execution_fixture、test_p17_boundaries四文件，既有接线和645项原模块均未再改。full-final-01亦为补修前历史；最终专项和full-final-02才对应交付源码。正式全量包含原1286项及全部新增项，原645项兼容身份再次覆盖，不将两次结果相加。',
        '末次补修前后的本地存储/Adapter探针、正式4项及此前所有失败见测试历史。存储限额按Fake世界完整JSON含metadata/hash/换行的实际UTF-8字节预检；另一主体或environment/world/version不符的Adapter在query/execute/read_result前拒绝，零调用、零对方世界写入。这些是P17本地TEST验证，未作生产漏洞或任意Adapter保证。',
        '', '测试假设与限制：本机OS锁、同一隔离世界Fake原子写效果/积分/receipt，固定可查询幂等键；无分布式一致性或生产exactly-once承诺。Outbox只保存投递索引，取消停止事实使用原E5-A；补偿仍是新的显式授权请求，Fake只产生独立补偿记录，不声称资产恢复。',
        '生产世界/真实Adapter/供应商/凭据/隐私政策/正式恢复/Owned Asset Registry与常驻运行未开放。REAL返回RECOVERABILITY_NOT_READY，Research不可用不回退REAL，Research默认不进入Main；未开放Research→Main生产晋升。本地接口保留后续P20/P21/P22扩展位置，没有提前施工。',
        '', '[矩阵](../80_P17_规划施工测试验收矩阵.md) · [恢复语义](../81_P17_Outbox世界恢复补偿与结果吸收语义.md) · [独立命令](../82_P17_测试索引与验收入口.md) · [首次失败](test-history.md) · [最终审计](final.audit.json) · [精确变更与排除清单](final.pending-files.md)',
        '', '受保护项及Git终局以final.audit.json为准；待规划监工独立复核和用户正式验收。P17 IMPLEMENTED_NOT_ACCEPTED，P18未开始。',''])
    (OUT/'final-report.md').write_text('\n'.join(report),encoding='utf-8')
    history=(OUT/'continuation.md').read_text(encoding='utf-8')
    (OUT/'continuation.md').write_text('# P17当前接续状态\n\n施工/必要验证与档案已完成，停在IMPLEMENTED_NOT_ACCEPTED。当前有效任务P17，不返回P16、不进入P18，不Git写操作。\n\n[完整交付](final-report.md)、[全部失败历史](test-history.md)、[最终审计](final.audit.json)、[清单](final.pending-files.md)。\n\n以下保留此前施工接续原文，仅为历史，不覆盖当前结论。\n\n'+history,encoding='utf-8')
    with (DOC/'79_P17_Execution与World架构边界.md').open('a',encoding='utf-8') as stream:
        stream.write('\n施工档案范围补充：13_P00_档案与测试索引.md只同步P17入口，符合本轮索引维护授权；其他已验收专题与历史证据不改。\n')
    print(short)

if __name__=='__main__':main()
