# W04-2 首次失败和辅助错误

原件以唯一标签保存，后续通过不覆盖旧结果。

| 标签 | 真实结果 | 分类与处理 |
|---|---|---|
| w04-2-before-01 | 1 ERROR，0 PASS | 原已验收内部Action契约尚无device参数入口，EXTERNAL_INPUT_BINDING_INVALID；本批未实现行为证据，不宣称旧版本违背旧范围 |
| w04-2-contract-01 | 1 ERROR | 新测试的时间使用+00:00，不符合既有要求的大写Z；修正新输入，未放宽契约 |
| w04-2-chain-01 | 15 PASS、3 ERROR | 新增历史范围数组在持久化前为tuple、后为list，引起原恢复身份拒绝；DeviceCommand规范化为JSON值修复 |
| w04-2-query-fix-01 | 3 PASS | 上述3个查询/权限场景定点复跑，7秒左右；精确时间见json |
| w04-2-chain-02 | 28 PASS、2 FAIL、1 ERROR | 新夹具重放后错取未执行的内存last_action；新错误身体断言误期待异常而原Planner持久化非成功；深层临时路径使宿主对照未到达认知。原输出保留 |
| w04-2-boundary-fix-01 | 3 PASS、1 ERROR | 换身体与错误身份已通过，旧P18无消息认知对照通过；同主体宿主新场景明确记录FileNotFoundError，失败临时文件路径超过Windows传统长度 |
| w04-2-host-fix-01 | 1 PASS | 仅将新夹具置于浅隔离临时根，保留认知、控制及无费用断言；同一主体/同一数据根，锁屏后宿主仍存活并可处理原认知 |
| w04-2-flow-01 | 5 PASS | 正常原始消息C1、合法吸收、历史范围/同根/过期与技术替代 |
| w04-2-guards-01 | 5 PASS、1 ERROR | 新测试误把Runtime的PAUSE用于SubjectLifecycle；原契约合法操作是SUSPEND，静态边界正确拒绝。仅修新测试的命令 |

另有只读辅助错误：初次进程命令行查询拒绝访问，获准只读系统查询后没有Python进程；多次Windows字面通配路径搜索失败，改用rg的文件筛选；一次不存在的候选文件读取；一次apply_patch上下文不匹配，工具原子拒绝且未产生半写。未把它们记为Engine行为缺陷。Git差异检查的LF→CRLF提示与功能结果分开，最终原始输出另存。

历史F1/H1/F2继续UNKNOWN，本次没有倒推其根因。没有运行生产设备/凭据，也没有取得远端CI结果。

## 最终兼容新失败（不覆盖上表）

414项为407 PASS/1 FAIL/6 ERROR，原结果及基线对照见[阻断说明](conflict-report.md)。两版同类失败不证明唯一根因，本轮未修原W02/P18逻辑。另一次只读定位误用不存在的p16_fixture.py/w02_fixture.py文件名，rg返回缺文件；改读实际p16_provider_fixture.py，未影响源码或测试结果。

finish.py和summarize.py是此前准备的全通过收尾分支，本轮未运行；实际阻断交付由close_blocked.py根据完成记录生成，不能将未运行脚本视为证据。
