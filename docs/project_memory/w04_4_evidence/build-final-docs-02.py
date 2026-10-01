"""Second frozen-version document generator; first-version template retained."""
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'build-final-docs.py').read_text(encoding='utf8')
source=source.replace('-final-01','-final-02').replace('新增49','新增52').replace('新49','新52').replace('共1972','共1975').replace('总1972','总1975')
source=source.replace('详见[调查记录](package-investigation-20261001.md)',
    '首次全量full-final-01的1969 PASS/1 SKIP/2 ERROR原件保留；该版2e910dd2…不覆盖最终版。后续当前Windows路径属性逐次读取及原日志来源字段投影补修，详见[最终超时调查](final-timeout-investigation-02.md)与[调查记录](package-investigation-20261001.md)')
source=source.replace('5类投影/副本/损坏/值突变新回归',
    '投影/副本/损坏/值突变、真实junction和元数据权限拒绝新回归')
source=source.replace('没有为性能改1000ms、2048或减少包级负载。',
    '没有为性能改1000ms、2048或减少包级负载。首次全量两处超时及后续定向最小补修另见final-timeout-investigation-02.md，不用这些较早的通过代替最终同版验证。')
source=source.replace('修补原始ThinkSession及上下文根追溯。',
    '修补原始ThinkSession及上下文根追溯。恢复任务时的native-related-memory-repair-01仍是1 PASS/1 ERROR、退出1：撤权对照通过，但正常链超时；该旧结果未改写，也不作为最终整体通过依据。')
source=source.replace('## 未被本次证明的范围',
    '按原始命令独立复跑某一组的方法见[复跑说明](reproduce.md)，恢复和拒绝边界见[恢复语义](recovery-semantics.md)。\n\n## 未被本次证明的范围')
exec(compile(source,str(here/'build-final-docs.py'),'exec'))
