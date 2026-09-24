from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.integration_results import IntegrationOperationRecord
from continuity_engine.testing.w02_input_fixture import W02InputFixture
from continuity_engine.testing.persistence import tree_inventory_hash


class InputIntegrationTests(unittest.TestCase):
    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        capture_failure(self,self.root)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_disabled_feature_has_no_new_fields_or_component_calls(self):
        f=W02InputFixture(self.root,enabled=False)
        self.assertIsNone(f.core.input_processing)
        request=f.message();f.submit(request)
        raw=f.app.ledger.load_operation(request['requestId']).to_dict()
        self.assertNotIn('inputProcessingEnabled',raw)
        self.assertNotIn('inputProcessing',raw['domainProgress'])
        self.assertNotIn('input_manifest_hash',raw['domainProgress']['perception']['continuity_context'])
        self.assertEqual(IntegrationOperationRecord.from_dict(raw).to_dict(),raw)

    def test_native_opportunity_without_input_flag_preserves_original_chain(self):
        from datetime import timedelta
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f=P14Fixture(self.root)
        self.assertIsNone(f.core.input_processing)
        f.runtime.clock.advance(timedelta(hours=1))
        before=f.state.revision
        f.opportunity('w02-native-legacy-shape')
        self.assertEqual(f.state.revision,before+1)
        self.assertEqual(f.provider.calls,1)
        self.assertTrue(f.state.intentions.dynamic_mind)

    def test_read_view_does_not_call_model_or_write(self):
        f=W02InputFixture(self.root)
        request=f.message();f.submit(request)
        before=tree_inventory_hash(f.runtime.data_root);calls=f.provider.calls
        view=f.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(view['status'],'COMPLETED')
        self.assertTrue(view['received_not_necessarily_remembered'])
        self.assertNotIn(request['platformFactPackage']['facts'][0]['content'],json.dumps(view,ensure_ascii=False))
        self.assertEqual(f.provider.calls,calls)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_read_rechecks_permission_before_return(self):
        f=W02InputFixture(self.root)
        request=f.message();f.submit(request)
        original=f.app.ledger.load_completed
        def revoke(*args):
            result=original(*args);f.permission.references_allowed=False;return result
        before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.app.ledger,'load_completed',side_effect=revoke):
            with self.assertRaises(Exception): f.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_snapshot_branch_preserves_input_progress(self):
        f=W02InputFixture(self.root)
        request=f.message();result=f.submit(request)
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.runtime.subject_state().revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id)
        before=tree_inventory_hash(f.runtime.data_root)
        runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
        fork=W02InputFixture(self.root,runtime=runtime,manager=f.manager)
        self.assertEqual(fork.submit(request).to_dict(),result.to_dict())
        self.assertEqual(fork.record(request),f.record(request))
        self.assertEqual(fork.provider.calls,0)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_protected_fixture_rejected_without_writes(self):
        protected=self.root/'.CONTINUITY-DATA';protected.mkdir()
        (protected/'canary').write_text('unchanged')
        before=tree_inventory_hash(self.root)
        with self.assertRaises(Exception): W02InputFixture(protected/'child')
        self.assertEqual(tree_inventory_hash(self.root),before)

    def test_ordinary_psychological_content_not_screened(self):
        f=W02InputFixture(self.root)
        request=f.message('我感到悲伤，也想安静地想一想。')
        result=f.submit(request)
        self.assertEqual(type(result).__name__,'FirstRoundSuccessResult')
        self.assertEqual(f.provider.calls,1)

    def test_w02_internal_evolution_survives_expression_refusal_and_replay(self):
        from datetime import timedelta
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        f=P14Fixture(self.root,mode='complex',gates=ContinuityCoreGates(input_processing=True))
        f.runtime.clock.advance(timedelta(hours=1));f.constraints.confirmation_allowed=False
        request=f.request();before=f.state.revision
        f.submit(request)
        self.assertEqual(f.state.revision,before+1)
        self.assertTrue(f.context(request).expression_enabled)
        self.assertEqual(f.artifact(request).decision.status,'PLATFORM_DENIED')
        self.assertEqual(f.adapter.effect_count,0)
        view=f.app.adapter.service.input_outcome(request['requestId'])
        self.assertIsNotNone(view['state_update_id'])
        f.reopen();f.submit(request)
        self.assertEqual((f.provider.calls,f.state.revision),(0,before+1))

    def test_material_rejected_before_any_w02_persistence(self):
        from continuity_engine.testing.p16_provider_fixture import P16Fixture
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        from continuity_engine.domain.integration_hashing import calculate_content_hash
        from continuity_engine.services.integration_contract_hashing import calculate_request_hash
        f=P16Fixture(self.root);f.core_options['gates']=ContinuityCoreGates(input_processing=True);f.reopen()
        request=f.request()
        # Use the existing Broker policy, without adding a W02 secret heuristic.
        f.broker.material_allowed=lambda descriptor,material:False
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(Exception):f.submit(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual(f.external_calls,0)

    def test_current_material_is_bound_to_original_message_version(self):
        f=W02InputFixture(self.root);request=f.message();f.submit(request)
        ctx=f.context(request)
        ref=next(r for r in ctx.route.manifest.candidates if r.source_id=='engine.current-input')
        source=f.core.input_processing.source
        with self.assertRaises(Exception):source.resolve(replace(ref,version='different-version'))
        with self.assertRaises(Exception):source.resolve(replace(ref,environment='RESEARCH'))

    def test_budget_clipping_is_explicit_and_does_not_claim_input_consumed(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=W02InputFixture(self.root,context_budget=ContextBudget(token_limit=768))
        request=f.message('这是一份较长的临时材料。'*250)
        f.submit(request)
        record=f.record(request)
        self.assertEqual(record.latest('conversation').disposition.value,'NOT_ADOPTED')
        self.assertFalse(record.latest('conversation').results)
        self.assertTrue(f.context(request).composition.snapshot.missing_notices)

    def test_model_capability_input_uses_the_same_current_input_composition(self):
        from continuity_engine.domain.capability import IntegrationThinkingMode, CapabilityRequiredEnvelope
        f=W02InputFixture(self.root,thinking_mode=IntegrationThinkingMode.CAPABILITY)
        result=f.submit(f.message('今天好吗？'))
        self.assertIsInstance(result,CapabilityRequiredEnvelope)
        self.assertIn('今天好吗？',result.capability_request.input.perception_summary)
        self.assertEqual(f.provider.calls,0)

    def test_real_process_restart_restores_original_effect_once(self):
        import subprocess,sys
        for phase in ('prepare','resume'):
            command=[sys.executable,'-B','-m','continuity_engine.testing.w02_input_fixture',
                     '--root',str(self.root),'--phase',phase]
            completed=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=25)
            print(json.dumps({'command':command,'exitCode':completed.returncode,
                'stdout':completed.stdout,'stderr':completed.stderr},ensure_ascii=False))
            self.assertEqual(completed.returncode,0,completed.stderr)

    def test_cross_process_busy_admission_does_not_create_operation(self):
        import subprocess,sys
        f=W02InputFixture(self.root)
        code=('from continuity_engine.storage.json_runtime_repository import file_lock; '
              'from pathlib import Path; import sys; '
              'with_lock = file_lock(Path(sys.argv[1])); with_lock.__enter__(); '
              'print("LOCKED",flush=True); sys.stdin.readline(); with_lock.__exit__(None,None,None)')
        process=subprocess.Popen([sys.executable,'-B','-c',code,str(f.core.input_processing.lock_path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        try:
            self.assertEqual(process.stdout.readline().strip(),'LOCKED')
            before=tree_inventory_hash(f.runtime.data_root)
            from continuity_engine.domain.errors import CapabilityValidationError
            with self.assertRaisesRegex(CapabilityValidationError,'INPUT_ADMISSION_BUSY'):f.submit(f.message())
            self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
            self.assertEqual(f.provider.calls,0)
        finally:
            output,error=process.communicate('\n',timeout=5)
            print(json.dumps({'childPid':process.pid,'exitCode':process.returncode,'stderr':error,'forced':False}))
        self.assertEqual(process.returncode,0)
        f.submit(f.message());self.assertEqual(f.provider.calls,1)
