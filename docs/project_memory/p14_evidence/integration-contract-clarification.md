# 首轮 C1 测试的契约核对

`integration-first` 实跑4项：3 PASS、1 ERROR。ERROR原始stdout/stderr与源码清单原样保留。

新P14测试最初要求自身UPDATE_STATE推进revision后，仍能通过普通submit消费旧表达正文。现有P13的 `ExpressionPolicyService.verify(current=True)` / `decide` 明确要求当前Context；`ContinuityInteractionService.expression_outcome()` 则通过 `expression_current=False` 核实原回执与Evolution，再单独报告表达当前是否可读。这是已验收P13的事实恢复/当前访问分离，不是新发现的独立旧阶段缺陷。

本轮只修正新测试过窄的假设：通过原 `expression_outcome` 验证原状态revision/update ID可恢复、artifact为空；再次submit必须明确拒绝过期表达，原完成结果字节语义不变，SubjectState、effect_count、credits不变。没有改变原P13实现或断言，没有删除失败记录，也没有降低回执/Context要求。
