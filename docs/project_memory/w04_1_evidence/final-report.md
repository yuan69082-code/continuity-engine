# W04-1 接口与身份绑定交付报告

状态：`IMPLEMENTED_NOT_ACCEPTED`，不代表用户验收。用户仅授权 W04 第一子批次实现、隔离测试和档案；无 Git 暂存、提交或推送授权。现行规划是总施工 v1.6、最终新增 v1.6、长期能力 v6.10；[Stage Brief](stage-brief.md)、[逐项矩阵](matrix.md)、[链路示例](chain-example.md)和[原始测试索引](test-index.md)可直接复核。

## 实际完成

- N08：内部连接元数据区分听说、发现、连接和**当前可用**；使用前按主体/环境、宿主代次、通道、用途、范围、期限、连接与授权重验。断线、撤权或旧宿主不能靠旧清单放行。候选替代路由仍逐条核对。
- N09：分别表示首次外部导入、同主体迁移准备、新主体创建和入口切换。隔离 TEST 的交接清单保存缺项与时间来源引用，generation 失权保护在重开后仍成立；正式迁移、生产恢复和唯一运行权转移仍归 P20/P21。
- N10 第一批：BODY `NONE/SIMULATED/REAL`、身份和绑定、能力方向/单位/坐标/有效期/范围、零值与未知分开；隔离模拟观察不能冒充内部 Somatic 或梦境。TEST 行动资格接到原 P17 最终投递前检查，动作效果/扣费/回执仍由原 E5-A 掌管。完整 Fake Body 感知→Perception 和动作→结果闭环是 W04-2，未伪报完成。
- N12：消息、工具、普通模型 API、同 Engine 集成分类分开；原 `ContinuityInteractionService.submit` 的可选内部参数在首次 operation/Wake 写入前核对可信连接身份。受保护的正式适配器与冻结 v1 消息格式保持原字节；同名账号不等于同一主体或全内容共享许可。
- N21 第一批：局部历史查询载明对象、软件/设备/会话、时间、来源、权限、意愿及限量；复用 Router/Composer 只给来源、版本/hash 的候选引用，不把索引变事实。深层归档和外部考证有意愿门且返回依赖未就绪；W05 自然记忆、再理解、梦和心智联动未施工。

公共影响仅在 TEST/RESEARCH 的可选内部连接被明确配置时生效；原 W02 入站、P17 请求/结果、P18 控制和默认旧调用路径未改职责。`JsonEnvironmentRepository` 是连接元数据仓储，不是第二主体状态、Event、Memory 或效果账本。旧正式数据不迁移；没有 W04 元数据时旧入口行为保持。未连接、缺权限、旧 generation 或损坏元数据均失败关闭。主体暂停/停止、现实权限、资源、费用与生命周期边界沿原链。

## 测试事实及限制

固定源码/测试/资源 310 项，指纹 `sha256:166dc0fcd1404560b7dff5af2bb253e751b5d5051e78484413a60f27bfb02824`。本批专项 `w04-targeted-09`：24 PASS，10.105 秒，退出 0；P16/P17/P18/W02/W03 受影响兼容 `w04-compat-fixed-01`：182 PASS，265.448 秒，退出 0。两组运行前后指纹一致，测试集合重叠，不相加。[原始结果](test-index.md)分别有完整命令和 stdout/stderr。

完整回归 `w04-full-final-01`：1797 项，1796 PASS、1 个既有 Win1314 SKIP、0 FAIL/ERROR，1650.896 秒，退出 0；运行前后指纹亦相同。各集合有交集，不相加。历史中 `w04-targeted-01` 的 Frozen Clock 辅助 ERROR、`w04-targeted-04` 的测试对照 FAIL、`w04-compat-01` 的五项测试启动导入 ERROR，以及源码漂移的 `w04-compat-final-01` 均原样保留，不用之后 PASS 覆盖。F1/H1/F2 历史根因仍是 `UNKNOWN`；原 Windows 1314 SKIP 仍按 SKIP 计，没有远端 CI 证据。

## 保留项与独立复核

D-085 的 20 项新版规划归档是进入本批前已授权但未提交的工作区成果，单独由 [其返修审计](../planning_v16_20260927/final.audit.repair-01.json)固定；本批不清理或提交它。原 57 项保留材料中 56 项不动，现行规划索引是 D-085 的授权变更。63 项保护文件、三份权威规划原文、七份正式数据及版本保持。本批先生成的 `final.audit.json`/`final.pending-files.md` 是报告定稿前审计；`final.audit-02.json` 记录了生成自身时的链接检查假阳性，两组均保留为过程记录。**定稿后的**路径、hash 与范围见[终局审计](final.audit-03.json)和[精确清单](final.pending-files-03.md)。

独立复核可在独立 TEST 根重跑 `E:/Adobe/python.exe -m unittest tests.test_w04_1_environment -v`（需 `PYTHONPATH` 同时包含仓库 `src` 和 `tests`），再按 [测试索引](test-index.md)选兼容或全量。证据 runner 的标签不可覆盖，应另取新标签。无真实设备、账号、Vio、外网、凭据、生产 Adapter 或正式主体操作；更大的真实负载和生产表现未经本批验证。W04-2/3/4、W05、P19—P23 均未开工。
