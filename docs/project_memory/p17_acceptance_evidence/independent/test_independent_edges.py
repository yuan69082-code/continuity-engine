"""Independent P17 edge probes using disposable local TEST worlds only."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.execution import BlastRadius
from continuity_engine.testing.p17_execution_fixture import P17Fixture


class IndependentEdges(unittest.TestCase):
    def fixture(self, **options):
        temporary = tempfile.TemporaryDirectory(prefix='p17i-')
        self.addCleanup(temporary.cleanup)
        return P17Fixture(Path(temporary.name), **options)

    def test_positive_direct_replay_has_one_effect(self):
        f = self.fixture()
        request = f.request()
        first = f.submit(request)
        self.assertEqual(first.status, 'completed')
        self.assertEqual(f.submit(request), first)
        self.assertEqual(f.fake.effect_count, 1)
        self.assertEqual(f.fake.credits, 1)

    def test_positive_initial_revoke_blocks_effect(self):
        f = self.fixture()
        f.broker.allowed = False
        with self.assertRaises(IntegrationExecutionError):
            f.submit()
        self.assertEqual(f.fake.effect_count, 0)

    def final_capacity_change(self, change):
        f = self.fixture()
        checks = []
        def hook():
            checks.append('capacity')
            # Original planner preflight, execute preflight, then the final
            # capacity check under the outbox dispatch transaction.
            if len(checks) == 3:
                change(f)
        f.boundary.hook = hook
        try:
            f.submit()
        except IntegrationExecutionError:
            pass
        self.assertEqual(len(checks), 3, 'Probe must reach the final in-transaction capacity check')
        self.assertEqual(f.fake.effect_count, 0,
                         'Authorization revoked inside the final resource check must not produce an effect')
        self.assertEqual(f.fake.credits, 0)

    def test_final_capacity_revokes_broker_before_dispatch(self):
        self.final_capacity_change(lambda f: setattr(f.broker, 'allowed', False))

    def test_final_capacity_revokes_recoverability_before_dispatch(self):
        self.final_capacity_change(lambda f: setattr(f.boundary, 'recovery_ready', False))

    def test_final_capacity_revokes_reality_permission_before_dispatch(self):
        self.final_capacity_change(lambda f: setattr(f.boundary, 'allowed', False))

    def test_credit_limit_uses_actual_effect_charge_for_zero_cost_route(self):
        f = self.fixture(limits=BlastRadius(credits=1))
        f.execution.routes = {k: replace(v, cost=0) for k,v in f.execution.routes.items()}
        f.reopen()
        self.assertEqual(f.submit().status, 'completed')
        self.assertEqual(f.fake.credits, 1)
        try:
            f.next_round()
        except IntegrationExecutionError:
            pass
        self.assertLessEqual(f.fake.credits, 1, 'The actual world charge must remain within BlastRadius.credits')
        self.assertEqual(f.fake.effect_count, 1)

    def test_revoked_result_is_excluded_without_blocking_normal_silence(self):
        f = self.fixture()
        self.assertEqual(f.submit().status, 'completed')
        f.broker.allowed = False
        f.mode = 'silence'
        result = f.next_round()
        self.assertEqual(result.status, 'completed')
        self.assertEqual(f.fake.effect_count, 1)
        self.assertFalse(any(x.source_type == 'execution_result'
                             for x in f.last_context.composition.snapshot.fragments))


if __name__ == '__main__':
    unittest.main()
