# W04-3 原始测试索引

全部为施工方本轮实跑，集合交叠不相加。规划窗口尚未独立复核，也没有远端 CI 结果。旧1863项身份和原测试文件字节保持；新增46项。

| 集合 | PASS / FAIL / ERROR / SKIP | unittest秒 / runner秒 | exit |
|---|---|---|---|
| [targeted-final-02](targeted-final-02.json) | 46 / 0 / 0 / 0 | 155.642 / 156.263 | 0 |
| [special-final-02](special-final-02.json) | 87 / 0 / 0 / 0 | 161.742 / 162.382 | 0 |
| [compatibility-final-02](compatibility-final-02.json) | 417 / 0 / 0 / 0 | 697.07 / 697.779 | 0 |
| [full-final-01](full-final-01.json) | 1908 / 0 / 0 / 1 | 2184.956 / 2186.189 | 0 |

- [targeted-final-02 stdout](targeted-final-02.stdout.log)、[stderr](targeted-final-02.stderr.log)、[命令/退出码/耗时/前后完整源码](targeted-final-02.json)。

- [special-final-02 stdout](special-final-02.stdout.log)、[stderr](special-final-02.stderr.log)、[命令/退出码/耗时/前后完整源码](special-final-02.json)。

- [compatibility-final-02 stdout](compatibility-final-02.stdout.log)、[stderr](compatibility-final-02.stderr.log)、[命令/退出码/耗时/前后完整源码](compatibility-final-02.json)。

- [full-final-01 stdout](full-final-01.stdout.log)、[stderr](full-final-01.stderr.log)、[命令/退出码/耗时/前后完整源码](full-final-01.json)。

## 可复跑入口

仓库根使用 E:/Adobe/python.exe，设置 PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1，PYTHONPATH 包含仓库根、src、tests。

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='C:/Users/Administrator/Documents/continuity-engine;C:/Users/Administrator/Documents/continuity-engine/src;C:/Users/Administrator/Documents/continuity-engine/tests'
& 'E:/Adobe/python.exe' -m unittest -v tests.test_w04_3_tools
& 'E:/Adobe/python.exe' -m unittest discover -s tests -v
```

其他组精确模块及顺序见对应 JSON 的 command。若归档新结果，用 run.py 的新唯一标签；不得覆盖现有标签，也不要重执行 validate-final.py 冒充原实跑。

修前缺口与中间失败见 [调查记录](investigations.md)。其中 before-01 为缺能力取证；observe-before/after 为同一观察到期反例；frozen-source-01 是辅助导入错误，frozen-source-03 才是有效最终身份。旧版本 PASS 仅作为过程证据，不能代替本表。

完整回归唯一 SKIP 是原 Windows 创建符号链接 WinError1314。旧 FAIL/ERROR、诊断错误、中断、cProfile超时及历史 F1/H1/F2 UNKNOWN 全部保留，没有将其改写成 PASS。
