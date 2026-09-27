# W04-2 Stage Brief：模拟设备操作与模拟身体闭环

状态：IN_PROGRESS。D-088 仅记录本次开工，非验收；W04-1/D-087 保持 ACCEPTED。

| 栏目 | 本批约束 |
|---|---|
| STAGE | W04 原四子批次之二，不另造阶段，不开 W04-3 |
| SOURCE OF TRUTH | 现行索引所指总施工 v1.6 W04、最终新增 v1.6 N10/N12/N13/N21、长期能力 v6.10；原件及 hash 见 baseline.json |
| ORIGINAL REQUIREMENTS | 受控模拟 UI 观察、定位、输入、操作、结果再观察；模拟身体传感→Perception、动作→原 P17/E5-A；局部历史 UI 查询→原 Router/Composer |
| CAPABILITY DETAILS | 主体、环境、设备、软件、账号、会话、连接代次、授权、观察和动作参数绑定；点击与业务完成分开；UNKNOWN 查询优先，不盲重发 |
| AMENDMENT OVERRIDES | 新版要求可运行模拟身体，不能以空接口替代；梦感官仅分源契约，无梦功能施工 |
| KEEP RULES | 单一 SubjectState/Event/Memory/E5-A；当前权限、Context、资源、生命周期、Reality/Recovery 门禁；旧公开格式与无新接线路径兼容；不动心理政策 |
| DEPENDENCIES | 已验收 W04-1 身份/能力、P16/P17 结果与秘密边界、P18 持续运行、W02 输入/召回、W03 事项 |
| NOT READY | W04-3 工具自主发现、W04-4 跨入口续接；W05 梦/自然记忆人格联动；P19 页面、P20/P21 正式恢复、P22 真实设备服务 |
| FILES ALLOWED | 下列精确实现/测试路径及本目录证据；必要六份现行档案新增本轮记录 |
| FILES FORBIDDEN | 63 项保护、7 份正式数据、三份规划原文、版本、70 份保留材料、旧证据；Assistant/Vio、真实执行端 |
| TESTS REQUIRED | T27—29/T37/T18、T22/T85—87、本批 T66/67/72；每项正反/恢复/权限/隔离；W04-1 和 P16/P17/P18/W02/W03 兼容，固定源码一次完整回归 |
| PLANNING CONFLICT | NONE（开工只读核对范围）；实际发现冲突立即停受影响项 |

## 实际文件范围与公共影响

- 新增 `src/continuity_engine/domain/device_operation.py`：内部版本化动作/观察契约，参数保存于原 ActionSpecification/E5-A；不建参数或事实账本。
- 新增 `src/continuity_engine/services/device_operation_service.py`：设备/身体当前性门禁、结果语义和传感/查询消费；复用原 Perception/Router/Composer。
- 修改 `src/continuity_engine/domain/action_planning.py`：仅给内部 `device.*` 动作增加受校验的可选参数，旧参数缺省仍保持旧行为；不改冻结外部 Schema。
- 修改 `src/continuity_engine/services/execution_service.py`：设备类请求经显式设备门禁；原普通 P17 请求路径不变，回执/UNKNOWN/取消仍由原账本负责。
- 修改 `src/continuity_engine/services/execution_context_source.py`：本批 UI 历史查询保留原材料根，避免重复查询按两个执行请求虚增独立依据；普通 P17 结果来源保持。
- 新增 `src/continuity_engine/testing/w04_device_fixture.py`、`tests/test_w04_2_simulation.py`：隔离外部世界状态、原正式入口和跨进程恢复；替身不存主体人格、不提供最终理解。
- 六份档案：`01_当前状态.md`、`03_施工日志.md`、`04_决策记录.md`、`06_未完成事项.md`、`10_档案修订记录.md`、`工程总档案.md`。只新增本轮区域，不替换历史。

不改变动作权限/费用规则；模拟成功效果按既有 E5-A synthetic credit 契约结算。拒绝、离线、页面变动和未知都有独立可读结果。历史成功可核实不等于获准新执行或新消费。回退只讨论本轮差异，不执行 reset 或改写已有成果。
