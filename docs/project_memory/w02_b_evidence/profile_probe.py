"""One bounded measurement; original deadline and operations are unchanged."""
from contextlib import ExitStack
from pathlib import Path
import tempfile,time,json,unittest
from unittest.mock import patch
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture

class ProfileProbe(unittest.TestCase):
    def test_measure_original_candidate_preparation(self):
        with tempfile.TemporaryDirectory() as root:
            f=W02RecallFixture(Path(root));totals={};counts={}
            def measured(name,call):
                def wrapper(*a,**kw):
                    begin=time.perf_counter()
                    try:return call(*a,**kw)
                    finally:
                        totals[name]=totals.get(name,0)+time.perf_counter()-begin
                        counts[name]=counts.get(name,0)+1
                return wrapper
            with ExitStack() as stack:
                for name,obj,method in [('ledger.load',f.app.ledger,'load_operation'),('ledger.list',f.app.ledger,'list_operations'),
                        ('route',f.core.router,'route'),('compose',f.core.composer,'compose'),
                        ('candidate',f.core.recall,'_preference_candidates'),('prepare',f.core.recall,'prepare')]:
                    stack.enter_context(patch.object(obj,method,side_effect=measured(name,getattr(obj,method))))
                for i,text in enumerate(('我吃了螺蛳粉。','我又在吃螺蛳粉。','我喜欢螺蛳粉。')):
                    f.event('meal'+str(i),content=text);r=f.message(text,source_event_id='meal'+str(i))
                    totals.clear();counts.clear()
                    try:f.submit(r)
                    finally:
                        print(json.dumps({'round':i,'seconds_including_nested_calls':totals,'counts':counts},ensure_ascii=False))
