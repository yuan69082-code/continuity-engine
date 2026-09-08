"""Render repair results from completed evidence, without touching code or old logs."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DOC=ROOT/'docs/project_memory'

def main():
    labels=['independent-before','formal-before','r1-r3-first','formal-first',
        'legacy-additions-before','legacy-additions-after','targeted-final','independent-after',
        'p15-final','clock-compat','targeted-stable','independent-stable','p15-stable',
        'compatibility-final','full-final']
    runs={name:json.loads((OUT/(name+'.json')).read_text(encoding='utf-8-sig')) for name in labels}
    stable=['targeted-stable','independent-stable','p15-stable','compatibility-final','full-final']
    assert all(runs[n]['status']=='FINISHED' and runs[n]['exitCode']==0 for n in stable)
    source=runs['full-final']['sourceAfter']
    assert all(runs[n]['sourceBefore']==runs[n]['sourceAfter']==source for n in stable)
    table=['| 本轮实跑标签 | 项数 | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | 原始输出 |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    commands=[]
    for name,r in runs.items():
        table.append(f"| [{name}](p15_repair_evidence/{name}.json) | {r['run']} | {r['passed']} | {len(r['failures'])} | {len(r['errors'])} | {len(r['skips'])} | {r['seconds']:.3f} | [stdout](p15_repair_evidence/{name}.stdout.log) / [stderr](p15_repair_evidence/{name}.stderr.log) |")
        commands.append(' '.join(r['command']))
    full=runs['full-final']
    body='''
## 本轮完成与待复核

R1/R2/R3已实现并完成下列本地验证，P15仍IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT等待独立复核，PLANNING_CONFLICT=NONE。没有自行验收、Git写操作或P16施工。

| 根因 | 修复责任与入口 | 正向和拒绝覆盖 |
|---|---|---|
| R1 缺字段一律兼容且历史只验revision | `storage/json_repository.py`核对原生命周期命令/变化/身份与当前终值，读写前失败关闭；真正无生命周期历史仍兼容 | 暂停缺字段、删除旧片段、Owner/environment/subject篡改、before/after冲突零写入拒绝；真正旧格式、普通同名旧Event、暂停恢复和历史重放保留 |
| R2 Learning先宣称完成导致旧revision无法继续 | `domain/learning.py`、`learning_service.py`、`json_learning_repository.py`、`subject_growth_service.py`沿用原Learning历史，区分PREPARED/真实COMMITTED/SUPERSEDED；新有效确认在当前revision继续，原命令终止且保留 | SOLIDIFY/ROLLBACK均覆盖无关状态变化、原准备记录不可改绑、提交后重启、终止后重启、旧格式待提交、来源/权限拒绝、原事实缺失失败关闭 |
| R3 read_growth缺返回前检查 | `mind_projection_service.py`返回前重读完整状态/hash与策略绑定，并复核当前权限及export | 中途撤权、EXPIRED、状态及同revision内容变化、export限制拒绝；合法观察零写入 |

具体恢复语义见[73](73_P15_成长纠错与生命周期恢复语义.md)。原1176项身份及原测试文件保留；新增32项，其中原有效探针8项字节不变纳入正式回归，补充24项。独立报告的原39 PASS/8项4 FAIL是监工历史实跑；本表原探针复跑由施工方执行，不冒称新的独立复核。旧1176全量仅历史引用。本轮完整结果以full-final为准。

## 命令与真实结果

'''+ '\n'.join(table)+'''

方法含subTest时FAIL/ERROR记录数不能与PASS直接相加冒充方法总数。首次失败及辅助错误详见[中间记录](p15_repair_evidence/auxiliary-errors.md)，不因后续PASS覆盖。P09 segment 10 stderr缺失、根因UNKNOWN及全部旧失败/SKIP保持历史原样。

```text
'''+ '\n'.join(commands)+'''
```

完整回归SKIP原始记录：

```text
'''+ json.dumps(full['skips'],ensure_ascii=False,indent=2)+'''
```

## 独立复核入口

在Engine仓库PowerShell设置环境后执行；输出使用新标签，runner拒绝覆盖旧日志。复核者可按影响选择定点、专项及完整，以下不是声称已由监工执行。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p15_repair_evidence/run.py review-probe --independent-probe
python docs/project_memory/p15_repair_evidence/run.py review-targeted test_p15_review_regressions test_p15_repair_edges
python docs/project_memory/p15_repair_evidence/run.py review-p15 test_p15_
python docs/project_memory/p15_repair_evidence/run.py review-full
```

最终源码逐文件hash、原1176身份保留、保护指纹、AST/链接/敏感内容/diff检查及完整Git状态见[终局审计](p15_repair_evidence/final.audit.json)。全P15成果和本轮修复的精确清单见[待提交清单](p15_repair_evidence/final.pending-files.md)，只提供清单，不暂存。31个P10排除脚本和原P14接续报告单列，不纳入修复。无Assistant改动、真实Provider、正式数据或备份操作。

## 限制

生命周期一致性核对不能证明所有存档及历史被一致替换时的外部真实性，不代替生产备份/灾难恢复。Learning审计仍在原仓储，SubjectState/Evolution为实际人格唯一权威；未新增请求账本。正式归档、删除和隐私策略不在本轮决定；TEST逻辑删除不代表物理擦除。测试通过不关闭独立复核阻断。

返修前before.json保留原来源字段，其中citedBaseline为继承的P14历史溯源；本轮实际返修基线为sourceTest的230文件、testIdentities的1176身份及原P15独立identity-check，不将P14数字作本轮结果。
'''
    report=DOC/'P15_独立复核返修_R1-R3.md'
    text=report.read_text(encoding='utf-8-sig').split('## 接续进度')[0]+body
    report.write_text(text,encoding='utf-8')
    for p in [ROOT/'README.md',*DOC.glob('*.md')]:
        text=p.read_text(encoding='utf-8-sig')
        if '<!-- P15_REPAIR_CURRENT_START -->' not in text:continue
        text=text.replace('当前正在施工。','本轮实现与测试完成，交回独立复核。')
        p.write_text(text,encoding='utf-8')
    additions={
      '04_决策记录.md':'### D-066 追加：合并返修完成，等待独立复核\n\nR1/R2/R3的范围内实现及最终本地专项、兼容和全量已完成，真实数量、耗时、首次失败与源码身份见返修入口。P15保持IMPLEMENTED_NOT_ACCEPTED，EVIDENCE_CONFLICT=PRESENT；未登记验收决定。',
      '71_P15_人格关系学习与主体生命周期架构边界.md':'## R1/R2/R3 Stage Brief 增量\n\n用户合并返修授权优先；FILES ALLOWED限定返修入口列明的6个现有运行文件、原探针正式副本及24项边界测试、直接档案与证据。其余SOURCE OF TRUTH、KEEP、NOT_READY与FILES FORBIDDEN不变。未改变生产策略、冻结边界或Authority；三项完成后等待独立复核。',
      '72_P15_规划施工测试验收矩阵.md':'## 本次三项返修与十二项映射\n\n上表39项及“本轮PASS”属于初版施工历史。当前71项专项含原39项、8项原探针及24项补充回归。R1覆盖07/08/09/11/12，R2覆盖01/02/03/12，R3覆盖04/05/12；其余原用例完整保留并在本轮专项重跑。十二行状态不变，不能将施工PASS冒称独立验收。',
      '74_P15_测试索引与验收入口.md':'## 当前有效返修入口\n\n本次使用p15_repair_evidence中的stable、compatibility-final、full-final结果；下方原39/1176等仅为历史。原探针字节一致的正式回归为test_p15_review_regressions.py；补充回归为test_p15_repair_edges.py。日志保留stdout/stderr、命令、时间、测试身份和前后源码hash。',
    }
    for name,addition in additions.items():
        p=DOC/name;text=p.read_text(encoding='utf-8-sig')
        assert addition.split('\n')[0] not in text
        p.write_text(text+'\n\n'+addition+'\n\n详见[合并返修报告](P15_独立复核返修_R1-R3.md)。\n',encoding='utf-8')
    print('repair documents updated from completed results')

if __name__=='__main__':main()
