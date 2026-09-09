"""P17 normal C1 execution requirements, local effects and independent receipts."""
import tempfile
from pathlib import Path
import unittest
from dataclasses import replace
from datetime import timedelta
from continuity_engine.domain.execution import ExecutionError, Outcome, BlastRadius
from continuity_engine.domain.action_capability import ActionReceipt, ReceiptQuery
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.p17_execution_fixture import P17Fixture, run_golden


class ExecutionCase(unittest.TestCase):
    def fixture(self, **options):
        temp=tempfile.TemporaryDirectory(prefix='p17-test-')
        self.addCleanup(temp.cleanup)
        return P17Fixture(Path(temp.name),**options)

    def seeded(self, **options):
        f=self.fixture(**options)
        self.assertEqual(f.submit().status,'completed')
        return f


class ExecutionTests(ExecutionCase):
    def test_direct_c1_produces_one_effect_and_replays(self):
        from continuity_engine.testing.p17_execution_fixture import P17Fixture
        with tempfile.TemporaryDirectory() as directory:
            f = P17Fixture(Path(directory))
            request = f.request()
            self.assertEqual(f.submit(request).status, 'completed')
            self.assertIsNone(f.core.last_action.plan)
            self.assertEqual(f.fake.effect_count, 1)
            self.assertEqual(f.submit(request).status, 'completed')
            self.assertEqual(f.fake.effect_count, 1)

    def test_planner_c1_executes_both_dependencies(self):
        from continuity_engine.testing.p17_execution_fixture import P17Fixture
        with tempfile.TemporaryDirectory() as directory:
            f = P17Fixture(Path(directory), mode='complex')
            self.assertEqual(f.submit().status, 'completed')
            self.assertIsNotNone(f.core.last_action.plan)
            self.assertEqual(len(f.core.last_action.requests), 2)
            self.assertEqual(f.fake.effect_count, 2)

    def test_result_absorbed_via_next_thinking_action_evolution(self):
        f=self.seeded();revision=f.state.revision
        f.mode='absorb';result=f.next_round()
        self.assertEqual(result.status,'completed')
        self.assertEqual(f.state.revision,revision+1)
        self.assertEqual(f.state.continuity.current_focus,['understood isolated TEST effect'])
        self.assertTrue(any(x.source_type=='execution_result' for x in f.last_context.composition.snapshot.fragments))
        self.assertEqual(f.fake.effect_count,1)
        self.assertEqual(f.submit(f.last_request),result)
        self.assertEqual(f.state.revision,revision+1)

    def test_execution_does_not_directly_write_subject(self):
        f=self.fixture();before=f.state.to_dict()
        f.submit()
        self.assertEqual(f.state.to_dict(),before)

    def test_research_result_never_default_main_memory_or_state(self):
        f=self.fixture(world='RESEARCH');before=f.state.to_dict()
        f.submit();self.assertEqual(f.fake.effect_count,1)
        self.assertEqual(f.execution.results_for_context(),[])
        f.mode='absorb';f.next_round()
        self.assertFalse(any(x.source_type=='execution_result' for x in f.last_context.composition.snapshot.fragments))
        self.assertEqual(f.state.to_dict(),before)
        self.assertIn('research',f.fake.store.path.parts)

    def test_real_recovery_unavailable_zero_world_write(self):
        f=self.fixture(world='REAL');before=tree_inventory_hash(f.fake.root)
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(f.fake.execute_calls,0)
        self.assertEqual(tree_inventory_hash(f.fake.root),before)
        request=f.core.last_action.requests[0]
        with self.assertRaisesRegex(ExecutionError,'RECOVERABILITY_NOT_READY'):
            f.execution.current(request,f.routes[0],'execute')

    def test_research_unavailable_has_no_real_fallback(self):
        f=self.fixture(world='RESEARCH');f.boundary.available=False
        with self.assertRaises(IntegrationExecutionError):f.submit()
        request=f.core.last_action.requests[0]
        with self.assertRaisesRegex(ExecutionError,'RESEARCH_UNAVAILABLE'):
            f.execution.current(request,f.routes[0],'execute')
        self.assertEqual(f.fake.execute_calls,0)
        self.assertFalse((f.runtime.data_root/'worlds'/'real').exists())

    def test_receipts_once_and_single_e5a_channel(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        self.assertEqual(f.execution.request(request.capability_request_id),request)
        entry=f.outbox.load()['entries'][0]
        self.assertEqual(set(entry),{'request_id','request_hash','route_hash','state','attempts','receipt_hash','reason','links'})
        self.assertEqual(f.execution.query(request),f.execution.execute(request))
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)

    def test_wait_information_and_retry_are_auditable_not_dispatch(self):
        f=self.seeded();request,_=f.manual()
        before=f.fake.effect_count
        for kind in ('WAIT','REQUEST_INFORMATION','RETRY'):
            self.assertEqual(f.execution.alternative(request.capability_request_id,kind),kind)
        entry=f.outbox.load()['entries'][-1]
        self.assertEqual([x['kind'] for x in entry['links']],['WAIT','REQUEST_INFORMATION','RETRY'])
        self.assertEqual(f.fake.effect_count,before)

    def test_alternative_new_confirmation_and_no_old_dispatch(self):
        f=self.seeded();old,old_run=f.manual(decision='old-route')
        new,new_run=f.manual('execution.alternate',decision='new-route')
        f.execution.alternative(old.capability_request_id,'CHANGE_ROUTE',new.capability_request_id)
        self.assertEqual(new_run().status,'COMPLETED')
        self.assertEqual(old_run().status,'WAITING_CAPABILITY')
        self.assertEqual(f.fake.effect_count,2)

    def test_unknown_forbids_alternative_or_fake_cancellation(self):
        f=self.seeded();old,_=f.manual(decision='old-route');new,_=f.manual('execution.alternate',decision='new-route')
        f.fake.mode='unknown';before=f.fake.effect_count
        with self.assertRaisesRegex(ExecutionError,'UNKNOWN_ROUTE'):
            f.execution.alternative(old.capability_request_id,'CHANGE_ROUTE',new.capability_request_id)
        self.assertEqual(f.execution.cancel(old.capability_request_id),Outcome.UNKNOWN)
        self.assertEqual(f.fake.effect_count,before)

    def test_compensation_is_separate_receipted_action(self):
        f=self.seeded();original=f.core.last_action.requests[0];fact=f.execution.query(original)
        request,run=f.manual('execution.compensate',decision='compensation',argument_hash=digest(['compensate',fact.canonical_hash()]))
        f.execution.compensation(original.capability_request_id,request.capability_request_id)
        result=run();self.assertEqual(result.status,'COMPLETED')
        self.assertNotEqual(result.results[0].receipt.capability_request_id,fact.capability_request_id)
        self.assertEqual(f.execution.query(original),fact)
        self.assertEqual(f.fake.effect_count,2)
        self.assertEqual(run().status,'COMPLETED');self.assertEqual(f.fake.effect_count,2)

    def test_compensation_failure_preserves_original_fact(self):
        f=self.seeded();original=f.core.last_action.requests[0];fact=f.execution.query(original)
        request,run=f.manual('execution.compensate',argument_hash=digest(['compensate',fact.canonical_hash()]))
        f.execution.compensation(original.capability_request_id,request.capability_request_id)
        f.fake.mode='terminal';result=run()
        self.assertEqual(result.status,'FAILED');self.assertEqual(f.fake.effect_count,1)
        self.assertEqual(f.execution.query(original),fact)

    def test_compensation_unknown_preserves_original_fact(self):
        f=self.seeded();original=f.core.last_action.requests[0];fact=f.execution.query(original)
        request,run=f.manual('execution.compensate',argument_hash=digest(['compensate',fact.canonical_hash()]))
        f.execution.compensation(original.capability_request_id,request.capability_request_id)
        f.fake.mode='before_failure';self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(f.execution.query(original),fact);self.assertEqual(f.fake.effect_count,1)

    def test_compensation_requires_matching_original_receipt(self):
        f=self.seeded();original=f.core.last_action.requests[0]
        request,_=f.manual('execution.compensate')
        with self.assertRaisesRegex(ExecutionError,'COMPENSATION_BINDING'):
            f.execution.compensation(original.capability_request_id,request.capability_request_id)
        self.assertEqual(f.fake.effect_count,1)

    def test_compensation_without_link_cannot_execute(self):
        f=self.seeded();request,run=f.manual('execution.compensate')
        self.assertNotEqual(run().status,'COMPLETED')
        self.assertEqual(f.fake.effect_count,1)

    def test_cancel_pending_idempotent_and_no_dispatch(self):
        f=self.seeded();request,run=f.manual()
        self.assertEqual(f.execution.cancel(request.capability_request_id),Outcome.CANCELLED)
        before=f.outbox.path.read_bytes()
        self.assertEqual(f.execution.cancel(request.capability_request_id),Outcome.CANCELLED)
        self.assertEqual(f.outbox.path.read_bytes(),before)
        self.assertNotEqual(run().status,'COMPLETED');self.assertEqual(f.fake.effect_count,1)

    def test_completed_cannot_be_cancelled_or_replaced(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        before=f.outbox.path.read_bytes()
        self.assertEqual(f.execution.cancel(request.capability_request_id),Outcome.COMPLETED)
        with self.assertRaisesRegex(ExecutionError,'UNKNOWN_ROUTE'):
            f.execution.alternative(request.capability_request_id,'ABANDON')
        self.assertEqual(f.outbox.path.read_bytes(),before)

    def test_golden_real_three_process_restart_and_absorption(self):
        temp=tempfile.TemporaryDirectory(prefix='p17-process-');self.addCleanup(temp.cleanup)
        records=run_golden(Path(temp.name))
        self.assertEqual(len(records),3)
        self.assertTrue(all(r['exitCode']==0 for r in records))
