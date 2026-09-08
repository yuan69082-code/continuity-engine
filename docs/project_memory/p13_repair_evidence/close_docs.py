"""Append measured R1/R2 outcomes after the single final full run finishes."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent;docs=root/'docs/project_memory'
def read(name):return json.loads((out/name).read_text(encoding='utf-8'))
full=read('full-final.tests.json');specific=read('p13-final.tests.json');compat=read('compat-final.tests.json')
assert all(r['status']=='FINISHED' and not r['failures'] and not r['errors'] for r in (full,specific,compat))
assert full['sourceTest']==specific['sourceTest']==compat['sourceTest']
assert read('probes-after.json')['exitCode']==0
summary=(f"本轮 P13 专项 {specific['run']} PASS、0 SKIP/FAIL/ERROR，{specific['seconds']:.3f} 秒；"
         f"直接兼容 {compat['run']} 项：{compat['passed']} PASS、{len(compat['skips'])} 既有 SKIP，{compat['seconds']:.3f} 秒；"
         f"最终全量 {full['run']} 项：{full['passed']} PASS、{len(full['skips'])} 既有 SKIP、0 FAIL/ERROR，{full['seconds']:.3f} 秒。")
for p in [root/'README.md',*docs.glob('*.md')]:
    content=p.read_text(encoding='utf-8')
    if '<!-- P13_REPAIR_CURRENT_START -->' not in content:continue
    prefix='docs/project_memory/' if p==root/'README.md' else ''
    block=('<!-- P13_REPAIR_CURRENT_START -->\n'
        '> P13 R1/R2 返修已实现（2026-09-08，D-062）：P00—P12 ACCEPTED；P13 / Engine side / 十二项 IMPLEMENTED_NOT_ACCEPTED；P14—P23 NOT_STARTED；Vio dependency=NONE。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，等待规划侧再次独立复核。\n>\n'
        '> 原七项探针本窗口修复前 4 FAIL/3 PASS（4.645 秒），修复后 7 PASS（4.065 秒）。'+summary+
        f' [修改、失败历史与复核入口]({prefix}P13_独立复核返修_R1-R2.md)。原 1049 项是开工引用；下方初版状态和证据作为历史保留。未执行 Git 写操作、未修改 Assistant、未登记 P13 用户验收。\n'
        '<!-- P13_REPAIR_CURRENT_END -->')
    content=re.sub(r'<!-- P13_REPAIR_CURRENT_START -->.*?<!-- P13_REPAIR_CURRENT_END -->',lambda m:block,content,flags=re.S)
    p.write_text(content,encoding='utf-8')
append={
 '03_施工日志.md':('2026-09-08 P13 R1/R2 返修完成','先逐字节保存复核原件及七项4 FAIL/3 PASS红测；定点修复当前表达许可、确认与资源重验，以及 Context 精确片段样式输入。保留新增测试中断点名称辅助错误，纠正后两个事实恢复断点通过。'),
 '04_决策记录.md':('D-062 R1/R2 施工完成事实（不是新验收决定）','本次开工授权持续适用；原 D-061/P12 ACCEPTED 不变。新增只读表达确认视图只绑定原请求并传给既有确认 Port，不注册新请求或账本，不投递、不扣费。'),
 '05_已完成模块.md':('P13 R1/R2 本地修复实现','首次/调用后/重放当前表达授权检查，以及 identity/relationship/emotion 的已授权 Composer 片段输入已实现。独立阻断尚未由监工确认关闭。'),
 '05_核心模块架构.md':('P13 表达当前授权与来源收口','表达不再直接读取完整 SubjectState 偏好；仅对获准投影作样式选择。原 Action/Evolution 事实先核验，当前拒绝只阻断正文。'),
 '06_未完成事项.md':('P13 当前待办更新','R1/R2 本地实现与验证完成；等待规划任务重新独立复核及用户正式验收。P14 未开工，Git 未授权。'),
 '07_待确认事项.md':('P13 返修待确认','当前 EVIDENCE_CONFLICT=PRESENT，不由修复方自行关闭。P12 生产遗忘阈值、归档年限、删除确认等未定策略保留，不随本次改变。'),
 '10_档案修订记录.md':('2026-09-08 P13 R1/R2 返修证据','追加独立原件、来源/hash、红测、两项实现、辅助错误、稳定结果和精确清单。旧证据及 P09 segment 10 UNKNOWN 未覆盖。'),
 'CHANGELOG.md':('2026-09-08 P13 表达权限与来源定点返修（0.1.0）','只读复用 Action Gate/确认/资源边界，阻断撤权/到期后的当前正文；样式来自授权 Context 精确片段。'),
 '工程总档案.md':('2026-09-08 P13 R1/R2 送审','四个运行文件及一个新正式测试文件的最小增量；P13 等待再次独立复核。六份 Schema/25冻结边界/正式数据/三规划源/版本和31脚本须由终局审计逐项证明不变。')}
for name,(title,body) in append.items():
    path=docs/name;content=path.read_text(encoding='utf-8')
    marker='<!-- P13_R1_R2_COMPLETED -->'
    assert marker not in content,'do not duplicate completion'
    with path.open('a',encoding='utf-8') as f:f.write(f'\n{marker}\n## {title}\n\n{body} {summary} [完整复核入口](P13_独立复核返修_R1-R2.md)。P13 IMPLEMENTED_NOT_ACCEPTED；EVIDENCE_CONFLICT=PRESENT。\n')
updates={
 '63_P13_ExpressionPolicy架构边界.md':('R1/R2 返修边界补记','此次只改 domain/expression.py、services/expression_policy_service.py、services/continuity_interaction_service.py、testing/p13_expression_fixture.py，并新增 tests/test_p13_review_regressions.py；档案新增 p13_repair_evidence/ 与返修入口，必要导航同步。既有 FILES FORBIDDEN 全部继续适用。上文完整 SubjectState 偏好的初版实现描述已由本次授权投影边界替代；不改用户权限政策。'),
 '64_P13_规划施工测试验收矩阵.md':('十二项矩阵的 R1/R2 复核补充','十二项状态均保持 IMPLEMENTED_NOT_ACCEPTED。R1 重点覆盖 02/06/08/09/10/12 的当前权限、确认、资源、消费与事实恢复；R2 重点覆盖 03/04/07/08/11/12 的片段依据、预算/缺失、来源权限、失效与样式对照。原38项原断言和原七项探针逐项保留，新21项正式回归在原矩阵上增加边界证明，不冒称原38项已经覆盖新反例。'),
 '65_P13_表达绑定持久化与恢复语义.md':('R1/R2 当前消费语义覆盖说明','当前正文必须通过既有 Action Gate 的当前 expression:emit 许可、范围、到期时间、确认和资源等只读评估；旧回执只证明旧事实。ExpressionAccessError 可使 expression_outcome 返回空 artifact 和已核实事实。损坏绑定/UNKNOWN 回执仍明确报错。样式 state_hash 改为获准片段 reference/fragment/version/hash 集合摘要，不再直接读取完整状态。旧初版产物只保留，不迁移/自动重授权限。'),
 '66_P13_测试索引与验收入口.md':('R1/R2 当前复核入口','初版下方38/1049证据全部为历史，不能覆盖独立新反例。当前独立原件、修复前后七项、正式相邻测试、失败辅助历史和运行命令统一见新返修入口。')}
for name,(title,body) in updates.items():
    with (docs/name).open('a',encoding='utf-8') as f:f.write(f'\n## {title}\n\n{body} {summary} [逐项证据](P13_独立复核返修_R1-R2.md)。当前 EVIDENCE_CONFLICT=PRESENT，待规划侧复核；未创建 P13 验收决定。\n')
with (docs/'P13_独立复核返修_R1-R2.md').open('a',encoding='utf-8') as f:
    f.write('\n## 终局实跑结果与审计\n\n')
    f.write('| 实跑 | PASS / SKIP / FAIL / ERROR | 耗时 | 原始证据 |\n|---|---|---|---|\n')
    f.write('| 原七项探针 | 7 / 0 / 0 / 0 | 4.065 秒 | [stderr](p13_repair_evidence/probes-after.stderr.log) |\n')
    for label,r in [('p13-final',specific),('compat-final',compat),('full-final',full)]:
        f.write(f"| {label}（{r['run']}项） | {r['passed']} / {len(r['skips'])} / 0 / 0 | {r['seconds']:.3f} 秒 | [身份/源码 hash](p13_repair_evidence/{label}.tests.json) / [stderr](p13_repair_evidence/{label}.stderr.log) |\n")
    f.write('\n原1049项身份与原38项P13测试文件完整保留，新增21项身份单列。唯一既有 SKIP 为 `test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`，`OS does not grant symlink creation: 1314`，不计 PASS。没有新增 SKIP。全部命令、环境、外层耗时、stdout/stderr、源码清单保存在同标签记录中；终局相关源码完全一致，之后只调整档案。\n\n[终局审计](p13_repair_evidence/final.audit.json) · [本轮增量与全部未提交文件](p13_repair_evidence/final.pending-files.md)。审计包括原件与副本、历史内容、保护文件、正式数据树、AST、本地链接、敏感模式和 git diff --check。本地通过不代替规划侧独立复核，EVIDENCE_CONFLICT 保持 PRESENT。\n')
print(summary)
