from datetime import timedelta
from pathlib import Path
import tempfile
import unittest


class MindCoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        self.temp = tempfile.TemporaryDirectory(prefix='p14-core-')
        self.addCleanup(self.temp.cleanup)
        self.fixture = P14Fixture(Path(self.temp.name))

    def test_normal_c1_commits_mind_through_original_evolution(self):
        f = self.fixture
        f.runtime.clock.advance(timedelta(hours=2))
        before = f.state.revision
        request = f.request()
        result = f.submit(request)
        self.assertIsNotNone(result)
        self.assertEqual(f.state.revision, before + 1)
        self.assertTrue(f.state.intentions.dynamic_mind['desires'])
        updates = f.runtime.subject_states.get_update_history(f.state.subject_id)
        self.assertEqual(updates[-1].event.source, 'action_engine')
        self.assertEqual(updates[-1].event.mutations[-1].field_path, 'intentions.dynamic_mind')
        self.assertIsNotNone(f.context(request).mind)

    def test_two_sessions_and_reopen_continue_one_mind(self):
        f = self.fixture
        f.runtime.clock.advance(timedelta(hours=2))
        first = f.request(); f.submit(first)
        original = f.state.intentions.dynamic_mind
        f.reopen()
        self.assertEqual(original, f.state.intentions.dynamic_mind)
        f.runtime.clock.advance(timedelta(hours=1))
        second = f.request(); f.submit(second)
        self.assertGreater(f.state.intentions.dynamic_mind['subjective_seconds'], original['subjective_seconds'])
        self.assertEqual(f.state.intentions.dynamic_mind['subject_id'], f.state.subject_id)

    def test_completed_replay_does_not_advance_revision_or_repeat_effect(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        f = self.fixture
        f.runtime.clock.advance(timedelta(hours=2))
        request = f.request(); first = f.submit(request)
        before = (f.state.to_dict(), f.adapter.effect_count, f.adapter.credits)
        f.reopen()
        # P13 revalidates access to expression text separately from historical
        # receipts/Evolution. The committed revision invalidates the old input.
        facts = f.app.adapter._service.expression_outcome(request['requestId'])
        self.assertEqual(facts['status'], 'CURRENTLY_UNAVAILABLE')
        self.assertIsNone(facts['artifact'])
        self.assertEqual(facts['verified_facts']['state_revision'], before[0]['revision'])
        self.assertIsNotNone(facts['verified_facts']['update_id'])
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(first.to_dict(), f.app.ledger.load_completed(request['requestId']).to_dict())
        self.assertEqual(before, (f.state.to_dict(), f.adapter.effect_count, f.adapter.credits))

    def test_feature_off_keeps_legacy_serialization_and_behavior(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f = P14Fixture(Path(self.temp.name), mind_enabled=False)
        before = f.state.revision
        request = f.request(); f.submit(request)
        self.assertEqual(f.state.revision, before)
        self.assertNotIn('dynamic_mind', f.state.to_dict()['intentions'])
        self.assertNotIn('mind', f.context(request).to_dict())

    def test_native_feature_off_does_not_read_p14_recovery_or_prepare(self):
        from unittest.mock import patch
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f=P14Fixture(Path(self.temp.name),mind_enabled=False)
        awakening=f.app.adapter._service._awakening
        with patch.object(awakening,'get_session',side_effect=AssertionError('disabled P14 recovery read')) as read, \
                patch.object(f.core,'prepare',side_effect=AssertionError('disabled P14 prepare')) as prepare:
            value=f.opportunity('legacy-opportunity')
            self.assertIsNone(value.perception.continuity_context)
            read.assert_not_called();prepare.assert_not_called()
        self.assertIsNone(f.state.intentions.dynamic_mind)

    def test_native_opportunity_without_observation_creates_desire_and_restores(self):
        f = self.fixture
        f.runtime.clock.advance(timedelta(hours=2))
        before = f.state.revision
        first = f.opportunity('mind-opportunity-one')
        self.assertEqual(first.perception.external_facts, ())
        self.assertTrue(f.state.intentions.dynamic_mind['desires'])
        self.assertEqual(f.state.revision, before + 1)
        original = f.state.to_dict()
        f.reopen()
        restored = f.opportunity('mind-opportunity-one')
        self.assertEqual(restored.state_update.to_dict(), first.state_update.to_dict())
        self.assertEqual(original, f.state.to_dict())

    def test_normal_c1_appraises_sources_and_apology_does_not_reset_episode(self):
        f = self.fixture
        f.affective_event('boundary-one', object_id='peer', observation='boundary_crossed')
        f.runtime.clock.advance(timedelta(minutes=1))
        first = f.request(); f.submit(first)
        anger = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind'] == 'anger')
        self.assertIn('boundary-one', anger['source_keys'][0])
        f.affective_event('apology-one', object_id='peer', observation='apology_offered')
        f.runtime.clock.advance(timedelta(minutes=1))
        second = f.request(); f.submit(second)
        ongoing = next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['id'] == anger['id'])
        self.assertEqual(ongoing['status'], 'unresolved')
        self.assertIsNone(ongoing['resolution'])
        self.assertTrue(f.context(second).mind['influence']['interpretations'])
        self.assertIn('QUESTION', f.context(second).mind['influence']['decisions'])

    def test_unsettled_interpretation_changes_actual_information_need(self):
        f = self.fixture
        f.affective_event('needs-understanding', object_id='peer', observation='boundary_crossed')
        f.runtime.clock.advance(timedelta(minutes=1))
        request = f.request(); f.submit(request)
        operation = f.app.ledger.load_operation(request['requestId'])
        session = f.app.adapter._service._thinking.get_session(f.state.subject_id,
            operation.domain_progress.think_session_id)
        self.assertTrue(session.result.request_more_memory)
        self.assertEqual(f.core.last_action.requests[0].choice.trigger, 'INFORMATION_NEED')
        self.assertEqual(f.core.last_action.requests[0].step.capability, 'memory.lookup')

    def test_normal_chain_attempts_regulation_without_erasing_episode(self):
        f = self.fixture
        # A genuinely later experience, not a tie with the genesis event under
        # the same bounded Composer budget (tie selection is intentionally stable).
        f.runtime.clock.advance(timedelta(hours=1))
        f.affective_event('regulation-concern', object_id='peer', observation='boundary_crossed')
        f.runtime.clock.advance(timedelta(minutes=1)); f.submit(f.request())
        f.runtime.clock.advance(timedelta(minutes=2)); f.submit(f.request())
        mind = f.state.intentions.dynamic_mind
        self.assertIn(mind['regulation'].get('outcome'), {'success', 'failure'})
        self.assertEqual(mind['episodes'][0]['status'], 'unresolved')

    def test_capability_wait_resumes_mind_in_original_think_session(self):
        from continuity_engine.domain.capability import IntegrationThinkingMode, CapabilityRequiredEnvelope
        from tests.test_e5_capability_flow import capability_result_payload
        f = self.fixture
        f.thinking_mode = IntegrationThinkingMode.CAPABILITY; f.reopen()
        f.runtime.clock.advance(timedelta(hours=1))
        request = f.request(); waiting = f.submit(request)
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
        self.assertIsNone(f.state.intentions.dynamic_mind)
        f.reopen()
        self.assertEqual(waiting.to_dict(), f.submit(request).to_dict())
        f.runtime.clock.advance(timedelta(seconds=3))
        f.app.adapter.submit_capability_result(capability_result_payload(waiting, response='A bounded synthetic response.'))
        self.assertIsNotNone(f.state.intentions.dynamic_mind)
        self.assertEqual(f.state.revision, 2)

    def test_new_commit_expired_or_revoked_after_thinking_is_blocked(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        for change in ('expiry', 'revoke'):
            with self.subTest(change=change):
                from continuity_engine.testing.p14_mind_fixture import P14Fixture
                f = P14Fixture(Path(self.temp.name))
                f.runtime.clock.advance(timedelta(hours=1)); request = f.request()
                def stop(stage, operation):
                    if stage == 'after_thinking_completed':
                        raise RuntimeError('P14 controlled crash before new Evolution')
                f.app.adapter._service._fault_injector = stop
                with self.assertRaises(IntegrationExecutionError): f.submit(request)
                original = f.state.to_dict()
                if change == 'expiry': f.runtime.clock.advance(timedelta(minutes=11))
                else: f.permission.references_allowed = False
                f.reopen()
                with self.assertRaises(IntegrationExecutionError): f.submit(request)
                self.assertEqual(original, f.state.to_dict())
                self.assertEqual(f.adapter.execute_calls, 0)

    def test_completed_mind_facts_still_require_real_adapter_receipt(self):
        from unittest.mock import patch
        from continuity_engine.domain.action_capability import ReceiptQuery
        from continuity_engine.domain.errors import CapabilityValidationError
        f = self.fixture
        f.runtime.clock.advance(timedelta(hours=1)); request=f.request(); f.submit(request)
        before=(f.state.to_dict(), f.adapter.path.read_bytes())
        with patch.object(f.adapter, 'query', return_value=ReceiptQuery.UNKNOWN) as query:
            with self.assertRaises(CapabilityValidationError):
                f.app.adapter._service.expression_outcome(request['requestId'])
            self.assertGreater(query.call_count, 0)
        self.assertEqual(before, (f.state.to_dict(), f.adapter.path.read_bytes()))

    def test_current_candidate_tampering_and_cross_subject_are_rejected(self):
        from copy import deepcopy
        from dataclasses import replace
        from continuity_engine.domain.errors import IntegrationExecutionError,CapabilityValidationError
        f = self.fixture; f.runtime.clock.advance(timedelta(hours=1)); request=f.request()
        def stop(stage, operation):
            if stage == 'after_thinking_completed': raise RuntimeError('P14 captured input')
        f.app.adapter._service._fault_injector=stop
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        context=f.context(request)
        m=deepcopy(context.mind);m['influence']['decisions']=['DEFER']
        self.assertFalse(f.core.current(replace(context,mind=m)))
        m=deepcopy(context.mind);m['proposal']['subject_id']='different-subject'
        with self.assertRaises(CapabilityValidationError): replace(context,mind=m)
        self.assertIsNone(f.state.intentions.dynamic_mind)

    def test_raw_provider_cannot_supply_dynamic_mind_mutation(self):
        from unittest.mock import patch
        from dataclasses import replace
        from continuity_engine.domain.events import StateMutation, ChangeOperation
        from continuity_engine.domain.errors import IntegrationExecutionError
        f=self.fixture; f.runtime.clock.advance(timedelta(hours=1))
        original=f.provider.think
        def fake(perception,budget):
            r=original(perception,budget)
            return replace(r,update_subject_state=True,proposed_mutations=[StateMutation(
                'intentions.dynamic_mind',ChangeOperation.SET,perception.continuity_context.mind['proposal'],
                'Unauthorized provider-supplied state')])
        with patch.object(f.provider,'think',side_effect=fake):
            with self.assertRaises(IntegrationExecutionError): f.submit(f.request())
        self.assertIsNone(f.state.intentions.dynamic_mind)
        self.assertEqual(f.adapter.execute_calls,0)

    def test_internal_body_changes_real_choice_with_same_provider_output(self):
        from continuity_engine.domain.dynamic_mind import MindState
        from continuity_engine.domain.events import StateMutation,ChangeOperation,EventClassification
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        choices=[];modes=[]
        for fatigue in (.01,.95):
            f=P14Fixture(Path(self.temp.name))
            mind=MindState.create(f.state.subject_id,'TEST',f.runtime.clock.now()).with_body(
                fatigue=fatigue,tension=fatigue,restlessness=fatigue)
            # Explicit isolated State Fixture seed; subsequent C1 commit remains
            # through the real Action/Evolution path, with identical provider text.
            f.event('body-seed',classification=EventClassification.STATE_CHANGE,
                mutations=[StateMutation('intentions.dynamic_mind',ChangeOperation.SET,
                mind.to_dict(),'Explicit synthetic body contrast')])
            f.runtime.clock.advance(timedelta(minutes=1));r=f.request();f.submit(r)
            choices.append(f.core.last_action.requests[0].step.capability)
            modes.append(f.artifact(r).decision.mode)
        self.assertEqual(choices,['expression.emit','silence'])
        self.assertEqual(modes,['PURSUE','DEFER'])

    def test_cognitive_resolution_requires_new_consistent_experience(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.fixture;f.affective_event('a-harm',object_id='peer',observation='boundary_crossed')
        # Two independently current examples require room for both; the
        # insufficient-budget counterexample must remain unresolved.
        f.core.context_budget=ContextBudget(token_limit=1000)
        f.runtime.clock.advance(timedelta(minutes=1));f.submit(f.request())
        original=next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['kind']=='anger')
        for index in (1,2):
            f.runtime.clock.advance(timedelta(minutes=1))
            f.affective_event('repair-'+str(index),object_id='peer',observation='expectation_met')
            f.runtime.clock.advance(timedelta(seconds=1));f.submit(f.request())
            episode=next(e for e in f.state.intentions.dynamic_mind['episodes'] if e['id']==original['id'])
            self.assertEqual(episode['status'],'processing' if index==1 else 'resolved')
            self.assertTrue(episode['resolution']['reason'])

    def test_snapshot_branch_includes_mind_without_polluting_parent(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from continuity_engine.testing.persistence import tree_inventory_hash
        f=self.fixture;f.runtime.clock.advance(timedelta(hours=1));f.opportunity('parent')
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id)
        before=tree_inventory_hash(f.runtime.data_root)
        fork=P14Fixture(Path(self.temp.name),runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch),
                        manager=f.manager)
        self.assertEqual(fork.state.intentions.dynamic_mind,f.state.intentions.dynamic_mind)
        fork.runtime.clock.advance(timedelta(hours=1));fork.opportunity('branch')
        self.assertNotEqual(fork.state.intentions.dynamic_mind,f.state.intentions.dynamic_mind)
        self.assertEqual(before,tree_inventory_hash(f.runtime.data_root))

    def test_path_protection_before_any_fixture_write(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from continuity_engine.testing.models import SandboxOperationError
        from tests.test_p14_mind_visibility import inventory
        for index,name in enumerate(('.continuity-data','.CONTINUITY-DATA','.Assistant-Data')):
            root=Path(self.temp.name)/str(index)/name;root.mkdir(parents=True)
            before=inventory(Path(self.temp.name))
            with self.assertRaises(SandboxOperationError):P14Fixture(root/'child')
            self.assertEqual(before,inventory(Path(self.temp.name)))
            self.assertFalse((root/'child').exists())

    def test_bounded_golden_survives_real_process_restarts(self):
        from continuity_engine.testing.p14_mind_fixture import run_golden
        result=run_golden(Path(self.temp.name))
        import json
        print(json.dumps(result,ensure_ascii=False))
        self.assertEqual(result['processRestarts'],2)
        self.assertEqual(result['rounds'],6)
        self.assertEqual(len(set(result['subjectIds'])),1)
        self.assertTrue(result['noDuplicateNativeCommit'])
        self.assertGreater(result['subjectiveSeconds'],result['logicalSeconds'])

    def test_native_evolution_saved_before_checkpoint_recovers_after_expiry(self):
        from unittest.mock import patch
        from continuity_engine.services.action_evolution_service import ActionEvolutionService
        f=self.fixture;f.runtime.clock.advance(timedelta(hours=1))
        original=ActionEvolutionService.evolve
        def crash(service,*args,**kwargs):
            update=original(service,*args,**kwargs)
            self.assertIsNotNone(update)
            raise RuntimeError('P14 crash after actual Evolution before checkpoint')
        with patch.object(ActionEvolutionService,'evolve',crash):
            with self.assertRaisesRegex(RuntimeError,'after actual Evolution'):f.opportunity('native-crash')
        before=f.state.to_dict();f.runtime.clock.advance(timedelta(hours=1));f.permission.references_allowed=False
        f.reopen();restored=f.opportunity('native-crash')
        self.assertIsNotNone(restored.state_update)
        self.assertEqual(before,f.state.to_dict());self.assertEqual(f.provider.calls,0)

    def test_native_missing_evolution_fact_is_rejected_without_writes(self):
        from unittest.mock import patch
        from continuity_engine.services.action_evolution_service import ActionEvolutionService
        from continuity_engine.domain.dynamic_mind import MindValidationError
        from tests.test_p14_mind_visibility import inventory
        f=self.fixture;f.runtime.clock.advance(timedelta(hours=1));f.opportunity('native-fact')
        before=inventory(f.runtime.data_root)
        with patch.object(ActionEvolutionService,'find_update_by_event_id',return_value=None):
            with self.assertRaises(MindValidationError):f.opportunity('native-fact')
        self.assertEqual(before,inventory(f.runtime.data_root))

    def test_attention_changes_actual_authorized_memory_ranking(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        f=self.fixture
        f.event('intimacy-source',content='intimacy intimacy')
        f.event('exploration-source',content='exploration exploration')
        def stop(stage,operation):
            if stage=='after_thinking_completed':raise RuntimeError('retain same original perception for contrast')
        f.app.adapter._service._fault_injector=stop;r=f.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        perception=f.app.ledger.load_operation(r['requestId']).domain_progress.perception
        from dataclasses import replace
        perception=replace(perception,continuity_context=None)
        rankings=[]
        for theme in ('intimacy','exploration'):
            route=f.core.router.route(perception,request_id='attention-'+theme,environment='TEST',
                attention={'themes':[theme],'breadth':1,'narrowing':.8})
            rankings.append(next(c.stable_id for c in route.manifest.candidates if c.source_id=='engine.memory'))
        self.assertEqual(rankings,['memory:intimacy-source','memory:exploration-source'])
        self.assertIsNone(f.state.intentions.dynamic_mind)

    def test_forgotten_or_revoked_current_source_cannot_finish_new_mind(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        from continuity_engine.domain.memory import MemoryLineageType
        f=self.fixture;f.affective_event('a-current-source',object_id='peer',observation='boundary_crossed')
        f.runtime.clock.advance(timedelta(minutes=1));r=f.request()
        def stop(stage,operation):
            if stage=='after_thinking_completed':raise RuntimeError('P14 before state commit')
        f.app.adapter._service._fault_injector=stop
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        context=f.context(r);self.assertTrue(f.core.current(context))
        f.core.consolidation.propagate_signal(f.state.subject_id,lineage_id='p14-delete',
            target_memory_id='memory:a-current-source',signal=MemoryLineageType.DELETION,
            source_event_id='explicit-test-deletion',root_evidence_ids=['event:explicit-test-deletion'])
        before=f.state.to_dict();self.assertFalse(f.core.current(context));f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(before,f.state.to_dict());self.assertEqual(f.adapter.execute_calls,0)

    def test_old_concurrent_candidate_cannot_overwrite_new_revision(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        f=self.fixture;f.runtime.clock.advance(timedelta(hours=1))
        def stop(stage,operation):
            if stage=='after_thinking_completed':raise RuntimeError('P14 two in-flight candidates')
        requests=[f.request(),f.request()]
        for r in requests:
            f.app.adapter._service._fault_injector=stop
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.context(requests[0]).mind['source_revision'],f.context(requests[1]).mind['source_revision'])
        f.reopen();f.submit(requests[0]);before=f.state.to_dict()
        with self.assertRaises(IntegrationExecutionError):f.submit(requests[1])
        self.assertEqual(before,f.state.to_dict())

    def test_complex_information_need_still_uses_original_optional_planner(self):
        f=self.fixture;f.mode='complex';f.reopen();f.runtime.clock.advance(timedelta(hours=1))
        f.submit(f.request())
        self.assertIsNotNone(f.core.last_action.plan)
        self.assertEqual([r.step.capability for r in f.core.last_action.requests],['memory.lookup','contact.send'])
        self.assertEqual(f.state.revision,2)

    def explicit_decision_control(self,mode):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f=P14Fixture(Path(self.temp.name),expression_mode=mode)
        f.runtime.clock.advance(timedelta(hours=1));request=f.request();f.submit(request)
        self.assertEqual(f.artifact(request).decision.mode,mode)
        self.assertTrue(f.state.intentions.dynamic_mind['desires'])
        if mode=='SILENCE':
            self.assertEqual(f.core.last_action.requests[0].step.capability,'silence')

    def test_explicit_subject_refusal_is_not_erased_by_generic_drive(self):
        self.explicit_decision_control('REFUSE')

    def test_explicit_subject_silence_is_not_relabelled_pursuit(self):
        self.explicit_decision_control('SILENCE')

    def test_explicit_subject_confrontation_is_retained(self):
        self.explicit_decision_control('CONFRONT')


if __name__ == '__main__':
    unittest.main()
