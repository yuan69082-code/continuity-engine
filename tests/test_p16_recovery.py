import tempfile
import unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from continuity_engine.domain.errors import IntegrationExecutionError,CapabilityValidationError
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.domain.action_capability import ReceiptQuery
from continuity_engine.testing.p16_provider_fixture import P16Fixture,SECRET_MARKER


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p16-recovery-');self.addCleanup(self.temp.cleanup)
        self.f=P16Fixture(Path(self.temp.name))
    def fault(self,point):
        def fail(at):
            if at==point:raise RuntimeError('P16_TEST_INTERRUPTION')
        self.f.core.fault=fail
    def test_completed_replay_rechecks_receipt_without_reexecution(self):
        f=self.f;r=f.request();f.submit(r);calls=f.external_calls;state=f.state.to_dict();f.reopen();f.submit(r)
        self.assertEqual(f.external_calls,calls);self.assertEqual(state,f.state.to_dict())
    def test_completed_replay_survives_revocation_without_new_consumption(self):
        f=self.f;r=f.request();f.submit(r);f.revoke();before=f.registry.cache_path.read_bytes();f.reopen();f.submit(r)
        self.assertEqual(f.external_calls,1);self.assertEqual(before,f.registry.cache_path.read_bytes());self.assertEqual(f.external.cached(),())
    def test_lost_response_after_receipt_can_close_after_revocation_without_consuming(self):
        f=self.f;r=f.request();self.fault('after_adapter_before_result')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.external_calls,1);f.revoke();f.reopen();f.submit(r)
        self.assertEqual(f.external_calls,1);self.assertEqual(f.external.cached(),())
        self.assertEqual(f.external.last_outcome,'CONSUMPTION_DENIED')
    def test_unknown_does_not_execute_even_with_explicit_retry(self):
        f=self.f;f.mode('unknown');r=f.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        f.reopen()
        for _ in range(3):
            with self.assertRaises(IntegrationExecutionError):f.submit(r)
            operation=f.app.ledger.load_operation(r['requestId'])
            with self.assertRaises(CapabilityValidationError):
                f.app.adapter._service.retry_c1_actions(r['requestId'],operation.request_hash)
        self.assertEqual(f.external_calls,0)
        self.assertEqual(f.fake.facts(),[])
    def test_string_not_executed_is_unknown(self):
        f=self.f;f.mode('untyped_not_executed')
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(f.external_calls,0)
    def test_historical_success_unknown_query_cannot_replay_completed(self):
        f=self.f;r=f.request();f.submit(r);f.mode('unknown')
        with self.assertRaises(IntegrationExecutionError) as caught:f.submit(r)
        self.assertIsInstance(caught.exception.__cause__,CapabilityValidationError)
        self.assertEqual(str(caught.exception.__cause__),'EXECUTION_FACT_UNVERIFIED_OR_DRIFTED')
        self.assertEqual(f.external_calls,1)
    def test_reserved_not_executed_after_revocation_cannot_dispatch(self):
        f=self.f;r=f.request();self.fault('after_requests')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.external_calls,0);f.revoke();f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.external_calls,0)
    def test_atomic_registry_failure_keeps_original_bytes(self):
        f=self.f;before=f.registry_bytes()
        with patch('continuity_engine.storage.json_external_provider_repository.os.replace',side_effect=OSError('test atomic failure')):
            with self.assertRaises(OSError):f.registry.disable(f.descriptors[0].key,expected_revision=f.registry.revision)
        self.assertEqual(before,f.registry_bytes())
    def test_p01_snapshot_covers_registry_cache_and_receipts(self):
        f=self.f;f.submit();snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        self.assertTrue(snapshot)
    def test_provider_error_secret_never_enters_engine_files(self):
        f=self.f;f.mode('timeout_unknown')
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertFalse(any(SECRET_MARKER.encode() in p.read_bytes() for p in f.runtime.data_root.rglob('*') if p.is_file()))

    def test_explicit_retry_uses_original_attempts_and_stops_at_bound(self):
        f=self.f;f.mode('timeout_unknown');r=f.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.external_calls,1)
        operation=f.app.ledger.load_operation(r['requestId'])
        for expected in (2,2,2):
            with self.assertRaises(CapabilityValidationError):
                f.app.adapter._service.retry_c1_actions(r['requestId'],operation.request_hash)
            self.assertEqual(f.external_calls,expected)
        self.assertEqual(f.fake.facts(),[])
        self.assertEqual(len(f.core.coordination.action_requests_by_decision(f.core.last_action.requests[0].choice.decision_id)),1)

    def test_query_exception_never_authorizes_dispatch_or_exposes_secret(self):
        f=self.f;f.mode('query_exception')
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(f.external_calls,0)
        self.assertFalse(any(SECRET_MARKER.encode() in p.read_bytes() for p in f.runtime.data_root.rglob('*') if p.is_file()))

    def test_p01_branch_replays_original_receipt_without_polluting_parent(self):
        from continuity_engine.testing.persistence import tree_inventory_hash
        f=self.f;r=f.request();result=f.submit(r)
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        branch=f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id)
        before=tree_inventory_hash(f.runtime.data_root)
        runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
        fork=P16Fixture(self.temp.name,runtime=runtime,manager=f.manager)
        self.assertEqual(fork.submit(r).to_dict(),result.to_dict());self.assertEqual(fork.external_calls,0)
        fork.revoke();self.assertEqual(fork.external.cached(),())
        self.assertEqual(before,tree_inventory_hash(f.runtime.data_root));self.assertTrue(f.external.cached())

    def test_three_real_process_golden_recovers_replaces_and_revokes(self):
        from continuity_engine.testing.p16_provider_fixture import run_golden
        # Keep the disposable root shallow enough for legacy Windows tempfile paths.
        with tempfile.TemporaryDirectory(prefix='p16g-') as root:records=run_golden(root)
        self.assertEqual(len(records),3);self.assertTrue(all(x['exit_code']==0 for x in records))

    def test_paused_subject_blocks_new_query_and_current_cache_but_recovers_fact(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        f=self.f;r=f.request();self.fault('after_adapter_before_result')
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        f.lifecycle('SUSPEND');state=f.state.to_dict();f.reopen()
        # E5-A must recover the fact. The old C1 result contract separately
        # refuses to publish an obsolete SubjectState revision after the pause.
        with self.assertRaises(IntegrationExecutionError) as caught:f.submit(r)
        self.assertEqual(str(caught.exception.__cause__),'authoritative SubjectState no longer matches the operation checkpoint')
        original=f.core.last_action.requests[0]
        binding=next(b for b in f.core.capabilities if b.capability==original.capability_type)
        attempts=f.core.coordination.action_attempts(original,receipt_verifier=binding.adapter)
        self.assertEqual(attempts[-1].result.status.value,'SUCCEEDED')
        self.assertEqual(f.external_calls,1);self.assertEqual(state,f.state.to_dict())
        self.assertEqual(f.external.cached(),())
        with self.assertRaises((IntegrationExecutionError,LifecycleError)):f.next_round()
        self.assertEqual(f.external_calls,1);self.assertEqual(state,f.state.to_dict())

    def test_archived_and_deleted_subjects_do_not_consume_or_execute(self):
        from continuity_engine.domain.subject_lifecycle import LifecycleError
        f=self.f;r=f.request();f.submit(r)
        for operation in ('ARCHIVE','DELETE'):
            with self.subTest(operation=operation):
                f.lifecycle(operation);state=f.state.to_dict();cache=f.registry.cache_path.read_bytes()
                self.assertEqual(f.external.cached(),())
                with self.assertRaises((IntegrationExecutionError,LifecycleError)):f.next_round()
                self.assertEqual(f.external_calls,1);self.assertEqual(state,f.state.to_dict());self.assertEqual(cache,f.registry.cache_path.read_bytes())

    def test_child_timeout_preserves_output_and_never_retries(self):
        import contextlib,io,json,subprocess
        from continuity_engine.testing.p16_provider_fixture import run_golden
        out=io.StringIO();fault=subprocess.TimeoutExpired(['synthetic-command'],60,output=b'controlled stdout',stderr=b'controlled stderr')
        with patch('subprocess.run',side_effect=fault) as child,contextlib.redirect_stdout(out):
            with self.assertRaises(subprocess.TimeoutExpired):run_golden(self.temp.name)
        record=json.loads(out.getvalue());self.assertEqual(record['interruption'],'TimeoutExpired')
        self.assertEqual(record['stdout'],'controlled stdout');self.assertEqual(record['stderr'],'controlled stderr');self.assertIsNone(record['exit_code'])
        self.assertEqual(child.call_count,1)


if __name__=='__main__':unittest.main()
