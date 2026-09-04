from pathlib import Path
import tempfile
import unittest

from continuity_engine.testing.p09_core_runner import run_golden, run_long


class P09LongRunTests(unittest.TestCase):
    def test_golden_is_repeatable_through_normal_app_without_transport(self):
        reports = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as directory:
                reports.append(run_golden(Path(directory)))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[0]["effects"], 2)
        self.assertEqual(reports[0]["formal_access_count"], 0)

    def test_thirty_logical_days_with_real_process_restarts_and_resource_invariants(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_long(Path(directory))
        self.assertEqual(report["rounds"], 30)
        self.assertEqual(report["restart_after_rounds"], [10, 20])
        samples = [o for s in report["segments"] for o in s["observations"]]
        self.assertEqual([o["round"] for o in samples], list(range(1, 31)))
        self.assertEqual(samples[-1]["effects"], 20)
        self.assertEqual(samples[-1]["credits"], 20)
        self.assertEqual(len({s["pid"] for s in report["segments"]}), 3)
        self.assertLess(max(o["data_bytes"] for o in samples), 32 * 1024 * 1024)
        self.assertTrue(all(s["formal_access_count"] == 0 for s in report["segments"]))


if __name__ == "__main__":
    unittest.main()
