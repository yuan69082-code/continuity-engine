"""Write current P16 documentation only after real stable test results exist."""
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;DOC=OUT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def load(label):
    r=read(OUT/(label+'.json'))
    if r.get('exitCode')!=0 or r.get('status')!='FINISHED' or r['sourceBefore']!=r['sourceAfter']:raise ValueError(label+' not stable/pass')
    return r
def result(r):return f"{r['run']} 项：{r['passed']} PASS、{len(r['skips'])} SKIP、{len(r['failures'])} FAIL、{len(r['errors'])} ERROR，{r['seconds']:.3f} 秒，退出码 {r['exitCode']}"
def write(p,t):p.write_text(t.strip()+'\n',encoding='utf-8')
def main():
    if (OUT/'final-report.md').exists():raise ValueError('preserve existing final report')
    p16,compat,full=(load(x) for x in ('p16-final','compatibility-final','full-final'))
    current={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests')
        for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    if any(r['sourceAfter']!=current for r in (p16,compat,full)):raise ValueError('current source mismatch')
    baseline=read(OUT/'before.json');old=set(baseline['testIdentities']);ids=set(full['testIdentities'])
    if not old<=ids:raise ValueError('missing baseline tests')
    source_hash='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    rows=[]
    for path in OUT.glob('*.json'):
        r=read(path)
        if r.get('command') and r.get('status')=='FINISHED':rows.append((r['startedAt'],path.stem,r))
    history=['# P16全部实跑记录与首次失败','',
        '每行run/PASS按测试方法计；FAIL/ERROR列是unittest原始记录条数，子用例可使记录条数多于失败方法数。时间为持久runner墙钟时间（包含发现），各stderr另有unittest计时。全部原件保留，不以新PASS覆盖旧结果。','',
        '| 标签/元数据 | run | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | exit | 原始输出 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for _,label,r in sorted(rows):
        history.append(f"| [{label}]({label}.json) | {r['run']} | {r['passed']} | {len(r['failures'])} | {len(r['errors'])} | {len(r['skips'])} | {r['seconds']:.3f} | {r['exitCode']} | [stdout]({label}.stdout.log) / [stderr]({label}.stderr.log) |")
    history.extend(['','## 失败解释及处理','',
        '- provider-before：新P16 Fixture模块尚未实现，5个ModuleNotFoundError，保留实现前入口失败。',
        '- provider-first：新TEST Thinking漏填should_wait/suggest_future_user_contact；新撤权断言曾过宽，随后绑定实际异常原因。均为辅助错误，未修改旧测试。',
        '- provider-fixture-corrected：新Source使用小写权限scope，原Router明确拒绝；改为既有ENGINE_PRIVATE枚举值。',
        '- provider-context-scope：768默认输入预算明确排除新材料，原规则正确；TEST正向显式1024并新增768排除对照，未改生产默认。',
        '- recovery-context-first：新Trace被后续C1 trace覆盖、原事实恢复被当前消费权限拦住、新P01组件未登记；定点修复。历史回执拒绝通过原IntegrationExecutionError包装，新测试改查其精确cause，未弱化回执断言。',
        '- binding-before：替换Connector描述可复用旧材料身份；cache的cached_at格式未校验。增加描述hash/version/capability精确绑定和时间校验。binding-closed仍有一个错误码包装ERROR，随后统一为EXTERNAL_STORE_CORRUPT。',
        '- lifecycle-golden-first：新消费分支未区分主体非活跃与原事实恢复；已修复。Golden嵌套根过长触发Windows既有临时路径限制，使用独立浅层Temp根；保留完整子进程栈，不修改旧Awakening。',
        '- lifecycle-golden-second：E5-A事实已经恢复，旧C1结果因合法暂停推进revision而拒绝过时摘要。新测试原本要求成功发布旧结果过窄；按现有完成契约分别断言SUCCEEDED事实、精确拒绝原因、无重复调用和新状态不变，未改Core完成契约。',
        '- lifecycle-golden-third：新回归引用了不存在的action_planning属性，改为读取真实capabilities绑定；为辅助错误。三进程Golden该轮已实际通过。',
        '- credential-binding-before：TEST Broker仅检查引用存在，未检查Connector归属；补精确映射和缺失/过期/跨主体对照。',
        '- expanded-first：根去重测试初版把不同内容错误要求为一个赢家；保留不同内容共同根并新增相同事实包装的正式反例。路径测试抛出原SandboxOperationError而新测试期待错误类型，改查实际拒绝码并保持两入口零写入断言。',
        '- root-dedup-before：相同根/内容/版本通过两个包装仍重复，复现后在P16 Source确定性去重；不同内容/不同根仍保留。',
        '- integration-first：P01 Genesis本来含一条Learning候选，新测试错误期待空表；改为比较前后原记录完全一致，保留capture为空和SubjectState不变断言。',
        '- 读取辅助错误：几次猜测文件名、PowerShell rg路径通配及77文档标题patch未匹配，未修改任何运行数据；随后按真实文件名继续。这些不是Engine测试结果。',
        '- 历史P00—P15 FAIL/ERROR/SKIP、P09 segment 10 stderr缺失且根因UNKNOWN全部保留，未因P16通过改写。',
        '- Windows symlink WinError 1314为原有权限SKIP，仍为SKIP；没有新增跳过项。'])
    write(OUT/'test-history.md','\n'.join(history))
    new=len(ids-old)
    write(OUT/'final-report.md',f'''# P16实际交付与独立复核入口

P16 / Engine side / P16-01—P16-12 IMPLEMENTED_NOT_ACCEPTED，交回独立复核；P00—P15 ACCEPTED，P17—P23 NOT_STARTED，Vio dependency=NONE。D-068开工，D-069未创建/未使用。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅表示本地已知施工缺口闭合，不能代替独立复核或用户验收。

## 实际能力

Memory/Knowledge/MCP查询/Skill确定性处理四类宿主中立Port已通过本地Fake接入正常C1：Thinking的信息需求→当前获准Connector→原Direct/E5-A→独立回执和结构化结果核验→候选缓存→下一次正常Router/Composer/Thinking消费或明确拒绝。简单查询无Goal/Plan，原模型和Optional Planner路径保留。

版本化注册/禁用、CAS、原子持久化、凭据引用绑定、撤权、缓存时效、恶意结果与秘密拒绝、根去重、不确定性标记、原E5-A有界重试/UNKNOWN、历史事实恢复均有正常/反例。P01分支恢复及三个真实子进程Golden通过；继承P12记忆归档和P15当前学习/活跃门禁。外部候选不会自动创建学习经历或推进SubjectState。

## 实跑结果与引用

- P16最终专项：[p16-final](p16-final.json)：{result(p16)}。
- 受影响兼容：[compatibility-final](compatibility-final.json)：{result(compat)}。覆盖E5-A/P02、P05/P06、P08、P09恢复/正常链、P12、P15及P01。
- 最终一次完整回归：[full-final](full-final.json)：{result(full)}。
- 原{len(old)}个测试身份全部保留、旧测试文件字节不变；新增{new}项单列。全量包含专项及兼容，不重复相加。
- P15开工全量{result(baseline['citedFull']) if 'failures' in baseline['citedFull'] else '1208项：1207 PASS、1既有1314 SKIP，1024.585秒'}仅引用已核验历史，P16开工未重跑。上述三轮为本轮实跑，非独立监工运行。

每个json含实际命令、唯一标签、测试身份、开始/结束UTC、退出码、原始FAIL/ERROR/SKIP及执行前后源码清单；对应stdout/stderr不在自动清理的Fixture根。三个子进程输出在[p16-final stdout](p16-final.stdout.log)。[全部首次失败与处理](test-history.md)保留初版、辅助错误和中间结果。

## 身份、保护与范围

最终源码/测试/资源{len(current)}文件，清单指纹`{source_hash}`；专项、兼容、全量执行前后均与其完全一致。最终审计见[final.audit.json](final.audit.json)，精确清单见[final.pending-files.md](final.pending-files.md)，包括15个源码/测试新增或修改路径、必要工程档案及本轮证据。

63保护、六份Schema/外部契约、三份规划、正式7文件及树指纹、pyproject/0.1.0、31个P10脚本和旧P14接续报告逐文件对比。[基线](before.json)与终局审计保存hash。正式树预期及实测核对值为`{baseline['formalTreeHash']}`。

新增源码AST、文档本地链接、静态秘密模式及git diff --check由终局审计实际记录。扫描不是无限秘密安全保证。两处既有格式注记原样保留：P15失败日志第5行尾空格、subject_lifecycle_ports.py第18行EOF空行；不倒写原件。原缓存/历史排除项不清理。

## 限制与未就绪

真实Provider/外部记忆库/MCP/Skill产品、密钥、外网、生产认证和重连仍NOT_READY，供应商清单待用户决定；不接Assistant/Vio，不建设P17或后台运行时，不启用正式删除/归档/可见性政策。注册和缓存有本地有界容量，未提供分布式并发保证；纯TEST查询成本0，原非零费用恢复由兼容回归验证。

历史事实和新执行分离；如果合法主体暂停推进revision，E5-A事实仍可恢复，但旧C1完成结果按既有契约明确拒绝发布过时状态摘要。不会覆盖后来状态。Windows子进程Golden使用浅层独立Temp根，未扩建生产长路径能力。本地Fake原子回执幂等不代表任意生产Adapter exactly-once。

## Git与停止状态

Engine main/HEAD及本地origin/main保持`{baseline['head']}`，本轮没有暂存/提交/push/分支操作，未访问远端；暂存区应为空，完整实测状态在终局审计。Engine无已登记Actions workflow，本轮没有远端CI run或CI PASS。另保留31个P10脚本及1个P14报告，未混入P16清单。停止P16，等待用户转交独立复核；不自动发消息、不验收、不进入P17。
''')
    descriptions=[
        ('Memory Provider正常Context入口','external_provider_ports / external_capability_service / external_context_source','ProviderTests.test_memory_information_need_calls_fake_then_normal_context_consumes_candidate；test_revoke_before_query_has_no_external_call_or_subject_write'),
        ('Knowledge候选与经历/判断分层','external_capabilities / 原SubjectGrowthService','ProviderTests.test_all_four_local_provider_kinds_really_execute；ContextTests.test_p15_growth_does_not_promote_external_candidates_to_experience / test_external_event_identity_cannot_be_internal_root'),
        ('Connector注册/禁用/版本替换','JsonExternalProviderRepository / ExternalCapabilityService','ProviderTests.test_registry_concurrent_revision_allows_only_one_write / test_disable_replay_is_idempotent_and_cannot_reregister_same_version；ContextTests.test_replacement_preserves_old_fact_but_invalidates_old_material'),
        ('MCP/Skill有界本地查询','QueryInput / ProviderResult / LocalMCPQueryProvider / LocalSkillQueryProvider','ProviderTests.test_all_four_local_provider_kinds_really_execute；ContextTests.test_same_request_payload_hash_conflict_is_rejected / test_strict_result_shape_version_hash_environment_and_bounds'),
        ('Credential引用绑定与秘密隔离','CredentialBroker / FakeBroker / 当前门禁','ProviderTests.test_credential_reference_cannot_be_reused_by_other_connector / test_missing_expired_and_cross_subject_credentials_refuse_before_call；ContextTests.test_secret_in_result_and_material_denial_never_reach_cache_or_state'),
        ('结果来源/hash/时间/根与恶意拒绝','ExternalCandidate / ProviderResult / 精确Resolver','ContextTests.test_malicious_mutation_field_rejected_before_cache / test_cross_subject_result_rejected_even_from_local_provider / test_strict_result_shape_version_hash_environment_and_bounds；正常四类查询对照'),
        ('调用/消费/恢复当前权限与生命周期','ExternalCapabilityService.require_current / 原P15','ContextTests.test_revoke_during_result_read_blocks_consumption_and_cache_write；RecoveryTests.test_paused_subject_blocks_new_query_and_current_cache_but_recovers_fact / test_archived_and_deleted_subjects_do_not_consume_or_execute'),
        ('Router/Composer预算/根去重/旧记忆语义','ExternalContextSource / 原Router/Composer/P12/P15','ContextTests.test_router_source_limit_is_separate_from_composer_budget / test_same_root_candidates_deduplicate_without_promoting_authority / test_distinct_roots_survive_and_same_root_conflict_never_selects_authority / test_p12_archived_internal_memory_stays_absent_with_external_queries_enabled'),
        ('离线/超时/取消/空结果/有界重试','ProviderResult状态 / 原ActionPlanningService可选上限','ContextTests.test_offline_timeout_cancel_and_empty_are_explicit_results；RecoveryTests.test_explicit_retry_uses_original_attempts_and_stops_at_bound / test_query_exception_never_authorizes_dispatch_or_exposes_secret'),
        ('可重建缓存当前绑定及失效','JsonExternalProviderRepository / ExternalCapabilityService.cached','ContextTests.test_exact_ttl_boundary_is_excluded_just_before_is_valid / test_cache_rehashed_payload_tamper_still_checks_original_fact / test_replacement_descriptor_cannot_reuse_old_exact_reference / test_invalid_cache_timestamp_is_corruption_not_freshness'),
        ('唯一E5-A恢复/回执/UNKNOWN分离','原CapabilityCoordination / P08 Adapter桥','RecoveryTests.test_completed_replay_rechecks_receipt_without_reexecution / test_lost_response_after_receipt_can_close_after_revocation_without_consuming / test_historical_success_unknown_query_cannot_replay_completed / test_unknown_does_not_execute_even_with_explicit_retry / test_string_not_executed_is_unknown'),
        ('正常C1/跨进程/P01/Feature Gate及旧格式','continuity_core_runtime / P16Fixture / 原P01组件','RecoveryTests.test_three_real_process_golden_recovers_replaces_and_revokes / test_p01_branch_replays_original_receipt_without_polluting_parent；ProviderTests.test_disabled_c1_gate_does_not_touch_installed_external_ports / test_upper_mixed_protected_roots_and_children_are_zero_write；原1208身份兼容')]
    matrix=['# P16施工测试验收矩阵','','本表是对原规划的施工分解，不冒充原件编号。十二项均 IMPLEMENTED_NOT_ACCEPTED，等待独立复核和用户验收；未就绪生产能力见[恢复语义](77_P16_外部候选凭据缓存与恢复语义.md)。',
        '',f'本轮专项{result(p16)}；受影响兼容{result(compat)}；稳定全量{result(full)}。完整方法身份、命令及原始输出见[测试入口](78_P16_测试索引与验收入口.md)。不重复相加。','',
        '| 项 | 范围 / 实现位置 | 状态 | 正常/反例与真实证据 |','|---|---|---|---|']
    for i,(name,impl,tests) in enumerate(descriptions,1):matrix.append(f'| P16-{i:02} | {name}：{impl} | IMPLEMENTED_NOT_ACCEPTED | {tests}；[本轮53项原始结果](p16_evidence/p16-final.json) |')
    matrix+=['','实现精确路径见[完整源码增量](p16_evidence/final.audit.json)；测试在[test_p16_providers.py](../../tests/test_p16_providers.py)、[test_p16_context.py](../../tests/test_p16_context.py)、[test_p16_recovery.py](../../tests/test_p16_recovery.py)。[首次失败与辅助错误](p16_evidence/test-history.md)全部保留。']
    write(DOC/'76_P16_规划施工测试验收矩阵.md','\n'.join(matrix))
    write(DOC/'78_P16_测试索引与验收入口.md',f'''# P16测试索引与独立复核入口

P16 IMPLEMENTED_NOT_ACCEPTED。实际成果、限制、测试来源及Git边界见[交付报告](p16_evidence/final-report.md)，十二项见[矩阵](76_P16_规划施工测试验收矩阵.md)，全部历史见[测试记录](p16_evidence/test-history.md)。D-068开工；不创建D-069，不自行验收或Git写操作。

最终P16：{result(p16)}。兼容：{result(compat)}。最终全量：{result(full)}。原1208身份未删，新增{new}身份单列；原WinError 1314 SKIP不计PASS。执行前后{len(current)}源码/测试/资源hash一致。P15基线仅核验引用，未冒称本轮重跑。

## 可直接运行

在Engine根目录执行。先使用未占用的日志标签；runner拒绝覆盖旧证据。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python docs/project_memory/p16_evidence/run.py review-p16 test_p16_
python docs/project_memory/p16_evidence/run.py review-full
python -m continuity_engine.testing.p16_provider_fixture --golden
python docs/project_memory/p16_evidence/audit.py review-audit
```

首两条保存stdout/stderr、时间、退出码、方法身份和源码清单，标签须唯一。Golden自动使用独立浅层Temp，依次启动prepare/resume/replace-revoke三个新Python进程，记录原子回执后中断、原请求恢复零新调用、Thinking消费、Connector替换及撤权。完整兼容命令保存在[compatibility-final.json](p16_evidence/compatibility-final.json)，不需要凭摘要重组。

源码不变时不机械重跑多轮全量。若有新失败，保留唯一标签输出；不得删除旧日志、变更原断言或将SKIP当PASS。审计脚本仅记录工作区，不暂存/提交。正式数据、31个P10脚本和1个P14报告不作为测试根。

[最终审计](p16_evidence/final.audit.json) · [完整待提交与排除清单](p16_evidence/final.pending-files.md) · [恢复/候选责任](77_P16_外部候选凭据缓存与恢复语义.md) · [Stage Brief](75_P16_外部记忆知识与可插拔能力架构边界.md)
''')
    for p in [ROOT/'README.md',*DOC.glob('*.md')]:
        t=p.read_text(encoding='utf-8-sig')
        if '<!-- P16_CURRENT_START -->' not in t:continue
        prefix='docs/project_memory/' if p.name=='README.md' else ''
        block=f'''<!-- P16_CURRENT_START -->
> P16 / Engine side / P16-01—P16-12 IMPLEMENTED_NOT_ACCEPTED（D-068），等待独立复核。P00—P15 ACCEPTED；P16 Vio dependency=NONE；P17—P23 NOT_STARTED。PLANNING_CONFLICT=NONE、EVIDENCE_CONFLICT=NONE仅为本地已知缺口闭合，不等于用户验收。D-069未创建/未使用，不Git写操作，不进入P17。
>
> 本轮专项{result(p16)}；兼容{result(compat)}；最终全量{result(full)}。原1208身份保留、新增{new}项，SKIP不计PASS；旧全量仅作为历史引用。[实际交付与限制]({prefix}p16_evidence/final-report.md) · [十二项矩阵]({prefix}76_P16_规划施工测试验收矩阵.md) · [精确清单及保护审计]({prefix}p16_evidence/final.audit.json)。真实服务/凭据/生产策略NOT_READY；下方旧阶段状态和授权为历史，全部FAIL/ERROR/SKIP及P09 segment 10 UNKNOWN保留。
<!-- P16_CURRENT_END -->'''
        write(p,re.sub(r'<!-- P16_CURRENT_START -->.*?<!-- P16_CURRENT_END -->',lambda _:block,t,count=1,flags=re.S))
    stage=DOC/'75_P16_外部记忆知识与可插拔能力架构边界.md';t=stage.read_text(encoding='utf-8')
    t=t.replace('P16/Engine side/P16-01—12 IN_PROGRESS','P16/Engine side/P16-01—12 IMPLEMENTED_NOT_ACCEPTED')
    t=t.replace('## 接续进度','## 施工中间接续记录（历史）')
    write(stage,t+f'\n\n## 当前终局接续\n\nP16实现、专项、兼容与最终一次全量完成。专项{result(p16)}；兼容{result(compat)}；全量{result(full)}。当前仅完成档案与只读终局审计后交付，不再修改源码或重复全量。后续用户指令前不验收、不Git写操作、不进入P17。[交付报告](p16_evidence/final-report.md)。\n')
    semantic=DOC/'77_P16_外部候选凭据缓存与恢复语义.md';write(semantic,semantic.read_text(encoding='utf-8').replace('IN_PROGRESS。','IMPLEMENTED_NOT_ACCEPTED，等待独立复核。',1))
    decision=DOC/'04_决策记录.md'
    with decision.open('a',encoding='utf-8') as f:f.write(f'\n\nD-068施工结果追加（非验收决定）：P16本轮实现及测试完成，最高IMPLEMENTED_NOT_ACCEPTED。专项{result(p16)}；兼容{result(compat)}；全量{result(full)}。证据见[78](78_P16_测试索引与验收入口.md)；完整首次失败保留，D-069未创建，未执行Git写操作，交回独立复核。\n')
    print('P16 current docs synchronized; no code/test/Git changes; final audit still required')
if __name__=='__main__':main()
