from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.associative_recall import RecallPolicy,seal_record
from continuity_engine.domain.errors import IntegrationExecutionError,CapabilityValidationError
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture


class RecallCombinationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def tearDown(self):capture_failure(self,self.root)

    def report(self,f,event,text):
        f.event(event,content=text)
        r=f.message(text,source_event_id=event);f.submit(r)
        return r

    def test_t05_actual_ingress_variants_reach_final_context(self):
        cases=[('我不爱吃螺蛳粉。','SELF_REPORTED','NEGATIVE_PREFERENCE_REPORT'),
               ('朋友在吃螺蛳粉。','OTHER_REPORTED','CONSUMPTION_REPORT'),
               ('我想吃但没吃。','SELF_REPORTED','NOT_CONSUMED_REPORT'),
               ('我去年吃过螺蛳粉。','SELF_REPORTED','CONSUMPTION_REPORT'),
               ('我又在吃螺丝粉。','SELF_REPORTED','CONSUMPTION_REPORT'),
               ('我中午用餐。','SELF_REPORTED','CONSUMPTION_REPORT')]
        for index,(text,actor,mode) in enumerate(cases):
            with self.subTest(text=text):
                f=W02RecallFixture(self.root/str(index));r=f.message(text);f.submit(r)
                ctx=f.context(r);frame=ctx.recall['assessment']['frames'][0]
                self.assertEqual((frame['actor'],frame['modality']),(actor,mode))
                self.assertFalse(frame['verified_fact'])
                fragment=next(x for x in ctx.composition.snapshot.fragments if x.source_id=='engine.current-input')
                material=json.loads(fragment.content)
                self.assertEqual(material['content'],text)
                self.assertEqual(material['reading']['frames'][0]['modality'],mode)
                self.assertEqual(material['reading']['authority'],'INTERPRETATION_NOT_FACT')
                self.assertEqual(f.provider.inputs[0].continuity_context,ctx)
                if '去年' in text:self.assertEqual(frame['time'],'HISTORICAL_UNRESOLVED')

    def test_quoted_and_ambiguous_reports_never_confirm_preference(self):
        for index,text in enumerate(('朋友说：“我喜欢螺蛳粉。”','我不是不喜欢螺蛳粉。','如果我吃螺蛳粉呢？')):
            with self.subTest(text=text):
                f=W02RecallFixture(self.root/str(index));r=f.message(text);f.submit(r)
                assessment=f.context(r).recall['assessment']
                self.assertTrue(assessment['uncertain'])
                self.assertTrue(all(not x['confirmed'] for x in f.context(r).recall['preference_candidates']))
                self.assertFalse(any(x['verified_fact'] for x in assessment['frames']))

    def test_t04_replay_and_derived_summary_do_not_add_roots(self):
        f=W02RecallFixture(self.root)
        first=self.report(f,'first','我喜欢螺蛳粉。')
        f.submit(first)
        f.core.consolidation.generate_summary(f.core.subject_id,summary_id='repeated-derived',summary_type='memory',scope='meal',
            source_memory_ids=('memory:first',),confidence=.99)
        r=f.message('我喜欢螺蛳粉。',source_event_id='first');f.submit(r)
        c=f.context(r).recall['preference_candidates'][0]
        self.assertEqual(c['independent_roots'],['event:first'])
        self.assertFalse(c['confirmed'])
        self.assertEqual(c['status'],'INSUFFICIENT_OR_CONTRADICTORY')

    def test_t04_no_fixed_number_implies_true_preference(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(preference_minimum_roots=2))
        self.report(f,'one','我吃了螺蛳粉。')
        r=self.report(f,'two','我又吃了螺蛳粉。')
        c=f.context(r).recall['preference_candidates'][0]
        self.assertEqual(len(c['independent_roots']),2)
        self.assertEqual(c['status'],'INSUFFICIENT_OR_CONTRADICTORY')
        self.assertTrue(c['rule']['preference_require_positive_report'])

    def test_t04_configured_candidate_rule_is_recorded_and_never_confirms(self):
        policy=RecallPolicy(preference_minimum_roots=2,preference_require_positive_report=False)
        f=W02RecallFixture(self.root,recall_policy=policy)
        self.report(f,'one','我吃了螺蛳粉。');r=self.report(f,'two','我又吃了螺蛳粉。')
        c=f.context(r).recall['preference_candidates'][0]
        self.assertEqual(c['status'],'UNCONFIRMED_CANDIDATE')
        self.assertFalse(c['confirmed']);self.assertEqual(c['rule'],policy.to_dict())

    def test_negative_counterevidence_prevents_candidate_confirmation(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(preference_minimum_roots=2))
        self.report(f,'negative','我不爱吃螺蛳粉。')
        self.report(f,'positive','我喜欢螺蛳粉。')
        r=self.report(f,'experience','我吃了螺蛳粉。')
        c=f.context(r).recall['preference_candidates'][0]
        self.assertEqual(c['counter_roots'],['event:negative'])
        self.assertEqual(c['status'],'INSUFFICIENT_OR_CONTRADICTORY')
        self.assertFalse(c['confirmed'])

    def test_other_person_report_does_not_count_as_user_preference(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(preference_minimum_roots=2))
        self.report(f,'friend','朋友喜欢螺蛳粉。')
        r=self.report(f,'self','我喜欢螺蛳粉。')
        c=f.context(r).recall['preference_candidates'][0]
        self.assertEqual(c['independent_roots'],['event:self'])

    def test_finite_association_records_a_reason_and_stops_on_repetition(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(sufficient_roots=20,max_rounds=8,candidate_limit=80))
        f.event('a',content='我吃了面条。');f.event('b',content='我以前吃过螺蛳粉。')
        r=f.message('我又在吃螺蛳粉。');f.submit(r);rec=f.context(r).recall
        self.assertGreater(len(rec['rounds']),1)
        self.assertLess(len(rec['rounds']),8)
        self.assertTrue(any(x['associations'] for x in rec['rounds']))
        self.assertEqual(rec['stop_reason'],'REPEATED_ASSOCIATION')
        self.assertLessEqual(rec['retrieved_count'],80)

    def test_sufficient_material_stops_before_configured_depth(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(sufficient_roots=1,max_rounds=8))
        f.event('meal',content='我吃过螺蛳粉');r=f.message('我又吃螺蛳粉');f.submit(r)
        self.assertEqual(f.context(r).recall['stop_reason'],'SUFFICIENT_MATERIAL')
        self.assertEqual(len(f.context(r).recall['rounds']),1)

    def test_unrelated_material_does_not_trigger_association(self):
        f=W02RecallFixture(self.root);f.event('unrelated',content='量子光学项目')
        r=f.message('我又吃螺蛳粉');f.submit(r);ctx=f.context(r)
        self.assertFalse(any(x.stable_id in {'unrelated','memory:unrelated'} for x in ctx.route.manifest.candidates))
        self.assertFalse(any(x['associations'] for x in ctx.recall['rounds']))

    def test_read_only_view_does_not_start_recall_or_provider(self):
        f=W02RecallFixture(self.root);r=f.message('你好');f.submit(r)
        before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.core.recall,'prepare',side_effect=AssertionError('no preparation')), \
             patch.object(f.core.router,'route',side_effect=AssertionError('no retrieval')), \
             patch.object(f.provider,'think',side_effect=AssertionError('no model')):
            f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_permission_withdrawn_during_view_is_rechecked(self):
        f=W02RecallFixture(self.root);r=f.message('你好');f.submit(r)
        load=f.app.ledger.load_operation;calls=0
        def revoke(request_id):
            nonlocal calls
            op=load(request_id);calls+=1
            if calls==2:f.permission.references_allowed=False
            return op
        before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.app.ledger,'load_operation',side_effect=revoke):
            with self.assertRaises(CapabilityValidationError):f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_blocked_record_after_revision_change_cannot_be_shown_as_current(self):
        from continuity_engine.domain.errors import ContextCompositionSourceError
        f=W02RecallFixture(self.root);r=f.message('我吃了午饭')
        source=next(b.source for b in f.core.router._bindings if b.source.source_id=='engine.memory')
        with patch.object(source,'retrieve',side_effect=ContextCompositionSourceError('SOURCE_READ_FAILED')):
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
        from continuity_engine.domain.events import StateMutation,ChangeOperation,EventClassification
        f.event('later',content='unrelated legal update',classification=EventClassification.STATE_CHANGE,mutations=(
            StateMutation('continuity.current_focus',ChangeOperation.SET,['later focus'],'Explicit independent TEST state change'),))
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(CapabilityValidationError):f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_cross_environment_source_is_rejected_without_resolution(self):
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了午饭');r=f.message('我吃了午饭');f.submit(r)
        ref=next(x for x in f.context(r).route.manifest.candidates if x.source_id=='engine.current-input')
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(Exception):f.core.input_processing.source.resolve(replace(ref,environment='RESEARCH'))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_recalled_information_does_not_force_expression(self):
        f=W02RecallFixture(self.root,mode='silence');f.event('meal',content='我吃过午饭')
        r=f.message('我又在吃午饭');f.submit(r)
        self.assertEqual(f.provider.calls,1)
        self.assertEqual(f.context(r).recall['status'],'READY')
        self.assertEqual(f.adapter.effect_count,0)

    def test_snapshot_branch_preserves_recall_and_does_not_pollute_origin(self):
        f=W02RecallFixture(self.root);r=f.message('你好');result=f.submit(r)
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.runtime.subject_state().revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id)
        before=tree_inventory_hash(f.runtime.data_root)
        runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
        fork=W02RecallFixture(self.root,runtime=runtime,manager=f.manager)
        self.assertEqual(fork.submit(r).to_dict(),result.to_dict())
        self.assertEqual(fork.context(r).recall,f.context(r).recall)
        self.assertEqual(fork.provider.calls,0)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_cross_process_restore_and_read_only_show(self):
        outputs=[]
        for phase in ('prepare','resume','show'):
            command=[sys.executable,'-B','-m','continuity_engine.testing.w02_recall_fixture','--root',str(self.root),'--phase',phase]
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60,
                                  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
            print(json.dumps({'command':command,'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},ensure_ascii=False))
            self.assertEqual(result.returncode,0,result.stderr)
            outputs.append(json.loads(result.stdout))
        self.assertEqual(outputs[1]['model_calls'],0)
        self.assertEqual(outputs[1]['total_effects'],1)
        self.assertEqual(outputs[2]['view']['status'],'READY')

    def test_new_independent_root_keeps_prior_candidate_source_readable(self):
        f=W02RecallFixture(self.root,recall_policy=RecallPolicy(preference_minimum_roots=2))
        self.report(f,'one','我吃了螺蛳粉。')
        first=self.report(f,'two','我喜欢螺蛳粉。')
        prior=f.context(first).recall['preference_candidates'][0]
        self.assertEqual(prior['status'],'UNCONFIRMED_CANDIDATE')
        next_request=self.report(f,'three','我又在吃螺蛳粉。')
        current=f.context(next_request).recall['preference_candidates'][0]
        self.assertEqual(len(current['independent_roots']),3)
        self.assertFalse(current['confirmed'])
        self.assertEqual(f.provider.calls,3)

    def test_denied_memory_source_is_not_recorded_as_empty_history(self):
        from continuity_engine.services.context_router_service import ContextPermissionDecision
        f=W02RecallFixture(self.root);r=f.message('我又吃了午饭')
        original=f.permission.authorize_source
        def policy(request,source,partition):
            if source=='engine.memory':return ContextPermissionDecision(False,'MEMORY_READ_DENIED','test-current')
            return original(request,source,partition)
        with patch.object(f.permission,'authorize_source',side_effect=policy):
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
            view=f.app.adapter.service.recall_outcome(r['requestId'])
        self.assertEqual(view['status'],'BLOCKED')
        self.assertIn('MEMORY_READ_DENIED',view['record']['rounds'][0]['reasons'])
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(0,0,0))

    def test_archive_and_delete_cannot_reenter_through_input_history(self):
        from continuity_engine.services.memory_lifecycle_service import MemoryLifecycleService,TimelineMemorySources
        from continuity_engine.services.permission_service import PermissionService
        from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
        from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand,LifecycleAction
        for index,action in enumerate(('deactivate','archive','delete')):
            with self.subTest(action=action):
                f=W02RecallFixture(self.root/str(index));old=self.report(f,'meal','我吃了螺蛳粉。')
                memory=f.core.memory.load_memory(f.core.subject_id,'memory:meal')
                permissions=PermissionService(JsonPermissionRepository(f.runtime.data_root),clock=f.runtime.clock.now)
                permission=permissions.create_permission(f.core.subject_id,permission_id='recall-test',
                    permission_type='TEST',name='Explicit test lifecycle',description='Isolated memory lifecycle test',
                    scope=['*'],capabilities=['memory.lifecycle.'+action],source='w02-test',reason='Explicit TEST only').permission
                sources=TimelineMemorySources(f.core.timeline,f.core.memory,f.core.subject_id);now=f.runtime.clock.now()
                command=MemoryLifecycleCommand('w02-lifecycle',f.core.subject_id,'TEST',memory.memory_id,LifecycleAction(action),
                    memory.revision,memory.canonical_hash(),permission.permission_id,permission.revision,memory.scope,
                    'Explicit TEST lifecycle',now,now+timedelta(hours=1),'test-confirm',tuple(sorted(sources(memory).items())))
                service=MemoryLifecycleService(f.core.memory,subject_id=f.core.subject_id,environment='TEST',
                    permissions=permissions,clock=f.runtime.clock.now,source_snapshot=sources,
                    confirmation_verifier=lambda c:c.canonical_hash()==command.canonical_hash(),allow_test_delete=True)
                service.submit(command);f.reopen();new=f.message('我又在吃螺蛳粉');f.submit(new)
                refs=f.context(new).route.manifest.candidates
                self.assertFalse(any(x.stable_id in {'meal','memory:meal','input:'+old['requestId']} for x in refs))

    def test_current_context_invalidated_by_corrected_root(self):
        from continuity_engine.domain.events import EventClassification,EventReference,EventRelationType
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了螺蛳粉')
        r=f.message('我又在吃螺蛳粉');f.submit(r);context=f.context(r)
        f.event('correction',content='更正先前进食报告',classification=EventClassification.CORRECTION,
                references=(EventReference('meal',f.core.subject_id,EventRelationType.CORRECTS),))
        self.assertFalse(f.core.current(context))

    def test_not_wanting_is_not_positive_intent(self):
        f=W02RecallFixture(self.root);r=f.message('我不想吃螺蛳粉');f.submit(r)
        frame=f.context(r).recall['assessment']['frames'][0]
        self.assertEqual(frame['modality'],'NEGATED_INTENT')
        self.assertFalse(f.context(r).recall['preference_candidates'])

    def test_local_recall_preserves_existing_external_capability_wait_channel(self):
        from continuity_engine.testing.p16_provider_fixture import P16Fixture
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        from continuity_engine.domain.context_composition import ContextBudget
        f=P16Fixture(self.root);f.core_options['gates']=ContinuityCoreGates(input_processing=True,automatic_recall=True)
        f.core_options['context_budget']=ContextBudget(token_limit=900);f.reopen()
        f.mode('unknown')
        with self.assertRaises(IntegrationExecutionError):f.submit()
        request=f.provider.inputs[0].continuity_context.route.plan.request.request_id
        operation=f.app.ledger.load_operation(request)
        self.assertEqual(operation.domain_progress.perception.continuity_context.recall['status'],'READY')
        self.assertEqual(f.external_calls,0)
        self.assertEqual(len(f.fake.facts()),0)

    def test_legacy_gate_disabled_does_not_construct_recall(self):
        from continuity_engine.testing.w02_input_fixture import W02InputFixture
        from continuity_engine.services.associative_recall_service import AssociativeRecallService
        with patch.object(AssociativeRecallService,'__init__',side_effect=AssertionError('recall gate off')):
            f=W02InputFixture(self.root);r=f.message('我吃了午饭');f.submit(r)
        self.assertIsNone(f.context(r).recall)

    def test_p18_native_recall_keeps_pause_stop_and_continuous_host(self):
        import continuity_engine.testing.p18_runtime_fixture as fixture_module
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        original=fixture_module.build_continuity_core
        def enabled(**kwargs):
            return original(**kwargs,gates=ContinuityCoreGates(input_processing=True,automatic_recall=True))
        with patch.object(fixture_module,'build_continuity_core',side_effect=enabled):
            f=fixture_module.P18Fixture(self.root)
        before=f.state.revision
        with f.host.running():
            f.control('PAUSE');f.advance(3600);f.host.tick()
            self.assertEqual(f.provider.calls,0)
            self.assertTrue(f.host.query()['host_alive'])
            f.control('RESUME');f.host.tick();f.advance(60);f.host.tick()
            self.assertGreater(f.provider.calls,0)
            self.assertGreater(f.state.revision,before)
            self.assertEqual(f.provider.inputs[-1].continuity_context.recall['status'],'READY')
            self.assertEqual(f.provider.inputs[-1].external_facts,())
            self.assertEqual(f.fake.effect_count,0)
            self.assertTrue(f.host.query()['host_alive'])
            calls=f.provider.calls;f.control('STOP');self.assertFalse(f.host.tick())
        with f.host.running():self.assertFalse(f.host.tick())
        self.assertEqual(f.provider.calls,calls)
