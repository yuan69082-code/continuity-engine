"""Separate internal cognition facts from independently gated world effects."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class AutonomyExecutionTests(unittest.TestCase):
    def test_platform_denial_preserves_intent_without_dispatch(self):
        from continuity_engine.testing.p13_expression_fixture import P13Fixture
        with tempfile.TemporaryDirectory(prefix='ap-') as directory:
            f=P13Fixture(Path(directory),mode='complex',expression_mode='REFUSE')
            f.app.adapter.service._available_permissions=()
            request=f.request();before=f.state.to_dict();f.submit(request)
            operation=f.app.ledger.load_operation(request['requestId'])
            progress=operation.domain_progress
            thinking=f.app.adapter.service._restore_domain_thinking(operation)
            choice=f.core.policy.choose(operation,progress.perception.continuity_context,
                                        thinking,progress.action)
            self.assertIsNotNone(choice)
            self.assertFalse(progress.action.decision.approved)
            self.assertEqual(f.artifact(request).decision.status,'PLATFORM_DENIED')
            self.assertEqual((f.adapter.execute_calls,f.adapter.effect_count,f.adapter.credits),(0,0,0))
            self.assertEqual(f.presentation.calls,0)
            self.assertEqual(f.state.to_dict(),before)
            self.assertEqual(f.core.coordination.action_requests_by_decision(choice.decision_id),[])
            f.reopen();f.submit(request)
            self.assertEqual((f.provider.calls,f.adapter.execute_calls,f.adapter.effect_count,f.adapter.credits),(0,0,0,0))
            self.assertEqual(f.state.to_dict(),before)

    def test_unresolved_world_does_not_exhaust_cognition_queue(self):
        f=self.fixture();f.fake.mode='unknown'
        f.scheduler._capacity=2;f.scheduler._resource_scan_limit=2
        with f.host.running():
            self.step(f);before=f.state.revision
            for _ in range(8):f.advance(300);f.host.tick()
            self.assertGreaterEqual(f.state.revision,before+3)
            self.assertEqual((f.fake.execute_calls,f.fake.effect_count,f.fake.credits),(0,0,0))
            self.assertNotEqual(f.core.last_action.status,'COMPLETED')
            f.control('STOP')

    def test_mixed_provider_proposal_cannot_assert_an_unperformed_effect(self):
        from continuity_engine.domain.events import StateMutation, ChangeOperation
        f=self.fixture();f.boundary.allowed=False
        original=f.provider.think
        def mixed(*args):
            result=original(*args)
            return replace(result,update_subject_state=True,proposed_mutations=[
                StateMutation('continuity.current_focus',ChangeOperation.SET,'contact delivered','premature outcome')])
        f.provider.think=mixed
        with f.host.running():
            before=f.state.continuity.current_focus
            self.step(f)
            self.assertIsNotNone(f.state.intentions.dynamic_mind)
            self.assertEqual(f.state.continuity.current_focus,before)
            session=f.work.thinking.get_sessions(f.state.subject_id)[-1]
            self.assertTrue(any(m.field_path=='continuity.current_focus' for m in session.result.proposed_mutations))
            self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            f.control('STOP')

    def test_normal_c1_input_preserves_internal_commit_on_reality_refusal(self):
        f=self.fixture();f.boundary.allowed=False;f.advance(3600)
        # The host-neutral submit entry uses the same C1 / Action / Evolution.
        f.core.expression_policy=None
        before=f.state.revision
        with f.host.running():
            f.submit()
            f.control('STOP')
        self.assertEqual(f.state.revision,before+1)
        self.assertIsNotNone(f.state.intentions.dynamic_mind)
        self.assertNotEqual(f.core.last_action.status,'COMPLETED')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_refused_effect_internal_commit_survives_crashes_before_and_after_write(self):
        class Crash(BaseException):pass
        for point in ('after_native_effect','after_native_evolution'):
            with self.subTest(point=point):
                f=self.fixture();f.boundary.allowed=False;before=f.state.revision
                def fault(stage):
                    if stage==point:raise Crash()
                with self.assertRaises(Crash):
                    with f.host.running():
                        f.advance(3600);f.host.tick();f.advance(60);f.fault=fault;f.host.tick()
                f=P18Fixture(f.root,initialize=False);f.boundary.allowed=False
                with f.host.running():
                    f.host.tick()
                    self.assertEqual(f.state.revision,before+1)
                    self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(0,0,0))
                    f.control('STOP')

    def test_stale_context_still_prevents_new_internal_commit(self):
        f=self.fixture();before=f.state.revision
        f.provider.hook=lambda:f.advance(1000)
        with f.host.running():
            self.step(f)
            self.assertEqual(f.state.revision,before)
            self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            f.control('STOP')

    def test_unknown_after_lost_response_recovers_receipt_without_repeating_effect(self):
        f=self.fixture();f.fake.mode='lost_response'
        with f.host.running():
            self.step(f);revision=f.state.revision
            self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
            f.host.tick()
            self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
            self.assertEqual(f.state.revision,revision)
            f.control('STOP')

    def test_denied_reality_keeps_experience_formed_commitment_for_next_cognition(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.fixture();f.boundary.allowed=False;f.core.context_budget=ContextBudget(token_limit=8000)
        for key in ('care-one','care-two'):
            P14Fixture.affective_event(f,key,object_id='peer',observation='expectation_met')
        with f.host.running():
            f.advance(3600)
            for _ in range(4):f.host.tick();f.advance(60)
            mind=f.state.intentions.dynamic_mind
            self.assertTrue(any(d['kind']=='TRUST' for d in mind['dispositions']))
            commitment=mind['will'][0]['commitment'];before=f.state.revision
            for _ in range(4):f.advance(300);f.host.tick()
            self.assertGreater(f.state.revision,before)
            self.assertTrue(any('Prior commitment: '+commitment in w['supporting_reasons']
                                for w in f.state.intentions.dynamic_mind['will']))
            self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            f.control('STOP')

    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='a19-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name), mode='contact')

    def step(self, f):
        f.advance(3600)
        f.host.tick()
        f.advance(60)
        f.host.tick()

    def test_reality_refusal_keeps_independent_mind_commit(self):
        f = self.fixture(); before = f.state.revision
        f.boundary.allowed = False
        with f.host.running():
            self.step(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, before + 1)
            self.assertTrue(f.state.intentions.dynamic_mind['desires'])
            self.assertEqual((f.fake.effect_count, f.fake.credits), (0, 0))
            self.assertNotEqual(f.core.last_action.status, 'COMPLETED')
            f.control('STOP')

    def test_current_world_resource_refusal_keeps_independent_mind_commit(self):
        f = self.fixture(); before = f.state.revision
        f.boundary.resource_ready = False
        with f.host.running():
            self.step(f)
            self.assertEqual(f.state.revision, before + 1)
            self.assertEqual((f.fake.effect_count, f.fake.credits), (0, 0))
            f.control('STOP')

    def test_broker_revoked_during_thinking_does_not_erase_internal_proposal(self):
        f = self.fixture(); before = f.state.revision
        f.provider.hook = lambda: setattr(f.broker, 'allowed', False)
        with f.host.running():
            self.step(f)
            self.assertEqual(f.state.revision, before + 1)
            self.assertEqual((f.fake.effect_count, f.fake.credits), (0, 0))
            f.control('STOP')

    def test_normal_action_and_internal_commit_remain_once(self):
        f = self.fixture(); before = f.state.revision
        with f.host.running():
            self.step(f)
            self.assertEqual(f.state.revision, before + 1)
            self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (1, 1, 1))
            f.host.tick()
            self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (1, 1, 1))
            f.control('STOP')

    def test_unknown_does_not_prevent_internal_commit_or_imply_success(self):
        f = self.fixture(); before = f.state.revision; f.fake.mode = 'unknown'
        with f.host.running():
            self.step(f)
            self.assertEqual(f.state.revision, before + 1)
            self.assertNotEqual(f.core.last_action.status, 'COMPLETED')
            self.assertEqual((f.fake.execute_calls, f.fake.effect_count, f.fake.credits), (0, 0, 0))
            f.control('STOP')

    def test_denial_reopen_recovers_internal_fact_without_resubmitting(self):
        f = self.fixture(); f.boundary.allowed = False
        with f.host.running():
            self.step(f)
            self.assertIsNotNone(f.state.intentions.dynamic_mind)
        previous = f.state.to_dict()
        f = P18Fixture(f.root, initialize=False)
        with f.host.running():
            f.host.tick()
            self.assertEqual(f.state.to_dict(), previous)
            self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (0, 0, 0))
            f.control('STOP')

    def test_external_gate_does_not_decide_whether_intent_exists(self):
        from types import SimpleNamespace as N
        from continuity_engine.services.continuity_core_service import CoreDecisionPolicy
        from continuity_engine.domain.action_planning import digest
        f = self.fixture(); now = f.clock.now()
        context = N(mind={}, composition=N(snapshot=N(environment='TEST',
            snapshot_hash=digest('test'), source_revision=1, fragments=(N(fragment_id='root'),))))
        thinking = N(session=N(result=N(update_subject_state=False, request_more_memory=False,
            suggest_future_user_contact=True, should_wait=False, result_id='result')))
        operation = N(subject_id=f.state.subject_id, operation_id='intent')
        choice = CoreDecisionPolicy().choose(operation, context, thinking,
            N(decision=N(approved=False, created_at=now)))
        self.assertIsNotNone(choice)
        self.assertEqual(choice.steps[0].capability, 'contact.send')
