"""Counterexamples and controls; isolated TEST fixtures, no production IO."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.domain.persistent_runtime import RuntimePolicy
from continuity_engine.services.dynamic_mind_service import MindDynamics
from continuity_engine.services.runtime_cognition import RuntimeCognition
from continuity_engine.testing.p18_runtime_fixture import P18Fixture

OUT = Path(__file__).resolve().parent


class IndependentBoundaries(unittest.TestCase):
    def setUp(self):
        self.observed = {}

    def tearDown(self):
        with (OUT / 'independent-observations.jsonl').open('a', encoding='utf8') as out:
            out.write(json.dumps({'test': self.id(), **self.observed}, ensure_ascii=False, default=str)+'\n')

    def fixture(self, mode='contact'):
        temp = tempfile.TemporaryDirectory(prefix='pr-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name), mode=mode)

    def native(self, f):
        before = f.state.revision
        with f.host.running():
            f.advance(3600); f.host.tick(); f.advance(60); f.host.tick()
            self.observed.update(providerCalls=f.provider.calls, beforeRevision=before,
                afterRevision=f.state.revision, mindPresent=f.state.intentions.dynamic_mind is not None,
                effects=f.fake.effect_count, credits=f.fake.credits,
                focus=f.state.continuity.current_focus, runtime=f.host.query(),
                lastAction=None if f.core.last_action is None else f.core.last_action.status)
            sessions=f.work.thinking.get_sessions(f.state.subject_id)
            self.observed['thinkingCompleted']=[s.completed_successfully for s in sessions]
            self.observed['formedMutationPaths']=[
                [m.field_path for m in s.result.proposed_mutations] for s in sessions if s.result]
            self.observed['originalActions']=[{
                'type':a.final_decision.selected_action.action_type.value,
                'approved':a.final_decision.approved,
                'automatic':a.final_decision.can_execute_automatically,
                'requiresConfirmation':a.final_decision.requires_confirmation,
                'rejection':a.final_decision.rejection_reason}
                for a in f.work.native._action.get_sessions(f.state.subject_id)]
            f.control('STOP')
        return before

    def test_expression_world_boundary_refusal_does_not_discard_formed_internal_state(self):
        f=self.fixture()
        f.constraints.reality_ready=False
        before=self.native(f)
        self.assertEqual(f.provider.calls,1)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
        self.assertEqual(f.state.revision,before+1,
            'Current expression/world refusal must not gate independently authorized internal Evolution')

    def test_expression_confirmation_refusal_does_not_discard_formed_internal_state(self):
        f=self.fixture()
        f.constraints.confirmation_allowed=False
        before=self.native(f)
        self.assertEqual(f.provider.calls,1)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
        self.assertEqual(f.state.revision,before+1)

    def test_same_native_path_with_authorized_expression_commits_once(self):
        f=self.fixture()
        before=self.native(f)
        self.assertEqual(f.state.revision,before+1)
        self.assertEqual((f.provider.calls,f.fake.effect_count,f.fake.credits),(1,1,1))

    def test_execution_adapter_denial_control_keeps_internal_state(self):
        f=self.fixture(); f.boundary.allowed=False
        before=self.native(f)
        self.assertEqual(f.state.revision,before+1)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_expression_routed_effect_cannot_commit_a_premature_effect_claim(self):
        f=self.fixture(mode='reflect'); f.boundary.allowed=False
        original=f.provider.think
        before_focus=f.state.continuity.current_focus
        def mixed(*args):
            result=original(*args)
            self.assertFalse(result.suggest_future_user_contact)
            self.assertFalse(result.suggest_tool_use)
            return replace(result,update_subject_state=True,proposed_mutations=[
                StateMutation('continuity.current_focus',ChangeOperation.SET,
                    ['world write completed'],'premature assertion of the same planned world effect')])
        f.provider.think=mixed
        before=self.native(f)
        self.assertEqual(f.state.revision,before+1)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
        self.assertEqual(f.state.continuity.current_focus,before_focus,
            'Effect-dependent provider proposal must not be trusted solely because contact/tool flags are false')

    def needs(self,mind,at):
        state=N(revision=3,intentions=N(dynamic_mind=mind.to_dict()))
        core=N(subject_states=N(require_active=lambda *a:state),mind=N(dynamics=MindDynamics()),
            memory=N(list_memories=lambda *a,**kw:[]),timeline=N(rebuild=lambda *a:N(entries=[])))
        work=N(core=core,subject_id=mind.subject_id,environment='TEST',policy=RuntimePolicy(),
            scheduler=N(list_tasks=lambda **kw:[]))
        return RuntimeCognition.needs(work,at)

    def test_fulfilled_desires_do_not_permanently_block_new_endogenous_needs(self):
        now=datetime(2026,9,20,tzinfo=timezone.utc)
        dynamics=MindDynamics()
        active=dynamics.advance(MindState.create('review','TEST',now),at=now+timedelta(hours=1)).state
        fulfilled=dynamics.advance(active,at=active.updated_at,outcomes=[
            {'desire_id':d['id'],'phase':'act','reason':'This particular need was fulfilled'}
            for d in active.desires]).state
        MindState.from_dict(fulfilled.to_dict())
        later=fulfilled.updated_at+timedelta(hours=1)
        proposal=dynamics.advance(fulfilled,at=later).state
        needs=self.needs(fulfilled,later)
        self.observed.update(beforePhases=[d['phase'] for d in fulfilled.desires],
            beforeDrives=fulfilled.drives, projectedPhases=[d['phase'] for d in proposal.desires],
            projectedDrives=proposal.drives, actualNeeds=[n.kind for n in needs],
            threshold=RuntimePolicy().need_delta)
        self.assertTrue(all(d['phase']=='recur' for d in proposal.desires))
        self.assertGreater(max(proposal.drives.values()),RuntimePolicy().need_delta)
        self.assertTrue(any(n.kind=='cognition' for n in needs),
            'Individual completed desires are not a permanent global decision to stop cognition')

    def test_unfinished_desires_control_requests_new_cognition(self):
        now=datetime(2026,9,20,tzinfo=timezone.utc)
        mind=MindDynamics().advance(MindState.create('review','TEST',now),at=now+timedelta(hours=1)).state
        needs=self.needs(mind,mind.updated_at+timedelta(hours=1))
        self.observed['needs']=[n.kind for n in needs]
        self.assertTrue(any(n.kind=='cognition' for n in needs))

    def test_rest_interval_remains_bounded_and_does_not_become_a_stop(self):
        now=datetime(2026,9,20,tzinfo=timezone.utc)
        mind=MindDynamics().advance(MindState.create('review','TEST',now),at=now+timedelta(days=365)).state
        mind=replace(mind,will=[{**w,'stance':'hold','decision':'DEFER'} for w in mind.will])
        self.assertFalse(self.needs(mind,mind.updated_at+timedelta(seconds=60)))
        self.assertTrue(self.needs(mind,mind.updated_at+timedelta(seconds=240)))
