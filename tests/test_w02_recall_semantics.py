from pathlib import Path
import tempfile
import unittest

from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture


class RecallEventScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def tearDown(self):capture_failure(self,self.root)

    def preference(self,text):
        f=W02RecallFixture(self.root)
        f.event('unrelated-meal',content='我吃了午饭。')
        r=f.message(text);f.submit(r)
        ctx=f.context(r)
        self.assertEqual(f.provider.inputs[-1].continuity_context,ctx)
        self.assertEqual(ctx.recall['assessment']['frames'][0]['event'],'preference')
        self.assertFalse({'吃','饭','进食','用餐','meal'} & set(ctx.recall['assessment']['query_terms']))
        self.assertFalse(any('unrelated-meal' in x.stable_source_id for x in ctx.composition.snapshot.fragments))
        self.assertFalse(any(step['associations'] for step in ctx.recall['rounds']))
        return ctx

    def test_color_preference_is_not_a_meal_in_real_response_context(self):
        ctx=self.preference('我喜欢其他颜色。')
        self.assertEqual(ctx.recall['assessment']['frames'][0]['actor'],'SELF_REPORTED')

    def test_music_preference_is_not_a_meal_in_real_response_context(self):
        ctx=self.preference('我喜欢音乐。')
        self.assertEqual(ctx.recall['assessment']['frames'][0]['modality'],'POSITIVE_PREFERENCE_REPORT')

    def test_quoted_preference_is_not_consumption_or_verified_fact(self):
        ctx=self.preference('我说：“我喜欢音乐。”')
        frame=ctx.recall['assessment']['frames'][0]
        self.assertEqual(frame['modality'],'QUOTED')
        self.assertFalse(frame['verified_fact'])
        self.assertTrue(ctx.recall['assessment']['uncertain'])

    def test_food_preference_recalls_same_object_without_other_meal_expansion(self):
        f=W02RecallFixture(self.root)
        f.event('same-food',content='我以前吃过螺蛳粉。')
        f.event('different-meal',content='我吃了午饭。')
        r=f.message('我喜欢螺蛳粉。');f.submit(r)
        ctx=f.context(r);frame=ctx.recall['assessment']['frames'][0]
        self.assertEqual(f.provider.inputs[-1].continuity_context,ctx)
        self.assertEqual((frame['event'],frame['modality']),('preference','POSITIVE_PREFERENCE_REPORT'))
        self.assertFalse(frame['verified_fact'])
        self.assertTrue(any('same-food' in x.stable_source_id for x in ctx.composition.snapshot.fragments))
        self.assertFalse(any('different-meal' in x.stable_source_id for x in ctx.composition.snapshot.fragments))
        self.assertFalse(any(step['associations'] for step in ctx.recall['rounds']))
