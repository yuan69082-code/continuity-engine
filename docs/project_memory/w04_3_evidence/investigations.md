# 实现与失败过程

所有原始标签保留，不以之后的 PASS 覆盖。下列结果是施工方本轮实跑，不是规划窗口独立复核。各次源码前后完整清单和指纹在对应 JSON。

| 记录 | 真实结果 | 原因、处理和对应限制 |
|---|---|---|
| before-01 | 探针退出 0；P16 查询确有回执，临时接入链 NOT_IMPLEMENTED | 保存开工缺口；不是故意造失败，也不是功能 PASS |
| targeted-draft-01 | 10 项，3 PASS、7 ERROR | 新工具服务把无回执 UNKNOWN 交给 P17 事实收集器导致 EXECUTION_RESULT_BINDING；改为保留在原 E5-A/Outbox，不伪造事实。另有历史查询 Fixture 未接既有 2048 预算，ContextNotReady；只修新 Fixture 接线，未提高预算 |
| targeted-draft-02 | 10 PASS | 中间源码；不能代替最终版 |
| expanded-draft-01 | 25 项，24 PASS、1 ERROR | 新跨主体候选 JSON 含空格达 2115 字符，超原候选 2048 界限，原 P16 在边界检查前正确拒绝；改新夹具紧凑编码，不放宽产品限额 |
| discovery-diagnostic-01 | 辅助退出 1 | 诊断临时根过长触发 Windows 临时文件路径失败，未进入预期反例；原脚本与输出保留 |
| discovery-diagnostic-02 | 诊断退出 1 | 使用短根记录 content_bytes=2115、ADAPTER_RESPONSE_UNKNOWN，定位上述辅助数据问题；两服务实例不同并非该错误已证明的根因 |
| expanded-draft-02 / boundaries-draft-01 | 33 PASS / 37 PASS | 中间扩展版本；覆盖恢复和新增边界 |
| observe-before-01 | 有效反例退出 1 | 临时租约到期后，纯 observe 尚返回 READY，effects=0；只动作有资格门禁不足 |
| observe-after-01 | 同原探针退出 0 | DeviceOperation 可选临时连接观察门禁前后核查，返回 W04_REVOKED，effects=0；不更改旧未接此门禁的调用行为 |
| targeted-final-candidate-01 | 43 PASS | 随后仅强化新 Fixture 首次持久化前材料检查及秘密测试；本次结果明确不是最终版本覆盖 |
| secret-final-01 | 1 PASS | 合成秘密作为 grant_ref 在原 P17 材料边界被拒，账本字节不变；端口异常标准 traceback 不含标记 |
| frozen-source-01.json | 身份收集错误，不是测试执行 | 辅助命令 PYTHONPATH 缺仓库根，13 个模块导入失败，1652 是无效收集数；保留全部导入异常和缺失列表。经原 runner 完整环境收集 frozen-source-02/identity-final-01：当时1906项、缺失0、导入错误0；取消补修后最终身份为 frozen-source-03/identity-final-02 |
| targeted-final-01 / special-final-01 / compatibility-final-01 | 43 / 87 / 417 PASS | 同属3d670f版本；其间发现新的取消漏口，故这三组保留为补修前历史，不当作最终覆盖。已只停止自动编排器，没有中断兼容，尚未启动全量 |
| cancel-before-01 / cancel-after-01 / cancel-after-final-01 | 同一探针修前退出1，修后退出0 | 待接入取消后原连接仍可新建；修后取消完成、重放WAITING_CAPABILITY、连接0、效果0、积分0。最终标签绑定ddb85f版本 |
| cancel-formal-01 | 3项，2 PASS、1 FAIL | 新交错测试错误要求嵌套执行锁内的清理立即CLOSED。定向诊断 cancel-nested-diagnostic-01 实测原P17返回EXECUTION_BUSY，取消记录已存、连接未建；不是清理成功事实丢失 |
| cancel-formal-02 | 3 PASS | 保留锁和产品语义，正式测试核对确切EXECUTION_BUSY及PENDING_CLEANUP，再在原执行退出后用同一清理请求完成CLOSED；未放宽观察时限或旧断言 |

另外保留开工不存在的决策路径、Git 中文路径引用导致断言、受限环境 CIM 进程查询拒绝、一次读取不存在 audit.py（实际旧 helper 名 finalize.py）等辅助工具错误；均未作为 Engine 缺陷，也没有修改旧原始证据。

最终档案 helper 首次写入04_决策记录.md时收到OSError/errno22（open阶段），已写完01及03顶部记录，04仍保持原长度、原D-090开工前缀和旧内容，无截断。见finalize-write-error-01.json。先核对已写段落精确相同再续接，避免重复前缀；不能据此归因到历史F1/H1/F2或宣称是已证明的共享冲突。仅辅助文档收尾，无源码/正式测试变化。

本批确认修的是新接入链的具体遗漏，不回溯宣称历史 F1/H1/F2 已查明。旧 cProfile 超时和已验收性能范围保持。最终测试见 [测试索引](test-index.md)，中间结果不拼接成最终覆盖。
