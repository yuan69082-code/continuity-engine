"""Append the authorized review blockers without rewriting old evidence."""
from pathlib import Path
root=Path(__file__).resolve().parents[3]
docs=root/'docs/project_memory'
for p in [root/'README.md',*docs.glob('*.md')]:
    s=p.read_text(encoding='utf-8')
    if '<!-- P13_CURRENT_START -->' in s:
        if '<!-- P13_REPAIR_CURRENT_START -->' in s: raise RuntimeError('already recorded')
        prefix='docs/project_memory/' if p==root/'README.md' else ''
        block=('<!-- P13_REPAIR_CURRENT_START -->\n'
            '> P13 R1/R2 独立复核返修（2026-09-08，D-062）：P00—P12 ACCEPTED；P13 / Engine side / 十二项 IMPLEMENTED_NOT_ACCEPTED；P14—P23 NOT_STARTED；Vio dependency=NONE。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=PRESENT，须待再次独立复核关闭。用户已授权两项定点修复，不授权验收或 Git 操作。旧 1049 项全量仅引用，不能覆盖新反例。\n>\n'
            f'> [本轮原始探针实跑](%sp13_repair_evidence/probes-before.stderr.log)：7 项，4 FAIL、3 PASS、0 ERROR，4.645 秒；[独立原件](%sp13_repair_evidence/independent/review-report.md) 的未授权措辞是本次用户确认之前的历史。下方初版送审状态与数字保留为历史。\n'
            '<!-- P13_REPAIR_CURRENT_END -->\n\n')%(prefix,prefix)
        p.write_text(block+s,encoding='utf-8')
with (docs/'04_决策记录.md').open('a',encoding='utf-8') as f:
    f.write('\n## D-062 R1/R2 返修授权事实（2026-09-08）\n\n用户经规划任务确认同时修复当前 expression:emit 授权遗漏与未授权 Context 材料使用。只允许两项必要代码、回归、档案；先保留七项真实红测。P12/D-061 验收不变；P13 未验收，EVIDENCE_CONFLICT=PRESENT。只读基线 211 源码/测试资源、63 保护文件与 119 待提交内容 hash 一致。未使用新的验收编号，不执行 Git 写操作。[证据](p13_repair_evidence/before.json)。\n')
