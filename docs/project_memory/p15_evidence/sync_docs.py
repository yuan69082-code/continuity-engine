"""Finalize P15 documentation from completed evidence, without changing source or Git."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
MEM=ROOT/'docs/project_memory'
OUT=Path(__file__).resolve().parent


def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf-8-sig'))


def write(path,text):path.write_text(text,encoding='utf-8')


def main():
    labels={name:name+'-2' for name in ('p15-final','compatibility-final','full-final')}
    runs={name:read(label) for name,label in labels.items()}
    for name,run in runs.items():
        if run.get('status')!='FINISHED' or run.get('exitCode')!=0:raise ValueError('not verified: '+name)
        if run['sourceBefore']!=run['sourceAfter']:raise ValueError('source changed during '+name)
    if len({json.dumps(x['sourceAfter'],sort_keys=True) for x in runs.values()})!=1:
        raise ValueError('final evidence differs')
    golden=read('golden-cli')
    if golden.get('exitCode')!=0 or golden.get('status')!='FINISHED':raise ValueError('golden CLI not verified')
    if golden['sourceBefore']!=golden['sourceAfter'] or golden['sourceAfter']!=runs['full-final']['sourceAfter']:
        raise ValueError('golden source changed')
    golden_value=json.loads((OUT/'golden-cli.stdout.log').read_text(encoding='utf-8-sig'))
    brief=MEM/'71_P15_人格关系学习与主体生命周期架构边界.md'
    text=brief.read_text(encoding='utf-8-sig')
    text=text.replace('P15 / Engine side / P15-01—12 IN_PROGRESS；',
        'P15 / Engine side / P15-01—12 IMPLEMENTED_NOT_ACCEPTED；')
    text=text.replace('状态仍IN_PROGRESS。','当时状态IN_PROGRESS。')
    if '## 本轮施工终局' not in text:
        text+='\n## 本轮施工终局\n\nP15实现与测试已完成，等待独立复核；不等于用户验收。保留上面的开工依据和初期失败进度。具体十二项及真实结果见[矩阵](72_P15_规划施工测试验收矩阵.md)、[测试入口](74_P15_测试索引与验收入口.md)和[交付报告](p15_evidence/final-report.md)。\n'
    write(brief,text)
    semantic=MEM/'73_P15_成长纠错与生命周期恢复语义.md'
    text=semantic.read_text(encoding='utf-8-sig').replace('IN_PROGRESS。原SubjectState',
        'IMPLEMENTED_NOT_ACCEPTED；等待独立复核。原SubjectState',1)
    write(semantic,text)
    # These are P15 decomposition rows, not verbatim numbering from the planning source.
    rows=[
        ('Trait与人格证据','SubjectGrowthService.capture/submit、LearningService、原Evolution',
         'growth.test_three_current_independent_experiences_form_trait_and_next_context',
         '三次实际C1经历形成Trait；下一轮授权Context触发Fake的Information Need。不是任意模型文本直写人格。'),
        ('根去重与当前来源','subject_growth_service.verify_source、原Learning当前支持重查',
         'growth.test_duplicate_root_wrappers_do_not_validate；test_current_source_binding_cannot_be_replaced_with_forged_roots；test_current_reference_revocation_prevents_solidify_without_writes',
         '精确reference/hash、当前权限、Timeline/P12及独立根重验；不把Wrapper或Summary加算为根。'),
        ('学习验证纠错及恢复','原LearningRecord pending_state_event/growth_operation、JsonLearningRepository事务',
         'growth.test_pending_learning_record_recovers_after_restart_without_second_revision；test_rollback_preserves_later_unrelated_trait；test_rollback_pending_record_recovers_and_does_not_remove_twice；test_completed_growth_recovers_after_authority_revoked',
         '实际提交前重查；已提交原Event核实后恢复；只移除自己Trait贡献，不回滚后来无关状态。'),
        ('关系长期演化与可见性','SubjectState.relationship.objects、MindProjectionService.read_growth',
         'growth.test_normal_chain_forms_subjective_narrative_and_object_relationship；test_growth_permission_policy_is_required_and_owner_read_is_read_only；test_reinterpreted_experience_preserves_opposite_stances_and_versions',
         '对象/根/版本追踪，LOVE/HATE可共存；未配置关系范围NOT_READY，Owner只读。'),
        ('连续自我叙事','SubjectState.identity.self_narrative、C1内部processor、P14有界Context投影',
         'growth.test_normal_chain_forms_subjective_narrative_and_object_relationship；test_reinterpreted_experience_preserves_opposite_stances_and_versions',
         '经历理解可重新解释，主观Authority明确，原Event和Evolution历史不改写。'),
        ('长期Will与心理冲突','复用DynamicMind、原desire identity、trajectory和Conflict',
         'growth.test_reinterpreted_experience_preserves_opposite_stances_and_versions；recovery.test_cross_process_golden；全体P14兼容',
         '保留相反立场与长期Will，跨进程不重建身份；不以priority代替Will。'),
        ('生命周期状态及持久化','SubjectLifecycle/SubjectLifecycleService、SubjectStateService、JsonRepository',
         'lifecycle.test_legacy_state_is_active_without_rewriting_serialization；test_create_suspend_restart_resume_and_replay；recovery.test_atomic_creation_failure_does_not_leave_active_subject；test_concurrent_lifecycle_commands_preserve_one_transition',
         'CREATE/ACTIVE/SUSPENDED/ARCHIVED/DELETED；原仓储原子创建/版本保护，旧格式保持字节结构。'),
        ('Owner命令与Subject意图','LifecycleAuthority Port、原Action Gate/Evolution',
         'lifecycle.test_subject_intent_preserves_state_and_owner_identity；test_revoked_confirmation_and_stale_command_zero_writes；test_action_gate_denial_is_zero_write；recovery.test_cross_subject_environment_and_direct_lifecycle_mutation_rejected',
         '主体意图只形成非状态Event，不等于Owner命令；当前确认/主体/环境/revision检查，拒绝零写入。'),
        ('暂停归档恢复及Binding','C1/Thinking/Awakening/ResourceAwareWakeScheduler/ModelCapability前置门禁；内部Selection Port',
         'lifecycle.test_c1_new_request_paused_zero_journal_provider_or_receipt；test_scheduler_paused_zero_attempt_resource_notification_then_resume；recovery.test_paused_pending_not_executed_model_cannot_dispatch；test_host_binding_switch_and_unbind_do_not_change_subject_revision',
         '暂停后不新增模型/调度/资源效果；历史事实查询保留。TEST切换/解绑不改主体，冻结SubjectBinding未变。'),
        ('新主体隔离及授权迁移','原Genesis/P01、SubjectLifecycleService.import_test_observation',
         'recovery.test_new_genesis_isolated_from_old_learning_mind_relationships；test_public_test_migration_requires_exact_confirmation_and_never_copies_personality',
         '仅TEST双端确认、原事件hash/类型匹配的PUBLIC_OBSERVATION；不复制旧人格、关系、私人记忆或主体权威。'),
        ('删除语义与待决定策略','LifecyclePolicy、原SubjectState终态',
         'lifecycle.test_policy_is_unconfigured_until_explicit_test_decision；test_archive_unconfigured_and_deleted_terminal；recovery.test_protected_fixture_root_rejects_before_any_write',
         'TEST逻辑DELETED禁止重新激活；历史/文件保留。正式归档、保留窗口、物理清除NOT_READY。'),
        ('正常C1与跨进程Golden','P15GrowthFixture、正常C1/P14、原P01 Snapshot/Branch',
         'recovery.test_cross_process_golden；test_p01_snapshot_branch_keeps_growth_and_does_not_pollute_original；growth.test_growth_feature_disabled_has_no_learning_read_or_write',
         '三次经历、两次真实子进程重启及native computation，重复零revision差；Feature Gate关闭不读写Learning。')]
    matrix='# P15 施工/测试/验收矩阵\n\n本表分解规划要求，不冒充规划原文编号。十二项均 IMPLEMENTED_NOT_ACCEPTED；P15 Engine side同值，Vio dependency=NONE，等待独立复核和用户验收。\n\n'
    matrix+='测试简称 growth/lifecycle/recovery 指 `tests/test_p15_subject_*.py`，方法名可在对应文件定位；同一测试覆盖多个要求，行数不等于互斥测试数量。最终专项39 PASS、0 SKIP/FAIL/ERROR；兼容与完整结果见[测试入口](74_P15_测试索引与验收入口.md)。\n\n'
    matrix+='| 项 | 范围 | 状态 | 实现责任 | 实测入口 | 结果及边界 |\n|---|---|---|---|---|---|\n'
    for i,(title,implementation,test,limit) in enumerate(rows,1):
        matrix+=f'| P15-{i:02} | {title} | IMPLEMENTED_NOT_ACCEPTED | {implementation} | `{test}` | 本轮PASS。{limit} |\n'
    write(MEM/'72_P15_规划施工测试验收矩阵.md',matrix)
    def result(run):
        return f"{run['run']} 项：{run['passed']} PASS、{len(run['skips'])} SKIP、{len(run['failures'])} FAIL、{len(run['errors'])} ERROR；runner {run['seconds']:.3f} 秒"
    results='\n'.join(f"- [{labels[name]}]({labels[name]}.json)：{result(run)}。" for name,run in runs.items())
    history=[]
    for p in OUT.glob('*.json'):
        data=json.loads(p.read_text(encoding='utf-8-sig'))
        if 'sourceBefore' in data and 'run' in data:
            history.append((data['startedAt'],p.stem,data))
    history.sort()
    table='| 证据标签 | PASS | SKIP | FAIL记录 | ERROR记录 | runner秒 |\n|---|---:|---:|---:|---:|---:|\n'
    for _,label,r in history:
        table+=f"| [{label}]({label}.json) | {r['passed']} | {len(r.get('skips',[]))} | {len(r.get('failures',[]))} | {len(r.get('errors',[]))} | {r['seconds']:.3f} |\n"
    explanations='''早期 lifecycle-model/service、growth、visibility 和 recovery 的缺失模块/Fixture/入口 ERROR 是新增行为的修复前实际执行记录，不冒充已验收代码回归。已实现后保留原输出。其他有意义的失败及辅助错误如下：

- `lifecycle-entry-before` 的C1请求建立在暂停前、revision已旧；修正新测试的当前请求后，`lifecycle-entry-corrected-before`仍实际暴露C1先写journal及Scheduler实际投递两项缺口。门禁补齐后通过。
- `lifecycle-entry-after` 一项ERROR为新测试过深Temp路径触发Windows MAX_PATH；只缩短新增Fixture测试根，`lifecycle-entry-short-root`通过，未改生产路径规则。
- `growth-first` 暴露Engine内部强类型成长提案未被ThinkSession接受；只增加准确两字段内部序列化，Provider入口继续拒绝。`growth-typed-proposal`随后一项ERROR来自新测试要求旧表达在revision变化后直接重放，违反P13/P14现有契约；改为断言拒绝表达、原事实可查且零额外revision，没有放宽旧门禁。
- `recovery-first` 一项为新并发用例捕获异常类型错误，改为准确捕获StateEvolutionError；其他三项为缺少新Fixture入口。实现后8项通过，未吞并发写入缺陷。
- `paused-model-before` ERROR和`paused-model-count-before` FAIL记录实际Fake Provider事实数0→1。补齐原ModelCapability首次和NOT_EXECUTED后执行前生命周期/C1门禁，`paused-model-after`事实数0→0、LifecycleError；UNKNOWN/已提交事实查询未改成重执行。
- `p15-combination-first` 38 PASS/1 ERROR：多经历关系用例在默认Context预算下未包含材料；新增用例显式使用3000预算（沿用P14多来源场景方式），不改变Engine默认值或断言。`growth-reinterpret-budget`与当前P15全专项通过。
- 首次完整回归`full-final`发现原P09错主体Context的兼容ERROR；新增生命周期读取发生在原身份比对之前。保留首次全量、定点修复前后及准确结果，详见[局部检查顺序修复](continuity-current-repair.md)。只恢复原主体/环境先比对的顺序，再检查生命周期；不修改任何原测试。第二套后缀`-2`证据才对应最终源码，旧39/299项PASS及首次全量保留为中间版本。
- PowerShell中对rg传未展开的通配路径曾返回os error 123；改为`rg -g`后读取。属于辅助命令错误，不计Engine测试FAIL/PASS。早前任务接续误回P14是上下文接续问题，其只读报告单列保留，不是用户撤回P15授权。

各记录的原`.stdout.log`/`.stderr.log`与JSON同名保存，独立于Fixture临时根，后续PASS未覆盖首次失败。历史P09 segment 10 stderr缺失、根因UNKNOWN及P00—P14的FAIL/ERROR/SKIP仍保留。Windows symlink权限1314仍单列SKIP，不算PASS。
'''
    commands='''```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p15_evidence/run.py independent-p15 test_p15_
python docs/project_memory/p15_evidence/run.py independent-compat test_learning test_resources test_awakening test_thinking test_action test_evolution test_pre_p12 test_p02 test_p11 test_p14 test_p09_continuity_core test_p09_review_regressions test_p09_evolution_review test_p09_boundaries
python docs/project_memory/p15_evidence/run.py independent-full
python -m continuity_engine.testing.p15_subject_fixture
python docs/project_memory/p15_evidence/audit.py independent
```

在仓库根顺序执行。标签必须未使用，runner拒绝覆盖已有证据；不并发全量。Golden默认独立Temp根，命令/子进程/PID/逻辑时长/不变量输出为JSON。audit仅核查已有本轮证据并生成独立审计清单，不运行或伪报测试，也不做Git写操作。源码若改变，旧结果仅为历史，应按影响重新验证。
'''
    report='# P15 Engine 本轮交付报告\n\nP15 / Engine side / P15-01—12 IMPLEMENTED_NOT_ACCEPTED，等待独立复核；P00—P14 ACCEPTED；P16—P23 NOT_STARTED；Vio dependency=NONE。D-066仅开工决定，未登记用户验收。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE表示当前已知施工缺口闭合，不代替独立复核。\n\n'
    report+='## 实际完成\n\n'
    report+='正常C1消费当前证据并复用Learning形成候选，当前支持验证后经显式确认、Action Gate和Evolution固化Trait；下一轮真实Context可消费。对象关系和自我叙事是带来源/版本的主观状态，支持相反立场与重新理解；长期Will/冲突继续使用P14。新增生命周期管理复用原SubjectState/Event，CREATE原子持久化，暂停/归档阻止新计算，恢复核实已发生事实；主体意图、Owner命令、宿主切换/解绑分开。\n\n'
    report+='没有新增状态、人格、请求或执行账本；旧SubjectState、Learning和ThinkSession字段兼容保留。仅两项强类型内部成长提案接入Thinking，Provider仍不能直接写入。详见[Stage Brief](../71_P15_人格关系学习与主体生命周期架构边界.md)、[十二项矩阵](../72_P15_规划施工测试验收矩阵.md)、[恢复语义](../73_P15_成长纠错与生命周期恢复语义.md)。\n\n'
    report+='[30个源码/测试变更文件的方法导航](source-responsibility-map.json)可按文件定位新增/修改入口；这是AST导航，不能替代完整Git diff、来源hash或验收授权。27个运行/内部测试设施文件与3个新增P15测试文件均列明，原测试文件没有修改。\n\n'
    report+='## 当前实跑与历史引用\n\n'+results+'\n\n各集合存在包含关系，不相加为互斥覆盖。原1137测试身份完整保留、原测试文件未改；增加39项P15测试。开工1137项（1136 PASS/1 SKIP，898.290秒）仅核验引用P14已验收结果，不是本轮修改前新跑。所有本轮JSON附源码前后hash、完整测试ID、命令、时间、输出和失败信息；最终审计核对当前内容一致。没有远端CI执行或CI PASS声明。\n\n'
    report+='## 首次失败及修复过程\n\n'+explanations+'\n'+table+'\n'
    report+='## 当前可运行Golden入口\n\n'
    report+=f"[CLI实跑](golden-cli.json)，退出码0，{golden['seconds']:.3f}秒；[完整JSON输出](golden-cli.stdout.log)、[stderr](golden-cli.stderr.log)。逻辑时长{golden_value['logical_seconds']}秒、{golden_value['event_rounds']}次经历、{golden_value['native_opportunities']}次正常计算机会、{golden_value['restarts']}次真实子进程重启，PID为{golden_value['process_ids']}；Trait和Will身份保留，重复revision差{golden_value['duplicate_revision_delta']}，真实生产Adapter调用{golden_value['production_adapter_calls']}。子进程输出保留版本、Provider调用和心智数量等观察，不以三轮全量替代长期连续性场景。该有界TEST场景不外推任意生产长期运行可靠性。\n\n"
    report+='## 独立复核命令\n\n'+commands+'\n'
    report+='## 保护、Git与剩余边界\n\n'
    report+='[最终只读审计](final.audit.json)保存全部源码/测试hash、63项保护清单、三份规划原件、正式七文件及树指纹、31个P10辅助脚本、原测试身份、AST/链接/敏感扫描、diff检查和完整Git状态。正式树预期`sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，版本0.1.0；具体实测结果以审计为准，不用预期替代检查。\n\n'
    report+='[精确待提交清单](final.pending-files.md)逐项列出本轮源码/测试/档案及必要证据；原31个P10本地工具和P14任务接续只读报告单独排除保留，不为清空工作区而加入本轮。HEAD/main及本地origin/main仍`f1185d20da06f52e7e85015bc6b963cf9769d08c`，暂存区空；本轮没有暂存、提交、push、分支或其他Git写操作，未修改Assistant。\n\n'
    report+='正式归档/删除保留与恢复窗口、关系可见性策略尚待用户决定；仅独立TEST确认与策略有实现，逻辑DELETED不是物理擦除。生产认证、备份清除、生产迁移/Provider/Adapter和任意外部exactly-once未实现或宣称。并发/幂等证明限已测本机持久化与Fake能力；P01仅TEST/Research。停止P15，等待独立复核，不自行验收或进入P16。\n'
    write(OUT/'final-report.md',report)
    entry='# P15 测试与独立复核入口\n\nP15 IMPLEMENTED_NOT_ACCEPTED；D-066开工，未验收、未提交。\n\n'
    entry+='[交付报告与完整失败历史](p15_evidence/final-report.md) · [Stage Brief](71_P15_人格关系学习与主体生命周期架构边界.md) · [十二项矩阵](72_P15_规划施工测试验收矩阵.md) · [恢复语义](73_P15_成长纠错与生命周期恢复语义.md) · [最终审计](p15_evidence/final.audit.json) · [精确清单](p15_evidence/final.pending-files.md)。\n\n'
    for name,run in runs.items():
        label=labels[name]
        entry+=f'- [{label}](p15_evidence/{label}.json)：{result(run)}；[stdout](p15_evidence/{label}.stdout.log)、[stderr](p15_evidence/{label}.stderr.log)。\n'
    entry+='\n集合存在包含关系；1个既有Windows symlink权限1314 SKIP不算PASS。原1137身份保留；开工P14基线仅引用，未重新运行。当前完整结果均为本轮实跑，未声称独立复核或远端CI通过。\n\n'+commands
    write(MEM/'74_P15_测试索引与验收入口.md',entry)
    for name in ('README.md','00_项目总览.md','01_当前状态.md','02_工程路线图.md','03_施工日志.md',
        '04_决策记录.md','05_已完成模块.md','05_核心模块架构.md','06_未完成事项.md','07_待确认事项.md',
        '10_档案修订记录.md','11_P00_全周期能力与阶段基线.md','12_P00_规划施工测试验收矩阵.md',
        '13_P00_档案与测试索引.md','CHANGELOG.md','工程总档案.md'):
        path=ROOT/name if name=='README.md' else MEM/name
        prefix='docs/project_memory/' if name=='README.md' else ''
        block='<!-- P15_CURRENT_START -->\n> 2026-09-08 P15本轮施工与测试完成（D-066）：P00—P14 ACCEPTED；P15 / Engine side / P15-01—12 IMPLEMENTED_NOT_ACCEPTED，Vio dependency=NONE；P16—P23 NOT_STARTED。等待独立复核，未自行验收。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅指本地已知施工缺口闭合。\n>\n'
        block+=f"> 当前专项：{result(runs['p15-final'])}；直接兼容：{result(runs['compatibility-final'])}；最终稳定全量：{result(runs['full-final'])}。1个既有SKIP为Windows symlink权限1314，不计PASS；原1137项开工结果仅引用，未重新执行。\n>\n"
        block+=f'> [实际成果、首次失败与限制]({prefix}p15_evidence/final-report.md) · [十二项矩阵]({prefix}72_P15_规划施工测试验收矩阵.md) · [独立复核入口]({prefix}74_P15_测试索引与验收入口.md)。HEAD仍f1185d20da06f52e7e85015bc6b963cf9769d08c，本轮成果尚未提交，未执行Git写操作或修改Assistant。正式归档/删除/关系可见性策略NOT_READY。下方历次未开工/失败/验收为历史，P14已验收并push，不重做；全部FAIL/ERROR/SKIP及P09 segment 10 UNKNOWN保留。\n<!-- P15_CURRENT_END -->'
        text=path.read_text(encoding='utf-8-sig')
        if '<!-- P15_CURRENT_START -->' in text:
            text=re.sub(r'<!-- P15_CURRENT_START -->.*?<!-- P15_CURRENT_END -->',lambda _:block,text,count=1,flags=re.S)
        else:text=block+'\n\n'+text
        write(path,text)
    decisions=MEM/'04_决策记录.md'
    text=decisions.read_text(encoding='utf-8-sig')
    if '### D-066 追加：本轮施工与复核交付' not in text:
        text+='\n### D-066 追加：本轮施工与复核交付\n\n用户再次明确P15授权有效，接续已存在源码/测试和71—74，不重做P14。任务接续误停报告不是撤权。P15最终实现及新增专项、相关兼容、完整回归真实结果见[交付报告](p15_evidence/final-report.md)。范围内暂停模型恢复缺口和首次全量发现的Context身份检查顺序兼容错误已保留前后证据；测试辅助错误与全部历史不改写。当前IMPLEMENTED_NOT_ACCEPTED，等待独立复核；未登记D-067，不执行Git写操作、不进入P16。正式策略仍NOT_READY。\n'
        write(decisions,text)
    print('P15 documents synchronized from actual finished runs; source/tests/Git not modified')


if __name__=='__main__':main()
