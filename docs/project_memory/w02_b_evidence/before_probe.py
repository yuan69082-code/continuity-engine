"""Unmodified production entry: establish W02-B's missing automatic assessment."""
from pathlib import Path
import json
import tempfile
import unittest
from continuity_engine.testing.w02_input_fixture import W02InputFixture

class BeforeRecallTests(unittest.TestCase):
    def test_answer_preparation_has_auditable_automatic_assessment(self):
        with tempfile.TemporaryDirectory() as root:
            f = W02InputFixture(Path(root))
            f.event('meal-before',content='我中午吃了午饭。')
            request=f.message('我又在吃螺蛳粉。')
            f.submit(request)
            context=f.context(request)
            print(json.dumps({'providerCalls':f.provider.calls,
                'contextKeys':list(context.to_dict()),
                'selectedSources':[r.stable_id for r in context.route.manifest.candidates],
                'thinkingReceivedOriginalContext': f.provider.inputs[0].continuity_context==context},ensure_ascii=False))
            self.assertIn('recall',context.to_dict(),
                'N02 requires an auditable pre-answer relevance/association assessment')

    def test_existing_current_message_still_enters_thinking(self):
        with tempfile.TemporaryDirectory() as root:
            f=W02InputFixture(Path(root)); request=f.message('我不爱吃苹果。'); f.submit(request)
            self.assertEqual(f.provider.calls,1)
            self.assertIn('我不爱吃苹果',f.context(request).model_summary())
