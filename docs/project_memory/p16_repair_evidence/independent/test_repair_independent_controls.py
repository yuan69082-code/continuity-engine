"""Additional independent repair controls, not added to Engine's official total."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_capability import ActionReceipt
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.testing.p16_provider_fixture import P16Fixture

MARKER = 'review-only-credential-class-marker-72f5'


class RepairControls(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='p16x-')
        self.addCleanup(temporary.cleanup)
        self.f = P16Fixture(Path(temporary.name))

    def files(self):
        return {p.relative_to(self.f.runtime.data_root).as_posix(): p.read_bytes()
                for p in self.f.runtime.data_root.rglob('*') if p.is_file()}

    def no_marker(self):
        self.assertEqual([], [p for p,data in self.files().items() if MARKER.encode() in data])

    @staticmethod
    def allowed(descriptor, value):
        return MARKER not in json.dumps(value, ensure_ascii=False)

    def test_alternate_prohibited_receipt_stays_unknown_without_redispatch(self):
        f = self.f
        query, execute = f.fake.query_receipt, f.fake.execute_query
        def decorate(value):
            return replace(value, receipt_id=MARKER) if isinstance(value, ActionReceipt) else value
        request = f.request()
        with patch.object(f.broker, 'material_allowed', side_effect=self.allowed), \
             patch.object(f.fake, 'query_receipt', side_effect=lambda r: decorate(query(r))), \
             patch.object(f.fake, 'execute_query', side_effect=lambda r,d: decorate(execute(r,d))):
            for _ in range(2):
                with self.assertRaises(IntegrationExecutionError):
                    f.submit(request)
                self.assertEqual(f.external_calls, 1)
                self.no_marker()
        f.submit(request)
        self.assertEqual(f.external_calls, 1)
        self.assertTrue(f.external.cached())

    def test_processor_output_is_checked_again_before_think_session_save(self):
        f = self.f
        f.core_options.update(dynamic_mind=True, subject_growth=True)
        f.reopen()
        state = f.state.to_dict()
        def process(perception, result):
            return replace(result, additional_memory_query='memory:' + MARKER)
        with patch.object(f.broker, 'material_allowed', side_effect=self.allowed), \
             patch.object(f.core, 'process_thinking', side_effect=process) as processor:
            with self.assertRaises(IntegrationExecutionError) as caught:
                f.submit()
            self.assertEqual(str(caught.exception.__cause__), 'EXTERNAL_INPUT_REJECTED')
            processor.assert_called_once()
        self.no_marker()
        self.assertEqual(f.external_calls, 0)
        self.assertEqual(state, f.state.to_dict())

    def test_non_boolean_truthy_answers_do_not_authorize(self):
        f = self.f
        d = f.descriptors[0]
        for answer in (1, 'true', ['granted']):
            for owner, method, code in (
                (f.broker, 'authorize_reference', 'EXTERNAL_CREDENTIAL_REFERENCE_DENIED'),
                (f.permissions, 'authorize', 'EXTERNAL_PERMISSION_DENIED')):
                with self.subTest(answer=answer, method=method), patch.object(owner, method, return_value=answer):
                    before = self.files()
                    with self.assertRaisesRegex(ExternalCapabilityError, code):
                        f.external.require_current(d, 'execute')
                    self.assertEqual(before, self.files())
            with patch.object(f.broker, 'material_allowed', return_value=answer):
                with self.assertRaisesRegex(ExternalCapabilityError, 'EXTERNAL_INPUT_REJECTED'):
                    f.external.validate_input_material({'query': 'ordinary allowed content'})
        self.assertEqual(f.external_calls, 0)
        f.submit()
        self.assertEqual(f.external_calls, 1)

    def test_alternate_exception_text_is_sanitized_at_registration_and_consumption(self):
        f = self.f
        f.submit()
        for owner, method in ((f.broker, 'material_allowed'), (f.broker, 'authorize_reference'),
                              (f.permissions, 'authorize')):
            for operation in (lambda: f.external.register(f.descriptors[0], expected_revision=f.registry.revision),
                              f.external.cached):
                with self.subTest(method=method), patch.object(owner, method, side_effect=RuntimeError(MARKER)):
                    before = self.files()
                    with self.assertRaises(ExternalCapabilityError) as caught:
                        operation()
                    self.assertNotIn(MARKER, ''.join(traceback.format_exception(caught.exception)))
                    self.assertEqual(before, self.files())
                    self.no_marker()
        self.assertEqual(f.external_calls, 1)
        self.assertTrue(f.external.cached())


if __name__ == '__main__':
    unittest.main()
