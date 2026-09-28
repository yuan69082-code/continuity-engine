# D-091：W04-3 初版及 R1/R2 正式验收

2026-09-29，用户正式验收 W04-3 工具发现、授权与缺项检查、临时接入、验证、使用、结束及恢复，以及 R1 等待首项不持续排除其他可执行事项、R2 取消累计三份清理请求的永久终止门槛。核查决定最高编号 D-090（开工），本次登记 **D-091**，不改写原决定。用户同时授权本批精确暂存、现有 Engine main 一次普通提交及向既有 origin/main 普通 push；不授权 W04-4。

**W04-3 = ACCEPTED；W04 整体 = IN_PROGRESS；W04-4 = NOT_STARTED。** W04-1/D-087、W04-2/D-089及全部既有阶段验收不重做。依据现行总施工 v1.6、最终新增 v1.6、长期能力 v6.10 的 W04 子批次三、N14/T30—T32/T41、C11、适用T18及N21查询衔接；三份规划原文及现行索引属于70份本地保留材料，不修改、不提交，不宣称D-085独有材料已推送。

## 本次验收依据

规划窗口独立只读复核了代码、原始输出、测试身份、源码指纹、交付清单和保护范围，**没有运行 Engine 或测试**。本次也只做验收归档和Git收尾，不重跑测试。321项源码/测试/资源逐文件与五组前后清单一致：`sha256:aa96381b507957c66efbb3a7cd6d8721d4b920199cfb6a547e59c2d655ad8506`。原1909项身份和旧测试文件保留，新增14项，共1923项。

| 施工方既有同版运行 | PASS / FAIL / ERROR / SKIP | unittest 秒 / runner 秒 | exit |
|---|---|---|---|
| [targeted-final-01](../w04_3_repair_evidence/targeted-final-01.json) | 14 / 0 / 0 / 0 | 166.421 / 167.125 | 0 |
| [w04-3-final-01](../w04_3_repair_evidence/w04-3-final-01.json) | 60 / 0 / 0 / 0 | 324.797 / 325.487 | 0 |
| [w04-12-final-01](../w04_3_repair_evidence/w04-12-final-01.json) | 87 / 0 / 0 / 0 | 159.335 / 160.0 | 0 |
| [compatibility-final-01](../w04_3_repair_evidence/compatibility-final-01.json) | 417 / 0 / 0 / 0 | 701.162 / 701.916 | 0 |
| [full-final-01](../w04_3_repair_evidence/full-final-01.json) | 1922 / 0 / 0 / 1 | 2390.489 / 2391.61 | 0 |


集合有交集，不相加。全量1923项＝1922 PASS、1个既有Windows1314 SKIP、0 FAIL/ERROR；SKIP不算PASS。命令、输出、时长和退出码见[原始测试索引](../w04_3_repair_evidence/test-index.md)，本次核对的原件hash见[test-references.json](test-references.json)。没有取得远端CI run/check结果，不能声称CI PASS。

## 已知阻断关闭依据及保留历史

| 本批已知事项 | 具体依据 | 本次状态 |
|---|---|---|
| 初版发现至退出的接线及验证 | 初版46项正式回归纳入最终W04-3的60项；发现≠授权≠接通≠当前可用，单次/限时/持续、当前资格及UNKNOWN按原P08/P16/P17/P18/E5-A处理；[初版矩阵](../w04_3_evidence/matrix.md)与原始记录对应 | 本批已交付初版ACCEPTED |
| R1 固定首项截取使后项不能入队 | before-02真实宿主反例FAIL；只为原Scheduler尚未拥有的需求提供最多两个入队名额，原native认知/维护不关闭；同反例及多事项、恢复、暂停/停止、UNKNOWN正式回归通过 | 已知入队饥饿缺口及其复核阻断关闭 |
| R2 全生命周期三次清理封顶 | before-02三份失败后不能续做FAIL；每次advance仍最多一份清理，后续自动清理由上一份原回执时间退避、默认复用P18的5秒；重开、部分失败、UNKNOWN/返回丢失、撤权与隔离正反对照通过 | 已知永久终止门槛及其复核阻断关闭 |
| 返修后同版与兼容证据待复核 | 最终14/60/87/417及全量均绑定上列源码；规划窗口只读复核和用户本次明确确认 | 本批现行EVIDENCE_CONFLICT=NONE；不代表无其他潜在缺陷 |

本批现行PLANNING_CONFLICT=NONE。旧IMPLEMENTED_NOT_ACCEPTED、旧EVIDENCE_CONFLICT=PRESENT、修前FAIL、辅助ERROR、中断、原SKIP、格式/行尾提示及重度剖析超时保留原字节；未把旧时点改成已验收。历史F1/H1/F2仍为UNKNOWN，本次验收不证明其历史唯一根因。详见[原返修报告](../w04_3_repair_evidence/final-report.md)、[调查记录](../w04_3_repair_evidence/investigations.md)。

## 效果与未开放边界

本机隔离TEST中，等待登录/依赖/核实/清理的工具不持续占掉所有新任务入口，原认知与维护仍可推进；清理失败超过三份后，当前条件恢复且资格有效时可沿原连接续做。UNKNOWN先查询原事实、成功清理不重复；原请求/费用/状态权威不另建。

旧Context失效仍正确拒绝，不自动重绑旧请求；合法后续步骤须经原链取得当前Context。不保证任意无界负载公平性、所有场景清理必能成功或生产性能。原W02的1000毫秒、历史查询2048预算、P18控制等待及每轮两个need上限均不变。主体持续运行、Owner PAUSE/STOP、当前权限/host/generation、生命周期及内部认知与现实行动边界保持。

真实服务、账号、设备、生产凭据仍未开放。W04-4跨入口接续与包级贯通、W05自然记忆/梦境、P19完整页面、P20/P21正式恢复及P22真实接入仍按原阶段待授权/未就绪。本次不是W04整体验收。

## 档案与Git范围

本轮只新增本验收目录，并在README及七份工程档案前置当前验收入口；原完整历史后缀逐字节核对。共享档案中已有D-085等授权记录保留，但70份独立保留材料不纳入。原227项加本次必要增量，实际路径与数量见[精确清单](final.pending-files.md)、[hash清单](final.files.json)，[排除清单](exclusions.json)列70份原件hash。源码、正式测试、原始测试日志、63保护、规划、正式七文件和版本本轮不改。

暂存使用命令级 `core.autocrlf=false`，不修改全局配置，逐文件比对Git blob与工作树原字节，尤其保留旧日志。若发生其他属性转换或范围不符则停下；不通过改写日志清除行尾提示。检查结果见[审计](final.audit.json)。

提交前实际远端已查询为 `f64fb797ae4defae2dfd16278f38e89c8b13cd66`；默认TLS凭据错误与单次OpenSSL核验见[远端预检](remote-precheck.json)，证书验证开启。本文不预填提交或push成功；实际操作和推送后核验单独在最终回复及明确标注的本地记录报告，不擅自追加第二提交。

[正式验收矩阵](acceptance-matrix.md) · [施工只读链路示例](../w04_3_repair_evidence/chain-example.md) · [原恢复语义](../w04_3_repair_evidence/recovery-semantics.md)。完成本批Git收尾即停止。

## 暂存检查实况（提交前）

239项＝原227项＋12项必要验收文件。已按清单精确暂存并核对全部blob等于工作树原字节，未发生行尾规范化。默认暂存差异检查exit 2、输出117212行，主要是原CRLF被默认规则判作行尾空白；以命令级`core.whitespace=cr-at-eol`识别CRLF后，仍exit 2，剩一处历史`w04_3_evidence/finalize.py:69`行尾空格（2行输出）。该辅助脚本原字节保留，不修掉提示，也不把提示记成功能失败。

原始暂存及差异检查记录保存在仓库外本地临时目录`C:/Users/Administrator/AppData/Local/Temp/w04-3-d091-git-closeout-p8njbzr8/`，不属于本次Git清单；本轮普通沙箱首次读取该目录被拒，授权读取后已确认上述内容。该辅助读取错误不涉及仓库内容或Engine行为。验收材料补记这些结果后仅重暂存相应档案，再核对所有blob；正式提交和push尚未在本文中预填成功。
