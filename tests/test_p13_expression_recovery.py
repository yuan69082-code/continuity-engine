"""P13 replay, current access, old facts and zero-new-effect regression matrix."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest
import os
import subprocess
import sys

from continuity_engine.domain.errors import IntegrationExecutionError, CapabilityValidationError
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.expression import ExpressionValidationError
from continuity_engine.domain.action_capability import ReceiptQuery
from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.interfaces.local_integration_app import LocalIntegrationInitializationError
from continuity_engine.testing.p13_expression_fixture import P13Fixture
from continuity_engine.testing.persistence import read_json, atomic_write_json, tree_inventory_hash


class ExpressionRecoveryTests(unittest.TestCase):
    def fixture(self,**kw):
        temp=tempfile.TemporaryDirectory(prefix='p13-recovery-');self.addCleanup(temp.cleanup)
        return P13Fixture(Path(temp.name),**kw)

    def stop(self,f,stage):
        def fault(point,operation):
            if point==stage:raise RuntimeError('P13 controlled crash: '+stage)
        f.app.adapter._service._fault_injector=fault

    def writer(self,f):
        original=f.provider.think
        f.provider.think=lambda perception,budget:replace(original(perception,budget),
            update_subject_state=True,proposed_mutations=[StateMutation('continuity.current_focus',
            ChangeOperation.SET,['p13-approved-focus'],'Explicit TEST proposal before Expression.')])

    def test_restart_repeat_submit_and_query_do_not_regenerate_or_execute(self):
        f=self.fixture(expression_mode='CONFRONT');r=f.request();first=f.submit(r)
        before=tree_inventory_hash(f.runtime.data_root)
        calls=f.presentation.calls;effects=f.adapter.effect_count;credits=f.adapter.credits
        f.reopen()
        self.assertEqual(f.submit(r).to_dict(),first.to_dict())
        self.assertEqual(f.app.adapter.query_request(r['requestId']).result.to_dict(),first.to_dict())
        self.assertEqual(f.presentation.calls,calls)
        self.assertEqual(f.provider.calls,0)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits),(effects,credits))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_crash_after_thinking_reuses_original_result_not_new_mode(self):
        f=self.fixture(expression_mode='REFUSE');r=f.request();self.stop(f,'after_thinking_completed')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        f.expression_mode='RESPOND';f.body='I agree.';f.reopen()
        self.assertEqual(f.submit(r).response.content,'I do not agree with this claim.')
        self.assertEqual(f.artifact(r).decision.mode,'REFUSE')
        self.assertEqual(f.provider.calls,0)

    def test_crash_after_domain_recovers_artifact_without_presentation(self):
        f=self.fixture();r=f.request();self.stop(f,'after_domain_completed')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        calls=f.presentation.calls;f.reopen()
        f.submit(r)
        self.assertEqual(f.presentation.calls,calls)
        self.assertEqual(f.provider.calls,0)

    def test_generation_failure_retry_does_not_rethink_or_duplicate_action(self):
        f=self.fixture();r=f.request();f.presentation.behavior='failure'
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        effects=f.adapter.effect_count;credits=f.adapter.credits
        f.presentation.behavior='success';f.reopen();f.submit(r)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits),(effects,credits))
        self.assertEqual(f.provider.calls,0)
        self.assertEqual(f.presentation.calls,2) # Explicit recovery of a pure materializer.

    def test_expired_context_blocks_text_but_keeps_original_receipts(self):
        f=self.fixture();r=f.request();f.submit(r)
        f.runtime.clock.advance(timedelta(minutes=11));f.reopen()
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        with self.assertRaises(ExpressionValidationError):f.app.adapter.query_request(r['requestId'])
        self.assertGreater(f.adapter.query_calls,0)
        self.assertEqual(f.provider.calls,0)
        self.assertEqual(f.presentation.calls,1)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_revoked_exact_permission_blocks_completed_replay_zero_writes(self):
        f=self.fixture();r=f.request();f.submit(r);f.permission.references_allowed=False;f.reopen()
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(f.adapter.execute_calls,0)

    def test_unknown_historical_receipt_cannot_be_expression_success(self):
        f=self.fixture();r=f.request();f.submit(r);f.reopen();before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.adapter,'query',return_value=ReceiptQuery.UNKNOWN) as query:
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
            self.assertGreater(query.call_count,0)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_missing_completed_artifact_cannot_downgrade_to_legacy(self):
        f=self.fixture();r=f.request();f.submit(r)
        data=read_json(f.app.ledger.operation_path);data['operations'][0]['domain'].pop('expression')
        atomic_write_json(f.app.ledger.operation_path,data);f.reopen()
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        with self.assertRaises(ExpressionValidationError):f.app.adapter.query_request(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_removing_original_gate_cannot_remove_expression_ownership(self):
        f=self.fixture();r=f.request();f.submit(r)
        data=read_json(f.app.ledger.operation_path)
        data['operations'][0]['domainProgress']['perception']['continuity_context'].pop('expression_enabled')
        atomic_write_json(f.app.ledger.operation_path,data)
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises((IntegrationExecutionError,LocalIntegrationInitializationError)):
            f.reopen();f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_direct_and_optional_planner_preserve_expression_mode(self):
        for action_mode,has_plan in [('direct',False),('complex',True)]:
            with self.subTest(action_mode=action_mode):
                f=self.fixture(mode=action_mode,expression_mode='PURSUE');r=f.request();f.submit(r)
                requests=f.core.coordination.action_requests_by_decision('c1:'+digest(
                    f.app.ledger.load_operation(r['requestId']).operation_id)[7:])
                self.assertEqual(any(x.plan_id is not None for x in requests),has_plan)
                self.assertEqual(f.artifact(r).decision.mode,'PURSUE')
                self.assertNotIn('delivered',f.artifact(r).to_dict())

    def test_current_approved_evolution_keeps_proposal_and_revision_semantics(self):
        f=self.fixture();self.writer(f);r=f.request();result=f.submit(r)
        self.assertIsInstance(result,FirstRoundSuccessResult)
        self.assertEqual(f.state.revision,2)
        self.assertEqual(f.state.continuity.current_focus,['p13-approved-focus'])
        self.assertEqual(f.artifact(r).content,f.body)

    def test_real_evolution_recovers_after_expiry_without_releasing_old_text(self):
        f=self.fixture();self.writer(f);r=f.request();self.stop(f,'after_evolution_committed')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.state.revision,2)
        f.runtime.clock.advance(timedelta(minutes=11));f.permission.references_allowed=False;f.reopen()
        before=tree_inventory_hash(f.runtime.data_root/'subject-state')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.state.revision,2)
        self.assertIsNotNone(f.app.ledger.load_completed(r['requestId']))
        self.assertIsNotNone(f.app.ledger.load_operation(r['requestId']).evolution)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root/'subject-state'),before)
        self.assertEqual(f.provider.calls,0)
        outcome=f.app.adapter.service.expression_outcome(r['requestId'])
        self.assertEqual(outcome['status'],'CURRENTLY_UNAVAILABLE')
        self.assertIsNone(outcome['artifact'])
        self.assertEqual(outcome['verified_facts']['state_revision'],2)

    def test_model_waiting_remains_waiting_not_subject_silence(self):
        f=self.fixture(thinking_mode=IntegrationThinkingMode.CAPABILITY);r=f.request()
        pending=f.submit(r)
        self.assertIn('capability',type(pending).__name__.lower())
        self.assertEqual(f.presentation.calls,0)
        self.assertIsNone(f.app.ledger.load_operation(r['requestId']).domain)

    def test_formal_relationship_and_compact_preference_change_format_only(self):
        f=self.fixture(body='I do not agree.\n\nMy position remains unchanged.')
        f.event('p13-formal',classification=EventClassification.STATE_CHANGE,mutations=[StateMutation('relationship.interaction_preferences',
            ChangeOperation.SET,['formal'],'Explicit TEST relationship preference.')])
        r=f.request();state=f.state.to_dict();f.submit(r)
        self.assertEqual(f.artifact(r).content,'> I do not agree.\n> My position remains unchanged.')
        self.assertEqual(f.state.to_dict(),state)

    def test_p12_archive_invalidates_saved_expression_and_normal_future_context(self):
        from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand,LifecycleAction
        from continuity_engine.services.permission_service import PermissionService
        from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
        f=self.fixture();f.event('p13-memory',content='continuity synthetic evidence')
        r=f.request();f.submit(r);context=f.context(r)
        self.assertIn('memory:p13-memory',[x.stable_id for x in context.route.manifest.candidates])
        permissions=PermissionService(JsonPermissionRepository(f.runtime.data_root),clock=f.runtime.clock.now)
        grant=permissions.create_permission(f.core.subject_id,permission_id='p13-lifecycle-grant',permission_type='TEST',
            name='TEST',description='TEST',scope=['*'],capabilities=['memory.lifecycle.archive'],source='TEST',reason='TEST').permission
        approved={};service=f.core.memory_lifecycle(permissions,confirmation_verifier=lambda c:approved.get(c.confirmation_id)==c.canonical_hash())
        memory=f.core.memory.load_memory(f.core.subject_id,'memory:p13-memory');now=f.runtime.clock.now()
        command=MemoryLifecycleCommand('p13-archive',f.core.subject_id,'TEST',memory.memory_id,LifecycleAction.ARCHIVE,
            memory.revision,memory.canonical_hash(),grant.permission_id,grant.revision,memory.scope,'TEST explicit archive',
            now,now+timedelta(hours=1),'confirm:p13',tuple(sorted(service.source_snapshot(memory).items())))
        approved[command.confirmation_id]=command.canonical_hash();service.submit(command)
        f.reopen();before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(f.app.adapter.service.expression_outcome(r['requestId'])['status'],'CURRENTLY_UNAVAILABLE')
        future=f.request();f.submit(future)
        self.assertNotIn('memory:p13-memory',[x.stable_id for x in f.context(future).route.manifest.candidates])

    def test_model_result_restart_expression_uses_one_original_capability_ledger(self):
        from tests.test_e5_capability_flow import capability_result_payload
        f=self.fixture(thinking_mode=IntegrationThinkingMode.CAPABILITY);r=f.request();waiting=f.submit(r)
        f.reopen();self.assertEqual(f.submit(r).to_dict(),waiting.to_dict())
        payload=capability_result_payload(waiting,response='Synthetic model judgment: I do not agree.')
        f.runtime.clock.advance(timedelta(seconds=3))
        first=f.app.adapter.submit_capability_result(payload)
        f.reopen();before=tree_inventory_hash(f.runtime.data_root)
        self.assertEqual(f.app.adapter.submit_capability_result(payload).to_dict(),first.to_dict())
        self.assertEqual(f.artifact(r).content,'Synthetic model judgment: I do not agree.')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        ledger=read_json(f.app.ledger.capability_path)
        self.assertEqual(sum(x.get('capabilityType')=='model.generate' for x in ledger['requests']),1)
        self.assertEqual(len(ledger['requests']),2)
        self.assertEqual(f.adapter.execute_calls,0)
        self.assertEqual(f.presentation.calls,1)

    def test_snapshot_branch_preserves_artifact_and_does_not_touch_original(self):
        f=self.fixture();r=f.request();first=f.submit(r)
        snap=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snap.snapshot_id)
        before=tree_inventory_hash(f.runtime.data_root)
        runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
        fork=P13Fixture(f.root,runtime=runtime,manager=f.manager)
        self.assertEqual(fork.submit(r).to_dict(),first.to_dict())
        self.assertEqual(fork.presentation.calls,0)
        self.assertEqual(fork.adapter.execute_calls,0)
        fork.submit()
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_cross_subject_and_environment_composition_rejects_before_port_or_writes(self):
        f=self.fixture();r=f.request();f.submit(r);service=f.app.adapter.service
        operation=f.app.ledger.load_operation(r['requestId']);thinking=service._restore_domain_thinking(operation)
        other=self.fixture();before=tree_inventory_hash(f.runtime.data_root);other_before=tree_inventory_hash(other.runtime.data_root)
        for core in (other.core,):
            with self.assertRaises(ExpressionValidationError):
                f.core.expression_policy.compose(core,operation,thinking,operation.domain_progress.action)
        with patch.object(f.core,'environment','RESEARCH'):
            with self.assertRaises(ExpressionValidationError):
                f.core.expression_policy.compose(f.core,operation,thinking,operation.domain_progress.action)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(tree_inventory_hash(other.runtime.data_root),other_before)
        self.assertEqual(f.presentation.calls,1)

    def test_context_rejection_and_platform_denial_are_distinct_from_subject_refusal(self):
        f=self.fixture(mode='complex',expression_mode='REFUSE');r=f.request()
        f.app.adapter.service._available_permissions=()
        before=f.state.to_dict();f.submit(r);artifact=f.artifact(r)
        self.assertEqual(artifact.decision.mode,'REFUSE')
        self.assertEqual(artifact.decision.status,'PLATFORM_DENIED')
        self.assertEqual(artifact.content,'')
        self.assertEqual(f.presentation.calls,0)
        self.assertEqual(f.adapter.execute_calls,0)
        self.assertEqual(f.adapter.credits,0)
        self.assertEqual(f.state.to_dict(),before)

    def test_forged_action_input_rejected_before_materialization(self):
        f=self.fixture();r=f.request();f.submit(r);service=f.app.adapter.service
        operation=f.app.ledger.load_operation(r['requestId']);thinking=service._restore_domain_thinking(operation)
        action=operation.domain_progress.action
        changed=replace(action,session=replace(action.session,action_session_id='forged-action'))
        before=tree_inventory_hash(f.runtime.data_root);calls=f.presentation.calls
        with self.assertRaises(ExpressionValidationError):
            f.core.expression_policy.compose(f.core,operation,thinking,changed)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(f.presentation.calls,calls)

    def test_disabled_expression_outcome_has_no_component_reads(self):
        f=self.fixture(expression_enabled=False)
        with patch.object(f.app.ledger,'load_operation',side_effect=AssertionError('disabled read')):
            self.assertEqual(f.app.adapter.service.expression_outcome('not-loaded')['status'],'FEATURE_DISABLED')

    def test_original_router_request_cannot_be_rebound_to_another_operation(self):
        f=self.fixture();r=f.request();f.submit(r);service=f.app.adapter.service
        operation=f.app.ledger.load_operation(r['requestId']);thinking=service._restore_domain_thinking(operation)
        different=replace(operation,request_id='different-request')
        before=tree_inventory_hash(f.runtime.data_root);calls=f.presentation.calls
        with self.assertRaises(ExpressionValidationError):
            f.core.expression_policy.compose(f.core,different,thinking,operation.domain_progress.action)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(f.presentation.calls,calls)

    def test_existing_emotion_only_affects_explicit_emphasis_preference(self):
        f=self.fixture(expression_mode='CONFRONT')
        values={'current_state':'alert','intensity':0.8,'updated_at':f.runtime.clock.now().isoformat(),'confidence':0.9,'baseline':0.2}
        mutations=[StateMutation('emotion_state.'+k,ChangeOperation.SET,v,'Explicit TEST seed.') for k,v in values.items()]
        mutations.append(StateMutation('identity.expression_preferences',ChangeOperation.SET,['concise','emphasis'],'Explicit TEST presentation preference.'))
        f.event('p13-emotion',classification=EventClassification.STATE_CHANGE,mutations=mutations)
        r=f.request();state=f.state.to_dict();f.submit(r)
        self.assertEqual(f.artifact(r).content,'**'+f.body+'**')
        self.assertEqual(f.state.to_dict(),state)

    def test_fresh_process_restores_original_expression_without_provider_or_effect(self):
        f=self.fixture(expression_mode='REFUSE');r=f.request();first=f.submit(r)
        config=f.root/'p13-restart-input.json'
        config.write_text(json.dumps({'root':str(f.root),'sandbox':f.runtime.descriptor.sandbox_id,
            'request':r}),encoding='utf-8')
        program='''
import json,sys
from pathlib import Path
from continuity_engine.testing.sandbox import P01SandboxManager
from continuity_engine.testing.p13_expression_fixture import P13Fixture
value=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root=Path(value['root']);manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
runtime=manager.open_runtime(value['sandbox'])
f=P13Fixture(root,runtime=runtime,manager=manager)
result=f.submit(value['request'])
assert f.provider.calls==f.presentation.calls==f.adapter.execute_calls==0
print(json.dumps({'result':result.to_dict(),'mode':f.artifact(value['request']).decision.mode}))
'''
        before=tree_inventory_hash(f.runtime.data_root)
        repo=Path(__file__).resolve().parents[1]
        process=subprocess.run([sys.executable,'-c',program,str(config)],cwd=f.root,
            capture_output=True,text=True,encoding='utf-8',timeout=30,
            env={**os.environ,'PYTHONPATH':str(repo/'src'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
        self.assertEqual(process.returncode,0,'P13 child stdout/stderr preserved in failure: '+process.stdout+process.stderr)
        output=json.loads(process.stdout)
        self.assertEqual(output['result'],first.to_dict());self.assertEqual(output['mode'],'REFUSE')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_bounded_three_day_seven_round_golden_no_cognitive_overwrite(self):
        f=self.fixture();state=f.state.to_dict();requests=[]
        for i,mode in enumerate(('RESPOND','SILENCE','REFUSE','QUESTION','CONFRONT','DEFER','PURSUE')):
            f.expression_mode=mode
            if i in (2,4,6):f.runtime.clock.advance(timedelta(days=1))
            f.reopen();r=f.request();result=f.submit(r);requests.append(r)
            self.assertEqual(f.artifact(r).decision.mode,mode)
            self.assertEqual(f.state.to_dict(),state)
            if i>=2:
                old=f.app.adapter.service.expression_outcome(requests[0]['requestId'])
                self.assertEqual(old['status'],'CURRENTLY_UNAVAILABLE')
                self.assertIsNone(old['artifact'])
        self.assertEqual(len(f.app.ledger.list_completed()),7)
        self.assertEqual(f.adapter.effect_count,6)
        self.assertEqual(f.adapter.credits,6)


if __name__=='__main__':unittest.main()
