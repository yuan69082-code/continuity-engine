"""Archive the finished batch without changing runtime code or old evidence."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from run import ROOT,DIRECTORY,source_hashes

def read(label): return json.loads((DIRECTORY/(label+'.json')).read_text(encoding='utf8'))
def main():
 selection=read('selected-runs')
 source=source_hashes(); full=read(selection['full']); compat=read(selection['compatibility']); targeted=read(selection['targeted'])
 for d in (full,compat,targeted):
  assert d['status']=='FINISHED' and d['exitCode']==0
  assert d['sourceBefore']==d['sourceAfter']==source
 baseline=read('before'); old=set(baseline['testIdentities']); current=set(full['testIdentities'])
 assert old <= current
 fingerprint='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 frozen=dict(at=datetime.now(timezone.utc).isoformat(),source=source,sourceHash=fingerprint,
  originalIdentities=baseline['testIdentities'],addedIdentities=sorted(current-old),finalIdentities=full['testIdentities'])
 (DIRECTORY/'final-source.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 records=[]
 for f in sorted(DIRECTORY.glob('*.json')):
  d=json.loads(f.read_text(encoding='utf8'))
  if isinstance(d,dict) and 'testIdentities' in d and 'status' in d:
   records.append((f.stem,d))
 lines=['# 本轮真实测试索引','',
 '下列均为本轮施工实跑，独立原件只作为审查来源；不冒称规划监工已复核修后实现。各集合相互重叠，不相加。',
 'FAIL/ERROR列统计原始失败记录；存在subTest时记录数可能超过失败测试用例数。R2修前3个失败用例包含8条子用例失败。',
 '耗时为run.py实际记录墙钟时间（含加载发现），详细命令、测试身份、时间、源码前后hash及退出码均在对应JSON。','',
 '| 标签/原始输出 | run | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | exit | 当前源码 |',
 '|---|---:|---:|---:|---:|---:|---:|---:|---|']
 for n,d in records:
  match=d.get('sourceBefore')==d.get('sourceAfter')==source
  lines.append(f"| [{n}]({n}.json) / [stdout]({n}.stdout.log) / [stderr]({n}.stderr.log) | {d.get('run','?')} | {d.get('passed','?')} | {len(d.get('failures',[]))} | {len(d.get('errors',[]))} | {len(d.get('skips',[]))} | {d.get('seconds','?')} | {d.get('exitCode','?')} | {'一致' if match else '历史中间版本'} |")
 lines += ['', '独立诊断（不按unittest计数）：[修前](independent-before-01.json)、[修后最终](independent-after-02.json)。旧原件及副本hash在[archives.json](archives.json)。',
  '', 'compatibility-01覆盖较广但属中间版本，749项=747PASS/1SKIP/1FAIL；其唯一FAIL及之后两处初稿遗漏见实现记录。最终兼容与完整回归均绑定最终源码。',
  '', '首次FAIL/ERROR、辅助设置错误与本轮引入遗漏的分类见[实现记录](implementation-notes.md)、[辅助记录](auxiliary-errors.md)。历史P18 F1/H1/F2仍UNKNOWN，不以新通过倒推根因。',
  '', '## 可复跑命令', '', '从Engine根运行；标签必须尚未占用。runner拒绝覆盖原日志。', '', '```powershell',
  "$env:PYTHONDONTWRITEBYTECODE='1'", "$env:PYTHONUTF8='1'", "$env:PYTHONPATH='src'",
  "& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/probe.py review-diagnostic-01",
  "& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-targeted-01 test_pre_p19_autonomy",
  "& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-compatibility-01 test_p14 test_p15 test_p18 test_pre_p19 test_action",
  "& 'E:/Adobe/python.exe' -B docs/project_memory/pre_p19_autonomy_evidence/run.py review-full-01", '```','']
 (DIRECTORY/'test-index.md').write_text('\n'.join(lines),encoding='utf8')
 report=f'''# P19 前 R1—R4 合并返修交付

本轮修复已实现，等待独立复核。批次状态 IMPLEMENTED_NOT_ACCEPTED；PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=PRESENT。P00—P18 历史 ACCEPTED / D-073 保留，P19—P23 NOT_STARTED；没有新的用户验收、Git写操作或P19开工。

起点 main / HEAD / 本地origin：{baseline['head']}。原1517个测试身份完整保留，新增{len(current-old)}项；当前{len(source)}份源码/测试/资源，最终指纹 `{fingerprint}`。文件及测试身份见[final-source.json](final-source.json)。

## 实际修改与责任

- **R1**：CoreDecisionPolicy的旧Action approval曾阻止意图形成，未完成世界执行又在独立Evolution前抛错。现由原C1/native链分别保留候选、内部授权与外部结果；当前Context、状态权限、revision和生命周期仍核验。含外部意图的混合提案仅提交Engine生成的独立心智/成长字段，模型其他提案保留原ThinkSession，不提前成为效果成功事实。内部已完成只释放认知队列；真正世界UNKNOWN仍留在E5-A/Outbox，并阻止换认知ID重发同能力/目标的未确认效果。
- **R2**：移除target包含critical的风险提升。保留ActionType最低风险（USE_TOOL仍HIGH）、明确更高风险及所有确认/权限/资源门。不把显示名称或模型自报LOW当可信资产证据，也未实施D1完整风险体系。
- **R3**：正常Composer经历经当前来源和独立根检查，形成可修订TRUST/DOUBT理解，经原Action/Evolution持久化；非Fixture直接预填。旧Will的有效承诺/支持进入下轮，当前相反经历可形成QUESTION并修订承诺，不简单消除矛盾。未选或撤回的根不再充当当前支持，但历史主观理解不因检索缺失被删除；缺证据理由可追溯。不自动制造LOVE/HATE，不扩原四字段Learning和rollback权限。
- **R4**：RuntimeCognition除驱力变化外，依据已有未决关注/有效Will提出有界复议。保留最低间隔与原稳定任务身份；hold/DEFER/rest较晚再评估，明确放弃/无需求不强制Provider。预算不足、STOP、主体生命周期、UNKNOWN和原防重复门保持。Scheduler不创造心理内容。

运行修改只在7个services文件：action_evaluators.py、continuity_core_service.py、continuity_interaction_service.py、dynamic_mind_service.py、execution_service.py、runtime_cognition.py、wake_perception_thinking_action_service.py。新增4份test_pre_p19_autonomy测试，纠正2份旧测试中的错误目标预期；无Schema、公共权限接口、计费、存储格式或权威归属变更。细节与限制见[实现记录](implementation-notes.md)，逐项入口见[矩阵](matrix.md)。

## 真实验证与失败历史

本轮正式定点/交叉 {selection['targeted']}：{targeted['run']}/{targeted['run']} PASS，{targeted['seconds']}秒；最后兼容 {selection['compatibility']}：{compat['run']}项，{compat['passed']}PASS、{len(compat['skips'])}SKIP、0FAIL/ERROR，{compat['seconds']}秒。

最终固定版本完整回归 {selection['full']}：{full['run']}项，{full['passed']}PASS、{len(full['skips'])}SKIP、0FAIL/ERROR，{full['seconds']}秒，退出码{full['exitCode']}。SKIP原因逐项保留原JSON（Windows symlink权限1314）；不算PASS。上述三组运行前后源码均与最终版本一致，集合重叠不相加。没有远端CI实跑或CI PASS声明。

修前R1为1PASS/6FAIL，R2为3个失败用例（8条subTest失败），R3为1PASS/4FAIL，R4为2PASS/3FAIL。首次辅助错误、测试设置错误、旧兼容revision预期失败、初稿队列占用与倾向消失反例均完整保留，未用新PASS覆盖。两个旧测试的修正依据及新增等效保护详见实现记录；没有删测试或跳过导入错误。

第一轮完整回归full-final-01为1550项：1548PASS、1既有SKIP、1FAIL，1718.557秒。失败证实本轮R1移除早退后漏保留原Action拒绝的派发拦截（Fake调用2次）。已在同一core入口最小修正，原P13零效果断言未改，修前全量与修后原用例均保留；新增反例也证明候选保留、零效果/费用及重启不派发。新增测试最初两次因临时根路径过长ERROR，单列为辅助问题。当前完整回归是修正后新标签的实际执行，不把第一轮失败抹去。

全部唯一标签、实际命令、stdout/stderr、退出码、时间和覆盖身份见[测试索引](test-index.md)。独立原诊断副本不变：修后观察现实允许时内部revision与效果各一次；现实拒绝时内部revision推进、世界效果及实际费用为零。诊断不冒充正式测试数量。

## 原始目标与限制

已经实测无新聊天仍有真实内部认知；自然进入稳定区及合成饱和、休息/延后、资源耗尽再恢复、跨进程续接、显式STOP及停止后再开不复活。真正执行UNKNOWN、回执丢失、内部写入前后中断、权限/Context变化与小容量队列有定点检查；原锁竞争、存储修补与生命周期恢复由最终兼容及全量覆盖。没有新增运行时长/轮数/概率性停机条件，测试控制器明确STOP并回收自己的进程。

仍未开放真实服务/凭据/部署、正式联系频率/费用政策，D1/D2/D3的风险、深思和全量固化授权改革未施工。倾向生产者仅处理现有结构化经历词汇；当前支持不足会保守要求重新理解，不等于任意自然语言心理解释已实现。有限本地Fake幂等不代表生产Adapter exactly-once。历史F1/H1/F2仍UNKNOWN，未补造原系统证据或宣称唯一归因。本轮是否闭合由独立复核决定。

## 审计与交接

保护63项、规划3份、正式7文件、版本0.1.0/pyproject、原32项排除材料与独立原件逐文件检查结果见[最终审计](final.audit.json)。正式数据预期指纹为 `{baseline['formalTreeHash']}`，只有逐文件一致才沿用该树身份。源码静态、文档链接、敏感材料及差异检查亦在审计中；历史原件/失败日志格式告警原样保留。

[精确待提交与排除清单](final.pending-files.md)列出本轮源码、测试、直接档案和必要证据；清单与审计自引用hash规则写明。暂存区为空，HEAD不变，完整只读Git状态存于审计。进程检查见[process-cleanup.json](process-cleanup.json)。本批次交回独立复核，不提交、不push、不进入P19。
'''
 (DIRECTORY/'final-report.md').write_text(report,encoding='utf8')
 summary=f'''<!-- PRE_P19_AUTONOMY_REPAIR_20260920 -->
## 当前批次：P19前R1—R4已实现，等待独立复核

本批次 IMPLEMENTED_NOT_ACCEPTED；PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT。P00—P18历史ACCEPTED及D-073不变，P19—P23 NOT_STARTED。本轮授权仅为四项返修；没有新增验收决定、Git写操作或P19开工。

已分离合法内部心智提交与世界执行结果、移除名称风险启发式、接通经历形成倾向及长期Will复议、补齐驱力稳定后的有界认知需求。权限/资源/恢复/现实效果门保留；不扩正式政策或新建Authority/账本。

定点/交叉{targeted['run']}PASS；最终受影响兼容{compat['run']}项={compat['passed']}PASS/{len(compat['skips'])}SKIP；最终全量{full['run']}项={full['passed']}PASS/{len(full['skips'])}既有Win1314 SKIP、0FAIL/ERROR，{full['seconds']}秒。均为本轮实跑，集合重叠不相加。首次失败和两处旧测试预期纠正有完整记录；历史F1/H1/F2仍UNKNOWN。

[返修交付、限制与独立复核命令]({{prefix}}pre_p19_autonomy_evidence/final-report.md) · [矩阵]({{prefix}}pre_p19_autonomy_evidence/matrix.md) · [精确清单]({{prefix}}pre_p19_autonomy_evidence/final.pending-files.md)。

以下内容保留为此前阶段发生时的历史状态；包括P18当时的现行冲突结论、提交授权与工作区描述，不代替本批次状态。

'''
 history_offsets={}
 for name in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md',
              'docs/project_memory/04_决策记录.md','docs/project_memory/06_未完成事项.md',
              'docs/project_memory/CHANGELOG.md','docs/project_memory/工程总档案.md'):
  path=ROOT/name; original=path.read_bytes()
  assert b'PRE_P19_AUTONOMY_REPAIR_20260920' not in original
  assert hashlib.sha256(original).hexdigest()==baseline['tracked'][name]
  prefix='docs/project_memory/' if name=='README.md' else ''
  header=summary.replace('{prefix}',prefix).encode('utf8')
  path.write_bytes(header+original)
  history_offsets[name]={'offset':len(header),'originalHash':hashlib.sha256(original).hexdigest()}
 (DIRECTORY/'document-history.json').write_text(json.dumps(history_offsets,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 matrix=(DIRECTORY/'matrix.md').read_text(encoding='utf8')
 matrix=matrix.replace('本批次尚待最终验证与独立复核','本批次实现与最终验证完成，等待独立复核')
 matrix=matrix.replace('实现及定点已运行，最终结果见报告','IMPLEMENTED_NOT_ACCEPTED；最终定点/兼容/全量见报告')
 matrix=matrix.replace('17项组合已通过，最终版本还需全量覆盖','IMPLEMENTED_NOT_ACCEPTED；最终定点/全量通过')
 matrix=matrix.replace('继续收紧当前支持与历史解释区分','IMPLEMENTED_NOT_ACCEPTED；历史保留及当前支持重验已验证')
 matrix=matrix.replace('8项扩展已通过，最终版本还需全量覆盖','IMPLEMENTED_NOT_ACCEPTED；最终兼容/全量已覆盖')
 matrix=matrix.replace('| 不预填 |','| 最终结果见报告/测试索引 |').replace('| 尚未运行 |','| 最终实跑见报告/测试索引 |')
 (DIRECTORY/'matrix.md').write_text(matrix,encoding='utf8')
 with (DIRECTORY/'stage-brief.md').open('a',encoding='utf8') as s:s.write('\n## 收工事实（开工计划及当时状态保留）\n\nR1—R4已实现并完成分项、交叉、受影响兼容及最终完整回归，批次IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT待独立复核。实际运行改动为7个services文件；新增4份正式测试，另有2份旧测试的错误目标预期按本轮授权更正，原效果/扣费/拒绝断言保留。完整范围、失败历史、源码身份及未开放事项见final-report.md、test-index.md和final.pending-files.md；未用计划中的其他候选文件扩修。\n')
 with (DIRECTORY/'continuation.md').open('a',encoding='utf8') as s:s.write('\n## 最终验证完成\n\n各最终组均结束且源码一致，报告、矩阵、索引已生成。当前仅做终局审计及精确清单，不再修改源码/测试。不得重新运行已完成全量或回到旧P18任务。独立复核前本批次IMPLEMENTED_NOT_ACCEPTED/EVIDENCE_CONFLICT=PRESENT。\n')
 print('Reports generated; final audit and process verification still required.')
if __name__=='__main__':main()
