"""Normal experienced roots produce bounded, revisable internal interpretations."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.services.dynamic_mind_service import MindDynamics
from continuity_engine.testing.p14_mind_fixture import P14Fixture
from continuity_engine.domain.context_composition import ContextBudget


class AutonomyGrowthTests(unittest.TestCase):
    def test_unselected_old_sources_do_not_erase_established_subjective_understanding(self):
        f=self.fixture();self.experience(f,'care1','expectation_met');self.experience(f,'care2','expectation_met')
        established=deepcopy(f.state.intentions.dynamic_mind['dispositions'])
        f.core.router._bindings=[b for b in f.core.router._bindings
                                if b.source.source_id not in {'engine.timeline','engine.memory'}]
        f.runtime.clock.advance(timedelta(minutes=10));f.submit(f.request())
        self.assertEqual(f.state.intentions.dynamic_mind['dispositions'],established)

    def test_revoked_root_cannot_continue_supporting_new_interpretation(self):
        from continuity_engine.domain.events import EventClassification, EventReference, EventRelationType
        f=self.fixture();self.experience(f,'care1','expectation_met');self.experience(f,'care2','expectation_met')
        original=deepcopy(f.state.intentions.dynamic_mind)
        f.event('revoke',classification=EventClassification.REVOCATION,references=(
            EventReference('care1',f.state.subject_id,EventRelationType.REVOKES),))
        f.runtime.clock.advance(timedelta(minutes=10));f.submit(f.request())
        mind=f.state.intentions.dynamic_mind
        self.assertTrue(any(d['kind']=='TRUST' for d in mind['dispositions']))
        self.assertFalse(any('Current interpretation: TRUST' in r for w in mind['will'] for r in w['supporting_reasons']))
        self.assertTrue(any('lacks currently consumable support' in r for w in mind['will'] for r in w['opposing_reasons']))
        history=f.runtime.subject_states.get_update_history(f.state.subject_id)
        self.assertTrue(any(any(m.field_path=='intentions.dynamic_mind' and m.value==original
                                for m in u.event.mutations) for u in history))

    def test_reference_revocation_during_thinking_does_not_commit_growth(self):
        f=self.fixture();self.experience(f,'care1','expectation_met')
        f.runtime.clock.advance(timedelta(minutes=10));f.affective_event('care2',object_id='peer',observation='expectation_met')
        before=f.state.to_dict();original=f.provider.think
        def revoked(*args):
            result=original(*args);f.permission.references_allowed=False;return result
        f.provider.think=revoked
        from continuity_engine.domain.errors import IntegrationExecutionError
        with self.assertRaises(IntegrationExecutionError):f.submit(f.request())
        self.assertEqual(f.state.to_dict(),before)

    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='a19g-'); self.addCleanup(temp.cleanup)
        f=P14Fixture(Path(temp.name),expression_enabled=False)
        f.core.context_budget=ContextBudget(token_limit=8000)
        return f

    def experience(self,f,key,kind,obj='peer'):
        f.runtime.clock.advance(timedelta(minutes=10))
        f.affective_event(key,object_id=obj,observation=kind)
        f.submit(f.request())

    def test_normal_experience_produces_disposition_and_survives_reopen(self):
        f=self.fixture()
        self.experience(f,'care1','expectation_met')
        self.assertEqual(f.state.intentions.dynamic_mind['dispositions'],[])
        self.experience(f,'care2','expectation_met')
        dispositions=deepcopy(f.state.intentions.dynamic_mind['dispositions'])
        self.assertTrue(dispositions)
        self.assertEqual(dispositions[0]['kind'],'TRUST')
        self.assertTrue({'event:care1','event:care2'} <= set(dispositions[0]['basis']))
        self.assertNotIn('LOVE',{d['kind'] for d in dispositions})
        f.reopen();f.core.context_budget=ContextBudget(token_limit=8000)
        f.runtime.clock.advance(timedelta(minutes=10)); f.submit(f.request())
        self.assertEqual(f.state.intentions.dynamic_mind['dispositions'],dispositions)
        self.assertTrue(any('TRUST' in reason for w in f.state.intentions.dynamic_mind['will']
                            for reason in w['supporting_reasons']))

    def test_duplicate_root_does_not_create_disposition(self):
        f=self.fixture();self.experience(f,'one','expectation_met')
        for _ in range(2):
            f.runtime.clock.advance(timedelta(seconds=10));f.submit(f.request())
        self.assertEqual(f.state.intentions.dynamic_mind['dispositions'],[])

    def test_opposite_experiences_coexist_and_change_deliberation(self):
        f=self.fixture()
        for key,kind in [('care1','expectation_met'),('care2','expectation_met'),
                         ('harm1','boundary_crossed'),('harm2','boundary_crossed')]:
            self.experience(f,key,kind)
        mind=f.state.intentions.dynamic_mind
        self.assertTrue({'TRUST','DOUBT'} <= {d['kind'] for d in mind['dispositions']})
        self.assertTrue(any(set(c['poles'])=={'TRUST','DOUBT'} for c in mind['conflicts']))
        self.assertTrue(any(w['decision']=='QUESTION' for w in mind['will']))

    def test_prior_commitment_is_used_and_unrelated_sources_do_not_erase_it(self):
        f=self.fixture();self.experience(f,'care1','expectation_met');self.experience(f,'care2','expectation_met')
        before=MindState.from_dict(f.state.intentions.dynamic_mind)
        self.experience(f,'other','unexpected_support',obj='unrelated')
        after=MindState.from_dict(f.state.intentions.dynamic_mind)
        for old in before.will:
            new=next(w for w in after.will if w['desire_id']==old['desire_id'])
            self.assertEqual(new['commitment'],old['commitment'])
            self.assertIn('Prior commitment: '+old['commitment'],new['supporting_reasons'])

    def test_new_understanding_can_revise_commitment_not_only_hash(self):
        f=self.fixture();self.experience(f,'care1','expectation_met');self.experience(f,'care2','expectation_met')
        before=deepcopy(f.state.intentions.dynamic_mind['will'])
        self.experience(f,'harm1','boundary_crossed');self.experience(f,'harm2','boundary_crossed')
        after=f.state.intentions.dynamic_mind['will']
        self.assertTrue(any(a['commitment']!=b['commitment'] for a,b in zip(before,after)))
        self.assertTrue(any('Reconsider' in w['commitment'] for w in after))
