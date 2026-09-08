# 开工只读辅助错误

2026-09-08：首次读取误猜了不存在的 domain/subject_state.py、services/evolution_service.py、services/context_ports.py、domain/permission.py 路径。命令返回路径不存在；随后通过 rg 定位 domain/models.py、services/subject_state_service.py、services/action_evolution_service.py、services/context_router_service.py、domain/permissions.py。属于本轮导航辅助错误，没有运行测试，也不是 Engine 回归失败。两次批量读取输出被截断，随后按规划段号和源码范围补读；不将被截断输出冒充完整读取。

恢复施工中的导航辅助错误另保留在本段：误猜 testing/runtime.py、testing/adapters.py、storage/json_action_repository.py、tests/test_p09_core_recovery.py、tests/test_p12_context_learning.py；Windows 下把 tests/test_p13*、testing/p09*、testing/*.py 通配符直接作为 rg 文件参数导致路径语法错误。随后用真实路径/rg --files 定位，没有对缺失路径写入或把这些错误计作 Engine 测试失败。多次输出超预算后按具体范围、错误段和结构化字段重读；历史大输出不是完整读取证据。

前轮仅核对 Git 时，一次只读 ls-remote 的 schannel SEC_E_NO_CREDENTIALS 失败；按当时用户 Git 核对授权在可用环境查询同一远端成功。没有新提交。本次恢复 P14 没有 Git 写操作或生产网络调用。

收尾静态检查首调误写 Python encoding='utf8-sig'，真实抛出 `LookupError: unknown encoding: utf8-sig`，发生在读取文件阶段，AST 和 diff 检查尚未完成。审计脚本与命令改为合法的 `utf-8-sig` 后重新检查。这是审计辅助错误，不是全量测试失败；没有修改运行代码或原测试。
