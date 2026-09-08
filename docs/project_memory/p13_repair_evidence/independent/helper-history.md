# 独立复核辅助错误历史

首次 `probes-01`：6 项，3 FAIL、2 PASS、1 ERROR，3.351 秒。

ERROR 是规划侧探针误写 `f.core.router._sources`；实际成员是 `_bindings`。不是引擎错误。原 stdout/stderr/result 已保留。改正这一成员名，同时避免两次调用同一 retrieve；原四个反例的断言未弱化。另增加“执行前撤权应拒绝”的正向对照，并明确断言测试授权项存在且已被撤销。

后续结果使用新标签保存，不覆盖首次输出。
