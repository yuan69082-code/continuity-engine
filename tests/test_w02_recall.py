from pathlib import Path
import tempfile
import unittest
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture
from continuity_engine.services.associative_recall_service import assess
from datetime import datetime,timezone


class AutomaticRecallTests(unittest.TestCase):
    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        capture_failure(self,self.root)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_original_message_is_assessed_before_thinking(self):
        f=W02RecallFixture(self.root); f.event('meal',content='我吃了午饭。')
        request=f.message('我又在吃螺蛳粉。'); f.submit(request)
        ctx=f.context(request)
        self.assertEqual(f.provider.calls,1)
        self.assertEqual(ctx.recall['status'],'READY')
        self.assertEqual(f.provider.inputs[0].continuity_context.recall,ctx.recall)
        self.assertTrue(any('meal' in r.stable_id for r in ctx.route.manifest.candidates))

    def test_no_relevant_cue_is_assessed_without_forced_recall(self):
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了午饭。')
        req=f.message('你好');f.submit(req)
        self.assertEqual(f.context(req).recall['stop_reason'],'NO_RELEVANT_CUE')
        self.assertFalse(any(r.source_id=='engine.memory' for r in f.context(req).route.manifest.candidates))

    def test_negative_preference_does_not_become_consumption(self):
        a=assess('我不爱吃螺蛳粉。',datetime(2026,9,24,tzinfo=timezone.utc))
        self.assertEqual(a['frames'][0]['modality'],'NEGATIVE_PREFERENCE_REPORT')
        self.assertFalse(a['frames'][0]['verified_fact'])

    def test_t03_raw_noon_and_afternoon_messages_recall_before_answer(self):
        from datetime import timedelta
        f=W02RecallFixture(self.root)
        f.event('old-meal',content='我以前吃过螺蛳粉。',occurred_at=f.runtime.clock.now()-timedelta(days=1))
        f.runtime.clock.advance(timedelta(hours=4))
        noon=f.message('我中午12点吃过午饭。');f.submit(noon)
        f.runtime.clock.advance(timedelta(hours=3))
        afternoon=f.message('我又在吃螺蛳粉。');f.submit(afternoon)
        ctx=f.context(afternoon)
        fragments=ctx.composition.snapshot.fragments
        self.assertTrue(any(noon['requestId'] in x.stable_source_id for x in fragments),
                        [(x.source_id,x.stable_source_id) for x in fragments])
        self.assertTrue(any('old-meal' in x.stable_source_id for x in fragments))
        noon_material=next(x for x in fragments if noon['requestId'] in x.stable_source_id)
        current_material=next(x for x in fragments if x.source_id=='engine.current-input')
        self.assertEqual((noon_material.occurred_at.hour,current_material.occurred_at.hour),(12,15))
        self.assertEqual(current_material.occurred_at-noon_material.occurred_at,timedelta(hours=3))
        self.assertIn('source_time',ctx.model_summary())
        self.assertEqual(f.provider.inputs[-1].continuity_context,ctx)
        self.assertIn('HUNGER_NOT_DETERMINED',ctx.recall['assessment']['assumptions'])

    def test_t05_variants_preserve_report_scope(self):
        cases=[('朋友在吃螺蛳粉。','OTHER_REPORTED','CONSUMPTION_REPORT'),
               ('我想吃但没吃。','SELF_REPORTED','NOT_CONSUMED_REPORT'),
               ('我去年吃过螺蛳粉。','SELF_REPORTED','CONSUMPTION_REPORT'),
               ('我说：“朋友在吃螺蛳粉。”','UNRESOLVED','QUOTED')]
        now=datetime(2026,9,24,tzinfo=timezone.utc)
        for text,actor,mode in cases:
            with self.subTest(text=text):
                frames=assess(text,now)['frames'];self.assertTrue(frames)
                self.assertEqual(frames[0]['modality'],mode)
                if mode!='QUOTED':self.assertEqual(frames[0]['actor'],actor)
        self.assertEqual(assess('我又在吃螺丝粉。',now)['frames'][0]['object'],'螺蛳粉')

    def test_t04_preference_candidate_uses_original_roots_without_state_write(self):
        f=W02RecallFixture(self.root)
        for i,text in enumerate(('我吃了螺蛳粉。','我又在吃螺蛳粉。','我喜欢螺蛳粉。')):
            event='meal-'+str(i);f.event(event,content=text)
            request=f.message(text,source_event_id=event);f.submit(request)
        ctx=f.context(request)
        candidates=ctx.recall['preference_candidates']
        self.assertTrue(candidates)
        candidate=candidates[0]
        self.assertEqual(candidate['status'],'UNCONFIRMED_CANDIDATE',candidate)
        self.assertEqual(len(candidate['independent_roots']),3)
        self.assertFalse(candidate['confirmed'])
        summary=f.core.memory.load_summary(f.core.subject_id,candidate['summary_id'])
        self.assertEqual(set(summary.root_evidence_ids),set(candidate['independent_roots']))
        count=len(f.core.memory.summary_history(f.core.subject_id,summary.summary_id))
        revision=f.runtime.subject_state().revision
        f.submit(request)
        self.assertEqual(f.runtime.subject_state().revision,revision)
        self.assertEqual(len(f.core.memory.summary_history(f.core.subject_id,summary.summary_id)),count)

    def test_read_only_recall_query_does_not_resume_or_write(self):
        from continuity_engine.testing.persistence import tree_inventory_hash
        f=W02RecallFixture(self.root);r=f.message('你好');f.submit(r)
        before=tree_inventory_hash(f.runtime.data_root)
        calls=f.provider.calls;effects=f.adapter.effect_count
        for _ in range(2):self.assertEqual(f.app.adapter.service.recall_outcome(r['requestId'])['status'],'READY')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual((f.provider.calls,f.adapter.effect_count),(calls,effects))

    def test_failure_and_reopen_resume_same_request(self):
        from unittest.mock import patch
        from continuity_engine.domain.errors import ContextCompositionSourceError
        f=W02RecallFixture(self.root);r=f.message('我又在吃螺蛳粉。')
        source=next(b.source for b in f.core.router._bindings if b.source.source_id=='engine.memory')
        with patch.object(source,'retrieve',side_effect=ContextCompositionSourceError('SOURCE_READ_FAILED')):
            with self.assertRaises(Exception):f.submit(r)
        self.assertEqual(f.provider.calls,0)
        self.assertEqual(f.app.adapter.service.recall_outcome(r['requestId'])['status'],'BLOCKED')
        f.reopen()
        self.assertEqual(f.app.adapter.service.recall_outcome(r['requestId'])['status'],'BLOCKED')
        f.submit(r);self.assertEqual(f.provider.calls,1)
        f.submit(r);self.assertEqual(f.provider.calls,1)
