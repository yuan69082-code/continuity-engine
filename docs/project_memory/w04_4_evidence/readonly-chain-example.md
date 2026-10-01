# 同一主体的实际只读链路样例

来自 [targeted-final-02.stdout.log](targeted-final-02.stdout.log) 的本轮实际结果，结构化引用见 [readonly-chain-example.json](readonly-chain-example.json)。本页不启动Engine或重新执行业务。

| 环节 | 原记录身份 |
|---|---|
|Subject|`sub-6cef3a33326c4a1f`|
|P16发现|`action-cap:0b85a39844d84c69d0fe9e0f2068a7f8d7827bd9f584f05c9852fbcce9b6cfbe`|
|临时连接|`action-cap:55252d623bd88ac667868db1776176fc8a42bfdb4420c33a374b6b5f534ac84e`|
|指定历史查询|`action-cap:521a4b62028a469171d79bb8e9afd222e092c542f2f09594a7340e795847536b`|
|A原始选店消息|`p01-request-ba4001e91e574b488a7235a6b633b62e`|
|原W03事项|`matter:f07a2d2321e596f679a2a1436760c992400b359f14104f1c5b425df4b33be354`|
|原生Wake/ThinkSession来源|`native:95e20326-dace-519f-92c5-d64b6208c8b1`|
|B发送请求|`action-cap:dd4961dfc936a3d544230575999b0b2f8352b745fbaa4c006e536e7731e30615`|
|B用户回复|`p01-request-b3b02a04b6754bf9809cff2533b1924f`|
|Body动作|`action-cap:1c4347102e7dc43dfca2b90f21623a7cee642949e0c66d5c690140900e6c66fe`|
|临时连接清理|`action-cap:160778d614b68462578603190c0b89af97789fd0ec2494e747118dcdf8fcb793`|

断言从原始消息的最终Context中查到查询请求，原生接续通过原Thinking产生表达、E5-A保留投递回执；B回复后投递投影为ANSWER_RECORDED，同一事项/主体。Body动作造成模拟值2后进入原Perception，旧身体附件及错误代次被拒绝，工具清理为CLOSED。

发送时快照为SENT、送达/已读NO_EVIDENCE、UNANSWERED；这是该发送时点，不把随后回复倒写成原发送时已读。独立DeliveryEvidenceTests另测有效查询证据提升及失效拒绝。包级TEST实际成本：A 2，B 2，Body 1；是模拟账本单位，不是人民币或生产价格。相同请求恢复不追加费用的证据见正式回归，不从本页重复执行来证明。

对已构造的Engine服务可调用 `entries.inspect(original_request_id)`；要投影送达/已读，仅传已有、当前可读的指定查询请求 `evidence_requests=(query_id,)`。这两个只读入口不生成查询、不调用模型或派发。当前绑定/来源不可用仍拒绝，不能把历史查询副本当永久授权。P19完整页面未施工。
