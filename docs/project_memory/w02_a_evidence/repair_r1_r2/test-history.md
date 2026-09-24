# 本轮运行记录（全部唯一标签保留）

| 标签 | 状态 | 总数 / PASS / FAIL / ERROR / SKIP | 墙钟秒 / 退出码 |
|---|---|---|---|
| [compatibility-final-01](compatibility-final-01.json) · [out](compatibility-final-01.stdout.log) · [err](compatibility-final-01.stderr.log) | FINISHED | 686 / 686 / 0 / 0 / 0 | 599.802 / 0 |
| [compatibility-final-02](compatibility-final-02.json) · [out](compatibility-final-02.stdout.log) · [err](compatibility-final-02.stderr.log) | FINISHED | 218 / 218 / 0 / 0 / 0 | 131.728 / 0 |
| [formal-final-01](formal-final-01.json) · [out](formal-final-01.stdout.log) · [err](formal-final-01.stderr.log) | FINISHED | 24 / 24 / 0 / 0 / 0 | 17.339 / 0 |
| [formal-final-02](formal-final-02.json) · [out](formal-final-02.stdout.log) · [err](formal-final-02.stderr.log) | FINISHED | 25 / 25 / 0 / 0 / 0 | 18.586 / 0 |
| [formal-intermediate-01](formal-intermediate-01.json) · [out](formal-intermediate-01.stdout.log) · [err](formal-intermediate-01.stderr.log) | FINISHED | 22 / 22 / 0 / 0 / 0 | 16.482 / 0 |
| [full-final-01](full-final-01.json) · [out](full-final-01.stdout.log) · [err](full-final-01.stderr.log) | FINISHED | 1645 / 1644 / 0 / 0 / 1 | 1649.505 / 0 |
| [full-final-02](full-final-02.json) · [out](full-final-02.stdout.log) · [err](full-final-02.stderr.log) | FINISHED | 1646 / 1645 / 0 / 0 / 1 | 1659.112 / 0 |
| [reproduction-after-01](reproduction-after-01.json) · [out](reproduction-after-01.stdout.log) · [err](reproduction-after-01.stderr.log) | FINISHED | 4 / 4 / 0 / 0 / 0 | 3.386 / 0 |
| [reproduction-before-01](reproduction-before-01.json) · [out](reproduction-before-01.stdout.log) · [err](reproduction-before-01.stderr.log) | FINISHED | 4 / 0 / 4 / 0 / 0 | 3.069 / 1 |
| [result-binding-after-01](result-binding-after-01.json) · [out](result-binding-after-01.stdout.log) · [err](result-binding-after-01.stderr.log) | FINISHED | 1 / 0 / 0 / 1 / 0 | 1.379 / 1 |
| [result-binding-after-02](result-binding-after-02.json) · [out](result-binding-after-02.stdout.log) · [err](result-binding-after-02.stderr.log) | FINISHED | 1 / 1 / 0 / 0 / 0 | 1.891 / 0 |
| [result-binding-before-01](result-binding-before-01.json) · [out](result-binding-before-01.stdout.log) · [err](result-binding-before-01.stderr.log) | FINISHED | 1 / 0 / 0 / 1 / 0 | 1.367 / 1 |
| [result-binding-before-02](result-binding-before-02.json) · [out](result-binding-before-02.stdout.log) · [err](result-binding-before-02.stderr.log) | FINISHED | 1 / 0 / 1 / 0 / 0 | 1.969 / 1 |
| [w02-final-01](w02-final-01.json) · [out](w02-final-01.stdout.log) · [err](w02-final-01.stderr.log) | FINISHED | 65 / 65 / 0 / 0 / 0 | 54.45 / 0 |
| [w02-final-02](w02-final-02.json) · [out](w02-final-02.stdout.log) · [err](w02-final-02.stderr.log) | FINISHED | 66 / 66 / 0 / 0 / 0 | 53.283 / 0 |
| [w02-intermediate-01](w02-intermediate-01.json) · [out](w02-intermediate-01.stdout.log) · [err](w02-intermediate-01.stderr.log) | FINISHED | 45 / 44 / 1 / 0 / 0 | 39.047 / 1 |

修前4FAIL对应本轮R1/R2；45项组合的1FAIL是普通问句过度分流。本轮末尾完成表绑定核查含2次辅助ERROR及1次有效FAIL，随后最小修补并用新冻结版本验证。其他中间通过（包括早先full-final-01）只覆盖当时源码。最终四组身份一致，不能把它们相加。旧W02顶层证据逐字节保留，历史F1/H1/F2仍UNKNOWN。
