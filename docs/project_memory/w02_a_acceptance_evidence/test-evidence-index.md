# 验收引用的测试证据

规划窗口完成的是只读代码与证据复核，结论仅为本轮核查范围内未发现新的验收阻断、实现/正式测试/原始结果相互对应；没有重新运行测试，也不保证不存在其他缺陷。本轮只做身份、保护、文档及Git检查，没有运行测试。

|施工方既有实跑（本轮仅引用）|结果|墙钟秒|原始记录|
|---|---|---:|---|
|formal|25项：25 PASS、0 SKIP、0 FAIL、0 ERROR|18.586|[JSON](../w02_a_evidence/repair_r1_r2/formal-final-02.json) · [stdout](../w02_a_evidence/repair_r1_r2/formal-final-02.stdout.log) · [stderr](../w02_a_evidence/repair_r1_r2/formal-final-02.stderr.log)|
|special|66项：66 PASS、0 SKIP、0 FAIL、0 ERROR|53.283|[JSON](../w02_a_evidence/repair_r1_r2/w02-final-02.json) · [stdout](../w02_a_evidence/repair_r1_r2/w02-final-02.stdout.log) · [stderr](../w02_a_evidence/repair_r1_r2/w02-final-02.stderr.log)|
|compatibility|218项：218 PASS、0 SKIP、0 FAIL、0 ERROR|131.728|[JSON](../w02_a_evidence/repair_r1_r2/compatibility-final-02.json) · [stdout](../w02_a_evidence/repair_r1_r2/compatibility-final-02.stdout.log) · [stderr](../w02_a_evidence/repair_r1_r2/compatibility-final-02.stderr.log)|
|full|1646项：1645 PASS、1 SKIP、0 FAIL、0 ERROR|1659.112|[JSON](../w02_a_evidence/repair_r1_r2/full-final-02.json) · [stdout](../w02_a_evidence/repair_r1_r2/full-final-02.stdout.log) · [stderr](../w02_a_evidence/repair_r1_r2/full-final-02.stderr.log)|

原1621测试身份保留，新增25；各组交集不累加。既有SKIP为test_p08_fixture_paths中Windows创建符号链接权限1314，非PASS。最终282文件源码指纹`sha256:1021239d8214b38493aa3ff8ea5011c7b27856966bfe3395545607a8c066c523`。

[修前失败及全部中间结果](../w02_a_evidence/repair_r1_r2/test-history.md) · [初版证据](../w02_a_evidence/final-report.md) · [补修证据](../w02_a_evidence/repair_r1_r2/final-report.md)。旧版通过仅覆盖各自版本，不能替代最终版本。
