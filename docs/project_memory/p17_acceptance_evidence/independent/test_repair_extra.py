"""Additional independent checks of the P17 repair's supported local semantics."""
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.execution import BlastRadius
from continuity_engine.testing.p17_execution_fixture import P17Fixture


class RepairExtra(unittest.TestCase):
    def fixture(self, **options):
        temporary = tempfile.TemporaryDirectory(prefix='p17x-')
        self.addCleanup(temporary.cleanup)
        return P17Fixture(Path(temporary.name), **options)

    def final_change(self, change):
        f = self.fixture()
        original = f.outbox.transaction
        inside = False
        observed = []

        @contextmanager
        def transaction():
            nonlocal inside
            with original() as document:
                inside = True
                try:
                    yield document
                finally:
                    inside = False

        def hook():
            if inside:
                observed.append('final resource preparation')
                change(f)

        f.boundary.hook = hook
        with patch.object(f.outbox, 'transaction', transaction):
            with self.assertRaises(IntegrationExecutionError):
                f.submit()
        self.assertEqual(observed, ['final resource preparation'])
        self.assertEqual(f.fake.execute_calls, 0)
        self.assertEqual(f.fake.effect_count, 0)
        self.assertEqual(f.fake.credits, 0)

    def test_world_unavailable_during_final_resource_check(self):
        self.final_change(lambda f: setattr(f.boundary, 'available', False))

    def test_credential_expiry_during_final_resource_check(self):
        self.final_change(lambda f: setattr(f, 'expiry', f.runtime.clock.now()))

    def test_cost_two_estimate_does_not_replace_actual_one_credit_charge(self):
        f = self.fixture(limits=BlastRadius(credits=1))
        f.execution.routes = {k: replace(v, cost=2) for k, v in f.execution.routes.items()}
        f.reopen()
        self.assertEqual(f.submit().status, 'completed')
        self.assertEqual(f.fake.effect_count, 1)
        self.assertEqual(f.fake.credits, 1)
        before = f.fake.store.path.read_bytes()
        with self.assertRaises(IntegrationExecutionError):
            f.next_round()
        self.assertEqual(f.fake.store.path.read_bytes(), before)

    def test_effect_projection_does_not_mutate_caller_document(self):
        f = self.fixture()
        self.assertEqual(f.submit().status, 'completed')
        request, _ = f.manual()
        document = f.fake.store.load()
        before = json.dumps(document, sort_keys=True)
        file_before = f.fake.store.path.read_bytes()
        projected, receipt = f.fake.projected_document(request, document)
        self.assertEqual(json.dumps(document, sort_keys=True), before)
        self.assertEqual(f.fake.store.path.read_bytes(), file_before)
        self.assertEqual(projected['credits'], document['credits'] + receipt.test_credits)
        self.assertEqual(receipt.test_credits, 1)


if __name__ == '__main__':
    unittest.main()
