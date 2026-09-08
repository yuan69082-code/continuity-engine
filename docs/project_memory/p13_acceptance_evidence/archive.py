"""D-063 documentation-only acceptance synchronization; no runtime or Git writes."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[3];docs=root/'docs/project_memory';out=Path(__file__).resolve().parent
before=json.loads((out/'before.json').read_text(encoding='utf-8'))
decisions=docs/'04_决策记录.md'
assert '## D-063：' not in decisions.read_text(encoding='utf-8')
names=['00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
       '05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md','10_档案修订记录.md',
       '11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md','13_P00_档案与测试索引.md',
       'CHANGELOG.md','工程总档案.md','63_P13_ExpressionPolicy架构边界.md','64_P13_规划施工测试验收矩阵.md',
       '65_P13_表达绑定持久化与恢复语义.md','66_P13_测试索引与验收入口.md','P13_独立复核返修_R1-R2.md']
paths=[root/'README.md',*(docs/name for name in names)]
for p in paths:
    text=p.read_text(encoding='utf-8');assert '<!-- P13_ACCEPTED_START -->' not in text
    prefix='docs/project_memory/' if p==root/'README.md' else ''
    block=('<!-- P13_ACCEPTED_START -->\n'
      '> P13 用户正式验收（2026-09-08，D-063）：P00—P13 ACCEPTED；P13 / Engine side / P13-01—P13-12 ACCEPTED；P13 Vio dependency=NONE；P14—P23 NOT_STARTED。现行 PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE，仅表示本轮已发现的 R1/R2 阻断经独立复核闭合并由用户确认验收。\n>\n'
      '> 监工独立实跑：原七项 7 PASS（3.832 秒）、P13 三模块 59 PASS（55.614 秒）、新增相邻检查 5 PASS（3.070 秒），均无 SKIP/FAIL/ERROR；59项含七项正式化版本，不相加为互斥覆盖数。全量仅核验引用施工1070项：1069 PASS、1既有 Windows symlink 1314 SKIP、0 FAIL/ERROR；stderr 621.987秒、结构化621.988秒是同一轮。本次纯档案归档未重跑测试。\n>\n'
      f'> [验收依据、未提交版本身份及审计入口]({prefix}P13_用户正式验收_20260908.md)。当前 HEAD 仍为 P12 checkpoint，P13 已验收源码由212文件 hash 标识、尚未提交；验收不等于提交或生产能力开放。下方历次施工/送审状态、PRESENT、FAIL/ERROR/SKIP、辅助错误、审批拒绝和 P09 segment 10 UNKNOWN 均为原样保留的历史。Git 操作及 P14 均须用户另行授权。\n'
      '<!-- P13_ACCEPTED_END -->\n\n')
    p.write_text(block+text,encoding='utf-8')
with decisions.open('a',encoding='utf-8') as f:
    f.write('''
<a id="d-063"></a>
## D-063：用户正式验收 P13 Expression Policy 及 R1/R2 返修

2026-09-08，用户明确回复“验收”，承接规划侧“本轮复核通过，可以验收 P13；确认后安排验收归档，push 和 P14 另行同意”。规划任务 `01a06e13-e558-7513-9c56-486fd48c686f` 传达此授权。本决定覆盖初版七模式、正常 C1 接线、当前表达授权/精确来源边界、持久化与事实恢复，以及已独立复核通过的 R1/R2 定点返修。

开档复核：main / HEAD / 本地 origin/main 为 `7afceba17635a8d9fd915bf09fa9df68f3ff3974`，0/0、暂存空；212个源码/测试及资源与施工最终专项/全量和监工清单一致，1364个复核仓库文件均未变化，63项保护文件、正式七文件、三规划源和31个排除脚本未变。172个既有待提交成果全部保留。此 HEAD 是 P12 checkpoint，不冒充已验收 P13 的提交；P13 工作区身份由验收清单/hash 固定。

独立实跑7/59/5项全部 PASS，耗时3.832/55.614/3.070秒；三组存在覆盖重叠，不相加。施工全量1070项（1069 PASS、1既有1314 SKIP、0 FAIL/ERROR）仅经身份核验后引用，不是本次验收重新执行。21项独立身份/边界核对通过。[独立报告](p13_acceptance_evidence/independent/repair-review-report.md)与[本次只读身份记录](p13_acceptance_evidence/before.json)保留来源及原字节证据。

现行 P00—P13 ACCEPTED，P13 Engine side及十二项矩阵 ACCEPTED，Vio dependency=NONE，P14—P23 NOT_STARTED。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE 只关闭本轮已发现阻断。D-061/P12 ACCEPTED、D-062开工/送审/返修及全部旧失败继续保留；不倒写历史为从未出现冲突，不改变 P09 segment 10 根因 UNKNOWN。

验收范围限已验证 Engine TEST/本地纯表达。生产 Provider、自由改写语义等价、消息实际送达、生产 exactly-once 未开放；P12正式自动清理/删除策略不随验收启用。本授权仅归档，不修改运行代码、测试、Assistant或保护边界，不授权 Git 写操作、P14开工、自动监控。[验收入口](P13_用户正式验收_20260908.md)。
''')
matrix=docs/'64_P13_规划施工测试验收矩阵.md';text=matrix.read_text(encoding='utf-8')
old_intro='依据 [Stage Brief](63_P13_ExpressionPolicy架构边界.md) 分解；以下编号为工程验收分解。P00—P12 ACCEPTED，P13 Engine side IMPLEMENTED_NOT_ACCEPTED，Vio dependency=NONE，P14—P23 NOT_STARTED。本轮实现及验证完成，等待独立复核和用户正式验收。'
assert old_intro in text
text=text.replace(old_intro,'依据 [Stage Brief](63_P13_ExpressionPolicy架构边界.md) 分解；以下编号为工程验收分解。用户已通过 D-063 正式验收，P00—P13 / P13 Engine side / 十二项现行状态 ACCEPTED；Vio dependency=NONE；P14—P23 NOT_STARTED。下方测试及返修过程保持各自历史时点。',1)
text,count=re.subn(r'(^\| P13-\d\d \|[^\n]*\| )IMPLEMENTED_NOT_ACCEPTED( \|$)',r'\1ACCEPTED\2',text,flags=re.M)
assert count==12
text+='\n## 验收前矩阵导语历史\n\n> '+old_intro+'\n'
matrix.write_text(text,encoding='utf-8')
road=docs/'02_工程路线图.md';text=road.read_text(encoding='utf-8')
old='- P13：D-062 已授权 Engine Expression Policy，当前 `IMPLEMENTED_NOT_ACCEPTED`，待独立复核；P14—P23 `NOT_STARTED`。'
assert old in text
text=text.replace(old,'- P13：用户已通过 D-063 正式验收 Engine Expression Policy 及 R1/R2 返修，现行 `ACCEPTED`；P14—P23 `NOT_STARTED`，未授权开工。',1)
road.write_text(text+'\n## P13 验收前路线条目历史\n\n'+old+'\n',encoding='utf-8')
append={
 '03_施工日志.md':'只读核对独立原件与当前身份后登记 D-063，同步十二项验收矩阵及直接相关导航；归档独立7/59/5项实跑，引用已核验1070项全量。本窗口未运行 Engine 测试。',
 '05_已完成模块.md':'P13 七模式表达、正常C1接线、当前许可/来源边界和原事实持久化恢复均已通过独立复核并获用户正式验收。实现仍处于未提交工作区。',
 '05_核心模块架构.md':'P13 已验收，表达层继续只呈现已形成判断。原 Action/Evolution Authority、唯一E5-A请求通道与当前Context精确来源边界不变，没有生产连接或第二账本。',
 '06_未完成事项.md':'P13 独立复核与用户正式验收待办已完成；提交/push未获本轮授权，P14尚未开工。生产能力与P12未定策略仍保持原限制。',
 '07_待确认事项.md':'不需重复确认P13验收。Engine提交/push及P14开工均待用户另行授权；P12遗忘阈值、归档年限、永久删除确认等生产策略仍待专项决定。',
 '10_档案修订记录.md':'新增D-063、P13验收入口和必要独立证据副本；同步现行状态、十二项、63—66及索引。原始日志、历史失败和D-062返修送审状态不覆盖。',
 'CHANGELOG.md':'P13 Expression Policy及R1/R2获用户正式验收。本次仅档案同步，软件版本保持0.1.0；没有运行代码或测试变更。',
 '工程总档案.md':'P00—P13正式ACCEPTED；P13 Vio dependency=NONE；P14—P23 NOT_STARTED。验收实现由212个文件hash固定，尚未形成P13提交SHA；当前7afceba是已有P12 checkpoint。',
 '63_P13_ExpressionPolicy架构边界.md':'本Stage Brief及其返修边界对应的Engine实现已由D-063验收。原IN_PROGRESS、NOT_READY及范围说明保留为开工/施工历史；生产NOT_READY能力不因验收开放。',
 '65_P13_表达绑定持久化与恢复语义.md':'本文当前R1/R2语义已经独立复核并由D-063验收。原事实可核实与当前正文可消费继续分开；没有重新授予生产运行或新增账本权限。',
 '66_P13_测试索引与验收入口.md':'现行验收入口转到D-063。独立7/59/5项均PASS；本次只核验引用1070项施工全量，不重跑或把重叠组相加。历次红测、辅助错误和单一既有SKIP保留。',
 'P13_独立复核返修_R1-R2.md':'R1/R2已获规划侧本轮独立核对通过，用户随后正式验收；本篇修复方送审时PRESENT和未验收文字均为历史。现行已发现阻断由D-063归档关闭，不代表未知问题或生产能力不存在限制。'}
for name,body in append.items():
    with (docs/name).open('a',encoding='utf-8') as f:
        f.write('\n## 2026-09-08 P13 用户正式验收补记（D-063）\n\n'+body+' [正式验收与证据](P13_用户正式验收_20260908.md)。本次无 Git 写操作，不修改 Assistant，不进入 P14。\n')
(out/'document-paths.json').write_text(json.dumps([p.relative_to(root).as_posix() for p in paths],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('D-063 registered; 12 current rows ACCEPTED;',len(paths),'existing documentation files synchronized.')
