"""Document-only report assembly from completed immutable run results."""
import json
from pathlib import Path
from snapshot import HERE, ROOT, read, source, fingerprint

LABELS = ('w02-b-final-04', 'w02-a-compatibility-04', 'affected-compatibility-04', 'full-final-04')
NAMES = ('W02-B新增正式专项', 'W02-A兼容', '实际受影响公共兼容', '最终完整回归')
CURRENT = {
 'README.md':'docs/project_memory/w02_b_evidence/',
 'docs/project_memory/01_当前状态.md':'w02_b_evidence/',
 'docs/project_memory/03_施工日志.md':'w02_b_evidence/',
 'docs/project_memory/06_未完成事项.md':'w02_b_evidence/',
 'docs/project_memory/CHANGELOG.md':'w02_b_evidence/',
 'docs/project_memory/工程总档案.md':'w02_b_evidence/',
}

def write(name, text):
    with (HERE/name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text.rstrip()+'\n')

def summary(d):
    return f"{d['run']}项：{d['passed']} PASS、{len(d['skips'])} SKIP、{len(d['failures'])} FAIL、{len(d['errors'])} ERROR；退出码{d['exitCode']}，{d['seconds']:.3f}秒"

def main():
    frozen=read(HERE/'frozen-source-04.json')
    current=source()
    assert current==frozen['source'], 'source drift'
    runs=[read(HERE/(s+'.json')) for s in LABELS]
    for d in runs:
        assert d['status']=='FINISHED' and d['exitCode']==0, 'do not manufacture completion'
        assert d['sourceBefore']==d['sourceAfter']==frozen['source'], 'mismatched test identity'
    old=read(ROOT/'docs/project_memory/w02_a_evidence/repair_r1_r2/full-final-02.json')
    norm=lambda ids:{i.removeprefix('tests.') for i in ids}
    assert norm(old['testIdentities'])<=norm(runs[-1]['testIdentities'])
    assert norm(runs[-1]['testIdentities'])==set(frozen['testIdentities'])
    assert all(current[p]==h for p,h in read(HERE/'baseline.json')['source'].items() if p.startswith('tests/'))
    rows='\n'.join(f"| {n} | [{l}]({l}.json) | {summary(d)} |" for n,l,d in zip(NAMES,LABELS,runs))
    table='| 集合 | 完整运行记录 | 实际结果（runner壁钟） |\n|---|---|---|\n'+rows
    write('test-index.md',f'''# W02-B 实跑证据与复跑入口

本表全部是本批施工方实跑，非规划窗口独立实跑、用户验收或远端CI。集合交叠不相加。最终版本{len(current)}份源码/测试/资源：`{frozen['sourceHash']}`。原1646身份及旧测试文件逐字节保留，新增{len(frozen["newTestIdentities"])}，最终发现与执行数量见表。

{table}

每个JSON均含实际命令、测试身份、成功/失败/错误/跳过身份、退出码、开始/结束时间及前后逐文件hash。同标签 `.stdout.log` / `.stderr.log` 是原始输出，不能用日志片段代替完整结果。既有SKIP：{json.dumps(runs[-1]['skips'],ensure_ascii=False)}。

## 可直接复跑

在Engine根目录设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=C:/Users/Administrator/Documents/continuity-engine/src`，使用 `E:/Adobe/python.exe`：

```powershell
& 'E:/Adobe/python.exe' -m unittest tests.test_w02_recall tests.test_w02_recall_boundaries tests.test_w02_recall_combinations tests.test_w02_recall_consistency tests.test_w02_recall_semantics -v
& 'E:/Adobe/python.exe' -m unittest discover -s tests -q
```

需要保留完整机器证据时使用本目录 `run.py <未占用标签> [测试模块...]`；标签不得覆盖，缺省模块执行全量，绝不会自动重试。A及受影响兼容的**准确完整参数**保存在对应JSON的command，勿把不同集合的通过数相加。三阶段跨进程TEST演示与只读查看见[实现说明](implementation-notes.md)。

## 引用与历史

修改前W02-A最终1646项=1645PASS/1既有1314SKIP仅为核验引用，未重跑修改前全量。本批前版测试、诊断及真实失败见[测试历史](test-history.md)，只能证明当时版本。当前四组逐文件身份均绑定同一冻结版本；本次没有远端CI结果，不声明CI PASS。
''')
    write('final-report.md',f'''# W02-B 交付及独立复核入口

W02-B = IMPLEMENTED_NOT_ACCEPTED；W02整体 = IN_PROGRESS；W02-A/D-076 = ACCEPTED。D-077仅为开工决定。本批PLANNING_CONFLICT=NONE（未发现需改变规划的实际冲突）；EVIDENCE_CONFLICT=PRESENT（首次失败及修补尚待独立核查，施工方结果不代替验收）。W02-C、W03、P19未启动。历史F1/H1/F2仍UNKNOWN，保留原验收及遗留不确定性，不重新打开旧阶段。

## 做成了什么

启用本批门控的正常C1在原入站/感知/W02-A处理后、Thinking形成回应之前，自动评估相关性，从原Memory、Timeline和可核验旧输入寻找当前可读材料；按明确关系有限展开，交原Composer去重、保留冲突、裁剪及注明缺失。无需用户说“查记忆”，找到材料也不会强迫表达或现实行动。

当前输入不必先被长期巩固；它和历史输入都保持候选、解释和来源身份。未命中、低相关、重复关系、足够材料、预算用尽、索引失效、权限拒绝和超时分开记录。来源失败不说成“历史不存在”。原请求保存准备及失败进度；重开和完成返回丢失按当前权限/来源/版本复核并复用原成功事实。没有第二状态、人物库、执行账本或新的内部人工审批。

T04沿原P04 DerivedSummary生成可追溯**未确认偏好候选视图**；独立Event根去重，重复消息及同根派生材料不加票，明确策略可配置且记录。候选不等于事实、Trait或SubjectState；未确认、负面反例和证据不足均保留。没有伪造P15结构化确认，也没有把候选阈值写成“必然喜欢”。

## 本轮实跑

{table}

上述集合有交集，不相加。全量是本批最终源码的真实新运行；修改前A全量仅引用。原1646正式身份和测试文件保留，新增{len(frozen["newTestIdentities"])}；既有Windows符号链接创建权限1314 SKIP不能算PASS。未取得远端CI，无CI PASS声明。

最终源码/测试/资源{len(current)}项：`{frozen['sourceHash']}`；各组前后源码完全对应[frozen-source-04](frozen-source-04.json)。[测试入口与精确命令](test-index.md)、[首次失败及中间过程](test-history.md)。

首轮全量 `full-final-01` 曾真实结束为1691PASS/1既有SKIP/1ERROR（T04准备超时），2182.850秒，退出1，不能算全量通过。随后减少重复日志解析仍不足，full-final-02完整1695项=1689PASS/1SKIP/1FAIL/4ERROR（2569.981秒，退出1）。定向剖析确认大量重复解析成本，在原已列明仓储文件中增加仅一次准备的当前字节校验及解析复用；每次权限/根核验仍执行，字节变动重新完整校验、返回独立副本，旧调用路径不启用。未增加时限，新增变化拒绝、损坏和副本隔离对照，按新固定版本验证。[原因链、定位与限制](full-timeout-investigation.md)。旧47/66/509通过仅为01版本历史，不冒充最终版本。版本02后又发现一般偏好被误归进食域，在真实入口保存反例并局部修正，详见[语义分类调查](semantic-type-investigation.md)。02版结果保留为历史；第三版专项仍54PASS/1ERROR（157.611秒），后续兼容及全量未启动。随后按输入原绑定定义避免无用旧Context展开，并在完整文档校验后返回独立输入投影，补充其他原记录损坏及副本隔离回归。最终04版单独绑定源码及验证。

## 接线、公共影响与边界

8个既有运行文件局部调整C1装配/准备/当前检查、Router可选关联查询、当前与旧输入投影及原journal可选序列化；新增回忆数据类型、协调服务、隔离TEST夹具及5份正式测试。完整路径及逐文件hash见[精确清单](final.pending-files.md)。未改既有测试、权限政策、Evolution Authority、计费、E5-A事实恢复、生命周期或运行寿命。

旧开关关闭不构造回忆服务，不增旧请求字段；旧接口/恢复由A及受影响兼容组验证。P18无新聊天时仍可经原内部关注推进；PAUSE禁止新调用，STOP不复活，沉默不产生现实效果。原UNKNOWN仍走原能力等待/核实链，不盲目重发。

只读入口 `app.adapter.service.recall_outcome(request_id)` 复核当前身份、权限、准备证据和版本后显示原记录；不调用模型、检索、学习或提交，不刷新过期授权。[正常链示例](chain-example.md) / [实现与恢复说明](implementation-notes.md) / [规划—代码—测试矩阵](matrix.md)。

## 真实限制与下一步

本地解释覆盖本批受控对象/进食、否定、意愿、转述、历史时间与同义/错字组合；不可靠语句保留不确定性，未声称通用中文理解或真实模型语义已验收。测试Fake只证明实际覆盖的工程链。JSON仓储仍需完整读取并校验原文档，检索和上下文窗口有界不等于已建大规模索引。来源时间不冒充事件发生时间，“可能馋了”不确定化为“不饿”。

完整外部资料可信吸收及最后贯通属W02-C，完整长期认识及确认属后续已规划工作；本批不开放真实服务、生产政策或P19页面。只读查看仅提供内部API和隔离TEST入口。下一步仅规划窗口独立复核及用户决定，未登记验收、未执行Git写操作。

## 保护与清理

[终局审计](final.audit.json)记录63保护项、正式七文件、旧三份规划、版本及57排除材料（原32+W01/规划25）、AST/链接/敏感内容/差异/进程核查。正式树预期`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，实际结果以审计为准。原始失败及历史格式提示不改写；没有清理无关材料、修改Assistant/Vio或接真实服务。

当前基线main/HEAD仍为`de710773ef6c12c12c1422711f1aab5113abd3e3`；本批成果未提交，暂存区应为空，实际终局状态完整保存在审计。[补充远端只读核对](remote-check.json)先遇沙箱Windows凭据错误，获准在宿主环境查询后，实际远端main与本地一致；首错保留，不把本地origin缓存冒称远端新验证。
''')
    text=f'''<!-- W02_B_IMPLEMENTED_D077 -->
## W02-B 已实现，等待独立复核（D-077）

用户授权仅回答形成前自动关联回忆；现行依据总施工v1.5、最终新增v1.5、长期v6.9及W01/A批范围。W02-B = IMPLEMENTED_NOT_ACCEPTED；W02整体IN_PROGRESS；W02-A/D-076 ACCEPTED，P00—P18历史验收保留。W02-C、W03、P19未启动。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT仅针对本批首次失败及修补待独立确认；历史F1/H1/F2仍UNKNOWN，不倒改旧案。

原入站→W02-A→C1准备→相关性/有界关联→原Router/Composer→Thinking已接通。当前输入及旧材料保持来源/候选属性；T04复用原DerivedSummary保留独立根、策略和未确认候选，不直接写主体。公开内部只读查询能核验并展示准备/失败原因；重开沿原请求复用成功事实，不重复模型、效果、扣费或revision。权限、失效传播、内部合法成长、现实执行、持续运行及PAUSE/STOP保持原边界。

本批施工方真实实跑：{'; '.join(n+' '+summary(d) for n,d in zip(NAMES,runs))}。集合交叠不相加；原1646身份及原测试字节保留，新增{len(frozen["newTestIdentities"])}。修改前A全量为引用，不是本轮重跑；不声称独立实跑或远端CI。最终{len(current)}份源码/测试/资源`{frozen['sourceHash']}`，四组前后身份一致。

首次缺少接线、预算排序/native Context、重复解析导致超时及辅助构造错误均保留；尤其首轮全量1691PASS/1SKIP/1ERROR、退出1、2182.850秒，以及第二轮1689PASS/1SKIP/1FAIL/4ERROR、退出1、2569.981秒均原样保留。定向定位后在本批允许文件内减少重复读取，增加仅准备期间的当前字节校验/解析复用；返回副本隔离，旧调用不启用，权限不缓存，并补读取中变更/损坏及副本对照；不放宽原时限、原断言或既有测试。随后还核查并修正一般偏好被误归进食域的问题，保留真实入口反例；最终04版本重新核验，具体标签和源码见交付历史。语言理解仍有界，JSON来源仍需完整文档校验；完整外部吸收、W03长期认识及生产接入未开放。下一步仅独立复核，无验收/Git写操作。

[交付与复核入口](PREFIXfinal-report.md) · [矩阵](PREFIXmatrix.md) · [真实测试及首次失败](PREFIXtest-index.md) · [精确成果/排除清单](PREFIXfinal.pending-files.md) · [保护与Git审计](PREFIXfinal.audit.json)。下文保留为发生时的历史状态，不代替本条。

---

'''
    for name,prefix in CURRENT.items():
        path=ROOT/name
        oldtext=path.read_text(encoding='utf-8')
        assert '<!-- W02_B_IMPLEMENTED_D077 -->' not in oldtext
        path.write_text(text.replace('PREFIX',prefix)+oldtext,encoding='utf-8',newline='\n')
    decision=ROOT/'docs/project_memory/04_决策记录.md'
    with decision.open('a',encoding='utf-8',newline='\n') as out:
        out.write('\n### D-077 施工结果补记（非验收）\n\nW02-B实现及本批验证已完成，状态IMPLEMENTED_NOT_ACCEPTED。'+
            '；'.join(n+' '+summary(d) for n,d in zip(NAMES,runs))+
            '。集合不相加，未登记验收或启动下一批；原W02-A验收、历史UNKNOWN不变。'+
            '[报告、限制与源码绑定](w02_b_evidence/final-report.md)。\n')
    write('selected-runs.json',json.dumps(dict(labels=LABELS,sourceHash=frozen['sourceHash'],sourceFiles=len(frozen['source']),
        original=1646,added=len(frozen["newTestIdentities"]),results=[dict(label=l,status=d['status'],run=d['run'],passed=d['passed'],
        skipped=len(d['skips']),failures=len(d['failures']),errors=len(d['errors']),seconds=d['seconds'],exitCode=d['exitCode'])
        for l,d in zip(LABELS,runs)]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
