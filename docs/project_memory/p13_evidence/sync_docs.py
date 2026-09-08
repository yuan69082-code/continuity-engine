"""Append measured P13 results and synchronize current status, preserving history."""
import hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[3];docs=root/'docs/project_memory';directory=Path(__file__).resolve().parent
full=json.loads((directory/'full-final.tests.json').read_text(encoding='utf-8'))
targeted=json.loads((directory/'p13-stable-final.tests.json').read_text(encoding='utf-8'))
compat=json.loads((directory/'compat-final.tests.json').read_text(encoding='utf-8'))
golden=json.loads((directory/'golden-layout-fixed.json').read_text(encoding='utf-8'))
scenarios=json.loads((directory/'golden-layout-fixed.stdout.log').read_text(encoding='utf-8'))['scenarios']
assert full['status']=='FINISHED' and not full['errors'] and not full['failures']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in full['sourceTest'].items())
assert not targeted['errors'] and not targeted['failures'] and not targeted['skips']
assert set(targeted['testIdentities'])<=set(full['testIdentities'])
assert golden['exitCode']==0 and len(scenarios)==7 and all(s['sameReplay'] for s in scenarios)
summary=f"专项 {targeted['run']} 项：{targeted['passed']} PASS、0 SKIP/FAIL/ERROR（{targeted['seconds']:.3f} 秒）；全量 {full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP、0 FAIL/ERROR（{full['seconds']:.3f} 秒）。"
names=['README.md']+['docs/project_memory/'+n for n in (
 '00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
 '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md',
 '10_档案修订记录.md','11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md',
 '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md')]
for name in names:
    p=root/name;t=p.read_text(encoding='utf-8');prefix='docs/project_memory/' if name=='README.md' else ''
    block=f'''<!-- P13_CURRENT_START -->
> P13 本轮施工与验证完成（2026-09-08，D-062）：P00—P12 ACCEPTED；P13 / Engine side / P13-01—12 IMPLEMENTED_NOT_ACCEPTED；P13 Vio dependency=NONE；P14—P23 NOT_STARTED。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE（本地已知施工失败已闭合，尚待独立复核及用户验收）。{summary}SKIP 仍为 Windows symlink 1314，不计 PASS。
>
> [Stage Brief]({prefix}63_P13_ExpressionPolicy架构边界.md) · [十二项矩阵]({prefix}64_P13_规划施工测试验收矩阵.md) · [表达/恢复语义]({prefix}65_P13_表达绑定持久化与恢复语义.md) · [测试、首次失败与独立复核入口]({prefix}66_P13_测试索引与验收入口.md)。本轮源码、测试和档案均未提交，无 Git 写操作；Assistant/保护边界未改。P12 已由 D-061 验收，下方各阶段旧快照、FAIL/ERROR/SKIP、审批拒绝和 P09 segment 10 UNKNOWN 保留。
<!-- P13_CURRENT_END -->'''
    t,n=re.subn(r'<!-- P13_CURRENT_START -->.*?<!-- P13_CURRENT_END -->',lambda m:block,t,count=1,flags=re.S)
    assert n==1,name
    if name.endswith('02_工程路线图.md'):
        t=t.replace('当前 `IN_PROGRESS`；P14—P23 `NOT_STARTED`。','当前 `IMPLEMENTED_NOT_ACCEPTED`，待独立复核；P14—P23 `NOT_STARTED`。')
    p.write_text(t,encoding='utf-8')

methods={
 1:('seven_modes','old_thinking','unknown_mode','crash_after_thinking'),
 2:('binding','cross_subject','forged_action','original_router'),
 3:('formal_relationship','existing_emotion','budget'),
 4:('reversing_provider','mode_and_binding','budget_rejection','generation_failure'),
 5:('silence','platform_denial','generation_failure','model_waiting'),
 6:('direct_and_optional','seven_modes','model_result'),
 7:('old_thinking','disabled','gate_off','missing_completed','removing_original'),
 8:('expired_context','revoked_exact','invalidation','p12_archive'),
 9:('restart_repeat','crash_after','fresh_process','generation_failure_retry','real_evolution'),
 10:('current_approved','real_evolution','model_result','unknown_historical'),
 11:('protected_root','cross_subject','seven_modes','forged_action'),
 12:('bounded_three_day','snapshot_branch','fresh_process')}
mapping={f'P13-{i:02d}':[t for t in targeted['testIdentities'] if any(k in t for k in keys)] for i,keys in methods.items()}
assert all(mapping.values())
assert set().union(*map(set,mapping.values()))==set(targeted['testIdentities'])
coverage={'source':'full-final.tests.json','targetedSource':'p13-stable-final.tests.json',
    'note':'A test may prove several rows; row counts must not be summed.', 'matrix':mapping}
(directory/'matrix-coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=docs/'64_P13_规划施工测试验收矩阵.md';t=p.read_text(encoding='utf-8')
t=t.replace('P13 Engine side IN_PROGRESS','P13 Engine side IMPLEMENTED_NOT_ACCEPTED')
t=t.replace('测试结果尚未执行，不预填 PASS。','本轮实现及验证完成，等待独立复核和用户正式验收。')
assert t.count('| IN_PROGRESS |')==12
t=t.replace('| IN_PROGRESS |','| IMPLEMENTED_NOT_ACCEPTED |')
t+='\n## 逐项证据与实现责任\n\n[完整测试身份映射](p13_evidence/matrix-coverage.json) 使用实际专项及当前完整回归的身份；下列数量不可相加。'+summary+'\n\n| 项 | 实际定点 | 主要实现/限制 |\n|---|---|---|\n'
locations={1:'ThinkingResult / ExpressionDecision；七模式为已形成 Engine 输入，不从聊天猜测。',
2:'ExpressionPolicyService.binding；原请求/ThinkSession/Action/Context，hash 不代替实际回执。',
3:'decide/render_body；现有偏好/简化投影，格式变化不改变判断。',
4:'PresentationCandidate 精确比较；不声称任意自由文本改写等价。',
5:'status/空正文/类型化错误/原 E5-A WAITING；失败不伪造沉默。',
6:'ContinuityInteractionService 正常链；PURSUE/DEFER 不等于已投递或新执行。',
7:'原 domain checkpoint 可选字段；无新账本/仓储，关闭不增加组件调用。',
8:'Core.current + P12 原 exact 生命周期传播；失效正文不能重复消费。',
9:'原 operation/ThinkSession 恢复；纯物化异常可显式重试，无新模型或副作用。',
10:'原 Gate/Evolution/E5-A；先核实事实，再判表达可消费，不重复 revision。',
11:'P13 Fixture 复用已验收 P08 路径保护；Windows 大小写遵循本机语义。',
12:'正常 Golden、三逻辑日七轮、新进程/分支；既有 Windows 路径长度约束保留。'}
for i in range(1,13):
    key=f'P13-{i:02d}';t+=f'| {key} | {len(mapping[key])} 个测试 PASS；0 SKIP/FAIL/ERROR | {locations[i]} |\n'
t+='\n所有原 1011 身份保留；P13 未验收，不将本地 PASS 写成 ACCEPTED。正式自动删除、生产 Provider/表达 Adapter、P14/P17/常驻运行时均未开放。\n'
p.write_text(t,encoding='utf-8')

p=docs/'66_P13_测试索引与验收入口.md';t=p.read_text(encoding='utf-8')
t+='''
## 后续首次失败与局部收口

- [沉默预算反例](p13_evidence/silence-budget-red.stderr.log)：1 ERROR；未输出草稿长度被错误用于限制 SILENCE。只对 SUBJECT_EXPRESSION 应用可见正文预算，空表达仍核验当前绑定，无 Port 调用。随后专项 38 项全部通过。
- [Golden 首次错误](p13_evidence/golden-final.stderr.log)：新增 CLI 给每个模式额外增加子目录，使旧 Windows 临时文件路径达到 263 字符。[路径诊断](p13_evidence/golden-layout-diagnosis.json) 与 [修复后输出](p13_evidence/golden-layout-fixed.stdout.log) 保留。仅移除冗余目录层；P01 自身仍创建独立 sandbox identity，没有修改原 Awakening/存储实现。

## 本轮终局实际结果

'''
t+=f'''| 执行项 | 实际结果 | 耗时 | 证据 |
|---|---|---|---|
| P13 专项 | {targeted['run']} 项：{targeted['passed']} PASS、0 SKIP/FAIL/ERROR | {targeted['seconds']:.3f} 秒 | [逐项结果](p13_evidence/p13-stable-final.tests.json) / [stderr](p13_evidence/p13-stable-final.stderr.log) |
| E5-A/P02、Thinking/Action、P08/P09/P12、前 P12 修复直接兼容 | {compat['run']} 项：{compat['passed']} PASS、{len(compat['skips'])} 既有 SKIP、0 FAIL/ERROR | {compat['seconds']:.3f} 秒 | [身份与结果](p13_evidence/compat-final.tests.json) |
| 当前最终源码全量，仅一轮 | {full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP、0 FAIL/ERROR | {full['seconds']:.3f} 秒 | [逐项结果及源码 hash](p13_evidence/full-final.tests.json) / [stdout](p13_evidence/full-final.stdout.log) / [stderr](p13_evidence/full-final.stderr.log) |
| Golden CLI | 7 模式及重放断言完成，退出码 0；不重复计作 unittest 项数 | 外层 {golden['wallSeconds']:.3f} 秒 | [命令记录](p13_evidence/golden-layout-fixed.json) |

专项之后仅修改了 Golden CLI 的目录布局，已经实际运行该命令验证；兼容之后的沉默预算调整只作用于新增 P13 纯物化代码，随后专项验证。最终全量包含这些最终源码、全部原兼容项和全部 {targeted['run']} 项新回归，源码 hash 与收口现场一致。全量后只调整档案，不机械再跑三轮。

SKIP 唯一身份仍为 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`，原因 `OS does not grant symlink creation: 1314`。没有新 SKIP；不计作 PASS。原 {len(full['testIdentities'])-len(targeted['testIdentities'])} 项身份全部保留，旧测试文件未修改。

## 终局审计与待复核

[只读审计](p13_evidence/final-audit.audit.json) · [精确未提交清单](p13_evidence/final-audit.pending-files.md)。包括六 Schema/25 冻结边界、正式七文件及树指纹、三规划源、版本 0.1.0、31 个 P10 脚本、源码/测试身份、静态/链接/敏感模式/差异和历史内容保护。

P00—P12 ACCEPTED；P13 / Engine side / 十二项 IMPLEMENTED_NOT_ACCEPTED；P14—P23 NOT_STARTED。当前 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE 仅表示本地已知失败均闭合，独立复核仍待进行。请重点核对七模式的上游决定绑定、当前消费与原事实恢复分离、原日志和最终源码身份。未执行任何 Git 写操作，不修改 Assistant，不进入 P14。
'''
p.write_text(t,encoding='utf-8')

sections={
 '03_施工日志.md':('2026-09-08 P13 施工与本地验证收口', '先 D-061 验收 P12，再 D-062/Stage Brief 开工。完成正常链表达及原账本内绑定；保留首次失败、辅助错误和 Golden 路径错误。'),
 '04_决策记录.md':('D-062 施工完成事实补记（不新增验收决定）','仅记录用户授权范围内本地实现完成；没有 P13 用户验收决定，不沿用以前 Git 权限。'),
 '05_已完成模块.md':('P13 本地实现完成、待独立复核','七模式、受约束纯呈现、正常 C1 接线、原 operation 内产物及当前消费/历史事实分离已实现。P12 已由 D-061 验收。'),
 '05_核心模块架构.md':('P13 表达接线','Context/Thinking/Action 保持原职责；Expression 只读当前来源/既有偏好，产物保存在原 domain checkpoint，不写 SubjectState/Memory 或建立新账本。'),
 '06_未完成事项.md':('2026-09-08 现行待办','P12 复核/验收待办已由 D-061 关闭；P13 等待独立复核及用户正式验收，当前工作区未提交。P14 不开始。'),
 '07_待确认事项.md':('2026-09-08 现行待确认','P12 阶段不需重复验收；其生产遗忘阈值、归档年限、永久删除确认仍待专项决定。P13 等待独立复核与用户验收；生产表达 Provider/Adapter 未开放。'),
 '10_档案修订记录.md':('2026-09-08 P12 验收与 P13 档案同步','增加 D-061、D-062 和 63—66；P00 11/12 补现行导览，原状态表作为历史保存。原始日志/旧数字不覆盖。'),
 'CHANGELOG.md':('2026-09-08 P13 Expression Policy（版本仍 0.1.0）','新增内部表达策略和原请求绑定，正常链覆盖七模式；修正本轮发现的 Action/request 绑定和空表达预算遗漏，新增 Golden Windows 目录布局已验证。'),
 '工程总档案.md':('2026-09-08 P13 本地交付','P12 由 D-061 正式验收；P13 由 D-062 开工并完成本地实现测试。生产/后续阶段及 Git 均未授权。')}
for name,(heading,content) in sections.items():
    with (docs/name).open('a',encoding='utf-8') as stream:
        stream.write(f'\n## {heading}\n\n{content} {summary} 当前 P13 IMPLEMENTED_NOT_ACCEPTED，等待独立复核。全部首次失败/ERROR/SKIP、旧审批拒绝及 P09 segment 10 UNKNOWN 保留。[本轮证据和清单](66_P13_测试索引与验收入口.md)。\n')
print(summary)
print('12 current P13 matrix rows synchronized; no P13 acceptance created.')
