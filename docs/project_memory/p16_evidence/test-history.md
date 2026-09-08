# P16全部实跑记录与首次失败

每行run/PASS按测试方法计；FAIL/ERROR列是unittest原始记录条数，子用例可使记录条数多于失败方法数。时间为持久runner墙钟时间（包含发现），各stderr另有unittest计时。全部原件保留，不以新PASS覆盖旧结果。

| 标签/元数据 | run | PASS | FAIL记录 | ERROR记录 | SKIP | 秒 | exit | 原始输出 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| [provider-before](provider-before.json) | 5 | 0 | 0 | 5 | 0 | 0.784 | 1 | [stdout](provider-before.stdout.log) / [stderr](provider-before.stderr.log) |
| [provider-first](provider-first.json) | 5 | 3 | 1 | 5 | 0 | 4.313 | 1 | [stdout](provider-first.stdout.log) / [stderr](provider-first.stderr.log) |
| [provider-fixture-corrected](provider-fixture-corrected.json) | 5 | 4 | 1 | 0 | 0 | 8.357 | 1 | [stdout](provider-fixture-corrected.stdout.log) / [stderr](provider-fixture-corrected.stderr.log) |
| [provider-context-scope](provider-context-scope.json) | 5 | 4 | 1 | 0 | 0 | 14.911 | 1 | [stdout](provider-context-scope.stdout.log) / [stderr](provider-context-scope.stderr.log) |
| [provider-budget-separated](provider-budget-separated.json) | 6 | 6 | 0 | 0 | 0 | 15.772 | 0 | [stdout](provider-budget-separated.stdout.log) / [stderr](provider-budget-separated.stderr.log) |
| [recovery-context-first](recovery-context-first.json) | 21 | 17 | 0 | 7 | 0 | 21.816 | 1 | [stdout](recovery-context-first.stdout.log) / [stderr](recovery-context-first.stderr.log) |
| [recovery-context-closed](recovery-context-closed.json) | 21 | 21 | 0 | 0 | 0 | 20.818 | 0 | [stdout](recovery-context-closed.stdout.log) / [stderr](recovery-context-closed.stderr.log) |
| [binding-before](binding-before.json) | 2 | 0 | 2 | 0 | 0 | 2.508 | 1 | [stdout](binding-before.stdout.log) / [stderr](binding-before.stderr.log) |
| [binding-closed](binding-closed.json) | 2 | 1 | 0 | 1 | 0 | 2.465 | 1 | [stdout](binding-closed.stdout.log) / [stderr](binding-closed.stderr.log) |
| [bounded-first](bounded-first.json) | 32 | 32 | 0 | 0 | 0 | 42.053 | 0 | [stdout](bounded-first.stdout.log) / [stderr](bounded-first.stderr.log) |
| [lifecycle-golden-first](lifecycle-golden-first.json) | 3 | 0 | 1 | 3 | 0 | 4.163 | 1 | [stdout](lifecycle-golden-first.stdout.log) / [stderr](lifecycle-golden-first.stderr.log) |
| [lifecycle-golden-second](lifecycle-golden-second.json) | 3 | 1 | 1 | 1 | 0 | 3.999 | 1 | [stdout](lifecycle-golden-second.stdout.log) / [stderr](lifecycle-golden-second.stderr.log) |
| [lifecycle-golden-third](lifecycle-golden-third.json) | 3 | 2 | 0 | 1 | 0 | 11.840 | 1 | [stdout](lifecycle-golden-third.stdout.log) / [stderr](lifecycle-golden-third.stderr.log) |
| [credential-binding-before](credential-binding-before.json) | 1 | 0 | 1 | 0 | 0 | 1.339 | 1 | [stdout](credential-binding-before.stdout.log) / [stderr](credential-binding-before.stderr.log) |
| [expanded-first](expanded-first.json) | 44 | 42 | 1 | 8 | 0 | 70.557 | 1 | [stdout](expanded-first.stdout.log) / [stderr](expanded-first.stderr.log) |
| [root-dedup-before](root-dedup-before.json) | 1 | 0 | 1 | 0 | 0 | 4.813 | 1 | [stdout](root-dedup-before.stdout.log) / [stderr](root-dedup-before.stderr.log) |
| [root-lifecycle-closed](root-lifecycle-closed.json) | 6 | 6 | 0 | 0 | 0 | 14.393 | 0 | [stdout](root-lifecycle-closed.stdout.log) / [stderr](root-lifecycle-closed.stderr.log) |
| [integration-first](integration-first.json) | 5 | 4 | 1 | 0 | 0 | 11.030 | 1 | [stdout](integration-first.stdout.log) / [stderr](integration-first.stderr.log) |
| [p16-final](p16-final.json) | 53 | 53 | 0 | 0 | 0 | 86.849 | 0 | [stdout](p16-final.stdout.log) / [stderr](p16-final.stderr.log) |
| [compatibility-final](compatibility-final.json) | 538 | 537 | 0 | 0 | 1 | 362.200 | 0 | [stdout](compatibility-final.stdout.log) / [stderr](compatibility-final.stderr.log) |
| [full-final](full-final.json) | 1261 | 1260 | 0 | 0 | 1 | 1081.872 | 0 | [stdout](full-final.stdout.log) / [stderr](full-final.stderr.log) |

## 失败解释及处理

- provider-before：新P16 Fixture模块尚未实现，5个ModuleNotFoundError，保留实现前入口失败。
- provider-first：新TEST Thinking漏填should_wait/suggest_future_user_contact；新撤权断言曾过宽，随后绑定实际异常原因。均为辅助错误，未修改旧测试。
- provider-fixture-corrected：新Source使用小写权限scope，原Router明确拒绝；改为既有ENGINE_PRIVATE枚举值。
- provider-context-scope：768默认输入预算明确排除新材料，原规则正确；TEST正向显式1024并新增768排除对照，未改生产默认。
- recovery-context-first：新Trace被后续C1 trace覆盖、原事实恢复被当前消费权限拦住、新P01组件未登记；定点修复。历史回执拒绝通过原IntegrationExecutionError包装，新测试改查其精确cause，未弱化回执断言。
- binding-before：替换Connector描述可复用旧材料身份；cache的cached_at格式未校验。增加描述hash/version/capability精确绑定和时间校验。binding-closed仍有一个错误码包装ERROR，随后统一为EXTERNAL_STORE_CORRUPT。
- lifecycle-golden-first：新消费分支未区分主体非活跃与原事实恢复；已修复。Golden嵌套根过长触发Windows既有临时路径限制，使用独立浅层Temp根；保留完整子进程栈，不修改旧Awakening。
- lifecycle-golden-second：E5-A事实已经恢复，旧C1结果因合法暂停推进revision而拒绝过时摘要。新测试原本要求成功发布旧结果过窄；按现有完成契约分别断言SUCCEEDED事实、精确拒绝原因、无重复调用和新状态不变，未改Core完成契约。
- lifecycle-golden-third：新回归引用了不存在的action_planning属性，改为读取真实capabilities绑定；为辅助错误。三进程Golden该轮已实际通过。
- credential-binding-before：TEST Broker仅检查引用存在，未检查Connector归属；补精确映射和缺失/过期/跨主体对照。
- expanded-first：根去重测试初版把不同内容错误要求为一个赢家；保留不同内容共同根并新增相同事实包装的正式反例。路径测试抛出原SandboxOperationError而新测试期待错误类型，改查实际拒绝码并保持两入口零写入断言。
- root-dedup-before：相同根/内容/版本通过两个包装仍重复，复现后在P16 Source确定性去重；不同内容/不同根仍保留。
- integration-first：P01 Genesis本来含一条Learning候选，新测试错误期待空表；改为比较前后原记录完全一致，保留capture为空和SubjectState不变断言。
- 读取辅助错误：几次猜测文件名、PowerShell rg路径通配及77文档标题patch未匹配，未修改任何运行数据；随后按真实文件名继续。这些不是Engine测试结果。
- 历史P00—P15 FAIL/ERROR/SKIP、P09 segment 10 stderr缺失且根因UNKNOWN全部保留，未因P16通过改写。
- Windows symlink WinError 1314为原有权限SKIP，仍为SKIP；没有新增跳过项。
