"""Mechanism contrasts: no preselected provider reply or real external input."""
from datetime import datetime, timedelta, timezone
import unittest


class DynamicMindMechanismTests(unittest.TestCase):
    def setUp(self):
        # Lazy import keeps the original suite discoverable during the red run.
        from continuity_engine.domain.dynamic_mind import MindState
        from continuity_engine.services.dynamic_mind_service import MindDynamics
        self.at = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.state = MindState.create('subject-a', 'TEST', self.at)
        self.dynamics = MindDynamics()

    def test_no_observation_forms_endogenous_desire(self):
        result = self.dynamics.advance(self.state, at=self.at + timedelta(hours=2))
        self.assertTrue(result.state.desires)
        self.assertTrue(all(d['origin'] == 'ENDOGENOUS' for d in result.state.desires))
        self.assertNotEqual(result.state.to_dict(), self.state.to_dict())
        self.assertEqual(self.state.desires, [])

    def test_same_time_replay_has_no_extra_dynamic_change(self):
        at = self.at + timedelta(hours=2)
        first = self.dynamics.advance(self.state, at=at)
        again = self.dynamics.advance(first.state, at=at)
        self.assertEqual(first.state.to_dict(), again.state.to_dict())

    def test_psychological_opposites_remain_together(self):
        state = self.state.with_dispositions([
            {'object': 'peer', 'kind': 'LOVE', 'basis': ['prior:care', 'prior:attachment']},
            {'object': 'peer', 'kind': 'HATE', 'basis': ['prior:harm', 'prior:betrayal', 'prior:unresolved']},
        ])
        result = self.dynamics.advance(state, at=self.at + timedelta(hours=2))
        self.assertEqual(result.state.dispositions, state.dispositions)
        self.assertTrue(result.state.conflicts)
        self.assertEqual(set(result.state.conflicts[0]['poles']), {'LOVE', 'HATE'})

    def test_subjective_time_depends_on_attention_and_somatic_state(self):
        rested = self.state.with_body(fatigue=0.1, tension=0.1, restlessness=0.1)
        strained = self.state.with_body(fatigue=0.9, tension=0.9, restlessness=0.9)
        at = self.at + timedelta(minutes=20)
        a = self.dynamics.advance(rested, at=at)
        b = self.dynamics.advance(strained, at=at)
        self.assertNotEqual(a.state.subjective_seconds, b.state.subjective_seconds)
        self.assertNotEqual(a.influence['attention'], b.influence['attention'])
        self.assertEqual(a.state.updated_at, b.state.updated_at)
        self.assertEqual(rested.updated_at, self.at)

    def test_suppression_can_fail_without_erasing_concern(self):
        strained = self.state.with_body(fatigue=0.95, tension=0.95, restlessness=0.95)
        first = self.dynamics.advance(strained, at=self.at + timedelta(hours=2))
        desired = first.state.desires[0]['id']
        result = self.dynamics.advance(first.state, at=first.state.updated_at + timedelta(minutes=1),
                                       regulation={'strategy': 'suppress', 'desire_id': desired,
                                                   'reason': 'The subject wants to stop returning to this concern.'})
        self.assertEqual(result.state.regulation['outcome'], 'failure')
        self.assertTrue(any(d['id'] == desired and d['phase'] == 'fail_to_suppress'
                            for d in result.state.desires))
        self.assertTrue(result.state.thoughts)

    def test_will_records_deliberation_not_scheduler_priority(self):
        result = self.dynamics.advance(self.state, at=self.at + timedelta(hours=2))
        self.assertTrue(result.state.will)
        for evaluation in result.state.will:
            self.assertTrue(evaluation['supporting_reasons'])
            self.assertIn('alternatives', evaluation)
            self.assertIn('opposing_reasons', evaluation)
            self.assertIn('desire_id', evaluation)
            self.assertFalse({'priority', 'reward', 'score'} & set(evaluation))

    def test_persisted_state_restores_without_reset(self):
        from continuity_engine.domain.dynamic_mind import MindState
        state = self.dynamics.advance(self.state, at=self.at + timedelta(hours=3)).state
        self.assertEqual(MindState.from_dict(state.to_dict()).to_dict(), state.to_dict())

    def test_clock_regression_and_cross_environment_are_rejected(self):
        from continuity_engine.domain.dynamic_mind import MindValidationError, MindState
        with self.assertRaises(MindValidationError):
            self.dynamics.advance(self.state, at=self.at - timedelta(seconds=1))
        document = self.state.to_dict()
        document['environment'] = 'PRODUCTION'
        with self.assertRaises(MindValidationError):
            MindState.from_dict(document)

    def test_apology_is_new_evidence_not_automatic_resolution(self):
        hurt = {'source_key': 'event:hurt:hash', 'object': 'peer', 'kind': 'anger',
                'interpretation': 'An agreed boundary was crossed.', 'unresolved': 'Whether the boundary will be respected.',
                'intensity': 0.8}
        apology = {'source_key': 'event:apology:hash', 'object': 'peer', 'kind': 'joy',
                   'interpretation': 'An apology was offered, without yet demonstrating change.',
                   'unresolved': 'Whether the promise will be fulfilled.', 'intensity': 0.4}
        first = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1), appraisals=[hurt])
        second = self.dynamics.advance(first.state, at=self.at + timedelta(hours=2), appraisals=[apology])
        anger = next(e for e in second.state.episodes if e['kind'] == 'anger')
        self.assertEqual(anger['status'], 'unresolved')
        self.assertIsNone(anger['resolution'])
        self.assertTrue(anger['source_keys'])
        self.assertEqual(second.state.dispositions, [])

    def test_duplicate_appraisal_does_not_reinforce_same_time(self):
        item = {'source_key': 'event:one:hash', 'object': 'peer', 'kind': 'anger',
                'interpretation': 'An agreement was violated.', 'unresolved': 'Future reliability.', 'intensity': 0.8}
        first = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1), appraisals=[item])
        repeated = self.dynamics.advance(first.state, at=first.state.updated_at, appraisals=[item])
        self.assertEqual(first.state.to_dict(), repeated.state.to_dict())

    def test_weaken_and_transform_change_desire_not_only_phase(self):
        first = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1))
        original = first.state.desires[0]
        weakened = self.dynamics.advance(first.state, at=first.state.updated_at,
            outcomes=[{'desire_id': original['id'], 'phase': 'weaken', 'reason': 'The imagined outcome matters less now.'}])
        target = next(d for d in weakened.state.desires if d['id'] == original['id'])
        self.assertLess(target['strength'], original['strength'])
        transformed = self.dynamics.advance(weakened.state, at=weakened.state.updated_at,
            outcomes=[{'desire_id': original['id'], 'phase': 'transform',
                       'reason': 'Instead of immediate closeness, I want to understand the uncertainty.',
                       'new_drive': 'exploration'}])
        target = next(d for d in transformed.state.desires if d['id'] == original['id'])
        self.assertEqual(target['drive'], 'exploration')
        self.assertEqual(target['phase'], 'transform')

    def test_unknown_nested_reasoning_fields_are_rejected(self):
        from continuity_engine.domain.dynamic_mind import MindState, MindValidationError
        state = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1)).state.to_dict()
        state['desires'][0]['trajectory'][0]['provider_hidden_reasoning'] = 'unprovided synthetic forbidden field'
        with self.assertRaises(MindValidationError):
            MindState.from_dict(state)

    def test_transformed_desire_can_continue_without_identity_collision(self):
        first = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1)).state
        transformed = self.dynamics.advance(first, at=first.updated_at, outcomes=[{
            'desire_id': first.desires[0]['id'], 'phase': 'transform',
            'new_drive': 'exploration', 'reason': 'Seek understanding rather than closeness.'}]).state
        continued = self.dynamics.advance(transformed, at=transformed.updated_at + timedelta(hours=1)).state
        self.assertEqual(len({d['id'] for d in continued.desires}), len(continued.desires))
        self.assertTrue(any(d['drive'] == 'intimacy' for d in continued.desires))

    def test_resolution_then_new_harm_reopens_same_concern(self):
        item = dict(source_key='event:one:hash', object='peer', kind='anger',
                    interpretation='A boundary was crossed.', unresolved='Future respect.', intensity=0.7)
        first = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1), appraisals=[item]).state
        e = first.episodes[0]
        resolved = self.dynamics.advance(first, at=first.updated_at, resolutions=[{
            'episode_id': e['id'], 'interpretation': 'The meaning is now understood.',
            'reason': 'Deliberated understanding of the original evidence.',
            'source_keys': e['source_keys'], 'resolve': True}]).state
        again = self.dynamics.advance(resolved, at=resolved.updated_at + timedelta(hours=1),
            appraisals=[{**item, 'source_key': 'event:two:hash'}]).state
        self.assertEqual(again.episodes[0]['status'], 'unresolved')
        self.assertIsNone(again.episodes[0]['resolution'])

    def test_unbound_will_and_thought_references_fail_closed(self):
        from continuity_engine.domain.dynamic_mind import MindState, MindValidationError
        value = self.dynamics.advance(self.state, at=self.at + timedelta(hours=1)).state.to_dict()
        value['will'][0]['desire_id'] = 'other-subject:desire'
        with self.assertRaises(MindValidationError):
            MindState.from_dict(value)

    def test_subjective_wait_changes_attention_even_with_equal_body(self):
        from dataclasses import replace
        first=self.dynamics.advance(self.state,at=self.at+timedelta(minutes=1)).state
        stretched=replace(first,subjective_seconds=360000.)
        self.assertNotEqual(self.dynamics.influence(first)['attention'],
                            self.dynamics.influence(stretched)['attention'])

    def test_desire_lifecycle_and_regulation_success(self):
        from continuity_engine.domain.dynamic_mind import PHASES
        first=self.dynamics.advance(self.state,at=self.at+timedelta(minutes=1)).state
        seen={d['phase'] for d in first.desires};target=first.desires[0]['id']
        later=self.dynamics.advance(first,at=first.updated_at+timedelta(hours=1)).state
        seen.update(d['phase'] for d in later.desires)
        for phase in ('weaken','persist','disappear','conflict','transform','act','abandon'):
            outcome={'desire_id':target,'phase':phase,'reason':'Explicit internal deliberation outcome: '+phase}
            if phase=='transform':outcome['new_drive']='exploration'
            value=self.dynamics.advance(first,at=first.updated_at,outcomes=[outcome]).state
            seen.add(next(d['phase'] for d in value.desires if d['id']==target))
            if phase=='abandon':
                again=self.dynamics.advance(value,at=value.updated_at+timedelta(hours=1)).state
                seen.add(next(d['phase'] for d in again.desires if d['id']==target))
        for fatigue in (0.,.99):
            value=self.dynamics.advance(first.with_body(fatigue=fatigue,tension=fatigue),at=first.updated_at,
                regulation={'strategy':'suppress','desire_id':target,'reason':'Try to redirect limited attention.'}).state
            seen.add(next(d['phase'] for d in value.desires if d['id']==target))
        self.assertEqual(seen,set(PHASES))

    def test_all_drives_and_somatic_dimensions_are_retained(self):
        from continuity_engine.domain.dynamic_mind import DRIVES, SOMATIC
        first=self.dynamics.advance(self.state,at=self.at+timedelta(hours=1)).state
        self.assertEqual(set(first.drives),set(DRIVES));self.assertEqual(set(first.somatic),set(SOMATIC))
        warmer=self.dynamics.advance(self.state.with_body(warmth=.8,excitement=.8),
                                      at=self.at+timedelta(hours=1)).state
        self.assertGreater(warmer.drives['sexual'],first.drives['sexual'])
        self.assertNotEqual(warmer.arousal,first.arousal)


if __name__ == '__main__':
    unittest.main()
