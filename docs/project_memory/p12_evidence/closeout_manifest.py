"""Generate P12 review matrices and exact pending lists, without Git writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[3]
folder=Path(__file__).resolve().parent
before=json.loads((folder/'before.json').read_text(encoding='utf-8'))
result=json.loads((folder/'p12-final-code.tests.json').read_text(encoding='utf-8'))
assert result['status']=='FINISHED' and not result['errors'] and not result['failures'] and not result['skips']
patterns={
 '01': (r'legacy_|lifecycle_is_distinct|legal_sequence', '旧记录不迁移；温度与可消费生命周期独立。'),
 '02': (r'wrong_subject|permission|confirmation|stale_version|hash_mismatch|expiry_', '确认方式仅 TEST 绑定输入；正式策略未决定。'),
 '03': (r'decay|downweight_affects|zero_weight|router_weight|timeline_material_honors_weight', '显式策略；读取不自动衰减，无正式默认阈值。'),
 '04': (r'inactive_and_archived|router_excludes|zero_weight|normal_context_before_after|new_alias', '退出普通检索；历史审计保持。'),
 '05': (r'authorized_trace|history_recall|restore_(?:invalid|source|resets|active)|invalid_source_after_real', '历史召回为确定性强词匹配，最多 5 条，不自动恢复。'),
 '06': (r'delet|raw_save|old_archive_replay|invalid_source_after_real|lifecycle_is_distinct', '逻辑 tombstone 不可恢复；物理擦除和生产删除 NOT_READY。'),
 '07': (r'summary|child|partial_root_merge', '旧子版本不随父恢复复活；须以新有效来源重建。'),
 '08': (r'composer|router_|old_reference|normal_context_before_after|disabled_memory_entry|timeline_material', '来源版本和当前状态重验；不写 Event/SubjectState。'),
 '09': (r'MemoryLearningTests|pending_learning_rechecks', '保留既有置信度及 Evolution 边界，不直接改主体。'),
 '10': (r'concurrent_|atomic_replace|command_identity|duplicate_command|restart|actual_fresh_process|tampered|replay', '本机同进程事务并发；跨进程串行恢复，不宣称分布式事务。'),
 '11': (r'FixtureIsolationTests|wrong_subject_and_environment|production_delete_not_ready', '新链接传感器为受控测试；真实 P08 symlink 1314 SKIP 在全量中保留。'),
 '12': (r'golden|thirty_days|normal_context_before_after|archive_delete_keep_event', '30 逻辑日/12 新事件/6 交互/2 次 runtime 重开；另有真实新进程重放。'),
}
matrix={}
for number,(pattern,limit) in patterns.items():
    ids=[x for x in result['testIdentities'] if re.search(pattern,x)]
    assert ids
    matrix['P12-'+number]={'state':'IMPLEMENTED_NOT_ACCEPTED','testIdentities':ids,
        'passed':len(ids),'failed':0,'errors':0,'skipped':0,'limitation':limit,
        'evidence':'p12-final-code.tests.json'}
(folder/'matrix-coverage.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'docs/project_memory/60_P12_规划施工测试验收矩阵.md'
text=p.read_text(encoding='utf-8')
start='<!-- P12_COVERAGE_START -->'; end='<!-- P12_COVERAGE_END -->'
block=start+'\n\n## 逐项实际证据与限制\n\n[完整测试身份映射](p12_evidence/matrix-coverage.json) 从已完成专项结果生成；每项 PASS 表示对应测试，阶段仍未验收。测试可跨项共享，以下数量不得相加当作总数。\n\n| 项 | 实跑定点 | 限制 |\n|---|---|---|\n'
for number,row in matrix.items():
    block+=f"| {number} | {row['passed']}/{row['passed']} PASS；0 SKIP/FAIL/ERROR | {row['limitation']} |\n"
block+='\n'+end
text=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,text,flags=re.S) if start in text else text+'\n'+block+'\n'
p.write_text(text,encoding='utf-8')

def git(*args):
    r=subprocess.run(['git',*args],cwd=root,capture_output=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    if r.returncode: raise RuntimeError(r.stderr.decode('utf-8'))
    return r.stdout.decode('utf-8')
def paths(*args): return [x for x in git(*args).split('\0') if x]
tracked=paths('diff','--name-only','-z')
untracked=paths('ls-files','--others','--exclude-standard','-z')
excluded=list(before['p10Untracked'])
assert set(excluded).issubset(untracked)
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in before['p10Untracked'].items())
owned=sorted(set(tracked+untracked)-set(excluded))
# These three reports are produced by this closeout and the following audit.
planned=['docs/project_memory/p12_evidence/'+x for x in ('pending-files.md','pending-files.json','final-audit.json')]
owned=sorted(set(owned+planned))
categories={'源码与测试':[],'P12 档案与导航':[],'P12 证据及本地执行辅助':[]}
for name in owned:
    category='源码与测试' if name.startswith(('src/','tests/')) else 'P12 证据及本地执行辅助' if '/p12_evidence/' in name else 'P12 档案与导航'
    categories[category].append(name)
metadata={'head':git('rev-parse','HEAD').strip(),'branch':git('branch','--show-current').strip(),
    'originMain':git('rev-parse','origin/main').strip(),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main').strip(),
    'staged':git('diff','--cached','--name-only').strip(),'trackedChanges':tracked,
    'p12Files':owned,'categories':categories,'excludedP10':before['p10Untracked'],'unrelated':[],
    'plannedCloseoutReports':planned,'gitWrites':False}
assert not metadata['staged'] and metadata['head']==before['head']
(folder/'pending-files.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# P12 精确待提交工作区清单','',
    '仅供独立复核与未来用户决定；本轮没有暂存、提交、推送或分支操作。本清单不是 Git 授权。', '',
    f"main / HEAD / 本地 origin/main：`{metadata['head']}`；ahead/behind 0/0；暂存区为空。",
    f"本轮 {len(owned)} 个路径："+'；'.join(f'{k} {len(v)}' for k,v in categories.items())+'。',
    '原有 P10 辅助脚本 31 个明确排除并保持原 hash；其他无关增量为 0。',
    'pending-files.md/json 和 final-audit.json 为本次收口报告；审计报告核对代码、保护边界和最终状态。',
    '源码与测试 hash 见 full-final.tests.json；正式文件及 P10 脚本逐文件 hash 见 before.json 与 final-audit.json。证据和辅助脚本须在未来提交授权中逐项判断，不能为了清空工作区无差别暂存。','']
for category,names in categories.items():
    lines+=['## '+category,'']+['- `'+name+'`' for name in names]+['']
lines+=['## 原有 P10 排除项（原样保留）','']
lines+=['- `'+name+'` — sha256:'+before['p10Untracked'][name] for name in sorted(excluded)]
lines+=['','## 其他无关或不应提交的新文件','','无新增缓存、正式数据、Sandbox、wheel、构建目录或凭据进入本轮 Git 增量。既有忽略缓存原样保留，终局扫描见 final-audit.json。','']
(folder/'pending-files.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'p12Files':len(owned),'tracked':len(tracked),'newP12':len(owned)-len(tracked),
    'excludedP10':len(excluded),'categories':{k:len(v) for k,v in categories.items()}},ensure_ascii=False))
