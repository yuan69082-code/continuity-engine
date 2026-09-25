# 一条可核对的原消息到回应前材料链（隔离 TEST）

来源为固定版[贯通专项 stdout](integration-targeted-01.stdout.log)与[原始运行记录](integration-targeted-01.json)。这里只摘取结构和来源身份；查看该文件不会调用模型、检索、学习或执行。完整正文仍留在隔离测试过程，不作为事实权威。

| 顺序 | 本轮实际证据 | 这一步证明的范围 |
| --- | --- | --- |
| 原消息入站 | 第一条请求 `p01-request-0a8542e9bdcc475ebabf8aab4d4bccf9`，原消息“我又在吃螺蛳粉。”经原契约 hash 后送入 Engine 正常 `submit`。 | 不是绕开入站的直接 Router 调用。 |
| W02-A 逐站 | `conversation`、`memory` 两站；memory 理由 `MESSAGE_IS_NOT_VERIFIED_EVENT`。 | 收到的陈述在本轮临时可用，但没有因说过就被写成已证实的长期记忆。 |
| W02-B 回忆 | 第二条原消息 `p01-request-9a5616f609db47b18c184e2bd89ff88b` 的 Recall `READY`，停止原因 `NO_NEW_ASSOCIATION`；最终 Context 中有当前消息、旧 Event/Memory/Timeline。 | 回答形成前完成评估并遵守停止理由；旧材料来自已有权威。 |
| W02-C 外部取得 | 第一轮原能力请求 `action-cap:948c…`、TEST 回执 `receipt:efd9…`；取得的有来源资料处置为 `CANDIDATE`。 | 回执证明原 TEST 取得事实，候选不自动升级为主体事实。 |
| 最终 Context | 来源包含 `engine.current-input`、`engine.memory`、`engine.timeline`、`engine.external-candidates`；第二次 Fake Provider 输入与该 Context 相同。 | 检索与候选消费发生在回答前，未用各批孤立输出拼造结果。 |

相同专项中的无关材料不展开、只读查询无副作用、局部失败恢复和部分派生撤回分别有独立正反测试；见[矩阵](matrix.md)。该样例只证明隔离 Fake 的工程链，不宣称真实服务、通用中文理解、P19 页面或生产删除传播已就绪。
