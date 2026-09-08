"""Independent P16 port-boundary probes; only disposable TEST fixtures are used."""
from dataclasses import replace
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_capability import ActionReceipt
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.testing.p16_provider_fixture import P16Fixture, SECRET_MARKER


class IndependentEdges(unittest.TestCase):
    def setUp(self):
        # Keep this shallow: nested repository fixtures approach Windows MAX_PATH.
        temp = tempfile.TemporaryDirectory(prefix='p16i-')
        self.addCleanup(temp.cleanup)
        self.f = P16Fixture(Path(temp.name))

    def secret_files(self):
        return sorted(p.relative_to(self.f.runtime.data_root).as_posix()
                      for p in self.f.runtime.data_root.rglob('*')
                      if p.is_file() and SECRET_MARKER.encode() in p.read_bytes())

    def assert_no_diagnostic_secret(self, operation):
        try:
            operation()
        except Exception as exc:
            diagnostic = ''.join(traceback.format_exception(exc))
        else:
            self.fail('A failing external port must not be silently successful')
        self.assertNotIn(SECRET_MARKER, diagnostic,
                         'Raw external-port exception reaches the normal diagnostic traceback')

    def test_positive_normal_query_still_consumes_candidate(self):
        f = self.f
        state = f.state.to_dict()
        f.submit()
        f.next_round()
        self.assertTrue(any(x.source_type == 'external_candidate' and
                            x.authority.value == 'retrieved_candidate'
                            for x in f.last_context.composition.snapshot.fragments))
        self.assertEqual(state, f.state.to_dict())
        self.assertFalse(self.secret_files())

    def test_positive_provider_result_exception_is_sanitized(self):
        f = self.f
        with patch.object(f.fake, 'read_result', side_effect=RuntimeError(SECRET_MARKER)) as port:
            self.assert_no_diagnostic_secret(f.submit)
            self.assertTrue(port.called)
        self.assertFalse(self.secret_files())

    def test_positive_ordinary_psychological_query_is_not_censored(self):
        f = self.f
        f.query = 'memory:anger, grief, disagreement and private experimental notes'
        f.submit()
        self.assertEqual(f.external_calls, 1)
        self.assertTrue(f.external.cached())
        self.assertEqual(f.core.last_action.requests[0].step.input_payload['query'], f.query[7:])

    def test_positive_safe_provider_receipt_id_remains_recoverable(self):
        f = self.f
        original_query, original_execute = f.fake.query_receipt, f.fake.execute_query
        def decorate(value):
            return replace(value, receipt_id='receipt:provider-assigned-safe') if isinstance(value, ActionReceipt) else value
        request = f.request()
        with patch.object(f.fake, 'query_receipt', side_effect=lambda r: decorate(original_query(r))), \
             patch.object(f.fake, 'execute_query', side_effect=lambda r, d: decorate(original_execute(r, d))):
            f.submit(request)
            self.assertEqual(f.external_calls, 1)
            self.assertTrue(f.external.cached())
            f.submit(request)
            self.assertEqual(f.external_calls, 1)

    def test_broker_authorization_exception_must_not_leak_in_diagnostics(self):
        f = self.f
        with patch.object(f.broker, 'authorize_reference', side_effect=RuntimeError(SECRET_MARKER)) as port:
            self.assert_no_diagnostic_secret(f.submit)
            self.assertTrue(port.called)

    def test_permission_port_exception_must_not_leak_in_diagnostics(self):
        f = self.f
        with patch.object(f.permissions, 'authorize', side_effect=RuntimeError(SECRET_MARKER)) as port:
            self.assert_no_diagnostic_secret(f.submit)
            self.assertTrue(port.called)

    def test_broker_material_exception_must_not_leak_in_diagnostics(self):
        f = self.f
        with patch.object(f.broker, 'material_allowed', side_effect=RuntimeError(SECRET_MARKER)) as port:
            self.assert_no_diagnostic_secret(f.submit)
            self.assertTrue(port.called)

    def test_secret_receipt_identifier_must_not_be_persisted_by_engine(self):
        f = self.f
        original_query = f.fake.query_receipt
        original_execute = f.fake.execute_query
        def decorate(value):
            return replace(value, receipt_id=SECRET_MARKER) if isinstance(value, ActionReceipt) else value
        with patch.object(f.fake, 'query_receipt', side_effect=lambda r: decorate(original_query(r))), \
             patch.object(f.fake, 'execute_query', side_effect=lambda r, d: decorate(original_execute(r, d))):
            try:
                f.submit()
            except IntegrationExecutionError:
                pass
        # Fake receipt storage itself is untouched: it contains its original, safe receipt.
        self.assertGreater(f.external_calls, 0)
        self.assertNotIn(SECRET_MARKER.encode(), f.fake.path.read_bytes())
        self.assertEqual([], self.secret_files(),
                         'Provider-controlled receipt bypasses the Broker material filter')

    def test_denied_external_query_is_not_copied_into_new_persistent_material(self):
        f = self.f
        f.query = 'memory:' + SECRET_MARKER
        with self.assertRaises(IntegrationExecutionError) as caught:
            f.submit()
        self.assertEqual(str(caught.exception.__cause__), 'EXTERNAL_INPUT_REJECTED')
        self.assertEqual(f.external_calls, 0)
        self.assertEqual([], self.secret_files(),
                         'Query rejected by Broker is already stored by the normal Thinking path')


if __name__ == '__main__':
    unittest.main()
