# P15返修辅助错误与中间兼容记录

- `p15-final`首次完整专项为71项，70 PASS、1 ERROR，205.140秒。R1新增的`changed_at <= applied_at`把生命周期Port时钟与Evolution服务时钟强制排序，原合法TEST接线不要求两者共用时钟。仅移除此额外上界，保留命令时间下界、生命周期历史时间单调性及所有身份/状态/变化绑定。原失败用例未改，`clock-compat`为1 PASS、1.034秒；后续稳定结果另存。此为R1修复引入的兼容错误，不能记作通过或无关工具故障。

- 一次apply_patch因预期单引号`growth_operation=value.get(...)`与真实双引号行不匹配，工具校验拒绝；核对无文件变化后按真实文本重新应用。不是Engine测试缺陷。
- `legacy-additions-before`的COMMITTED事实缺失用例初版patch了Fixture runtime的另一个SubjectStateService实例，未作用于Growth实际事实Port，因此FAIL。改为patch `growth.core.subject_states.get_update_history`，不修改业务断言；此辅助失误不计第四类Engine缺陷，原输出保留。
- 同轮普通旧Event仅使用同名event_type却被R1初版当作管理历史，实跑ERROR；R1收窄为真实生命周期mutation/change或受管理source/稳定前缀标记，保留真正旧格式。后续结果另存，未覆盖。
- `formal-before`的26个方法含subTest，10个方法通过；14条FAIL与3条ERROR记录包含同一方法的多个失败，不相加冒充测试总数。JSON保留方法身份和全部堆栈。

- `legacy-additions-after`保留2 ERROR：新增SUPERSEDED强绑定校验在构造时执行，而内部生成器此前先构造再赋resolution。已把绑定作为构造参数传入，保留校验、不改断言；最终32项包含这两个旧格式恢复场景并通过。
