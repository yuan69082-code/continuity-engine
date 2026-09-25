# W03 开工简报与施工矩阵

状态：IN_PROGRESS；本文件记录 2026-09-25 用户授予的 Engine W03 施工范围，尚非验收。

## 基线与来源

- `main`、HEAD／本地 `origin/main`／实测远端 `main`：`ec9c59054a599d028e39a80134abec6aa9802eba`；开工时暂存区和已跟踪工作区为空。
- 297 份源码／测试／资源，指纹 `sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1`。W02 全量 1735 PASS／1 既有 SKIP 是历史引用，本轮尚未实跑。
- 权威规划：总施工 v1.5 (`465be409311d5ded8522021770506dc86d7f84ec0f120d3f1c117be6f66de388`)、最终新增 v1.5 (`55ddcffaffe8e216ab1d0561e72ca5b81ae55bebdec40a805295697d5d103cfc`)、长期能力 v6.9 (`c125ef6dae3fbd03c63e02c87316647ca2c44a02c56aa6f8191e6c2fcdcfe5e0`)；均与现行版本索引一致。
- D-081 已验收 W02；W03 本轮只实施并交独立复核。旧 F1/H1/F2 根因仍 UNKNOWN，W02 四份资料触及 1000ms 回忆时限的限制不因本包改变。

## Planning Item → 现有代码入口 → 真实缺口 → 拟改文件 → 测试 → 验收证据

| 项目 | 现有入口与可复用部分 | 真实缺口 | 拟改文件 | 测试及证据 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| N03／T04／T07／T08 | `LearningService` 的独立根验证、`SubjectGrowthService` 与 `relationship.objects` 的原 Evolution、W02 来源及 Memory | 缺对象别名／范围／反例／更正关系的可重建认识视图；现有 P15 条目是主观解释而非完整证据视图 | `domain/recognition.py`、`services/recognition_service.py`，必要的原 Learning／Growth 局部接线及 TEST | 同源去重、三独立根、同名消歧、反例纠错、撤销／版本变化、成功内化及重开只读 | IN_PROGRESS |
| N04／T09 | `SubjectStateContextSource`、Router／Composer protected 材料、正常 `ContinuityCoreService.prepare`／Thinking | 核心的身份、自我认识、关系未被正常回应强制保留；缺失、过期和预算不足缺可读状态 | `services/context_router_service.py`、`services/context_composer_service.py`、`services/continuity_core_service.py` 内必要接线及 TEST | 日常无关键词仍带核心、三层区分、预算不足显式失败、权限／版本漂移、模型替换走同接口 | IN_PROGRESS |
| N06／T12／T18 | `continuity.unfinished_items`、`intentions.dynamic_mind`、`SchedulerTask`／P18；原 Evolution 和 Action Gate | 现有未完事项仅字符串，缺稳定身份、来源、等待与完成事实；Scheduler 只有唤醒任务而非主体意图 | `domain/models.py`、`domain/evolution.py`、`domain/unfinished_item.py`、`services/unfinished_item_service.py` 与必要上下文／调度接线及 TEST | 旧数据映射、同一事项升级降级、急事受阻公平排序、完成可靠回执、取消／延期、CAS／返回丢失／重开 | IN_PROGRESS |

## 范围、兼容与回退

允许仅在上述职责内新增或局部修改运行文件、`tests/test_w03_*.py`、独立 TEST Fixture、W03 证据及必要工程档案。原六份冻结外部 Schema、外部契约、三份规划原文、63 项保护清单、正式七文件、57 项保留材料、版本、Assistant/Vio 均禁止修改。`SubjectState` 仍是唯一当前主体状态权威；如添加内部可选字段，旧数据缺字段须按原状读取，不改变已冻结外部 Schema。事件和 Learning 历史不可改写；Scheduler 只安排计算机会，不制造意愿或承诺。所有试验用隔离 TEST 根，失败保留原记录；回退只在 Fixture 内验证，不处理正式主体。

公共影响包括 Router／Composer 的正常 C1 回应用材、SubjectState 旧序列化、Learning 与 Evolution 读取、P11/P18 调度查询。逐项定点及正向对照先于 W03 专项、受影响兼容和最终同版全量。真实模型语言理解、完整 P19 页面、P20/P21 正式恢复与迁移、P22 现实设备和生产凭据、W04/W05 完整运行联动均为 NOT_READY，不以本包接口冒称完成。

开工核对未发现三份现行规划之间的实质冲突；施工中若发现真实冲突，停止受影响项并记录 `PLANNING_CONFLICT`，等待用户决定。
