"""P17 R1/R2: final delivery authorization and actual TEST charge bounds."""
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from test_p17_execution import ExecutionCase
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.execution import BlastRadius, ExecutionError
from continuity_engine.domain.action_capability import ActionReceipt, ReceiptQuery


class FinalAdmissionRepairTests(ExecutionCase):
    def final_resource_revocation(self, owner, field):
        f=self.fixture();revision=f.state.revision
        original=f.outbox.transaction;inside=False;final_checks=[]
        @contextmanager
        def transaction():
            nonlocal inside
            with original() as document:
                inside=True
                try:yield document
                finally:inside=False
        def revoke():
            if inside:
                final_checks.append('resource-check-under-dispatch-lock')
                setattr(getattr(f,owner),field,False)
        f.boundary.hook=revoke
        before=f.fake.store.path.read_bytes() if f.fake.store.path.exists() else None
        with patch.object(f.outbox,'transaction',transaction):
            with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(final_checks,['resource-check-under-dispatch-lock'])
        self.assertEqual(f.fake.effect_count,0);self.assertEqual(f.fake.credits,0)
        self.assertEqual(f.fake.execute_calls,0);self.assertEqual(f.state.revision,revision)
        self.assertEqual(f.fake.store.path.read_bytes() if f.fake.store.path.exists() else None,before)
        self.assertIs(f.execution.query(f.core.last_action.requests[0]),ReceiptQuery.NOT_EXECUTED)
        # Restoring permission is not implicit retry authorization. Keep the
        # original sealed request/Context and use the existing explicit retry.
        f.boundary.hook=None;setattr(getattr(f,owner),field,True)
        with self.assertRaises(IntegrationExecutionError):f.submit(f.last_request)
        self.assertEqual(f.fake.effect_count,0);self.assertEqual(f.fake.credits,0)
        request=f.core.last_action.requests[0]
        planner,choice,context=f.execution._contexts[(request.choice.decision_id,request.step_id)]
        retried=planner.run(choice,context,retry=True)
        self.assertEqual(retried.status,'COMPLETED')
        result=f.submit(f.last_request)
        self.assertEqual(result.status,'completed')
        self.assertEqual(f.submit(f.last_request),result)
        self.assertEqual(f.fake.effect_count,1);self.assertEqual(f.fake.credits,1)

    def test_final_resource_revokes_broker_zero_effect_and_charge(self):
        self.final_resource_revocation('broker','allowed')

    def test_final_resource_revokes_reality_zero_effect_and_charge(self):
        self.final_resource_revocation('boundary','allowed')

    def test_final_resource_revokes_recoverability_zero_effect_and_charge(self):
        self.final_resource_revocation('boundary','recovery_ready')

    def test_direct_execution_exposes_static_current_denial(self):
        for owner,field,reason in (('broker','allowed','PLATFORM_DENIAL'),
                ('boundary','allowed','REALITY_DENIAL'),('boundary','recovery_ready','RECOVERABILITY_NOT_READY')):
            with self.subTest(owner=owner,field=field):
                f=self.seeded();request,_=f.manual();before=f.fake.store.path.read_bytes()
                f.boundary.hook=lambda:setattr(getattr(f,owner),field,False)
                with self.assertRaisesRegex(ExecutionError,reason):f.execution.execute(request)
                self.assertEqual(f.fake.store.path.read_bytes(),before)
                self.assertEqual(f.fake.credits,1)

    def test_historical_fact_after_revocation_skips_new_resource_admission(self):
        f=self.seeded();request=f.core.last_action.requests[0];before=f.fake.store.path.read_bytes()
        f.broker.allowed=False;f.boundary.allowed=False;f.boundary.recovery_ready=False
        with patch.object(f.boundary,'capacity',side_effect=AssertionError('no new admission for old fact')):
            receipt=f.execution.execute(request)
            self.assertEqual(receipt.effect_count,1)
            self.assertEqual(f.submit(f.last_request).status,'completed')
        self.assertEqual(f.fake.store.path.read_bytes(),before)
        self.assertEqual(f.fake.execute_calls,1)


class ActualChargeRepairTests(ExecutionCase):
    def configured(self, cost=0, **limits):
        f=self.fixture(limits=BlastRadius(**limits))
        f.execution.routes={k:replace(v,cost=cost) for k,v in f.execution.routes.items()}
        f.reopen();return f

    def assert_fact_usage(self,f,effects,credits):
        document=f.fake.store.load()
        self.assertEqual(f.fake.effect_count,effects);self.assertEqual(f.fake.credits,credits)
        self.assertEqual(sum(row['receipt']['test_credits'] for row in document['facts']),credits)
        self.assertEqual(sum(row['receipt']['effect_count'] for row in document['facts']),effects)

    def test_zero_estimated_cost_has_explicit_one_credit_fake_charge(self):
        f=self.configured(credits=1);self.assertEqual(f.submit().status,'completed')
        self.assert_fact_usage(f,1,1)
        before=f.fake.store.path.read_bytes()
        with self.assertRaises(IntegrationExecutionError):f.next_round()
        self.assert_fact_usage(f,1,1);self.assertEqual(f.fake.store.path.read_bytes(),before)

    def test_default_cost_exact_budget_then_next_rejected(self):
        f=self.configured(cost=1,credits=1);self.assertEqual(f.submit().status,'completed')
        self.assert_fact_usage(f,1,1)
        with self.assertRaises(IntegrationExecutionError):f.next_round()
        self.assert_fact_usage(f,1,1)

    def test_zero_cost_capacity_uses_actual_projection_without_writes(self):
        f=self.configured(credits=1);f.submit();request,_=f.manual();route=f.execution.routes[request.capability_type]
        before=f.fake.store.path.read_bytes();projected,receipt=f.fake.projected_document(request,f.fake.store.load())
        self.assertEqual(projected['credits'],2);self.assertEqual(receipt.test_credits,1)
        self.assertFalse(f.boundary.capacity(route,request,f.execution.limits))
        self.assertEqual(f.fake.store.path.read_bytes(),before)

    def test_duplicate_zero_cost_request_does_not_repeat_effect_or_charge(self):
        f=self.configured(credits=1);result=f.submit();before=f.fake.store.path.read_bytes()
        f.reopen();self.assertEqual(f.submit(f.last_request),result)
        self.assertEqual(f.fake.store.path.read_bytes(),before);self.assert_fact_usage(f,1,1)

    def test_zero_cost_still_respects_request_and_message_limits(self):
        for limits in ({'requests':1},{'messages':1}):
            with self.subTest(limits=limits):
                f=self.configured(**limits);f.submit();before=f.fake.store.path.read_bytes()
                with self.assertRaises(IntegrationExecutionError):f.next_round()
                self.assertEqual(f.fake.store.path.read_bytes(),before);self.assert_fact_usage(f,1,1)

    def test_zero_cost_respects_exact_serialized_storage_limit(self):
        f=self.configured();f.submit();request,run=f.manual()
        limit=f.fake.projected_size(request);f.execution.limits=BlastRadius(storage_bytes=limit)
        self.assertEqual(run().status,'COMPLETED');self.assertEqual(f.fake.store.path.stat().st_size,limit)
        before=f.fake.store.path.read_bytes();_,later=f.manual(decision='beyond-storage')
        self.assertNotEqual(later().status,'COMPLETED')
        self.assertEqual(f.fake.store.path.read_bytes(),before);self.assert_fact_usage(f,2,2)

    def test_failed_receipt_at_credit_and_message_limit_has_zero_extra_usage(self):
        f=self.configured(cost=1,credits=1,messages=1);f.submit();f.fake.mode='terminal'
        request,run=f.manual();run()
        fact=f.execution.query(request)
        self.assertIsInstance(fact,ActionReceipt,'A zero-usage terminal result still requires a real receipt')
        self.assertEqual(fact.status,'FAILED_TERMINAL')
        self.assertEqual(fact.test_credits,0);self.assertEqual(fact.effect_count,0)
        self.assert_fact_usage(f,1,1);self.assertEqual(len(f.fake.store.load()['facts']),2)
