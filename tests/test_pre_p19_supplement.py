"""A1/A2/A3: actual native/C1 paths and current negative controls, TEST only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
import tempfile
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.domain.persistent_runtime import RuntimePolicy
from continuity_engine.services.dynamic_mind_service import MindDynamics
from continuity_engine.services.runtime_cognition import RuntimeCognition
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class SupplementFixture(unittest.TestCase):
    def setUp(self):self.fixtures=[]

    def tearDown(self):
        failed=any(t is self for t,_ in self._outcome.result.failures+self._outcome.result.errors)
        if failed:
            import json,sys
            for f in self.fixtures:
                try:
                    print(json.dumps({'test':self.id(),'stage':'before-test-cleanup',
                        'runtime':f.host.query(),'revision':f.state.revision,'providerCalls':f.provider.calls,
                        'effects':f.fake.effect_count,'credits':f.fake.credits,
                        'sessions':[{'id':s.think_id,'completed':s.completed_successfully,
                                     'update_id':s.state_update_id} for s in f.work.thinking.get_sessions(f.state.subject_id)]},default=str),file=sys.stderr)
                except Exception as exc:print('TEST_DIAGNOSTIC_UNAVAILABLE:'+type(exc).__name__,file=sys.stderr)

    def fixture(self, mode='contact'):
        temp=tempfile.TemporaryDirectory(prefix='a3-');self.addCleanup(temp.cleanup)
        f=P18Fixture(Path(temp.name),mode=mode);self.fixtures.append(f);return f

    def step(self,f):
        f.advance(3600);f.host.tick();f.advance(60);f.host.tick()

    def assert_no_world(self,f):
        self.assertEqual((f.fake.execute_calls,f.fake.effect_count,f.fake.credits),(0,0,0))


class ExpressionIndependenceTests(SupplementFixture):
    def test_normal_c1_explicit_expression_consent_still_presents(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        with tempfile.TemporaryDirectory(prefix='ac-') as td:
            f=P14Fixture(Path(td),mode='complex');f.runtime.clock.advance(timedelta(hours=1))
            request=f.request();f.submit(request)
            self.assertEqual(f.artifact(request).decision.status,'SUBJECT_EXPRESSION')
            self.assertTrue(f.artifact(request).content)
            self.assertEqual(f.state.revision,2)

    def native_denied(self,gate):
        f=self.fixture();setattr(f.constraints,gate,False);before=f.state.revision
        with f.host.running():
            self.step(f)
            self.assertEqual((f.provider.calls,f.state.revision),(1,before+1))
            self.assertIsNotNone(f.state.intentions.dynamic_mind)
            self.assertEqual(f.work.expression_trace['status'],'PLATFORM_DENIED')
            self.assertIn('INDEPENDENT_STATE_EXPRESSION_DENIED',f.work.expression_trace['reason_codes'])
            self.assert_no_world(f)
        used=f.resources.get_resource_state(f.state.subject_id).token_used
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick()
            self.assertEqual((f.provider.calls,f.state.revision),(0,before+1))
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,used)
            self.assert_no_world(f);f.control('STOP')

    def test_native_confirmation_denial_commits_and_reopens_once(self):
        self.native_denied('confirmation_allowed')

    def test_native_reality_denial_commits_and_reopens_once(self):
        self.native_denied('reality_ready')

    def test_native_recoverability_denial_is_not_internal_state_denial(self):
        self.native_denied('recovery_ready')

    def c1_denied(self,gate):
        f=self.fixture();setattr(f.constraints,gate,False);f.advance(3600)
        request=f.request();before=f.state.revision
        with f.host.running():
            f.submit(request)
            self.assertEqual(f.state.revision,before+1)
            operation=f.app.ledger.load_operation(request['requestId'])
            self.assertTrue(operation.domain_progress.perception.continuity_context.expression_enabled)
            self.assertEqual(operation.domain.expression.decision.status,'PLATFORM_DENIED')
            self.assertEqual(operation.domain.expression.content,'')
            self.assertTrue(operation.domain_progress.action.decision.can_execute_automatically)
            self.assert_no_world(f)
        state=f.state.to_dict();f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.submit(request)
            self.assertEqual(f.state.to_dict(),state);self.assertEqual(f.provider.calls,0)
            self.assert_no_world(f);f.control('STOP')

    def test_c1_confirmation_denial_commits_and_replays_empty_refusal(self):
        self.c1_denied('confirmation_allowed')

    def test_c1_reality_denial_commits_and_replays_empty_refusal(self):
        self.c1_denied('reality_ready')

    def test_expression_only_confirmation_refusal_never_dispatches_otherwise_allowed_effect(self):
        f=self.fixture();confirmed=f.constraints.confirmed
        f.constraints.confirmed=lambda r:False if r.choice.decision_id.startswith('expression-access:') else confirmed(r)
        with f.host.running():
            self.step(f);self.assertEqual(f.state.revision,2)
            self.assertEqual(f.work.expression_trace['status'],'PLATFORM_DENIED')
            self.assert_no_world(f);f.control('STOP')

    def test_current_state_permission_still_required(self):
        f=self.fixture();f.constraints.confirmation_allowed=False
        f.work.native._available_permissions=tuple(p for p in f.work.native._available_permissions if p!='subject_state:update')
        with f.host.running():
            self.step(f);self.assertEqual(f.state.revision,1)
            self.assertIsNone(f.state.intentions.dynamic_mind);self.assert_no_world(f);f.control('STOP')

    def test_late_state_permission_revocation_still_prevents_commit(self):
        f=self.fixture();f.constraints.confirmation_allowed=False
        def revoke(stage):
            if stage=='after_native_effect':
                f.work.native._available_permissions=tuple(p for p in f.work.native._available_permissions if p!='subject_state:update')
        f.fault=revoke
        with f.host.running():
            self.step(f);self.assertEqual(f.state.revision,1)
            self.assert_no_world(f);f.control('STOP')

    def test_expired_context_is_not_an_expression_only_refusal(self):
        f=self.fixture();f.constraints.confirmation_allowed=False;f.provider.hook=lambda:f.advance(1000)
        with f.host.running():
            self.step(f);self.assertEqual(f.state.revision,1);self.assert_no_world(f);f.control('STOP')

    def test_revoked_source_prevents_internal_commit(self):
        f=self.fixture();f.constraints.reality_ready=False
        f.provider.hook=lambda:setattr(f.base.permission,'references_allowed',False)
        with f.host.running():
            self.step(f);self.assertEqual(f.state.revision,1);self.assert_no_world(f);f.control('STOP')

    def test_refused_expression_survives_after_evolution_crash_without_duplicate(self):
        class Crash(BaseException):pass
        f=self.fixture();f.constraints.confirmation_allowed=False
        def fault(stage):
            if stage=='after_native_evolution':raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():f.fault=fault;self.step(f)
        self.assertEqual(f.state.revision,2);self.assert_no_world(f)
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.host.tick();self.assertEqual((f.provider.calls,f.state.revision),(0,2))
            self.assertEqual(f.host.query()['unconfirmed_tasks'],0)
            self.assert_no_world(f);f.control('STOP')


class RoutedProposalTests(SupplementFixture):
    def test_plain_memory_query_cannot_precommit_its_unreceived_result(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        with tempfile.TemporaryDirectory(prefix='am-') as td:
            f=P14Fixture(Path(td),mode='information',expression_mode='SILENCE')
            original=f.provider.think;before=f.state.continuity.current_focus
            f.provider.think=lambda *args:replace(original(*args),update_subject_state=True,
                proposed_mutations=[StateMutation('continuity.current_focus',ChangeOperation.SET,
                    ['not yet received query outcome'],'proposal predates the pending memory query')])
            f.runtime.clock.advance(timedelta(hours=1));f.submit()
            self.assertEqual(f.state.revision,2)
            self.assertEqual(f.state.continuity.current_focus,before)
            self.assertEqual(f.core.last_action.requests[0].capability_type,'memory.lookup')

    def route_case(self,route,outcome):
        f=self.fixture('contact' if route=='contact' else 'reflect')
        if outcome=='denied':f.boundary.allowed=False
        elif outcome=='unknown':f.fake.mode='unknown'
        original=f.provider.think;claim=['arbitrary opaque value, not a keyword rule']
        def mixed(*args):
            result=original(*args)
            return replace(result,request_more_memory=route=='memory',
                additional_memory_query='current evidence' if route=='memory' else None,
                update_subject_state=True,proposed_mutations=[StateMutation(
                    'continuity.current_focus',ChangeOperation.SET,claim,'proposal formed before the same routed effect')])
        f.provider.think=mixed
        with f.host.running():
            before=f.state.continuity.current_focus;self.step(f)
            self.assertEqual(f.state.revision,2);self.assertEqual(f.state.continuity.current_focus,before)
            self.assertIsNotNone(f.state.intentions.dynamic_mind)
            session=f.work.thinking.get_sessions(f.state.subject_id)[-1]
            self.assertTrue(any(m.value==claim for m in session.result.proposed_mutations))
            self.assertEqual(f.core.last_action.requests[0].capability_type,
                             'execution.read' if route=='memory' else 'execution.write')
            self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1) if outcome=='success' else (0,0))
            self.assertEqual(f.core.last_action.status=='COMPLETED',outcome=='success')
            f.host.tick();self.assertEqual(f.state.revision,2)
            f.control('STOP')

    def test_expression_route_denied(self):self.route_case('expression','denied')
    def test_expression_route_unknown(self):self.route_case('expression','unknown')
    def test_expression_route_verified_success_retains_preeffect_proposal(self):self.route_case('expression','success')
    def test_contact_route_denied(self):self.route_case('contact','denied')
    def test_contact_route_unknown(self):self.route_case('contact','unknown')
    def test_contact_route_verified_success_retains_preeffect_proposal(self):self.route_case('contact','success')
    def test_memory_route_denied(self):self.route_case('memory','denied')
    def test_memory_route_unknown(self):self.route_case('memory','unknown')
    def test_memory_route_verified_success_retains_preeffect_proposal(self):self.route_case('memory','success')

    def test_later_receipt_backed_cognition_can_form_a_new_authorized_judgment(self):
        f=self.fixture('reflect')
        with f.host.running():
            self.step(f);self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
            original=f.provider.think;f.mode='silence'
            def observed(perception,budget):
                self.assertTrue(any(x.source_id=='engine.execution-results'
                    for x in perception.continuity_context.composition.snapshot.fragments))
                return replace(original(perception,budget),update_subject_state=True,
                    proposed_mutations=[StateMutation('continuity.current_focus',ChangeOperation.SET,
                        ['verified TEST outcome considered'],'current received observation supports this new judgment')])
            f.provider.think=observed;f.advance(300);f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.state.revision,3)
            self.assertEqual(f.state.continuity.current_focus,['verified TEST outcome considered'])
            self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1));f.control('STOP')

    def test_current_internal_only_reflection_preserves_provider_proposal(self):
        f=self.fixture('silence');original=f.provider.think
        f.provider.think=lambda *args:replace(original(*args),update_subject_state=True,
            proposed_mutations=[StateMutation('continuity.current_focus',ChangeOperation.SET,
                ['an independent internal focus'],'independent cognition, no proposed world execution')])
        with f.host.running():
            self.step(f);self.assertEqual(f.state.continuity.current_focus,['an independent internal focus'])
            self.assert_no_world(f);f.control('STOP')


class RenewedNeedTests(SupplementFixture):
    def fulfilled(self):
        now=datetime(2026,9,20,tzinfo=timezone.utc);d=MindDynamics()
        active=d.advance(MindState.create('test','TEST',now),at=now+timedelta(hours=1)).state
        return d.advance(active,at=active.updated_at,outcomes=[
            dict(desire_id=x['id'],phase='act',reason='particular need fulfilled') for x in active.desires]).state

    def needs(self,mind,at):
        core=N(subject_states=N(require_active=lambda *a:N(revision=2,intentions=N(dynamic_mind=mind.to_dict()))),
            mind=N(dynamics=MindDynamics()),memory=N(list_memories=lambda *a,**kw:[]),
            timeline=N(rebuild=lambda *a:N(entries=[])))
        return RuntimeCognition.needs(N(core=core,subject_id=mind.subject_id,environment='TEST',
            policy=RuntimePolicy(),scheduler=N(list_tasks=lambda **kw:[])),at)

    def test_fulfilled_needs_recur_from_original_dynamics(self):
        mind=self.fulfilled();later=mind.updated_at+timedelta(hours=1)
        self.assertTrue(all(d['phase']=='recur' for d in MindDynamics().advance(mind,at=later).state.desires))
        self.assertTrue(self.needs(mind,later))

    def test_fulfilled_without_sufficient_new_need_does_not_force_call(self):
        mind=self.fulfilled();self.assertEqual(self.needs(mind,mind.updated_at+timedelta(seconds=60)),())

    def test_abandoned_goal_is_not_renewed_by_scheduler(self):
        mind=self.fulfilled();mind=replace(mind,desires=[{**d,'phase':'abandon'} for d in mind.desires],
            will=[{**w,'stance':'abandon'} for w in mind.will])
        self.assertEqual(self.needs(mind,mind.updated_at+timedelta(hours=1)),())

    def test_suppression_and_rest_have_a_bounded_reconsideration(self):
        mind=self.fulfilled();mind=replace(mind,desires=[{**d,'phase':'suppress'} for d in mind.desires])
        self.assertEqual(self.needs(mind,mind.updated_at+timedelta(seconds=60)),())
        self.assertTrue(self.needs(mind,mind.updated_at+timedelta(hours=1)))

    def test_persisted_fulfillment_reopens_then_real_cognition_progresses_with_pause_stop(self):
        f=self.fixture('silence')
        with f.host.running():self.step(f)
        mind=MindState.from_dict(f.state.intentions.dynamic_mind)
        fulfilled=MindDynamics().advance(mind,at=mind.updated_at,outcomes=[
            dict(desire_id=d['id'],phase='act',reason='TEST confirmed need completion') for d in mind.desires]).state
        # Authorized internal test outcome uses the original State/Event transaction;
        # the subsequent cognition uses the unmodified normal native chain.
        from continuity_engine.domain.events import Event,EventClassification,EventSourceKind,StateSection
        at=f.clock.now()
        event=Event.create(event_id='a3-fulfilled',occurred_at=at,observed_at=at,recorded_at=at,
            source='a3-test-outcome',source_kind=EventSourceKind.TEST,event_type='state_change',
            classification=EventClassification.STATE_CHANGE,impact_scope=[StateSection.INTENTIONS],
            mutations=[StateMutation('intentions.dynamic_mind',ChangeOperation.SET,fulfilled.to_dict(),'confirmed test outcome')],
            reason='isolated authorized outcome',content='TEST fulfillment')
        f.runtime.subject_states.apply_event(f.state.subject_id,event)
        before=f.state.revision;f=P18Fixture(f.root,initialize=False)
        with f.host.running():
            f.control('PAUSE');f.advance(3600);f.host.tick()
            self.assertEqual((f.provider.calls,f.state.revision),(0,before))
            f.grant_test_budget(f.resources.get_resource_state(f.state.subject_id).token_used)
            f.control('RESUME');f.host.tick();f.advance(60);f.host.tick()
            self.assertEqual(f.provider.calls,0)
            self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
            f.grant_test_budget(10000);f.advance(60);f.host.tick()
            self.assertEqual((f.provider.calls,f.state.revision),(1,before+1))
            self.assertTrue(any(d['phase']=='recur' for d in f.state.intentions.dynamic_mind['desires']))
            self.assert_no_world(f);f.control('STOP');self.assertFalse(f.host.tick())
        f=P18Fixture(f.root,initialize=False)
        with f.host.running():self.assertFalse(f.host.tick())
        self.assertEqual(f.provider.calls,0)
