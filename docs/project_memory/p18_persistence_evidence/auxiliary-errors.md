# 本轮辅助错误及失败尝试（不覆盖原件）

- 首次Native定点 `native-before-01` 5项中4 FAIL；其中3项由于新TEST临时根前缀过长，Windows路径达到260导致临时文件创建FileNotFoundError/errno2。`aux-smoke-01`—`04` 保存逐步定位。只将本轮新测试前缀改为`ps18-`，未改产品路径、旧测试、超时或保护规则。随后 `native-before-02` 得到有效3 PASS/2 FAIL。不能将这3个辅助失败冒称Engine已发生的持久化缺陷。
- 共享DELETE读取尝试没有解决当前环境的replace拒绝；`reader-after-01`仍2 FAIL，`win-share-01.log`、`win-share-02.log`保留API实验。尝试代码已从当前实现中移除，旧输出未动。
- 新增重开恢复测试先假设usage只有2条，实际3条；`formal-after-02` 13 PASS/1 FAIL。改为比较原usage后，`formal-final-01`仍13 PASS/1 FAIL：错误地要求未结算记录在合法恢复后逐字不变。现依据原资源契约明确比较稳定usage身份、原预留金额及Thinking实际结算None→256，token总量320不变；不修改ResourceManager、usage历史或原测试断言。`formal-final-02` 14 PASS。两个辅助假设失败完整保留，不能冒称新Engine缺陷，也不能为了忽略它们删除日志。
- 若干只读检索曾命中不存在的猜测路径，属于工具路径错误；未改文件或据此认定Engine失败。长日志工具输出发生显示截断，但磁盘原始stdout/stderr及JSON完整保留，最终审计按文件读取。
- 原F2/F1/H1、R1/R2、P09 segment10 UNKNOWN、WinError1314 SKIP和更早工具错误均保持历史。当前通过不覆盖首次失败。

具体测试身份、失败断言、运行源码及耗时以各唯一标签JSON/stdout/stderr为准。定点反例允许明确合成的错误文字作为TEST证据；新增运行时诊断不输出任意异常原文或repr。
