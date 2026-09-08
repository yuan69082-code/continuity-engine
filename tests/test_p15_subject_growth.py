"""P15 growth uses real Learning/Evolution; Fake only supplies isolated evidence/consent."""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest


class SubjectGrowthTests(unittest.TestCase):
    def setUp(self):
        from continuity_engine.testing.p15_subject_fixture import P15GrowthFixture
        self.temp=tempfile.TemporaryDirectory(prefix='g15-')
        self.addCleanup(self.temp.cleanup)
        self.f=P15GrowthFixture(Path(self.temp.name))

    def test_three_current_independent_experiences_form_trait_and_next_context(self):
        f=self.f; ids=f.experiences()
        f.growth.validate(ids[0], ids[1:])
        revision=f.state.revision
        result=f.solidify(ids[0], identity='grow')
        self.assertIn('consider evidence',f.state.identity.stable_traits)
        self.assertEqual(f.state.revision,revision+1)
        f.reopen()
        self.assertEqual(f.replay('grow').update_id,result.update_id)
        self.assertEqual(f.state.revision,revision+1)
        request=f.request(); f.submit(request)
        self.assertIn('consider evidence',f.context(request).model_summary())
        operation=f.app.ledger.load_operation(request['requestId'])
        session=f.app.adapter.service._thinking.get_session(f.state.subject_id,operation.domain.think_session_id)
        self.assertTrue(session.result.request_more_memory)
        self.assertEqual(session.result.additional_memory_query,'independent evidence')

    def test_rejected_support_and_permission_revocation_zero_state_change(self):
        from continuity_engine.domain.errors import LearningValidationError
        f=self.f; ids=f.experiences(); f.growth.validate(ids[0],ids[1:])
        f.growth.learning.reject_learning(f.state.subject_id,ids[1],reason='evidence rejected',source='test')
        before=f.inventory()
        with self.assertRaises(LearningValidationError):f.solidify(ids[0])
        self.assertEqual(before,f.inventory())

    def test_duplicate_root_wrappers_do_not_validate(self):
        from continuity_engine.domain.errors import LearningValidationError
        f=self.f
        ids=f.experiences(roots=('one','one','one'))
        with self.assertRaises(LearningValidationError):f.growth.validate(ids[0],ids[1:])
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)

    def test_rollback_preserves_later_unrelated_trait(self):
        from continuity_engine.domain.events import Event, StateMutation, StateSection, ChangeOperation
        f=self.f; ids=f.experiences(); f.growth.validate(ids[0],ids[1:])
        update=f.solidify(ids[0],identity='grow')
        event=Event.create(occurred_at=f.runtime.clock.now(),source='test-authorized',event_type='state_change',
            content='Later unrelated judgment',impact_scope=[StateSection.IDENTITY],reason='test',
            mutations=[StateMutation('identity.stable_traits',ChangeOperation.APPEND,'independent later trait','test')])
        f.runtime.subject_states.apply_event(f.state.subject_id,event,expected_revision=f.state.revision)
        f.rollback(ids[0], update.event.metadata['trait_id'])
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)
        self.assertIn('independent later trait',f.state.identity.stable_traits)

    def test_pending_learning_record_recovers_after_restart_without_second_revision(self):
        f=self.f; ids=f.experiences(); f.growth.validate(ids[0],ids[1:])
        class Crash(BaseException):pass
        f.growth.fault=lambda stage: (_ for _ in ()).throw(Crash()) if stage=='after_learning_record' else None
        revision=f.state.revision
        with self.assertRaises(Crash):f.solidify(ids[0],identity='pending')
        self.assertEqual(f.state.revision,revision)
        f.reopen(); result=f.replay('pending')
        self.assertEqual(f.state.revision,revision+1)
        f.replay('pending')
        self.assertEqual(f.state.revision,revision+1)
        self.assertEqual(result.after_revision,revision+1)

    def test_normal_chain_forms_subjective_narrative_and_object_relationship(self):
        f=self.f
        f.affective_event('care',object_id='peer-a',observation='support_received')
        f.runtime.clock.advance(timedelta(seconds=1))
        request=f.request(); f.submit(request)
        self.assertIsNotNone(f.state.identity.self_narrative)
        self.assertIsNotNone(f.state.relationship.objects)
        self.assertEqual(f.state.relationship.objects['subject_id'],f.state.subject_id)
        self.assertEqual(f.state.relationship.objects['entries'][0]['object_id'],'peer-a')
        self.assertTrue(f.state.identity.self_narrative['entries'][0]['source_roots'])
        self.assertEqual(f.state.identity.self_narrative['authority'],'SUBJECTIVE_INTERPRETATION')
        from continuity_engine.domain.errors import IntegrationExecutionError
        original=f.state.to_dict()
        # Existing P13/P14 contract: historical facts remain queryable, while
        # re-presenting text requires a current Context after the state revision.
        facts=f.app.adapter._service.expression_outcome(request['requestId'])
        self.assertEqual(facts['verified_facts']['state_revision'],f.state.revision)
        self.assertEqual(facts['status'],'CURRENTLY_UNAVAILABLE')
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(original,f.state.to_dict())

    def test_current_confidence_policy_095_02_02_and_reduced_support(self):
        f=self.f; ids=f.experiences(confidences=(0.95,0.2,0.2))
        result=f.growth.validate(ids[0],ids[1:])
        self.assertEqual(result.learning_event.confidence,0.95)
        update=f.solidify(ids[0])
        self.assertEqual(update.event.metadata['learning_confidence'],0.95)

    def test_current_reference_revocation_prevents_solidify_without_writes(self):
        from continuity_engine.domain.errors import LearningValidationError
        f=self.f; ids=f.experiences(); f.growth.validate(ids[0],ids[1:])
        f.permission.references_allowed=False; before=f.inventory()
        with self.assertRaises(LearningValidationError):f.solidify(ids[0])
        self.assertEqual(before,f.inventory())

    def test_growth_permission_policy_is_required_and_owner_read_is_read_only(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        f=self.f; f.affective_event('care',object_id='peer-a',observation='support_received')
        f.runtime.clock.advance(timedelta(seconds=1)); f.submit(f.request())
        projection=f.owner_projection(); before=f.inventory()
        with self.assertRaisesRegex(MindAccessError,'NOT_READY'):projection.read_growth('test-owner-session')
        value=projection.read_growth('test-owner-session',allowed_objects=('peer-a',))
        self.assertEqual(value['relationships']['entries'][0]['object_id'],'peer-a')
        with self.assertRaises(MindAccessError):projection.read_growth('test-other-session',allowed_objects=('peer-a',))
        self.assertEqual(before,f.inventory())

    def test_growth_feature_disabled_has_no_learning_read_or_write(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from unittest.mock import patch
        from continuity_engine.storage.json_learning_repository import JsonLearningRepository
        with patch.object(JsonLearningRepository,'list_learning_events',side_effect=AssertionError('disabled growth read')):
            f=P14Fixture(Path(self.temp.name)/'off',mind_enabled=False)
            f.submit(f.request())
        self.assertIsNone(f.core.growth)
        self.assertIsNone(f.state.identity.self_narrative)

    def test_current_source_binding_cannot_be_replaced_with_forged_roots(self):
        from continuity_engine.domain.events import StateMutation, ChangeOperation
        from continuity_engine.domain.errors import LearningValidationError
        f=self.f; ids=f.experiences()
        origin=f.growth.learning.get_history(f.state.subject_id,ids[0])[0]
        for i in range(2):
            f.growth.learning.create_candidate(f.state.subject_id,learning_id='forged-'+str(i),
                source_event_id='one',source_memory_id=None,related_state_revision=f.state.revision,
                observation='alias',hypothesis='alias',proposed_change=StateMutation('identity.stable_traits',
                    ChangeOperation.APPEND,'consider evidence','alias'),confidence=0.9,
                original_experience=origin.original_experience,reason='test alias',source='test',
                root_evidence_ids=['event:forged-'+str(i)])
        with self.assertRaises(LearningValidationError):f.growth.validate(ids[0],['forged-0','forged-1'])

    def test_weaker_still_sufficient_support_records_current_confidence(self):
        f=self.f; ids=f.experiences();f.growth.validate(ids[0],ids[1:])
        f.growth.learning.adjust_confidence(f.state.subject_id,ids[1],-0.15,reason='current support weaker',source='test')
        update=f.solidify(ids[0])
        self.assertAlmostEqual(update.event.metadata['learning_confidence'],0.95)

    def test_revoked_event_blocks_pending_commit_but_does_not_rewrite_existing_trait(self):
        from continuity_engine.domain.errors import LearningValidationError
        from continuity_engine.domain.events import Event,EventReference,EventRelationType,EventClassification,StateSection
        f=self.f;ids=f.experiences();f.growth.validate(ids[0],ids[1:])
        original=f.solidify(ids[0],identity='accepted-fact')
        event=Event.create(event_id='revoke-one',occurred_at=f.runtime.clock.now(),source='test',event_type='revocation',
            classification=EventClassification.REVOCATION,content='Source no longer usable',
            impact_scope=[StateSection.CONTINUITY],mutations=[],reason='explicit source revocation',
            references=[EventReference('one',f.state.subject_id,EventRelationType.REVOKES)])
        f.runtime.subject_states.apply_event(f.state.subject_id,event)
        before=f.state.to_dict()
        self.assertEqual(f.replay('accepted-fact').update_id,original.update_id)
        self.assertEqual(before,f.state.to_dict())
        with self.assertRaises(LearningValidationError):f.growth.learning._verify_current_support(
            f.state.subject_id,f.growth.learning.get_learning_event(f.state.subject_id,ids[0]))

    def test_rollback_pending_record_recovers_and_does_not_remove_twice(self):
        f=self.f;ids=f.experiences();f.growth.validate(ids[0],ids[1:])
        initial=f.solidify(ids[0])
        class Crash(BaseException):pass
        f.growth.fault=lambda stage: (_ for _ in ()).throw(Crash()) if stage=='after_learning_record' else None
        revision=f.state.revision
        with self.assertRaises(Crash):f.rollback(ids[0],initial.event.metadata['trait_id'],identity='rollback')
        self.assertEqual(f.state.revision,revision)
        f.reopen();f.replay('rollback');f.replay('rollback')
        self.assertEqual(f.state.revision,revision+1)
        self.assertNotIn('consider evidence',f.state.identity.stable_traits)

    def test_completed_growth_recovers_after_authority_revoked(self):
        f=self.f;ids=f.experiences();f.growth.validate(ids[0],ids[1:])
        class Crash(BaseException):pass
        f.growth.fault=lambda stage: (_ for _ in ()).throw(Crash()) if stage=='after_evolution' else None
        with self.assertRaises(Crash):f.solidify(ids[0],identity='committed')
        before=f.state.to_dict(); f.reopen();f.growth_authority.revoked=True
        self.assertEqual(f.replay('committed').after_revision,before['revision'])
        self.assertEqual(before,f.state.to_dict())

    def test_reinterpreted_experience_preserves_opposite_stances_and_versions(self):
        from continuity_engine.domain.dynamic_mind import MindState
        from continuity_engine.domain.events import Event,StateMutation,ChangeOperation,StateSection
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.f
        f.core.context_budget=ContextBudget(token_limit=3000)
        mind=MindState.create(f.state.subject_id,'TEST',f.runtime.clock.now()).with_dispositions([
            {'object':'peer','kind':'LOVE','basis':['prior-care']},
            {'object':'peer','kind':'HATE','basis':['prior-harm']}])
        f.runtime.subject_states.apply_event(f.state.subject_id,Event.create(occurred_at=f.runtime.clock.now(),
            source='authorized-TEST-genesis',event_type='state_change',content='Explicit contrasting dispositions fixture',
            impact_scope=[StateSection.INTENTIONS],reason='TEST initial state',mutations=[
                StateMutation('intentions.dynamic_mind',ChangeOperation.SET,mind.to_dict(),'TEST initial state')]))
        for identity,observation in [('harm','boundary_crossed'),('support1','expectation_met'),('support2','expectation_met')]:
            f.runtime.clock.advance(timedelta(minutes=1));f.affective_event(identity,object_id='peer',observation=observation)
            f.runtime.clock.advance(timedelta(seconds=1));f.submit(f.request())
        relation=f.state.relationship.objects['entries'][0]
        self.assertTrue({'LOVE','HATE'}<=set(relation['stances']))
        self.assertTrue(f.state.intentions.dynamic_mind['conflicts'])
        self.assertTrue(any(e['version']>1 for e in f.state.identity.self_narrative['entries']))
