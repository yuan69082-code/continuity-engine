"""Independent positive/negative neighbors for the P13 R1/R2 repair."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.p13_expression_fixture import P13Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class RepairNeighbors(unittest.TestCase):
    def fixture(self, **kw):
        temp = tempfile.TemporaryDirectory(prefix='p13-nb-')
        self.addCleanup(temp.cleanup)
        return P13Fixture(Path(temp.name), **kw)

    def grant(self, f, revoked):
        provider = f.core.action_gate._permissions
        provider._grants = [replace(g, revoked=revoked) if g.permission == 'expression:emit' else g
                            for g in provider._grants]

    def seed(self, f):
        values = {'identity.expression_preferences': ['concise', 'emphasis'],
                  'relationship.interaction_preferences': ['formal'],
                  'emotion_state.current_state': 'alert', 'emotion_state.intensity': 0.8,
                  'emotion_state.updated_at': f.runtime.clock.now().isoformat(),
                  'emotion_state.confidence': 0.9, 'emotion_state.baseline': 0.2}
        f.event('review-neighbor-styles', classification=EventClassification.STATE_CHANGE,
                mutations=[StateMutation(k, ChangeOperation.SET, v, 'Explicit isolated TEST fixture.')
                           for k, v in values.items()])

    def test_silence_does_not_need_visible_expression_grant(self):
        f = self.fixture(expression_mode='SILENCE')
        self.grant(f, True)
        request = f.request()
        self.assertEqual(f.submit(request).response.content, '')
        before = tree_inventory_hash(f.runtime.data_root)
        view = f.app.adapter.service.expression_outcome(request['requestId'])
        self.assertEqual(view['status'], 'SUBJECT_SILENCE')
        self.assertEqual(f.presentation.calls, 0)
        self.assertEqual((f.adapter.effect_count, f.adapter.credits), (0, 0))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_all_style_sources_omitted_preserves_unstyled_body(self):
        f = self.fixture(body='No agreement.\n\nStill no agreement.')
        self.seed(f)
        source = next(b.source for b in f.core.router._bindings
                      if b.source.source_id == 'engine.subject-state')
        retrieve = source.retrieve
        def omit(query):
            batch = retrieve(query)
            return replace(batch, candidates=tuple(c for c in batch.candidates
                           if c.stable_id.rsplit(':', 1)[-1] not in {'identity', 'relationship', 'emotion_state'}))
        source.retrieve = omit
        request = f.request()
        self.assertEqual(f.submit(request).response.content, f.body)
        decision = f.artifact(request).decision
        self.assertFalse(decision.compact)
        self.assertFalse(decision.emphasis)
        self.assertEqual(decision.layout, 'plain')

    def test_emotion_feature_off_does_not_add_emphasis(self):
        f = self.fixture(gates=ContinuityCoreGates(emotion_decay=False))
        self.seed(f)
        request = f.request()
        f.submit(request)
        self.assertFalse(f.artifact(request).decision.emphasis)
        self.assertEqual(f.artifact(request).content, '> ' + f.body)

    def test_original_action_confirmation_does_not_replace_expression_confirmation(self):
        f = self.fixture()
        request = f.request()
        def withdraw_exact(point, operation):
            if point == 'after_c1_action_completed':
                thinking = f.app.adapter.service._restore_domain_thinking(operation)
                access = f.core.expression_policy.authorization_request(
                    f.core, operation, thinking.perception.continuity_context,
                    thinking, operation.domain_progress.action)
                self.assertIn(access.idempotency_key, f.constraints.confirmed_ids)
                f.constraints.confirmed_ids.remove(access.idempotency_key)
        f.app.adapter.service._fault_injector = withdraw_exact
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.presentation.calls, 0)
        self.assertIsNone(f.app.ledger.load_completed(request['requestId']))
        self.assertEqual((f.adapter.effect_count, f.adapter.credits), (1, 1))

    def test_interrupted_materialization_can_recover_after_explicit_reauthorization(self):
        f = self.fixture(expression_mode='REFUSE')
        request = f.request()
        f.presentation.on_present = lambda: self.grant(f, True)
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertIsNone(f.app.ledger.load_operation(request['requestId']).domain)
        effects, credits = f.adapter.effect_count, f.adapter.credits
        self.grant(f, False)
        f.presentation.on_present = None
        f.reopen()
        self.assertEqual(f.submit(request).response.content, f.body)
        self.assertEqual(f.artifact(request).decision.mode, 'REFUSE')
        self.assertEqual((f.adapter.effect_count, f.adapter.credits), (effects, credits))
        self.assertEqual((f.adapter.execute_calls, f.provider.calls), (0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
