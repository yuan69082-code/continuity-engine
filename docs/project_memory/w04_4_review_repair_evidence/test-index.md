# 本轮测试原始证据索引

|集合|PASS|SKIP|FAIL/ERROR|退出码|unittest / 控制器秒|
|---|---:|---:|---|---:|---|
|[lineage-prefix-repair-09](lineage-prefix-repair-09.json)|17|0|0 / 0|0|277.089 / 277.817|
|[w04-final-02](w04-final-02.json)|215|0|0 / 0|0|904.839 / 905.626|
|[public-final-02](public-final-02.json)|1144|1|0 / 0|0|1605.812 / 1606.717|
|[full-final-02](full-final-02.json)|1990|1|0 / 0|0|2460.921 / 2462.046|

命令、UTC时间、控制器退出码及运行前后逐文件源码在各同名JSON；原始输出在同名stdout.log/stderr.log。
所有隔离TEST，无真实设备/网络/账号；本轮仅当前四组可作为最终同版覆盖。

## 全部运行历史（不覆盖旧标签）

|标签|状态/退出码|控制器秒|源码前后相同|
|---|---|---:|---|
|[binding-before-02](binding-before-02.json)|COMPLETED / 1|8.46|True|
|[boundary-extension-04](boundary-extension-04.json)|COMPLETED / 1|146.296|True|
|[consume-current-repair-08](consume-current-repair-08.json)|COMPLETED / 1|104.662|True|
|[counterexamples-before-01](counterexamples-before-01.json)|COMPLETED / 1|47.199|True|
|[counterexamples-repair-01](counterexamples-repair-01.json)|COMPLETED / 1|64.84|True|
|[full-final-02](full-final-02.json)|COMPLETED / 0|2462.046|True|
|[lineage-and-guard-02](lineage-and-guard-02.json)|COMPLETED / 1|102.336|True|
|[lineage-and-guard-03](lineage-and-guard-03.json)|COMPLETED / 1|122.927|True|
|[lineage-prefix-repair-09](lineage-prefix-repair-09.json)|COMPLETED / 0|277.817|True|
|[native-diagnostic-01](native-diagnostic-01.json)|COMPLETED / 0|3.531|True|
|[native-diagnostic-02](native-diagnostic-02.json)|COMPLETED / 0|3.476|True|
|[package-all-diagnostic-02](package-all-diagnostic-02.json)|COMPLETED / 1|67.486|True|
|[package-lineage-diagnostic-01](package-lineage-diagnostic-01.json)|COMPLETED / 1|18.502|True|
|[projection-scope-repair-07](projection-scope-repair-07.json)|COMPLETED / 1|36.462|True|
|[public-final-02](public-final-02.json)|COMPLETED / 0|1606.717|True|
|[scoped-package-diagnostic-03](scoped-package-diagnostic-03.json)|COMPLETED / 1|65.24|True|
|[selected-state-before-05](selected-state-before-05.json)|COMPLETED / 1|9.003|True|
|[selected-state-repair-06](selected-state-repair-06.json)|COMPLETED / 0|25.389|True|
|[targeted-final-01](targeted-final-01.json)|COMPLETED / 0|151.854|True|
|[w04-final-01](w04-final-01.json)|COMPLETED / 1|765.416|True|
|[w04-final-02](w04-final-02.json)|COMPLETED / 0|905.626|True|

诊断脚本退出0不等于Engine正式测试PASS；原生诊断只解释夹具路线，不用于最终计数。原始汇总为准。
counterexamples-before-01的绑定夹具错误、首次修后旧Context断言、可选片段预算、包装异常和辅助属性错误逐项见repair-progress.md。
原旧最终全量1974 PASS/1 SKIP仅引用；未重新写成当前版本测试。F1/H1/F2 UNKNOWN、Windows1314 SKIP及原始超时/中断保留。

复跑：设置PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1、PYTHONPATH包含src与tests；使用run.py的未占用新标签和冻结JSON的groups。不得重用已有标签或同时启动全量。
本次已完成最终验证，交付后不自动再跑。
