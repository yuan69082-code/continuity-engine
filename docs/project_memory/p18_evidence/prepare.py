"""P18 kickoff snapshot and authorized Stage Brief; no Git mutations."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DOC=OUT.parent
KICKOFF=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p18-kickoff-20260910')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
from continuity_engine.testing.persistence import tree_inventory_hash

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT).decode('utf-8').strip()

SOURCE_ALLOWED=[
 'src/continuity_engine/domain/persistent_runtime.py',
 'src/continuity_engine/storage/json_runtime_repository.py',
 'src/continuity_engine/services/persistent_runtime_service.py',
 'src/continuity_engine/services/runtime_ports.py',
 'src/continuity_engine/services/runtime_cognition.py',
 'src/continuity_engine/runtime.py',
 'src/continuity_engine/testing/p18_runtime_fixture.py',
 'src/continuity_engine/services/wake_perception_thinking_action_service.py',
 'src/continuity_engine/services/thinking_service.py',
 'src/continuity_engine/services/resource_aware_wake_scheduler.py',
 'tests/test_p18_runtime.py','tests/test_p18_runtime_recovery.py','tests/test_p18_runtime_process.py']
TOP=['00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md','04_决策记录.md',
 '05_核心模块架构.md','05_已完成模块.md','06_未完成事项.md','07_待确认事项.md','08_未来扩展.md',
 '10_档案修订记录.md','11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md',
 '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md']
STAGE_FILES=['83_P18_PersistentRuntime架构与开工简报.md','84_P18_规划施工测试验收矩阵.md',
 '85_P18_持续运行控制资源等待与恢复语义.md','86_P18_测试索引与验收入口.md']

def main():
 assert not (OUT/'before.json').exists()
 b=read(DOC/'p17_acceptance_evidence/before.json');a=read(DOC/'p17_acceptance_evidence/final.audit.json')
 head=git('rev-parse','HEAD');assert head==git('rev-parse','origin/main')=='5a3247a5d23ff17de2b4ba12bc327594b492e725'
 assert git('branch','--show-current')=='main' and not git('diff','--name-only') and not git('diff','--cached','--name-only')
 current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*'))
          if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
 assert current==a['sourceTest']
 for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
  assert all(sha(ROOT/p)==h for p,h in b[key].items()),key
 assert tree_inventory_hash(ROOT/'.continuity-data')==b['formalTreeHash']
 full=read(DOC/'p17_repair_evidence/full-final-01.json')
 assert full['sourceBefore']==full['sourceAfter']==current and full['run']==1360 and full['passed']==1359 and len(full['skips'])==1
 untracked=list(filter(None,git('ls-files','--others','--exclude-standard','-z').split('\0')))
 assert set(untracked)==set(b['excluded'])|{Path(__file__).relative_to(ROOT).as_posix()}
 decisions=(DOC/'04_决策记录.md').read_text(encoding='utf-8')
 assert '\n## D-072' not in decisions and '\n## D-073' not in decisions
 copies={}
 for name in ('implementation-brief.md','baseline-verification.json','planning-extract.json'):
  data=(KICKOFF/name).read_bytes();(OUT/name).write_bytes(data)
  copies[name]={'source':str(KICKOFF/name),'sha256':sha(KICKOFF/name)}
 snapshot=dict(at=datetime.now(timezone.utc).isoformat(),stage='P18',head=head,originMain=git('rev-parse','origin/main'),
  aheadBehind=git('rev-list','--left-right','--count','HEAD...origin/main'),sourceTest=current,testIdentities=full['testIdentities'],
  baselineCitedNotRerun={k:full[k] for k in ('run','passed','skips','failures','errors','seconds','command')},
  excluded=b['excluded'],formalTreeHash=b['formalTreeHash'],pyproject=sha(ROOT/'pyproject.toml'),kickoffCopies=copies,
  sourceAllowed=SOURCE_ALLOWED,documentsAllowed=['README.md',*['docs/project_memory/'+p for p in TOP+STAGE_FILES]],
  historicalFiles={p:sha(ROOT/p) for p in git('ls-files','-z').split('\0') if p and (ROOT/p).is_file()},
  gitStatus=git('status','--short','--untracked-files=all'),gitWrites=False)
 for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):snapshot[key]=b[key]
 (OUT/'before.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/'auxiliary-errors.log').write_text('Kickoff read-only tool launch failed: helper_unknown_error: apply deny-read ACLs. No Engine command ran. The same bounded read was retried successfully; not a test failure.\n',encoding='utf-8')
 state='P00—P17 ACCEPTED；P18 / Engine side / P18-01—P18-12 IN_PROGRESS；P18 Vio dependency=NONE；P19—P23 NOT_STARTED。D-072 开工；D-073 未创建/未使用。PLANNING_CONFLICT=NONE，EVIDENCE_CONFLICT=NONE（开工未发现冲突，不构成验收）。'
 brief='''# P18 Stage Brief：默认持续运行的 Persistent Subject Runtime

| 字段 | 本阶段明确边界 |
|---|---|
| STAGE | P18 Engine 独立施工；启动后默认持续运行；产品没有总轮数/总时长自动退出限制。 |
| SOURCE OF TRUTH | 用户 2026-09-10 整合授权优先；完整简报、已核对的 2026-08-26 三份规划与当前真实代码，见下方原件副本。 |
| ORIGINAL REQUIREMENTS | v1.1 P18 220—227：Engine 托管生命周期、持续宿主、无消息 Wake/认知/整理/内部事务/主动联系、资源与恢复。 |
| V6.7 DETAILS | 同一 Subject 跨计算会话连续心智，P14 内生需要与原 C1/Thinking/Action/Evolution；P15 解释非事实权威。 |
| AMENDMENT OVERRIDES | Runtime Ownership 属 Engine；D1 Scheduler 只安排计算、不创建心理内容；Direct 与 Optional Planner 均保留。用户澄清持续存活不等于固定间隔强制调用模型，局部资源等待不等于整体停止。 |
| KEEP RULES | 唯一 SubjectState/Event/Memory/E5-A Authority；原回执及 UNKNOWN 先查询；P01 仅 TEST/Research；原思想与心理冲突不被基础设施筛查。 |
| DEPENDENCIES | P11 Scheduler、ResourceAwareWakeScheduler/ResourceManager、原生 WakePerceptionThinkingActionService、正常 C1、P12/P14/P15/P16/P17。 |
| NOT READY | 正式联系时段/频率/费用和生产控制策略待用户决定；生产 Adapter/凭据、P20/P21 恢复与 P22 接入未开放；不安装服务或自启。 |
| FILES ALLOWED | 下方精确实现清单、83—86、现行状态及必要工程档案、p18_evidence 下唯一标签证据/辅助验证。 |
| FILES FORBIDDEN | 六份 Schema/冻结契约/63 项保护、三份规划、正式七文件、pyproject/0.1.0、Assistant/Vio、32 排除项和所有旧证据。 |
| TESTS REQUIRED | 先定点反例与正常对照，再专项/兼容，最终源码稳定后一次全量；保留原 1360 身份和断言，SKIP 单列；实际进程由测试控制器明确停止并清理。 |
| PLANNING CONFLICT | NONE；若必须越过上述边界，保留证据并停止对应项，不能默默缩减。 |

## 用户澄清与实现职责

持续入口只有 Owner 明确 STOP、经合法 P15 落地的主体暂停/归档/删除，或不可继续的真实进程故障会终止/限制运行；空队列、单轮结束、沉默、断连、局部资源耗尽不自动停止进程。PAUSE 保留控制宿主；STOP 持久保留，重启不能复活。若整个认知暂不可用，如实表示 WAITING_RESOURCES，不能伪造“仍在思考”。

Runtime 新持久记录仅管 Owner 运行意图、运行者 fencing、调度水位及诊断，不存心理正文、模型结果或竞争请求账本。原 Scheduler Queue 仍管理任务，原 Wake/ThinkSession/Action/E5-A/Event 记录是实际结果依据。单进程运行权采用本机 OS 锁；控制事务和派发前门槛分开，同步控制从明确的线性化点生效。

原生 C1 执行入口按需要最小增加可选当前 Runtime 门禁和原 ActionPlanning/Execution 回流接线；新执行在资源准备之后复核，已有事实按原身份核实恢复。认知机会由原内部状态/时间差/待整理来源驱动，不制造用户消息，tick 不直接写心理内容。可信 UTC 与单调等待时间分开；回拨等候、跃进只给一次当前机会，不无界追赶漏掉的轮次。

正常入口独立于 UI/Vio，使用可中断的有界等待保持控制响应。CLI 的 start 默认持续；TEST 控制器独立设置观察期限并明确 STOP，不把测试限时写成产品规则。此次只运行隔离 Fake，测试结束不得遗留后台实例。

## 精确实现文件范围

'''+''.join('- `'+p+'`\n' for p in SOURCE_ALLOWED)+'''
## 原文与核对

[完整整合简报](p18_evidence/implementation-brief.md) · [规划原文摘录](p18_evidence/planning-extract.json) · [规划侧基线核验](p18_evidence/baseline-verification.json) · [本轮实测基线](p18_evidence/before.json)。

已验证开工全量是引用施工方 1360 项、1359 PASS/1 既有 1314 SKIP、1171.401 秒，未重跑；不是 1360 PASS。原始失败与八加三处历史格式告警全部保留，无远端 CI PASS 声明。
'''
 (DOC/STAGE_FILES[0]).write_text(brief+'\n'+state+'\n',encoding='utf-8')
 names=['运行身份与生命周期控制','默认持续入口与可中断等待','可信时间与时钟异常','内部需要驱动 Scheduler/Wake','无消息 C1/连续心智与记忆整理','统一资源及局部等待恢复','Owner/Subject 暂停停止与当前门槛','双进程互斥与故障恢复','原请求/回执 UNKNOWN 幂等续接','主体联系/沉默与投递政策','隔离、材料边界与静态诊断','真实跨进程 Golden 与完整兼容']
 (DOC/STAGE_FILES[1]).write_text('# P18 规划施工测试验收矩阵\n\n'+state+'\n\n本表是工程验收分解，不冒充原规划编号；结果只在实跑后填写。\n\n| 项目 | 语义 | 现行状态 | 证据 |\n|---|---|---|---|\n'+''.join(f'| P18-{i:02} | {name} | IN_PROGRESS | 待实现/实测 |\n' for i,name in enumerate(names,1)),encoding='utf-8')
 for name,title in zip(STAGE_FILES[2:],('持续运行、控制、资源等待与恢复语义','测试索引与验收入口')):
  (DOC/name).write_text('# P18 '+title+'\n\n'+state+'\n\n按 [Stage Brief]('+STAGE_FILES[0]+') 接续；本轮新结果尚未执行，不预填 PASS。\n',encoding='utf-8')
 (OUT/'continuation.md').write_text('# 当前有效任务：P18 实现\n\n'+state+'\n\n用户已授权默认持续运行，不退回 P17 收尾。已读整合简报并核验基线；下一步先固化缺失行为反例，再做最小宿主及原链接线。无 Git 写授权。正常入口不自动限时，测试控制器负责停止和清理。\n',encoding='utf-8')
 for p in [ROOT/'README.md',*[DOC/n for n in TOP]]:
  prefix='docs/project_memory/' if p.name=='README.md' else ''
  block='<!-- P18_CURRENT_START -->\n'+state+'\n\n用户确认启动后默认持续运行；空闲/沉默/单项资源等待不停止宿主，测试限时与产品寿命分开。见 [Stage Brief]('+prefix+STAGE_FILES[0]+')。下方旧阶段与授权记录为历史。\n<!-- P18_CURRENT_END -->\n\n'
  p.write_text(block+p.read_text(encoding='utf-8'),encoding='utf-8')
 with (DOC/'04_决策记录.md').open('a',encoding='utf-8') as f:
  f.write('\n## D-072：用户授权 P18 默认持续运行与 Engine 独立施工\n\n2026-09-10 用户转发更新整合简报并明确：启动后持续运行，正常入口不以无消息、空队列、单轮结束、沉默、外部断连或局部额度用完自行结束。局部等待与整体控制分离；STOP/P15 已落地意图不能因故障恢复自动推翻。测试控制器限时并明确停止进程，不是产品运行时限。\n\n'+state+'\n\n仅原链内宿主/控制/恢复接线和隔离 TEST，正式策略未定、生产能力 NOT_READY，不 Git 写、不 P19、不创建验收决定。见[完整 Stage Brief]('+STAGE_FILES[0]+')。\n')
 print(json.dumps({'baselineSource':len(current),'originalTestIdentities':len(full['testIdentities']),'protected':len(b['protected']),'excluded':len(b['excluded']),'stageBrief':str(DOC/STAGE_FILES[0]),'decision':'D-072'},ensure_ascii=False))

if __name__=='__main__':main()
