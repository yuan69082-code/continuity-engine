# W04-1 Stage Brief：接口与身份绑定

2026-09-27 用户已授权本子批实施、隔离测试及档案同步；此前 [未授权的审阅简报](../planning_v16_20260927/w04-1-pre-kickoff-brief.md) 保留为历史。本批状态 `IN_PROGRESS`，不是 W04 整体验收。

| 栏目 | 本轮决定 |
|---|---|
| STAGE | W04 四子批次之首：接口与身份绑定。W04-2 才做完整 Fake Body 感知与动作效果闭环。 |
| SOURCE OF TRUTH | [现行索引](../现行规划版本索引.md)所列总施工 v1.6、最终新增 v1.6、长期能力 v6.10；W04 正文、N08/N09/N10/N12/N21、[需求差距](../planning_v16_20260927/requirement-matrix.md)和[测试映射](../planning_v16_20260927/test-stage-map.md)。既有代码与 D-081/D-083/D-084 是实际基线。 |
| ORIGINAL REQUIREMENTS | 环境与能力四态、导入/迁移/创建/入口切换分开、身体类型/身份/能力/有效性、入口与账号会话用途范围绑定、局部历史查询契约。 |
| CAPABILITY DETAILS | 环境元数据只记录连接和候选状态；正式请求仍经 Subject Binding、P16/P17、W02 入站、Router/Composer 与 E5-A。来源与权限每次使用前重验，断线/撤权/代次变化失效。 |
| AMENDMENT OVERRIDES | 新版 N10 要求 W04 整包有可运行模拟感知及动作；本批先完成可验证契约与接线，W04-2 完成双向效果。N21 本批是局部历史查询范围和来源契约，W05 才做自然记忆与心智联动。 |
| KEEP RULES | 不撤销 W02/W03/P00—P18 验收；F1/H1/F2 UNKNOWN、旧 FAIL 和 Win1314 SKIP 不倒改。主体状态、Event、Memory 与请求结果只认原权威。 |
| DEPENDENCIES | P15 Subject Binding/Genesis、P16 外部能力、P17 执行和回执、P18 运行控制、W02 回答前回忆、W03 认识及事项。 |
| NOT READY | W04-2/3/4、W05 自然记忆与梦、P19 页面、P20/21 正式恢复和运行权、P22 真设备与服务、P23 总验均未完成。 |
| PLANNING CONFLICT | 开工文本与既有内部接口未见需要改冻结契约的必然冲突；如施工中出现，暂停受影响项并具体报告。 |

## FILES ALLOWED / FILES FORBIDDEN

允许新增 `src/continuity_engine/domain/environment_access.py`、`storage/json_environment_repository.py`、`services/environment_access_service.py`、`services/scoped_history_service.py` 和 `tests/test_w04_1_*.py`；允许最小局部修改 `services/continuity_interaction_service.py`、`services/execution_service.py` 的**可选内部接线**，原调用者默认路径不变。允许本目录的测试、审计、矩阵与证据，以及 `docs/project_memory/01_当前状态.md`、`03_施工日志.md`、`04_决策记录.md`、`06_未完成事项.md`、`10_档案修订记录.md`、`工程总档案.md` 的本轮新增区块。`interfaces/local_integration_app.py` 和 `interfaces/integration_adapter.py` 在 63 项保护清单内，维持原字节；W04-1 使用原服务的内部入口验证绑定。

禁止修改六份冻结外部 Schema、受保护外部契约、三份规划原文、`pyproject.toml`、正式数据、63 项保护文件和 57 项旧排除材料（其中现行规划索引作为前置档案已获单独更新，本轮不再修改）。不接真实设备、账号、Vio、服务或凭据；不另建请求/效果账本或主体状态。

## TESTS REQUIRED

N08/T16/T17：四态、断线、过期、撤权、替代路由。N09/T19—T21/T60：导入、迁移准备清单、缺项、旧端失权隔离契约、新主体与入口切换。N10/T22/T85—T87 的本批契约：NONE/SIMULATED/REAL，三源、单位/零值/未知、代次、感知/行动入口绑定；完整效果留 W04-2。N12/T26/T33：消息/工具/模型 API/Engine 集成入口及同名错人。N21/T66/T67/T72：局部范围、当前授权、来源与结果引用，深层回查意愿门。联验 T18 恢复和只读查询零写入。先专项，后 P16/P17/P18/W02/W03 兼容，固定源码后全量；各组原始输出及源码身份分别留存。

## 前置工作区分离

HEAD `546fb25db0f1e248c703db855ee754234ce59458`、`main`；D-085 新规划归档的 20 项见 [前置审计](../planning_v16_20260927/final.audit.repair-01.json)及[清单](../planning_v16_20260927/final.pending-files.repair-01.md)。其 305 项源码/测试/资源指纹 `sha256:1008aabea9c72f769b97886cd9017051da083a95d14f9d9a010d7a738daa297b`。实际远端 main 以 OpenSSL TLS 的只读查询核到同一 SHA；默认 schannel 查询曾报 `SEC_E_NO_CREDENTIALS`，不是提交或测试失败。57 项旧排除材料中 56 项 hash 未变，现行版本索引为前置授权修改。暂存区空。以上不计作 W04-1 代码成果。

施工后注：本文件保留开工时 `IN_PROGRESS` 口径作为历史。现行交付状态已更新为 `IMPLEMENTED_NOT_ACCEPTED`，固定源码、终局测试与限制见[交付报告](final-report.md)和[矩阵](matrix.md)，未登记用户验收。
