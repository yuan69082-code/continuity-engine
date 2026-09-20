# 本轮辅助错误（不计为 Engine 行为缺陷）

- 只读查找中将 PowerShell 通配路径直接交给 rg，出现 Windows 123；若干按推测名称读取不存在文件（mind_cognition.py、dynamic_mind_cognition.py、approved_state_action.py 等）。改为真实文件索引，不修改代码或文件来掩盖。
- 一次读取 before.json 使用系统默认 GBK，UnicodeDecodeError；改为显式 UTF-8。
- 一次 apply_patch 未匹配 retain_pending 的具体代码上下文，补丁未生效；读取实际代码后按正确上下文应用。
- audit.py progress-01 首次启动，AST读取编码拼为 utf8-sig，LookupError: unknown encoding: utf8-sig。在audit.py main的源码读取处停止，无检查成功报告。改为标准 utf-8-sig；使用新标签progress-02。
- 新增正式测试中的字段、owner及TEST时钟/额度设置问题见 implementation-notes.md，各次实际测试原始 FAIL/ERROR 保留在对应标签的 JSON/stdout/stderr。

这些记录补足工具调用中的失败历史；不将工具输出读错、补丁不匹配或辅助编码错误计作运行时 Engine 缺陷。

- 续接只读CIM进程查询在沙箱内拒绝访问；未执行任何清理。顶层CHANGELOG.md读取路径不存在，实际位于docs/project_memory/CHANGELOG.md；没有修改文件，也不是Engine失败。

- 续接rg首次直接传Windows通配文件名失败（os error123），改用rg -g筛选后读取成功；属于只读辅助命令错误，不是行为测试。

- platform-before-01 / platform-after-01：新增TEST根前缀过长，深层NamedTemporaryFile触及Windows路径限制并抛FileNotFoundError；未触达目标行为。缩短为ap-后通过。空请求集合接口返回list，测试初稿tuple预期在下一次运行前据源码修正。另一次查找json_capability_repository.py路径不存在，实际方法在json_integration_repository.py；只读辅助错误，不修改存储。

- 交付脚本文案的一次apply_patch定位未匹配，未改文件；随后以唯一锚点补入真实全量失败说明。无运行源码或测试语义影响。

- progressive-01观察脚本使用不存在的host.status而非现有query，导致观察、异常诊断及STOP后的读取均AttributeError。STOP调用在最后一次错误读取之前。原完整异常链/失败Fixture保留；只修观察脚本并新标签progressive-02通过，Engine源码和正式测试无变化。另一次只读查询domain/runtime.py文件不存在，实际为persistent_runtime.py。

- 补充失败根的首次只读核对把runtime文件封装层当document，未找到version而未形成核对文件。随后按实际document封装读取，确认STOP/STOPPED、owner为空；无Engine状态修改，不能将此辅助检查误当成新的运行故障。
