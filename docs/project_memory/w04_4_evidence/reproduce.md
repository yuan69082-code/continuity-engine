# W04-4 验证复跑入口

本页只是复核说明，没有启动额外测试。当前完整结果以 [test-index.md](test-index.md) 和各组原始 JSON 为准；不同集合不能相加。

四组最终命令分别保存在 targeted-final-02.json、w04-final-02.json、public-final-02.json、full-final-02.json 的 `command`。同文件记录工作目录、开始时间、退出码、耗时和运行前后源码。原环境及配置见 [环境记录](validation-environment-20261001.json)，固定版本和测试身份见 [frozen-source-final-02.json](frozen-source-final-02.json)。

需要复跑时，先检查源码仍对应目标证据，再选一个从未使用的新标签。下面以定向组为例，不会重跑另外三组：

```powershell
Set-Location -LiteralPath 'C:/Users/Administrator/Documents/continuity-engine'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$record = Get-Content -LiteralPath 'docs/project_memory/w04_4_evidence/targeted-final-02.json' -Raw | ConvertFrom-Json
$testArgs = @($record.command | Select-Object -Skip 1)
& 'E:/Adobe/python.exe' 'docs/project_memory/w04_4_evidence/run.py' 'review-targeted-01' @testArgs
```

`review-targeted-01` 只是示例；已存在时必须另选，不能删除或覆盖原文件。运行器自身拒绝重复标签，设置原 ROOT/src/tests 导入环境，并为所选组保存新 JSON、stdout 和 stderr。它的超时只约束测试控制器，不是 Engine 产品运行期限。

复核其他组时，选择对应 JSON 并给新标签，保留其完整命令参数和原负载。不要直接再次运行已经完成的 verification-sequence-02.py；它用于本轮固定顺序的一次验证，不能靠清除旧标签重启。诊断脚本和正式测试分开，轻量计时、重度剖析及包装程序退出码均不能代替 unittest 的完成汇总。

局部失败或测试中断时先保留诊断和进程身份，再处理本轮自建进程；不清理无关进程或历史证据。未完成的一轮不得记为 PASS。
