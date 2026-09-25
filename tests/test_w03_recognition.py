"""N03 evidence-backed recognition through normal C1 and original Learning."""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, EventReference, EventRelationType, StateSection
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.w02_input_fixture import W02InputFixture
from continuity_engine.testing.persistence import tree_inventory_hash


class W03RecognitionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='r3-')
        self.addCleanup(temp.cleanup)
        self.f=P09Fixture(Path(temp.name),subject_growth=True)

    def experience(self, event_id, *, object_id='user:alice', alias='小林',
                   conclusion='喜欢螺蛳粉', polarity='SUPPORT', content=None, corrects=None,
                   owner='USER', expires_after=None):
        f=self.f
        f.runtime.clock.advance(timedelta(seconds=1))
        now=f.runtime.clock.now()
        descriptor={'object_id':object_id,'owner':owner,'aliases':[alias],
                    'scope':'food-preference','conclusion':conclusion,'polarity':polarity,
                    'valid_at':now.isoformat().replace('+00:00','Z'),
                    'source_type':'TEST_EXPERIENCE'}
        if corrects is not None:descriptor['corrects']=corrects
        if expires_after is not None:
            descriptor['expires_at']=(now+expires_after).isoformat().replace('+00:00','Z')
        value='recognition:'+digest([descriptor['owner'],descriptor['object_id'],
            descriptor['scope'],descriptor['conclusion'],descriptor['polarity']])[7:]
        event=Event.create(event_id=event_id,occurred_at=now,observed_at=now,recorded_at=now,
            source='w03.synthetic-experience',source_kind=EventSourceKind.TEST,
            event_type='recognition_experience',classification=EventClassification.INTERACTION,
            content=content or ('小林说她喜欢螺蛳粉：'+event_id),impact_scope=[StateSection.RELATIONSHIP],
            mutations=[],reason='Versioned isolated recognition experience',
            metadata={'w03_recognition':descriptor,'learning_observation':content or event_id,
                      'learning_hypothesis':conclusion,
                      'learning_field_path':'relationship.interaction_preferences',
                      'learning_value':value,'learning_confidence':0.85})
        f.runtime.subject_states.apply_event(f.runtime.descriptor.subject_id,event)
        request=f.request();f.submit(request)
        candidates=[candidate for candidate in f.core.growth.learning.list_learning_events(
            f.runtime.descriptor.subject_id) if candidate.source_event_id==event_id]
        self.assertEqual(len(candidates),1)
        return candidates[0].learning_id

    def test_three_independent_experiences_commit_correct_and_replay(self):
        f=self.f
        ids=[self.experience(name) for name in ('one','two','three')]
        result=f.core.recognition.validate(ids[0],ids[1:])
        self.assertEqual(result.learning_event.validation_status.value,'VALIDATED')
        rev=f.runtime.subject_state().revision
        update=f.core.recognition.commit(ids[0],command_id='recognize-alice',
            expected_revision=rev,reason='Independent current roots support a bounded interpretation')
        self.assertEqual(f.runtime.subject_state().revision,rev+1)
        self.assertEqual(f.core.recognition.commit(ids[0],command_id='recognize-alice',
            expected_revision=rev,reason='Independent current roots support a bounded interpretation').update_id,
            update.update_id)
        f.reopen()
        self.assertEqual(f.core.recognition.commit(ids[0],command_id='recognize-alice',
            expected_revision=rev,reason='Independent current roots support a bounded interpretation').update_id,
            update.update_id)
        request=f.request();f.submit(request)
        before=tree_inventory_hash(f.runtime.data_root)
        view=f.core.recognition.read(f.context(request))
        self.assertEqual(len(view['entries']),1)
        self.assertEqual(view['entries'][0]['status'],'CURRENT')
        self.assertEqual(len(view['entries'][0]['roots']),3)
        self.assertEqual(view['change_history'][0]['operation'],'FORM')
        self.assertEqual(view['change_history'][0]['reason'],
                         'Independent current roots support a bounded interpretation')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.experience('counter',conclusion='不喜欢螺蛳粉',polarity='COUNTER',
                        corrects='喜欢螺蛳粉')
        request=f.request();f.submit(request)
        view=f.core.recognition.read(f.context(request))
        self.assertEqual(len(view['entries'][0]['counterevidence']),1)
        self.assertEqual(view['entries'][0]['status'],'CONTESTED')

    def test_same_root_and_different_object_cannot_corroborate(self):
        f=self.f
        one=self.experience('one')
        with self.assertRaises(LearningValidationError):
            f.core.recognition.validate(one,(one,one))
        other=self.experience('other',object_id='user:bob',alias='小林')
        third=self.experience('three')
        with self.assertRaises(LearningValidationError):
            f.core.recognition.validate(one,(other,third))
        subject=self.experience('subject',object_id='user:alice',alias='小林',owner='SUBJECT')
        with self.assertRaises(LearningValidationError):
            f.core.recognition.validate(one,(third,subject))
        self.assertIsNone(f.runtime.subject_state().relationship.objects)

    def test_expired_transient_interpretation_cannot_become_current(self):
        f=self.f
        ids=[self.experience(name,expires_after=timedelta(seconds=30))
             for name in ('one','two','three')]
        f.core.recognition.validate(ids[0],ids[1:])
        f.runtime.clock.advance(timedelta(minutes=1))
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(LearningValidationError):
            f.core.recognition.commit(ids[0],command_id='expired-taste',
                expected_revision=f.runtime.subject_state().revision,
                reason='Expired temporary source is not current')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_revoked_support_blocks_commit_without_state_write(self):
        f=self.f
        ids=[self.experience(name) for name in ('one','two','three')]
        f.core.recognition.validate(ids[0],ids[1:])
        f.permission.references_allowed=False
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(LearningValidationError):
            f.core.recognition.commit(ids[0],command_id='unapproved',
                expected_revision=f.runtime.subject_state().revision,reason='No current permission')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_read_rechecks_permission_before_return_without_writing(self):
        f=self.f;request=f.request();f.submit(request)
        before=tree_inventory_hash(f.runtime.data_root)
        original=f.core.subject_states.get_update_history
        def revoke(subject_id):
            rows=original(subject_id)
            f.permission.references_allowed=False
            return rows
        with patch.object(f.core.subject_states,'get_update_history',side_effect=revoke):
            with self.assertRaises(LearningValidationError):
                f.core.recognition.read(f.context(request))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_revised_conclusion_keeps_old_evolution_and_revocation_marks_view_stale(self):
        f=self.f
        first=[self.experience(name) for name in ('one','two','three')]
        f.core.recognition.validate(first[0],first[1:])
        before=f.runtime.subject_state().revision
        old=f.core.recognition.commit(first[0],command_id='old-view',expected_revision=before,
                                      reason='Initial three independent roots')
        second=[self.experience(name,conclusion='后来不喜欢螺蛳粉',corrects='喜欢螺蛳粉')
                for name in ('four','five','six')]
        f.core.recognition.validate(second[0],second[1:])
        revised=f.core.recognition.commit(second[0],command_id='new-view',
            expected_revision=f.runtime.subject_state().revision,reason='New independent counter-history')
        self.assertGreater(revised.after_revision,old.after_revision)
        self.assertEqual(f.runtime.subject_state().relationship.objects['entries'][-1]['version'],2)
        request=f.request();f.submit(request)
        change_view=f.core.recognition.read(f.context(request))
        self.assertEqual([row['operation'] for row in change_view['change_history']],
                         ['FORM','REPLACE'])
        self.assertTrue(change_view['change_history'][-1]['prior_hash'].startswith('sha256:'))
        self.assertIn(old.update_id,[u.update_id for u in f.runtime.subject_states.get_update_history(
            f.runtime.descriptor.subject_id)])
        now=f.runtime.clock.now()
        revocation=Event.create(event_id='revoke-five',occurred_at=now,source='w03.synthetic-revocation',
            event_type='source_revocation',classification=EventClassification.REVOCATION,
            impact_scope=[StateSection.RELATIONSHIP],mutations=[],content='Synthetic source withdrawn',
            reason='Withdraw one supporting experience',references=[EventReference(
                'five',f.runtime.descriptor.subject_id,EventRelationType.REVOKES)])
        f.runtime.subject_states.apply_event(f.runtime.descriptor.subject_id,revocation)
        request=f.request();f.submit(request)
        view=f.core.recognition.read(f.context(request))
        self.assertEqual(view['entries'][0]['status'],'STALE_REVIEW_REQUIRED')

    def test_validated_contrary_roots_withdraw_without_erasing_history(self):
        f=self.f
        support=[self.experience(name) for name in ('one','two','three')]
        f.core.recognition.validate(support[0],support[1:])
        original=f.core.recognition.commit(support[0],command_id='current',
            expected_revision=f.runtime.subject_state().revision,reason='Independent support')
        counter=[self.experience(name,conclusion='不喜欢螺蛳粉',polarity='COUNTER',
                    corrects='喜欢螺蛳粉') for name in ('four','five','six')]
        f.core.recognition.validate(counter[0],counter[1:])
        revision=f.runtime.subject_state().revision
        withdrawn=f.core.recognition.withdraw(counter[0],command_id='withdraw',
            expected_revision=revision,reason='Current independent contrary evidence')
        self.assertEqual(f.runtime.subject_state().revision,revision+1)
        self.assertEqual(f.core.recognition.withdraw(counter[0],command_id='withdraw',
            expected_revision=revision,reason='Current independent contrary evidence').update_id,
            withdrawn.update_id)
        self.assertEqual(f.runtime.subject_state().relationship.objects['entries'],[])
        self.assertIn(original.update_id,[u.update_id for u in f.runtime.subject_states.get_update_history(
            f.runtime.descriptor.subject_id)])
        f.reopen();request=f.request();f.submit(request)
        view=f.core.recognition.read(f.context(request))
        self.assertEqual(view['entries'],())
        self.assertEqual(view['change_history'][-1]['operation'],'WITHDRAW')
        self.assertEqual(view['change_history'][-1]['reason'],
                         'Current independent contrary evidence')

    def test_raw_messages_enter_w02_then_original_learning_before_recognition(self):
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        from continuity_engine.domain.context_composition import ContextBudget
        f=W02InputFixture(self.f.root/'raw-chain',subject_growth=True,
                          gates=ContinuityCoreGates(input_processing=True),
                          context_budget=ContextBudget(token_limit=4096))
        evidence=[]
        for number in range(3):
            f.runtime.clock.advance(timedelta(seconds=1))
            now=f.runtime.clock.now()
            event_id='original-'+str(number)
            content='小林说她喜欢螺蛳粉。第'+str(number+1)+'次独立经历。'
            descriptor={'object_id':'user:alice','owner':'USER','aliases':['小林'],
                        'scope':'food-preference','conclusion':'喜欢螺蛳粉',
                        'polarity':'SUPPORT','valid_at':now.isoformat().replace('+00:00','Z'),
                        'source_type':'TEST_MESSAGE_EXPERIENCE'}
            value='recognition:'+digest([descriptor['owner'],descriptor['object_id'],
                descriptor['scope'],descriptor['conclusion'],descriptor['polarity']])[7:]
            event=Event.create(event_id=event_id,occurred_at=now,observed_at=now,recorded_at=now,
                source='w03.synthetic-message',source_kind=EventSourceKind.TEST,
                event_type='message_experience',classification=EventClassification.INTERACTION,
                content=content,impact_scope=[StateSection.RELATIONSHIP],mutations=[],
                reason='Isolated original message',metadata={'w03_recognition':descriptor,
                    'learning_observation':content,'learning_hypothesis':'喜欢螺蛳粉',
                    'learning_field_path':'relationship.interaction_preferences',
                    'learning_value':value,'learning_confidence':0.85})
            f.runtime.subject_states.apply_event(f.runtime.descriptor.subject_id,event)
            request=f.message(content,source_event_id=event_id)
            f.submit(request)
            record=f.record(request)
            self.assertEqual(record.manifest['source']['source_event_id'],event_id)
            self.assertIsNotNone(f.context(request).composition.snapshot)
            candidates=[candidate for candidate in f.core.growth.learning.list_learning_events(
                f.runtime.descriptor.subject_id) if candidate.source_event_id==event_id]
            self.assertEqual(len(candidates),1,repr({
                'fragments':[(fragment.source_id,fragment.provenance_roots)
                             for fragment in f.context(request).composition.snapshot.fragments],
                'route':[(ref.source_id,ref.stable_id) for ref in f.context(request).route.manifest.candidates]}))
            candidate=candidates[0]
            evidence.append(candidate.learning_id)
        f.core.recognition.validate(evidence[0],evidence[1:])
        before=f.runtime.subject_state().revision
        f.core.recognition.commit(evidence[0],command_id='raw-message-recognition',
            expected_revision=before,reason='Independent messages through original input and Learning')
        self.assertEqual(f.runtime.subject_state().revision,before+1)
        request=f.message('你好，今天还好吗？')
        f.submit(request)
        self.assertEqual(f.core.recognition.read(f.context(request))['entries'][0]['status'],'CURRENT')


if __name__=='__main__':
    unittest.main()
