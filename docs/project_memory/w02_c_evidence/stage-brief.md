# W02-C 开工简报：N11 外部资料可信吸收

状态：IN_PROGRESS。W02-A/B 已验收；W02 整体仍 IN_PROGRESS。本批不含 W02 总贯通、W03、P19、P20 生产删除或 P22 真实服务。

现行来源：[规划版本索引](../现行规划版本索引.md)所列总施工 v1.5、最终新增 v1.5、长期能力 v6.9；核对 W02 施工卡、N11、T23、T04、T18 及 [测试阶段映射](../w01_planning_v15_20260923/test-stage-map.md)。W02-A 拆批说明只用于核对分工。

## 已核对基线

- Engine `main`，HEAD/本地 `origin/main`/实际远端 `main` 均为 `d23441619f82c1b186736f5d65e2f9de34d95522`；暂存区与已跟踪工作区为空。
- 290 份源码、测试和资源指纹 `sha256:c3e9649dbf8590a202e5fc82de79bdc6f641fbb41bd4355efd912eaa62c62aed`。57 份保留材料及保护清单与 W02-B 验收基线相符；本批另存修改前审计。
- W02-B 全量 1703 项（1702 PASS、1 个 WinError 1314 SKIP）仅为历史引用，本批尚未实跑。

## 职责与文件范围

原 P16 结果/独立回执和 E5-A 请求账本继续证明取得事实；新增的吸收判断只是原 P16 可重建缓存中的派生处置，不是第二请求或资料权威。可核验根来源由隔离 TEST/RESEARCH 提供者的当前只读证明端口给出。W02-A 仍负责原始消息逐站记录。Router/Composer 在回应前使用当前可读的候选；P04 的长期更新必须显式经原 Consolidation 且保持 EXTERNAL 证据类型，不由资料文本或分流器直接写 SubjectState。撤销、更正、过期或撤权后，候选、Context 与由该根派生的记忆/摘要投影必须不可继续消费；生产跨 Store/备份删除属于 P20。

拟允许的运行文件：`src/continuity_engine/domain/external_absorption.py`、`src/continuity_engine/services/external_absorption_service.py`、`src/continuity_engine/services/external_capability_service.py`、`src/continuity_engine/services/external_context_source.py`、`src/continuity_engine/services/external_provider_ports.py`、`src/continuity_engine/services/continuity_core_runtime.py`、`src/continuity_engine/services/context_router_service.py`、`src/continuity_engine/storage/json_external_provider_repository.py`。如最终需扩大运行文件，先审查是否超出本批授权与公共边界。

拟允许的隔离测试与证据：`src/continuity_engine/testing/w02_c_fixture.py`、必要的 `p16_provider_fixture.py` TEST 扩展、`tests/test_w02_external_absorption.py`、`tests/test_w02_external_recovery.py` 及本目录。本批必要档案：`03_施工日志.md`、`01_当前状态.md`、`06_未完成事项.md`、CHANGELOG、W02 矩阵与索引。冻结 Schema/契约、pyproject/版本、正式数据、三份规划原文、Assistant/Vio 与原 57 份排除材料禁止修改。

## 验证门

先保存真实修前缺口，再新增正式正反对照；运行 W02-C 定点与专项，T04/T18 及 W02-A/B、P16/P17/P04/P05/P06 直接兼容，固定源码后一次完整 Engine 回归。使用隔离 Fake、可信时钟，记录命令/输出/耗时/退出码及运行前后源码身份。SKIP、首次失败和辅助错误均保留。最后核对保护/正式数据/规划/排除项、文档链接、静态解析、敏感内容与 `git diff --check`。不暂存、提交或推送。

PLANNING_CONFLICT：开工核对为 NONE；实际实施若发现必须改变冻结边界、公共权限语义或把 N11 明确义务后移，立即停止对应项并报告。
