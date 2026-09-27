"""Write current delivery documents from completed evidence only; no Git writes."""
from datetime import datetime, timezone
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
report=HERE/'final-report.md'
if report.exists(): raise SystemExit('final report exists; preserve it')
data=json.loads((HERE/'final-test-summary.json').read_text(encoding='utf-8'))
examples=json.loads((HERE/'chain-examples.json').read_text(encoding='utf-8'))
fp=data['source_fingerprint']
assert examples['source_before']==examples['source_after']==fp
assert examples['status']=='COMPLETED' and examples['exit_code']==0
runs=data['selected']
assert all(r['exit_code']==0 and r['source_before']==r['source_after']==fp for r in runs)
rows=[]
for name,r in zip(('专项（含W04-1）','受影响兼容','完整回归'),runs):
    c=r['counts']
    rows.append(f"| {name} | {r['total']} | {r['passed']} | {c['skipped']} | {c['failures']} / {c['errors']} | {r['duration_seconds']} | [原始记录]({r['result']}) |")
table='\n'.join(rows)
report.write_text(f'''# W04-2 交付报告

状态：**IMPLEMENTED_NOT_ACCEPTED**，交回独立复核；W04整体仍IN_PROGRESS，W04-3未开工。D-088仅为开工决定，不是验收。PLANNING_CONFLICT=NONE（本批已核范围）；本轮中间实现问题已修复并验证，尚未由独立复核或用户验收。历史F1/H1/F2继续UNKNOWN。

## 实际完成

1. 模拟界面可观察、定位、点击、输入、滚动、保存、发送与再观察。请求绑定主体、环境、软件、设备、账号、会话、连接代次、当前页面/焦点及期限。CLICKED不等于SAVED/SENT；无法证实结果时保持UNKNOWN。
2. 模拟身体传感经原Perception形成明确分源的观察；模拟动作经原ActionPlanning/P17门禁到外部隔离替身，再由原E5-A记录核验事实。原始消息C1和后续Thinking/Action/Evolution吸收均有正式测试；不由Adapter直接修改SubjectState。
3. 局部历史界面查询保留时间/对象/软件/会话/来源/当前权限，结果经原Router/Composer。相同根重读不虚增独立证据；撤回或过期停止消费，旧回执不删除。
4. 回执丢失、真UNKNOWN、可靠未执行、取消、重开和三个真实子进程恢复分别验证。断线/锁屏只阻塞相关操作，同一主体的宿主控制和其他合法工作仍可推进。

详细规划对应：[矩阵](matrix.md) · [正式入口与测试定位](coverage-map.md) · [公共兼容及NOT_READY](implementation-notes.md)。

## 同版施工方实跑

固定314项源码/测试/资源：`{fp}`。原1802项测试身份及原113份测试文件字节保留，新增42项；最终身份差集见[汇总](final-test-summary.json)。各集合有交集，不相加。

| 集合 | 总数 | PASS | SKIP | FAIL / ERROR | runner秒 | 证据 |
|---|---|---|---|---|---|---|
{table}

以上是施工方本轮实跑，规划窗口尚未对本批完成独立复核；没有把旧结果写成本轮实跑，没有取得远端CI结果。完整回归的既有Windows 1314权限SKIP不计PASS。stdout/stderr、命令、退出码、运行前后指纹与全部中间失败见[测试索引](test-index.md)。

## 首次失败与修复

原Action契约缺少本批设备参数接线的修前ERROR已保存。新增历史范围数组的tuple/list持久化身份差异已规范化为JSON值并复跑。新夹具还出现时间格式、重放后误读last_action、拒绝返回方式、深临时路径和生命周期命令误用等辅助失败；逐项原因、原输出和修复后结果见[失败历史](failure-history.md)，未修改既有断言或时限。

## 可读链路与最小查询

[三条真实隔离样例](chain-examples.json)记录消息、请求、观察、回执、根、Context引用和效果/费用。样例各使用独立TEST根，不冒充W04-4跨入口贯通，不计入正式测试数量。最小只读入口为observe、inspect与history_context，详见[复核入口](review-entry.md)；这些查看不会触发模型、业务续跑或主体revision。

## 修改范围与保护

原公共运行文件只改ActionSpecification、ExecutionService、ExecutionContextSource；新增DeviceCommand/Observation、DeviceOperationService、隔离Fixture和正式测试，共7份实现/测试文件。版本化设备参数使用原E5-A，无第二请求/结果/主体账本。具体变更及hash见[最终逐路径清单](final.pending-files.md)，核对项见[终局审计](final.audit.json)。

63项保护、7份正式数据、三份现行规划及70份既有保留材料逐项核对；70份为原57份加13份不重叠的D-085独有材料，共享档案仅在顶部新增本轮记录，旧内容保留。不得把这些保留材料算作本批成果。最终Git状态、AST、链接、敏感模式和临时产物检查原始结果在终局审计中；Git的LF→CRLF提示如实保留，不据此改写证据。

## 限制与下一步

本批只证明明确模拟控件、位置传感/动作、局部查询及其工程链，未证明任意软件视觉、真实语言质量、真实硬件、生产恢复或生产exactly-once。W04-3自主发现、W04-4跨入口总联验、W05自然记忆/再理解/梦、P19页面、P20/P21正式恢复、P22真实接入均未完成。W02原1000毫秒配置及已有负载回归保留，不保证更大负载永不超时。

未暂存、提交、推送，未操作真实桌面/账号/设备或生产服务。下一步仅交规划窗口独立复核及用户决定。
''',encoding='utf-8')
matrix=HERE/'matrix.md'
text=matrix.read_text(encoding='utf-8')
text=text.replace('开工阶段均 IN_PROGRESS，不是验收。','本批交付状态 IMPLEMENTED_NOT_ACCEPTED；实现/测试通过不是正式验收。具体方法与原始结果见 [coverage-map.md](coverage-map.md)、[test-index.md](test-index.md)。')
text=text.replace('| IN_PROGRESS |','| IMPLEMENTED_NOT_ACCEPTED |')
matrix.write_text(text,encoding='utf-8')
entry=HERE/'review-entry.md'
text=entry.read_text(encoding='utf-8').replace('实际最终结果与交付清单在收尾时另行生成，未完成运行不可算通过。',
    '最终结果见 [交付报告](final-report.md)、[测试索引](test-index.md)、[终局审计](final.audit.json) 和 [精确清单](final.pending-files.md)。')
entry.write_text(text,encoding='utf-8')
spec,compat,full=runs
common=(f'W04-2为IMPLEMENTED_NOT_ACCEPTED；W04整体IN_PROGRESS，W04-1/D-087保持ACCEPTED，W04-3未开工。D-088仅为开工决定。'
        f'施工方同版专项{spec["passed"]} PASS（新增42及原W04-1的29），兼容{compat["passed"]} PASS，'
        f'全量{full["total"]}项：{full["passed"]} PASS、{full["counts"]["skipped"]}既有Windows 1314 SKIP、0 FAIL/ERROR。集合重叠不相加。'
        f'314项固定源码指纹 `{fp}`；原1802身份、原测试断言保留。未取得远端CI结果。')
for name in ('01_当前状态.md','03_施工日志.md','04_决策记录.md','06_未完成事项.md','10_档案修订记录.md','工程总档案.md'):
    path=ROOT/'docs/project_memory'/name
    old=path.read_text(encoding='utf-8')
    assert '<!-- W04_2_DELIVERY -->' not in old
    prefix=('<!-- W04_2_DELIVERY -->\n## W04-2 本轮施工交付，等待独立复核\n\n'+common+'\n\n'
        '已接通模拟UI受控操作、模拟身体感知/动作和局部历史查询；复用原Action/P17/E5-A、Perception、Router/Composer及Thinking/Evolution。'
        '拒绝、UNKNOWN、撤权、换身体、重开、重复回执和宿主局部等待均有正反证据；原始失败及辅助错误不倒改。'
        '历史F1/H1/F2仍UNKNOWN；生产能力及W04后续批次未开放。未暂存、提交、push或自行验收。\n\n'
        '[交付报告](w04_2_evidence/final-report.md) · [规划矩阵](w04_2_evidence/matrix.md) · [原始测试索引](w04_2_evidence/test-index.md) · '
        '[首次失败](w04_2_evidence/failure-history.md) · [终局审计与清单](w04_2_evidence/final.audit.json)。\n\n')
    path.write_text(prefix+old,encoding='utf-8')
continuation=HERE/'continuation.md'
old=continuation.read_text(encoding='utf-8')
continuation.write_text('## 本轮最终接续点\n\n'+common+'\n\n全部选定验证与链路样例完成；下一步仅独立复核。最终文件及进程核对见final.audit.json和process-cleanup.json。以下是施工时历史进度，不代表仍有测试运行。\n\n'+old,encoding='utf-8')
print(json.dumps({'at_utc':datetime.now(timezone.utc).isoformat(),'status':'IMPLEMENTED_NOT_ACCEPTED','source':fp},ensure_ascii=False))
