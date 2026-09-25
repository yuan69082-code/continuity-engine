# W02 整体贯通正式验收矩阵（D-081）

用户正式验收仅覆盖现行规划的 W02 内部贯通；原[A](../w02_a_acceptance_evidence/acceptance-matrix.md)、[B](../w02_b_acceptance_evidence/acceptance-matrix.md)、[C](../w02_c_acceptance_evidence/acceptance-matrix.md) 各批验收不倒改。本矩阵引用[施工时矩阵](../w02_integration_evidence/matrix.md)及固定源码 `sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1` 的[原始测试索引](../w02_integration_evidence/test-index.md)；规划窗口只读复核，未独立运行测试。

| Planning Item | Code Change / 原职责 | Test / 本批验收依据 | Acceptance Result |
| --- | --- | --- | --- |
| N01 / T01—T02 | 正常 `submit`、原 `InputProcessingService` 逐站记录；收到材料不自动成为长期记忆 | 新贯通原始消息、站理由、只读零副作用；A/B/C 兼容 156 PASS | `ACCEPTED`，仅 W02 内部链 |
| N02 / T03 | 原 `AssociativeRecallService` → Router/Composer → Thinking 输入 | 同日旧 Event/Memory 在回答前进入最终 Context，Fake Provider 输入一致；贯通 8 PASS | `ACCEPTED` |
| N02 / T04 内部部分 | 原根证明、同源去重和 W02-C 撤回；不另造人物认识库 | 同源转述不增加独立根，派生撤回后依赖失效；A/B/C 兼容 156 PASS | `ACCEPTED`；W03 长期认识部分 `NOT_READY` |
| N02 / T05 | 原 W02-A 有界否定/指代与 B 真实入站语义对照 | 否定、他人、愿望、历史时间维持非事实解释；A/B/C 兼容 156 PASS | `ACCEPTED`，不宣称通用语言理解 |
| N02 / T06 | 原检索预算、关联展开与明确停止理由 | 不相关不展开、重复/环路停止、预算失败不伪称不存在；贯通与 B 兼容 PASS | `ACCEPTED`；四份同时资料的 1000 毫秒负载仍是已记录限制 |
| N11 / T23 内部部分 | 原 P16/E5-A 请求及独立回执、W02-C 根核验和候选投影 | 同主体原请求、回执、合法候选与下一轮最终 Context 串联；贯通 8 PASS | `ACCEPTED`；P19 页面、P22 真实服务 `NOT_READY` |
| N11 撤销 / T23 | 原 Memory/Summary/P15 当前根材料核验 | 仅撤回派生后旧 Context、依赖 Memory/Summary、学习支持及下一轮使用停止；贯通与公共兼容 PASS | `ACCEPTED`；P20 跨 Store/备份删除 `NOT_READY` |
| T18 / N01+N02 恢复 | 用户定点授权的 `ContinuityCoreService._prepare` 原 Context 复用点补做失败站；不重发模型/效果 | 修前 A+B ERROR，修后同反例、重开、撤权、重复失败对照 PASS；公共兼容 318 PASS | `ACCEPTED`；原首败保留 |
| W02 整体 | 上述 A/B/C 同版正常链及单处获授权恢复补修 | 专项 8 PASS、A/B/C 156 PASS、公共 318 PASS；全量 1735 PASS/1 既有 SKIP、0 FAIL/ERROR，集合重叠 | `ACCEPTED`；仅本次内部贯通 |

早期四份资料负载触及时限的原始 ERROR 仍是有效限制，最终两份资料对照不能替代四份负载证明。历史 F1/H1/F2 `UNKNOWN` 与 Win1314 SKIP 保留。W03、P19、P20、P22 后置边界不因本矩阵改变。
