"""Archive only completed, identity-matched results; no Git writes."""
import datetime
import hashlib
import json
import re
import runpy
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
DOC = OUT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def create(name, value):
    with (OUT / name).open('x', encoding='utf8') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')


before = read(OUT / 'before.json')
frozen = read(OUT / 'frozen-source.json')
source = runpy.run_path(str(OUT / 'run.py'))['source_hashes']()
assert source == frozen['source']
labels = ['independent-final-01', 'formal-after-01', 'storage-compatibility-final-01',
          'p18-final-01', 'compatibility-final-01', 'full-final-01']
runs = {label: read(OUT / (label + '.json')) for label in labels}
for result in runs.values():
    assert result['status'] == 'FINISHED' and result['exitCode'] == 0
    assert not result['failures'] and not result['errors']
    assert result['sourceBefore'] == source == result['sourceAfter']
full, p18, compat = (runs[label] for label in ('full-final-01', 'p18-final-01', 'compatibility-final-01'))
assert set(full['testIdentities']) == set(frozen['identities'])
assert full['run'] == len(frozen['identities'])
assert full['skips'] == read(DOC / 'p18_storage_final_evidence/full-final-01.json')['skips']
assert all(source.get(p) == h for p, h in before['sourceTest'].items() if p.startswith('tests/'))
assert all(t in before['testIdentities'] and '1314' in reason for t, reason in full['skips'])
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
           for group in before['protected'].values() for p, h in group.items())
history = {}
for path in sorted(OUT.glob('*.json')):
    row = read(path)
    if 'sourceBefore' not in row:
        continue
    history[path.name] = {k: row.get(k) for k in ('status', 'command', 'startedAt', 'finishedAt',
                                                'run', 'passed', 'seconds', 'exitCode', 'skips')}
    history[path.name].update(failureRecords=len(row.get('failures', [])),
                             errorRecords=len(row.get('errors', [])),
                             sourceStable=row.get('sourceBefore') == row.get('sourceAfter'),
                             matchesFinal=row.get('sourceBefore') == source == row.get('sourceAfter'))
create('test-history.json', history)
create('selected-runs.json', {'source': 'frozen-source.json', 'runs': labels, 'full': 'full-final-01',
                              'before': 'independent-before-01.json', 'overlappingSetsNotAdded': True})
matrix = read(DOC / 'p18_storage_final_evidence/matrix-test-map.json')
for key, row in matrix.items():
    additions = frozen['addedIdentities'] if key in {'P18-08', 'P18-09', 'P18-11'} else []
    row['testIdentities'] = sorted(set(row['testIdentities'] + additions))
    assert set(row['testIdentities']) <= set(p18['testIdentities']) <= set(full['testIdentities'])
    row.update(status='IMPLEMENTED_NOT_ACCEPTED', evidence='p18-final-01 / full-final-01')
create('matrix-test-map.json', matrix)

state = ('P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；'
         'P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；'
         'EVIDENCE_CONFLICT=PRESENT；D-073未创建/未使用。')
summary = (f"本轮新增正式{len(frozen['addedIdentities'])}项，原{len(before['testIdentities'])}项身份和断言保留。"
           f"P18 {p18['passed']} PASS；公共兼容 {compat['passed']} PASS；最终全量 {full['run']}项："
           f"{full['passed']} PASS、{len(full['skips'])}既有Windows 1314 SKIP、0 FAIL/ERROR，"
           f"运行记录耗时{full['seconds']}秒，exit 0。各组有交集，不重复相加。")
table = '| 组 | PASS | SKIP | FAIL/ERROR | 记录秒数 | unittest秒数 | 原始输出 |\n|---|---:|---:|---|---:|---:|---|\n'
for label, result in runs.items():
    stderr = (OUT / (label + '.stderr.log')).read_text(encoding='utf8')
    timing = re.search(r'Ran \d+ tests? in ([\d.]+)s', stderr)
    table += (f"| [{label}]({label}.json) | {result['passed']} | {len(result['skips'])} | 0/0 | "
              f"{result['seconds']} | {timing.group(1) if timing else '未提取'} | "
              f"[stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |\n")
report = '# P18 连续异常原因保留：返修交付\n\n' + state + '\n\n' + summary + '\n\n'
report += '''## 修改与责任边界

本轮只修改两个既有运行文件的清理错误处理：`src/continuity_engine/storage/json_repository.py`、`src/continuity_engine/storage/json_runtime_repository.py`。新增 `tests/test_p18_storage_exceptions.py`，其余运行文件及原正式测试字节未变。

旧代码在cleanup处理器内重新抛出primary，覆盖隐式context，只保留显式cause。现在由共享内部helper保留pending主异常自然传播，保留显式cause和隐式context分支，追加清理错误及其自身原因；移除自动回指，共享原因在上方接续，避免新循环。顶层授权拒绝、版本冲突、deferred、原生错误对象/类型与错误码仍保留。正常traceback格式化、原生errno/winerror/文件绑定都有正式回归。

没有更改有限重试资格、次数/期限、当前授权、字节/版本/事务检查、原生替换、PAUSE/STOP、Provider、派发、扣费、revision或事实恢复。没有修改其他运行模块，不改变ACL或只读属性。内部异常链新增完整原因，不自动向既有脱敏对外接口打印任意原文；公共兼容覆盖原P16及Runtime诊断边界。

## 修前、修后及历史证据

- 本轮原样实跑：[independent-before-01](independent-before-01.json)，6项4PASS、2FAIL；[stderr](independent-before-01.stderr.log)、[stdout](independent-before-01.stdout.log)保留。失败确认同一个异常证据缺口，目标未变、替换1次、顶层拒绝生效，不描述成数据损坏/重复执行/停机。
- 修后首次六项6PASS记录 [independent-after-01](independent-after-01.json)。该次尚未加入新测试文件，属于中间源码清单；最终源码身份下另有 independent-final-01 6PASS。
- 新正式10项首次 formal-after-01 10PASS，其源码与最终冻结一致，直接纳入最终证据，没有机械重复。
- 原147专项PASS及35旧独立组合PASS是规划侧上轮实跑；原1507全量1506PASS/1SKIP是上一施工版本。详见[只读原件副本](independent/review-report.md)，本轮不冒称重新运行这些旧标签。
- 本轮所有原件与副本SHA256在[开工清单](before.json)；既有失败、辅助错误、原始输出和缺失证据均未覆盖。
- 默认沙箱CIM只读查询被拒，获准提升后查询成功；内部审阅rg通配路径辅助错误123已记录并修正读取。见[工具观察](tool-observation.json)，不是Engine行为失败。

## 最终实跑

记录秒数含测试发现和运行；unittest秒数来自stderr原文。各组交叉包含，不能相加成总测试数。

''' + table
report += f"\n源码/测试/资源{len(source)}份，最终身份 `{frozen['sourceHash']}`；上述组执行前后均匹配[冻结清单](frozen-source.json)。原测试身份完整保留，新增10项单列。\n\n"
report += '''## 原始目标与持续运行语义核对

本轮未改变运行寿命或持续运行入口，不新增无聊天、固定轮数、固定时长或概率停机条件。当前完整P18专项实测包含：无新消息推进、空闲/沉默保活、资源局部等待、耗尽存档尝试后宿主控制响应、释放后复用原事实、局部等待不阻塞独立维护、无重复执行/扣费、PAUSE/STOP与主体生命周期、单宿主及R1/R2恢复。

公共模块仅异常证据链可观察结构补全；原顶层拒绝及执行政策无变化，605项受影响兼容和最终全量提供当前版本证据，不承诺任意未知组合无缺陷。未验证生产部署、实际外部Adapter或任意磁盘故障下控制一定可持久化；生产能力原NOT_READY边界不变。

## 历史F1/H1/F2与待复核项

F1缺历史ThinkSession阶段和完整原生错误链；H1缺清理前活动、水位及系统码；F2缺原始系统错误码/读句柄证据。当前读句柄机制的旧修补和本次原因保留通过，不足以唯一归因上述历史现场，三项仍按UNKNOWN保留，不合并结案、不自行清除EVIDENCE_CONFLICT。P09 segment 10的stderr缺失/UNKNOWN也未改变。

本次局部修补已实现，等待规划监工独立复核。没有用户验收登记、D-073、Git写、Assistant改动或P19；没有访问远端或取得新CI，不宣称CI PASS。

## 复跑与核查入口

用未占用的新标签，避免覆盖原证据；完整全量运行无需重复其他组。测试使用隔离TEST根，全部原始输出保留。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine/src'
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-six-01 --review-class test_independent_storage_final.IndependentStorageFinal
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-formal-01 test_p18_storage_exceptions
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-p18-01 test_p18_
# 仅需要独立全量时：
& E:/Adobe/python.exe docs/project_memory/p18_exception_evidence/run.py review-full-01
```

受影响兼容的精确选择及原命令在 compatibility-final-01.json。全部测试历史见[test-history.json](test-history.json)，精确当前成果/32排除项见[final.pending-files.md](final.pending-files.md)，保护、链接、敏感内容、格式提示、源码及Git状态见[final.audit.json](final.audit.json)。审计保留历史原始日志格式告警，不为消除告警改写旧日志；敏感扫描仅有限key特征，不冒称穷尽秘密检测。

正式七文件树指纹应由最终审计实测为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`；63保护项、3规划、版本0.1.0、32排除材料均按开工逐文件hash核验。进程实际观察及测试清理记录单列于审计，不把只读查询失败伪报为零进程。
'''
report = report.replace('605项受影响兼容', f"{compat['run']}项受影响兼容")
report = report.replace('新增10项单列', f"新增{len(frozen['addedIdentities'])}项单列")
report = report.replace('新正式10项首次 formal-after-01 10PASS',
                        f"新正式{len(frozen['addedIdentities'])}项首次 formal-after-01 {runs['formal-after-01']['passed']}PASS")
create('final-report.md', report)
marker = '<!-- P18_EXCEPTION_REPAIR_20260914 -->'
for rel in read(OUT / 'documentation-files.json'):
    path = ROOT / rel
    prior = path.read_text(encoding='utf8')
    assert marker not in prior
    prefix = 'docs/project_memory/' if rel == 'README.md' else ''
    entry = prefix + 'p18_exception_evidence/'
    block = marker + '\n' + state + '\n\n' + summary + '\n\n'
    block += '本轮仅修连续异常导致原生原因丢失；原独立六项修前4PASS/2FAIL、当前身份修后6PASS，新增正式10PASS。顶层拒绝/有限重试/持续运行语义不变。F1/H1/F2历史根因仍UNKNOWN，待独立复核；D-072追加本轮返修事实，不创建验收决定。\n\n'
    block += f'[本轮完整报告]({entry}final-report.md) · [精确清单/审计]({entry}final.pending-files.md)。\n\n'
    if path.name.startswith('84_'):
        block += '| 矩阵 | 当前状态 | 最终覆盖身份数 |\n|---|---|---:|\n'
        for key, row in matrix.items():
            block += f"| {key} | IMPLEMENTED_NOT_ACCEPTED | {len(row['testIdentities'])} |\n"
        block += f'\n[身份映射]({entry}matrix-test-map.json)。各行交叉引用，不相加。\n\n'
    block += '以下为此前真实阶段/中间结果及当时状态，均作为历史保留，不倒改。\n\n'
    path.write_text(block + prior, encoding='utf8')
with (OUT / 'continuation.md').open('a', encoding='utf8') as stream:
    stream.write('\n' + datetime.datetime.now(datetime.timezone.utc).isoformat() + '：最终各组完整，档案已据真实结果同步；源码未再变化。下一步仅最终进程只读观察与audit.py，禁止重跑validate_final或全量。\n')
print(summary)
