# 首次验收审计辅助错误保留

2026-09-25，首次运行本目录 `final_audit.py` 退出码 1。脚本在写出 `final.audit.json`、`final.files.json`、`final.pending-files.md` **之前**要求这三个未来生成的文件已经出现在 Git 工作区，因而把它们列为 `status_missing`，触发 `W02_ACCEPTANCE_AUDIT_FAILED`。当次输出同时显示：实际远端与开工 SHA 相同、源码 297 项及指纹正确、63 项保护/三份规划/正式七文件/57 项排除材料不变、四组测试固定同一源码、AST/链接/敏感内容/`git diff --check` 无阻断。该失败是验收审计辅助脚本的生成顺序错误，不是 Engine 测试失败或交付文件缺失。

已将首轮预写检查调整为允许**仅这三个明确生成输出**尚不存在；输出写成后仍计入最终精确提交路径。首轮原始 stderr 与完整 JSON 打印保留在本任务的工具执行记录中；不将其改写为 PASS。修改后的审计再次运行的真实结果以本目录 `final.audit.json` 为准。
