# full-final-01 有记录中断（不计通过或 Engine 失败）

`full-final-01.started.json` 显示固定源码/测试指纹 `sha256:0fb843ae12d8e0d54293e34bba8ec5aba8f34771adf5fbb0f4858f43c0077840`，本地 2026-09-25 01:21:57 开始 `E:/Adobe/python.exe -m unittest discover -s tests -q`。其时原输出尚无完成汇总。运行约 808.894 秒后，为补齐 W02-C 根证明自身跨 subject/environment 的正式隔离反例，施工方核对当时仅有的两个 Python 进程及启动时间与该运行相符，停止了本轮测试子进程 ID 17820；父运行器随后以 Windows 返回码 4294967295 结束，记录于 `full-final-01.json`。`stderr.log` 空，`stdout.log` 只有未完成片段，**不能**推定已运行数量、PASS 数量或 Engine 行为 FAIL。

停止前后该轮源码清单完全一致，正式数据、保护文件与排除材料一致。随后新增的正式边界用例使旧轮不再覆盖最终测试版本。原始 started/result/stdout/stderr 及 SHA-256 保留；下一次全量标签为 `full-final-02`，其后续状态另见[测试索引](test-index.md)，不以它倒改本条。
