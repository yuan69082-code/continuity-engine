# W02 三批既有证据与贯通缺口（加测前）

只读核对同一已提交源码 `sha256:3bd153ce992261b1b5898da4e980bd0de4da1667f6d0136e27a6b04d300c08ea` 的[A](../w02_a_acceptance_evidence/acceptance-matrix.md)、[B](../w02_b_acceptance_evidence/acceptance-matrix.md)、[C](../w02_c_acceptance_evidence/acceptance-matrix.md)正式矩阵及测试实现。2026-09-25 本轮对现有 `test_w02_a_and_b_real_ingress_share_pre_answer_external_candidate` 实跑 1/1 PASS；[原始结果](baseline-existing-link-01.json)。旧批次数值仅为引用，不能相加称作本轮整包通过。

| Planning Item | 既有正式证据实际覆盖 | 本轮仍需贯通核验 |
| --- | --- | --- |
| N01 / T01—T02 | A 的原始消息经正常 submit、逐站 disposition、部分失败与只读出口；只接收不自动记忆 | 与同轮 N02、N11 的请求／来源／回执／Context 身份相连，不能靠各批独立夹具拼接 |
| N02 / T03—T06 | B 的旧 Event/Memory、同日时间、语义、预算、只读与恢复；Provider 得到最终 Context | 同一消息与 N01 记录、N11 当前外部候选同存于回应前 Context；无关资料不展开 |
| N11 / T04/T23 | C 的 P16/E5-A 回执、当前根、独立证据、候选、撤销、Memory/Summary/P15 支持及跨进程 | 启用 A/B 的同一正常入口，确认资料取得后**下一次**回应前消费；部分派生撤回对这条贯通链生效 |
| T18 | A/B/C 各自恢复及效果、费用、revision 防重 | 一次贯通配置中的局部失败、重开查询、原身份续做和只读零副作用 |

上述现有 C 联验只断言 input manifest、READY recall、外部候选及模型输入，并未逐一串起原始消息内容、站内理由、原外部请求与回执、旧事件来源、最终 Context 和撤回后的下一轮。因此增加最小正式集成测试；既有验收用例不修改。若新测试发现已验收运行实现缺口，先保留失败并请求定向修改确认。
