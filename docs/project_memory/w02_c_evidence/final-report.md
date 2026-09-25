# W02-C / N11 外部资料可信吸收：施工交付与独立复核入口

**状态：IMPLEMENTED_NOT_ACCEPTED。** D-079 是用户授权本子批开工的边界记录，不是验收。W02-A/B 已 ACCEPTED；W02 整体 IN_PROGRESS。P00—P18 原验收、F1/H1/F2 历史 UNKNOWN 保持。PLANNING_CONFLICT=NONE；EVIDENCE_CONFLICT=PRESENT，待规划窗口独立复核。没有暂存、提交或推送，也没有启动 W02 总贯通、W03、P19。

## 实际接线和结果

原消息经已验收的 W02-A 入站处置进入 C1，W02-B 仍做回应前的本地关联回忆。模型经原 ThinkSession 形成 Information Need 后，P16 在原 E5-A 请求/独立回执链取得 TEST 外部资料。W02-C 对候选核对请求、主体/环境、原回执、Connector、当前根身份、版本、材料 hash、取得/有效时间、可读范围与权限。处置只保存在 P16 可重建投影，外部来源仍掌握根的当前状态，未建立第二请求账本或事实权威。

在本轮回应准备时，当前且与话题相关的资料只作为 `RETRIEVED_CANDIDATE` 进入原 Router/Composer，并由原 Composer 去重、保留冲突及预算裁剪；这不是“已记住”或“必然表达”。缺根证明进入 `NEEDS_EVIDENCE`，后到且当前有效的证明可以核实原请求后解除等待，不重发原查询。不同独立根的相反内容标 `CONFLICT`，不自动选赢家；外部文字声称“授权”或“改变人设”没有控制面权威。

明确注入的隔离 TEST 策略允许至少两个独立、当前可读且达到置信度要求的根，经**原 P04 MemoryConsolidation** 建立 EXTERNAL 记忆及可重建 Summary；同根翻译/摘要不增加独立证据数。这个路径不直接写 SubjectState，也不自动推进人格/关系。撤销、更正、删除、过期或撤权后，候选与旧 Context 失效，原 Router/Composer 中的依赖 Memory/Summary 及 P15 待固化学习支持也重新检查当前根。生产长期吸收策略没有默认启用。

可复核的隔离链例：原 TEST 消息 → W02-A 输入记录 → W02-B 回忆准备 → Thinking 请求 `memory:continuity` → 原 P16/E5-A `external.memory.v1` 回执 → 当前 `external:shared-source:continuity` 根证明 → `CANDIDATE`（未形成主体事实）→ 下一轮回应前 Context 的 `external_candidate` 片段 → ThinkSession 输入。将根改为 REVOKED 后，原历史取得事实仍可核实，但旧 Context 不再 current，后续不能再消费该资料。对应正式测试是 `test_w02_a_and_b_real_ingress_share_pre_answer_external_candidate`、`test_receipted_root_becomes_pre_answer_candidate_not_subject_fact`、`test_revocation_correction_scope_and_expiry_invalidate_old_context`。

## 证据口径和首次失败

开工时 `main`、HEAD/本地及实际远端 `main` 均为 `d23441619f82c1b186736f5d65e2f9de34d95522`，原 290 份源码/测试/资源指纹 `sha256:c3e9649dbf8590a202e5fc82de79bdc6f641fbb41bd4355efd912eaa62c62aed`。[基线](baseline.json)保留 57 份排除材料及保护/正式数据清单。本批当前固定源码和测试指纹 `sha256:41c56bd71950de9aca28b13043797fb794dfd04844dba17dd670341732419056`；后续结果只在前后清单一致时适用。

当前源码/测试/资源共 296 份；原 104 份正式测试文件内容与开工基线一致，新增两份本批测试。最终完整回归的前后清单确认 63 项保护文件、三份规划、正式七文件与原 57 份保留材料均未改变；正式数据树指纹保持 `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`，版本仍为 0.1.0。

修前真实 C1 探针 2 项中 1 FAIL：外部控制面声明仍以旧 P16 候选进入 Context；同根计数对照 PASS。正式测试的初版辅助路径/夹具前提错误和后来“旧日期结果应抛错”的错误预期都以首次输出原样保留。后者的实际 P16 契约是 `CONSUMPTION_DENIED` 且零缓存。相关性新增反例曾出现 21 项中 1 FAIL：无关外部候选进入本轮 Context；仅在 W02-C 投影处复用原 Router 词项语义修补，P16 未启用 W02-C 的路径保持。公共兼容首次 3 个 P17 导入 ERROR 为新增证据运行器缺 `tests` 导入路径；修正运行器后原样重跑。完整历史和原始标签见[测试索引](test-index.md)，不得用后续 PASS 改写这些结果。

前一固定版本完成 `formal-final-04` 21/21、`w02-compat-02` 123/123、`core-compat-03` 260/260 PASS；为补根证明跨主体/环境隔离正式用例，`full-final-01` 在 808.894 秒处有记录地中断，无完成汇总。[原因](full-final-01-interruption.md)保留。其后 `root-boundary-01` 1/1、`formal-final-05` 22/22、`w02-compat-03` 123/123、`core-compat-04` 260/260 PASS；又发现本批控制声明识别误把普通心理内容判为恶意指令，`full-final-02` 在 308.954 秒处有记录地中断，无完成汇总。[原因](full-final-02-interruption.md)保留。收窄命令式识别后，`control-boundary-01` 2/2、`formal-final-06` 23/23（62.512 秒）、`w02-compat-04` 123/123（137.048 秒）、`core-compat-05` 260/260（223.582 秒）均在当前最终指纹下 PASS、退出 0，运行前后身份一致。最终完整回归 [`full-final-03`](full-final-03.json) 实跑 1726 项：1725 PASS、1 既有 Windows 1314 SKIP、0 FAIL/ERROR，1656.915 秒，退出 0，运行前后源码/保护/正式数据/排除项一致。较早两轮无汇总全量仍是中断记录，不能当作 PASS 或 Engine 行为 FAIL。集合有交集，不能相加；旧 W02-B 全量 1703 项仅为历史引用。无远端 CI PASS 证据。

## 保留边界与待复核

隔离 Fake 只证明所测 Engine 链路，不代表真实资料服务、通用语言理解或任意生产 Adapter 的 exactly-once。根提供者当前证明的独立性在 TEST 中显式建模；真实来源选择、长期吸收阈值与生产凭据仍 NOT_READY。P20 的跨 Store/备份删除传播、P22 真实资料服务、P19 完整观察页面未施工。W02 整体最后贯通仍待后续授权；本批不能替代它。

复核顺序：先核对[逐项矩阵](matrix.md)与[原始测试索引](test-index.md)，再用 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONPATH=src;tests` 运行 `E:/Adobe/python.exe -m unittest tests.test_w02_external_absorption tests.test_w02_external_recovery`；W02-A/B、P04/P05/P06/P16/P17 的精确命令见各标签 JSON。`run.py` 只创建新标签，不覆盖旧证据。终局保护审计、逐文件清单与测试进程清理记录按最终核对结果另见 `final.audit.json` 和 `final.pending-files.md`；本报告不将其当作正式验收。
