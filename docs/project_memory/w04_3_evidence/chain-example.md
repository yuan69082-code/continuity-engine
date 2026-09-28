# 实际链路样例与只读入口

本页只摘录 example-final-01 的真实隔离运行，不预填主体结果。命令、exit0、24.271秒、前后指纹见[运行记录](example-final-01.json)；完整身份/回执hash/上下文来源见[原始输出](example-final-01.stdout.log)。这不是额外正式测试数量。

## 缺登录后继续同一任务

- 主体 `sub-523f8c5f099e451b`，环境 TEST。
- 原始信息请求 `p01-request-c07a2453616f4c43ac3a8cd1aa40df7f` → P16发现请求 `action-cap:85b72dee959ccb2f0215722d7c88f270b4be4765e6eed4cffae69b75eaf17f2e`。
- 候选来源 `offer:one`，hash `sha256:f50f3e290aa3eb27735fcffb896ae91383f2dff862005eb7406e4472e3eb5b1c`，未预先登记为可调用。
- 原连接请求 `action-cap:405198f86c827f3c1b5113557159340ac5e8af8760d334d21532e56c7b5fe1e4`，用途 `history.lookup`，范围 `device:read`。
- 缺项为 `['LOGIN']`，状态 `WAITING_CONDITIONS`；补齐当前登录条件后仍用该连接身份，验证、实际模拟type动作、清理。
- 最终 `CLOSED`，再续接仍 `CLOSED`；实际业务效果 1、TEST credits 1，发现调用 1，revision 1。没有重复连接或业务。

| 操作 | 原请求 | 回执hash / 结果 |
|---|---|---|
| connect | `action-cap:405198f86c827f3c1b5113557159340ac5e8af8760d334d21532e56c7b5fe1e4` | `sha256:957bc11c30bdc8a8d4a14276911af0f293164389c4d789b0e4ee57899f65a7ef` / CONNECTED |
| verify | `action-cap:c5cd08eee593447b7af074a321da38e851739f9174a8356a70f8870380fd0e43` | `sha256:fd339341a4ce9dfd5c1038c4aeeb786af854aed2102fc73238467f76a3689715` / VERIFIED |
| close | `action-cap:1c17c6ab5194d86c158c8ca2ebf79eef1fa0382ad255dd1957967b00de311b36` | `sha256:8490c4a54687b43cb9704fafd7dded9345b598bf1e9ab3662ba8142d2b66c265` / CLOSED |
| device.type | `action-cap:4f8264f18f890d824a606f257aeaf070cb1d5a07d86d6589b6c78ed01a2c40bb` | `sha256:a0dc84a6158cd8b5f46f4aa2669a01e8e7b0c7ba08f6ece50df147b5131bff5e` / SUCCEEDED |

## N21局部历史查询

另一个隔离同构场景，接入原查询能力后，实际query请求 `action-cap:33acc001d4cab1e2f5227f618c9537dcea593cef3521e47741b07ca800098449`；原Router/Composer组成Context `sha256:b5921fa88358fa7701d114b8b56b138aa04c114f1bbd3a9911006d4e2c6aa6fa`，其中选中 `execution:action-cap:33acc001d4cab1e2f5227f618c9537dcea593cef3521e47741b07ca800098449` 的原结果来源。该查询效果 0、TEST credits 0。来源清单在原始输出中；2048原预算未改。

## 最小只读查看

已有绑定宿主可调用 `TemporaryToolService.inspect(connection_request_id)`。返回E5_A_FACT_PROJECTION：当前状态、缺项、期限、原请求/回执引用、使用结果、待清理原因。入口前后均检查查看权限；不调用模型、执行/清理、登记Attachment、学习或推进revision。不能将这条只读API说成P19完整页面。

复跑整个样例会创建隔离TEST业务；只想查已有状态时仅调用inspect，不重新运行发现/advance。原始三进程恢复及重放记录另见[targeted-final-02 stdout](targeted-final-02.stdout.log)：prepare→UNKNOWN但连接已发生，resume→CLOSED，replay仍一次效果/费用，无新发现/模型。真实跨进程退出码均0。
