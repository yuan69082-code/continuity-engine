# 2026-10-01 验证续接期间的辅助检查记录

以下不是Engine功能测试，不能计为PASS或FAIL测试项。原工具输出保留在本会话，本文保存可识别的命令、实际错误和后续处理；不据此推断引擎故障。

1. 读取targeted-final-01日志后，以 `Get-CimInstance Win32_Process` 只读查看Python进程详情，被系统拒绝。组合检查的实际退出码1；错误正文为 `Get-CimInstance ... 拒绝访问`。没有提高权限、杀进程或重新启动测试。随后成功接回已有exec会话35647，并用 `Get-Process python` 的进程ID、启动时间、CPU及原日志核验它仍运行；最终该原测试正常退出0、49项通过。进程查询失败不改写原测试结果。

2. `rg '^    def test_' tests/test_w04_4*` 在Windows原生参数传递下没有展开路径通配符，报 `IO error ... 文件名、目录名或卷标语法不正确。 (os error 123)`。这是查找命令路径问题；123是错误正文中的系统错误号，未单独记录rg退出码，不能编造其退出码。该组合调用的其他文档读取正常，外层最终退出0不代表此搜索成功。后改为 `rg '^    def test_' tests -g 'test_w04_4*.py'`，获得实际测试方法；未修改任何测试。

3. 验证归档工具只做AST语法核查；当时build-final-docs.py尚未执行，不把“语法正常”写成“交付已完成”。实际生成、审计及最终运行结果分别以对应输出为准。

Git读取曾提示工作副本文本LF以后会被转换为CRLF；本轮不进行Git写操作，不为消除提示改写历史日志。最终差异提示另存final.diff-check.stdout.log与stderr.log。

4. 首次全量失败续查时，读取过不存在的候选路径package-reply-stations.py（实际带-01后缀）、domain/fixture_paths.py、infrastructure目录、test_w04_1_repair.py及旧证据final-report.md（实际为report.md）；PowerShell/rg报路径不存在。另有package-causal-*.json及test_w04_1*.py作为字面参数导致rg OS123。随后按实际文件列表读取，未创建假文件或将这些工具错误算作Engine缺陷。无Python时Get-Process -ErrorAction SilentlyContinue导致组合命令退出1，这不代表已结束的测试失败，测试退出码始终读取各运行记录。

5. full-errors-repair-01中新增两个正式TEST的错误是异常断言层级写错：正式C1入口按原逻辑包装为IntegrationExecutionError，原因链分别保留W04_STORE_LINK_FORBIDDEN与WinError5。只修本批新增测试，补上外层/原原因/零提交/零效果断言，guards-02通过；旧日志和旧1923项测试原样保留。
