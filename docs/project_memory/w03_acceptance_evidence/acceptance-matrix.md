# W03 逐项正式验收矩阵（D-083）

本矩阵记录用户对已交付 W03 Engine 范围的正式验收。施工时的失败和 `IMPLEMENTED_NOT_ACCEPTED` 状态仍保存在[原矩阵](../w03_evidence/matrix.md)与[返修证据](../w03_n06_repair_evidence/report.md)，不回写历史。测试结果来自施工方同一最终源码实跑；规划窗口为只读复核。

| Planning Item | Code Change | Test / 原始证据 | Acceptance Result |
| --- | --- | --- | --- |
| N03 / T04 | `SubjectGrowthService.capture` 沿 Event、Memory、Learning 同根去重；`RecognitionService.validate` 按当前独立根核验。 | `tests/test_w03_recognition.py`：原消息入口、三独立事件、同根重放与摘要、同名不同对象。 | `ACCEPTED`；受控 TEST 注解不等于真实自由语言质量验收。 |
| N03 / T07、T08 | `RecognitionService.commit/withdraw/read` 经原 Action Gate/Evolution 保留反证、更正、撤销及旧依据；当前状态仍在 SubjectState。 | 同文件的强化、削弱、纠正、反例、权限和版本变化及重开只读对照。 | `ACCEPTED`；不建立第二对象状态权威。 |
| N04 / T09 | `ContinuityCoreGates.essential_core`、原 Router/Composer 与正常 C1/Thinking 输入；缺失/过期/超预算显式失败。 | `tests/test_w03_core_context.py`：正常回应、模型替换、核心缺失和预算裁剪。 | `ACCEPTED`；完整常驻联动及生产配置仍后置。 |
| N06 / T12 | `UnfinishedItemService.submit/ready/read` 复用 SubjectState/Evolution/CAS；原有界当前事项集合只保留未终结项，终态保留原 Event/Evolution 历史。 | `tests/test_w03_unfinished_items.py`、`tests/test_w03_n06_repair.py`；受阻急事与普通事、65 件连续终结后再新增、完成/取消/重开及旧命令重放。 | `ACCEPTED`；W05 的完整持续运行联动未在此验收。 |
| N06 / T12 旧数据 | 显式旧列表位置、标题、列表 hash 与当前 revision 绑定，原 Evolution 更新中迁移；无身份依据不自动合并。 | `tests/test_w03_n06_repair.py`：创建及已有结构化事项终态转换、无绑定同名、错误列表指纹和重复命令。 | `ACCEPTED`；无可靠身份的旧字符串仍独立显示，等待合法显式绑定。 |
| N06 / T18 来源与完成 | `_verify_roots` 复用 Memory/Timeline、P05 来源授权、W02-C 外部根和具体材料当前核验；完成依原内部事实或 E5-A 成功回执。 | 两份 N06 测试：Memory 不可用及撤权、派生材料部分撤回、跨主体、重开、只读零写入、失败与返回丢失。 | `ACCEPTED`；真实生产效果的 exactly-once 未宣称。 |
| 兼容与整体验证 | 原 P09/C1、P11/P18、P14/P15、W02 链路不改变权威。 | [原始索引](../w03_n06_repair_evidence/test-index.md)：专项 32 PASS、兼容 176 PASS、全量 1767 PASS/1 既有 SKIP，三组同一源码指纹且交叠。 | `ACCEPTED`；旧 W02 `RECALL_TIMEOUT` 与四份负载风险仍保留。 |

现行 W03 已知验收阻断据用户决定关闭；历史 F1/H1/F2 为 `UNKNOWN`，原 FAIL/ERROR、中断、辅助错误和 SKIP 不改写。W04/W05/P19 未因本次验收开工。
