"""Additional P13 invariants; writes are confined to disposable TEST fixtures."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.expression import ExpressionValidationError
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification
from continuity_engine.services.context_router_service import ContextPermissionDecision
from continuity_engine.testing.p13_expression_fixture import P13Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class P13ReviewProbes(unittest.TestCase):
    def fixture(self, **options):
        temp = tempfile.TemporaryDirectory(prefix='p13-rv-')
        self.addCleanup(temp.cleanup)
        return P13Fixture(Path(temp.name), **options)

    @staticmethod
    def revoke_expression(f):
        permissions = f.core.action_gate._permissions
        permissions._grants = [replace(g, revoked=True) if g.permission == 'expression:emit' else g
                               for g in permissions._grants]
        assert any(g.permission == 'expression:emit' and g.revoked for g in permissions._grants)

    def test_revoked_expression_grant_during_presentation_blocks_new_artifact(self):
        f = self.fixture()
        request = f.request()
        f.presentation.on_present = lambda: self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertIsNone(f.app.ledger.load_completed(request['requestId']))

    def test_revoked_expression_grant_after_action_blocks_first_presentation(self):
        f = self.fixture()
        request = f.request()
        def change_permission(point, operation):
            if point == 'after_c1_action_completed':
                self.revoke_expression(f)
        f.app.adapter.service._fault_injector = change_permission
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.presentation.calls, 0)

    def test_historical_receipts_do_not_authorize_new_consumption_after_grant_revocation(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        f.reopen()
        self.revoke_expression(f)
        before = tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises((ExpressionValidationError, IntegrationExecutionError)):
            f.submit(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_omitted_relationship_source_does_not_influence_expression(self):
        f = self.fixture()
        f.event('review-formal', classification=EventClassification.STATE_CHANGE, mutations=[
            StateMutation('relationship.interaction_preferences', ChangeOperation.SET,
                          ['formal'], 'Explicit isolated review fixture preference.')])
        # A valid bounded source may omit a section. The omitted section is also
        # explicitly denied by exact-reference policy; all selected sources stay valid.
        source = next(b.source for b in f.core.router._bindings if b.source.source_id == 'engine.subject-state')
        original_retrieve = source.retrieve
        def omit_relationship(query):
            batch = original_retrieve(query)
            return replace(batch, candidates=tuple(c for c in batch.candidates
                           if not c.stable_id.endswith(':relationship')))
        source.retrieve = omit_relationship
        original_authorize = f.permission.authorize_reference
        f.permission.authorize_reference = lambda request, reference: (
            ContextPermissionDecision(False, 'REFERENCE_REVOKED', 'review-v1')
            if reference.stable_id.endswith(':relationship') else original_authorize(request, reference))
        request = f.request()
        try:
            result = f.submit(request)
        except IntegrationExecutionError:
            return  # Missing required expression basis may fail closed.
        context = f.context(request)
        self.assertFalse(any(c.stable_id.endswith(':relationship') for c in context.route.manifest.candidates))
        self.assertEqual(f.artifact(request).decision.layout, 'plain',
                         'Expression used a relationship source absent from and unauthorized for this Context')

    def test_revoked_expression_grant_before_action_control_blocks(self):
        f = self.fixture()
        self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):
            f.submit()
        self.assertEqual(f.presentation.calls, 0)
        self.assertEqual(f.adapter.effect_count, 0)

    def test_old_context_revocation_control_still_blocks(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        f.permission.references_allowed = False
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)

    def test_unchanged_restart_control_preserves_body_and_zero_new_effect(self):
        f = self.fixture(expression_mode='REFUSE')
        request = f.request()
        first = f.submit(request)
        effects, credits = f.adapter.effect_count, f.adapter.credits
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
        self.assertEqual((f.adapter.effect_count, f.adapter.credits), (effects, credits))
        self.assertEqual(f.provider.calls, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
