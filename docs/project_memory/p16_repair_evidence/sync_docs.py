"""Append P16 repair facts; preserve initial construction and failure evidence."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;DOC=ROOT/'docs/project_memory'
def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf-8-sig'))
def summary(r):
    return f"{r['run']} 项，{r['passed']} PASS、{len(r['skips'])} SKIP、{len(r['failures'])} FAIL、{len(r['errors'])} ERROR，{r['seconds']:.3f} 秒，退出码 {r['exitCode']}"
def main():
    runs={name:read(name) for name in ('independent-after-01','p16-final-01','compatibility-final-01','full-final-01')}
    assert all(r['status']=='FINISHED' and r['exitCode']==0 for r in runs.values())
    assert all(r['sourceBefore']==r['sourceAfter']==runs['full-final-01']['sourceAfter'] for r in runs.values())
    history=['# P16 R1/R2/R3 全部运行历史\n','所有条目为本轮实跑。秒为 runner 计时（包含发现及记录），unittest 自身计时保留在原始 stderr。FAIL/ERROR 列是 unittest 失败记录数（含子用例），不是可与方法总数相加的人为总数；PASS 按独立方法剔除失败/错误/跳过计算。后续通过不覆盖首次失败。\n',
             '| 唯一标签 | 方法数 | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | 退出码 | 原始输出 |','|---|---|---|---|---|---|---|---|---|']
    records=[]
    for p in OUT.glob('*.json'):
        r=json.loads(p.read_text(encoding='utf-8-sig'))
        if 'command' not in r or 'testIdentities' not in r:continue
        assert r['status']=='FINISHED'
        records.append((r['startedAt'],p.stem,r))
    for _,label,r in sorted(records):
        history.append(f"| [{label}]({label}.json) | {r['run']} | {r['passed']} | {len(r['failures'])} | {len(r['errors'])} | {len(r['skips'])} | {r['seconds']:.3f} | {r['exitCode']} | [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |")
    history += ['\n## 失败解释与证据局限\n',
        '- independent-before-01：原九项，4 PASS / 5 FAIL，7.902 秒，原 R1/R2/R3 的有效修前复现。独立侧先前的首次 Temp 路径错误保留在 independent/independent-edges-01.*，不算 Engine 缺陷。',
        '- formal-before-01：22 方法，7 PASS；47 条 FAIL 含完整回执 12 字段×2入口等子用例；2 ERROR 分别是新增测试误用 LocalIntegrationApp.coordination 属性，以及尚未实现的可选检查方法。首版诊断断言还可能把源码行里的预期错误码误当实际错误消息，已改为核实异常类型与真实 cause 消息，增强而未删除断言；相关早期 PASS 不能作为该入口关闭证据。',
        '- formal-after-01：22/22；当时尚未加入模型结果首次 E5-A 持久化的三项组合，所以这是中间结果，不冒充最终覆盖。',
        '- capability-before-01：3 方法，2 FAIL / 1 ERROR。FAIL 是未在 CapabilityResult 首次入账及旧结果恢复 checkpoint 前执行材料重查；ERROR 是新增测试的查询专用 Fixture 未注册原 C1 expression.emit。',
        '- formal-after-02：24 PASS / 1 ERROR。新增正常模型结果对照补注册表达能力后，仍缺原 P09 明确权限和按原请求身份确认配置。最终复用 ConfirmedFixturePolicy 和已有 Fake 能力，未关闭 Action、削弱断言或修改原 Fixture。capability-after-01 三项均通过。',
        '- 只读辅助命令曾使用不存在的文件名和 PowerShell rg 通配参数，结果已识别为路径查询错误；一次快照字段打印过多导致输出截断。未改变文件或被计作测试 PASS。',
        '- 原 P16 p16_evidence 全部原件及 P09 segment 10 根因 UNKNOWN、既有 WinError 1314、P15 与此前历史失败不变。当前仅本地测试；没有远程 CI run/check。\n']
    (OUT/'test-history.md').write_text('\n'.join(history)+'\n',encoding='utf-8')
    code='''```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p16_repair_evidence/run.py review-r16-probes --independent-probe
python docs/project_memory/p16_repair_evidence/run.py review-r16-formal test_p16_repair_edges test_p16_review_regressions
python docs/project_memory/p16_repair_evidence/run.py review-r16-p16 test_p16_
python docs/project_memory/p16_repair_evidence/run.py review-r16-full
python docs/project_memory/p16_repair_evidence/audit.py review-r16
```
'''
    report='''# P16 R1/R2/R3 返修交付（等待独立复核）

P16 / Engine side / P16-01—P16-12 = IMPLEMENTED_NOT_ACCEPTED；P00—P15 ACCEPTED；P17—P23 NOT_STARTED；Vio dependency = NONE。PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = PRESENT，已知复核阻断等待监工独立确认，本轮不关闭、不验收、不创建 D-069、不 Git 写操作。

## 实际修复

| 项 | 根因与责任边界 | 实际变化及验证 |
|---|---|---|
| R1 | P16 Adapter 只验证 ActionReceipt 结构/绑定，遗漏回执材料 | [external_capability_service.py](../../../src/continuity_engine/services/external_capability_service.py) 在执行返回、独立 query、历史恢复共同 Adapter 出口，把整份 to_dict 原材料交给 Broker；保留全部 12 字段、原回执与事实文件，不改写编号/hash。拒绝返回静态码，原 E5-A 保留 UNKNOWN；查询后恢复事实，不自动重发。正式回归逐字段检查两入口，正常自定义 ID 与恢复继续通过。 |
| R2 | Information Need 在 P16 Policy 选择时才检查，Thinking 及模型结果可能先入账 | [thinking_service.py](../../../src/continuity_engine/services/thinking_service.py) 增加可选 result_validator，先检查原结果再运行 P14/P15 processor、首次保存；失败只保存通用失败结果及安全原因。等待恢复先检查后 resume 写入；已完成结果返回前重查。[continuity_interaction_service.py](../../../src/continuity_engine/services/continuity_interaction_service.py) 仅 P16 开启时接线，C1 CapabilityResult 首次 E5-A 入账、结果/ThinkSession 重放及 checkpoint 恢复检查同一材料边界。原结果身份、hash、历史事实不修改；P16 关闭不调用外部检查。普通心理/实验内容对照不受审查。 |
| R3 | Broker/Permission 异常通过标准异常链泄漏任意原文 | ExternalCapabilityService 统一 material_allowed / authorize_reference / authorize_permission 静态错误边界，异常使用 from None，不转存 repr/原文。覆盖注册、选择、执行、消费、恢复；必须明确 True 才获准，异常不是成功。原 Provider 异常防护保留。正式回归检查真实异常消息、标准 traceback 及重定向 stdout/stderr，运行目录没有合成秘密泄漏。 |

本轮只改三个现有服务文件，新增两个正式回归文件；未改变冻结接口、Authority、E5-A 账本或业务主体定位。旧 1261 项身份及测试断言完整保留，新加 25 项（原九项探针副本 + 16 项边界组合）；原独立九项已包含在正式 P16 中，不再相加计数。

## 真实验证

'''
    for name,r in runs.items():report+=f'- [{name}]({name}.json)：{summary(r)}。[stdout]({name}.stdout.log) / [stderr]({name}.stderr.log)。\n'
    full=runs['full-final-01']
    report+='\n上述均是本轮修复方实跑，包括执行原独立脚本副本；不是新的监工独立核验。秒为 runner 计时（包含发现与记录），unittest 自身计时保留在 stderr。原监工 53 PASS 与九项 4 PASS / 5 FAIL 属于修前历史。[全部首次失败和辅助错误](test-history.md)保留。原 P16 全量 1260 PASS / 1 SKIP 仅作历史，未冒充返修后结果。\n\n'
    report+='本轮完整回归的既有 SKIP：'+json.dumps(full['skips'],ensure_ascii=False)+'。SKIP 不计 PASS。每次原始 JSON 保存命令、完整方法身份、UTC 起止时间、耗时、退出码和执行前后源码 SHA-256。\n\n'
    report+='## 独立复核入口\n\n'+code+'\n必须使用未占用标签，runner 拒绝覆盖输出；顺序运行，不同时启动全量。原始独立材料逐文件 hash 来源见 [before.json](before.json)，[报告副本](independent/review-report.md)、[探针副本](independent/test_independent_edges.py)及所有原始日志/快照保持原样。\n\n'
    report+='## 保护、清单与剩余事项\n\n[最终只读审计](final.audit.json)记录当前源码身份、原 1261 身份、63 保护项、三份规划、正式七文件、版本和 32 排除项；[完整 P16 待提交及排除清单](final.pending-files.md)包括已有 P16 成果，不仅是本轮增量。正式树预期 sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2。最终实测值以审计为准。\n\n剩余：三项阻断待独立确认；P16 未用户验收。真实服务、生产凭据与隐私策略、生产接入未开放；不声称任意 Adapter exactly-once。本轮不访问外网，既有 HTTP 回归仅本机 loopback；不访问 Assistant/Vio，不运行或配置 CI，不提交/push。历史格式问题仅列明，不修写原始日志。\n'
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    block='''当前有效任务：P16 R1/R2/R3 返修已实现，等待独立复核。P16 / Engine side / 十二项 IMPLEMENTED_NOT_ACCEPTED；P00—P15 ACCEPTED；P17—P23 NOT_STARTED；Vio dependency = NONE。PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = PRESENT，独立确认前不关闭。D-068 追加返修事实，D-069 未创建/未使用。'''
    block+='\n\n本轮 P16：'+summary(runs['p16-final-01'])+'；兼容：'+summary(runs['compatibility-final-01'])+'；最终全量：'+summary(full)+'。下方此前施工结论及数字保留为历史。'
    documents=[ROOT/'README.md']+[p for p in DOC.glob('*.md') if '<!-- P16_CURRENT_START -->' in p.read_text(encoding='utf-8-sig')]+list(DOC.glob('7[5-8]_P16_*.md'))
    for p in dict.fromkeys(documents):
        text=p.read_text(encoding='utf-8-sig')
        text=re.sub(r'<!-- P16_REPAIR_CURRENT_START -->.*?<!-- P16_REPAIR_CURRENT_END -->\s*','',text,flags=re.S)
        prefix='docs/project_memory/' if p==ROOT/'README.md' else ''
        new='<!-- P16_REPAIR_CURRENT_START -->\n'+block+'\n\n见 [返修报告]('+prefix+'p16_repair_evidence/final-report.md)、[接续记录]('+prefix+'P16_独立复核返修_R1-R3.md)。\n<!-- P16_REPAIR_CURRENT_END -->\n\n'
        p.write_text(new+text,encoding='utf-8')
    decision=DOC/'04_决策记录.md'
    with decision.open('a',encoding='utf-8') as f:f.write('\n\n### D-068 追加：P16 三项返修施工测试完成，待独立确认\n\n'+block+'\n\n[完整证据](p16_repair_evidence/final-report.md)。本条为施工事实，不是用户验收决定。\n')
    with (DOC/'P16_独立复核返修_R1-R3.md').open('a',encoding='utf-8') as f:f.write('\n\n## 终局接续\n\n'+block+'\n\n[修复位置、真实运行、限制与复核命令](p16_repair_evidence/final-report.md)。当前不执行任何 Git 写操作，完成后交回独立复核。\n')
    with (DOC/'77_P16_外部候选凭据缓存与恢复语义.md').open('a',encoding='utf-8') as f:f.write('\n\n## R1/R2/R3 补充语义\n\n整份外部回执在原 E5-A 持久化前过 Broker 材料检查；拒绝只表示材料不可用，不证明未执行，继续 UNKNOWN/查询。C1 模型结果入账和 Thinking 完成前采用可选材料校验；已存原事实不清理、不改 hash，恢复拒绝不合格材料，不能授权重发。三个端口异常统一静态码并抑制原文异常链。详见 [返修报告](p16_repair_evidence/final-report.md)。\n')
    with (DOC/'76_P16_规划施工测试验收矩阵.md').open('a',encoding='utf-8') as f:f.write('\n\n## 本次修复与十二项对应\n\nR1 → P16-05/06/09/11：完整回执、UNKNOWN 和可信恢复；R2 → P16-01/04/05/08/12：真实 C1/Thinking/模型结果首次入账及恢复材料边界；R3 → P16-03/05/07/10/11：注册、选择、执行、消费、恢复异常。其余原项由本次完整 P16 专项重新运行覆盖。各项仍 IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT。[新增正式 25 项与原 53 项完整身份](p16_repair_evidence/p16-final-01.json)。\n')
    with (DOC/'78_P16_测试索引与验收入口.md').open('a',encoding='utf-8') as f:f.write('\n\n## 当前返修复核命令\n\n下面使用返修 runner 与审计脚本；上方原 p16_evidence/audit.py 对应旧历史施工身份，不能作为当前返修的最终审计。\n\n'+code+'\n[当前最终审计](p16_repair_evidence/final.audit.json) · [当前精确清单](p16_repair_evidence/final.pending-files.md) · [全部失败历史](p16_repair_evidence/test-history.md)\n')
    print('P16 repair docs synchronized; no acceptance or Git writes')
if __name__=='__main__':main()
