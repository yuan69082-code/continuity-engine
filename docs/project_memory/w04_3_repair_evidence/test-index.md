# W04-3 R1/R2 原始测试索引

以下为施工方本轮实跑，集合交叠不相加；规划窗口此前是静态复核，不是独立实跑。没有远端CI结果。

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-01](targeted-final-01.json) | 14 / 0 / 0 / 0 | 166.421 / 167.125 | 0 |
| [w04-3-final-01](w04-3-final-01.json) | 60 / 0 / 0 / 0 | 324.797 / 325.487 | 0 |
| [w04-12-final-01](w04-12-final-01.json) | 87 / 0 / 0 / 0 | 159.335 / 160.0 | 0 |
| [compatibility-final-01](compatibility-final-01.json) | 417 / 0 / 0 / 0 | 701.162 / 701.916 | 0 |
| [full-final-01](full-final-01.json) | 1922 / 0 / 0 / 1 | 2390.489 / 2391.61 | 0 |

全部最终集合绑定321个源码/测试/资源文件 `sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506`；正式身份1923=原1909+新增14。原测试文件字节及身份完全保留。

- [targeted-final-01命令/退出码/耗时/前后清单](targeted-final-01.json)、[stdout](targeted-final-01.stdout.log)、[stderr](targeted-final-01.stderr.log)。

- [w04-3-final-01命令/退出码/耗时/前后清单](w04-3-final-01.json)、[stdout](w04-3-final-01.stdout.log)、[stderr](w04-3-final-01.stderr.log)。

- [w04-12-final-01命令/退出码/耗时/前后清单](w04-12-final-01.json)、[stdout](w04-12-final-01.stdout.log)、[stderr](w04-12-final-01.stderr.log)。

- [compatibility-final-01命令/退出码/耗时/前后清单](compatibility-final-01.json)、[stdout](compatibility-final-01.stdout.log)、[stderr](compatibility-final-01.stderr.log)。

- [full-final-01命令/退出码/耗时/前后清单](full-final-01.json)、[stdout](full-final-01.stdout.log)、[stderr](full-final-01.stderr.log)。

## 历史与复跑

[test-history.json](test-history.json)逐次保留修前、修后、辅助错误及旧版本结果。before-02是两个有效修前FAIL；before-01含辅助夹具ERROR，不冒充同等证据。各次解释见[investigations.md](investigations.md)。这些记录不被最终通过覆盖。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine;C:/Users/Administrator/Documents/continuity-engine/src;C:/Users/Administrator/Documents/continuity-engine/tests'
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_repairs
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_tools tests.test_w04_3_repairs
& 'E:/Adobe/python.exe' -m unittest discover -s tests -v
```

其余组精确模块及顺序见对应JSON.command；保存新复跑时可用run.py加未使用标签，再跟同样参数。不得复用/覆盖本轮标签。最终全量仅运行一次。Windows1314 SKIP仍为SKIP，不算PASS。
