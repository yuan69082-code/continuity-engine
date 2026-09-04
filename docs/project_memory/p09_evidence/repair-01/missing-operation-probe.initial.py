"""Diagnostic only: deletion of an operation is not a genuine old-format record.

The legacy positive assumption below is intentionally preserved as the original
helper error; the normal App rejected both C1 deletions before replay.
"""
import unittest
from unittest.mock import patch
from tests.test_p09_review_regressions import P09ReviewRegressionTests as Base
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.persistence import atomic_write_json

class MissingOperationProbe(Base):
    def test_missing_operation_cannot_downgrade_c1_but_keeps_real_legacy(self):
        for mode in ("direct", "state", "legacy"):
            with self.subTest(mode=mode):
                f = self.fixture()
                if mode == "legacy":
                    f.gates = ContinuityCoreGates(enabled=False)
                    f.reopen()
                elif mode == "state":
                    self.state_writer(f)
                request = f.request()
                first = f.submit(request)
                document, item = self.raw_operation(f, request)
                document["operations"].remove(item)
                atomic_write_json(f.app.ledger.operation_path, document)
                before = self.state_inventory(f)
                if mode == "legacy":
                    f.reopen()
                    with patch.object(f.adapter, "query", side_effect=AssertionError("legacy adapter accessed")):
                        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
                else:
                    self.assert_replay_blocked(f, request, first, "MISSING_OPERATION_" + mode)
                self.assertEqual(self.state_inventory(f), before)

if __name__ == "__main__":
    unittest.main(defaultTest="MissingOperationProbe.test_missing_operation_cannot_downgrade_c1_but_keeps_real_legacy", verbosity=2)
