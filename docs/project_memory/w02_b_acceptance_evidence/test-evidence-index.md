# W02-B 验收测试证据口径

规划窗口做只读代码与证据复核，未独立运行Engine测试；本次验收归档未重跑。以下均为施工方在最终固定源码上的原始实跑结果，四组有交集，不相加；具体命令、测试身份、stdout/stderr、退出码及前后源码hash见各JSON和[原测试索引](../w02_b_evidence/test-index.md)。

| 标签 | 原始结果 | 耗时/退出码 |
|---|---|---|
| [w02-b-final-04](../w02_b_evidence/w02-b-final-04.json) | 57 PASS，0 SKIP/FAIL/ERROR | 164.630秒 / 0 |
| [w02-a-compatibility-04](../w02_b_evidence/w02-a-compatibility-04.json) | 66 PASS，0 SKIP/FAIL/ERROR | 91.768秒 / 0 |
| [affected-compatibility-04](../w02_b_evidence/affected-compatibility-04.json) | 509 PASS，0 SKIP/FAIL/ERROR | 644.300秒 / 0 |
| [full-final-04](../w02_b_evidence/full-final-04.json) | 1703项=1702 PASS、1既有WinError1314 SKIP、0 FAIL/ERROR | 3191.570秒 / 0 |

原1646项身份和旧测试文件字节均保留，新增57。完整回归的SKIP为`test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes`，Windows不授予符号链接创建权限1314。最终290份源码/测试/资源与四组运行前后指纹一致：`sha256:c3e9649dbf8590a202e5fc82de79bdc6f641fbb41bd4355efd912eaa62c62aed`。[固定来源](../w02_b_evidence/frozen-source-04.json)。

[首次失败及中间过程](../w02_b_evidence/test-history.md)原样保留，包括早期全量ERROR、第二轮FAIL/ERROR、专项超时、语义误判与辅助错误；后续PASS不覆盖它们。历史F1/H1/F2的UNKNOWN另按原P18档案保留。本批未取得远端CI检查结果，不声明远端CI PASS。
