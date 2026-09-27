"""Prepend current authorization/progress; never replace historical sections."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
section='''<!-- W04_2_PUBLIC_REPAIR_CONTINUATION -->
## W04-2 公共验证阻断定向续修（非验收）

用户已授权W02回忆/P18锁异常的证据化最小修补，替代此前仅调查的停止点。main/HEAD fc185843…、原314项源码、91成果及70保留材料均先核验；原失败/历史F1/H1/F2 UNKNOWN保持。现有D-088不变，不创建验收决定。

第一轮五个原回忆及两个原锁测试带诊断本次通过，不据此关闭旧失败。进一步CPU剖析定位外部注册路径每祖先三次元数据查询；已仅在JsonExternalProviderRepository._safe合为一次当前lstat，仍每次重查全部祖先，不缓存授权/来源、不改1000ms。新增7项路径/读取边界回归通过；修前重复探测失败、一次注入位置不适用的辅助失败及导入错误全部保留。正式同版验证待完成，不冒称全量通过。

P18受控事务时序另复现两条原断言与有限等待的冲突：两个真实竞争区间可合法产生两条BUSY；owner已持有不保证checkpoint空闲，单次STOP可正确忙拒绝。原产品与原测试未改，STOP CURRENT ITEM，仅该项PLANNING_CONFLICT=PRESENT，已提交最小测试同步修正方案等用户决定。W02独立项继续；本批EVIDENCE_CONFLICT=PRESENT。无验收、Git写入或W04-3。

入口：[调查协议与矩阵](w04_2_public_repair_evidence/protocol.md) · [W02修法](w04_2_public_repair_evidence/w02-repair-plan.md) · [P18冲突证据及选项](w04_2_public_repair_evidence/p18-test-conflict.md) · [续接](w04_2_public_repair_evidence/continuation.md)。以下历史不倒改。

'''
for name in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md'):
    p=ROOT/'docs/project_memory'/name
    if not p.exists():raise RuntimeError('inspect actual archive path first: '+str(p))
    text=p.read_text(encoding='utf8')
    if '<!-- W04_2_PUBLIC_REPAIR_CONTINUATION -->' in text:raise RuntimeError('already recorded')
    p.write_text(section+text,encoding='utf8',newline='')
