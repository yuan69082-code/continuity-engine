"""Synchronize only authorized W02 docs from completed, identity-matched runs."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def load(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def save(name,text):(HERE/name).write_text(text,encoding='utf-8')


def main():
    selected=load('selected-runs.json');frozen=load(selected['source'])
    data={k:load(selected[k]+'.json') for k in ('special','compatibility','full')}
    for run in data.values():
        assert run['status']=='FINISHED' and run['exitCode']==0 and not run['loaderErrors']
        assert run['sourceBefore']==run['sourceAfter']==frozen['source']
    src={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
         for base in ('src','tests') for p in sorted((ROOT/base).rglob('*'))
         if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert src==frozen['source']
    special,compat,full=(data[k] for k in ('special','compatibility','full'))
    table=['| 本轮实跑 | 标签 / 原始证据 | 实际结果 | 墙钟秒 / 退出码 |', '|---|---|---|---|']
    for group,title in (('special','W02-A 专项'),('compatibility','受影响兼容组合'),('full','最终完整回归')):
        r=data[group];label=selected[group]
        table.append(f"| {title} | [{label}]({label}.json) · [stdout]({label}.stdout.log) · [stderr]({label}.stderr.log) | {r['run']} 项：{r['passed']} PASS、{len(r['skips'])} SKIP、{len(r['failures'])} FAIL、{len(r['errors'])} ERROR | {r['seconds']:.3f} / {r['exitCode']} |")
    table='\n'.join(table)
    summary=(f"W02-A 专项 {special['passed']} PASS；受影响兼容 {compat['run']} 项（{compat['passed']} PASS、{len(compat['skips'])} SKIP）；"
        f"最终全量 {full['run']} 项（{full['passed']} PASS、{len(full['skips'])} 既有 Windows 1314 SKIP），均 0 FAIL/ERROR。")
    status='W02-A = IMPLEMENTED_NOT_ACCEPTED；W02 整体 = IN_PROGRESS（尚未完成）；W02-B/C、W03 与 P19 未开工。'
    conflict='PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT（本批首次失败及修补交回独立核对，不以施工方通过替代独立确认）。'
    save('final-report.md',f'''# W02-A 输入理解与逐站处置记录：交付报告

{status}本轮只有 D-075 开工记录，没有用户验收决定，没有 Git 写操作。{conflict}

## 实际做成的内容

原始消息通过原 IntegrationAdapter、Perception 和 C1 处理。新增可选来源经原 Router/Composer 进入本轮 Thinking；有界解释保留否定、愿望、他人、转述、假设及不确定性，不将它们自动升级为事实或许可。

相关站点在原 operation journal 内记录处置、理由、来源和结果身份。会话临时使用不等于已记住；只有合法 Event/Memory 的匹配证据才引用原记忆。缺证据、预算未选中、失败等待分别如实记录，不强迫每条消息走全部模块。合法内部变化仍由原 Thinking/Action/Evolution 提案和提交，表达拒绝仍然保持，不由分流器写人格或关系。

恢复沿同一请求和原事实进行：成功站点不可改写或重复执行；失败站保留历史后补未完成步骤。核验原 Context、Memory 历史、ThinkSession、Action/Evolution 及 E5-A 回执；不能靠处置日志自证成功。两个真实进程的 Golden 已覆盖已发生 Fake 效果后的恢复：第二进程新增模型调用 0、新增效果 0，总效果和费用各 1，revision 不重复。

启用方式：原 `build_continuity_core` 使用 `ContinuityCoreGates(input_processing=True)`。默认 False 保持旧调用；未开关旧 native 轻量 operation 兼容已经专门回归。只读 `input_outcome(request_id)` 给出结构原因和原提交身份，返回前复核许可，不创建新模型调用或状态变化。未完成感知时只报告待完成，不公开尚不可核验的片段。

## 修改入口与责任

| 文件 | 变化 |
|---|---|
| [input_processing.py](../../../src/continuity_engine/domain/input_processing.py) | 输入解释/七类处置、不可改写的成功站历史、请求与感知绑定 |
| [input_processing_service.py](../../../src/continuity_engine/services/input_processing_service.py) | 有界解释、相关站选择、原巩固服务适配、原事实核验和本机短时 admission |
| [input_context_source.py](../../../src/continuity_engine/services/input_context_source.py) | 原 Context source/resolver 端口中的当前输入候选、当前权限和版本/hash 复查 |
| [continuity_core_runtime.py](../../../src/continuity_engine/services/continuity_core_runtime.py) / [continuity_core_service.py](../../../src/continuity_engine/services/continuity_core_service.py) | 原工厂可选装配和 C1 接线；保留关闭开关与原 native 入口 |
| [continuity_interaction_service.py](../../../src/continuity_engine/services/continuity_interaction_service.py) | 首次持久化前复用材料门禁、逐站保存/恢复、只读处置出口 |
| [continuity_core.py](../../../src/continuity_engine/domain/continuity_core.py) / [integration_results.py](../../../src/continuity_engine/domain/integration_results.py) / [json_integration_repository.py](../../../src/continuity_engine/storage/json_integration_repository.py) | 内部可选 checkpoint 与顺序/绑定核验；旧记录 round-trip 保留，原外部合同不改 |
| [w02_input_fixture.py](../../../src/continuity_engine/testing/w02_input_fixture.py) / 三份 `test_w02_input_*` | 隔离 TEST 数据、故障与真实进程回放；业务接线位于正常服务，不在演示代码里另造流程 |

本机 admission 复用现有 OS 锁原语，系统 Temp 仅留无业务内容的协调字节，不是第二请求/执行账本。未改 Scheduler、P18 Runtime、Thinking、Action/Evolution、Memory、权限或计费公共实现。没有修改原正式测试。精确路径及分类见 [清单](final.pending-files.md) 和 [逐文件哈希](final.inventory.json)。

## 本轮实跑与引用

{table}

以上三组有交集，不能相加为总数。JSON 的 seconds 是从加载到结束的墙钟时长；stderr 的 unittest 时长较短，两个口径均保留。原 1580 项身份及原断言保留，本批新增 {special['run']} 项。SKIP 仍是已有 Windows 符号链接创建权限 1314，不算 PASS；具体身份见全量 JSON。

历史基线仅引用 `pre_p19_supplement_evidence/full-final-01.json` 的 1580 项（1579 PASS、1 SKIP、1687.548 秒），不冒称本轮重跑。独立复核尚未进行，没有远端 CI 实跑或 CI PASS 声明。

最终 {len(src)} 份源码/测试/资源集合指纹：`{frozen['sourceHash']}`。三组运行前后均与 [冻结清单]({selected['source']}) 一致；早期 39/40 项版本属于历史，不能替代最终覆盖。

## 真实失败及修复

全部标签原始保留，见 [失败历史](failure-history.md) 与 [完整运行索引](test-history.md)。主要发现：

- 首条新开关反例红测试；早期测试曾误拒原 C1 合法 Genesis 记忆巩固，后来精确限定为不得把新消息造为事件。
- 材料拒绝测试的辅助端口签名错误被单独记录；发现的原始消息首次落 operation 前检查缺口，已在允许的 C1 接线复用原材料门禁。
- 两条伪造站点回执曾能冒称记忆或 Context 成功，已改为核对原权威事实，不靠日志标签自证。
- admission 曾扩大异常捕获范围，已限制为锁获取阶段，业务原异常保持。
- 首轮兼容真实暴露旧 native 缺新开关字段的回归，已在本批 CoreService 按缺省 False 处理。77 个失败记录、9 个错误及 1 SKIP 的旧输出完整保留；其中 3 加载错误及 2 运行期导入错误来自 runner 缺 tests 路径，未修改旧测试或跳过错误。新增 native 正式反例修前 ERROR、修后通过，完整兼容及全量另有最终新标签。

早期 runner 对有多个失败子用例的运行使用减法统计 passed，不能作为准确通过方法数；原 JSON 不改写，新 runner 用 unittest `addSuccess` 统计。历史失败和工具错误不混成同一类，也不并入 F1/H1/F2。

## 检查与停止边界

终局保护、源码静态解析、新增文档链接、敏感材料/产物检查、差异检查及只读 Git 状态见 [final.audit.json](final.audit.json)。原 63 项保护、六 Schema/25 冻结边界、旧三份规划、现行规划与归档、正式七文件、版本 0.1.0、32 排除项均按开工 hash 逐项核对。正式数据树应为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，实际结果以审计为准。

原 57 个未跟踪文件（32 排除项、25 份 W01/规划归档）与本批清单分开保留。源码固定后只整理文档；没有暂存、提交、push、真实服务连接或正式主体启动。

子进程由原测试控制器等待结束/明确 STOP；本轮进程观察见 [process-cleanup.json](process-cleanup.json)。不清理无关进程、旧缓存或其他用户材料。

## 剩余能力和待复核事项

有界规则不是完整语言理解，不能凭规则替模型或事实来源决定长期人格。Composer 当前输入预算不冒称重新定义所有旧 Provider 的总输入预算。历史恢复证明只适用于已验证本地 Fixture/Fake；不承诺任意生产 Adapter exactly-once，也不允许混用不同版本宿主共同写正式根。

W02-B 自动回忆、W02-C 外部资料完整可信吸收以及整个 W02 的最终贯通仍未施工。W03/P19 页面及 P20—P23 后置生产能力保持原阶段边界。历史 F1/H1/F2 原 UNKNOWN、D-073 接受遗留不确定性、D-074 既有验收均未重开或改写。

本轮不新增需用户选择的正式政策。下一步是按 [复核入口](review-entry.md) 独立核对本批实现和修补；通过后仍需用户确认，不自行开始下一批。

大白话：现在一条消息可以真正进入原来的思考链，并留下“用了什么、没有记住什么、为什么等证据、失败后接着做哪一步”的记录。您可以检查一条消息的去向，以及重启后是否只补没完成的步骤。自动翻旧经历、完整吸收外部资料和私有页面还不在这批里。
''')
    history=['# W02-A 全部运行索引','','各组有交集；只按最终全量报告正式测试总数。原始输出不可覆盖。',
        '早期 runner 的 passed 减法在失败子用例场景下可能不准确，失败运行列原始记录数，不替它补造通过数量。','',
        '| 标签 | 运行次数 | PASS（成功计数或无失败） | FAIL记录 / ERROR / SKIP | 秒 / exit | 源码前后相等 |',
        '|---|---|---|---|---|---|']
    for path in sorted(HERE.glob('*.json')):
        d=load(path.name)
        if not isinstance(d,dict) or 'sourceBefore' not in d:continue
        passed=d.get('passed') if not d.get('failures') and not d.get('errors') or 'successfulIdentities' in d else '见原始记录，不重算'
        history.append(f"| [{path.stem}]({path.name}) · [stderr]({path.stem}.stderr.log) · [stdout]({path.stem}.stdout.log) | {d.get('run','未完成')} | {passed} | {len(d.get('failures',[]))} / {len(d.get('errors',[]))} / {len(d.get('skips',[]))} | {d.get('seconds')} / {d.get('exitCode')} | {d.get('sourceBefore')==d.get('sourceAfter')} |")
    save('test-history.md','\n'.join(history)+'\n')
    save('continuation.md',f'''# W02-A 交付续接记录

{status}

{summary} 最终索引 selected-runs.json；源码 frozen-source-03.json，{len(src)} 文件，{frozen['sourceHash']}。

本轮已停止施工，交回独立复核。D-075 仅为开工，没有验收决定、没有 Git 写操作。{conflict}

已生成 final-report、矩阵、运行历史、精确清单及终局审计；源码/测试之后没有变更，不重复全量。各次首次失败、兼容回归、导入辅助错误和修前/修后记录全部保留。

原 P00—P18 验收、W01 与旧规划、32 排除材料及 F1/H1/F2 UNKNOWN 保留。W02-B/C、W03、P19 不自动开工。下一次接续先核对真实现场及最终源码身份，不重做本批。
''')
    matrix=(HERE/'matrix.md').read_text(encoding='utf-8')
    start=matrix.index('当前施工中');end=matrix.index('\n\n| 项',start)
    matrix=matrix[:start]+f'十二项均为 IMPLEMENTED_NOT_ACCEPTED，已完成本地验证，等待独立复核与用户确认。{summary} 下列测试名为定位入口，精确身份/结果见 [最终报告](final-report.md) 与 [运行索引](test-history.md)。本表不是整个 W02 完成或验收。'+matrix[end:]
    save('matrix.md',matrix)
    marker='<!-- W02_A_CURRENT -->'
    for relative in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md',
                     'docs/project_memory/06_未完成事项.md','docs/project_memory/CHANGELOG.md','docs/project_memory/工程总档案.md'):
        p=ROOT/relative;old=p.read_text(encoding='utf-8')
        boundary=old.index('<!-- PRE_P19_ACCEPTED_D074_20260920 -->')
        link='docs/project_memory/w02_a_evidence/final-report.md' if relative=='README.md' else 'w02_a_evidence/final-report.md'
        new=f'''{marker}
## W02-A 当前交付状态

用户已确认施工（D-075），{status} {summary}

本批完成原 C1 输入接线、相关站处置/理由及局部恢复；保留原 Authority、内部合法成长和现实边界。{conflict} P00—P18 历史验收、D-073/D-074 与 F1/H1/F2 UNKNOWN 原样保留。

原源码/测试固定后完整验证，保护核查和精确清单见 [交付与复核入口]({link})。本轮未暂存、提交、push 或正式验收。以下旧结论均是发生时的历史记录。

'''
        assert old.startswith(marker)
        p.write_text(new+old[boundary:],encoding='utf-8')
    decision=ROOT/'docs/project_memory/04_决策记录.md'
    original=decision.read_text(encoding='utf-8')
    note=f'''\n### D-075 施工交付事实（非验收）

2026-09-24：{status} {summary} 最终源码身份与三组运行前后清单一致。首次失败、native 回归和 runner 导入辅助错误原样保留。{conflict}

详见 [W02-A 交付报告](w02_a_evidence/final-report.md)。W02 后续子批次、W03、P19 未授权自动开始，无 Git 写操作，无新增正式政策或用户验收决定。
'''
    assert '### D-075 施工交付事实' not in original
    decision.write_text(original+note,encoding='utf-8')
    print(summary)


if __name__=='__main__':main()
