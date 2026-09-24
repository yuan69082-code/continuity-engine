from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.associative_recall import RecallPolicy
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.context_routing import ContextSourceBatch
from continuity_engine.domain.errors import IntegrationExecutionError,CapabilityValidationError
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.w02_input_fixture import W02InputFixture,capture_failure
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture


class RecallBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def tearDown(self):capture_failure(self,self.root)

    def test_disabled_gate_preserves_original_round_trip(self):
        from continuity_engine.domain.integration_results import IntegrationOperationRecord
        f=W02InputFixture(self.root);r=f.message('我吃了午饭');f.submit(r)
        raw=f.app.ledger.load_operation(r['requestId']).to_dict()
        self.assertNotIn('recallEnabled',raw)
        self.assertNotIn('recallProgress',raw['domainProgress'])
        self.assertNotIn('recall',f.context(r).to_dict())
        self.assertEqual(IntegrationOperationRecord.from_dict(raw).to_dict(),raw)

    def test_timeout_is_blocked_before_model_and_query_is_read_only(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(latency_ms=1))
        r=f.message('我吃了午饭')
        with patch.object(f.core.recall,'timer',side_effect=[0,0,0.01,0.01]):
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(0,0,0))
        before=tree_inventory_hash(f.runtime.data_root)
        view=f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(view['record']['stop_reason'],'RECALL_TIMEOUT')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_reference_withdrawal_prevents_new_model(self):
        f=W02RecallFixture(self.root);r=f.message('我吃了午饭')
        def fail(stage,operation):
            if stage=='after_perception_checkpoint_saved':raise RuntimeError('CONTROLLED_CHECKPOINT')
        f.app.adapter.service._fault_injector=fail
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        f.permission.references_allowed=False;f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(0,0,0))
        with self.assertRaises(CapabilityValidationError):f.app.adapter.service.recall_outcome(r['requestId'])

    def test_stale_context_does_not_authorize_resume(self):
        f=W02RecallFixture(self.root);r=f.message('我吃了午饭')
        def fail(stage,operation):
            if stage=='after_perception_checkpoint_saved':raise RuntimeError('CONTROLLED_CHECKPOINT')
        f.app.adapter.service._fault_injector=fail
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        f.runtime.clock.advance(timedelta(minutes=11));f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.provider.calls,0)

    def test_ready_preparation_return_lost_reuses_receipt(self):
        f=W02RecallFixture(self.root);r=f.message('你好')
        def fail(stage,operation):
            if stage=='after_input_checkpoint_saved' and operation.domain_progress.input_preparation.continuity_context is not None:
                raise RuntimeError('CONTROLLED_READY_RETURN_LOST')
        f.app.adapter.service._fault_injector=fail
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        before=f.app.ledger.load_operation(r['requestId']).domain_progress.recall_progress
        self.assertEqual(len(before),1)
        f.reopen()
        with patch.object(f.core.recall,'prepare',side_effect=AssertionError('must reuse READY')):f.submit(r)
        self.assertEqual(f.app.ledger.load_operation(r['requestId']).domain_progress.recall_progress,before)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(1,1,1))

    def test_corrupt_recall_hash_is_refused_without_writes(self):
        f=W02RecallFixture(self.root);r=f.message('你好');f.submit(r)
        path=f.app.ledger.operation_path; data=json.loads(path.read_text())
        def corrupt(value):
            if isinstance(value,dict):
                if value.get('version')=='w02-recall-v1':value['stop_reason']='FORGED'
                for x in value.values():corrupt(x)
            elif isinstance(value,list):
                for x in value:corrupt(x)
        corrupt(data);path.write_text(json.dumps(data),encoding='utf-8')
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(Exception):f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_wrong_subject_record_is_rejected(self):
        from continuity_engine.domain.associative_recall import seal_record,validate_record
        f=W02RecallFixture(self.root);r=f.message('你好');f.submit(r)
        op=f.app.ledger.load_operation(r['requestId']);record=f.context(r).recall
        forged=seal_record({**{k:v for k,v in record.items() if k!='record_hash'},'subject_id':'other'})
        with self.assertRaises(CapabilityValidationError):validate_record(forged,operation=op)

    def test_no_match_is_distinct_from_source_failure(self):
        f=W02RecallFixture(self.root);r=f.message('量子光学项目')
        f.submit(r);record=f.context(r).recall
        self.assertEqual(record['status'],'READY')
        self.assertIn(record['stop_reason'],('NO_MATCH','RELEVANCE_INSUFFICIENT'))
        self.assertFalse(any(x['reasons'] for x in record['rounds']))

    def test_retrieval_and_context_budgets_are_independent(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(candidate_limit=30,per_round_limit=12,max_rounds=1),
                           context_budget=ContextBudget(token_limit=600))
        for i in range(5):f.event('meal'+str(i),content='我吃了午饭。')
        r=f.message('我又吃了午饭');f.submit(r);ctx=f.context(r)
        self.assertLessEqual(ctx.recall['retrieved_count'],30)
        self.assertLessEqual(ctx.composition.trace.tokens_used,600)
        self.assertTrue(ctx.composition.snapshot.missing_notices)
        self.assertEqual((ctx.recall['model_calls'],ctx.recall['external_calls']),(0,0))

    def test_bound_policy_does_not_force_fixed_depth(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(max_rounds=7))
        r=f.message('你好');f.submit(r)
        self.assertEqual(len(f.context(r).recall['rounds']),1)

    def test_stale_source_version_cannot_be_consumed(self):
        from continuity_engine.services.context_router_service import ContextSourceValidation
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了午饭');r=f.message('我又在吃午饭')
        source=next(b.source for b in f.core.router._bindings if b.source.source_id=='engine.memory')
        with patch.object(source,'revalidate',return_value=ContextSourceValidation(False,'STALE_INDEX','stale','stale','sha256:'+'0'*64)):
            f.submit(r)
        self.assertTrue(any(d.reason_code=='STALE_INDEX' for d in f.context(r).route.trace.candidate_decisions))
        self.assertFalse(any(x.source_id=='engine.memory' for x in f.context(r).composition.snapshot.fragments))

    def test_source_revocation_excludes_memory_and_history_projection(self):
        from continuity_engine.domain.events import EventClassification,EventReference,EventRelationType
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了螺蛳粉')
        r=f.message('我吃了螺蛳粉',source_event_id='meal');f.submit(r)
        f.event('revoke',classification=EventClassification.REVOCATION,
                references=(EventReference('meal',f.core.subject_id,EventRelationType.REVOKES),))
        new=f.message('我又在吃螺蛳粉');f.submit(new)
        refs=f.context(new).route.manifest.candidates
        self.assertFalse(any(x.stable_id in {'meal','memory:meal','input:'+r['requestId']} for x in refs))

    def test_native_cognition_uses_same_pre_answer_evaluation(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f=P14Fixture(self.root,gates=ContinuityCoreGates(input_processing=True,automatic_recall=True))
        f.runtime.clock.advance(timedelta(hours=1))
        result=f.opportunity('w02-native-recall')
        self.assertEqual(result.perception.continuity_context.recall['status'],'READY')
        self.assertEqual(result.perception.continuity_context.recall['assessment']['actor'],'SUBJECT_INTERNAL_CUE')

    def test_actual_effect_return_lost_replays_without_duplicate(self):
        f=W02RecallFixture(self.root);r=f.message('你好')
        def fail(stage,operation):
            if stage=='after_c1_action_completed':raise RuntimeError('CONTROLLED_EFFECT_RETURN_LOST')
        f.app.adapter.service._fault_injector=fail
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(1,1,1))
        f.reopen();f.submit(r)
        self.assertEqual((f.provider.calls,f.adapter.execute_calls,f.adapter.effect_count,f.adapter.credits),(0,0,1,1))
