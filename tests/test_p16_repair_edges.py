"""P16 material boundaries; all fault material and stores are isolated TEST data."""
import contextlib
import io
import json
import tempfile
import traceback
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.action_capability import ActionReceipt
from continuity_engine.domain.errors import IntegrationExecutionError, CapabilityValidationError
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.testing.p16_provider_fixture import P16Fixture, SECRET_MARKER


class RepairEdges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p16r-')
        self.addCleanup(self.temp.cleanup)
        self.f = P16Fixture(Path(self.temp.name))

    def files(self):
        return {p.relative_to(self.f.runtime.data_root).as_posix(): p.read_bytes()
                for p in self.f.runtime.data_root.rglob('*') if p.is_file()}

    def no_secret(self):
        self.assertEqual([p for p, data in self.files().items() if SECRET_MARKER.encode() in data], [])

    def rejected_diagnostic(self, call, code=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                call()
            except Exception as exc:
                self.assertIsInstance(exc, (IntegrationExecutionError, CapabilityValidationError))
                messages = []
                cursor = exc
                while cursor is not None:
                    messages.append(str(cursor))
                    cursor = cursor.__cause__
                diagnostic = ''.join(traceback.format_exception(exc))
                print(diagnostic)
            else:
                self.fail('must fail closed')
        self.assertNotIn(SECRET_MARKER, output.getvalue())
        if code:
            self.assertIn(code, '\n'.join(messages))
        self.no_secret()

    def request_adapter(self):
        request = self.f.core.last_action.requests[0]
        adapter = next(b.adapter for b in self.f.core.capabilities if b.capability == request.capability_type)
        return request, adapter

    def test_whole_receipt_is_checked_on_query_and_execute(self):
        f = self.f
        f.submit()
        request, adapter = self.request_adapter()
        fact = f.fake.query_receipt(request)
        before = self.files()
        # Every field, including hashes/counters, reaches the broker intact. The
        # chosen disallowed value need not be the built-in synthetic marker.
        for field in fact.to_dict():
            for call in (lambda: adapter.query(request), lambda: adapter.execute(request)):
                with self.subTest(field=field, entry=call):
                    seen = []
                    def allowed(d, value):
                        if isinstance(value, dict) and 'receipt_id' in value:
                            seen.append(value)
                            return value[field] != fact.to_dict()[field]
                        return True
                    with patch.object(f.external.broker, 'material_allowed', side_effect=allowed):
                        with self.assertRaisesRegex(ExternalCapabilityError, 'EXTERNAL_RECEIPT_MATERIAL_REJECTED'):
                            call()
                    self.assertEqual(seen, [fact.to_dict()])
                    self.assertEqual(before, self.files())

    def test_rejected_execution_receipt_is_unknown_and_recovers_without_redispatch(self):
        f = self.f
        request = f.request()
        original_execute = f.fake.execute_query
        def poisoned(*args):
            return replace(original_execute(*args), receipt_id=SECRET_MARKER)
        with patch.object(f.fake, 'execute_query', side_effect=poisoned):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        self.assertEqual(f.external_calls, 1)
        self.no_secret()
        rows = f.core.coordination._repository.list_capability_attempts(self.request_adapter()[0].capability_request_id)
        self.assertEqual(rows[-1].result.status.value, 'UNKNOWN')
        raw = f.fake.path.read_bytes()
        f.reopen()
        original_query = f.fake.query_receipt
        def bad_query(r):
            fact = original_query(r)
            return replace(fact, receipt_id=SECRET_MARKER) if isinstance(fact, ActionReceipt) else fact
        with patch.object(f.fake, 'query_receipt', side_effect=bad_query):
            for _ in range(2):
                self.rejected_diagnostic(lambda: f.submit(request))
                self.assertEqual(f.external_calls, 1)
        self.assertEqual(raw, f.fake.path.read_bytes())
        f.submit(request)
        self.assertEqual(f.external_calls, 1)
        self.no_secret()

    def test_completed_replay_rejects_material_without_rewriting_fact_or_ledger(self):
        f = self.f
        request = f.request()
        f.submit(request)
        original = f.fake.query_receipt
        def bad(r):
            return replace(original(r), receipt_id=SECRET_MARKER)
        before = self.files()
        f.reopen()
        with patch.object(f.fake, 'query_receipt', side_effect=bad):
            self.rejected_diagnostic(lambda: f.submit(request))
        self.assertEqual(before, self.files())
        self.assertEqual(f.external_calls, 1)

    def test_query_is_rejected_before_any_think_result_save_or_processor(self):
        f = self.f
        f.query = 'memory:' + SECRET_MARKER
        thinking = f.app.adapter._service._thinking
        original = thinking._repository.save_think_session
        saved = []
        def save(session):
            saved.append(session.to_dict())
            self.assertNotIn(SECRET_MARKER, json.dumps(saved[-1]))
            return original(session)
        with patch.object(thinking._repository, 'save_think_session', side_effect=save):
            self.rejected_diagnostic(f.submit, 'EXTERNAL_INPUT_REJECTED')
        self.assertTrue(saved)
        self.assertEqual(f.external_calls, 0)
        self.assertTrue(all(not row.get('result') or SECRET_MARKER not in json.dumps(row['result']) for row in saved))

    def test_whole_thinking_material_not_only_query_is_checked(self):
        f = self.f
        original = f.provider.think
        def result(*args):
            return replace(original(*args), rationale_summary=SECRET_MARKER)
        with patch.object(f.provider, 'think', side_effect=result):
            self.rejected_diagnostic(f.submit, 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(f.external_calls, 0)

    def test_newly_prohibited_completed_material_is_not_replayed_or_rewritten(self):
        f = self.f
        request = f.request()
        f.submit(request)
        before = self.files()
        f.reopen()
        def allowed(d, value):
            return not (isinstance(value, dict) and value.get('additional_memory_query') == f.query)
        with patch.object(f.external.broker, 'material_allowed', side_effect=allowed):
            self.rejected_diagnostic(lambda: f.submit(request), 'EXTERNAL_INPUT_REJECTED')
            self.rejected_diagnostic(lambda: f.app.adapter.query_request(request['requestId']), 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(before, self.files())
        self.assertEqual(f.external_calls, 1)

    def waiting(self):
        f = self.f
        f.submit()
        service = f.app.adapter._service._thinking
        perception = f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
        session = service.begin_capability_wait(perception, capability_request_id='test:waiting', think_id='test:waiting')
        return service, perception, session

    def test_wait_completion_rejects_before_resume_write_or_processing(self):
        service, perception, session = self.waiting()
        f = self.f
        f.query = 'memory:' + SECRET_MARKER
        result = f.provider.think(perception, session.token_budget)
        before = self.files()
        with patch.object(f.core, 'process_thinking') as processor:
            self.rejected_diagnostic(lambda: service.complete_capability_wait(
                perception, think_id=session.think_id, result=result, ended_at=f.runtime.clock.now(),
                result_validator=f.external.validate_thinking_material, result_processor=processor), 'EXTERNAL_INPUT_REJECTED')
            processor.assert_not_called()
        self.assertEqual(before, self.files())
        self.assertEqual(service.get_session(perception.subject_id, session.think_id).status.value, 'WAITING_CAPABILITY')

    def test_wait_completion_and_completed_replay_keep_original_result_identity(self):
        service, perception, session = self.waiting()
        f = self.f
        result = f.provider.think(perception, session.token_budget)
        options = dict(think_id=session.think_id, result=result, ended_at=f.runtime.clock.now(),
                       result_validator=f.external.validate_thinking_material)
        done = service.complete_capability_wait(perception, **options)
        before = self.files()
        replay = service.complete_capability_wait(perception, **options)
        self.assertEqual(done.session.to_dict(), replay.session.to_dict())
        self.assertEqual(before, self.files())
        with patch.object(f.external.broker, 'material_allowed', return_value=False):
            self.rejected_diagnostic(lambda: service.complete_capability_wait(perception, **options), 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(before, self.files())

    def test_optional_thinking_check_precedes_growth_and_preserves_gate_off(self):
        f = self.f
        f.core_options.update(subject_growth=True, dynamic_mind=True)
        f.reopen()
        f.query = 'memory:' + SECRET_MARKER
        state = f.state.to_dict()
        with patch.object(f.core, 'process_thinking') as processor:
            self.rejected_diagnostic(f.submit, 'EXTERNAL_INPUT_REJECTED')
            processor.assert_not_called()
        self.assertEqual(state, f.state.to_dict())
        f.disable_feature()
        with patch.object(f.external.broker, 'material_allowed', side_effect=RuntimeError(SECRET_MARKER)) as port:
            f.submit()
            port.assert_not_called()

    def test_registration_port_exceptions_are_static_and_zero_write(self):
        f = self.f
        before = self.files()
        d = replace(f.descriptors[0], version='v3', capability_ref='external.memory.v3')
        for owner, method, code in ((f.external.broker, 'material_allowed', 'EXTERNAL_MATERIAL_CHECK_UNAVAILABLE'),
                                    (f.external.broker, 'authorize_reference', 'EXTERNAL_CREDENTIAL_CHECK_UNAVAILABLE'),
                                    (f.external.permissions, 'authorize', 'EXTERNAL_PERMISSION_CHECK_UNAVAILABLE')):
            with self.subTest(port=method), patch.object(owner, method, side_effect=RuntimeError(SECRET_MARKER)):
                self.rejected_diagnostic(lambda: f.external.register(d, expected_revision=f.registry.revision), code)
            self.assertEqual(before, self.files())

    def test_selection_execution_consumption_port_exceptions_fail_closed(self):
        f = self.f
        f.submit()
        request, adapter = self.request_adapter()
        for owner, method in ((f.external.broker, 'material_allowed'), (f.external.broker, 'authorize_reference'),
                              (f.external.permissions, 'authorize')):
            for call in (lambda: f.external.register(f.descriptors[0], expected_revision=f.registry.revision),
                         lambda: adapter.execute(request), f.external.cached):
                with self.subTest(port=method), patch.object(owner, method, side_effect=RuntimeError(SECRET_MARKER)):
                    before = self.files()
                    self.rejected_diagnostic(call)
                    self.assertEqual(before, self.files())
        self.assertEqual(f.external_calls, 1)

    def test_recovery_broker_failure_is_unknown_not_permission_or_execution(self):
        f = self.f
        f.submit()
        request, adapter = self.request_adapter()
        before = self.files()
        with patch.object(f.external.broker, 'material_allowed', side_effect=RuntimeError(SECRET_MARKER)):
            self.rejected_diagnostic(lambda: adapter.query(request), 'EXTERNAL_MATERIAL_CHECK_UNAVAILABLE')
        self.assertEqual(before, self.files())
        self.assertEqual(f.external_calls, 1)

    def test_normal_permission_and_reference_denial_still_reject(self):
        f = self.f
        for control in ('permission_allowed', 'broker_allowed'):
            with self.subTest(control=control):
                f.control_change(**{control: False})
                self.rejected_diagnostic(f.submit)
                self.assertEqual(f.external_calls, 0)
                f.control_change(**{control: True})
        f.submit()
        self.assertEqual(f.external_calls, 1)

    def capability_app(self):
        from continuity_engine.domain.capability import IntegrationThinkingMode
        from continuity_engine.interfaces.local_integration_app import build_local_integration_app
        from continuity_engine.testing.p09_core_fixture import ConfirmedFixturePolicy
        def build(*args, **kwargs):
            kwargs['available_permissions'] = (*kwargs['available_permissions'], 'expression:emit', 'action:silence')
            return build_local_integration_app(*args, **kwargs, thinking_mode=IntegrationThinkingMode.CAPABILITY)
        with patch('continuity_engine.testing.p16_provider_fixture.build_local_integration_app', side_effect=build):
            self.f.reopen()
        # A plain model response uses the inherited C1 expression capability;
        # P16 query-only Fixture does not register it by default.
        self.f.core.capabilities = (*self.f.core.capabilities, *self.f.base.core.capabilities)
        self.f.core.policy = self.f.external.policy(ConfirmedFixturePolicy(self.f.constraints, self.f.core.capabilities))

    def test_c1_capability_ingress_rejects_before_original_ledger_write(self):
        from tests.test_e5_capability_flow import capability_result_payload
        f = self.f
        self.capability_app()
        required = f.submit()
        payload = capability_result_payload(required, response=SECRET_MARKER)
        before = self.files()
        self.rejected_diagnostic(lambda: f.app.adapter.submit_capability_result(payload), 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(before, self.files())
        self.assertEqual(f.external_calls, 0)
        self.assertEqual(f.app.ledger.list_capability_attempts(required.capability_request.capability_request_id), [])

    def test_c1_capability_safe_result_replay_preserves_fact_hash(self):
        from tests.test_e5_capability_flow import capability_result_payload
        f = self.f
        self.capability_app()
        request = f.request()
        required = f.submit(request)
        payload = capability_result_payload(required, response='anger, affection and private experiments are ordinary query content')
        f.runtime.clock.advance(__import__('datetime').timedelta(seconds=3))
        result = f.app.adapter.submit_capability_result(payload)
        before = self.files()
        self.capability_app()
        self.assertEqual(result.to_dict(), f.app.adapter.submit_capability_result(payload).to_dict())
        self.assertEqual(before, self.files())
        self.assertEqual(len(f.app.ledger.list_capability_attempts(required.capability_request.capability_request_id)), 1)

    def test_c1_capability_restore_rechecks_material_before_checkpoint(self):
        from tests.test_e5_capability_flow import capability_result_payload
        f = self.f
        self.capability_app()
        request = f.request()
        required = f.submit(request)
        payload = capability_result_payload(required)
        def crash(stage, operation):
            if stage == 'after_capability_result_persisted':
                raise RuntimeError('controlled interruption')
        f.app.adapter.service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.app.adapter.submit_capability_result(payload)
        self.capability_app()
        before = self.files()
        def allowed(d, value):
            return not (isinstance(value, dict) and 'contentHash' in value)
        with patch.object(f.external.broker, 'material_allowed', side_effect=allowed):
            self.rejected_diagnostic(lambda: f.submit(request), 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(before, self.files())
        self.assertEqual(len(f.app.ledger.list_capability_attempts(required.capability_request.capability_request_id)), 1)


if __name__ == '__main__':
    unittest.main()
