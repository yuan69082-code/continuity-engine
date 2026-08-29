# P02 Provider 配置、预算与失败语义

> 本文件记录 P02 Engine 本地 Fake Provider 验收配置。它不是供应商 SDK、真实价格表、密钥配置或 P22 生产 Adapter。

## 1. 当前验收 Profile

| 项目 | 值 | 边界 |
|---|---|---|
| 逻辑 Provider | `Alibaba Cloud Model Studio` | 元数据可替换；未连接供应商 |
| 逻辑 Model | `qwen-flash-2025-07-28` | Fake Provider Profile；不是实际模型调用 |
| Profile version | `1` | 持久化到 execution record |
| 单次 Token 上限 | `1024` | Provider request 硬上限 |
| 每日 Token 上限 | `10240` | 按持久化成功 usage 的 UTC 日期聚合 |
| 成功 test-credit | `1` | 合成测试单位，不代表货币或供应商价格 |
| fallback | disabled | 不允许静默切换 Provider/Model |
| Vio dependency | `NONE` | 不读取 Vio 路由、账本或配置 |
| real usage/cost | `DEFERRED_TO_P22` | P02 不产生真实 usage/cost |

Profile 必须显式启用并由 ID 选择；缺失、禁用或意外开启 fallback 时失败关闭。Provider/Model 名称属于选择结果和审计元数据，不构成 Subject 身份，也不得硬编码为 Engine 永久唯一供应商。

## 2. usage、test-credit 与幂等

每个成功且唯一的 Fake execution 产生一条 `ModelUsageEntry`，保存 capabilityRequestId、executionId、attemptId、Provider/Model、UTC usage day、input/output/total tokens、1 test-credit、recordedAt、`synthetic=true` 以及 P22 延后标记。

- 执行前拒绝：0 execution、0 usage、0 credit。
- 成功但调用方丢失响应：复用原 Provider fact、usage、credit、CapabilityResult 和 Engine completed result。
- 同 requestId/hash 重放：不新增 execution、credit、Thinking、Action 或主体结果。
- Provider 查询原结果：不新增 credit。
- 成功事实超过单次或每日上限：失败关闭，不能进入 Engine 主体结果。
- 每日已用额度达到上限：在 Provider 调用前生成 `RESOURCE_EXHAUSTED / never`，Provider execution 为 0。

幂等计数必须从 `model-execution-ledger.p02-v1.json` 的 execution/usage 事实读取，Fake Provider 内存计数不是验收权威。

## 3. 失败与查询语义

| Provider fact | Capability status | errorCode | retryClass | 是否可直接重试 |
|---|---|---|---|---|
| `SUCCEEDED` | `SUCCEEDED` | null | null | 不适用；精确重放 |
| `GENERATION_FAILED` | `FAILED_TERMINAL` | `GENERATION_FAILED` | `never` | 否 |
| `NETWORK_FAILED` | `FAILED_RETRYABLE` | `NETWORK_FAILED` | `retry` | 仅显式 retry |
| `RESOURCE_EXHAUSTED` | `FAILED_TERMINAL` | `RESOURCE_EXHAUSTED` | `never` | 否 |
| `TIMEOUT` | `UNKNOWN` | `TIMEOUT` | `query` | 否；先查询原 execution |
| `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `query` | 否；无法确认时保持 UNKNOWN |
| `FAILED_RETRYABLE` | `FAILED_RETRYABLE` | Provider 受控错误 | `retry` | 仅显式 retry |
| `FAILED_TERMINAL` | `FAILED_TERMINAL` | Provider 受控错误 | `never` | 否 |
| `CANCELLED` | `CANCELLED` | `CANCELLED` | `never` | 否 |
| `EXPIRED` | `EXPIRED` | `EXPIRED` | `never` | 否 |

`UNKNOWN` 不允许盲目重试。恢复先以已持久化 attempt identity 查询 Provider；找到原结果则补写 Engine execution fact，明确未执行才可能进入受控 retry，仍无法确认则维持 UNKNOWN。所有失败都不修改 SubjectState。

## 4. 冻结兼容字段

冻结 CapabilityResult Schema 的 `vioLedgerEntryId` 不变。P02 使用 `engine-p02-test-ledger-*` 确定性兼容值，不宣称 Vio 参与。真实 Provider usage、费用、凭据和账单权威均后置到 P22。
