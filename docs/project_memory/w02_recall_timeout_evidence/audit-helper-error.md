# 终局审计辅助编码错误（保留）

首次运行 `E:/Adobe/python.exe docs/project_memory/w02_recall_timeout_evidence/audit.py` 退出码为 0，打印的源码/保护/排除/清单检查均为通过，且生成了 `final.*` 三份原始文件。但它在 `git diff --check` 的 Python 文本捕获线程中使用主机默认 GBK 解码，遇中文路径提示产生 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position 66`。该线程异常不能被首轮退出码 0 掩盖；首轮结果及输出原样保留，不把它写成无告警审计。

已在审计辅助脚本中将该子进程输出解码明确指定 UTF-8，未改变运行实现、正式测试、差异检查规则或保护范围。使用独立 `verified-final.*` 标签重新执行相同终局核对，保留 `final.*` 首轮材料。另以 PowerShell 独立执行的 `git diff --check` 退出码为 0；Git 报告的 LF/CRLF 转换提示按原样记录，不是功能失败，也没有为消除提示改写历史文件。
