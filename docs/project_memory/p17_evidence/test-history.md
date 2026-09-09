# P17完整测试与失败历史

所有表项来自同名原始JSON。PASS为测试方法计数；FAIL/ERROR为unittest原始记录数，含subTest时不得与方法数简单相加。后续通过不覆盖首次失败。

| 标签 | 状态与结果 | 原始输出 |
|---|---|---|
| boundaries-first-01 | 16项：14 PASS、0 SKIP、4 FAIL记录、2 ERROR记录；27.851秒，退出码1 | [JSON](boundaries-first-01.json) / [stdout](boundaries-first-01.stdout.log) / [stderr](boundaries-first-01.stderr.log) |
| cancel-index-after-01 | 1项：1 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；1.668秒，退出码0 | [JSON](cancel-index-after-01.json) / [stdout](cancel-index-after-01.stdout.log) / [stderr](cancel-index-after-01.stderr.log) |
| cancel-index-before-01 | 1项：0 PASS、0 SKIP、1 FAIL记录、0 ERROR记录；1.752秒，退出码1 | [JSON](cancel-index-before-01.json) / [stdout](cancel-index-before-01.stdout.log) / [stderr](cancel-index-before-01.stderr.log) |
| compatibility-final-01 | 645项：644 PASS、1 SKIP、0 FAIL记录、0 ERROR记录；754.658秒，退出码0 | [JSON](compatibility-final-01.json) / [stdout](compatibility-final-01.stdout.log) / [stderr](compatibility-final-01.stderr.log) |
| context-binding-after-01 | 1项：1 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；3.308秒，退出码0 | [JSON](context-binding-after-01.json) / [stdout](context-binding-after-01.stdout.log) / [stderr](context-binding-after-01.stderr.log) |
| context-binding-before-01 | 1项：0 PASS、0 SKIP、1 FAIL记录、0 ERROR记录；3.609秒，退出码1 | [JSON](context-binding-before-01.json) / [stdout](context-binding-before-01.stdout.log) / [stderr](context-binding-before-01.stderr.log) |
| direct-planner-first-01 | 2项：0 PASS、0 SKIP、0 FAIL记录、2 ERROR记录；1.581秒，退出码1 | [JSON](direct-planner-first-01.json) / [stdout](direct-planner-first-01.stdout.log) / [stderr](direct-planner-first-01.stderr.log) |
| direct-planner-fourth-01 | 2项：2 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；2.258秒，退出码0 | [JSON](direct-planner-fourth-01.json) / [stdout](direct-planner-fourth-01.stdout.log) / [stderr](direct-planner-fourth-01.stderr.log) |
| direct-planner-second-01 | 2项：0 PASS、0 SKIP、0 FAIL记录、2 ERROR记录；2.145秒，退出码1 | [JSON](direct-planner-second-01.json) / [stdout](direct-planner-second-01.stdout.log) / [stderr](direct-planner-second-01.stderr.log) |
| direct-planner-third-01 | 2项：0 PASS、0 SKIP、2 FAIL记录、0 ERROR记录；2.174秒，退出码1 | [JSON](direct-planner-third-01.json) / [stdout](direct-planner-third-01.stdout.log) / [stderr](direct-planner-third-01.stderr.log) |
| execution-recovery-first-01 | 33项：32 PASS、0 SKIP、1 FAIL记录、0 ERROR记录；31.457秒，退出码1 | [JSON](execution-recovery-first-01.json) / [stdout](execution-recovery-first-01.stdout.log) / [stderr](execution-recovery-first-01.stderr.log) |
| expanded-first-01 | 56项：56 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；67.846秒，退出码0 | [JSON](expanded-first-01.json) / [stdout](expanded-first-01.stdout.log) / [stderr](expanded-first-01.stderr.log) |
| full-final-01 | 1344项：1343 PASS、1 SKIP、0 FAIL记录、0 ERROR记录；1035.059秒，退出码0 | [JSON](full-final-01.json) / [stdout](full-final-01.stdout.log) / [stderr](full-final-01.stderr.log) |
| full-final-02 | 1348项：1347 PASS、1 SKIP、0 FAIL记录、0 ERROR记录；1100.490秒，退出码0 | [JSON](full-final-02.json) / [stdout](full-final-02.stdout.log) / [stderr](full-final-02.stderr.log) |
| late-boundary-formal-after-01 | 4项：4 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；5.944秒，退出码0 | [JSON](late-boundary-formal-after-01.json) / [stdout](late-boundary-formal-after-01.stdout.log) / [stderr](late-boundary-formal-after-01.stderr.log) |
| late-boundary-formal-before-01 | 3项：0 PASS、0 SKIP、5 FAIL记录、0 ERROR记录；5.419秒，退出码1 | [JSON](late-boundary-formal-before-01.json) / [stdout](late-boundary-formal-before-01.stdout.log) / [stderr](late-boundary-formal-before-01.stderr.log) |
| p17-final-01 | 57项：57 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；70.802秒，退出码0 | [JSON](p17-final-01.json) / [stdout](p17-final-01.stdout.log) / [stderr](p17-final-01.stderr.log) |
| p17-final-02 | 58项：58 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；76.180秒，退出码0 | [JSON](p17-final-02.json) / [stdout](p17-final-02.stdout.log) / [stderr](p17-final-02.stderr.log) |
| p17-final-03 | 62项：62 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；76.336秒，退出码0 | [JSON](p17-final-03.json) / [stdout](p17-final-03.stdout.log) / [stderr](p17-final-03.stderr.log) |
| p17-second-01 | 49项：49 PASS、0 SKIP、0 FAIL记录、0 ERROR记录；60.370秒，退出码0 | [JSON](p17-second-01.json) / [stdout](p17-second-01.stdout.log) / [stderr](p17-second-01.stderr.log) |
| requirements-before-01 | 2项：0 PASS、0 SKIP、0 FAIL记录、2 ERROR记录；0.720秒，退出码1 | [JSON](requirements-before-01.json) / [stdout](requirements-before-01.stdout.log) / [stderr](requirements-before-01.stderr.log) |

原因说明：requirements-before-01是新增模块尚未实现；direct-planner-first-01为P17新接线UTC格式不匹配；second/third为新增测试返回类型/大小写辅助错误。
execution-recovery-first-01首次发现无link补偿能执行；boundaries-first-01含拒绝原因混同四个subTest FAIL及两个生命周期Fixture误用ERROR。context-binding-before-01、cancel-index-before-01分别固化旧请求重绑新Context、取消索引丢失后重派发。对应after及最终专项保留通过证据。
末次审计发现两项P17缺口：固定+1024字节估算不足，实际世界文件可能超限；只用adapter_id绑定允许接入其他主体的TEST Adapter。late-boundary-formal-before-01为3方法失败（含多个subTest），修后4方法通过；并增加精确限额正向对照。按实际完整序列化字节预检，核实Adapter的subject/environment/world/version和世界文件绑定，原探针无需弱化即通过。
辅助读取路径/glob错误见[原记录](auxiliary-read-errors.log)，接线诊断见[原输出](direct-diagnostic-01.log)。这些不是旧阶段缺陷。历史P16八处格式告警和P09 segment10 UNKNOWN不改写。

## 原始边界探针（不与正式测试数量相加）

| 标签 | 退出码 / 秒 | 原始证据 |
|---|---|---|
| storage-probe-before-01 | 1 / 1.020 | [JSON](storage-probe-before-01.json) / [stdout](storage-probe-before-01.stdout.log) / [stderr](storage-probe-before-01.stderr.log) |
| storage-probe-before-02 | 1 / 1.868 | [JSON](storage-probe-before-02.json) / [stdout](storage-probe-before-02.stdout.log) / [stderr](storage-probe-before-02.stderr.log) |
| storage-probe-after-01 | 0 / 1.469 | [JSON](storage-probe-after-01.json) / [stdout](storage-probe-after-01.stdout.log) / [stderr](storage-probe-after-01.stderr.log) |
| adapter-binding-before-01 | 1 / 1.879 | [JSON](adapter-binding-before-01.json) / [stdout](adapter-binding-before-01.stdout.log) / [stderr](adapter-binding-before-01.stderr.log) |
| adapter-binding-after-01 | 0 / 1.669 | [JSON](adapter-binding-after-01.json) / [stdout](adapter-binding-after-01.stdout.log) / [stderr](adapter-binding-after-01.stderr.log) |

storage-probe-before-01在长Temp路径下出现FileNotFoundError，未到目标断言，仅为辅助运行错误，不作为存储缺陷证据；原脚本和原输出保留。短路径before-02实际复现超限；adapter-binding-before-01实际复现跨主体TEST写入。
[补修前源码存档清单](late-boundary-source-before.json)对应full-final-01；此轮全量1344项中1343 PASS、1既有SKIP不覆盖随后发现的新反例，也不是最终源码的全量结果。645项兼容源码与终局仅上述四个P17新增文件有差异，全部原模块不变，最终全量再次包含其全部645身份。
