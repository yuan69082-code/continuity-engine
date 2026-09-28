# 同一宿主的可追溯样例

数据从[targeted-final-01.stdout.log](targeted-final-01.stdout.log)按字段摘录，非预填结果：[请求、任务、步骤及回执hash](chain-example.json)。

- R1-native-and-tools：首工具LOGIN等待；第二工具沿原已接入事实完成一次业务和清理。真实native认知1次、revision=2、原维护任务完成，模拟业务效果1/费用1 TEST credit。新use/close有当前Context，旧connect未重绑。
- R1-mixed-waits：一个连接仍PARTIAL待清理，一个缺依赖，后面可执行连接完成；业务效果1/费用1。等待项仍如实等待，没有将失败改成功。
- R1-UNKNOWN：首连接结果仍UNKNOWN，没有创建其模拟连接；后一连接完成效果1/费用1。未知原请求未盲重放。
- R2-before-stop：原连接保留三份FAILED清理回执，条件恢复后第四份清理CLOSED，旧请求及回执不丢失，模型0、业务效果0、费用0。其他自动PARTIAL/重开与退避验证见正式测试。

本机TEST的连接/验证/清理费用为0，业务动作1 TEST credit；沿原回执/资源核验，不是现实预算或任意Provider成本保证。只读状态可从原inspect查看投影，查看不是Scheduler.query恢复调用，不执行业务。
