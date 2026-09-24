"""One bounded diagnostic of the preserved T03 failure; no relaxed assertion."""
import json
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture

class BudgetProbe(unittest.TestCase):
    def test_report_material_budget(self):
        with tempfile.TemporaryDirectory() as root:
            f=W02RecallFixture(Path(root))
            f.event('old-meal',content='我以前吃过螺蛳粉。',occurred_at=f.runtime.clock.now()-timedelta(days=1))
            f.runtime.clock.advance(timedelta(hours=4));noon=f.message('我中午12点吃过午饭。');f.submit(noon)
            f.runtime.clock.advance(timedelta(hours=3));r=f.message('我又在吃螺蛳粉。');f.submit(r)
            ctx=f.context(r)
            print(json.dumps({'snapshot':[(x.stable_source_id,x.estimated_tokens,len(x.content)) for x in ctx.composition.snapshot.fragments],
                'trace':ctx.composition.trace.to_dict(),'route':ctx.route.trace.to_dict(),
                'modelChars':len(ctx.model_summary()),'noon':noon['requestId']},ensure_ascii=False))
