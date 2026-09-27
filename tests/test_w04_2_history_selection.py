"""Explicit history targets through the real device/result/Router/Composer chain."""
import json
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_capability import ActionReceipt
from continuity_engine.domain.environment_access import EnvironmentAccessError
from continuity_engine.domain.execution import ExecutionError
from continuity_engine.domain.integration_results import format_contract_datetime as fmt
from continuity_engine.testing.w04_device_fixture import W04DeviceFixture
from continuity_engine.testing.persistence import tree_inventory_hash


class HistorySelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='w4hs-')
        self.addCleanup(self.tmp.cleanup)
        self.f=W04DeviceFixture(Path(self.tmp.name))
        self.assertEqual(self.f.submit().status,'completed')
        f=self.f;now=f.runtime.clock.now()
        self.row=dict(source_id='source:one',root_id='root:one',version='v1',readable=True,
            software_id='software:a',device_id='device:a',session_id='session:a',object_id='object:continuity',
            occurred_at=fmt(now),expires_at=fmt(now+timedelta(hours=1)),content='continuity same root')
        f.fake.change(history=[self.row])

    def query(self,identity):
        f=self.f
        request,run=f.prepare(f.command('query',history=asdict(f.scope(query_id=identity))),decision=identity)
        result=run();f.execution.collect(result)
        self.assertEqual(result.results[0].status.value,'SUCCEEDED')
        return request

    def context(self,request):
        f=self.f
        perception=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
        return f.device.history_context(request.capability_request_id,perception)

    def assert_context(self,request):
        c=self.context(request)
        self.assertTrue(c.snapshot.consumable)
        self.assertTrue(any(x.stable_source_id=='execution:'+request.capability_request_id for x in c.snapshot.fragments))
        self.assertTrue(any(x.protected for x in c.snapshot.fragments))
        self.assertEqual(c.trace.budget.token_limit,2048)
        targets=[x for x in c.snapshot.fragments if x.source_type=='execution_result']
        self.assertEqual({r for x in targets for r in x.provenance_roots},{'external-history:root:one'})
        self.assertTrue(all('SIMULATED_RESULT_OBSERVATION' in x.conflict_markers for x in targets))
        return c

    def test_two_current_targets_both_orders_and_distinct_identifiers(self):
        requests=[self.query(identity) for identity in ('query:Z-final','query:a.other-second')]
        before=tree_inventory_hash(self.f.runtime.data_root)
        for request in (*requests,*reversed(requests)):
            with self.subTest(target=request.capability_request_id):self.assert_context(request)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)
        self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(0,0))

    def test_reopen_and_same_query_replay_keep_original_facts(self):
        requests=[self.query('query:reopen-'+str(i)) for i in range(2)]
        f=self.f;before=(f.state.revision,f.fake.effect_count,f.fake.credits,len(f.fake.store.load()['facts']))
        f.reopen()
        for request in requests:
            self.assert_context(request)
            self.assertIsInstance(f.execution.query(request),ActionReceipt)
        self.assertEqual((f.state.revision,f.fake.effect_count,f.fake.credits,len(f.fake.store.load()['facts'])),before)

    def test_target_that_cannot_fit_is_blocked_without_substituting_other_receipt(self):
        requests=[self.query('query:budget-'+str(i)) for i in range(2)]
        f=self.f;before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.core,'context_budget',replace(f.core.context_budget,token_limit=128)):
            for request in requests:
                with self.assertRaisesRegex(EnvironmentAccessError,'DEVICE_HISTORY_CONTEXT_NOT_READY'):self.context(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_revoked_permission_rejects_and_does_not_consume_old_receipt(self):
        request=self.query('query:revoked');self.assert_context(request)
        f=self.f;f.history_allowed=False;before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaisesRegex(ExecutionError,'^DEVICE_SOURCE_NOT_CURRENT$'):self.context(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertIsInstance(f.execution.query(request),ActionReceipt)

    def test_permission_revoked_during_composition_rejects_before_return(self):
        request=self.query('query:mid-revoke');f=self.f;original=f.core.composer.compose
        def revoke(*args,**kw):
            result=original(*args,**kw);f.history_allowed=False;return result
        before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.core.composer,'compose',revoke):
            with self.assertRaisesRegex(ExecutionError,'^DEVICE_SOURCE_NOT_CURRENT$'):self.context(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_expired_source_rejects_while_historical_receipt_is_preserved(self):
        request=self.query('query:expired');f=self.f
        f.runtime.clock.advance(timedelta(hours=1))
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaisesRegex(ExecutionError,'^DEVICE_SOURCE_NOT_CURRENT$'):self.context(request)
        self.assertIsInstance(f.execution.query(request),ActionReceipt)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_withdrawn_source_cannot_be_replaced_by_other_same_root_copy(self):
        first=self.query('query:withdraw-one');f=self.f
        f.fake.change(history=[self.row,{**self.row,'source_id':'source:copy'}])
        second=self.query('query:withdraw-two')
        f.fake.change(history=[self.row])
        self.assert_context(first)
        with self.assertRaisesRegex(ExecutionError,'^DEVICE_SOURCE_NOT_CURRENT$'):self.context(second)
        self.assertIsInstance(f.execution.query(second),ActionReceipt)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_non_targeted_result_source_keeps_original_candidate_ranking(self):
        requests=[self.query('query:ordinary-'+str(i)) for i in range(2)]
        f=self.f
        from continuity_engine.services.execution_context_source import ExecutionContextSource
        from continuity_engine.services.context_router_service import ContextSourceQuery
        source=ExecutionContextSource(f.execution)
        query=ContextSourceQuery('ordinary:read',f.state.subject_id,'TEST',f.state.revision,
            f.runtime.clock.now(),('memory',),('continuity',),30)
        batch=source.retrieve(query)
        self.assertEqual({c.stable_id for c in batch.candidates},{'execution:'+r.capability_request_id for r in requests})
        self.assertTrue(all((c.relevance,c.importance,c.activation)==(.95,.8,0) for c in batch.candidates))

    def test_target_priority_keeps_other_candidates_and_conflict_material(self):
        requests=[self.query('query:priority-'+str(i)) for i in range(2)];f=self.f
        from continuity_engine.services.execution_context_source import ExecutionContextSource,history_context_request_id
        source=ExecutionContextSource(f.execution);original=source.__class__.retrieve;observed=[]
        def capture(self,query):
            batch=original(self,query)
            if query.request_id==history_context_request_id(requests[-1].capability_request_id):observed.append(batch)
            return batch
        with patch.object(source.__class__,'retrieve',capture):self.assert_context(requests[-1])
        self.assertTrue(observed)
        for batch in observed:
            self.assertEqual(batch.candidates[0].stable_id,'execution:'+requests[-1].capability_request_id)
            self.assertEqual({c.stable_id for c in batch.candidates},{'execution:'+r.capability_request_id for r in requests})
            other=next(c for c in batch.candidates if c.stable_id=='execution:'+requests[0].capability_request_id)
            self.assertEqual((other.relevance,other.importance,other.activation),(.95,.8,0))


if __name__=='__main__':unittest.main()
