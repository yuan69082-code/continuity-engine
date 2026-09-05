# P11 Event Priority 与 Scheduler 架构边界及 Stage Brief

> 现行状态：P00—P11 = ACCEPTED；P11 / P11 Engine side / P11-01—P11-12 = ACCEPTED；P11 Vio dependency = NONE；P12—P23 = NOT_STARTED；PLANNING_CONFLICT = NONE；EVIDENCE_CONFLICT = NONE（仅表示现行验收阻断已闭合）。D-057 保留开工/返修历史；D-058 已登记正式验收，见 [58 第 9 节](58_P11_测试索引与验收入口.md#p11-accepted)。

## STAGE

P11 — Event Priority 与 Scheduler，Engine 独立施工。Scheduler 只决定何时给同一 Subject 一次计算/认知机会，不产生心理内容，不执行现实动作，不形成后台常驻 Runtime。

## SOURCE OF TRUTH

1. 用户于 2026-09-05 明确授权的 P11 范围、边界、矩阵和停止条件。
2. 2026-08-26《Continuity Engine（数字连续性引擎）全周期工程监工规划 v1.1》P11 施工卡及统一验收门。
3. 2026-08-26《连续性引擎长期能力增补规划 v6.7》及 Architecture Amendment D1、Override、Keep 条款。
4. D-056、P00 阶段基线、P00—P10 矩阵和当前真实代码。
5. 现有 `AwakeningService`、`WakeSession`、`ResourceManager` 与 `ResourceAwareWakeScheduler` 的实际行为。

三份规划源只读，不修改或重新保存；P10 的 31 个本地审计脚本按开工清单隔离保护。

## ORIGINAL REQUIREMENTS

- 以重要性、到期时间和资源状态调度事件与内部任务。
- 支持 `priority`、`dueAt`、`wakeReason`、持久化队列、确定性排序、背压、防饥饿、有界重试、取消、跨重启恢复、静默时段、Fake Notification Adapter 与可信投递回执。
- 资源不足时安全延迟；同一任务、同一投递尝试和重复 tick 不重复执行。
- 使用 Engine 可信 UTC 时钟；测试使用 Frozen Clock，不调用真实 `sleep`。
- 组合验证 Awakening、Timeline 和 P09 正常链，但能力依赖不表示每个请求机械执行全部模块。

## V6.7 DETAILS

- Scheduler 处理并发队列、优先级、批处理与必要的有界抢占语义，同时保持 Awakening → Perception → Thinking 管线边界清晰。
- `priority` 是可解释的调度输入，不是 Will、Desire、人格、情绪或心理强度。
- 持续性不得实现为“每隔若干分钟叫醒模型思考”；Scheduler 只发出一次有界 computation opportunity。
- 调度 Trace 仅记录稳定身份、状态、时间、来源引用和理由码，不保存任务正文、凭据或 Provider 隐藏思维链。

## AMENDMENT OVERRIDES

- Architecture Amendment D1 覆盖把 Scheduler 解释为心理内容生成器的旧表述：它只能选择计算机会的时机。
- P01—P21 Engine 必须在 Vio 不可用时独立施工和验收；P11 不访问 Vio。
- SubjectState 是主体状态唯一权威；Event 是事实权威；心理状态变化只能经过既有 Evolution/revision 链。
- Event 的客观时间保持原值；P11 不提前实现 Subjective Time。

## KEEP RULES

- 保留 P00—P10 已验收接口、序列化与恢复语义。
- 保留既有 Authority、来源、版本、hash、provenance 与失效传播。
- 复用 Awakening 和 Resource 边界；不建立第二套唤醒、资源、Capability 或 Action 账本。
- UNKNOWN 先按稳定 attempt/receipt identity 查询；自洽 hash 不代替可信回执。
- 已完成终态不倒退；取消幂等；资源/静默/背压延迟不消耗 attempt，不丢任务。
- 本地 Fake/原子持久化的不重复投递结论不外推为任意生产 Adapter exactly-once。
- 六份冻结外部 Schema、25 项冻结边界、`pyproject.toml`、版本 0.1.0 和正式数据不变。

## DEPENDENCIES

- P10 = `ACCEPTED`，已满足阶段前置条件。
- P03 Event/Timeline、P08 Action/E5-A、P09 C1、Awakening 与 Resources 均复用其已验收边界。
- P11 Vio dependency = `NONE`；测试只用 Engine 内 Fixture/Fake 与独立数据根。

## NOT READY

- P12 Intentional Forgetting、P13 Expression Policy、P14 Dynamic Mind、P17 Execution Engine、P18 Persistent Runtime、P20—P22 均未开始。
- 真实 Notification/Provider/Vio/生产 Adapter、凭据、网络、外部数据库、后台服务和生产 exactly-once 均不在 P11 范围。
- Assistant 是否同步通用 Scheduler 等待 Engine P11 形成固定提交后的另行决定；本阶段 Assistant 只读。

## FILES ALLOWED

运行实现和测试仅限：

- `src/continuity_engine/domain/scheduling.py`
- `src/continuity_engine/services/scheduler_ports.py`
- `src/continuity_engine/services/scheduler_service.py`
- `src/continuity_engine/storage/json_scheduler_repository.py`
- `src/continuity_engine/testing/p11_scheduler_fixture.py`
- `tests/test_p11_scheduler.py`
- `tests/test_p11_scheduler_recovery.py`
- 为公开 P11 类型所必需的 `src/continuity_engine/domain/__init__.py`、`services/__init__.py`、`storage/__init__.py`、`testing/__init__.py`、包根 `__init__.py`，以及为仓储 Protocol 所必需的 `storage/base.py`
- 若真实组合测试证明必要，可对 `ResourceAwareWakeScheduler` 做保持旧签名兼容的局部接线；任何此类修改必须先有失败证据。
- `docs/project_memory/55`—`58`、P11 证据目录及本提示要求同步的既有工程档案。

## FILES FORBIDDEN

- `src/continuity_engine/interfaces/**`、六份冻结外部 Schema、`pyproject.toml`、版本声明和 `.continuity-data/**`。
- SubjectState、Event、Memory、Contradiction、Action、Capability、E5-A 的 Authority/账本与既有外部契约。
- 三份 2026-08-26 规划源文件。
- `C:/Users/Administrator/Documents/continuity-assistant/**`。
- `docs/project_memory/p10_evidence/**` 中开工时已存在的 31 个未跟踪本地辅助脚本。
- P12—P23 运行实现，以及真实网络、Provider、Vio、生产 Adapter 或后台轮询。

## TESTS REQUIRED

2026-09-05 首次 admission 定点返修补充授权：本轮代码只改 `services/scheduler_service.py` 的 submit 前置校验及 `tests/test_p11_scheduler.py` 的直接回归。验证限定为新增定点和完整 P11 专项，不重复下列首版施工的三轮全量；原已完成全量继续作为历史保留。

- 修改前 Engine 全量基线与原测试身份清单。
- 先保存 P11 失败反例，再实现 P11-01—P11-12。
- P11 专项：定时/未到期/乱序、排序、背压、防饥饿、资源不足、静默时段、取消、UNKNOWN 查询、回执冲突、有界重试、重复 tick/receipt、损坏持久化、跨重启和 Golden。
- 直接相关：Awakening、Resources、Event/Timeline、P08、P09。
- P00—P11 综合矩阵；代码稳定后完整回归连续三轮；档案后终局 P11 专项和全量。
- Python AST、Markdown 链接、敏感内容、缓存/Sandbox 残留、`git diff --check`、正式数据逐文件 hash、冻结边界及 31 个 P10 脚本终局对比。

## PLANNING CONFLICT

`NONE`。用户本轮授权与 v1.1 P11、v6.7 D1/Override/Keep 及当前 Engine 边界相容。若后续真实实现证明必须修改冻结契约、正式数据、Assistant、生产适配或后续阶段，停止对应项并将冲突如实更新为 `PRESENT`。

## 开工实测

- 分支/HEAD/本地 `origin/main`：`main` / `a905853ca05edd56d9a8b0164818b4388a90b85f` / 同值；ahead/behind `0/0`；暂存及 tracked diff 为空。
- 修改前完整回归：794 tests，793 PASS、1 SKIP、0 FAIL；unittest 410.432 秒，进程墙钟 411.338 秒。该结果是本轮实跑，不替代 P10 历史证据。
- 正式数据：7 文件，tree inventory `sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2`。
- 25 项冻结边界全部匹配开工预期；`pyproject.toml` SHA-256 `40703a155ab1c1626901d1b61363384e49b5c64e58303cc110fe499ff6c25419`；版本 `0.1.0`。
- 31 个 P10 未跟踪辅助脚本的路径、长度与 SHA-256 见 [开工清单](p11_evidence/start-20260905/before.json)。
