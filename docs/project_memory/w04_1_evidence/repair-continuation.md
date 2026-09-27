# W04-1 N09/N10 定点返修续接记录

2026-09-27；用户只授权 W04-1 迁移绑定、输出能力时效、传感值契约及对应测试/档案。状态仍为 `IMPLEMENTED_NOT_ACCEPTED`；不验收、不执行 Git 写操作、不进入 W04-2。

开工核对 `main`、HEAD `546fb25db0f1e248c703db855ee754234ce59458`、暂存区空；既有 310 项源码/测试/资源指纹为 `sha256:166dc0fcd1404560b7dff5af2bb253e751b5d5051e78484413a60f27bfb02824`。W04-1 原交付 66 项和 D-085 前置 20 项规划档案保留，57 项原排除材料按既有规则保护；不清理历史证据。

先新增正式反例并运行 `w04-r1-before-01`：4 个测试方法中 8 FAIL、3 ERROR。首轮行动夹具因 Windows 临时路径过长出现辅助 ERROR，原样保留；缩短隔离目录前缀及去除前一失败对子用例的状态干扰后，`w04-r1-before-02` 仍按原正式入口得到 9 FAIL、2 ERROR。修前来源指纹分别在同名 JSON 中。

实现仅修改 `domain/environment_access.py` 和 `services/environment_access_service.py`：准备单状态与类别/缺项一致，隔离交接前绑定当前主体和环境；P17 行动门禁检查具体输出能力期限；传感读数拒绝非有限值、布尔及非数值类型。新增回归在 `tests/test_w04_1_environment.py`。`w04-r1-targeted-01` 28 项中 27 PASS、1 ERROR：正式入站将能力拒绝包裹为原 `IntegrationExecutionError`，测试最初误断言顶层为内部错误，原记录保留。调整测试核对静态 `__cause__` 后 `w04-r1-targeted-02` 29 PASS，13.709 秒、退出 0，前后源码同为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`。

`w04-r1-compat-final-01` 已完成 182 PASS、290.358 秒、退出 0，运行前后指纹均为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`。`w04-r1-full-final-01` 因用户要求临时暂停而中断，没有 `unittest` 最终汇总；其运行器退出码不能当全量 PASS 或 Engine 行为 FAIL。进程、哈希、已完成/未完成及下一次恢复入口见[暂停记录](repair-pause-01.md)。**当前停止，不启动新测试或修改。**

## 2026-09-27 获用户明确恢复授权后的现场

暂停记录和四份中断原件 hash 复核一致；`main`、HEAD `546fb25db0f1e248c703db855ee754234ce59458`、暂存区空，310 项源码/测试/资源指纹仍为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`。无 Python 测试进程，Git 工作区无清单外路径；63 项保护、七份正式数据、三份现行规划未变，原 57 项排除材料只含 D-085 已授权的索引变化。已完成专项与兼容 JSON 均记录退出 0 和相同的前后指纹。

只补跑新标签 `w04-r1-full-resume-01` 的 `unittest discover -s tests -v`，旧中断标签不覆盖、不计 PASS。新全量完成前只记 `STARTED`；其后再按真实结果同步终局施工日志、矩阵、审计及精确清单。

## 新标签全量实际结束

`w04-r1-full-resume-01` 已完成，退出 0、运行器耗时 1876.171 秒；`unittest` 汇总 1802 项中 1801 PASS、1 原 Windows symlink 1314 SKIP、0 FAIL/ERROR。运行前后源码指纹均为 `sha256:4660952c9a4243db1928b706a4b2e73885122715815733eefc4a84efd531ec6c`，无剩余 Python 测试进程。暂停前 `w04-r1-full-final-01` 继续只标 `INTERRUPTED`，它的 JSON/日志和[暂停记录](repair-pause-01.md)不被覆盖。现只补档案、审计和清单，仍待独立复核，不进行 Git 写入或 W04-2。
