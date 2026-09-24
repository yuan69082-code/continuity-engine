import copy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import IntegrationExecutionError, CapabilityValidationError
from continuity_engine.domain.input_processing import InputDisposition as D
from continuity_engine.domain.integration_results import IntegrationOperationRecord
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from continuity_engine.testing.w02_input_fixture import W02InputFixture
from continuity_engine.testing.persistence import tree_inventory_hash


class PartialInputQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        capture_failure(self, self.root)

    def partial(self):
        f = W02InputFixture(self.root)
        request = f.message('朋友可能喜欢苹果。')
        with patch.object(f.core, '_consolidate_events', side_effect=OSError('TEST_MEMORY_UNAVAILABLE')):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        return f, request

    def check_partial(self, f, request):
        before = tree_inventory_hash(f.runtime.data_root)
        view = f.app.adapter.service.input_outcome(request['requestId'])
        print('partial public query:', view)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        self.assertEqual((f.provider.calls, f.adapter.effect_count, f.adapter.credits), (0, 0, 0))
        self.assertEqual(view['status'], 'PENDING')
        latest = {r['station']: r for r in view['record']['receipts']}
        self.assertEqual(latest['conversation']['disposition'], 'TEMP_USE')
        self.assertEqual(latest['memory']['disposition'], 'FAILED_WAITING')
        self.assertEqual(latest['verification']['disposition'], 'NEEDS_EVIDENCE')
        self.assertEqual(view['resume_stations'], ['memory'])
        self.assertIsNone(view['state_update_id'])

    def test_partial_public_query_after_local_failure(self):
        self.check_partial(*self.partial())

    def test_partial_public_query_after_reopen(self):
        f, request = self.partial()
        f.reopen()
        self.check_partial(f, request)

    def test_repeat_read_and_resume_do_not_repeat_successful_stations(self):
        f, request = self.partial()
        revision = f.runtime.subject_state().revision
        self.check_partial(f, request)
        self.check_partial(f, request)
        before_receipts = f.record(request).receipts
        f.reopen()
        result = f.submit(request)
        after_receipts = f.record(request).receipts
        for station in ('conversation', 'verification'):
            self.assertEqual([r for r in before_receipts if r.station == station],
                             [r for r in after_receipts if r.station == station])
        self.assertEqual(f.runtime.subject_state().revision, revision)
        self.assertEqual((f.provider.calls, f.adapter.effect_count, f.adapter.credits), (1, 1, 1))
        before = tree_inventory_hash(f.runtime.data_root)
        self.assertEqual(f.app.adapter.service.input_outcome(request['requestId'])['status'], 'COMPLETED')
        self.assertEqual(f.submit(request).to_dict(), result.to_dict())
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def assert_query_rejected_without_effect(self, f, request):
        before = tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(Exception):
            f.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        self.assertEqual((f.provider.calls, f.adapter.effect_count, f.adapter.credits), (0, 0, 0))

    def test_partial_read_revoked_permission(self):
        f, request = self.partial()
        f.reopen()
        f.permission.references_allowed = False
        self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_revoked_during_query(self):
        f, request = self.partial()
        original = f.app.ledger.load_completed
        def revoke(*args):
            result = original(*args)
            f.permission.references_allowed = False
            return result
        with patch.object(f.app.ledger, 'load_completed', side_effect=revoke):
            self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_expired_context(self):
        f, request = self.partial()
        f.runtime.clock.advance(timedelta(minutes=11))
        self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_subject_revision_changed(self):
        f, request = self.partial()
        state = f.runtime.subject_state()
        with patch.object(f.core.subject_states, 'load', return_value=replace(state, revision=state.revision+1)):
            self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_rechecks_revision_before_return(self):
        f, request = self.partial()
        state = f.runtime.subject_state()
        original = f.app.ledger.load_completed
        changed = False
        def lookup(*args):
            nonlocal changed
            result = original(*args)
            changed = True
            return result
        with patch.object(f.app.ledger, 'load_completed', side_effect=lookup), patch.object(
                f.core.subject_states, 'load', side_effect=lambda *a: replace(state, revision=state.revision+1) if changed else state):
            self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_in_separate_process_is_read_only(self):
        import json
        import subprocess
        import sys
        f, request = self.partial()
        before = tree_inventory_hash(f.runtime.data_root)
        code = '''import json,sys
from pathlib import Path
from continuity_engine.testing.sandbox import P01SandboxManager
from continuity_engine.testing.w02_input_fixture import W02InputFixture
from continuity_engine.testing.persistence import tree_inventory_hash
root=Path(sys.argv[1])
manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
f=W02InputFixture(root,manager=manager,runtime=manager.open_runtime(sys.argv[2]))
before=tree_inventory_hash(f.runtime.data_root)
view=f.app.adapter.service.input_outcome(sys.argv[3])
assert tree_inventory_hash(f.runtime.data_root)==before
assert (f.provider.calls,f.adapter.effect_count,f.adapter.credits)==(0,0,0)
print(json.dumps(view))
'''
        command = [sys.executable, '-B', '-c', code, str(self.root), f.runtime.descriptor.sandbox_id, request['requestId']]
        child = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=25)
        print(json.dumps({'command': command, 'exitCode': child.returncode,
                          'stdout': child.stdout, 'stderr': child.stderr, 'forced': False}))
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)['resume_stations'], ['memory'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_partial_read_subject_and_environment_mismatch(self):
        f, request = self.partial()
        for field, value in (('subject_id', 'other-subject'), ('environment', 'RESEARCH')):
            with self.subTest(field=field), patch.object(f.core.input_processing.source, field, value):
                self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_corruption_and_forged_success_refused(self):
        import json
        f, request = self.partial()
        path = f.app.ledger.operation_path
        original = json.loads(path.read_text(encoding='utf-8'))
        for variant in ('invalid_json', 'version', 'source', 'receipt', 'operation'):
            with self.subTest(variant=variant):
                data = copy.deepcopy(original)
                op = data['operations'][0]
                record = op['domainProgress']['inputProcessing']
                if variant == 'version':
                    op['domainProgress']['inputPreparation']['external_facts'][0]['message_version_id'] = 'forged'
                elif variant == 'source':
                    record['manifest']['source']['message_id'] = 'forged'
                elif variant == 'receipt':
                    row = next(r for r in record['receipts'] if r['station'] == 'conversation')
                    row['results'] = ['forged-fragment']
                elif variant == 'operation':
                    record['manifest']['operation_id'] = 'other-operation'
                path.write_text('{' if variant == 'invalid_json' else json.dumps(data), encoding='utf-8')
                self.assert_query_rejected_without_effect(f, request)

    def test_partial_read_rejects_unbound_completed_result(self):
        import json
        f, request = self.partial()
        peer_temp = tempfile.TemporaryDirectory()
        self.addCleanup(peer_temp.cleanup)
        peer = W02InputFixture(Path(peer_temp.name))
        foreign = peer.submit(peer.message('今天好吗？')).to_dict()
        # A structurally valid completed record does not prove this operation
        # completed. Simulate a damaged result/journal association in TEST only.
        foreign['requestId'] = request['requestId']
        path = f.app.ledger.path
        raw = json.loads(path.read_text(encoding='utf-8'))
        raw['results'] = [foreign]
        path.write_text(json.dumps(raw), encoding='utf-8')
        self.assert_query_rejected_without_effect(f, request)

    def test_composition_failure_exposes_other_station_and_resumes_only_failed(self):
        f = W02InputFixture(self.root)
        request = f.message('我喜欢苹果。')
        with patch.object(f.core.composer, 'compose', side_effect=RuntimeError('TEST_COMPOSITION_FAILED')):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        f.reopen()
        before = tree_inventory_hash(f.runtime.data_root)
        view = f.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(view['resume_stations'], ['conversation'])
        self.assertEqual(view['status'], 'PENDING')
        self.assertEqual({r['station']: r['disposition'] for r in view['record']['receipts']},
                         {'memory': 'NEEDS_EVIDENCE', 'conversation': 'FAILED_WAITING'})
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        with patch.object(f.core, '_consolidate_events', side_effect=AssertionError('REPEATED_SUCCESS')):
            f.submit(request)
        self.assertEqual((f.provider.calls, f.adapter.effect_count, f.adapter.credits), (1, 1, 1))

    def test_partial_preparation_cannot_be_removed_or_rewritten(self):
        f, request = self.partial()
        operation = f.app.ledger.load_operation(request['requestId'])
        before = tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(Exception):
            f.app.ledger.save_operation(replace(operation, domain_progress=replace(
                operation.domain_progress, input_preparation=None)))
        prepared = operation.domain_progress.input_preparation
        with self.assertRaises(Exception):
            f.app.ledger.save_operation(replace(operation, domain_progress=replace(
                operation.domain_progress, input_preparation=replace(prepared, continuity_context=None))))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_legacy_partial_read_remains_unverified_until_explicit_resubmit(self):
        import json
        f, request = self.partial()
        path = f.app.ledger.operation_path
        data = json.loads(path.read_text(encoding='utf-8'))
        del data['operations'][0]['domainProgress']['inputPreparation']
        path.write_text(json.dumps(data), encoding='utf-8')
        f.reopen()
        before = tree_inventory_hash(f.runtime.data_root)
        view = f.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(view, {'status': 'PENDING_PERCEPTION', 'record': None})
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        f.submit(request)
        self.assertEqual(f.app.adapter.service.input_outcome(request['requestId'])['status'], 'COMPLETED')


class InputRecoveryTests(unittest.TestCase):
    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        capture_failure(self,self.root)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_local_memory_failure_is_recorded_then_resumed(self):
        f = W02InputFixture(self.root)
        request = f.message('记住我提出的这个候选。')
        with patch.object(f.core, '_consolidate_events', side_effect=OSError('isolated storage fault')):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        self.assertEqual(f.record(request).latest('memory').disposition, D.FAILED_WAITING)
        self.assertEqual(f.record(request).latest('conversation').disposition, D.TEMP_USE)
        self.assertEqual(f.provider.calls, 0)
        f.reopen()
        f.submit(request)
        record = f.record(request)
        self.assertEqual([r.disposition for r in record.receipts if r.station == 'memory'],
                         [D.FAILED_WAITING, D.NEEDS_EVIDENCE])
        self.assertEqual(f.provider.calls, 1)

    def test_saved_memory_fact_before_receipt_loss_is_not_written_twice(self):
        f = W02InputFixture(self.root)
        f.event('saved', content='合法测试事件')
        request = f.message('合法测试事件', source_event_id='saved')
        original = f.core._consolidate_events
        def after_save():
            original()
            raise OSError('result lost after memory saved')
        with patch.object(f.core, '_consolidate_events', side_effect=after_save):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        before = [m.to_dict() for m in f.core.memory.list_memories(f.runtime.descriptor.subject_id)]
        f.reopen()
        f.submit(request)
        self.assertEqual([m.to_dict() for m in f.core.memory.list_memories(f.runtime.descriptor.subject_id)], before)
        self.assertEqual(f.record(request).latest('memory').disposition, D.REFERENCE_EXISTING)

    def test_completed_station_not_reexecuted_after_later_checkpoint_fault(self):
        f = W02InputFixture(self.root)
        request = f.message('请记住这份候选。')
        def crash(stage, operation):
            r = operation.domain_progress.input_processing if operation.domain_progress else None
            if stage == 'after_input_checkpoint_saved' and r.latest('memory'):
                raise RuntimeError('after completed memory receipt')
        f.app.adapter.service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        f.reopen()
        with patch.object(f.core, '_consolidate_events', side_effect=AssertionError('completed station repeated')):
            f.submit(request)
        self.assertEqual(f.provider.calls, 1)

    def test_restart_completed_request_is_byte_stable_and_no_duplicate_effect(self):
        f = W02InputFixture(self.root)
        request = f.message('今天好吗？')
        result = f.submit(request)
        before = tree_inventory_hash(f.runtime.data_root)
        effects, credits = f.adapter.effect_count, f.adapter.credits
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), result.to_dict())
        self.assertEqual(f.provider.calls, 0)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits), (effects,credits))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_thinking_saved_before_checkpoint_reuses_original_session(self):
        f = W02InputFixture(self.root)
        request = f.message()
        def crash(stage, operation):
            if stage == 'after_thinking_completed': raise RuntimeError('controlled crash')
        f.app.adapter.service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        self.assertEqual(f.provider.calls,1)
        f.reopen()
        f.submit(request)
        self.assertEqual(f.provider.calls,0)
        self.assertEqual(f.adapter.effect_count,1)

    def test_missing_input_checkpoint_cannot_be_downgraded_to_legacy(self):
        f = W02InputFixture(self.root)
        request = f.message()
        f.submit(request)
        raw = f.app.ledger.load_operation(request['requestId']).to_dict()
        del raw['domainProgress']['inputProcessing']
        with self.assertRaises(Exception): IntegrationOperationRecord.from_dict(raw)

    def test_missing_original_gate_is_rejected(self):
        f = W02InputFixture(self.root)
        request=f.message(); f.submit(request)
        raw=f.app.ledger.load_operation(request['requestId']).to_dict()
        del raw['inputProcessingEnabled']
        with self.assertRaises(Exception): IntegrationOperationRecord.from_dict(raw)

    def test_receipt_cannot_be_rewritten_or_removed(self):
        f=W02InputFixture(self.root)
        request=f.message(); f.submit(request)
        op=f.app.ledger.load_operation(request['requestId'])
        r=replace(op.domain_progress.input_processing, receipts=())
        with self.assertRaises(CapabilityValidationError):
            f.app.ledger.save_operation(replace(op,domain_progress=replace(op.domain_progress,input_processing=r)))

    def test_cross_operation_record_rejected(self):
        f=W02InputFixture(self.root)
        request=f.message(); f.submit(request)
        raw=f.app.ledger.load_operation(request['requestId']).to_dict()
        raw['domainProgress']['inputProcessing']['manifest']['operation_id']='other'
        with self.assertRaises(Exception): IntegrationOperationRecord.from_dict(raw)

    def test_current_permission_revocation_stops_new_thinking_without_effect(self):
        f=W02InputFixture(self.root)
        request=f.message()
        def crash(stage, operation):
            if stage=='after_perception_checkpoint_saved': raise RuntimeError('checkpoint')
        f.app.adapter.service._fault_injector=crash
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        f.reopen(); f.permission.references_allowed=False
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(0,0,0))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_context_expired_after_checkpoint_rejects(self):
        f=W02InputFixture(self.root)
        request=f.message()
        def crash(stage, operation):
            if stage=='after_perception_checkpoint_saved': raise RuntimeError('checkpoint')
        f.app.adapter.service._fault_injector=crash
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        f.runtime.clock.advance(timedelta(minutes=11));f.reopen()
        with self.assertRaises(IntegrationExecutionError): f.submit(request)
        self.assertEqual(f.provider.calls,0)

    def test_idempotency_conflict_preserves_original_receipts(self):
        f=W02InputFixture(self.root)
        request=f.message(); f.submit(request)
        before=tree_inventory_hash(f.runtime.data_root)
        changed=copy.deepcopy(request);changed['createdAt']='2026-09-04T08:01:00Z'
        changed['requestHash']=calculate_request_hash(changed)
        result=f.submit(changed)
        self.assertNotEqual(type(result).__name__,'FirstRoundSuccessResult')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_concurrent_submission_is_replayed_or_explicitly_busy_without_duplicate(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        f=W02InputFixture(self.root);request=f.message()
        entered=Event();release=Event();original=f.provider.think
        def blocked(*args):
            entered.set()
            if not release.wait(5): raise AssertionError('test handshake timeout')
            return original(*args)
        f.provider.think=blocked
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(f.submit,request)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(CapabilityValidationError,'INPUT_ADMISSION_BUSY'):
                    pool.submit(f.submit,request).result(timeout=3)
            finally:release.set()
            result=first.result(timeout=5)
        self.assertEqual(f.submit(request).to_dict(),result.to_dict())
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(1,1,1))

    def test_disabled_after_original_enabled_checkpoint_refuses_downgrade(self):
        f=W02InputFixture(self.root);request=f.message();f.submit(request)
        f.gates=replace(f.gates,input_processing=False);f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.provider.calls,0)

    def test_composer_failure_preserves_finished_memory_and_safe_reason(self):
        f=W02InputFixture(self.root);request=f.message('请记住这个候选')
        with patch.object(f.core.composer,'compose',side_effect=RuntimeError('controlled composer failure')):
            with self.assertRaises(IntegrationExecutionError):f.submit(request)
        record=f.record(request)
        self.assertEqual(record.latest('conversation').disposition,D.FAILED_WAITING)
        self.assertEqual(record.latest('memory').disposition,D.NEEDS_EVIDENCE)
        f.reopen()
        with patch.object(f.core,'_consolidate_events',side_effect=AssertionError('completed work repeated')):
            f.submit(request)
        self.assertEqual(len([r for r in f.record(request).receipts if r.station=='conversation']),2)

    def test_forged_memory_receipt_cannot_claim_message_was_remembered(self):
        import json
        f=W02InputFixture(self.root);request=f.message('请记住此候选。');f.submit(request)
        path=f.app.ledger.operation_path;data=json.loads(path.read_text(encoding='utf-8'))
        row=next(r for r in data['operations'][0]['domainProgress']['inputProcessing']['receipts'] if r['station']=='memory')
        row.update(disposition='REFERENCE_EXISTING',reason='MATCHED_EXISTING_EVENT_MEMORY',results=['memory:invented@0'])
        path.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(Exception):f.app.adapter.service.input_outcome(request['requestId'])

    def test_forged_conversation_receipt_cannot_claim_a_missing_fragment(self):
        import json
        f=W02InputFixture(self.root);request=f.message();f.submit(request)
        path=f.app.ledger.operation_path;data=json.loads(path.read_text(encoding='utf-8'))
        row=next(r for r in data['operations'][0]['domainProgress']['inputProcessing']['receipts'] if r['station']=='conversation')
        row['results']=['invented-fragment']
        path.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(Exception):f.submit(request)

    def test_admission_does_not_reclassify_an_application_runtime_error(self):
        from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
        f=W02InputFixture(self.root)
        original=RuntimeBoundaryError('RUNTIME_BUSY')
        try:
            with f.core.input_processing.admission():raise original
        except Exception as caught:
            self.assertIs(caught,original)
        else:self.fail('original application error must survive')
