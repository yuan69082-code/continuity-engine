# 只读工具辅助错误补记

本文件是工具回执摘录和归类，不是Engine测试stderr，也不补造测试退出码。

- 读取候选但不存在的测试路径 `tests/test_w04_4_materials.py`、`tests/test_w04_4_native.py`：`系统找不到指定的文件。 (os error 2)`。
- 读取候选 `src/continuity_engine/services/core_context_service.py`：`Cannot find path ... because it does not exist.`；随后从实际 `continuity_core_service.py` 定义定位。
- 读取候选 `src/continuity_engine/testing/w04_simulation_fixture.py`：`系统找不到指定的文件。 (os error 2)`。
- Windows rg直接接收 `services/learning*` 等路径通配符：`文件名、目录名或卷标语法不正确。 (os error 123)`；随后使用实际目录及 `-g` 过滤读取。以上没有修改文件、没有运行Engine，不计Engine FAIL。
- 之前的PowerShell辅助引号ParserError、沙箱进程查询拒绝及新夹具问题详见repair-progress。其测试原始输出/运行JSON各自保留，未覆盖旧标签。
- Git只读差异枚举提示文本下次Git处理时LF会转为CRLF；本轮没有Git写操作，没有据此改写日志或规范化原件。最终差异检查实际输出另存。
