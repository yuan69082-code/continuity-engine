"""Build review artifacts from completed runs; never prefill a test result."""
import ast,datetime,hashlib,json,os,re,runpy,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;DOC=OUT.parent;ROOT=OUT.parents[2]
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def create(name,value):
    with (OUT/name).open('x',encoding='utf8') as f:
        f.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def paths(*args):return git(*args).stdout.splitlines()
b=read(OUT/'before.json');frozen=read(OUT/'frozen-source-02.json')
source=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
assert source==frozen['source']
labels=['boundaries-final-04','originals-final-03','advancing-final-02','prior-boundaries-final-01',
        'native-denial-final-02','p18-final-01','compatibility-final-01','full-final-01']
runs={label:read(OUT/(label+'.json')) for label in labels}
for r in runs.values():
    assert r['status']=='FINISHED' and r['exitCode']==0 and not r['failures'] and not r['errors']
    assert r['sourceBefore']==source==r['sourceAfter']
full=runs['full-final-01'];p18=runs['p18-final-01'];compat=runs['compatibility-final-01']
assert set(full['testIdentities'])==set(frozen['identities'])
assert all(identity in b['testIdentities'] and '1314' in reason for identity,reason in full['skips'])
assert all(sha(ROOT/p)==h for group in b['protected'].values() for p,h in group.items())
assert sha(ROOT/'pyproject.toml')==b['pyproject']
assert {p.relative_to(ROOT).as_posix() for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}==set(b['protected']['formalFiles'])
assert not paths('diff','--cached','--name-only')
assert git('rev-parse','HEAD').stdout.strip()==b['head']==git('rev-parse','origin/main').stdout.strip()
assert git('branch','--show-current').stdout.strip()=='main'

history={}
for path in sorted(OUT.glob('*.json')):
    r=read(path)
    if 'status' in r and 'sourceBefore' in r:
        history[path.name]={k:r.get(k) for k in ('command','status','startedAt','finishedAt','seconds','run','passed','exitCode')}
        history[path.name].update(failureRecords=len(r.get('failures',[])),errorRecords=len(r.get('errors',[])),
            skips=r.get('skips',[]),sourceStable=r.get('sourceBefore')==r.get('sourceAfter'),
            matchesFinal=r.get('sourceBefore')==source==r.get('sourceAfter'))
create('test-history.json',history)
create('selected-runs.json',{'source':'frozen-source-02.json','runs':labels,'full':'full-final-01',
    'historicalBefore':'../p18_storage_repair_evidence/original-flows-before-01.json','overlappingSetsNotAdded':True})

matrix=read(DOC/'p18_persistence_evidence/matrix-test-map.json')
for key,row in matrix.items():
    relevant=[]
    if key in {'P18-01','P18-02','P18-04','P18-06','P18-07','P18-08','P18-09','P18-12'}:
        relevant += [t for t in frozen['addedIdentities'] if t.startswith('test_p18_storage_runtime.')]
    if key in {'P18-05','P18-08','P18-09','P18-11'}:
        relevant += [t for t in frozen['addedIdentities'] if t.startswith('test_p18_storage_retry.')]
    row['testIdentities']=sorted(set(row['testIdentities']+relevant))
    assert set(row['testIdentities'])<=set(p18['testIdentities'])<=set(full['testIdentities'])
    row['status']='IMPLEMENTED_NOT_ACCEPTED';row['evidence']='p18-final-01 / full-final-01'
create('matrix-test-map.json',matrix)

table='| 组 | PASS | SKIP | FAIL/ERROR | 秒 | 原始记录 |\n|---|---:|---:|---|---:|---|\n'
for label,r in runs.items():table+=f"| {label} | {r['passed']} | {len(r['skips'])} | 0/0 | {r['seconds']} | [{label}.json]({label}.json) |\n"
state='P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IMPLEMENTED_NOT_ACCEPTED；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT。D-072追加本次授权/返修事实，D-073未创建/未使用。'
summary=f"新增正式{len(frozen['addedIdentities'])}项，原{len(b['testIdentities'])}项身份及断言保留。P18 {p18['passed']} PASS；公共兼容 {compat['passed']} PASS；本轮最终全量 {full['run']}项={full['passed']} PASS、{len(full['skips'])}既有Windows 1314 SKIP、0 FAIL/ERROR，{full['seconds']}秒，exit 0。各组重叠，不相加。"
report='# P18 统一有限存储尝试：返修交付\n\n'+state+'\n\n'+summary+'\n\n'
report+='当前两个读句柄机制有修前失败、同流程修后通过。历史F1/H1/F2仍缺原现场证据，不能唯一归因或合并结案；详见[因果调查及首次失败分类](investigation-notes.md)。当前实现交独立复核，不构成验收。\n\n'
report+='## 实际修改与公共影响\n\n仅两个运行文件：`src/continuity_engine/storage/json_repository.py`、`src/continuity_engine/storage/json_runtime_repository.py`；新增两份P18测试文件。其余运行实现和旧测试文件与开工hash一致。\n\n'
report+='SubjectState沿用显式P18授权；完整操作绑定、原payload/临时inode、目标字节/身份、目录、当前权限/属性及版本检查通过后，在原0.25秒预算内继续同一次原生替换。完整绑定固定WinError5可以有限尝试；无绑定错误、无授权旧路径不取得此资格。当前允许尝试不证明过去一定发生共享冲突。运行实现不改ACL/只读属性、不提权，不另换写入方式。\n\n'
report+='Checkpoint沿用原OS事务锁和CAS，事务资格绑定实例、线程及活动生命周期；原owner/generation/control文档受当前检查约束。合格尝试耗尽用静态内部类型保留失败并交原宿主等待处理，不能误写BACKOFF、伪报提交或终止主体；真实拒绝、损坏及冲突仍失败。保留原生与清理异常链。\n\n'
report+='## 原始目标与持续运行语义核对\n\n'
report+='- 已实测：无聊天、沉默和空闲继续运行；真实进程长读占用超过提交预算后仍存活、可查询，释放后Frozen时间下重获资源等待观察；资源恢复后无需聊天推进。\n'
report+='- 已实测：PAUSE阻止新执行，RESUME恢复；STOP终态不复活；R1单宿主/锁/CAS与R2调用阶段保护继续覆盖。\n'
report+='- 已实测：SubjectState局部等待时独立Memory维护仍推进；原已执行事实恢复不重调用模型、不重派动作、不重扣credits，不重复revision。保存成功返回丢失重放原记录。\n'
report+='- 限制：关键状态不可信仍明确拒绝；本轮不承诺任意存储故障都能推进其他任务、不承诺生产exactly-once。真实常驻部署、自启动、供应商/凭据、生产恢复和正式联系政策仍未开放。没有新增引擎运行时长、tick数量或随机停机规则。\n\n'
report+='## 本轮实际验证\n\n'+table+'\n上述最终组运行前后均匹配[最终源码身份](frozen-source-02.json)。标准输出/错误输出与同名JSON在本目录，命令在每个JSON内。SKIP按上表及原始记录实录，与PASS分开；允许引用的既有原因仅Windows符号链接权限1314。没有远程CI运行，不能声称CI PASS。\n\n'
report+='## 修前及中间记录\n\n修前原对照/反例4项=2PASS/2FAIL，79.248秒，是开工核对一致的上轮实际运行引用，不冒充本轮重跑。当前完整运行和旧记录严格分开。新TEST长路径3FAIL、三项守卫反例、过期事务Context ERROR、辅助缩进错误均保留；详细[测试历史](test-history.json)。旧full-final-01中断、H1/F1/F2失败、P09 segment10 UNKNOWN及历次SKIP不改写。\n\n'
report+='## 可复跑入口\n\n在Engine根设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，使用未占用标签：\n\n```powershell\n& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-storage-01 test_p18_storage_\n& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-originals-01 --review-class original_suites.baseline_suite\n& E:/Adobe/python.exe docs/project_memory/p18_storage_final_evidence/run.py review-p18-01 test_p18_\n```\n\n不重执行已用标签或整个旧validate脚本。若独立复核需要全量，用新标签且不带测试前缀。\n\n'
report+='## 清单、保护与停止位置\n\n[终局审计](final.audit.json)记录63项保护、三规划、正式七文件、版本/pyproject与32项排除材料，及原件/副本hash。[完整P18未提交清单](final.pending-files.md)区分开工已有成果、本轮增量和排除项；[本轮逐文件变化](turn-changes.json)。没有Git写操作。保持未验收，等待独立复核，不进入P19。\n'
create('final-report.md',report)

names=['01_当前状态.md','03_施工日志.md','04_决策记录.md','05_已完成模块.md','06_未完成事项.md','07_待确认事项.md',
       '10_档案修订记录.md','83_P18_PersistentRuntime架构与开工简报.md','84_P18_规划施工测试验收矩阵.md',
       '85_P18_持续运行控制资源等待与恢复语义.md','86_P18_测试索引与验收入口.md','CHANGELOG.md','工程总档案.md']
changed_docs=['README.md']+['docs/project_memory/'+n for n in names]
for rel in changed_docs:
    p=ROOT/rel;prefix='docs/project_memory/' if rel=='README.md' else ''
    block='<!-- P18_STORAGE_REPAIR_FINAL_20260914 -->\n'+state+'\n\n'+summary+'\n\n'
    block+='用户已明确授权两个存储文件及完整绑定WinError5的有限尝试变化，本轮补修和验证完成待独立复核。有限尝试只约束同一存档，不改变宿主默认持续运行；不重派动作、不重复扣费。F1/H1/F2历史唯一根因仍未证实。\n\n'
    block+=f'[完整返修报告、证据与持续运行核对]({prefix}p18_storage_final_evidence/final-report.md) · [清单/审计]({prefix}p18_storage_final_evidence/final.pending-files.md)。\n\n'
    if p.name.startswith('84_'):
        block+='| 矩阵 | 现行状态 | 最终身份覆盖 |\n|---|---|---:|\n'
        for key,row in matrix.items():block+=f"| {key} | IMPLEMENTED_NOT_ACCEPTED | {len(row['testIdentities'])} |\n"
        block+='\n[精确身份映射](p18_storage_final_evidence/matrix-test-map.json)。各行可交叉引用，不重复计数。\n\n'
    block+='以下均保留此前阶段/中间结果及当时授权状态，不倒改历史。\n\n'
    p.write_text(block+p.read_text(encoding='utf8'),encoding='utf8')
with (OUT/'continuation.md').open('a',encoding='utf8') as stream:
    stream.write('\n## 最终交付进度\n\n'+summary+'\n最终结果已完成，标签见selected-runs.json；源码仍frozen-source-02。不要再次跑全量。审计后交独立复核，历史UNKNOWN及EVIDENCE_CONFLICT保留。\n')
create('documentation-files.json',changed_docs)
print(summary)
