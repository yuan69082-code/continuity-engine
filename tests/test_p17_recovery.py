"""Crash and delivery history verification, independent Fake fact controls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import patch
from test_p17_execution import ExecutionCase
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.execution import ExecutionError, Outcome
from continuity_engine.domain.errors import IntegrationExecutionError


class RecoveryTests(ExecutionCase):
    def test_lost_response_queries_before_retry_no_second_effect(self):
        f=self.fixture();f.fake.mode='lost_response';request=f.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.fake.effect_count,1)
        f.fake.mode='success';calls=f.fake.execute_calls
        self.assertEqual(f.submit(request).status,'completed')
        self.assertEqual(f.fake.execute_calls,calls);self.assertEqual(f.fake.credits,1)

    def test_crash_before_world_can_resume_only_with_current_gates(self):
        f=self.fixture();request=f.request()
        def fault(point):
            if point=='before_adapter':raise RuntimeError('P17_INJECTED_PRE_DISPATCH')
        f.core.fault=fault
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.fake.effect_count,0)
        f.core.fault=None;f.constraints.confirmation_allowed=False
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.fake.effect_count,0)

    def test_crash_after_effect_recovers_after_revocation(self):
        f=self.fixture();request=f.request()
        def fault(point):
            if point=='after_adapter_before_result':raise RuntimeError('P17_INJECTED_POST_EFFECT')
        f.core.fault=fault
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        f.core.fault=None;f.broker.allowed=False
        self.assertEqual(f.submit(request).status,'completed')
        self.assertEqual(f.fake.effect_count,1)
        with self.assertRaises(ExecutionError):f.execution.results_for_context()

    def test_delivery_checkpoint_loss_never_skips_receipt_verification(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        with f.outbox.transaction() as d:
            d['entries']=[];f.outbox.save(d)
        f.fake.mode='unknown'
        with self.assertRaises(Exception):f.submit(f.last_request)
        self.assertEqual(f.fake.effect_count,1)

    def test_receipt_conflict_fails_closed_on_replay(self):
        f=self.seeded();f.fake.receipt_hook=lambda r:replace(r,output_hash=digest('tampered'))
        with self.assertRaises(Exception):f.submit(f.last_request)
        self.assertEqual(f.fake.effect_count,1)

    def test_same_identity_different_world_target_hash_rejected(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        for changed in (replace(request,policy_hash=digest('changed')),
                        replace(request,choice=replace(request.choice,environment='RESEARCH')),
                        replace(request,choice=replace(request.choice,steps=(replace(request.step,target='another'),)))):
            with self.subTest(changed=changed.request_hash):
                with self.assertRaises(ExecutionError):f.execution.query(changed)
        self.assertEqual(f.fake.effect_count,1)

    def test_corrupt_outbox_rejected_without_repair(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        f.outbox.path.write_text('{damaged',encoding='utf-8');before=f.outbox.path.read_bytes()
        with self.assertRaisesRegex(ExecutionError,'OUTBOX_CORRUPT'):f.execution.query(request)
        self.assertEqual(f.outbox.path.read_bytes(),before);self.assertEqual(f.fake.effect_count,1)

    def test_rehashed_wrong_request_binding_rejected(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        with f.outbox.transaction() as d:
            d['entries'][0]['route_hash']=digest('wrong route');f.outbox.save(d)
        with self.assertRaisesRegex(ExecutionError,'OUTBOX_BINDING'):f.execution.query(request)
        self.assertEqual(f.fake.effect_count,1)

    def test_atomic_write_failure_precedes_world_effect(self):
        f=self.seeded();request,_=f.manual();before=f.outbox.path.read_bytes()
        with patch('continuity_engine.storage.json_execution_outbox.os.replace',side_effect=OSError('TEST_ATOMIC_FAILURE')):
            with self.assertRaises(OSError):f.execution.execute(request)
        self.assertEqual(f.outbox.path.read_bytes(),before);self.assertEqual(f.fake.effect_count,1)

    def test_two_workers_compete_without_duplicate_effect_or_credit(self):
        f=self.seeded();request,_=f.manual()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(f.execution.execute,[request,request]))
        self.assertEqual(results[0],results[1]);self.assertEqual(f.fake.effect_count,2);self.assertEqual(f.fake.credits,2)

    def test_unknown_and_untyped_nonexecution_never_dispatch(self):
        for mode in ('unknown','untyped','query_exception'):
            with self.subTest(mode=mode):
                f=self.fixture();f.fake.mode=mode
                with self.assertRaises(IntegrationExecutionError):f.submit()
                self.assertEqual(f.fake.execute_calls,0);self.assertEqual(f.fake.effect_count,0)

    def test_bounded_retries_after_explicit_not_executed(self):
        f=self.seeded();request,run=f.manual();f.fake.mode='before_failure'
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(run(retry=True).status,'WAITING_CAPABILITY')
        calls=f.fake.execute_calls
        self.assertEqual(run(retry=True).status,'WAITING_CAPABILITY')
        self.assertEqual(f.fake.execute_calls,calls)
        self.assertEqual(f.outbox.load()['entries'][-1]['attempts'],2)

    def test_cancel_after_unknown_with_actual_success_returns_completed(self):
        f=self.fixture();f.fake.mode='lost_response';request=f.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        action=f.core.last_action.requests[0]
        self.assertEqual(f.execution.cancel(action.capability_request_id),Outcome.COMPLETED)
        f.fake.mode='success';self.assertEqual(f.submit(request).status,'completed')
        self.assertEqual(f.fake.effect_count,1)

    def test_completed_fact_replay_after_choice_expiry_has_no_dispatch(self):
        f=self.seeded();request=f.last_request;calls=f.fake.execute_calls
        f.runtime.clock.advance(timedelta(minutes=11))
        self.assertEqual(f.submit(request).status,'completed')
        self.assertEqual(f.fake.execute_calls,calls)

    def test_two_real_process_workers_use_same_dispatch_identity(self):
        import os,subprocess,sys
        from continuity_engine.testing.persistence import atomic_write_json
        f=self.seeded();request,_=f.manual()
        atomic_write_json(f.root/'p17-golden.json',{'sandbox_id':f.runtime.descriptor.sandbox_id,
                'request':f.last_request,'worker_request_id':request.capability_request_id})
        command=[sys.executable,'-m','continuity_engine.testing.p17_execution_fixture','--root',str(f.root),'--phase','worker']
        children=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}) for _ in range(2)]
        rows=[]
        for child in children:
            stdout,stderr=child.communicate(timeout=60)
            print(json.dumps({'command':command,'exitCode':child.returncode,'stdout':stdout,'stderr':stderr}))
            self.assertEqual(child.returncode,0,stderr)
            rows.append(json.loads(stdout))
        self.assertTrue(any('receipt_hash' in row for row in rows))
        self.assertEqual(f.fake.effect_count,2);self.assertEqual(f.fake.credits,2)

    def test_cancel_dispatch_race_respects_observed_fact(self):
        f=self.seeded();request,_=f.manual()
        def execute():
            try:return f.execution.execute(request)
            except ExecutionError as exc:
                self.assertIn(str(exc),('EXECUTION_CANCELLED','CANCELLED'));return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            execution=pool.submit(execute)
            cancelled=pool.submit(f.execution.cancel,request.capability_request_id)
            fact=execution.result();status=cancelled.result()
        if fact is not None:
            self.assertEqual(status,Outcome.COMPLETED);self.assertEqual(f.fake.effect_count,2)
        else:
            self.assertEqual(status,Outcome.CANCELLED);self.assertEqual(f.fake.effect_count,1)

    def test_compensation_crash_after_effect_recovers_without_duplicate(self):
        f=self.seeded();original=f.core.last_action.requests[0];fact=f.execution.query(original)
        request,run=f.manual('execution.compensate',argument_hash=digest(['compensate',fact.canonical_hash()]))
        f.execution.compensation(original.capability_request_id,request.capability_request_id)
        def fault(point):
            if point=='after_world_before_delivery':raise RuntimeError('P17_COMPENSATION_CRASH')
        f.execution.fault=fault
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,2)
        f.execution.fault=lambda point:None
        self.assertEqual(run().status,'COMPLETED');self.assertEqual(f.fake.effect_count,2)
        self.assertEqual(f.execution.query(original),fact)

    def test_cancel_survives_missing_delivery_index_without_redispatch(self):
        f=self.seeded();request,run=f.manual()
        self.assertEqual(f.execution.cancel(request.capability_request_id),Outcome.CANCELLED)
        with f.outbox.transaction() as d:
            d['entries']=[e for e in d['entries'] if e['request_id']!=request.capability_request_id]
            f.outbox.save(d)
        self.assertNotEqual(run(retry=True).status,'COMPLETED')
        self.assertEqual(f.fake.effect_count,1)
