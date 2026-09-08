"""Register the user's P16 acceptance; only current documentation is updated."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;DOC=ROOT/'docs/project_memory'
def main():
    before=json.loads((OUT/'before.json').read_text(encoding='utf-8'))
    decisions=DOC/'04_决策记录.md';text=decisions.read_text(encoding='utf-8-sig')
    assert not re.search(r'^## D-069[：:]',text,re.M)
    entry=DOC/'P16_用户正式验收_20260909.md';assert not entry.exists()
    report='''# P16 用户正式验收与 Git 收尾入口

2026-09-09 用户正式验收 P16 初版及 R1/R2/R3 返修，登记 [D-069](04_决策记录.md)。P00—P16 ACCEPTED；P16 / Engine side / P16-01—P16-12 ACCEPTED；P16 Vio dependency = NONE；P17—P23 NOT_STARTED。现行 PLANNING_CONFLICT = NONE、EVIDENCE_CONFLICT = NONE，仅表示本次独立复核覆盖范围内已知三项阻断闭合，不保证不存在其他缺陷。

## 验收依据与统计边界

[独立复核报告原样副本](p16_repair_evidence/independent/repair-review-report.md)、[22 项独立身份检查](p16_repair_evidence/independent/repair-identity-check.json)支持本次验收。24 件本次独立报告、原始输出、前后快照及必要脚本追加到既有独立证据目录，复用此前失败报告及脚本，不重复复制旧材料。[来源和副本逐文件 hash](p16_acceptance_evidence/before.json)保留完整路径；规划侧原件只读。

| 来源 | 验证 | 真实结果 | unittest 秒 | 包装器秒 |
|---|---|---|---:|---:|
| 监工独立实跑 | 原九项探针 | 9 PASS，0 SKIP/FAIL/ERROR | 6.849 | 7.455 |
| 监工独立实跑 | 当前完整 P16 | 78 PASS，0 SKIP/FAIL/ERROR | 112.062 | 112.712 |
| 监工独立实跑 | 额外独立检查 | 4 PASS，0 SKIP/FAIL/ERROR | 3.843 | 4.657 |
| 监工只读核查 | 身份与保护 | 22/22 通过，不是行为测试 | — | 2.038 |
| 施工方实跑，经监工核验引用 | 最终全量 | 1286 项：1285 PASS、1 SKIP、0 FAIL/ERROR | 见原始 stderr | 1072.026 |

原九项已经包含在正式 78 项中，不重复相加；额外四项不增加 Engine 正式测试数量。正式 1286 项保留原 1261 身份，新增 25 项。唯一 SKIP 为 `OS does not grant symlink creation: 1314`，不计 PASS。[最终全量原始记录](p16_repair_evidence/full-final-01.json)和 [stderr](p16_repair_evidence/full-final-01.stderr.log)对应当前 243 个源码/测试/资源文件。本次验收归档没有重跑专项或全量，也不是远端 CI。

## 当前实现与未开放边界

宿主中立的 Memory/Knowledge Provider、MCP/Skill 查询、Credential Broker 引用、注册/缓存/撤销恢复已在正常 C1 与唯一 E5-A 通道内实现并验收。R1 覆盖整份回执材料；R2 覆盖首次持久化、processor 前后、C1 模型结果入账及恢复；R3 使用静态错误码与安全异常链。原 UNKNOWN 先查事实、不盲目重发，以及普通心理内容查询、当前权限、Context、生命周期和学习支持校验保留。

真实服务清单、生产供应商、凭据、生产隐私政策、生产传输/认证/恢复及后续接入仍 NOT_READY；没有上线或启用真实服务，不新增 Authority 或账本，不声称任意生产 Adapter exactly-once。六份 Schema、冻结外部契约、63 保护项、三份规划、正式七文件、pyproject 和版本 0.1.0 不变。正式数据树为 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。不修改 Assistant/Vio，不进入 P17。

## 提交与审计入口

开工实测 main，HEAD、本地 origin/main 和实际 `git ls-remote origin refs/heads/main` 均为 `a41a733635b0f5978c19b287274b4c63925b8979`；暂存区空。原 192 项 P16 清单与 32 排除项精确覆盖原工作区，243 文件 hash 和独立四轮各 1949 文件前后快照一致。[开工核对](p16_acceptance_evidence/before.json)及[元数据读取辅助错误](p16_acceptance_evidence/baseline-auxiliary-error.log)保留；字段名错误不属于 Engine 缺陷。

完整授权范围由原 192 项加必要验收档案与复核证据组成，准确路径和数量见[逐文件提交及排除清单](p16_acceptance_evidence/commit-files.md)、[机器清单](p16_acceptance_evidence/commit-manifest.json)及[提交前审计](p16_acceptance_evidence/precommit.audit.json)。原31个 P10 脚本和1份 P14 接续报告继续原样排除，不纳入提交；缓存、正式数据、构建/Temp 产物和凭据不得入 Git。

本次用户授权一次普通提交 `feat: implement and accept P16 external capability providers`，仅在现有 Engine main 按精确路径暂存、普通 push 到既有 origin/main。提交 SHA、直接父提交和真实远端/CI 状态须在提交形成后读取并报告，不在提交中编造自身 SHA。没有 Engine Actions workflow，不新增 workflow，不把本地结果冒充 CI PASS。收尾后工作区仅保留明确排除项，不为记录自身 SHA 留下一份未说明改动。

## 历史保留

[初版施工证据](p16_evidence/test-history.md)、[返修全部运行历史](p16_repair_evidence/test-history.md)、[返修矩阵原始快照](p16_acceptance_evidence/matrix-before.md)以及旧 IMPLEMENTED_NOT_ACCEPTED/PRESENT 状态完整保留。原五个有效失败、首次临时路径错误、修复中辅助 ERROR、WinError 1314 和 P09 segment 10 stderr 缺失/根因 UNKNOWN 不改写。已知历史格式告警继续列入审计，不为通过扫描修改原始日志。
'''
    entry.write_text(report,encoding='utf-8')
    matrix=DOC/'76_P16_规划施工测试验收矩阵.md'
    with (OUT/'matrix-before.md').open('xb') as stream:stream.write(matrix.read_bytes())
    # This exact historical snapshot has relative links based on project_memory;
    # keep bytes unchanged and audit its links using its original location.
    m=matrix.read_text(encoding='utf-8-sig')
    m,count=re.subn(r'(^\| P16-\d{2} \|[^\n]*?\| )IMPLEMENTED_NOT_ACCEPTED( \|)',r'\1ACCEPTED\2',m,flags=re.M);assert count==12
    m=m.replace('十二项均 IMPLEMENTED_NOT_ACCEPTED，等待独立复核和用户验收','十二项已由用户按 D-069 正式验收，均为 ACCEPTED')
    m=m.replace('## 本次修复与十二项对应','## 本次返修时的十二项对应（历史记录）')
    matrix.write_text(m,encoding='utf-8')
    block='''2026-09-09 用户正式验收 P16 初版及 R1/R2/R3 返修（D-069）。P00—P16 ACCEPTED；P16 / Engine side / P16-01—P16-12 ACCEPTED；P16 Vio dependency = NONE；P17—P23 NOT_STARTED。现行 PLANNING_CONFLICT = NONE、EVIDENCE_CONFLICT = NONE，仅表示独立复核覆盖范围内已知阻断闭合，不保证不存在其他缺陷。

监工独立实跑：原九项9/9、完整P16 78/78、额外4/4 PASS，身份保护22/22通过。九项包含在78项中，额外四项不增加Engine正式测试数。全量引用已核验的施工方1286项：1285 PASS、1既有Windows 1314 SKIP、0 FAIL/ERROR，1072.026秒；本次归档未重跑行为测试。

真实服务、生产凭据与生产隐私政策等仍 NOT_READY。用户仅授权本阶段精确清单普通提交与push；不进入P17。下方此前未验收、PRESENT、D-069未使用及无Git授权说明均为历史，全部失败、辅助错误、SKIP和旧UNKNOWN保留。'''
    paths=[ROOT/'README.md']+[p for p in DOC.glob('*.md') if '<!-- P16_REPAIR_CURRENT_START -->' in p.read_text(encoding='utf-8-sig')]
    paths.append(DOC/'P16_独立复核返修_R1-R3.md')
    for p in dict.fromkeys(paths):
        old=p.read_text(encoding='utf-8-sig');assert '<!-- P16_ACCEPTED_START -->' not in old
        link='docs/project_memory/P16_用户正式验收_20260909.md' if p==ROOT/'README.md' else 'P16_用户正式验收_20260909.md'
        p.write_text('<!-- P16_ACCEPTED_START -->\n'+block+'\n\n[正式验收依据、审计与提交清单]('+link+')。\n<!-- P16_ACCEPTED_END -->\n\n'+old,encoding='utf-8')
    with decisions.open('a',encoding='utf-8') as stream:
        stream.write('\n\n### D-068 追加：开工及返修由 D-069 正式验收收口\n\n2026-09-09 用户确认验收初版及 R1/R2/R3。开工与返修历史不倒改，现行已知证据阻断由独立复核及用户验收闭合。\n\n## D-069：用户正式验收 P16 初版及 R1/R2/R3 返修\n\n'+block+'\n\n依据[独立报告](p16_repair_evidence/independent/repair-review-report.md)及[验收入口](P16_用户正式验收_20260909.md)，用户已授权 Engine main 精确清单一次普通提交并推送既有 origin/main，不授权 P17。\n')
    for name in ('03_施工日志.md','10_档案修订记录.md','CHANGELOG.md','工程总档案.md'):
        with (DOC/name).open('a',encoding='utf-8') as stream:stream.write('\n\n## 2026-09-09 P16 正式验收归档\n\nD-069 登记初版及 R1/R2/R3 用户正式验收；当前已知阻断闭合，阶段止于 P16。原测试与实现未变，本次核对独立证据并同步验收档案，引用已验证全量，不新增运行结果。精确提交和保护检查见 [验收入口](P16_用户正式验收_20260909.md)。版本仍0.1.0。\n')
    print('D-069 registered; 12 current matrix rows ACCEPTED; historical evidence retained')
if __name__=='__main__':main()
