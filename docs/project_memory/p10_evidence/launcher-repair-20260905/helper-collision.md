# Git 收据索引命名冲突（保留首次辅助错误）

本地流水线通过后，repair-stage、repair-commit、repair-push 均 exit 0。
`run('repair-commit', ...)` 已将真实提交命令证据保存为 repair-commit.json。
随后的最终提交摘要也尝试用独占创建方式写入同名文件，发生：

```
FileExistsError: [Errno 17] File exists:
C:\Users\Administrator\Documents\continuity-engine\docs\project_memory\p10_evidence\launcher-repair-20260905\repair-commit.json
```

错误发生在 advance.py 的 write('repair-commit.json', ...) 处，提交与推送已成功。
没有覆盖原提交命令证据，没有重跑 Git 操作。只将摘要名改为 published-repair.json，
随后只读核实 HEAD、父提交、真实远端、两文件清单和经过本地回归的 hash 后补录。
这是本轮工程证据脚本局部错误，不是 Core 回归、来源或冻结边界失败。
