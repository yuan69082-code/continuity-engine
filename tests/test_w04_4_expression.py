"""Exact confirmation and expression-before-effect on the actual C1 entry."""
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.expression import ExpressionValidationError
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.testing.w02_input_fixture import capture_failure


class EntryExpressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='w44e-')
        self.root = Path(self.temp.name)
        self.f = W04EntryFixture(self.root)

    def tearDown(self):
        capture_failure(self, self.root)
        self.temp.cleanup()

    def operation(self):
        return self.f.app.ledger.load_operation(self.f.last_request['requestId'])

    def facts(self):
        return tuple((port.effect_count, port.credits) for port in self.f.ports.values())

    def test_exact_confirmation_satisfies_contact_without_erasing_required_flag(self):
        response = self.f.submit('周六选择哪家店？')
        op = self.operation()
        self.assertEqual(response.status, 'completed')
        self.assertTrue(op.domain_progress.action.decision.requires_confirmation)
        self.assertEqual(op.domain.expression.decision.status, 'SUBJECT_EXPRESSION')
        self.assertIn('EXACT_ACTION_CONFIRMATION_CHECKED', op.domain.expression.decision.reason_codes)
        self.assertEqual(self.facts(), ((1, 1), (0, 0)))
        self.assertEqual(len(self.f.provider.inputs), 1)

    def test_unconfirmed_contact_keeps_refusal_and_has_no_effect(self):
        self.f.constraints.confirmation_allowed = False
        self.f.submit('周六选择哪家店？')
        self.assertEqual(self.operation().domain.expression.decision.status, 'PLATFORM_DENIED')
        self.assertEqual(self.facts(), ((0, 0), (0, 0)))

    def test_revocation_during_presentation_prevents_delivery(self):
        original = self.f.presentation.present
        def revoked(*args):
            result = original(*args)
            self.f.constraints.confirmation_allowed = False
            return result
        self.f.presentation.present = revoked
        with self.assertRaises(IntegrationExecutionError):
            self.f.submit('周六选择哪家店？')
        self.assertEqual(self.facts(), ((0, 0), (0, 0)))

    def test_failed_presentation_precedes_native_effect(self):
        def unavailable(*args):
            raise RuntimeError('TEST_PRESENTATION_UNAVAILABLE')
        self.f.presentation.present = unavailable
        with self.assertRaises(IntegrationExecutionError):
            self.f.submit('周六选择哪家店？')
        self.assertEqual(self.facts(), ((0, 0), (0, 0)))

    def test_historical_confirmed_artifact_does_not_grant_current_consumption(self):
        self.f.submit('周六选择哪家店？')
        op = self.operation()
        thinking = self.f.app.adapter.service._restore_domain_thinking(op)
        before = (self.facts(), self.f.state.revision, len(self.f.provider.inputs))
        self.f.constraints.confirmation_allowed = False
        policy = self.f.core.expression_policy
        self.assertEqual(policy.verify(self.f.core, op, thinking, op.domain_progress.action,
                                       current=False), op.domain.expression)
        with self.assertRaises(ExpressionValidationError):
            policy.verify(self.f.core, op, thinking, op.domain_progress.action, current=True)
        self.assertEqual((self.facts(), self.f.state.revision, len(self.f.provider.inputs)), before)

    def test_saved_refusal_is_not_upgraded_when_confirmation_later_appears(self):
        self.f.constraints.confirmation_allowed = False
        self.f.submit('周六选择哪家店？')
        op = self.operation()
        thinking = self.f.app.adapter.service._restore_domain_thinking(op)
        self.f.constraints.confirmation_allowed = True
        artifact = self.f.core.expression_policy.verify(self.f.core, op, thinking,
            op.domain_progress.action, current=False)
        self.assertEqual(artifact.decision.status, 'PLATFORM_DENIED')
        self.assertEqual(artifact.content, '')
        self.assertEqual(self.facts(), ((0, 0), (0, 0)))

    def test_action_permission_refusal_is_not_overridden_by_expression_confirmation(self):
        self.f.app.adapter.service._available_permissions = ()
        self.f.submit('周六选择哪家店？')
        op = self.operation()
        self.assertFalse(op.domain_progress.action.decision.approved)
        self.assertEqual(op.domain.expression.decision.status, 'PLATFORM_DENIED')
        self.assertEqual(self.facts(), ((0, 0), (0, 0)))


if __name__ == '__main__':
    unittest.main()
