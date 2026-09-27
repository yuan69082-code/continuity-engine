"""Summarize completed immutable runner evidence; never execute tests."""
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
targets = [HERE/'test-index.md', HERE/'final-test-summary.json']
if any(p.exists() for p in targets):
    raise SystemExit('summary exists; preserve original')
records = []
for path in sorted(HERE.glob('w04-2-*.json')):
    record = json.loads(path.read_text(encoding='utf-8'))
    if 'command' not in record:
        continue
    stderr = path.with_suffix('.stderr.log').read_text(encoding='utf-8')
    ran = re.search(r'^Ran (\d+) tests? in ([\d.]+)s$', stderr, re.M)
    summary = re.findall(r'^(?:OK(?: \(.*\))?|FAILED \(.*\))$', stderr, re.M)
    if record['status'] != 'COMPLETED' or not ran or not summary:
        raise SystemExit('unfinished evidence: '+path.name)
    counts = {key:int(re.search(key+r'=(\d+)',summary[-1]).group(1))
              if re.search(key+r'=(\d+)',summary[-1]) else 0
              for key in ('failures','errors','skipped','expected failures','unexpected successes')}
    total = int(ran.group(1))
    record.update(total=total, passed=total-sum(counts.values()), counts=counts,
                  unittest_seconds=float(ran.group(2)), summary=summary[-1],
                  result=path.name, stdout=path.with_suffix('.stdout.log').name,
                  stderr=path.with_suffix('.stderr.log').name)
    records.append(record)
required = ['w04-2-special-final-01','w04-2-compat-final-01','w04-2-full-final-01']
selected = [next(r for r in records if r['label']==label) for label in required]
fingerprint=json.loads((HERE/'frozen-source.json').read_text(encoding='utf-8'))['fingerprint']
if not all(r['source_before']==r['source_after']==fingerprint for r in selected):
    raise SystemExit('final evidence source mismatch; do not publish final coverage')
full_text=(HERE/'w04-2-full-final-01.stderr.log').read_text(encoding='utf-8')
ids=sorted(re.findall(r'^test_\S+ \(([^)]+)\)',full_text,re.M))
old=json.loads((HERE/'baseline-test-identities.json').read_text(encoding='utf-8'))['ids']
new=json.loads((HERE/'new-test-identities.json').read_text(encoding='utf-8'))
new_ids=new['ids']
normal=lambda values:{x.removeprefix('tests.') for x in values}
identity=dict(original_count=len(old),final_count=len(ids),new_count=len(new_ids),
              missing_original=sorted(normal(old)-normal(ids)),
              missing_new=sorted(normal(new_ids)-normal(ids)),
              unexpected_new=sorted(normal(ids)-normal(old)-normal(new_ids)),
              final_ids=ids)
if identity['missing_original'] or identity['missing_new'] or identity['unexpected_new']:
    raise SystemExit('test identity drift')
data=dict(source_fingerprint=fingerprint,selected=selected,all_runs=records,identity=identity,
          all_selected_passed=all(r['exit_code']==0 for r in selected),
          source='施工方本轮实跑；不是规划窗口独立实跑或远端CI。集合有交集，不相加。')
targets[1].write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# W04-2 原始测试索引','',data['source'],'',
       '最终同版源码：`'+fingerprint+'`，完整文件hash见 [frozen-source.json](frozen-source.json)。', '',
       '| 标签 | PASS / FAIL / ERROR / SKIP | runner秒 / unittest秒 | 退出码 | 原始证据 |',
       '|---|---|---|---|---|']
for r in sorted(records,key=lambda x:x['started_at']):
    c=r['counts']
    lines.append(f"| {r['label']} | {r['passed']} / {c['failures']} / {c['errors']} / {c['skipped']} | {r['duration_seconds']} / {r['unittest_seconds']} | {r['exit_code']} | [命令与hash]({r['result']}) · [stdout]({r['stdout']}) · [stderr]({r['stderr']}) |")
lines+=['','专项71项为本批新增42项及原W04-1的29项；原1802项身份与原测试文件保留。',
        '完整回归的既有 Windows 1314 SKIP 不计 PASS。每组运行前后指纹相同才用于最终覆盖；中间结果只覆盖当时版本。',
        '首次失败、辅助错误及原因见 [failure-history.md](failure-history.md)。历史 F1/H1/F2 仍 UNKNOWN。',
        '测试身份逐项差集、真实命令和最终选定记录见 [final-test-summary.json](final-test-summary.json)。','']
targets[0].write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({r['label']:[r['passed'],r['counts'],r['duration_seconds']] for r in selected},ensure_ascii=False))
