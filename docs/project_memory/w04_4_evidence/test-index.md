# W04-4 全部运行索引

施工窗口实跑/诊断，与规划窗口只读复核、远端CI分开。集合有交集，不能相加。退出0的诊断包装不等于测试通过；FAILED汇总即使包装退出0仍保留失败。没有最终汇总不计算PASS。精确命令、前后源hash及原始stdout/stderr在同名文件，详细分类见[test-index.json](test-index.json)。

| 标签 | PASS / SKIP / FAIL / ERROR | 测试/外层秒 | 退出码 | 最终同版 |
|---|---|---|---:|---|
|[before-entry-01](before-entry-01.json)|无正式最终汇总|None / 0.538|1|False|
|[before-entry-02](before-entry-02.json)|无正式最终汇总|None / 0.876|0|False|
|[compatibility-interim-01](compatibility-interim-01.json)|153 / 0 / 0 / 0|278.354 / 279.081|0|False|
|[confirmation-conflict-01](confirmation-conflict-01.json)|无正式最终汇总|None / 1.427|0|False|
|[confirmation-conflict-02](confirmation-conflict-02.json)|无正式最终汇总|None / 1.427|0|False|
|[confirmation-conflict-03](confirmation-conflict-03.json)|无正式最终汇总|None / 2.532|0|False|
|[confirmation-repair-01](confirmation-repair-01.json)|0 / 0 / 0 / 1|6.294 / 6.938|1|False|
|[contact-pause-internal-before-01](contact-pause-internal-before-01.json)|0 / 0 / 1 / 0|11.588 / 12.163|1|False|
|[contact-pause-internal-repair-01](contact-pause-internal-repair-01.json)|1 / 0 / 0 / 0|6.513 / 7.069|0|False|
|[continuation-cases-01](continuation-cases-01.json)|2 / 0 / 1 / 2|16.18 / 16.766|1|False|
|[continuation-cases-02](continuation-cases-02.json)|4 / 0 / 1 / 0|20.883 / 21.438|1|False|
|[delivery-file-check-01](delivery-file-check-01.json)|0 / 0 / 0 / 2|24.283 / 24.921|1|False|
|[delivery-observation-01](delivery-observation-01.json)|1 / 0 / 0 / 3|7.181 / 7.739|1|False|
|[delivery-observation-02](delivery-observation-02.json)|4 / 0 / 0 / 0|13.815 / 14.357|0|False|
|[delivery-profile-01](delivery-profile-01.json)|无正式最终汇总|None / 14.445|0|False|
|[delivery-projection-01](delivery-projection-01.json)|0 / 0 / 0 / 2|25.046 / 25.701|1|False|
|[delivery-selective-01](delivery-selective-01.json)|2 / 0 / 0 / 0|32.165 / 32.812|0|False|
|[delivery-state-parse-01](delivery-state-parse-01.json)|0 / 0 / 0 / 2|23.493 / 24.118|1|False|
|[delivery-state-stations-01](delivery-state-stations-01.json)|无正式最终汇总|None / 12.422|0|False|
|[delivery-stations-01](delivery-stations-01.json)|无正式最终汇总|None / 13.164|0|False|
|[entry-boundaries-before-01](entry-boundaries-before-01.json)|4 / 0 / 1 / 0|12.5 / 13.143|1|False|
|[entry-boundaries-repair-01](entry-boundaries-repair-01.json)|6 / 0 / 0 / 0|24.28 / 24.913|0|False|
|[entry-draft-01](entry-draft-01.json)|0 / 0 / 0 / 1|2.066 / 2.769|1|False|
|[entry-draft-02](entry-draft-02.json)|0 / 0 / 0 / 1|2.271 / 2.974|1|False|
|[entry-draft-03](entry-draft-03.json)|0 / 0 / 0 / 1|7.949 / 8.607|1|False|
|[entry-profile-01](entry-profile-01.json)|0 / 0 / 0 / 1|2.525 / 3.531|0|False|
|[entry-projection-01](entry-projection-01.json)|0 / 0 / 0 / 1|20.351 / 21.073|1|False|
|[entry-read-repair-01](entry-read-repair-01.json)|0 / 0 / 0 / 2|36.047 / 36.785|1|False|
|[entry-root-work-01](entry-root-work-01.json)|0 / 0 / 0 / 1|15.157 / 15.893|1|False|
|[entry-scope-01](entry-scope-01.json)|2 / 0 / 0 / 1|26.786 / 27.485|1|False|
|[entry-single-boundary-01](entry-single-boundary-01.json)|0 / 0 / 0 / 2|24.879 / 25.543|1|False|
|[entry-source-union-01](entry-source-union-01.json)|0 / 0 / 0 / 2|30.694 / 31.473|1|False|
|[entry-unknown-dispatched-before-01](entry-unknown-dispatched-before-01.json)|5 / 0 / 0 / 1|21.653 / 22.277|1|False|
|[expression-repair-01](expression-repair-01.json)|60 / 0 / 0 / 0|87.204 / 87.888|0|False|
|[full-errors-copy-stations-01](full-errors-copy-stations-01.json)|0 / 0 / 0 / 1|56.406 / 57.045|1|False|
|[full-errors-guards-02](full-errors-guards-02.json)|3 / 0 / 0 / 0|4.35 / 4.992|0|True|
|[full-errors-repair-01](full-errors-repair-01.json)|3 / 0 / 0 / 2|135.167 / 135.812|1|False|
|[full-errors-stations-01](full-errors-stations-01.json)|1 / 0 / 0 / 1|72.789 / 73.413|1|False|
|[full-errors-stations-after-01](full-errors-stations-after-01.json)|2 / 0 / 0 / 0|132.059 / 132.685|0|True|
|[full-final-01](full-final-01.json)|1969 / 1 / 0 / 2|2253.815 / 2254.777|1|False|
|[full-final-02](full-final-02.json)|1974 / 1 / 0 / 0|2380.273 / 2381.35|0|True|
|[independent-scope-01](independent-scope-01.json)|8 / 0 / 0 / 0|30.739 / 31.523|0|False|
|[native-chain-01](native-chain-01.json)|0 / 0 / 1 / 0|5.858 / 6.485|1|False|
|[native-chain-02](native-chain-02.json)|0 / 0 / 0 / 1|5.909 / 6.565|1|False|
|[native-chain-03](native-chain-03.json)|0 / 0 / 1 / 0|8.726 / 9.406|1|False|
|[native-chain-04](native-chain-04.json)|0 / 0 / 0 / 2|41.902 / 42.63|1|False|
|[native-fact-view-01](native-fact-view-01.json)|0 / 0 / 0 / 2|27.724 / 28.365|1|False|
|[native-path-measure-01](native-path-measure-01.json)|无正式最终汇总|None / 8.451|0|False|
|[native-path-repair-01](native-path-repair-01.json)|0 / 0 / 1 / 0|7.28 / 7.997|1|False|
|[native-read-measure-01](native-read-measure-01.json)|无正式最终汇总|None / 8.169|0|False|
|[native-recall-diagnostic-01](native-recall-diagnostic-01.json)|0 / 0 / 1 / 0|9.372 / 10.126|1|False|
|[native-related-memory-before-01](native-related-memory-before-01.json)|0 / 0 / 1 / 0|12.857 / 13.504|1|False|
|[native-related-memory-repair-01](native-related-memory-repair-01.json)|1 / 0 / 0 / 1|23.257 / 23.904|1|False|
|[native-scope-01](native-scope-01.json)|0 / 0 / 1 / 0|10.071 / 10.829|1|False|
|[native-transfer-before-01](native-transfer-before-01.json)|0 / 0 / 0 / 1|10.858 / 11.494|1|False|
|[native-transfer-source-01](native-transfer-source-01.json)|1 / 0 / 0 / 0|12.643 / 13.308|0|False|
|[native-unknown-before-01](native-unknown-before-01.json)|1 / 0 / 0 / 0|15.514 / 16.163|0|False|
|[native-unknown-inspect-01](native-unknown-inspect-01.json)|1 / 0 / 0 / 0|14.027 / 14.589|0|False|
|[native-version-repair-01](native-version-repair-01.json)|0 / 0 / 1 / 0|17.979 / 18.806|1|False|
|[package-binding-batch-01](package-binding-batch-01.json)|3 / 0 / 0 / 1|92.063 / 92.655|1|False|
|[package-bounded-read-01](package-bounded-read-01.json)|1 / 0 / 1 / 0|21.51 / 22.068|1|False|
|[package-chain-01](package-chain-01.json)|1 / 0 / 0 / 1|2.656 / 3.24|1|False|
|[package-chain-02](package-chain-02.json)|0 / 0 / 0 / 1|12.291 / 12.866|1|False|
|[package-cpu-01](package-cpu-01.json)|0 / 0 / 0 / 1|13.39 / 13.986|1|False|
|[package-digest-01](package-digest-01.json)|2 / 0 / 0 / 1|53.077 / 53.642|1|False|
|[package-projection-01](package-projection-01.json)|1 / 0 / 0 / 1|13.732 / 14.321|1|False|
|[package-projection-02](package-projection-02.json)|0 / 0 / 0 / 2|12.509 / 13.07|1|False|
|[package-query-priority-01](package-query-priority-01.json)|1 / 0 / 0 / 1|12.066 / 12.651|1|False|
|[package-reply-stations-01](package-reply-stations-01.json)|1 / 0 / 0 / 1|54.888 / 55.451|1|False|
|[package-selection-01](package-selection-01.json)|1 / 0 / 1 / 0|19.367 / 19.949|1|False|
|[package-selection-repair-01](package-selection-repair-01.json)|1 / 0 / 0 / 1|12.447 / 13.011|1|False|
|[package-stations-01](package-stations-01.json)|0 / 0 / 0 / 1|12.908 / 13.478|1|False|
|[package-stations-02](package-stations-02.json)|0 / 0 / 2 / 0|20.479 / 21.054|1|False|
|[package-tool-read-01](package-tool-read-01.json)|1 / 0 / 0 / 1|12.026 / 12.6|1|False|
|[path-metadata-comparison-01](path-metadata-comparison-01.json)|无正式最终汇总|None / 1.188|0|False|
|[provenance-repair-02](provenance-repair-02.json)|2 / 0 / 0 / 3|13.715 / 14.289|1|False|
|[provenance-repair-03](provenance-repair-03.json)|3 / 0 / 0 / 0|32.609 / 33.202|0|False|
|[provenance-stations-before-01](provenance-stations-before-01.json)|无正式最终汇总|None / 17.028|0|False|
|[public-final-01](public-final-01.json)|1144 / 1 / 0 / 0|1621.323 / 1622.197|0|False|
|[public-final-02](public-final-02.json)|1144 / 1 / 0 / 0|1666.164 / 1667.02|0|True|
|[queried-entry-before-01](queried-entry-before-01.json)|1 / 0 / 1 / 0|12.263 / 12.826|1|False|
|[queried-entry-repair-01](queried-entry-repair-01.json)|2 / 0 / 0 / 0|11.619 / 12.188|0|False|
|[reply-measure-01](reply-measure-01.json)|无正式最终汇总|None / 21.007|1|False|
|[reply-measure-02](reply-measure-02.json)|无正式最终汇总|None / 15.728|1|False|
|[reply-profile-01](reply-profile-01.json)|无正式最终汇总|None / 17.106|0|False|
|[reply-stations-01](reply-stations-01.json)|无正式最终汇总|None / 15.927|0|False|
|[scope-02](scope-02.json)|0 / 0 / 0 / 1|7.321 / 7.96|1|False|
|[scope-light-01](scope-light-01.json)|无正式最终汇总|None / 11.932|0|False|
|[scope-profile-01](scope-profile-01.json)|0 / 0 / 0 / 1|31.797 / 32.805|0|False|
|[targeted-final-01](targeted-final-01.json)|49 / 0 / 0 / 0|298.406 / 298.979|0|False|
|[targeted-final-02](targeted-final-02.json)|52 / 0 / 0 / 0|306.026 / 306.668|0|True|
|[unknown-distinction-01](unknown-distinction-01.json)|2 / 0 / 0 / 0|21.467 / 22.042|0|False|
|[w04-entry-development-01](w04-entry-development-01.json)|45 / 0 / 0 / 0|263.209 / 263.848|0|False|
|[w04-final-01](w04-final-01.json)|196 / 0 / 0 / 0|638.131 / 638.782|0|False|
|[w04-final-02](w04-final-02.json)|199 / 0 / 0 / 0|662.495 / 663.233|0|True|

原1923身份保留，新增52，共1975；原测试文件字节未改。原1000ms/2048/每轮两need未变；Windows1314 SKIP不算PASS。历史不同版成功不代替最终同版结果。
