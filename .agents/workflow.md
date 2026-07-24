# Continuity Engine 开发工作流程

每次执行开发任务时，遵循以下流程：

## 修改前

1. 阅读：
- README.md
- docs/project_memory/
- 当前相关源码

2. 确认：
- 当前项目阶段
- 已完成模块
- 未完成事项

不要重复建设已有能力。

---

## 修改过程中

要求：

1. 优先修改现有架构，不随意新增重复模块。
2. 不修改核心设计方向。
3. 涉及功能变化时，同步更新：
- docs/project_memory/
- CHANGELOG.md

---

## 修改完成后

必须执行：

1. 运行测试。

2. 检查：

git status

3. 汇报：

- 修改文件
- 修改原因
- 测试结果
- 当前剩余问题

---

## Git流程

完成修改并测试通过后：

生成清晰 commit 信息。

格式：

类型: 内容

例如：

feat: add engine api adapter

fix: repair storage compatibility

docs: update project memory

提交前等待用户确认。

用户确认后执行：

git add .
git commit
git push origin main

---

## 禁止

未经确认禁止：

- 大规模重构
- 删除已有模块
- 接入真实外部服务
- 修改项目路线
- 自动创建版本标签
## 工程档案同步

每次完成开发任务后，必须检查 docs/project_memory：

根据实际修改内容同步更新：

- 01_当前状态.md
- 03_施工日志.md
- 04_决策记录.md（如有架构决策）
- 05_已完成模块.md（如有模块完成）
- 06_未完成事项.md（如有状态变化）
- CHANGELOG.md（如有版本变化）

要求：
- 只记录实际已经完成的内容
- 不把计划写成完成
- 不修改未来规划方向