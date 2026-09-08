"""One-time P12 acceptance archive, preserving dated implementation snapshots."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
docs = root / 'docs/project_memory'
baseline = json.loads((docs/'p13_evidence/before.json').read_text(encoding='utf-8'))
for group in ('sourceTest', 'protected'):
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest() == h for p,h in baseline[group].items())
decision = docs/'04_决策记录.md'
assert '## D-061：' not in decision.read_text(encoding='utf-8')
paths = ['README.md'] + ['docs/project_memory/'+name for name in (
    '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
    '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md',
    '10_档案修订记录.md','13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md',
    '59_P12_IntentionalForgetting架构边界.md','60_P12_规划施工测试验收矩阵.md',
    '61_P12_生命周期恢复删除与传播语义.md','62_P12_测试索引与验收入口.md')]
for relative in paths:
    path = root/relative
    content = path.read_text(encoding='utf-8')
    assert '<!-- P12_ACCEPTED_START -->' not in content
    prefix = 'docs/project_memory/' if relative=='README.md' else ''
    block = f'''<!-- P12_ACCEPTED_START -->
> P12 用户正式验收（2026-09-08，D-061）：P00—P12 / P12 Engine side / P12-01—P12-12 = ACCEPTED；P12 Vio dependency=NONE。此验收覆盖初版、R1—R5 及 F1/F2 返修。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅关闭本轮已解决阻断。P13 的后续开工另行登记 D-062；本验收记录不代表 P13 已验收。
>
> 已实现源码 checkpoint 为 `7afceba17635a8d9fd915bf09fa9df68f3ff3974`；本次验收档案为该提交之后的未提交增量。监工实跑 9/9、7/7、117/117 PASS；全量为核验引用 1011 项：1010 PASS、1 个既有 Windows symlink 1314 SKIP、0 FAIL/ERROR，本次未重跑。没有 Engine Actions workflow 或 CI PASS。[正式验收与证据归属]({prefix}P12_用户正式验收_20260908.md)。下方截至 2026-09-07 的状态、审批拒绝、失败及测试全部作为历史快照保留；P09 segment 10 根因仍 UNKNOWN。
<!-- P12_ACCEPTED_END -->

'''
    position = content.index('\n')+1
    content = content[:position]+'\n'+block+content[position:]
    if relative.endswith('60_P12_规划施工测试验收矩阵.md'):
        content=content.replace('当前十二项施工与规定验证已完成，状态 IMPLEMENTED_NOT_ACCEPTED，等待独立复核及用户验收；P00—P11 历史 ACCEPTED 保留。', '当前十二项已由用户正式验收，状态 ACCEPTED（D-061）；下方各轮实跑结果继续按原执行时点标识。')
        lines=content.splitlines()
        changed=0
        for i,line in enumerate(lines):
            if line.startswith('| P12-') and line.endswith('| IMPLEMENTED_NOT_ACCEPTED |'):
                lines[i]=line.removesuffix('| IMPLEMENTED_NOT_ACCEPTED |')+'| ACCEPTED |'
                changed+=1
        assert changed==12
        content='\n'.join(lines)+'\n'
        content=content.replace('全部结果须交回独立复核，不创建用户验收决定。','此限制段以下为初版及返修时点的测试记录；当前用户验收见 D-061。')
    path.write_text(content,encoding='utf-8')

entry='''
<a id="d-061"></a>

## D-061：用户正式验收 P12 Intentional Forgetting 及两轮返修

2026-09-08（Asia/Shanghai），用户在规划任务明确回复“验收”，承接“你看看，没问题就开始p13”。规划任务 `01a06e13-e558-7513-9c56-486fd48c686f` 于 01:49 向施工任务传达验收和后续 P13 Engine 独立施工范围。本决定仅登记 P12 验收；P13 开工另记 D-062，不授予本轮 Git 操作。

验收对象为 `7afceba17635a8d9fd915bf09fa9df68f3ff3974` 中的 P12 初版、R1—R5 及 F1/F2 返修。当前 205 个源码/测试文件、63 个保护文件与最终复核证据一致，1011 个原测试身份无导入错误；此次只核对身份和 hash，没有重新执行全量。

监工独立实跑原 9 条（1.207 秒）、新 7 条（1.011 秒）、P12 117 条（27.198 秒）全部 PASS、0 SKIP/FAIL/ERROR。施工最终全量为监工核验引用：1011 项，1010 PASS、1 既有 Windows symlink 1314 SKIP、0 FAIL/ERROR；stderr 521.632 秒、结构化记录 521.633 秒。此处不冒称监工或本次重新执行全量。

P00—P12、P12 Engine side、P12-01—12 ACCEPTED；P12 Vio dependency=NONE；本轮阻断闭合，两类 conflict=NONE。正式自动阈值、归档年限、永久删除确认政策仍待用户专项决定；生产自动删除、物理擦除及备份清理 NOT_READY。接受 TEST/Engine 机制不等于开启生产政策。

保留所有历史 FAIL/ERROR/SKIP、旧证据冲突、辅助错误、过夜授权及审批拒绝；P09 segment 10 stderr 缺失、根因 UNKNOWN 不变。已完成的 241 文件提交与普通 push 是此前独立授权事实；本次验收归档尚未提交，不自动沿用 Git 权限。[验收入口](P12_用户正式验收_20260908.md)。
'''
with decision.open('a',encoding='utf-8') as stream: stream.write(entry)
for name,title in [('03_施工日志.md','2026-09-08 P12 用户验收归档'),('10_档案修订记录.md','2026-09-08 P12 验收同步'),('CHANGELOG.md','2026-09-08 P12 正式验收（版本仍 0.1.0）')]:
    with (docs/name).open('a',encoding='utf-8') as stream:
        stream.write(f'\n## {title}\n\n登记 D-061，同步现行十二项矩阵及直接导航为 ACCEPTED，引用已核验历史测试；源码/测试未改，不重跑全量，无 Git 写操作。旧失败及拒绝记录保留。详见 [验收入口](P12_用户正式验收_20260908.md)。\n')
(docs/'p13_evidence/p12-acceptance-paths.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Updated',len(paths),'P12 acceptance documents; 12 current matrix rows ACCEPTED; D-061 registered.')
