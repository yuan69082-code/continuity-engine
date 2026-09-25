"""One isolated W02 deadline diagnosis; read TEST records before cleanup."""
import json
from pathlib import Path
from time import perf_counter

from tests.test_w02_integration import W02IntegratedChainTests
from continuity_engine.domain import unfinished_item

original_item_records = unfinished_item.item_records
item_cost = {'count': 0, 'seconds': 0.0}
def counted_item_records(*args, **kwargs):
    started = perf_counter()
    try:
        return original_item_records(*args, **kwargs)
    finally:
        item_cost['count'] += 1
        item_cost['seconds'] += perf_counter() - started
unfinished_item.item_records = counted_item_records

case = W02IntegratedChainTests(
    'test_partial_derived_withdrawal_invalidates_integrated_reply_and_support')
case.setUp()
try:
    try:
        case.test_partial_derived_withdrawal_invalidates_integrated_reply_and_support()
        outcome = 'PASS'
    except Exception as exc:
        outcome = type(exc).__name__
    records = []
    for path in sorted(case.f.base.runtime.data_root.rglob('operation-journal*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        def visit(node):
            if isinstance(node, dict):
                if 'elapsed_ms' in node and 'stop_reason' in node:
                    records.append({key: node.get(key) for key in
                        ('status','stop_reason','elapsed_ms','retrieved_count',
                         'model_calls','external_calls')})
                for child in node.values(): visit(child)
            elif isinstance(node, list):
                for child in node: visit(child)
        visit(payload)
    print(json.dumps({'outcome':outcome,'recall_records':records,
                      'item_parse_calls': item_cost['count'],
                      'item_parse_ms': round(item_cost['seconds']*1000,3)},
                     ensure_ascii=False))
finally:
    unfinished_item.item_records = original_item_records
    case.doCleanups()
