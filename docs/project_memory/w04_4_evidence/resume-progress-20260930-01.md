
## 2026-09-30 恢复施工：当前事实（历史快照保留）

D-092 继续 IN_PROGRESS / EVIDENCE_CONFLICT=PRESENT。P13精确表达确认、相关C1表达先于投递两处最小公共补修已获用户明确确认，已实施；不再等待同一授权。未验收、不写Git、不启动W05。

恢复核对：main/HEAD c910be8ff65f1384c4942c980fc4087c1b595a87，328项指纹5f41c792…与native-related-memory-repair-01前后完全一致。63保护、正式7、规划、70保留及旧测试文件均无变化，暂存空，未见旧Python测试进程。原native-related-memory-repair-01为1PASS/1ERROR，不能当整体完成。

本次一次轻量测量provenance-stations-before-01：检索686.814ms、Composer212.820ms、补充授权88.956ms（嵌套统计不可任意相加），原1000ms保持。新增来源追溯同次walk复用原记录/祖先投影，无跨请求授权缓存；每次独立来源检查仍读取当前原件。补读取回调后绑定版本核验。provenance-repair-03三项PASS：API/UI正常链及读取中撤权；此前相关native Memory撤权反例已PASS。尚须同最终版集中验证。

新增投递观察只读投影：从原P17 query/E5-A及当前来源核验取得送达/已读证据，发送回执不能冒充已读；delivery-observation-02四项PASS。尝试把事项采纳直接追加在C1返回之后会使原Context过期，已撤下该接线尝试，保留失败；事项仍由原W03入口根据已形成的Thinking意图、当前核验和同一命令采纳/恢复，旧Context不得静默重绑。

contact-pause-internal-before-01实际FAIL：联系暂停在选路时抛错阻断独立native心智提交。定点改为选路只核验读取/身份，实际发送仍由原P17当前与最终关口检查联系权限；repair-01同反例PASS，发送与费用0、独立心智revision推进。相应新增草稿测试从要求异常改为同时断言零发送与合法内部推进；原1923项测试文件未改。

迟到时区入站元数据原误用UTC-only事实解析器，已在新增EntryMessage职责内解析带时区RFC3339并保留原文，冻结事实时间格式不改。并发入站测试改为识别原INPUT_ADMISSION_BUSY且验证未持久化，再沿原身份续接。原STOP命令幂等重放与新RESUME身份分别核验。包级组合第一轮因跨core旧Context不一致被正确拒绝；改为新后续步骤取得自己的当前Context，不改原请求绑定。

辅助记录：恢复清单脚本将planning列表误当映射；两条新测试启动类名错误；新增断言用了错误异常层；模拟观察expires_at遗漏字符串格式；若干只读候选路径不存在。均保留原输出/说明，不当作已证实Engine行为缺陷。首次失败/ERROR不删除。当前专项、公共兼容、全量尚未固定最终版运行，不能借用旧PASS。

下一步：完成包级因果组合、剩余权限/恢复验证，固定源码，再专项、受影响公共兼容及一次全量。历史F1/H1/F2 UNKNOWN、SKIP及无远端CI证据照留。
